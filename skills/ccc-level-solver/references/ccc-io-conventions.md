# CCC I/O conventions and output-only submission

Practical notes on how Cloudflight Coding Contest levels are delivered and
judged, and the formatting pitfalls that lose points.

## Delivery model

- Each level gives you one or more **input files** and asks for **answer files**
  (outputs). This is **output-only**: you upload answers, not source code.
  (You may also upload source later for bonus time, but that is not how the level
  is judged.)
- Levels are **gated and sequential**: you cannot skip ahead. Harder levels
  usually extend the previous level's model with more constraints.
- All languages are allowed. You produce the answer files however you like —
  usually by writing a program that reads each input and writes an output.

## File naming

Community tooling and CCC downloads typically use names like:

```
level3_1.in      level3_2.in      level3_3.in      ...
level3_1.out     level3_2.out     level3_3.out     ...
```

- Keep a **1:1 mapping** between input and output names: `X.in` → `X.out`.
- Our default workspace uses `inputs/*.in` → `outputs/*.out` with the same base
  name. `scripts/run_solver.py` preserves the base name automatically.
- Some levels ship the first file(s) as **worked examples** with a provided
  `.out`. Treat those as samples (copy to `samples/`), not as answers to submit.

## Formatting pitfalls

The judge compares text. Avoid these:

- **Trailing newline:** end the file with a single `\n` (our templates enforce
  this). Extra blank lines can fail.
- **Trailing spaces:** strip them; some judges are whitespace-tolerant, some not.
- **Line endings:** LF, not CRLF.
- **Number formatting:** integers without leading zeros; floats to the required
  precision; watch `-0`, exponent notation, and locale decimal separators.
- **Ordering:** if the statement fixes an order, follow it exactly; do not sort
  unless told to.
- **Empty answers:** print nothing but a newline, or as the statement specifies.

Unless the statement says otherwise, `checker.py` for `exact` levels compares
**token by token after stripping trailing whitespace**, and reports the first
differing line so you can see the mismatch.

## Optimization levels in CCC

Some CCC levels are scored: the platform may say "your answer is better / not
better than the example" rather than giving a number. Consequences:

- Treat the provided example answer as the initial **threshold to beat**; store it
  as `judge.best`.
- A new answer is accepted only if it is **valid** and **strictly better** under
  the level's metric (usually `min` — smaller/shorter/cheaper).
- Keep the best-known answer in `outputs/` at all times; never overwrite it with
  a worse one.
- Reproducibility matters: pin any randomness (record the seed) so an improvement
  can be regenerated.

## Workspace contract

This skill expects (and `scripts/scaffold_level.py` can create) :

```
<level_dir>/
  statement.*      problem text
  inputs/          *.in   real inputs you must answer
  samples/         sample_*.in + sample_*.out   optional worked examples
  verifier/        optional provided checker/visualizer
  notes/spec.md    your extracted specification (Phase 1)
  level.json       kind + run + judge config
  solver.py        your solver (contract: {in} -> {out})
  checker.py       oracle for exact / any_valid
  scorer.py        oracle for optimization (validate + score)
  tests/           pytest tests
  outputs/         generated answers (*.out) — what you upload
  report.md        final summary (Phase 5)
```