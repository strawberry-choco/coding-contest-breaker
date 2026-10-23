# Shared rules — read first on every dispatch

These rules apply to every phase of a level. Every dispatch brief assumes
them instead of restating them; the briefs reference them by their leading
word (bolded below).

- **The statement is authoritative.** Samples and earlier levels' notes
  illustrate or summarize; every rule the work leans on is re-verified
  against the current level's statement. Never generalize a rule from
  samples alone.
- **Fresh contract.** A level builds on the previous level's model but adds
  or removes rules. Prior levels' rules, tests, inputs, and solver are not
  a baseline — re-derive from this level's statement, and expect to rewrite
  rather than keep earlier tests. Reusing them unchanged is more likely
  wrong than right.
- **Renders are the reference.** Read the statement from the rendered pages
  recorded in `notes/spec.md`; never re-render the PDF.
- **Persist.** Throwaway analysis dies with the context window: write files
  into the level dir and read them back with the file tool — long tables
  printed to a terminal mangle (dropped characters).
- **Bank-and-emit.** The provided inputs are the entire submission, and
  `outputs/` is the deliverable. The moment an answer passes the oracle it
  is frozen into `outputs/` (a per-key bank the solver emits verbatim is
  fine); build no generality, determinism, or regeneration machinery beyond
  what the provided inputs need.
- **Contest code.** Time is the score, so effort goes into correct output
  files, fast. Spend nothing on what the judge cannot see (docstrings,
  comments, elegance, defensive checks, extensibility), and never trade away
  what the pipeline leans on (the run contract, determinism, iterative-only
  code, the oracle gates, code you can still debug at minute 50).
- **On paper.** Plan-level cost claims are settled by arithmetic on stated
  operation counts at the largest input — never by running prototype code.
  Data checks over the provided instances (closed-form fits, small exact
  probes that discover a construction) are fine.
