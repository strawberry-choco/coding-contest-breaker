---
name: ccc-level-solver
description: >-
  Solve a single Cloudflight Coding Contest (CCC) level end-to-end with
  test-driven development. Use when pointed at a level directory that contains
  the problem statement, input file(s), and (optionally) sample answers or a
  provided verifier/visualizer. Phase 0 identifies the level's judging kind
  (exact, any-valid, optimization, interactive, ...); later phases build a
  verification oracle and tests BEFORE the solver, implement a baseline, then
  iterate until the output is correct or its score can no longer be improved.
  Produces submission-ready output files. Assumes manual download/upload
  (no platform automation).
---

# CCC Level Solver

A phased, test-driven playbook for solving one level of the Cloudflight Coding
Contest from a local level directory.

This skill assumes the **manual bridge** model: a human downloads the level's
statement and inputs and uploads the resulting output files. This skill never
talks to the contest platform.

## Core principle

**Build the judge before the solution.** For every level you first construct a
*local oracle* — the exact thing that decides whether an output is acceptable
(for correctness) or how good it is (for optimization). Only then write the
solver, and drive it with tests derived from that oracle. This is the TDD loop
applied to contest levels, where "the test" is often a checker or a scorer
rather than a fixed expected string.

## Inputs

The skill is pointed at a **level directory**. Expected shape (missing pieces
are tolerated; Phase 0 records what is present):

```
<level_dir>/
  statement.*            # problem statement: .md/.txt/.html/.pdf
  inputs/                # *.in  — one real input per file (these you must answer)
  samples/               # optional: sample_*.in  +  sample_*.out  (worked examples)
  verifier/              # optional: provided checker/visualizer (e.g. visualizer.html, checker.py)
  notes.*                # optional: any hints the platform gave you
```

If the platform handed you a flat folder, run `scripts/scaffold_level.py --import`
to normalize it into the shape above first.

## Phases

Follow the phases in order. Do not skip Phase 0 or Phase 2 — they are what make
this reliable instead of guess-driven.

### Phase 0 — Identify the level kind

**Goal:** decide *how the level is judged*, because everything downstream
depends on it.

1. Gather signals:
   ```bash
   python3 scripts/detect_level.py "<level_dir>"
   ```
   It reports which artifacts exist (samples, verifier, statement) and scans the
   statement for classification keywords, and suggests a `kind` with a reason.
2. Read the statement yourself and confirm/override. Use
   `references/level-kinds.md` for the full taxonomy and the tell-tale phrases.
3. Kinds to choose from:
   - `exact` — one correct answer; compare to reference output.
   - `any_valid` — many valid answers; a checker validates *format + constraints*.
   - `optimization` — output is scored; "better" (smaller/larger/cheaper) wins.
   - `interactive` — the program converses with a judge (usually unsupported here).
   - `unknown` — not enough information yet; gather more before proceeding.
4. Record the decision in `level.json` (see schema below).

A level is often a **composite**: e.g. every level of a CCC game is *output-only*
(the answers are uploaded as files) while its *kind* may be `exact`,
`any_valid`, or `optimization`. Classify by how an answer is judged, not by how
it is delivered.

### Phase 1 — Recon and specification

**Goal:** turn the statement into a precise, testable contract.

- Parse the input format exactly (dimensions, delimiters, edge cases, units).
- State the output format byte-for-byte (line count, ordering, rounding, `YES`/`NO`).
- Extract the objective: for `optimization`, what is minimized/maximized and how
  is it measured? For `any_valid`, what constraints must a valid answer satisfy?
- Note constraints and limits (sizes, value ranges) — they choose the algorithm.
- List edge cases (empty, size 1, all-equal, maximal, adversarial).
- Write the specification into `notes/spec.md` (create it). Short and concrete.

### Phase 2 — Build the oracle and tests (RED)

**Goal:** a machine-checkable definition of "acceptable" / "good" exists, and it
is wired to tests, *before* any solver is written.

- Score/profile the oracle against the provided samples *first*: the oracle must
  mark every provided sample answer as acceptable. If it rejects a sample, the
  oracle is wrong — fix the oracle, not the sample.
- Choose the oracle per kind:
  - `exact` → `checker.py` does normalized comparison (trailing whitespace /
    newline, token-wise vs line-wise) and reports the first differing line.
  - `any_valid` → `checker.py` validates structure and every stated constraint.
    Add negative tests: deliberately malformed/invalid answers must be rejected.
  - `optimization` → `scorer.py` first *validates* the answer, then returns a
    numeric score. Record `direction` (min/max) and a `baseline` (sample score
    or a trivial-construction score).
  - `interactive` → write a local interactor that speaks the protocol.
- Write `tests/test_level.py` (start from `templates/test_level.py.tmpl`):
  - samples pass the oracle,
  - the solver (once written) reproduces sample answers or beats the baseline,
  - regression tests for every bug you fix (so it never comes back).
- Run the tests and **watch them fail** — that is the RED state.

### Phase 3 — Implement a baseline solver (GREEN)

**Goal:** the simplest thing that makes the tests pass.

- Start from `templates/solver.py.tmpl`. Keep the contract:
  read one input, write one answer, deterministic.
- Prefer a correct-but-slow baseline first (brute force, DP, simulation).
- Loop: run `python3 scripts/run_solver.py "<level_dir>"`, then
  `python3 scripts/check_outputs.py "<level_dir>"`, then the tests. Fix until
  green.
- Never edit the oracle to make a failing solution pass unless the oracle itself
  is demonstrably wrong — and if so, add a test that pins the corrected behavior.

### Phase 4 — Iterate (scale up, or optimize)

**Goal:** go from "passes samples" to "passes everything" or "as good as possible".

- `exact` / `any_valid`: scale to the real inputs. Check limits; replace the
  baseline with an efficient algorithm if needed. Verify with the checker.
- `optimization`: this is the core loop.
  1. Score the current output; keep the best in `outputs/` and its score in
     `level.json` (`judge.best`).
  2. Improve with a heuristic strategy: better construction, greedy + local
     search (2-opt, swap, relocation), simulated annealing, or an exact method
     on small cases used to seed/validate heuristics.
  3. A candidate replaces the incumbent **only if it is valid AND strictly
     better** (respecting `direction`).
  4. Stop when improvements stall for a meaningful number of iterations, when a
     time budget is hit, or when you can prove optimality. Always leave the
     best-known answer in `outputs/`.
- Keep every accepted improvement reproducible: solver code + seed go in the repo.

### Phase 5 — Finalize and package submission

**Goal:** submission-ready artifacts plus a short report.

- Run the full pipeline once more end-to-end on a clean state:
  `run_solver.py` → `check_outputs.py` → `tests`.
- Ensure `outputs/` contains exactly one answer per input, correctly named.
- Write `report.md`: level kind, approach/algorithm, score or correctness
  result, runtime, assumptions, and known risks.
- List the files to upload (manual) in the order the platform expects.

## level.json

Created in Phase 0 and updated as you learn. Missing keys fall back to defaults.

```json
{
  "kind": "exact | any_valid | optimization | interactive | unknown",
  "run": ["python3", "solver.py", "{in}", "{out}"],
  "inputs": "inputs",
  "outputs": "outputs",
  "samples": "samples",
  "judge": {
    "command": ["python3", "checker.py", "{in}", "{out}", "{expected}"],
    "scorer": ["python3", "scorer.py", "{in}", "{out}"],
    "direction": "min",
    "metric": "total_cost",
    "best": null
  },
  "notes": ""
}
```

Placeholders: `{in}` input path, `{out}` output path, `{expected}` matching
sample answer (when it exists), `{level}` the level directory.

## Helper scripts

All are dependency-free Python 3 and take the level directory as the first arg.

| Script | Purpose |
| --- | --- |
| `scripts/detect_level.py` | Phase 0: gather signals and suggest the level kind. |
| `scripts/scaffold_level.py` | Normalize a raw download into a level dir; scaffold `level.json`, `tests/`, `solver.py`. |
| `scripts/run_solver.py` | Run the solver over every input in `inputs/` → `outputs/`. |
| `scripts/check_outputs.py` | Dispatch on `kind`: compare (exact), validate (any_valid), or score (optimization). |

## Templates

`solver.py.tmpl`, `checker.py.tmpl`, `scorer.py.tmpl`, `test_level.py.tmpl` —
copy the relevant ones into the level directory and fill them in.

## References

- `references/level-kinds.md` — full taxonomy, tell-tale phrases, judging method.
- `references/ccc-io-conventions.md` — CCC file naming, output-only submission, formatting pitfalls.
- `references/tdd-workflow.md` — how to derive tests/oracles per kind; RED/GREEN/REFACTOR for contests.

## Anti-patterns

- **Solving before defining the judge.** You will optimize the wrong objective.
- **Trusting samples as the full spec.** Samples are illustrative; the statement
  and constraints are authoritative.
- **Editing the oracle to pass a wrong solution.** Only fix the oracle when it
  provably rejects a valid answer — then add a test.
- **Discarding a better answer.** In `optimization`, never overwrite a valid,
  better incumbent with a worse one.
- **Assuming "correct" means "identical".** Many levels accept *any* valid answer.