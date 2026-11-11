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
- CI lives in `.github/workflows/`: `test.yml` (checks on push/PR)
  and `release.yml` (PyPI publish + GitHub release, tag-triggered
  only).

## Versioning & releases

- Semantic versioning: `MAJOR.MINOR.PATCH`. While the project is 0.x
  (Development Status :: 4 - Beta), the minor digit carries breaking
  changes (0.2 → 0.3 may break the CLI contract) and the patch digit
  is fixes only; bump to 1.0.0 once the CLI contract is considered
  stable, after which major = breaking, minor = features, patch =
  fixes.
- The single source of truth for the version is `version` in
  `cli/pyproject.toml`. Release tags are `vX.Y.Z` and must match it
  exactly; the release workflow refuses to publish on mismatch.
- Releases are tag-driven from `master` (trunk-based; no release
  branches):
  1. Bump with `uv version X.Y.Z` in `cli/`, then run `uv sync` so
     `cli/uv.lock` records the new version; commit both.
  2. Run the full check suite from `cli/AGENTS.md` plus `uv build`.
  3. Commit, tag the release commit `vX.Y.Z`, and push with the tag.
  4. `.github/workflows/release.yml` builds, publishes to PyPI via
     Trusted Publisher (OIDC; no stored secrets), and creates the
     GitHub Release, with notes generated from the commit log since
     the previous tag. If it fails after tagging, fix, delete and
     re-create the tag — PyPI rejects re-uploading an existing
     version.
- Commit messages follow Conventional Commits (the commitizen
  format): `type(scope): subject`. Types: `feat`, `fix`, `docs`,
  `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`; the
  scope names the area touched (e.g. `imageprep`, `dongniao`,
  `clipread`, `release`). The subject must say what actually
  changed — a bare `refactor` or `update` is not a message. Mark
  breaking changes with `!` (e.g. `feat(cli)!: drop the --raw flag`).
- The same messages drive releases: the release workflow turns the
  `git log` between tags into the GitHub Release body, and the type
  suggests the version bump — `feat` → minor, `fix`/`perf` → patch,
  `!` or a `BREAKING CHANGE:` footer → major (minor while 0.x).
- CI split: the test workflow has no publish rights; only the
  tag-triggered release workflow publishes, and its publish job must
  stay minimal (download artifacts + `pypa/gh-action-pypi-publish`).
  Never attach publishing to PR-triggered workflows.
- All `uses:` actions in workflows are pinned to commit SHAs (with a
  version comment); bump them deliberately, not passively.

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
