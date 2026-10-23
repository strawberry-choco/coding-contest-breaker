"""Shared helpers for the ccc-level-solver scripts.

Standard library only. Imported by the sibling scripts via ``import _common``
(they live in the same directory, which is on ``sys.path`` at run time).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

# Default workspace configuration, merged with a level's level.json.
DEFAULTS: dict = {
    "kind": "unknown",
    "run": ["python3", "solver.py", "{in}", "{out}"],
    "timeout": 120,
    "inputs": "inputs",
    "outputs": "outputs",
    "samples": "samples",
    "statement": None,
    "judge": {
        "command": None,   # exact/any_valid checker command (placeholders allowed)
        "scorer": None,     # optimization scorer command
        "compare": "tokens",  # exact comparison mode: tokens | lines | exact
        "atol": None,       # absolute tolerance for float answers
        "rtol": None,       # relative tolerance for float answers
        "direction": "min",  # optimization: min | max
        "metric": "score",
        "best": None,       # best-known score (optimization)
    },
    "notes": "",
}

INPUT_SUFFIXES = {".in", ".txt", ".dat", ".csv", ".input", ""}

# Repo root (this file sits at <root>/.agents/skills/ccc-level-solver/scripts/).
REPO_ROOT = Path(__file__).resolve().parents[4]


# --------------------------------------------------------------------------- #
# level.json
# --------------------------------------------------------------------------- #
def level_json_path(level_dir: Path) -> Path:
    return level_dir / "level.json"


def load_level(level_dir: Path) -> dict:
    """Load level.json, merged over DEFAULTS (missing keys fall back)."""
    cfg = json.loads(json.dumps(DEFAULTS))
    p = level_json_path(level_dir)
    if p.exists():
        data = json.loads(p.read_text(encoding="utf-8"))
        _deep_update(cfg, data)
    return cfg


def save_level(level_dir: Path, cfg: dict) -> None:
    level_json_path(level_dir).write_text(
        json.dumps(cfg, indent=2) + "\n", encoding="utf-8"
    )


def _deep_update(base: dict, over: dict) -> None:
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_update(base[key], value)
        else:
            base[key] = value


# --------------------------------------------------------------------------- #
# files
# --------------------------------------------------------------------------- #
def find_statement(level_dir: Path, cfg: dict) -> Path | None:
    """Return the problem statement path, if one can be found.

    Provided file names are authoritative: the level.json "statement" key (or
    these fallbacks) resolves names like `level-2.pdf` untouched.
    """
    if cfg.get("statement"):
        p = level_dir / cfg["statement"]
        if p.exists():
            return p
    for name in ("statement.md", "statement.txt", "statement.html",
                 "statement.pdf", "problem.md", "problem.txt", "README.md"):
        p = level_dir / name
        if p.exists():
            return p
    for pattern in ("statement*", "level-*.pdf"):
        for p in sorted(level_dir.glob(pattern)):
            if p.is_file():
                return p
    return None


def iter_inputs(level_dir: Path, cfg: dict) -> list[Path]:
    """List input files in the configured inputs directory."""
    d = level_dir / cfg["inputs"]
    if not d.exists():
        return []
    out: list[Path] = []
    for p in sorted(d.iterdir()):
        if p.is_file() and not p.name.startswith("."):
            if p.suffix.lower() in INPUT_SUFFIXES:
                out.append(p)
    return out


def output_path_for(level_dir: Path, cfg: dict, input_path: Path) -> Path:
    """Map an input file to its answer file, mirroring the provided naming.

    School track pairs files as `in_X.<ext>` / `out_X.<ext>`, so an input with
    the `in_` prefix gets its answer under the `out_` prefix with the same
    suffix (`in_level3_1.txt` -> `out_level3_1.txt`). Otherwise the shared-stem
    convention applies (`level3_1.in` -> `level3_1.out`).
    """
    name = input_path.name
    if name.lower().startswith("in_"):
        return level_dir / cfg["outputs"] / ("out_" + name[3:])
    return level_dir / cfg["outputs"] / (input_path.stem + ".out")


def sample_pairs(samples_dir: Path) -> list[tuple[Path, Path]]:
    """Pair worked-example inputs with their provided answers, verbatim names.

    Convention 1: shared stem (X.in <-> X.out).
    Convention 2: in_/out_ prefixes, any suffix (in_X.txt <-> out_X.txt).
    """
    pairs: list[tuple[Path, Path]] = []
    if not samples_dir.is_dir():
        return pairs
    for inp in sorted(samples_dir.iterdir()):
        if not inp.is_file() or inp.name.startswith("."):
            continue
        if inp.name.lower().startswith("in_"):
            out = inp.with_name("out_" + inp.name[3:])
        elif inp.suffix.lower() == ".in":
            out = inp.with_suffix(".out")
        else:
            continue
        if out.exists():
            pairs.append((inp, out))
    return pairs


# --------------------------------------------------------------------------- #
# running commands
# --------------------------------------------------------------------------- #
def venv_python() -> Path | None:
    """The repo's venv interpreter, when it exists (absolute path)."""
    p = REPO_ROOT / ".venv" / "bin" / "python"
    return p if p.exists() else None


def render(cmd: list[str], level_dir: Path, input_path: Path | None = None,
           output_path: Path | None = None, expected: Path | None = None) -> list[str]:
    """Substitute placeholders in a command list and resolve the interpreter.

    A bare ``python3``/``python`` as the first entry runs the repo's
    ``.venv/bin/python`` when it exists, so level code can import the venv's
    third-party packages. The path is absolute because commands execute with
    ``cwd`` set to the level dir; without a venv the command passes through
    untouched (system ``python3``).
    """
    mapping = {
        "{level}": str(level_dir),
        "{in}": str(input_path) if input_path is not None else "",
        "{out}": str(output_path) if output_path is not None else "",
        "{expected}": str(expected) if expected is not None else "",
    }
    rendered: list[str] = []
    for part in cmd:
        for key, value in mapping.items():
            part = part.replace(key, value)
        rendered.append(part)
    if rendered and rendered[0] in ("python3", "python"):
        venv = venv_python()
        if venv is not None:
            rendered[0] = str(venv)
    return rendered


def run_command(cmd: list[str], cwd: Path, timeout: float | None = None,
                stdin_text: str | None = None) -> tuple[int, str, str]:
    """Run a command, returning (returncode, stdout, stderr)."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            input=stdin_text,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after {timeout}s"
    except FileNotFoundError as exc:
        return 127, "", str(exc)


# --------------------------------------------------------------------------- #
# comparison
# --------------------------------------------------------------------------- #
def _tokens(text: str) -> list[str]:
    return text.split()


def trim_output(text: str) -> str:
    """Strip trailing whitespace and newlines.

    The platform's provided answers disagree about their trailing bytes — some
    end with a single `\\n`, some with a blank line, the level-1 fixture with
    none — and no level's convention is stable enough to imitate, so trailing
    newlines are insignificant by decision: every comparison trims both sides
    before looking at anything.
    """
    return text.rstrip()


def compare_outputs(candidate: str, expected: str, mode: str = "tokens",
                    atol: float | None = None, rtol: float | None = None
                    ) -> tuple[bool, str]:
    """Compare two answer texts, ignoring trailing newlines. Returns (ok, detail).

    Both sides are trimmed of trailing whitespace/newlines first (see
    trim_output), so a missing or extra final newline is never a mismatch.

    mode:
      - "exact":  byte-for-byte apart from that trailing trim
      - "lines":  line-wise, ignoring trailing whitespace per line
      - "tokens": token-wise, ignoring all whitespace runs (default)
    Float tolerance (atol/rtol) applies to numeric tokens when set.
    """
    candidate, expected = trim_output(candidate), trim_output(expected)

    if atol is not None or rtol is not None:
        ok, detail = _compare_numeric(candidate, expected, atol or 0.0, rtol or 0.0)
        if ok is not None:
            return ok, detail

    if mode == "exact":
        if candidate == expected:
            return True, "exact match"
        return False, _first_diff_line(candidate, expected)

    if mode == "lines":
        a = [ln.rstrip() for ln in candidate.split("\n")]
        b = [ln.rstrip() for ln in expected.split("\n")]
    else:  # tokens
        a = _tokens(candidate)
        b = _tokens(expected)
        if a == b:
            return True, "token match"
        return False, _first_token_diff(a, b)

    if a == b:
        return True, f"{mode} match"
    return False, _first_diff_line(candidate, expected)


def _compare_numeric(candidate: str, expected: str, atol: float, rtol: float
                     ) -> tuple[bool | None, str]:
    ca = _tokens(candidate)
    eb = _tokens(expected)
    if ca == eb:
        return True, "token match"
    if len(ca) != len(eb):
        return None, ""
    for x, y in zip(ca, eb):
        try:
            fx, fy = float(x), float(y)
        except ValueError:
            return None, ""
        if abs(fx - fy) <= max(atol, rtol * max(1.0, abs(fy))):
            continue
        return False, f"numeric mismatch: got {x}, expected {y}"
    return True, "numeric match within tolerance"


def _first_diff_line(candidate: str, expected: str) -> str:
    a = trim_output(candidate).split("\n")
    b = trim_output(expected).split("\n")
    for i in range(max(len(a), len(b))):
        av = a[i] if i < len(a) else "<missing>"
        bv = b[i] if i < len(b) else "<missing>"
        if av != bv:
            return f"first diff at line {i + 1}: got {av!r}, expected {bv!r}"
    return "differences beyond trailing whitespace"


def _first_token_diff(a: list[str], b: list[str]) -> str:
    for i in range(max(len(a), len(b))):
        av = a[i] if i < len(a) else "<missing>"
        bv = b[i] if i < len(b) else "<missing>"
        if av != bv:
            return f"first token diff at #{i + 1}: got {av!r}, expected {bv!r}"
    return "differences beyond whitespace"


# --------------------------------------------------------------------------- #
# tiny CLI helper
# --------------------------------------------------------------------------- #
def die(msg: str, code: int = 2) -> "NoReturn":
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(code)


def as_level_dir(value: str) -> Path:
    p = Path(value).expanduser().resolve()
    if not p.exists():
        die(f"level directory does not exist: {p}")
    return p


__all__ = [
    "DEFAULTS", "INPUT_SUFFIXES",
    "REPO_ROOT", "venv_python",
    "load_level", "save_level", "level_json_path",
    "find_statement", "iter_inputs", "output_path_for", "sample_pairs",
    "render", "run_command", "compare_outputs", "trim_output",
    "die", "as_level_dir",
]