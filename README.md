# WBAILA

**W**hat **B**ird **A**m **I** **L**ooking **A**t? — a [WAILA](https://github.com/profmobius/Waila)-style "what am I looking at" tool for birds and other wildlife.

> 中文简介：WBAILA（"我在看的是什么鸟？"）是一个 WAILA 风格的野生动物鉴定命令行工具。当前内置 `dongniao` 后端，调用懂鸟动物识别 API 实现拍照识鸟；后续计划加入更多后端（例如基于 LLM 的资料检索与辅助鉴定）。本项目为非官方客户端，详见下方声明。

Identify an animal from a photo (and, over time, more input types) via
pluggable identification backends, one subcommand each:

```bash
uvx wbaila dongniao photo.jpg
```

## LLM usage transparency

This repo is built by using LLM exclusively. I don't like python and I don't have any plan to learn it.
However, it is the most convenient way to run stuff (thanks to `uvx`). As a matured developer, I choose
whatever fits the best and let LLM handles the coding.

And I also don't like vibe coding as it only delivers AI slops. So I will do my best to not turn this
repo into AI slop. However, if you're AIphobia or antiAI person, feel free to hit Ctrl+W now.

## Backends

| backend     | input | service                                                            |
| ----------- | ----- | ------------------------------------------------------------------ |
| `dongniao`  | image | Dongniao (懂鸟) animal recognition API — HHOLOVE AI Open Platform |

The `dongniao` backend preprocesses the image locally (EXIF rotation fix, JPEG conversion,
resizing to meet the API's 11~8192 px / 2 MB limits), submits the recognition task, polls for
the result, and prints exactly one JSON document — the API's own `[code, payload]` shape — so
the output is `jq`-friendly.

## Usage

```bash
# Direct, with your own API key (the platform offers free test quota):
HHODATA_API_KEY=xxxx uvx wbaila dongniao photo.jpg

# Or through a local relay that injects the key:
HHODATA_API_BASE=http://10.233.1.8:8002/relay/hhodata \
    uvx wbaila dongniao photo.png --class BM

# Windows PowerShell:
#   $env:HHODATA_API_KEY = "xxxx"; uvx wbaila dongniao photo.jpg
#   $env:HHODATA_API_BASE = "http://10.233.1.8:8002/relay/hhodata"; uvx wbaila dongniao photo.jpg
```

Options: `--class BM` (B bird / M mammal / A amphibian / R reptile), `--area CODE` (region filter),
`--did ID` (client ID), `--interval` and `--max-retries` (polling).

Exit codes: `0` success, `1` API-level business error, `2` local or network error. See `cli/README.md`
for the full reference.

## Disclaimer / 声明

WBAILA is an **unofficial** client, written for personal use and published as open source.
It is not affiliated with, endorsed by, or sponsored by 懂鸟 (Aboutbirds), HHOLOVE, or 两氢一氧(杭州)数字科技有限公司;
all related trademarks belong to their respective owners.
To use the API, register your own account and API key on the [HHOLOVE AI Open Platform](https://ai.open.hhodata.com/).

本项目为独立开发的非官方客户端，与懂鸟(Aboutbirds)、HHOLOVE 及两氢一氧(杭州)数字科技有限公司无任何隶属、合作或背书关系；
相关商标归其权利人所有。

## Repository layout

- `cli/` — the `wbaila` Python CLI, an independent
  [uv](https://docs.astral.sh/uv/) project; published to PyPI as
  `wbaila` (development conventions in `cli/AGENTS.md`).
- Agent-facing helpers (skills, MCP servers) are planned as further
  subprojects in their own directories.

## Development

```bash
git clone https://github.com/hurui200320/wbaila
cd wbaila/cli
uv sync
pyright                      # strict, 0 errors expected
uvx ruff check .
uvx ruff format --check .
uv run wbaila dongniao --help
```

To cut a release: `uv build && uv publish`.

## License

[AGPL-3.0](LICENSE) — see also the disclaimer above.
