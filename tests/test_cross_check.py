"""Tests for scripts/cross_check.py — the solver-vs-oracle diff runner.

Builds throwaway level fixtures in a temp dir. Run with:  pytest -q
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / ".agents" / "skills" / "ccc-level-solver" / "scripts"

SOLVER_OK = """\
def solve(data):
    tokens = data.split()
    n = int(tokens[0])
    return str(sum(int(x) for x in tokens[1:1 + n]))
"""

ORACLE_OK = """\
from functools import reduce

def solve(data):
    tokens = data.split()
    n = int(tokens[0])
    return str(reduce(lambda a, b: a + int(b), tokens[1:1 + n], 0))
"""

ORACLE_BUGGY = """\
def solve(data):
    tokens = data.split()
    n = int(tokens[0])
    return str(sum(int(x) for x in tokens[1:1 + n]) + 1)  # deliberately wrong
"""

FUZZ_GEN = """\
def generate(rng):
    n = rng.randint(1, 5)
    nums = [rng.randint(-50, 50) for _ in range(n)]
    return f"{n}\\n{' '.join(map(str, nums))}\\n"
"""

SOLVER_CRASH = """\
def solve(data):
    if data.startswith("2"):
        raise ValueError("boom")
    tokens = data.split()
    n = int(tokens[0])
    return str(sum(int(x) for x in tokens[1:1 + n]))
"""


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "cross_check.py"), *args],
        capture_output=True, text=True,
    )


def _make_level(tmp_path: Path, *, solver: str = SOLVER_OK,
                oracle: str | None = ORACLE_OK, fuzz: str | None = None) -> Path:
    level = tmp_path / "level"
    (level / "samples").mkdir(parents=True)
    (level / "inputs").mkdir()
    (level / "level.json").write_text('{"kind": "exact"}', encoding="utf-8")
    (level / "solver.py").write_text(solver, encoding="utf-8")
    if oracle is not None:
        (level / "oracle.py").write_text(oracle, encoding="utf-8")
    if fuzz is not None:
        (level / "fuzz_gen.py").write_text(fuzz, encoding="utf-8")
    (level / "samples" / "in_example.txt").write_text("3\n1 2 3\n",
                                                      encoding="utf-8")
    (level / "samples" / "out_example.txt").write_text("6\n", encoding="utf-8")
    (level / "inputs" / "case1.in").write_text("2\n10 20\n",
                                               encoding="utf-8")
    return level


def test_agreement_over_samples_and_inputs(tmp_path: Path):
    level = _make_level(tmp_path)
    result = _run(str(level))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "CROSS-CHECK OK" in result.stdout
    assert "2 case(s)" in result.stdout  # 1 sample + 1 input


def test_disagreement_prints_counterexample(tmp_path: Path):
    level = _make_level(tmp_path, oracle=ORACLE_BUGGY)
    result = _run(str(level))
    assert result.returncode == 1
    assert "COUNTEREXAMPLE" in result.stdout
    assert "first token diff" in result.stdout
    assert "CROSS-CHECK FAILED" in result.stdout
    assert "--- solver ---" in result.stdout and "--- oracle ---" in result.stdout


def test_missing_oracle_exits_2(tmp_path: Path):
    level = _make_level(tmp_path, oracle=None)
    result = _run(str(level))
    assert result.returncode == 2
    assert "oracle.py not found" in result.stderr
    assert "BLIND" in result.stderr


def test_fuzz_cases_counted_when_generator_present(tmp_path: Path):
    level = _make_level(tmp_path, fuzz=FUZZ_GEN)
    result = _run(str(level), "--fuzz", "30", "--seed", "7")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "30 fuzz" in result.stdout
    assert "32 case(s)" in result.stdout  # 2 provided + 30 fuzz


def test_fuzz_finds_disagreement(tmp_path: Path):
    level = _make_level(tmp_path, oracle=ORACLE_BUGGY, fuzz=FUZZ_GEN)
    result = _run(str(level), "--fuzz", "30")
    assert result.returncode == 1
    assert "COUNTEREXAMPLE" in result.stdout
    assert "fuzz #" in result.stdout or "CROSS-CHECK FAILED" in result.stdout


def test_fuzz_zero_skips_generator(tmp_path: Path):
    level = _make_level(tmp_path, fuzz=FUZZ_GEN)
    result = _run(str(level), "--fuzz", "0")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "2 case(s)" in result.stdout  # fuzz disabled


def test_solver_crash_is_reported(tmp_path: Path):
    level = _make_level(tmp_path, solver=SOLVER_CRASH)
    result = _run(str(level))
    assert result.returncode == 1
    assert "solver.solve() raised" in result.stdout


# ---------------------------------------------------------------------------
# kind=any_valid — validity mode: byte/token equality is not the gate.
# ---------------------------------------------------------------------------

CHECKER_PERMUTATION = """\
import sys

def main(argv):
    inp = open(argv[1], encoding="utf-8").read().split()
    out = open(argv[2], encoding="utf-8").read().split()
    k = int(inp[0])
    nums = inp[1:1 + k]
    if len(out) != k:
        print("REJECT: wrong token count")
        return 1
    if sorted(map(int, out)) != sorted(map(int, nums)):
        print("REJECT: answer is not a permutation of the input")
        return 1
    print("OK")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
"""

SOLVER_ASC = """\
def solve(data):
    tokens = data.split()
    return " ".join(sorted(tokens[1:1 + int(tokens[0])], key=int))
"""

ORACLE_DESC = """\
def solve(data):
    tokens = data.split()
    return " ".join(sorted(tokens[1:1 + int(tokens[0])], key=int, reverse=True))
"""

ORACLE_INVALID = """\
def solve(data):
    tokens = data.split()
    return " ".join(["9"] * int(tokens[0]))  # right count, not a permutation
"""


def _make_any_valid_level(tmp_path: Path, *, solver: str = SOLVER_ASC,
                          oracle: str = ORACLE_DESC,
                          checker: str | None = CHECKER_PERMUTATION) -> Path:
    level = tmp_path / "level"
    (level / "samples").mkdir(parents=True)
    (level / "inputs").mkdir()
    (level / "level.json").write_text('{"kind": "any_valid"}',
                                      encoding="utf-8")
    (level / "solver.py").write_text(solver, encoding="utf-8")
    (level / "oracle.py").write_text(oracle, encoding="utf-8")
    if checker is not None:
        (level / "checker.py").write_text(checker, encoding="utf-8")
    (level / "samples" / "in_example.txt").write_text("3\n3 1 2\n",
                                                      encoding="utf-8")
    (level / "samples" / "out_example.txt").write_text("1 2 3\n",
                                                       encoding="utf-8")
    (level / "inputs" / "case1.in").write_text("4\n4 2 7 1\n",
                                               encoding="utf-8")
    return level


def test_any_valid_accepts_differing_valid_answers(tmp_path: Path):
    """Solver and oracle return different-but-valid answers: must PASS."""
    level = _make_any_valid_level(tmp_path)
    result = _run(str(level))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "mode: validity" in result.stdout
    assert "both pass checker.py" in result.stdout
    assert "identical answers on 0 case(s)" in result.stdout


def test_any_valid_rejects_invalid_answer(tmp_path: Path):
    level = _make_any_valid_level(tmp_path, oracle=ORACLE_INVALID)
    result = _run(str(level))
    assert result.returncode == 1
    assert "oracle answer rejected by checker" in result.stdout
    assert "not a permutation" in result.stdout
    assert "CROSS-CHECK FAILED" in result.stdout


def test_any_valid_requires_checker(tmp_path: Path):
    level = _make_any_valid_level(tmp_path, checker=None)
    result = _run(str(level))
    assert result.returncode == 3
    assert "needs checker.py" in result.stderr
