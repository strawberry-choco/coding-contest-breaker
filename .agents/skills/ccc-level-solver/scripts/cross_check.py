#!/usr/bin/env python3
"""Cross-check a level's solver against an independently formulated oracle.

Usage:
    python3 cross_check.py <level_dir> [--fuzz N] [--seed S]

Convention: the level directory contains

  solver.py    the (possibly wrong) solver — exposes solve(data) -> str
  oracle.py    an independently formulated implementation — solve(data) -> str.
               Write it BLIND: from the statement and notes/spec.md only, never
               by reading solver.py (a fresh-context subagent run is the
               intended author). Formulation independence is the whole point —
               same-author unit tests confirm a solver instead of testing it.
  checker.py   the level's oracle/checker (required for kind=any_valid)
  fuzz_gen.py  optional — exposes generate(rng) -> str returning one random
               input text, for small randomized cases.

The runner feeds samples, real inputs, and fuzz cases to both modules. The
gate depends on the level kind (auto-detected from level.json):

  exact / optimization / unknown — token-compares the answers
      (mode from level.json "judge.compare"). On the first disagreement it
      prints a concrete COUNTEREXAMPLE (input + both answers) and exits 1 —
      a counterexample is a certificate; "looks right" is not.

  any_valid — VALIDITY mode: the level accepts many different answers, so
      byte/token equality would flag legitimate multiple-solution answers as
      fake counterexamples. Instead both the solver's and the oracle's answer
      must pass checker.py. Differing-but-both-valid is success (reported as
      a note); the first rejected answer is a counterexample naming the side
      and the checker's reason.

Exit codes: 0 pass, 1 counterexample/crash, 2 oracle/checker missing,
3 bad usage.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import random
import signal
import sys
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C  # noqa: E402

MAX_INPUT_ECHO_LINES = 40
_THIS_FILE = Path(__file__).resolve()


def _reexec_under_venv() -> None:
    """Continue under the repo's venv interpreter when one exists.

    solver.py and oracle.py are imported in-process, so they can only use the
    packages the running interpreter has — and level code is allowed to import
    the venv's third-party packages. Re-exec transparently (same pid, exit
    codes preserved) unless we are already on the venv python.
    """
    venv = C.venv_python()
    if venv is None:
        return
    try:
        if Path(sys.executable).resolve() == venv.resolve():
            return
        os.execv(str(venv), [str(venv), str(_THIS_FILE), *sys.argv[1:]])
    except OSError:
        pass  # broken venv — fall through and run as-is


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _echo(text: str) -> str:
    """Echo an input text, truncated for readability."""
    lines = text.split("\n")
    if len(lines) <= MAX_INPUT_ECHO_LINES:
        return text.rstrip("\n")
    head = "\n".join(lines[:MAX_INPUT_ECHO_LINES // 2])
    tail = "\n".join(lines[-(MAX_INPUT_ECHO_LINES // 2):])
    return f"{head}\n... ({len(lines)} lines total) ...\n{tail}"


class _Timeout(Exception):
    """Raised when a per-case solve exceeds its wall-clock bound."""


def _run_with_deadline(fn, seconds: float | None, label: str):
    """Call fn() with a wall-clock bound (no-op without SIGALRM / 0 disables).

    A level's oracle may legitimately be slow; without a bound an in-process
    solve can stall the whole gate silently.
    """
    if seconds is None or seconds <= 0 or not hasattr(signal, "SIGALRM"):
        return fn()

    def _handler(signum, frame):  # noqa: ARG001
        raise _Timeout(f"{label} exceeded {seconds:g}s")

    old = signal.signal(signal.SIGALRM, _handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        return fn()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def _passes_checker(checker_py: Path, data: str, answer: str) -> str | None:
    """Run checker.py on one answer; None if accepted, reason if rejected."""
    with tempfile.TemporaryDirectory() as td:
        inp = Path(td) / "input.txt"
        out = Path(td) / "answer.txt"
        inp.write_text(data, encoding="utf-8")
        out.write_text(answer, encoding="utf-8")
        rc, stdout, stderr = C.run_command(
            [sys.executable, str(checker_py), str(inp), str(out)],
            cwd=checker_py.parent, timeout=120)
    if rc == 0:
        return None
    detail = (stdout or stderr).strip().splitlines()
    return detail[-1] if detail else "checker produced no output"


def _run_case(solver, oracle, label: str, data: str,
              compare_mode: str, atol, rtol,
              checker_py: Path | None = None, timeout: float | None = None):
    """Run one case; return (counterexample_report | None, identical_bool)."""
    try:
        got = _run_with_deadline(lambda: solver.solve(data), timeout,
                                 "solver.solve")
    except Exception:
        return (f"COUNTEREXAMPLE {label}: solver.solve() raised\n"
                + traceback.format_exc(limit=3)), False
    try:
        want = _run_with_deadline(lambda: oracle.solve(data), timeout,
                                  "oracle.solve")
    except Exception:
        return (f"COUNTEREXAMPLE {label}: oracle.solve() raised\n"
                + traceback.format_exc(limit=3)), False

    if checker_py is not None:  # validity mode (any_valid)
        for who, answer in (("solver", got), ("oracle", want)):
            reason = _passes_checker(checker_py, data, answer)
            if reason is not None:
                return (f"COUNTEREXAMPLE {label}: {who} answer rejected by "
                        f"checker: {reason}\n"
                        f"--- input ---\n{_echo(data)}\n"
                        f"--- {who} answer ---\n{answer.rstrip()}\n"), False
        return None, C.compare_outputs(got, want, mode="tokens")[0]

    ok, detail = C.compare_outputs(got, want, mode=compare_mode,
                                   atol=atol, rtol=rtol)
    if ok:
        return None, True
    return (f"COUNTEREXAMPLE {label}: {detail}\n"
            f"--- input ---\n{_echo(data)}\n"
            f"--- solver ---\n{got.rstrip()}\n"
            f"--- oracle ---\n{want.rstrip()}\n"), False


def main(argv: list[str]) -> int:
    _reexec_under_venv()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("level_dir")
    ap.add_argument("--fuzz", type=int, default=200,
                    help="fuzz cases when fuzz_gen.py exists (0 disables)")
    ap.add_argument("--seed", type=int, default=0, help="fuzz rng seed")
    ap.add_argument("--timeout", type=float, default=600.0,
                    help="per-case wall-clock bound for solver.solve and "
                         "oracle.solve, seconds (0 disables)")
    args = ap.parse_args(argv[1:])

    level = C.as_level_dir(args.level_dir)
    cfg = C.load_level(level)

    solver_py = level / "solver.py"
    oracle_py = level / "oracle.py"
    checker_py = level / "checker.py"
    if not solver_py.exists():
        C.die(f"{solver_py} not found", 3)
    if not oracle_py.exists():
        print(f"error: {oracle_py} not found — write it BLIND (statement + "
              f"notes/spec.md only, never solver.py) before cross-checking",
              file=sys.stderr)
        return 2

    kind = cfg.get("kind", "unknown")
    validity_mode = kind == "any_valid"
    if validity_mode and not checker_py.exists():
        C.die("kind=any_valid needs checker.py: token comparison would flag "
              "legitimate multiple-solution answers as counterexamples", 3)

    solver = _load_module(solver_py, "level_solver")
    oracle = _load_module(oracle_py, "level_oracle")

    mode = cfg["judge"].get("compare", "tokens")
    atol = cfg["judge"].get("atol")
    rtol = cfg["judge"].get("rtol")

    cases: list[tuple[str, str]] = []
    for inp, _expected in C.sample_pairs(level / cfg["samples"]):
        cases.append((f"sample {inp.name}", inp.read_text(encoding="utf-8")))
    for inp in C.iter_inputs(level, cfg):
        cases.append((f"input {inp.name}", inp.read_text(encoding="utf-8")))

    fuzz_py = level / "fuzz_gen.py"
    n_fuzz = 0
    if args.fuzz > 0 and fuzz_py.exists():
        gen = _load_module(fuzz_py, "level_fuzz_gen")
        rng = random.Random(args.seed)
        for i in range(args.fuzz):
            cases.append((f"fuzz #{i + 1} (seed {args.seed})",
                          gen.generate(rng)))
        n_fuzz = args.fuzz
    elif args.fuzz > 0:
        print(f"note: no fuzz_gen.py — running provided cases only "
              f"({len(cases)} so far)")

    if validity_mode:
        print(f"mode: validity (kind=any_valid — both answers must pass "
              f"checker.py; differing-but-valid is success)")
    failures: list[str] = []
    identical = 0
    for label, data in cases:
        bad, same = _run_case(solver, oracle, label, data, mode, atol, rtol,
                              checker_py=checker_py if validity_mode else None,
                              timeout=args.timeout)
        if bad:
            failures.append(bad)
        if same:
            identical += 1

    if failures:
        print("\n".join(failures))
        print(f"CROSS-CHECK FAILED: {len(failures)} of {len(cases)} case(s) "
              f"disagree")
        return 1
    gate = ("solver and oracle both pass checker.py"
            if validity_mode else "solver and oracle agree")
    extra = (f"; identical answers on {identical} case(s) "
             f"(differences are fine — any valid answer is accepted)"
             if validity_mode else "")
    print(f"CROSS-CHECK OK: {gate} on {len(cases)} case(s) "
          f"(samples + inputs"
          + (f" + {n_fuzz} fuzz" if n_fuzz else "") + f"){extra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
