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

**Execution model — orchestrator only.** The agent running this skill never
performs phase work in its own context: every phase runs in a subagent, and
the orchestrator sequences phases, verifies their outputs, and decides.

## Core principle

**Build the judge before the solution.** For every level, first construct a
*local oracle* — the thing that decides whether an output is acceptable
(correctness) or how good it is (optimization). Only then write the solver,
driven by tests derived from that oracle. In contest TDD, "the test" is
usually a checker or scorer, not a fixed expected string. The attack plan
(Phase 3) is written before any code — that is where the problem gets
reduced, split, and matched to tools. A level ships within one session; time
spent is part of the score — every phase works the **effort ladder**
(cheapest rung first, banked progress) rather than opening with the most
ambitious tool. The cross-phase rules every brief assumes — the statement is
authoritative, fresh contract, renders are the reference, persist,
bank-and-emit, on paper — live in `references/shared-rules.md`; Phase 6 runs
under the orchestrator-owned ≤ 30-minute EV checkpoints.

For **output-only** levels the minimum pipeline is Phases 0→1→2→4→5→7 — build
the checker, ship a solver whose outputs pass it on every provided input,
package. Phase 3 supplies the construction ladder the solver needs; Phase 6 is
optional deep-validation, reached when the checker rejects an output you cannot
diagnose.

## Orchestration protocol

The orchestrator drives every phase the same way:

1. **Dispatch** a general-purpose subagent with a self-contained brief: the
   level directory, the phase's steps (copied from this file — subagents are
   stateless and cannot see this conversation), a standing first
   instruction to **read `references/shared-rules.md`** (the cross-phase
   rules — briefs never restate them), the artifacts it must
   **read** and the artifacts it must **write**, and the return contract: a
   compact summary (verdicts, counts, sizes, paths, anomalies) — never raw
   data, never long tables.
2. **Stage monolithic phases**: when a phase's green is all-or-nothing (e.g.
   `any_valid` with a supplied maximum), split the dispatch by size-group or
   ladder rung so each dispatch lands banked progress a human can see and
   cancel at a seam; `notes/progress.md` tracks rooms-closed/rooms-open
   across dispatches.
3. **Pass state through the level directory.** Phases communicate only via
   files (`notes/*.md`, `level.json`, `tests/`, `solver.py`, `outputs/`);
   each brief names them explicitly. The orchestrator's context carries
   paths and verdicts, not data.
4. **Verify against the phase's done-when**: the artifact exists, plus 2-3
   spot-checks (one small read each) of claims in the returned summary or
   the artifact. Distrust → re-dispatch with the discrepancy named.
5. **Gate**: a phase that has not met its done-when blocks the next phase.
   The orchestrator's own tool use stays cheap — file-existence checks,
   small reads, one-command status checks with bounded output; everything
   that produces or transforms data belongs to a subagent.

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
`python3 .agents/skills/ccc-level-solver/scripts/scaffold_level.py --import <flat_dir> <level_dir>`
(when the flat files already sit inside the level dir, pass the level dir as
both arguments). `--import` **moves** the provided files into `inputs/` and
`samples/`, so the level dir holds exactly one copy of each. The full workspace
contract — everything the level dir contains once solved — is also in
`references/ccc-io-conventions.md`.

## Phases

Follow the phases in order. Phases 0–2 and 4–5 are the required spine — they
are what make this reliable instead of guess-driven. Phase 3 records the
construction ladder; Phase 6 is optional deep-validation (see the minimum
pipeline above).

**Every level is a fresh contract** (shared rules): nothing carries over for
free — re-read the statement, re-derive the oracle, re-check every
assumption.

### Phase 0 — Gather and transform the inputs

**Done when `notes/inputs.md` records every provided input file's
structure, stats, and invariants.** Classifying (Phase 1) is only as good as
the ground truth it reasons over: counts read off an un-normalized directory
mislead, and parsers written from the statement's format table miss
byte-level quirks the files themselves show immediately.

**Brief** (subagent):
- Normalize the workspace first: flat download → `scaffold_level.py
  --import` (see Inputs). Provided names stay verbatim, moving into
  `inputs/` and `samples/`.
- Read the statement once for the **input format**. Statements are often
  image slides: run `pdftotext` for copyable text, then **render every page
  and read them visually regardless** — pdftotext garbles or interleaves
  slide layouts, and a model built on silently-garbled text is the expensive
  failure. Use
  `python3 .agents/skills/ccc-level-solver/scripts/render_statement.py "<pdf>"`
  (renders all pages at 300 dpi into /tmp — never into the level dir). When
  table characters stay too small to read reliably, re-render that region
  with `--crop PAGE:fx:fy:fw:fh` (fractions of the page; the crop keeps
  native pixels while full-page views get downsampled). Transcribe I/O
  tables from the image character by character; never pair columns by
  position in the `pdftotext -layout` output. Render long PDFs in batches
  (`--pages 1-8`).
- Parse and study **every** provided input: block/record counts, shapes,
  character or value invariants, size ranges, delimiters and whitespace
  placement (verify byte-level — e.g. blank lines between *and* after the
  header). Cross-check each claimed invariant against all files, not one.
- **Persist everything to disk in the level folder** (shared rules):
  - `notes/inputs.md` — what was parsed and what was found: per-file
    structure and stats, the invariants a parser must accept, format quirks
    with evidence, the sizes that will choose the algorithm, and the path of
    the rendered statement pages (default `/tmp/<pdf-stem>-render`) plus any
    crops worth re-reading — later phases read those images instead of
    re-rendering the PDF.
  - for non-trivial formats, keep the working parser as
    `notes/parse_inputs.py`; later phases adapt it instead of re-deriving it
    (a blind oracle still writes its own — it must inherit no assumptions).

**Return**: the file inventory, record counts, size ranges, format quirks,
anomalies, and the paths of everything written.
**Orchestrator verify**: the files exist; 2-3 claims in `notes/inputs.md`
spot-check clean against the actual inputs (one read each).

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

**Brief** (subagent):
1. Take the inventory: which artifacts exist (statement, `inputs/`,
   `samples/`, `verifier/` — a provided visualizer often sits under a
   platform name rather than `visualizer.html`), and what the statement's
   rules actually say.
2. **Read `references/level-kinds.md`** (the full taxonomy, tell-tale
   phrases, and judging method per kind) before classifying. Then classify by
   *how an answer is judged*, never by how it is delivered: CCC is
   always output-only while the kind varies per level. Choose from: `exact`
   (one correct answer, compared to a reference), `any_valid` (many valid
   answers; a checker validates format + constraints), `optimization` (scored;
   "better" wins), `interactive` (converses with a judge — usually unsupported
   here), `unknown` (not enough information; gather more before proceeding).
3. An input-supplied optimum is **not** `optimization`: when the statement says
   the given number *is the maximum possible*, that is an achievability
   guarantee for a constructive (`any_valid`) level, not a score to beat.
   Likewise a provided sample answer does not make a level `exact` — every kind
   ships one.
4. Record the decision in `level.json` (schema below).

**Return**: the kind and 2-3 lines of evidence from the statement.
**Orchestrator verify**: `level.json` parses and names a known kind; the
evidence quotes the statement.

### Phase 2 — Recon and specification

**Done when `notes/spec.md` pins the contract (output format
byte-for-byte, objective, constraints, edge cases) before any code is
written.** (The input format was pinned in Phase 0.)

**Brief** (subagent):
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
- Note constraints and limits (sizes, value ranges, plus the statement's
  time/memory limits when given) — they choose the algorithm.
- List edge cases (empty, size 1, all-equal, maximal, adversarial).
- Write the specification into `notes/spec.md` (create it).
**Return**: the spec's non-obvious deltas (format quirks, objective), and
anything ambiguous enough to need an orchestrator decision.
**Orchestrator verify**: `notes/spec.md` exists; one spec rule spot-checks
clean against the statement.

### Phase 3 — Attack plan

**Done when `notes/attack.md` records the attack plan — complexity budget
derived from the largest input, every ladder rung gated against it on paper —
before any code is written.**

**Brief** (subagent):
- Read `notes/spec.md` and `notes/inputs.md` for the contract and the sizes;
  re-verify against the statement every rule the plan leans on.
- Derive the **complexity budget** from the largest input and record it in
  `notes/attack.md`: the operation count a rung may afford (rule of thumb:
  CPython does ~10⁷ simple ops/sec, so n ≤ 10⁵ demands O(n log n) or
  better and n ≤ 10⁶ only O(n) within seconds). Every rung of the ladder
  is measured against this yardstick.
- **On paper, for cost**: this phase runs no whole-solution prototype and no
  timing/benchmark runs; the cost gate is arithmetic on stated operation
  counts. Checks over the provided instances are data checks and are fine —
  closed-form fits, and a *small exact probe* (DP or tiny ILP on small
  instances) run to **discover** a construction, both O(instances)/seconds. If
  a rung's cost cannot be established by arithmetic, the plan says so and the
  rung's Phase 6 budget discovers it empirically.
- **Write the attack plan into `notes/attack.md` — the reduce-then-split
  work, on paper, before coding starts:**
  - **Reduce**: translate the statement into the problem's exact structure
    (packing, covering, counting, ...) and restate the objective in those
    terms. Per sub-problem, name the algorithm and state its **time and
    space complexity** — on paper, before any code — and say *why the naive
    approach fails* at these bounds (the first idea that comes to mind is
    almost always the O(n²) one). Match to a known primitive rather than
    inventing: recurrence + matrix exponentiation, sieve / prefix sums,
    modular arithmetic / CRT, generating functions, closed-form formula
    (for count-shaped levels a closed form beats simulation every time),
    DP with state compression, flows / matchings.
  - **Split**: break it into independent sub-problems — exact solutions for
    small cases, provable periodic patterns for the bulk, and seam conditions
    you can verify. Prove the pieces compose (independent regions add up),
    and only then attack the remaining gap. Example: a no-touch packing level
    reduces to rectangle packing; columns decompose into exact-DP bases plus
    periodic strips whose seam independence you prove once. **Series levels
    are formula-shaped — harvest, don't re-derive**: earlier levels' notes
    carry the proven count formulas; when the platform supplies the target
    count per instance (an achievability guarantee), those counts are ground
    truth — fit/derive the count function f(x, y, …) and verify it predicts
    EVERY provided instance exactly before writing construction code (a
    wrong formula dies in seconds; a passing one is proven by exhaustion).
    The shape to aim for: one periodic supertile per parameter value
    (found by a single small exact solve, not per-instance solves) + a
    boundary DP for the edges — timeboxed; if the fit fails, fall down the
    ladder. When the supplied targets admit no closed form, stop fitting: the
    plan's job is then the cheapest per-instance construction that hits each
    supplied target, generalising (a periodic supertile or strip pattern) only
    where a large instance forces it — the supplied target is ground truth, so
    verify the construction against it. On a constructive level the fit itself
    is **rung 1** of the ladder and lands within the first ~15 minutes; once
    it predicts every provided key, the primary engine is
    **reverse-engineering the generator's construction** (small exact solves
    as specimens, boundary algebra, transplant/grow between verified grids) —
    search is for residuals.
  - **Choose tools library-first, per sub-problem**: a CP-SAT/ILP solver
    (e.g. OR-Tools) for packing and covering, networkx for graphs,
    numpy/scipy for numerics. Name the library you will try FIRST and the
    input sizes it must handle; hand-roll only what no library provides, and
    only after a rung's Phase 6 run has measured the library too slow for
    those sizes. When
    the judge demands exact attainment (`any_valid` with a supplied maximum),
    a cheap rung counts only if it provably *hits* the supplied count
    (checker-verified, ideally closed-form) — near-misses never ship; the
    exact solver then enters at the residual rung, smallest first, not as
    the level-wide engine.
  - **Record the constraints and the order of attempts**: level code is
    iterative only (no recursive functions — solver, checker, scripts, any
    language; explicit stacks, queues, bitmask loops, since recursion blows
    Python's ~1000-frame limit on large grids); the fallback chain (e.g.
    constructive pattern → exact solver → heuristic repair) ordered
    cheapest-first as an **effort ladder**: each rung gets a wall-clock
    budget and a done-when, banks what it closes (later rungs touch only
    the residual), and expensive solvers (CP-SAT/ILP) are scalpels —
    validation and residual rooms ≤ ~1k cells only, never the level-wide
    engine; on constructive levels the ladder order is fixed — count-formula
    fit → generator reverse-engineering → bounded search on residuals;
    benchmark numbers go into `notes/`, never the terminal.
  - **Complexity gate — pass it on paper before coding**: for every rung of
    the ladder, multiply out its planned operations at the largest input and
    compare against the budget. A plan that fails the gate (O(n²) at
    n = 10⁵, per-instance exact solves at n = 10⁶) is rejected here, not
    discovered mid-run: return to the reduction for a better primitive —
    never "optimize later" a plan that is asymptotically dead.

**Return**: the attack plan's structure, complexity budget, and chosen
tools, and anything that needs an orchestrator decision.
**Orchestrator verify**: `notes/attack.md` exists, states the complexity
budget, and every ladder rung's complexity fits it — checked **on paper**:
each rung's *stated* op count, multiplied out at the largest input (sizes
from `notes/inputs.md`), against the *stated* budget; a rung without a
concrete op count fails the gate (re-dispatch). A rung that misses the
budget blocks Phase 4.

### Phase 4 — Build the oracle and tests (RED)

**Done when `tests/test_level.py` runs red** — failing because no solver
exists yet, not because the oracle rejects a provided sample. A machine-
checkable definition of "acceptable" / "good" exists and is wired to tests
*before* any solver is written.

**Brief** (subagent):
- Score/profile the oracle against the provided samples *first*: it must
  accept every sample answer. If it rejects one, the oracle is wrong — fix
  the oracle, never the sample.
- Choose the oracle per kind — `checker.py` (exact: normalized comparison /
  any_valid: structure + every stated constraint, with negative tests) or
  `scorer.py` (optimization: validate then score; record `direction` and a
  `baseline`). The per-kind recipes, normalization levels, and test lists
  are in `references/tdd-workflow.md`.
- Read `notes/attack.md`: the plan's split names seam conditions to verify
  and (for series levels) a count formula that must predict every provided
  instance — pin each as a test alongside the sample checks.
- Write `tests/test_level.py` (start from `templates/test_level.py.tmpl`;
  the scaffolded `tests/test_level.py` is that template verbatim, so read
  one, not both):
  samples pass the oracle; the solver (once written) reproduces sample
  answers or beats the baseline; a regression test for every bug you fix.
  Scope tests to **this level** — see the regression discipline in
  `references/tdd-workflow.md` for why they must not carry across levels.
- Run the fast loop (`pytest -q -m "not slow"`) and **watch it fail** —
  that is the RED state.

**Return**: the RED confirmation — which tests fail and why — plus the
sample-check verdict.
**Orchestrator verify**: the test file and the oracle exist; the returned
failures name the missing solver, not sample rejections.

### Phase 5 — Implement a baseline solver (GREEN)

**Done when every output in `outputs/` passes the oracle and the tests are
green** — via the simplest thing that achieves it.

**Brief** (subagent):
- Start from `templates/solver.py.tmpl`. Keep the contract: read one input,
  write one answer, deterministic.
- Prefer a correct-but-slow baseline first (brute force, DP, simulation) —
  per the attack plan's tool choices. Open with the **cheapest rung** of the
  attack ladder and bank what it closes into `outputs/` before touching the
  next rung; a phase that ends with some inputs still unsolved is honest
  progress, recorded in `notes/progress.md`, never a reason to have opened
  with the expensive tool.
- **Bank-and-emit** (shared rules): the moment an answer passes the oracle,
  it is frozen into `outputs/`.
- **Smoke test after every solver edit**: solve the sample and run the checker
  on it (seconds) before any longer run. It catches crashes, import errors,
  and format breaks that otherwise surface mid-pipeline minutes later.
- Loop: run `python3 .agents/skills/ccc-level-solver/scripts/run_solver.py
  "<level_dir>"`, then `python3 .agents/skills/ccc-level-solver/scripts/check_outputs.py
  "<level_dir>"`, then the fast loop. Fix until green.
- Edit the oracle only when it demonstrably rejects a valid answer — and pin
  the corrected behavior with a test.

**Return**: the green confirmation (fast loop) and per-input status.
**Orchestrator verify**: `outputs/` holds one answer per input, named after
its input.

### Phase 6 — Iterate (scale up, or optimize)

**Done when the branch's gate holds** — `check_outputs.py` ACCEPT on every
provided input plus a green test suite (`any_valid`, and `exact` by
default), or improvements stalled / optimality proven (`optimization`) —
with the best-known answer in `outputs/`. For `exact`, a solver–oracle
cross-check is additionally required only when a blind `oracle.py` was
written (see below).

The Iterator runs whenever the ladder still has open inputs. The blind-oracle
and gate roles are optional deep-validation — by default none of them runs:
on `any_valid` the supplied target is ground truth, and on `exact` the
checker's own independent recomputation already gates every output, so the
default gate is `check_outputs.py` ACCEPT plus the test suite. Dispatch a
blind oracle only when the checker rejects an output you cannot diagnose (or
the orchestrator explicitly opts into deep-validation); on `any_valid` that
budget instead goes into an adversarial re-read of `checker.py` against the
statement.

**EV checkpoints — the orchestrator owns the clock.** At least every 30
wall-clock minutes, re-run `check_outputs.py` and count checker-ACCEPT files —
the only currency that scores. Two consecutive checkpoints with zero new
ACCEPTs force an approach switch, chosen from: (1) count-formula fit if not
yet done, (2) generator reverse-engineering (specimens from small exact
solves, boundary algebra, transplant/grow between verified grids), (3) a
different decomposition of the stuck rooms — never a longer run of the same
search family. Timeboxes bind approaches, not individual attempts.

Three subagent roles, sequenced by the orchestrator:

- **Iterator** — brief per branch:
  - `exact` / `any_valid`: check the limits; replace the baseline with an
    efficient algorithm if needed. Verify with the checker. Climb the
    attack plan's effort ladder rung by rung, respecting each
    rung's budget: every input a rung closes is banked into `outputs/` and
    logged (closed/open) in `notes/progress.md`; when a rung overruns its
    budget, record the residual and escalate to the next rung — the last
    resort for a still-open input is reported, never shipped short.
  - `optimization`: score the current output; keep the best in `outputs/`
    and its score in `level.json` (`judge.best`). Improve with a heuristic
    strategy: better construction, greedy + local search (2-opt, swap,
    relocation), simulated annealing, or an exact method on small cases used
    to seed/validate heuristics. A candidate replaces the incumbent **only
    if it is valid AND strictly better** (respecting `direction`) — a worse
    answer never lands in `outputs/`. Stop when improvements stall for a
    meaningful number of iterations, when a time budget is hit, or when
    optimality is proven. Returns per-room/per-case status and what blocks
    the gate.
- **Blind oracle author** (only after an undiagnosable checker rejection, or
  when the orchestrator explicitly opts into deep-validation) — a
  **fresh-context subagent** whose brief
  carries only the statement and `notes/spec.md`, never `solver.py`: it writes
  `oracle.py`. The rationale (why independence catches what self-testing
  cannot) is in `references/tdd-workflow.md`.
- **Gate runner** — runs
  `python3 .agents/skills/ccc-level-solver/scripts/cross_check.py "<level_dir>"`
  (requires a written `oracle.py`; without one it aborts): solver vs oracle
  over samples, real inputs, and (when `fuzz_gen.py` provides
  `generate(rng) -> str`) random small cases, printing a concrete
  counterexample on the first failure. When no `oracle.py` exists — the
  default for every kind — the gate is `check_outputs.py` ACCEPT on every
  provided input plus the test suite; write a fuzzer only when a diagnosis
  needs one.

**The gate** (when cross_check.py runs): for `exact`, solver–oracle
**agreement**; for `any_valid`, cross_check.py switches to **validity mode**
— both answers must pass `checker.py`, since a byte-diff would flag
legitimate multiple-solution answers as fake counterexamples.

**Return**: the gate verdict (or the stall/optimality proof), plus any
counterexample text — relayed verbatim.
**Orchestrator verify**: `exact` / `any_valid` → `check_outputs.py` reports
ACCEPT on every provided input and the test suite is green; when a blind
`oracle.py` was written, additionally `cross_check.py` exited 0 (re-run it
inline — a bounded one-command check — if in doubt); `optimization` →
`level.json` records the best score and `outputs/` holds the best-known
answers.

### Phase 7 — Finalize and package submission

**Done when the pipeline passes on a clean state and the upload list is
unambiguous.**

**Brief** (subagent):
- Run the full pipeline once more end-to-end: `run_solver.py` →
  `check_outputs.py` → `cross_check.py` (when the level has an oracle) →
  tests (unfiltered, including slow).
- Ensure `outputs/` contains exactly one answer per input, correctly named.
- Write `report.md`: level kind, approach/algorithm, score or correctness
  result, runtime, assumptions, and known risks.
- List the files to upload (manual) in the order the platform expects.

**Return**: the pipeline verdict, the report summary, and the upload list —
the orchestrator relays the upload list to the human verbatim.
**Orchestrator verify**: `report.md` exists; the upload list matches
`outputs/` one-to-one with the inputs.

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

A bare `python3` (or `python`) as the command's interpreter is executed under
the repo's `.venv/bin/python` when that exists — the helper scripts resolve it
to an absolute path, since commands run with `cwd` set to the level dir — so
level code (`solver.py`, `checker.py`, `scorer.py`, `oracle.py`, `fuzz_gen.py`)
may import the venv's third-party packages (ortools, numpy, networkx, scipy).
Without a venv the command falls back to the system `python3`.
`cross_check.py` likewise re-execs itself under the venv interpreter, so
in-process solver/oracle imports work there too.

## Helper scripts

All live in `.agents/skills/ccc-level-solver/scripts/`; run them from the repo root,
e.g. `python3 .agents/skills/ccc-level-solver/scripts/run_solver.py "<level_dir>"`.
All are dependency-free Python 3 (stdlib only, so they run under a bare
`python3` before `uv sync` has created the venv) and take the level directory
as the first arg.

| Script | Purpose |
| --- | --- |
| `scripts/scaffold_level.py` | Normalize a raw download into a level dir (moves the provided files into `inputs/` and `samples/`); scaffold `level.json`, `tests/`, `solver.py`. |
| `scripts/run_solver.py` | Run the solver over every input in `inputs/` → `outputs/`. |
| `scripts/check_outputs.py` | Dispatch on `kind`: compare (exact), validate (any_valid), or score (optimization). |
| `scripts/cross_check.py` | Phase 6 gate: solver vs independently written `oracle.py` (+ optional `fuzz_gen.py`); prints a counterexample on the first failure. |
| `scripts/render_statement.py` | Render statement PDF pages to /tmp at 300 dpi for visual reading; `--crop` re-renders a region at native pixels. |

## Templates

`solver.py.tmpl`, `checker.py.tmpl`, `scorer.py.tmpl`, `test_level.py.tmpl`
— copy the relevant ones into the level directory and fill them in.

## References

- `references/shared-rules.md` — the cross-phase rules every brief assumes
  (the statement is authoritative, fresh contract, renders are the
  reference, persist, bank-and-emit, on paper); every dispatched subagent
  reads it first.
- `references/level-kinds.md` — full taxonomy, tell-tale phrases, judging
  method per kind; composite kinds.
- `references/ccc-io-conventions.md` — verbatim file naming, output-only
  submission, formatting pitfalls, full workspace contract.
- `references/tdd-workflow.md` — deriving tests/oracles per kind; RED /
  GREEN / REFACTOR; blind-oracle verification; regression discipline.
