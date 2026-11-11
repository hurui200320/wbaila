# wbaila-cli

The `wbaila` cli dispatches to pluggable identification backends, one subcommand each.
The first backend is `dongniao`: an unofficial client for the Dongniao (懂鸟) animal recognition API
(photo identification of birds, mammals, amphibians and reptiles) on the HHOLOVE AI Open Platform.

## Install & run

With [uv](https://docs.astral.sh/uv/) installed, no project setup is needed:

```bash
uvx wbaila dongniao photo.jpg
```

Or install it as a persistent tool:

```bash
uv tool install wbaila
wbaila dongniao photo.jpg
```

Python 3.13+ is required; uv fetches a matching interpreter automatically if missing.
(pipx or a plain `pip install wbaila` work too.)

## Authentication

```bash
# Direct, with your own API key:
HHODATA_API_KEY=xxxx uvx wbaila dongniao photo.jpg

# Or through a relay that injects the key:
HHODATA_API_BASE=https://my-relay.example/relay/hhodata \
    uvx wbaila dongniao photo.jpg
```

- `HHODATA_API_KEY` — API key from the HHOLOVE AI Open Platform; the header is skipped when unset or empty.
- `HHODATA_API_BASE` — API base URL; defaults to `https://ai.open.hhodata.com/api/v2`.

## Options

```text
image                 path of the image to recognize
--class BM            animal classes: B(bird)/M(mammal)/A(amphibian)/R(reptile), any combination (default: BM)
--area CODE           area code to filter results (optional)
--did ID              unique device/client ID, alphanumeric (optional)
--interval SECONDS    polling interval (default: 2)
--max-retries N       maximum number of polls (default: 30)
```

## Output & exit codes

stdout always carries exactly one JSON document in the API's own shape, `[code, payload]` (code `1000` = success,
`0` = local/HTTP failure with an English message) — pipe it into `jq` freely.

Exit codes: `0` success · `1` API-level business error or polling timeout · `2` local or network error.

## Disclaimer

Unofficial project, not affiliated with or endorsed by 懂鸟 (Aboutbirds), HHOLOVE, or 两氢一氧(杭州)数字科技有限公司;
all related trademarks belong to their respective owners.
Register your own API key on the [HHOLOVE AI Open Platform](https://ai.open.hhodata.com/).

## License

AGPL-3.0 (see the repository's LICENSE file).
