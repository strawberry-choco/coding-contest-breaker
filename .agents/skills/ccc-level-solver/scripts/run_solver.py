#!/usr/bin/env python3
"""Run a level's solver over every input file, writing outputs.

Usage:
    python3 run_solver.py <level_dir> [--only NAME] [--timeout SECONDS] [--quiet]

Reads level.json for the run command (default: python3 solver.py {in} {out})
and the per-input timeout in seconds (level.json "timeout" key, default 120;
--timeout overrides).
For each file in inputs/, runs the command with cwd = level_dir and writes the
answer to outputs/ under the provided naming: in_X.<ext> -> out_X.<ext>,
otherwise X.in -> X.out. Prints per-file status and a summary, and
exits non-zero if any run failed.
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import _common as C


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("level_dir")
    ap.add_argument("--only", default=None,
                    help="run only inputs whose stem contains this substring")
    ap.add_argument("--timeout", type=float, default=None,
                    help="per-input timeout in seconds")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    level_dir = C.as_level_dir(args.level_dir)
    cfg = C.load_level(level_dir)
    timeout = args.timeout if args.timeout is not None else cfg.get("timeout")

    inputs = C.iter_inputs(level_dir, cfg)
    if args.only:
        inputs = [p for p in inputs if args.only in p.stem]
    if not inputs:
        C.die(f"no input files found in {level_dir / cfg['inputs']}")

    (level_dir / cfg["outputs"]).mkdir(parents=True, exist_ok=True)

    failures = 0
    total_time = 0.0
    for inp in inputs:
        out = C.output_path_for(level_dir, cfg, inp)
        tmp = out.with_name(f".tmp-{out.name}")
        cmd = C.render(cfg["run"], level_dir, input_path=inp, output_path=tmp)
        start = time.perf_counter()
        rc, stdout, stderr = C.run_command(cmd, cwd=level_dir, timeout=timeout)
        elapsed = time.perf_counter() - start
        total_time += elapsed

        if rc == 0 and tmp.exists():
            tmp.replace(out)
            if not args.quiet:
                print(f"  [ok] {inp.name} -> {out.name}  ({elapsed:.3f}s)")
        else:
            failures += 1
            tmp.unlink(missing_ok=True)
            detail = stderr.strip().splitlines()[-1] if stderr.strip() else ""
            print(f"  [FAIL] {inp.name}  {'timeout' if rc == 124 else f'rc={rc}'}  "
                  f"{'kept previous output; ' if out.exists() else 'no output written; '}"
                  f"{detail}")

    print(f"\n{len(inputs) - failures}/{len(inputs)} ok in {total_time:.3f}s "
          f"(outputs in {level_dir / cfg['outputs']})")
    if failures:
        print("some inputs failed; fix the solver or level.json run command")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())