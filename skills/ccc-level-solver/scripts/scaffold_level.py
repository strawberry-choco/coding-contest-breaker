#!/usr/bin/env python3
"""Prepare a level directory for the ccc-level-solver workflow.

Usage:
    python3 scaffold_level.py <level_dir> [--import <src_dir>] [--kind KIND]
                              [--force]

Creates the standard workspace (inputs/, samples/, outputs/, tests/, notes/),
writes a starter level.json, and copies solver/test templates if absent.

With --import, a flat downloaded folder is normalized: an input file that has a
sibling answer file becomes a sample pair (moved to samples/); everything else
input-like is moved to inputs/. Provided file names are kept verbatim — the
platform's naming is the truth. Two pairing conventions are recognized:

  * shared stem, paired suffixes:  X.in <-> X.out
  * in_/out_ prefixes:             in_X.txt <-> out_X.txt   (School track)

**It moves, it does not copy.** The documented flow passes the level dir as
both arguments when the download already sits there flat, and copying would
leave a second, silently drifting twin of every provided file at the level
root next to the workspace copies. Moving keeps one copy of each file.

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
    """Copy a template into the workspace (the source is the skill's own file)."""
    if dst.exists() and not force:
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def _maybe_move(src: Path, dst: Path, force: bool) -> bool:
    """Move a provided file into the workspace under its verbatim name.

    Returns False when there is nothing to do: the file already sits at the
    destination (the flat download was the level dir itself), or the
    destination exists and --force was not given.
    """
    if src.resolve() == dst.resolve():
        return False  # already in place
    if dst.exists() and not force:
        print(f"  left {src.name} in place: {dst} already exists "
              f"(pass --force to overwrite it)")
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
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


def _pair_sibling(p: Path) -> Path | None:
    """The answer file paired with an input (or vice versa), if one exists.

    Convention 1: shared stem with a paired suffix (X.in <-> X.out).
    Convention 2: in_/out_ prefixes with any suffix (in_X.txt <-> out_X.txt).
    """
    if p.suffix.lower() in INPUT_SUFFIXES:
        for out_suffix in OUTPUT_SUFFIXES:
            cand = p.with_suffix(out_suffix)
            if cand.exists():
                return cand
    low = p.name.lower()
    if low.startswith("in_"):
        cand = p.with_name("out_" + p.name[3:])
        if cand.exists():
            return cand
    if low.startswith("out_"):
        cand = p.with_name("in_" + p.name[4:])
        if cand.exists():
            return cand
    return None


def import_flat(src: Path, level_dir: Path, force: bool) -> tuple[int, int]:
    """Normalize a flat download folder, moving the files. Returns (#in, #samples)."""
    n_in = n_sample = 0
    candidates = [p for p in sorted(src.iterdir()) if p.is_file()
                  and not p.name.startswith(".")]
    for p in candidates:
        if not p.exists():
            continue  # moved already, together with its paired sibling
        suffix = p.suffix.lower()
        if p.name.lower().startswith("out_"):
            # An answer file is only meaningful next to its input, never an
            # input itself; its pairing is handled when the input is seen.
            if _pair_sibling(p) is None:
                print(f"  skipped {p.name}: answer file with no matching input")
            continue
        if suffix not in INPUT_SUFFIXES:
            # verifier-ish artifacts
            name = p.name.lower()
            if name.endswith((".html", ".js", ".py")) and (
                "check" in name or "visual" in name or "verif" in name or "scor" in name
            ):
                _maybe_move(p, level_dir / "verifier" / p.name, force)
            elif name.endswith((".md", ".pdf")) or name.startswith("statement"):
                _maybe_move(p, level_dir / p.name, force)
            continue
        sibling = _pair_sibling(p)
        if sibling is not None:
            # Provided names are kept verbatim, in samples/ too.
            _maybe_move(p, level_dir / "samples" / p.name, force)
            _maybe_move(sibling, level_dir / "samples" / sibling.name, force)
            n_sample += 1
        else:
            _maybe_move(p, level_dir / "inputs" / p.name, force)
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
        print(f"imported {n_in} input(s), {n_sample} sample pair(s) from {src} "
              f"(moved)")

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

    print("\nnext: study the parsed inputs and persist findings to notes/inputs.md "
          "(Phase 0), then identify the kind (Phase 1).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())