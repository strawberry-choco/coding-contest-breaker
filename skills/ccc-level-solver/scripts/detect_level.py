#!/usr/bin/env python3
"""Phase 0 helper: gather signals and suggest a CCC level's judging kind.

Usage:
    python3 detect_level.py <level_dir> [--write]

Prints the artifacts found, keyword hits in the statement, a suggested kind,
and the reasoning. With --write it records ``kind`` (and a verifier/scorer
command guess) into level.json.
"""
from __future__ import annotations

import argparse
import html
import re
from pathlib import Path

import _common as C

# Keyword patterns per kind. Deliberately conservative; a human confirms.
KEYWORDS = {
    "optimization": [
        r"\bminimi[sz]e\b", r"\bmaximi[sz]e\b", r"\bsmallest\b", r"\bfewest\b",
        r"\bshortest\b", r"\bcheapest\b", r"\blowest\b", r"\bhighest\b",
        r"as (?:small|short|few|cheap|low) as possible", r"\bscore\b",
        r"\bbetter\b", r"\bimprove\b", r"\boptimi[sz]e\b", r"\bfewer\b",
        r"\bless than\b", r"\bat most\b.*\bbetter\b",
    ],
    "any_valid": [
        r"any valid", r"print any", r"output any", r"if (?:multiple|several)",
        r"\bconstruct\b", r"\ba valid\b", r"\bany permutation\b",
        r"\bone possible\b", r"\bin any order\b",
    ],
    "interactive": [
        r"\bquer(?:y|ies)\b", r"the judge (?:responds|replies|answers)",
        r"\binteractor\b", r"you may ask", r"implement the function",
    ],
}


def _read_statement_text(path: Path) -> str:
    try:
        if path.suffix.lower() == ".pdf":
            return path.name  # cannot parse PDF here; filename only
        raw = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    if path.suffix.lower() in (".html", ".htm"):
        raw = re.sub(r"<[^>]+>", " ", raw)
        raw = html.unescape(raw)
    return raw


def _scan_keywords(text: str) -> dict[str, list[str]]:
    lowered = text.lower()
    hits: dict[str, list[str]] = {}
    for kind, patterns in KEYWORDS.items():
        found = []
        for pat in patterns:
            m = re.search(pat, lowered)
            if m:
                found.append(m.group(0))
        if found:
            hits[kind] = sorted(set(found))
    return hits


_VERIFIER_EXCLUDE = ("statement", "problem", "readme", "notes", "level.json", "report")


def _find_verifier(level_dir: Path) -> list[Path]:
    found: list[Path] = []
    for d in (level_dir / "verifier", level_dir / "verifiers", level_dir):
        if d.is_dir():
            for p in sorted(d.glob("*")):
                name = p.name.lower()
                if not p.is_file():
                    continue
                if any(name.startswith(x) or name.endswith(x) for x in _VERIFIER_EXCLUDE):
                    continue
                if ("visual" in name or "check" in name or "verif" in name
                        or "scor" in name):
                    found.append(p)
    # de-dup preserving order
    seen: set[Path] = set()
    return [p for p in found if not (p in seen or seen.add(p))]


def detect(level_dir: Path) -> dict:
    cfg = C.load_level(level_dir)
    statement = C.find_statement(level_dir, cfg)
    text = _read_statement_text(statement) if statement else ""
    inputs = C.iter_inputs(level_dir, cfg)
    samples_dir = level_dir / cfg["samples"]
    sample_ins = sorted(samples_dir.glob("*.in")) if samples_dir.is_dir() else []
    sample_outs = sorted(samples_dir.glob("*.out")) if samples_dir.is_dir() else []
    verifier = _find_verifier(level_dir)
    hits = _scan_keywords(text)

    # Score each candidate kind.
    scores: dict[str, int] = {k: 0 for k in KEYWORDS}
    reasons: list[str] = []
    for kind, found in hits.items():
        scores[kind] += 2 * len(found)
        reasons.append(f"statement keywords for {kind}: {', '.join(found)}")

    if sample_outs:
        scores["exact"] = scores.get("exact", 0) + 1
        reasons.append(f"{len(sample_outs)} sample answer(s) present")
    for p in verifier:
        name = p.name.lower()
        if "visual" in name or "scor" in name:
            scores["optimization"] += 2
            reasons.append(f"verifier '{p.name}' suggests scoring")
        elif "check" in name or "verif" in name:
            scores["any_valid"] += 2
            reasons.append(f"verifier '{p.name}' suggests a checker")

    # Choose highest-scoring kind, defaulting sensibly.
    best_kind = max(scores, key=lambda k: (scores[k], k != "exact"))
    if scores[best_kind] == 0:
        best_kind = "exact" if sample_outs else "unknown"
        reasoning = reasons or ["no decisive signals; defaulting"]
        confidence = "low"
    else:
        reasoning = reasons
        confidence = "high" if scores[best_kind] >= 4 else "medium"

    return {
        "kind": best_kind,
        "confidence": confidence,
        "scores": scores,
        "reasons": reasoning,
        "artifacts": {
            "statement": str(statement) if statement else None,
            "inputs": len(inputs),
            "sample_inputs": len(sample_ins),
            "sample_outputs": len(sample_outs),
            "verifier": [str(p) for p in verifier],
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("level_dir")
    ap.add_argument("--write", action="store_true",
                    help="write the suggested kind into level.json")
    args = ap.parse_args(argv)

    level_dir = C.as_level_dir(args.level_dir)
    result = detect(level_dir)

    a = result["artifacts"]
    print(f"level:      {level_dir}")
    print(f"statement:  {a['statement'] or '(none found)'}")
    print(f"inputs:     {a['inputs']}")
    print(f"samples:    {a['sample_inputs']} in / {a['sample_outputs']} out")
    print(f"verifier:   {', '.join(a['verifier']) or '(none)'}")
    print()
    print(f"suggested kind: {result['kind']}  (confidence: {result['confidence']})")
    for r in result["reasons"]:
        print(f"  - {r}")
    print(f"  scores: {result['scores']}")

    if args.write:
        cfg = C.load_level(level_dir)
        cfg["kind"] = result["kind"]
        C.save_level(level_dir, cfg)
        print(f"\nwrote kind='{result['kind']}' to {C.level_json_path(level_dir)}")

    print("\nConfirm or override this in level.json; see references/level-kinds.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())