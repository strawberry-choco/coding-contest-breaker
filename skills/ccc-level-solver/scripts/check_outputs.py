#!/usr/bin/env python3
"""Check a level's outputs according to the level kind in level.json.

Usage:
    python3 check_outputs.py <level_dir> [--update-best] [--quiet]

Dispatch on ``kind``:
  exact        compare outputs to sample answers (or run judge.command)
  any_valid    run judge.command (a checker) on each (input, output) pair
  optimization run judge.scorer on each output; report scores and best-known
  interactive  not supported here (use the level's interactor directly)
  unknown      cannot check; record the kind in level.json first (Phase 1)
"""
from __future__ import annotations

import argparse
from pathlib import Path

import _common as C


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _sample_pairs(level_dir: Path, cfg: dict) -> list[tuple[Path, Path]]:
    return C.sample_pairs(level_dir / cfg["samples"])


def check_exact(level_dir: Path, cfg: dict, quiet: bool) -> int:
    judge_cmd = cfg["judge"].get("command")
    pairs = _sample_pairs(level_dir, cfg)

    # 1) every real input must have an output
    missing = [p.name for p in C.iter_inputs(level_dir, cfg)
               if not C.output_path_for(level_dir, cfg, p).exists()]
    if missing:
        print(f"missing outputs for {len(missing)} input(s): {', '.join(missing[:5])}"
              + (" ..." if len(missing) > 5 else ""))
        return 1

    if not pairs:
        print("no sample answers to compare against; outputs exist for all inputs")
        print("(add samples/*.in + samples/*.out, or set judge.command, for a real check)")
        return 0

    # 2) compare each sample: preferred candidate is outputs/<stem>.out, else
    #    run the solver on the sample input into a temp file.
    fails = 0
    for inp, expected in pairs:
        cand = C.output_path_for(level_dir, cfg, inp)
        tmp = None
        if not cand.exists():
            tmp = level_dir / cfg["outputs"] / f"__sample_{inp.stem}.out"
            tmp.parent.mkdir(parents=True, exist_ok=True)
            cmd = C.render(cfg["run"], level_dir, input_path=inp, output_path=tmp)
            rc, _, err = C.run_command(cmd, cwd=level_dir)
            if rc != 0 or not tmp.exists():
                fails += 1
                print(f"  [FAIL] {inp.name}: solver run failed ({err.strip()[:120]})")
                continue
            cand = tmp

        if judge_cmd:
            cmd = C.render(judge_cmd, level_dir, input_path=inp,
                           output_path=cand, expected=expected)
            rc, out, err = C.run_command(cmd, cwd=level_dir)
            ok = rc == 0
            detail = (out.strip() or err.strip())[:160] if not ok else "checker ok"
        else:
            atol = cfg["judge"].get("atol")
            rtol = cfg["judge"].get("rtol")
            ok, detail = C.compare_outputs(
                _read(cand), _read(expected), mode=cfg["judge"].get("compare", "tokens"),
                atol=atol, rtol=rtol)
        if tmp and tmp.exists():
            tmp.unlink()
        if not ok:
            fails += 1
            print(f"  [FAIL] {inp.name}: {detail}")
        elif not quiet:
            print(f"  [ ok ] {inp.name}: {detail}")

    print(f"\nexact: {len(pairs) - fails}/{len(pairs)} samples match")
    return 1 if fails else 0


def check_any_valid(level_dir: Path, cfg: dict, quiet: bool) -> int:
    judge_cmd = cfg["judge"].get("command")
    if not judge_cmd:
        print("kind=any_valid but no judge.command (checker) is configured")
        print("write checker.py and set judge.command in level.json")
        return 2
    fails = 0
    checked = 0
    for inp in C.iter_inputs(level_dir, cfg):
        out = C.output_path_for(level_dir, cfg, inp)
        if not out.exists():
            fails += 1
            print(f"  [FAIL] {inp.name}: missing output {out.name}")
            continue
        cmd = C.render(judge_cmd, level_dir, input_path=inp, output_path=out)
        rc, sout, serr = C.run_command(cmd, cwd=level_dir)
        checked += 1
        if rc != 0:
            fails += 1
            detail = (serr.strip() or sout.strip())[:160]
            print(f"  [FAIL] {inp.name}: invalid ({detail})")
        elif not quiet:
            print(f"  [ ok ] {inp.name}: valid")

    # The checker must also accept every provided sample answer — an oracle
    # that rejects a sample is broken by definition, and the real inputs have
    # no reference to catch it (Phase 3's rule, enforced here too).
    samples = _sample_pairs(level_dir, cfg)
    for inp, expected in samples:
        cmd = C.render(judge_cmd, level_dir, input_path=inp, output_path=expected)
        rc, sout, serr = C.run_command(cmd, cwd=level_dir)
        checked += 1
        if rc != 0:
            fails += 1
            detail = (serr.strip() or sout.strip())[:160]
            print(f"  [FAIL] sample {expected.name}: checker rejects the "
                  f"provided answer ({detail})")
        elif not quiet:
            print(f"  [ ok ] sample {expected.name}: checker accepts it")

    tail = f" ({len(samples)} sample answer(s))" if samples else ""
    print(f"\nany_valid: {checked - fails}/{checked} outputs valid{tail}")
    return 1 if fails else 0


def check_optimization(level_dir: Path, cfg: dict, quiet: bool, update_best: bool) -> int:
    scorer_cmd = cfg["judge"].get("scorer")
    if not scorer_cmd:
        print("kind=optimization but no judge.scorer is configured")
        print("write scorer.py and set judge.scorer in level.json")
        return 2
    direction = cfg["judge"].get("direction", "min")
    total = 0.0
    valid = 0
    invalid = 0
    score_unit = 0.0
    scores: list[tuple[str, float]] = []
    for inp in C.iter_inputs(level_dir, cfg):
        out = C.output_path_for(level_dir, cfg, inp)
        if not out.exists():
            invalid += 1
            print(f"  [FAIL] {inp.name}: missing output")
            continue
        cmd = C.render(scorer_cmd, level_dir, input_path=inp, output_path=out)
        rc, sout, serr = C.run_command(cmd, cwd=level_dir)
        if rc != 0:
            invalid += 1
            print(f"  [FAIL] {inp.name}: invalid ({serr.strip()[:120]})")
            continue
        try:
            score = float(sout.strip().split()[0])
        except (ValueError, IndexError):
            invalid += 1
            print(f"  [FAIL] {inp.name}: scorer produced no number ({sout.strip()[:60]!r})")
            continue
        valid += 1
        total += score
        scores.append((inp.name, score))
        if not quiet:
            print(f"  [ ok ] {inp.name}: {cfg['judge'].get('metric','score')}={score:g}")

    metric = cfg["judge"].get("metric", "score")
    print(f"\noptimization ({metric}, direction={direction}): "
          f"{valid} valid, {invalid} invalid, total={total:g}")
    for name, score in scores:
        print(f"    {name}: {score:g}")

    best = cfg["judge"].get("best")
    improved = False
    if invalid == 0 and valid > 0:
        if best is None:
            improved = True
        elif direction == "min":
            improved = total < best
        else:
            improved = total > best
        if improved:
            print(f"  improved on best-known ({best!r} -> {total:g})" if best is not None
                  else f"  recorded first best-known={total:g}")
            if update_best:
                cfg["judge"]["best"] = total
                C.save_level(level_dir, cfg)
                print("  updated level.json judge.best")
        else:
            print(f"  no improvement on best-known ({best!r})")

    return 1 if invalid else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("level_dir")
    ap.add_argument("--update-best", action="store_true",
                    help="for optimization levels, store a better total in level.json")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    level_dir = C.as_level_dir(args.level_dir)
    cfg = C.load_level(level_dir)
    kind = cfg["kind"]

    if kind == "exact":
        return check_exact(level_dir, cfg, args.quiet)
    if kind == "any_valid":
        return check_any_valid(level_dir, cfg, args.quiet)
    if kind == "optimization":
        return check_optimization(level_dir, cfg, args.quiet, args.update_best)
    if kind == "interactive":
        print("interactive level: run the level's interactor directly; "
              "check_outputs.py does not handle it")
        return 2
    print(f"unknown level kind (kind={kind!r}); record it in level.json "
          f"(Phase 1 of SKILL.md)")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())