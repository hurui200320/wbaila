# AGENTS.md — `wbaila` CLI subproject

Coding conventions for the Python CLI package in this directory
(`src/wbaila/`). The repo root's `AGENTS.md` describes the overall
repository layout. The checks in the last section must pass before you
consider a change done.

## Scope & layout

- This directory is an independent `uv` project: the `wbaila` package,
  published to PyPI and normally invoked as `uvx wbaila <backend> ...`.
- Python 3.14+. Prefer the standard library; Pillow is allowed for
  image work (and is the only runtime dependency). numpy is a
  **dev-only** dependency: pillow's annotations define `NumpyArray`
  under `TYPE_CHECKING`, so pyright needs numpy importable in the
  analysis environment (`.venv`); it is never needed at runtime.
- Each identification backend lives in one module under `src/wbaila/`
  (currently `dongniao.py`) and exposes:
  - `register(subparsers)`: argparse subcommand registration (sets the
    `func` default);
  - `run(args)`: the workflow, returning the process exit code.
  New backends must be registered in `__main__.py:build_parser` under a
  subcommand named after the service (e.g. `inaturalist`).
- Shared image preprocessing lives in `src/wbaila/imageprep.py`
  (loading with EXIF fix + RGB conversion, edge fitting, JPEG encoding
  under size limits). It is a pure library layer: it raises
  `ImageError` and never touches stdout, exit codes, or argparse.
  Backends catch `ImageError` and map the message onto the standard
  `[0, "<message>"]` output via `fail()`.
- Shared clipboard grabbing lives in `src/wbaila/clipread.py` (the
  `--clipboard` input source; wraps `PIL.ImageGrab.grabclipboard`
  with a macOS TIFF/JPEG fallback and Windows file-path handling).
  Same library-layer contract as `imageprep.py`: raises `ImageError`
  only, no stdout/exit-code side effects.
- Cross-backend helpers (e.g. `fail()`) currently live in
  `dongniao.py`; factor them into a shared module when the second
  backend actually needs them.
- Tests live in `tests/` (a plain package, excluded from the wheel).
  They are offline (no API quota); run them with
  `uv run python -m unittest discover -s tests`.

## Language conventions

- Comments, docstrings, CLI help text, and error messages: **English**.
- Product/API proper nouns may stay in their original language
  (e.g. 懂鸟/Dongniao in the module docstring).

## Output contract (CLI scripts)

- **stdout carries exactly one JSON document** and nothing else:
  `[code, payload]`, mirroring the backend API's own shape. Local and
  HTTP-level failures use the same shape with code `0`:
  `[0, "<english error message>"]`. Never print progress, banners, or
  logs to stdout; scripts should stay pipe-friendly (`jq` etc.).
- Prefer writing nothing to stderr at all; if a script ever needs
  progress output, it must go to stderr, never stdout.
- Exit codes: `0` = success; `1` = API-level business error or timeout;
  `2` = local or network error. `run()` returns the exit code; only
  error paths may `sys.exit()` directly (via `fail()`).
- argparse usage errors are the one exception: argparse prints its own
  message to stderr and exits 2 before any backend code runs.

## Type checking — pyright, strict mode

Configured in `pyrightconfig.json` (`typeCheckingMode: "strict"`).
Run with the system `pyright` binary; imports resolve from `.venv`,
so run `uv sync` once after cloning or after dependency changes.

- Every function needs full parameter **and** return annotations. Use
  precise types (`tuple[bytes, int, tuple[int, int]]`) rather than bare
  `Any`.
- Functions that always exit or raise (e.g. `fail()`) must be annotated
  `-> NoReturn` so callers get control-flow narrowing (possibly-unbound
  variables after an `except` branch, unreachable returns, etc.).
- `Any` is acceptable only at the JSON boundary (values coming from
  `json.loads`) and at the argparse `Namespace` boundary; do not let it
  leak into image/HTTP layer signatures.
- Gotcha: `isinstance(x, list)` narrows an `Any` value to
  `list[Unknown]` under strict mode, which then fails
  `reportUnknownArgumentType` on `len()`/subscripts. Prefer defensive
  unpacking (`code, data = payload` in a `try/except`) or
  `typing.cast("list[Any]", ...)` over chained isinstance checks.
- Do not silence diagnostics with `# pyright: ignore` unless there is a
  comment explaining why; restructure the code instead when possible.

## Lint & format — ruff

Configured in `ruff.toml` (line length 88, `target-version = "py314"`,
rules `E4/E7/E9/F + UP + ISC`). ruff is not installed locally; run it
through `uvx ruff`.

- Code must be `ruff format`-clean.
- Typical fixes the ruleset enforces:
  - `UP012`: `.encode()` instead of `.encode("utf-8")` (UTF-8 is the
    default).
  - `ISC004`: parenthesize implicitly concatenated strings when they
    sit inside a collection literal, or split them across lines inside
    existing parentheses.
- No unused imports/variables (F401/F841); no bare `except:` (E722).

## Checks before finishing a change

From this directory:

```bash
uv sync                              # keep .venv / uv.lock in sync
pyright                              # 0 errors (strict)
uvx ruff check .                     # all checks passed
uvx ruff format --check .            # no diff
uv run python -m unittest discover -s tests   # imageprep unit tests pass
```

Plus a smoke test of the failure paths (does not consume API quota):

```bash
uv run wbaila dongniao --image /nonexistent.jpg
# -> [0, "image file not found: ..."] on stdout, exit code 2
```

When touching `pyproject.toml`, also run `uv build` to catch packaging
problems early.
