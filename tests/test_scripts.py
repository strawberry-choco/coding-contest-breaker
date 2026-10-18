"""Tests for the ccc-level-solver helper scripts.

Uses a copy of ``examples/level1`` in a temp dir so the repo example is never
mutated. Run with:  pytest -q
"""
from __future__ import annotations

import json
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
# _common.compare_outputs — trailing bytes are insignificant
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


def test_compare_lines_ignores_trailing_blank_lines():
    """The platform's own answers disagree about trailing newlines."""
    ok, _ = C.compare_outputs("a\nb\n\n\n", "a\nb", mode="lines")
    assert ok


def test_compare_exact_ignores_trailing_newline():
    ok, _ = C.compare_outputs("12\n", "12", mode="exact")
    assert ok
    ok, _ = C.compare_outputs("12", "12\n\n", mode="exact")
    assert ok


def test_compare_exact_still_catches_an_internal_diff():
    ok, detail = C.compare_outputs("1 2\n3\n", "1 2\n4\n", mode="exact")
    assert not ok
    assert "4" in detail and "3" in detail


def test_trim_output_strips_trailing_whitespace():
    assert C.trim_output("a\nb \n\n") == "a\nb"


def test_compare_numeric_tolerance():
    ok, _ = C.compare_outputs("0.3333", "0.33333333", atol=1e-3)
    assert ok
    ok, _ = C.compare_outputs("0.5", "0.33333333", atol=1e-6)
    assert not ok


# --------------------------------------------------------------------------- #
# interpreter resolution — level code may import the venv's packages
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(C.venv_python() is None, reason="repo venv not present")
def test_render_runs_bare_python_under_the_repo_venv():
    cmd = C.render(["python3", "solver.py", "{in}", "{out}"],
                   Path("/tmp/level"), input_path=Path("/tmp/level/a.txt"),
                   output_path=Path("/tmp/level/b.txt"))
    assert cmd[0] == str(C.venv_python())
    assert cmd[1:] == ["solver.py", "/tmp/level/a.txt", "/tmp/level/b.txt"]


def test_render_without_venv_keeps_bare_python(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(C, "REPO_ROOT", tmp_path)
    assert C.render(["python3", "solver.py"], tmp_path) == ["python3", "solver.py"]


def test_render_leaves_non_python_commands_alone():
    cmd = C.render(["pdftoppm", "-r", "300", "x.pdf"], Path("/tmp/level"))
    assert cmd == ["pdftoppm", "-r", "300", "x.pdf"]


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


def _write_any_valid_level(tmp_path: Path, accept_sample: bool) -> Path:
    """A minimal any_valid level: a checker that accepts exactly "OK"."""
    lvl = tmp_path / "lvl"
    for sub in ("inputs", "samples", "outputs"):
        (lvl / sub).mkdir(parents=True)
    (lvl / "inputs" / "in_a.txt").write_text("1\n", encoding="utf-8")
    (lvl / "outputs" / "out_a.txt").write_text("OK\n", encoding="utf-8")
    (lvl / "samples" / "in_b.txt").write_text("1\n", encoding="utf-8")
    (lvl / "samples" / "out_b.txt").write_text(
        "OK\n" if accept_sample else "BAD\n", encoding="utf-8")
    (lvl / "checker.py").write_text(
        "import sys\n"
        "print('ok' if open(sys.argv[2]).read().strip() == 'OK' else 'bad')\n"
        "sys.exit(0 if open(sys.argv[2]).read().strip() == 'OK' else 1)\n",
        encoding="utf-8")
    (lvl / "level.json").write_text(json.dumps({
        "kind": "any_valid",
        "judge": {"command": ["python3", "checker.py", "{in}", "{out}"]},
    }), encoding="utf-8")
    return lvl


def test_check_any_valid_also_validates_the_sample_answer(tmp_path: Path):
    """Phase 4's rule: an oracle that rejects a provided sample is broken."""
    lvl = _write_any_valid_level(tmp_path, accept_sample=True)
    result = _run("check_outputs.py", str(lvl))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "2/2 outputs valid" in result.stdout
    assert "1 sample answer(s)" in result.stdout


def test_check_any_valid_flags_a_checker_that_rejects_the_sample(tmp_path: Path):
    lvl = _write_any_valid_level(tmp_path, accept_sample=False)
    result = _run("check_outputs.py", str(lvl))
    assert result.returncode == 1
    assert "rejects the" in result.stdout


# --------------------------------------------------------------------------- #
# provided-names-are-truth helpers
# --------------------------------------------------------------------------- #
def test_output_path_for_mirrors_provided_naming(tmp_path: Path):
    cfg = {"outputs": "outputs"}
    got = C.output_path_for(tmp_path, cfg, tmp_path / "in_level-2_1-small.txt")
    assert got == tmp_path / "outputs" / "out_level-2_1-small.txt"
    got = C.output_path_for(tmp_path, cfg, tmp_path / "level1_1.in")
    assert got == tmp_path / "outputs" / "level1_1.out"


def test_sample_pairs_recognizes_both_conventions(tmp_path: Path):
    d = tmp_path / "samples"
    d.mkdir()
    (d / "in_a.txt").write_text("1", encoding="utf-8")
    (d / "out_a.txt").write_text("2", encoding="utf-8")
    (d / "b.in").write_text("1", encoding="utf-8")
    (d / "b.out").write_text("2", encoding="utf-8")
    (d / "c.txt").write_text("1", encoding="utf-8")  # unpaired, ignored
    pairs = C.sample_pairs(d)
    assert sorted((i.name, o.name) for i, o in pairs) == [
        ("b.in", "b.out"), ("in_a.txt", "out_a.txt"),
    ]


def test_find_statement_finds_provided_pdf_name(tmp_path: Path):
    (tmp_path / "level-9.pdf").write_bytes(b"%PDF-")
    assert C.find_statement(tmp_path, {}) == tmp_path / "level-9.pdf"


# --------------------------------------------------------------------------- #
# scaffold — imports move the provided files, never duplicate them
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


def test_scaffold_import_moves_instead_of_copying(tmp_path: Path):
    """A download's files end up in the workspace, not in both places."""
    src = tmp_path / "download"
    src.mkdir()
    (src / "level2_1.in").write_text("1\n5\n")
    (src / "level2_2.in").write_text("1\n7\n")
    (src / "level2_2.out").write_text("7\n")

    dst = tmp_path / "level2"
    result = _run("scaffold_level.py", str(dst), "--import", str(src))
    assert result.returncode == 0, result.stdout + result.stderr

    assert (dst / "inputs" / "level2_1.in").exists()
    assert (dst / "samples" / "level2_2.out").exists()
    assert not (src / "level2_1.in").exists()
    assert not (src / "level2_2.in").exists()
    assert not (src / "level2_2.out").exists()
    assert "(moved)" in result.stdout


def test_scaffold_import_in_place_leaves_no_flat_duplicates(tmp_path: Path):
    """The documented flat-download case: the level dir is the source too."""
    lvl = tmp_path / "level4"
    lvl.mkdir()
    (lvl / "in_lv_0-example.txt").write_text("1\n", encoding="utf-8")
    (lvl / "out_lv_0-example.txt").write_text("1\n", encoding="utf-8")
    (lvl / "in_lv_1-small.txt").write_text("1\n", encoding="utf-8")
    (lvl / "visualizer.html").write_text("<html></html>", encoding="utf-8")
    (lvl / "lv.pdf").write_bytes(b"%PDF-")

    result = _run("scaffold_level.py", str(lvl), "--import", str(lvl))
    assert result.returncode == 0, result.stdout + result.stderr

    assert (lvl / "inputs" / "in_lv_1-small.txt").exists()
    assert (lvl / "samples" / "in_lv_0-example.txt").exists()
    assert (lvl / "samples" / "out_lv_0-example.txt").exists()
    assert (lvl / "verifier" / "visualizer.html").exists()
    assert (lvl / "lv.pdf").exists()          # the statement stays at the root
    for flat in ("in_lv_1-small.txt", "in_lv_0-example.txt", "out_lv_0-example.txt",
                 "visualizer.html"):
        assert not (lvl / flat).exists(), f"{flat} left behind at the level root"

    # idempotent: a second import finds nothing left to move
    again = _run("scaffold_level.py", str(lvl), "--import", str(lvl))
    assert again.returncode == 0, again.stdout + again.stderr
    assert (lvl / "inputs" / "in_lv_1-small.txt").exists()


def test_scaffold_import_school_track_prefix_pairs(tmp_path: Path):
    """School-track downloads pair files as in_X.txt / out_X.txt; names stay verbatim."""
    src = tmp_path / "download"
    src.mkdir()
    (src / "in_level-1_0-example.txt").write_text("O-O\n-O-\n", encoding="utf-8")
    (src / "out_level-1_0-example.txt").write_text("2\n", encoding="utf-8")
    (src / "in_level-1_1-small.txt").write_text("O-O-O\n", encoding="utf-8")

    dst = tmp_path / "level1x"
    result = _run("scaffold_level.py", str(dst), "--import", str(src))
    assert result.returncode == 0, result.stdout + result.stderr

    # the example pair becomes a sample pair under its provided names
    assert (dst / "samples" / "in_level-1_0-example.txt").exists()
    assert (dst / "samples" / "out_level-1_0-example.txt").exists()
    # an answer file is never imported as an input
    assert not (dst / "inputs" / "out_level-1_0-example.txt").exists()
    assert (dst / "inputs" / "in_level-1_1-small.txt").exists()
    assert "1 input(s), 1 sample pair(s)" in result.stdout


def test_scaffold_import_orphan_answer_is_skipped(tmp_path: Path):
    src = tmp_path / "download"
    src.mkdir()
    (src / "out_level-2_0.txt").write_text("5\n", encoding="utf-8")
    (src / "in_level-2_1.txt").write_text("data\n", encoding="utf-8")

    dst = tmp_path / "level2x"
    result = _run("scaffold_level.py", str(dst), "--import", str(src))
    assert result.returncode == 0, result.stdout + result.stderr

    assert "skipped out_level-2_0.txt" in result.stdout
    assert not (dst / "inputs" / "out_level-2_0.txt").exists()
    assert (dst / "inputs" / "in_level-2_1.txt").exists()
