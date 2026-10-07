#!/usr/bin/env python3
"""Prepare a level directory for the ccc-level-solver workflow.

Usage:
    python3 scaffold_level.py <level_dir> [--import <src_dir>] [--kind KIND]
                              [--force]

Creates the standard workspace (inputs/, samples/, outputs/, tests/, notes/),
writes a starter level.json, and copies solver/test templates if absent.

With --import, a flat downloaded folder is normalized: an input file that has a
sibling ``.out`` with the same base name becomes a sample pair (copied to
samples/); everything else input-like is copied to inputs/.

Idempotent: existing files are left alone unless --force is given.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import _common as C

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"

INPUT_SUFFIXES = {".in", ".txt", ".dat", ".csv", ".input", ""}
OUTPUT_SUFFIXES = {".out", ".ans", ".answer"}


def _maybe_copy(src: Path, dst: Path, force: bool) -> bool:
    if dst.exists() and not force:
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def ensure_structure(level_dir: Path) -> list[str]:
    created: list[str] = []
    for sub in ("inputs", "samples", "outputs", "tests", "notes", "verifier"):
        d = level_dir / sub
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            created.append(sub + "/")
    return created


def starter_level_json(kind: str) -> dict:
    cfg = C.load_level(Path("/nonexistent"))  # defaults only
    cfg["kind"] = kind
    cfg["run"] = ["python3", "solver.py", "{in}", "{out}"]
    if kind in ("any_valid",):
        # any_valid checks real inputs, which have no reference answer, so the
        # checker is invoked with just (input, output).
        cfg["judge"]["command"] = ["python3", "checker.py", "{in}", "{out}"]
    elif kind == "optimization":
        cfg["judge"]["scorer"] = ["python3", "scorer.py", "{in}", "{out}"]
        cfg["judge"]["direction"] = "min"
        cfg["judge"]["best"] = None
    elif kind == "exact":
        cfg["judge"]["command"] = None  # built-in token comparison
    return cfg


def import_flat(src: Path, level_dir: Path, force: bool) -> tuple[int, int]:
    """Normalize a flat download folder. Returns (#inputs, #samples)."""
    n_in = n_sample = 0
    candidates = [p for p in sorted(src.iterdir()) if p.is_file()
                  and not p.name.startswith(".")]
    for p in candidates:
        suffix = p.suffix.lower()
        if suffix in OUTPUT_SUFFIXES:
            continue  # handled alongside its .in
        if suffix not in INPUT_SUFFIXES:
            # verifier-ish artifacts
            name = p.name.lower()
            if name.endswith((".html", ".js", ".py")) and (
                "check" in name or "visual" in name or "verif" in name or "scor" in name
            ):
                _maybe_copy(p, level_dir / "verifier" / p.name, force)
            elif name.endswith((".md", ".pdf")) or name.startswith("statement"):
                _maybe_copy(p, level_dir / p.name, force)
            continue
        sibling_out = None
        for out_suffix in OUTPUT_SUFFIXES:
            cand = p.with_suffix(out_suffix)
            if cand.exists():
                sibling_out = cand
                break
        if sibling_out is not None:
            _maybe_copy(p, level_dir / "samples" / p.name, force)
            _maybe_copy(sibling_out, level_dir / "samples" / sibling_out.name, force)
            n_sample += 1
        else:
            _maybe_copy(p, level_dir / "inputs" / p.name, force)
            n_in += 1
    return n_in, n_sample


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("level_dir")
    ap.add_argument("--import", dest="src", default=None,
                    help="flat downloaded folder to normalize into the level dir")
    ap.add_argument("--kind", default="unknown",
                    choices=["unknown", "exact", "any_valid", "optimization", "interactive"])
    ap.add_argument("--force", action="store_true",
                    help="overwrite existing files")
    args = ap.parse_args(argv)

    level_dir = Path(args.level_dir).expanduser().resolve()
    level_dir.mkdir(parents=True, exist_ok=True)

    created = ensure_structure(level_dir)
    if created:
        print(f"created: {', '.join(created)}")

    if args.src:
        src = Path(args.src).expanduser().resolve()
        if not src.is_dir():
            C.die(f"--import source is not a directory: {src}")
        n_in, n_sample = import_flat(src, level_dir, args.force)
        print(f"imported {n_in} input(s), {n_sample} sample pair(s) from {src}")

    # level.json
    lj = C.level_json_path(level_dir)
    if not lj.exists() or args.force:
        C.save_level(level_dir, starter_level_json(args.kind))
        print(f"wrote {lj.name} (kind={args.kind})")
    else:
        print(f"kept existing {lj.name}")

    # templates
    copies = [
        (TEMPLATES / "solver.py.tmpl", level_dir / "solver.py"),
        (TEMPLATES / "test_level.py.tmpl", level_dir / "tests" / "test_level.py"),
    ]
    if args.kind in ("any_valid", "optimization"):
        copies.append((TEMPLATES / "checker.py.tmpl", level_dir / "checker.py"))
    if args.kind == "optimization":
        copies.append((TEMPLATES / "scorer.py.tmpl", level_dir / "scorer.py"))

    for src_t, dst in copies:
        if src_t.exists() and _maybe_copy(src_t, dst, args.force):
            print(f"scaffolded {dst.relative_to(level_dir)}")

    print("\nnext: run detect_level.py, read the statement, define the oracle (Phase 2).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())