# coding-contest-breaker

A pipeline for solving [Cloudflight Coding Contest (CCC)](https://codingcontest.org/)
practice levels. The core deliverable is an **agent skill** that solves one level
at a time using **test-driven development**, and that adapts to the level's
judging kind (exact answer, any-valid answer, or optimization / "better" score).

The model is **human-in-the-loop with a manual bridge**: you download a level's
statement and inputs, the skill helps you build a solver and verify it locally,
and you upload the resulting output files. The skill never talks to the platform.

## The skill

`skills/ccc-level-solver/` — an agent skill (see `SKILL.md`). It runs in phases:

| Phase | What happens |
| --- | --- |
| **0 — Identify the level kind** | Classify how the level is judged (see below). |
| **1 — Recon & specification** | Extract the exact I/O contract, objective, constraints, edge cases. |
| **2 — Build the oracle (RED)** | Write the checker/scorer and tests *before* the solver. |
| **3 — Baseline solver (GREEN)** | Simplest correct solver; make the tests pass. |
| **4 — Iterate** | Scale to real inputs, or improve the score until it stalls. |
| **5 — Finalize** | Produce submission-ready outputs and a short report. |

### Level kinds

- **`exact`** — one correct answer; compared to a reference (CCC correctness levels).
- **`any_valid`** — many valid answers; a checker validates constraints.
- **`optimization`** — scored; "better" (smaller/shorter/cheaper) wins.
- **`interactive`** — program converses with a judge (rare in CCC).
- **`unknown`** — not enough signal yet.

Full taxonomy and tell-tale phrases: `skills/ccc-level-solver/references/level-kinds.md`.

## Repository layout

```
coding-contest-breaker/
├── README.md
├── skills/ccc-level-solver/
│   ├── SKILL.md                    # the phased playbook
│   ├── references/                 # level-kinds, ccc-io-conventions, tdd-workflow
│   ├── scripts/                    # detect_level, scaffold_level, run_solver, check_outputs
│   └── templates/                  # solver / checker / scorer / test templates
├── examples/level1/                # worked example (kind: exact)
└── tests/                          # tests for the skill's scripts
```

A level workspace looks like:

```
<level_dir>/
  statement.*      inputs/      samples/      verifier/    notes/spec.md
  level.json       solver.py    checker.py    scorer.py    tests/    outputs/    report.md
```

## Quickstart

The helper scripts are dependency-free Python 3.

```bash
# 1. Prepare a level directory (scaffold structure + templates)
python3 skills/ccc-level-solver/scripts/scaffold_level.py path/to/level3 --kind exact

# (or normalize a flat download:)
python3 skills/ccc-level-solver/scripts/scaffold_level.py path/to/level3 --import ~/Downloads/level3

# 2. Phase 0 — classify the level
python3 skills/ccc-level-solver/scripts/detect_level.py path/to/level3

# 3. Edit solver.py, then run it over every input
python3 skills/ccc-level-solver/scripts/run_solver.py path/to/level3

# 4. Verify (dispatch depends on level.json "kind")
python3 skills/ccc-level-solver/scripts/check_outputs.py path/to/level3

# 5. Run the TDD tests
cd path/to/level3 && pytest -q
```

## Worked example

See `examples/level1/` (a trivial `exact` level: sum N integers). It is also the
fixture used by `tests/`.

```bash
python3 skills/ccc-level-solver/scripts/detect_level.py examples/level1
python3 skills/ccc-level-solver/scripts/run_solver.py examples/level1
python3 skills/ccc-level-solver/scripts/check_outputs.py examples/level1
```

## Installing the skill

CodeArts loads skills from `~/.codearts/skills/`. To use this skill during a
solving session, link or copy it there:

```bash
mkdir -p ~/.codearts/skills
ln -s "$(pwd)/skills/ccc-level-solver" ~/.codearts/skills/ccc-level-solver
```

## Development

```bash
python3 -m pytest -q        # tests for the skill's scripts
```

## Scope

In scope: solving a single CCC Classic level locally with TDD, for all judging
kinds. Out of scope (for now): platform automation / auto-submission, and the
Data/AI and School tracks.