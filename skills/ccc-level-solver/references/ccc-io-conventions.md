# CCC I/O conventions and output-only submission

Practical notes on how Cloudflight Coding Contest levels are delivered and
judged, and the formatting pitfalls that lose points.

## Delivery model

- Each level gives you one or more **input files** and asks for **answer files**
  (outputs). This is **output-only**: you upload answers, not source code.
  (You may also upload source later for bonus time, but that is not how the level
  is judged.)
- Levels are **gated and sequential**: you cannot skip ahead. Each level is a
  **fresh contract** (defined in `../SKILL.md`): re-derive it from its own
  statement rather than assuming the previous level's rules, tests, or solver
  still apply.
- All languages are allowed. You produce the answer files however you like —
  usually by writing a program that reads each input and writes an output.

## File naming

**The platform's provided file names are the truth.** The workspace preserves
them verbatim; nothing is renamed. Two delivery shapes are recognized:

School track — flat download, `in_`/`out_` prefix pairs:

```
in_level3_1.txt  in_level3_2.txt  ...          inputs, as provided
in_level3_0-example.txt / out_level3_0-example.txt   worked example, as provided
level3.pdf                                     statement, as provided
```

The answer to `in_X.<ext>` is `out_X.<ext>` in `outputs/` — the same prefix
swap the platform itself uses for its example answers.

Classic track — shared stem:

```
level3_1.in -> outputs/level3_1.out
```

- Keep a **1:1 mapping** between input and answer; `run_solver.py` derives the
  answer name from the input name automatically (`in_X.<ext>` → `out_X.<ext>`,
  otherwise `X.in` → `X.out`).
- Worked examples ship as input+answer pairs and are copied to `samples/`
  under their provided names (`in_X` + `out_X`, or `X.in` + `X.out`). They are
  reference material, never answers to submit.
- Statement PDFs keep names like `level3.pdf`; point `level.json`'s
  `statement` key at the provided name (the tooling also finds `level-*.pdf`
  on its own).

## Formatting pitfalls

The judge compares text. Avoid these:

- **Trailing newline:** emit a single final `\n`, and treat the trailing bytes
  as insignificant when checking: the platform's own answers disagree (some end
  with one `\n`, some with a blank line, the level-1 fixture with none), so no
  convention can be imitated reliably. Our comparisons trim both sides first
  (`_common.trim_output`), and a level's checker must accept blank lines at the
  end too. Mirroring a provided example's bytes exactly is allowed, never
  required.
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
better than the example" rather than giving a number. The judging model
(`direction: "min"`, the sample as the initial threshold) is in
`level-kinds.md`; the file-level consequences:

- Store the provided example answer's score as `judge.best` in `level.json`
  (the initial threshold to beat).
- Keep the best-known answer in `outputs/` at all times; never overwrite it
  with a worse one.
- Reproducibility matters: pin any randomness (record the seed) so an
  improvement can be regenerated.

## Workspace contract

This skill expects (and `scripts/scaffold_level.py` can create) — the level
directory's final state once a level is solved. The *provided* files at
handoff are listed in `../SKILL.md` under Inputs; everything below is what
you add:

```
<level_dir>/
  statement.*      problem text, under its provided name (e.g. level3.pdf)
  inputs/          provided input files, names kept verbatim (in_X.txt / X.in)
  samples/         provided worked-example pairs (in_X + out_X, or X.in + X.out)
  verifier/        optional provided checker/visualizer
  notes/inputs.md   your parsed-input analysis, persisted (Phase 0)
  notes/spec.md    your extracted specification (Phase 2)
  level.json       kind + run + judge config
  solver.py        your solver (contract: {in} -> {out})
  checker.py       oracle for exact / any_valid
  scorer.py        oracle for optimization (validate + score)
  tests/           pytest tests
  outputs/         generated answers, named after their inputs — what you upload
  report.md        final summary (Phase 6)
```

Each provided file lives in exactly one place: an input in `inputs/`, a
worked-example pair in `samples/`, the statement under its provided name at the
root. `scaffold_level.py --import` **moves** rather than copies, precisely so
there is no second, silently drifting twin of a provided file to read from or
edit by mistake; a level dir left with flat `in_*`/`out_*` files at its root is
un-normalized.