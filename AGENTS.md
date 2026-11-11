# AGENTS.md — wbaila (repository root)

**WBAILA** = **W**hat **B**ird **A**m **I** **L**ooking **A**t? A
WAILA-style "what am I looking at" tool family for birds and wildlife.

## Repository layout

- `cli/` — the `wbaila` CLI: an independent uv project, published to
  PyPI as `wbaila` and normally invoked as `uvx wbaila <backend> ...`.
  **All Python work lives here**; its conventions and required checks
  are specified in `cli/AGENTS.md` and must be followed.
- Future agent-facing helpers (skills, MCP servers, agent tooling)
  will get their own subdirectories, each as an independent project
  with its own `AGENTS.md`.

## Repo-wide rules

- Naming hygiene: the project/brand is `wbaila`. `dongniao` appears
  only as a backend module name, subcommand name, and the API endpoint
  path — never as the project name. Keep it that way (trademark).
- Public-facing text (READMEs, docs, CLI help) is English; product/API
  proper nouns may stay in their original language (懂鸟/Dongniao).
- Third-party branding: describe the services we call factually and
  mark the project as unofficial (see the disclaimer in README.md);
  never imply endorsement, and never copy third-party documentation or
  logos into this repository.
- `cli/uv.lock` is committed; keep it in sync with
  `cli/pyproject.toml` (`uv sync` after any dependency change).
- License: AGPL-3.0 (see `LICENSE`).
