"""Tests for the ccc-level-solver helper scripts.

Uses a copy of ``examples/level1`` in a temp dir so the repo example is never
mutated. Run with:  pytest -q
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "ccc-level-solver" / "scripts"
EXAMPLE = ROOT / "examples" / "level1"

sys.path.insert(0, str(SCRIPTS))
import _common as C  # noqa: E402


def _run(script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        capture_output=True, text=True,
    )


@pytest.fixture()
def level_dir(tmp_path: Path) -> Path:
    dst = tmp_path / "level1"
    shutil.copytree(EXAMPLE, dst)
    return dst


# --------------------------------------------------------------------------- #
# _common.compare_outputs
# --------------------------------------------------------------------------- #
def test_compare_tokens_ignores_whitespace():
    ok, _ = C.compare_outputs("1 2\n3\n", "1  2 3")
    assert ok


def test_compare_reports_first_diff():
    ok, detail = C.compare_outputs("1 2 4", "1 2 3")
    assert not ok
    assert "4" in detail and "3" in detail


def test_compare_lines():
    ok, _ = C.compare_outputs("a  \nb", "a\nb", mode="lines")
    assert ok


def test_compare_numeric_tolerance():
    ok, _ = C.compare_outputs("0.3333", "0.33333333", atol=1e-3)
    assert ok
    ok, _ = C.compare_outputs("0.5", "0.33333333", atol=1e-6)
    assert not ok


# --------------------------------------------------------------------------- #
# Phase 0 detection
# --------------------------------------------------------------------------- #
def test_detect_level_classifies_exact(level_dir: Path):
    result = _run("detect_level.py", str(level_dir))
    assert result.returncode == 0
    assert "suggested kind: exact" in result.stdout


def test_detect_level_write_updates_level_json(level_dir: Path):
    (level_dir / "level.json").write_text('{"kind": "unknown"}', encoding="utf-8")
    result = _run("detect_level.py", str(level_dir), "--write")
    assert result.returncode == 0
    assert C.load_level(level_dir)["kind"] == "exact"


# --------------------------------------------------------------------------- #
# run_solver + check_outputs end to end
# --------------------------------------------------------------------------- #
def test_run_solver_produces_outputs(level_dir: Path):
    result = _run("run_solver.py", str(level_dir))
    assert result.returncode == 0, result.stdout + result.stderr
    assert (level_dir / "outputs" / "level1_1.out").read_text().strip() == "150"
    assert (level_dir / "outputs" / "level1_2.out").read_text().strip() == "42"


def test_check_outputs_exact_passes(level_dir: Path):
    _run("run_solver.py", str(level_dir))
    result = _run("check_outputs.py", str(level_dir))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1/1 samples match" in result.stdout


def test_check_outputs_detects_wrong_answer(level_dir: Path):
    _run("run_solver.py", str(level_dir))
    # corrupt the candidate that should match sample_1 (expected answer: 6)
    (level_dir / "outputs" / "sample_1.out").write_text("999\n", encoding="utf-8")
    result = _run("check_outputs.py", str(level_dir))
    assert result.returncode == 1


def test_check_outputs_unknown_kind(level_dir: Path):
    (level_dir / "level.json").write_text('{"kind": "unknown"}', encoding="utf-8")
    result = _run("check_outputs.py", str(level_dir))
    assert result.returncode == 3


# --------------------------------------------------------------------------- #
# scaffold
# --------------------------------------------------------------------------- #
def test_scaffold_import_normalizes_flat_download(tmp_path: Path):
    src = tmp_path / "download"
    src.mkdir()
    (src / "level2_1.in").write_text("1\n5\n")
    (src / "level2_2.in").write_text("1\n7\n")
    (src / "level2_2.out").write_text("7\n")  # worked example
    (src / "visualizer.html").write_text("<html></html>")
    (src / "statement.md").write_text("# Level 2")

    dst = tmp_path / "level2"
    result = _run("scaffold_level.py", str(dst), "--import", str(src), "--kind", "optimization")
    assert result.returncode == 0, result.stdout + result.stderr

    assert (dst / "inputs" / "level2_1.in").exists()
    # level2_2 has a sibling .out -> sample
    assert (dst / "samples" / "level2_2.in").exists()
    assert (dst / "samples" / "level2_2.out").exists()
    assert (dst / "verifier" / "visualizer.html").exists()
    assert (dst / "scorer.py").exists()
    assert (dst / "checker.py").exists()
    assert C.load_level(dst)["kind"] == "optimization"