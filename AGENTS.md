# AGENTS.md

- **Purpose.** A TDD pipeline for solving Cloudflight Coding Contest (CCC)
  practice levels, one level at a time, adapting to each level's judging kind
  (`exact` / `any_valid` / `optimization`; taxonomy and tell-tale phrases in
  `skills/ccc-level-solver/references/level-kinds.md`). Human-in-the-loop with a
  manual bridge: a human downloads a level's statement and inputs, the skill
  builds and verifies a solver locally, and the human uploads the resulting
  answer files; the skill never talks to the contest platform.
- **Scope.** Solving a single CCC level locally, for all judging kinds (Classic
  and School tracks). Out of scope: platform automation / auto-submission, and
  the Data/AI track.
- **Solve a level** by following `skills/ccc-level-solver/SKILL.md` phase by
  phase — that file owns the phase list; nothing else restates it. When the
  `/ccc-level-solver` command is not registered with the host's Skill tool, read
  SKILL.md and execute the phases manually. Helper scripts in
  `skills/ccc-level-solver/scripts/` are dependency-free Python 3; templates
  live in `skills/ccc-level-solver/templates/`.
- **Level workspaces** live under `contests/<contest>/<level>/` (for example
  `contests/school-honeycomb/level-2/`). Each level directory is a
  self-contained workspace; its contract is documented in
  `skills/ccc-level-solver/references/ccc-io-conventions.md`.
- **Provided level files are authoritative**: keep their names verbatim
  (`in_X.txt` inputs, `out_X.txt` example answers, `level-N.pdf` statement)
  and derive answer names from them.
- **`examples/level1/`** is the worked example (a trivial `exact` level) and
  the fixture the repo's own script tests run against — do not mutate it.
- Run pytest via `uv run pytest -q` (or `.venv/bin/python`); the system
  `python3` has no pytest.
