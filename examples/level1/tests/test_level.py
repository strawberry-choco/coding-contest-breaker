"""TDD tests for the worked example (exact level)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

LEVEL = Path(__file__).resolve().parent.parent


def _load_solver():
    spec = importlib.util.spec_from_file_location("solver", LEVEL / "solver.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sample_sum():
    solver = _load_solver()
    assert solver.solve("3\n1 2 3\n").split() == ["6"]


def test_single_element():
    solver = _load_solver()
    assert solver.solve("1\n42\n").split() == ["42"]


def test_larger_input():
    solver = _load_solver()
    assert solver.solve("5\n10 20 30 40 50\n").split() == ["150"]