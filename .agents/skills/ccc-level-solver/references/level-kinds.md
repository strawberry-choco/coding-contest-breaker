# Level kinds — taxonomy and classification

How a level is *judged* determines how you must solve and verify it. This file
is the reference for **Phase 0**. The taxonomy is drawn from how mainstream
online judges structure problems (classic/exact, special judge, output-only,
interactive, communication, grader/function) and how scored/optimization
contests (marathons, Optil.io-style) judge answers.

## Two orthogonal axes

Do not conflate these:

1. **Delivery** — *how* answers reach the judge.
   - `program` — the judge runs your source code on hidden inputs (classic IOI/ICPC style).
   - `output_only` — you upload answer *files* and no program runs (Codeforces
     output-only, CCC). **CCC is always `output_only`.**
2. **Kind** — *how* an answer is judged. This is what Phase 0 classifies.

CCC levels are `output_only` in delivery, but their kind varies per level. Classify
by kind.

## Kinds

### `exact` — deterministic single answer
Exactly one correct output per input. Judged by comparison after normalizing
trailing whitespace/newlines (and sometimes token order).
- **Tell-tale phrases:** "print the number", "output the shortest path length",
  "how many …", "the answer is unique".
- **Oracle:** `checker.py` = normalized comparison against the reference answer
  (samples provide reference answers for the sample inputs).
- **Risk:** floating point → compare with absolute/relative tolerance; otherwise
  token-by-token.

### `any_valid` — special judge / checker
Many outputs may be correct (constructive problems). A checker validates that
the answer is well-formed and satisfies all stated constraints; it may not need
a reference answer at all.
- **Tell-tale phrases:** "output any valid …", "if multiple answers exist, print
  any", "construct a …", "print a permutation such that …".
- **Oracle:** `checker.py` implementing the constraints. Feed it a deliberately
  invalid answer in tests to prove it rejects garbage.
- **Risk:** a checker that is too strict rejects valid answers; one that is too
  lax accepts invalid ones. Test both directions.

### `optimization` — scored / "better"
The answer is graded by a quality metric; better (smaller/larger/cheaper/faster)
wins, often with no single optimum required.
- **Tell-tale phrases:** "minimize", "maximize", "the smallest", "the fewest",
  "as short as possible", "your score", "fewer points is better", "better than
  the sample".
- **Oracle:** `scorer.py` = **validate first, then score**. Record
  `judge.direction` (`min`/`max`), a `metric` name, and a `baseline`
  (the sample's score, or a trivial construction).
- **CCC specifics:** some CCC levels ask for a *smaller* answer than the
  example; the platform may only tell you "better / not better", not the exact
  score. Model this as `direction: "min"` and treat the sample as the initial
  `best` threshold to beat.
- **Risk:** optimizing an invalid answer. Always validate before comparing scores.

### `interactive`
Your program exchanges messages with a judge (queries + responses), or is a
grader/function you must fill in.
- **Tell-tale phrases:** "you may ask up to Q queries", "the judge responds",
  "implement the function".
- **Handling in CCC:** rare. Only relevant if a level's tooling exposes an
  interactor. Build a local interactor as the oracle (`references/tdd-workflow.md`).
- **Note:** `function`/grader and `communication` (multi-program) are other
  judge shapes in the wider ecosystem; recognize them, but they are unlikely in
  a CCC Classic output-only level.

### `unknown`
Not enough information. Signals conflict, or the statement is incomplete.
Gather more (open the statement, inspect the download, look for a verifier)
before choosing. It is better to pause in `unknown` than to guess a kind and
optimize against the wrong oracle.

## Classification cheat-sheet

| Signal | Likely kind |
| --- | --- |
| Samples with reference outputs + unique-answer wording | `exact` |
| "any valid", "construct", "if several, print any" | `any_valid` |
| "minimize/maximize/smallest/fewest/best/score", a visualizer/score page | `optimization` |
| "queries", "the judge replies", a provided interactor | `interactive` |
| Provided `visualizer.html` / `checker.py` | `any_valid` or `optimization` (open it to tell which) |
| Nothing but inputs and vague text | `unknown` |

## Composite levels

A level can have layers, e.g. "output any valid routing that is *also* as short
as possible": that is `any_valid` **and** `optimization`. Prefer the strongest
constraint: build the validator, then optimize within the valid space. Record the
dominant kind as `optimization` and keep validity checks in the scorer.