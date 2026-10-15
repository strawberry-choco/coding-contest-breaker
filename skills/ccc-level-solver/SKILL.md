---
name: ccc-level-solver
description: >-
  Solve one Cloudflight Coding Contest (CCC) level end-to-end with
  test-driven development: build the judging oracle first, then the solver,
  and iterate until outputs are correct or the score stalls. Use when
  pointed at a level directory (e.g. under contests/) holding the problem
  statement and input files — a level to solve. Assumes manual
  download/upload; the skill never talks to the contest platform.
---

# CCC Level Solver

A phased, test-driven playbook for solving one level of the Cloudflight Coding
Contest from a local level directory. **Manual bridge** model: a human
downloads the level's statement and inputs and uploads the resulting output
files; this skill never talks to the contest platform.

## Core principle

**Build the judge before the solution.** For every level, first construct a
*local oracle* — the thing that decides whether an output is acceptable
(correctness) or how good it is (optimization). Only then write the solver,
driven by tests derived from that oracle. In contest TDD, "the test" is
usually a checker or scorer, not a fixed expected string.

## Inputs

The skill is pointed at a **level directory** holding the platform's
download. Expected shape (missing pieces are tolerated; Phase 0 records what
is present). Provided file names are kept **verbatim**; the naming rules live
in `references/ccc-io-conventions.md`:

```
<level_dir>/
  statement.*            # problem statement: .md/.txt/.html/.pdf (e.g. level-2.pdf)
  inputs/                # provided input files (in_X.txt / X.in) — these you must answer
  samples/               # optional worked-example pairs (in_X + out_X, or X.in + X.out)
  verifier/              # optional: provided checker/visualizer (e.g. visualizer.html, checker.py)
  notes.*                # optional: any hints the platform gave you
```

If the download is flat, normalize it first:
`python3 skills/ccc-level-solver/scripts/scaffold_level.py --import <flat_dir> <level_dir>`
(when the flat files already sit inside the level dir, pass the level dir as
both arguments). `--import` **moves** the provided files into `inputs/` and
`samples/`, so the level dir holds exactly one copy of each. The full workspace
contract — everything the level dir contains once solved — is also in
`references/ccc-io-conventions.md`.

## Phases

Follow the phases in order. Do not skip Phases 0–2 — they are what make this
reliable instead of guess-driven.

**Every level is a fresh contract.** A CCC level builds on the previous
level's model but adds or removes rules, so nothing carries over for free:
re-read the statement, re-derive the oracle, re-check every assumption. The
previous level's rules, tests, inputs, and solver are *not* a baseline to
preserve — reusing them unchanged is more likely wrong than right.

### Phase 0 — Gather and transform the inputs

**Done when `notes/inputs.md` records every provided input file's
structure, stats, and invariants.** Classifying (Phase 1) is only as good as
the ground truth it reasons over: counts read off an un-normalized directory
mislead, and parsers written from the statement's format table miss
byte-level quirks the files themselves show immediately.

1. Normalize the workspace first: flat download → `scaffold_level.py
   --import` (see Inputs). Provided names stay verbatim, moving into `inputs/`
   and `samples/`.
2. Read the statement once for the **input format**. Statements are often
   image slides: run `pdftotext` for copyable text, then **render every page
   and read them visually regardless** — pdftotext garbles or interleaves
   slide layouts, and a model built on silently-garbled text is the expensive
   failure. Use
   `python3 skills/ccc-level-solver/scripts/render_statement.py "<pdf>"`
   (renders all pages at 300 dpi into /tmp — never into the level dir). When
   table characters stay too small to read reliably, re-render that region
   with `--crop PAGE:fx:fy:fw:fh` (fractions of the page; the crop keeps
   native pixels while full-page views get downsampled). Transcribe I/O
   tables from the image character by character; never pair columns by
   position in the `pdftotext -layout` output. Render long PDFs in batches
   (`--pages 1-8`).
3. Parse and study **every** provided input: block/record counts, shapes,
   character or value invariants, size ranges, delimiters and whitespace
   placement (verify byte-level — e.g. blank lines between *and* after the
   header). Cross-check each claimed invariant against all files, not one.
4. **Persist the transformed output to disk in the level folder** —
   throwaway analysis dies with the context window:
   - `notes/inputs.md` — what was parsed and what was found: per-file
     structure and stats, the invariants a parser must accept, format quirks
     with evidence, and the sizes that will choose the algorithm.
   - for non-trivial formats, keep the working parser as
     `notes/parse_inputs.py`; later phases adapt it instead of re-deriving it
     (a blind oracle still writes its own — it must inherit no assumptions).

### Phase 1 — Identify the level kind

**Done when `level.json` records a kind** — including a deliberate
`unknown` plus the evidence still missing. Everything downstream depends on
this; with the inputs parsed (Phase 0), it is inference from evidence, not
keyword guessing.

**This is a judgement, so an agent makes it, not a script.** A keyword scan is
not a verdict: the classifying words live in narrative prose as often as in the
rules, and a script cannot tell the difference. Real examples — level 4's only
"better" is the email pleasantry *"we expect better results than your
predecessor"*, which a keyword scan reads as a scoring directive. Read the
statement and decide.

1. Take the inventory yourself: which artifacts exist (statement, `inputs/`,
   `samples/`, `verifier/` — a provided visualizer often sits under a
   platform name rather than `visualizer.html`), and what the statement's rules
   actually say.
2. Classify by *how an answer is judged*, never by how it is delivered: CCC is
   always output-only while the kind varies per level. Choose from: `exact`
   (one correct answer, compared to a reference), `any_valid` (many valid
   answers; a checker validates format + constraints), `optimization` (scored;
   "better" wins), `interactive` (converses with a judge — usually unsupported
   here), `unknown` (not enough information; gather more before proceeding).
   Full taxonomy, tell-tale phrases, and judging method per kind:
   `references/level-kinds.md`.
3. An input-supplied optimum is **not** `optimization`: when the statement says
   the given number *is the maximum possible*, that is an achievability
   guarantee for a constructive (`any_valid`) level, not a score to beat.
   Likewise a provided sample answer does not make a level `exact` — every kind
   ships one.
4. Record the decision in `level.json` (schema below).

### Phase 2 — Recon and specification

**Done when `notes/spec.md` pins the contract**: output format
byte-for-byte, objective, constraints, edge cases. (The input format was
pinned in Phase 0; re-consult the rendered pages and crops as needed.)

- The model builds level over level: earlier levels' `notes/spec.md` files
  document the shared conventions (grid geometry, I/O format, character
  semantics). Read them as reference, then re-verify every rule against this
  level's statement and samples — reference for the model, never a code
  baseline.
- State the output format byte-for-byte (line count, ordering, rounding,
  `YES`/`NO`).
- Extract the objective: for `optimization`, what is minimized/maximized and
  how is it measured? For `any_valid`, what constraints must a valid answer
  satisfy?
- Note constraints and limits (sizes, value ranges) — they choose the
  algorithm.
- List edge cases (empty, size 1, all-equal, maximal, adversarial).
- The statement and its constraints are authoritative; samples illustrate
  them. Never generalize a rule from samples alone.
- Write the specification into `notes/spec.md` (create it). Short and
  concrete.

### Phase 3 — Build the oracle and tests (RED)

**Done when `tests/test_level.py` runs red** — failing because no solver
exists yet, not because the oracle rejects a provided sample. A machine-
checkable definition of "acceptable" / "good" exists and is wired to tests
*before* any solver is written.

- Score/profile the oracle against the provided samples *first*: it must
  accept every sample answer. If it rejects one, the oracle is wrong — fix
  the oracle, never the sample.
- Choose the oracle per kind:
  - `exact` → `checker.py` does normalized comparison (trailing whitespace /
    newline, token-wise vs line-wise) and reports the first differing line.
  - `any_valid` → `checker.py` validates structure and every stated
    constraint. Add negative tests: deliberately malformed answers must be
    rejected.
  - `optimization` → `scorer.py` first *validates* the answer, then returns
    a numeric score. Record `direction` (min/max) and a `baseline` (sample
    score or a trivial-construction score).
  - `interactive` → write a local interactor that speaks the protocol.
- Write `tests/test_level.py` (start from `templates/test_level.py.tmpl`;
  the scaffolded `tests/test_level.py` is that template verbatim, so read
  one, not both):
  samples pass the oracle; the solver (once written) reproduces sample
  answers or beats the baseline; a regression test for every bug you fix.
  Scope tests to **this level** — see the regression discipline in
  `references/tdd-workflow.md` for why they must not carry across levels.
- Run the tests and **watch them fail** — that is the RED state.

### Phase 4 — Implement a baseline solver (GREEN)

**Done when every output in `outputs/` passes the oracle and the tests are
green** — via the simplest thing that achieves it.

- Start from `templates/solver.py.tmpl`. Keep the contract: read one input,
  write one answer, deterministic.
- Prefer a correct-but-slow baseline first (brute force, DP, simulation).
- **Smoke test after every solver edit**: solve the sample and run the checker
  on it (seconds) before any longer run. It catches crashes, import errors,
  and format breaks that otherwise surface mid-pipeline minutes later.
- Loop: run `python3 skills/ccc-level-solver/scripts/run_solver.py
  "<level_dir>"`, then `python3 skills/ccc-level-solver/scripts/check_outputs.py
  "<level_dir>"`, then the tests. Fix until green.
- Edit the oracle only when it demonstrably rejects a valid answer — and pin
  the corrected behavior with a test.

### Phase 5 — Iterate (scale up, or optimize)

**Done when the branch's gate holds** — cross-check passed (exact /
any_valid), or improvements stalled / optimality proven (optimization) —
with the best-known answer in `outputs/`.

- `exact` / `any_valid`: scale to the real inputs, then pass the
  **cross-check gate**:
  1. Check the limits; replace the baseline with an efficient algorithm if
     needed. Verify with the checker.
  2. Dispatch a fresh-context subagent to write `oracle.py` **blind** — feed
     it only the statement and `notes/spec.md`, never `solver.py`. The
     rationale (why independence catches what self-testing cannot) is in
     `references/tdd-workflow.md`.
  3. Run `python3 scripts/cross_check.py "<level_dir>"`: solver vs oracle
     over samples, real inputs, and (when `fuzz_gen.py` provides
     `generate(rng) -> str`) random small cases, printing a concrete
     counterexample on the first failure.
  4. The gate: for `exact`, solver–oracle **agreement**; for `any_valid`,
     cross_check.py switches to **validity mode** — both answers must pass
     `checker.py`, since a byte-diff would flag legitimate
     multiple-solution answers as fake counterexamples. Passing this gate is
     what qualifies a level as solved.
- `optimization`: this is the core loop.
  1. Score the current output; keep the best in `outputs/` and its score in
     `level.json` (`judge.best`).
  2. Improve with a heuristic strategy: better construction, greedy + local
     search (2-opt, swap, relocation), simulated annealing, or an exact
     method on small cases used to seed/validate heuristics.
  3. A candidate replaces the incumbent **only if it is valid AND strictly
     better** (respecting `direction`) — a worse answer never lands in
     `outputs/`.
  4. Stop when improvements stall for a meaningful number of iterations,
     when a time budget is hit, or when you can prove optimality.
- Keep every accepted improvement reproducible: solver code + seed go in the
  repo.

### Phase 6 — Finalize and package submission

**Done when the pipeline passes on a clean state and the upload list is
unambiguous.**

- Run the full pipeline once more end-to-end: `run_solver.py` →
  `check_outputs.py` → `cross_check.py` → tests.
- Ensure `outputs/` contains exactly one answer per input, correctly named.
- Write `report.md`: level kind, approach/algorithm, score or correctness
  result, runtime, assumptions, and known risks.
- List the files to upload (manual) in the order the platform expects.

## level.json

Created in Phase 1 and updated as you learn. Missing keys fall back to
defaults.

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

All live in `skills/ccc-level-solver/scripts/`; run them from the repo root,
e.g. `python3 skills/ccc-level-solver/scripts/run_solver.py "<level_dir>"`.
All are dependency-free Python 3 and take the level directory as the first
arg.

| Script | Purpose |
| --- | --- |
| `scripts/scaffold_level.py` | Normalize a raw download into a level dir (moves the provided files into `inputs/` and `samples/`); scaffold `level.json`, `tests/`, `solver.py`. |
| `scripts/run_solver.py` | Run the solver over every input in `inputs/` → `outputs/`. |
| `scripts/check_outputs.py` | Dispatch on `kind`: compare (exact), validate (any_valid), or score (optimization). |
| `scripts/cross_check.py` | Phase 5 gate: solver vs independently written `oracle.py` (+ optional `fuzz_gen.py`); prints a counterexample on the first failure. |
| `scripts/render_statement.py` | Render statement PDF pages to /tmp at 300 dpi for visual reading; `--crop` re-renders a region at native pixels. |

## Templates

`solver.py.tmpl`, `checker.py.tmpl`, `scorer.py.tmpl`, `test_level.py.tmpl`
— copy the relevant ones into the level directory and fill them in.

## References

- `references/level-kinds.md` — full taxonomy, tell-tale phrases, judging
  method per kind; composite kinds.
- `references/ccc-io-conventions.md` — verbatim file naming, output-only
  submission, formatting pitfalls, full workspace contract.
- `references/tdd-workflow.md` — deriving tests/oracles per kind; RED /
  GREEN / REFACTOR; blind-oracle verification; regression discipline.
