#!/usr/bin/env python3
"""Run a level's solver over every input file, writing outputs.

Usage:
    python3 run_solver.py <level_dir> [--only NAME] [--timeout SECONDS] [--quiet]

Reads level.json for the run command (default: python3 solver.py {in} {out}).
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
        cmd = C.render(cfg["run"], level_dir, input_path=inp, output_path=out)
        start = time.perf_counter()
        rc, stdout, stderr = C.run_command(cmd, cwd=level_dir, timeout=args.timeout)
        elapsed = time.perf_counter() - start
        total_time += elapsed

        made = out.exists()
        status = "ok" if (rc == 0 and made) else "FAIL"
        if status == "ok" and not args.quiet:
            print(f"  [{status}] {inp.name} -> {out.name}  ({elapsed:.3f}s)")
        elif status != "ok":
            failures += 1
            detail = stderr.strip().splitlines()[-1] if stderr.strip() else ""
            print(f"  [{status}] {inp.name}  rc={rc}  "
                  f"{'no output written; ' if not made else ''}{detail}")

    print(f"\n{len(inputs) - failures}/{len(inputs)} ok in {total_time:.3f}s "
          f"(outputs in {level_dir / cfg['outputs']})")
    if failures:
        print("some inputs failed; fix the solver or level.json run command")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())