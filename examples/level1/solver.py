#!/usr/bin/env python3
"""Worked-example solver: sum N integers. kind = exact."""
from __future__ import annotations

import sys


def parse(data: str):
    tokens = data.split()
    n = int(tokens[0])
    return [int(x) for x in tokens[1:1 + n]]


def solve(data: str) -> str:
    numbers = parse(data)
    return str(sum(numbers))


def main(argv: list[str]) -> int:
    data = open(argv[1], encoding="utf-8").read() if len(argv) > 1 else sys.stdin.read()
    out = solve(data)
    if out and not out.endswith("\n"):
        out += "\n"
    if len(argv) > 2:
        with open(argv[2], "w", encoding="utf-8") as fh:
            fh.write(out)
    else:
        sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))