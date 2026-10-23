# AGENTS.md

- **Purpose.** A TDD pipeline for solving Cloudflight Coding Contest (CCC)
  practice levels, one level at a time, adapting to each level's judging kind
  (`exact` / `any_valid` / `optimization`; taxonomy and tell-tale phrases in
  `.agents/skills/ccc-level-solver/references/level-kinds.md`). Human-in-the-loop with a
  manual bridge: a human downloads a level's statement and inputs, the skill
  builds and verifies a solver locally, and the human uploads the resulting
  answer files; the skill never talks to the contest platform.
- **Scope.** Solving a single CCC level locally, for all judging kinds, Classic
  and School tracks; the Data/AI track is out of scope.
- **Level workspaces** live under `contests/<contest>/<level>/` (for example
  `contests/school-honeycomb/level-2/`). Each level directory is a
  self-contained workspace; provided level files are authoritative (names kept
  verbatim), and the directory contract is documented in
  `.agents/skills/ccc-level-solver/references/ccc-io-conventions.md`.
- **`examples/level1/`** is the worked example (a trivial `exact` level) and
the fixture the repo's own script tests run against — do not mutate it.
- Third-party packages live only in the uv venv: run dev tools via
`uv run pytest -q` (or `.venv/bin/python`). Level code may import them; how
`level.json` commands resolve the venv interpreter is documented in SKILL.md.