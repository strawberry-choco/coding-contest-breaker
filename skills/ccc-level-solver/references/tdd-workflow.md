# TDD workflow for contest levels

Contest "tests" are unusual: the expected result may be a unique string, a set
of constraints, or a number to beat. This file explains how to build the oracle
and derive tests for each kind, and how to run the RED → GREEN → REFACTOR loop.

## The oracle-first rule

Write the thing that decides acceptability **before** the solver. Then:

1. The oracle must accept every provided sample answer. If it rejects a sample,
   the oracle is buggy — fix the oracle.
2. Add a negative test: the oracle must reject an obviously invalid answer.
3. Only then write the solver, and let the oracle test it.

## Building the oracle per kind

### exact
`checker.py` receives input, candidate output, and the expected output (from the
matching sample) and exits 0 if acceptable.

Normalization levels (most tolerant → strictest), pick per statement:
- token-wise, ignoring all whitespace runs (default for CCC),
- line-wise, ignoring trailing spaces,
- exact bytes (only when the statement demands it).

For floats, accept if `abs(a-b) <= atol` or `abs(a-b) <= rtol*max(1,abs(b))`.

### any_valid
`checker.py` receives input and candidate output, and validates:
- output well-formed per the statement (counts, ranges, tokens),
- every stated constraint holds, and
- if a reference exists, that the answer is consistent with the input.

It does **not** need to match a reference answer. Add tests with:
- the provided sample (must be valid),
- a hand-crafted invalid answer (must be rejected),
- a hand-crafted *different but valid* answer (must be accepted) — proves the
  checker is not secretly comparing to a reference.

### optimization
`scorer.py` = `validate(...)` then `score(...)`:
1. If invalid, print an error and exit non-zero (never return a score).
2. Otherwise print a single number (the metric). The smaller/better direction is
   recorded in `level.json` as `judge.direction`.

Tests:
- the sample answer validates and yields the recorded baseline,
- an invalid answer is rejected,
- `score` is deterministic and monotone: a strictly better construction scores
  strictly better.

### interactive
Write a local `interactor.py` that plays the judge: it holds the hidden secret,
answers queries, enforces the query budget, and validates the final answer. Run
the solver as a subprocess over pipes. This is both oracle and test harness.

## RED → GREEN → REFACTOR for a solver

- **RED:** write `tests/test_level.py` from `templates/test_level.py.tmpl`.
  Assert (a) samples pass the oracle, (b) your solver's output passes the oracle,
  (c) for optimization, the solver beats or ties the baseline. Run it; it should
  fail because the solver is not written yet.
- **GREEN:** implement the simplest correct solver (`templates/solver.py.tmpl`).
  Iterate `run_solver.py` → `check_outputs.py` → `pytest` until green.
- **REFACTOR / SCALE:** replace the baseline with an efficient algorithm; keep
  the tests green. For optimization, wrap the loop from Phase 5 and re-run the
  scorer after every accepted improvement.

## Independent verification (the blind oracle)

Unit tests written from the same reading of the statement as the solver
**confirm** the solver instead of testing it: they share the author's blind
spots, so a wrong mental model passes its own tests. (Real case: a staggered
grid's border test was wrong, passed ten unit tests and the structure checker,
and was caught only by a differently formulated implementation.)

After GREEN on an `exact`/`any_valid` level:

1. Have a **fresh-context subagent write `oracle.py` blind** — give it the
   statement and `notes/spec.md`, withhold `solver.py`. Formulation
   independence (different algorithm shape, e.g. union-find vs BFS) plus
   author independence is the point.
2. Run `scripts/cross_check.py`: it feeds samples, real inputs, and — when the
   level provides `fuzz_gen.py` with `generate(rng) -> str` — random small
   cases to both modules and prints a **counterexample** (input + both
   answers) on the first disagreement. A counterexample is a certificate;
   "the code looks right" is not. Agreement is the gate for declaring the
   level solved.
3. Optionally, a second subagent reads statement + solver together and checks
   semantic drift ("does the code implement every stated rule?") — the one
   failure class a second implementation cannot catch, since it can share the
   misreading. One agent run per level is cheap next to a wrong upload.

## Regression discipline (within one level only)

Every time you fix a bug, add a test that reproduces it. Contest solvers fail on
edge cases (size 1, maximal input, ties, ambiguous whitespace) — encode each one
you discover **for the level you are currently solving**.

Do **not** carry tests, rules, or assumptions across levels. Each level is a
**fresh contract** (defined in `../SKILL.md`): a test pinning the previous
level's behavior may be wrong here — or assert something the new statement
forbids. Re-derive the oracle and tests from the current statement every
time, and expect to delete or rewrite prior tests rather than keep them
green. Earlier tests are not a safety net for later levels; they are a
liability.

## When you may change the oracle

Only when it *provably* rejects a valid answer (or accepts an invalid one), and
you have a concrete counterexample. Then fix it and add a test pinning the
corrected behavior. Never weaken the oracle just to make a failing solver pass.