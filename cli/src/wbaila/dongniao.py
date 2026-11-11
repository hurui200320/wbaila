"""Dongniao (懂鸟) animal recognition backend for WBAILA.

Pipeline: preprocess the image locally with wbaila.imageprep (EXIF
orientation fix, JPEG conversion, optional resizing to meet the API
limits of 11~8192 px per edge and <= 2MB) -> submit the recognition
task -> poll for the result -> print exactly one JSON document to
stdout. Preprocessing failures raise `wbaila.imageprep.ImageError`,
which `run()` maps onto the local-error output below.

stdout always carries a single JSON array in the API's own shape:

    [code, payload]

where `code` is the API business code (1000 = success), or 0 for local /
HTTP-level failures with an English error message as the payload. This
keeps the output safe to pipe into tools like jq.

Dependencies: Python 3.13 standard library + Pillow (declared in
pyproject.toml).

Environment variables:
    HHODATA_API_KEY   API key; the header is skipped when unset or empty
                      (e.g. when going through a relay injecting the key)
    HHODATA_API_BASE  API base URL; defaults to
                      https://ai.open.hhodata.com/api/v2

Exit codes: 0 = got a recognition result (code 1000); 1 = API-level
business error or polling timeout; 2 = local or network error.

Examples:
    # Through a bifrost relay (no api key needed)
    HHODATA_API_BASE=http://10.233.1.8:8002/relay/hhodata \\
        uvx wbaila dongniao ~/Pictures/DSC_3006_DxO.png --class BM

    # Direct against the official API (api key required)
    HHODATA_API_KEY=xxxx uvx wbaila dongniao photo.jpg

Code style: see cli/AGENTS.md (pyright strict, ruff check + ruff format).
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any, NoReturn

from wbaila import imageprep

DEFAULT_API_BASE = "https://ai.open.hhodata.com/api/v2"
ENV_API_KEY = "HHODATA_API_KEY"
ENV_API_BASE = "HHODATA_API_BASE"

HTTP_TIMEOUT = 60  # per-request timeout in seconds

CODE_OK = 1000  # task accepted / result ready
CODE_PENDING = 1001  # upload: image over 2MB; poll: result not ready yet


def fail(message: str, exit_code: int = 2) -> NoReturn:
    """Print the error form of the final JSON to stdout and exit.

    All local/HTTP-level failures are reported as [0, "<message>"] so
    that stdout stays a single, consistently shaped JSON document.
    """
    print(json.dumps([0, message], ensure_ascii=False, indent=2))
    sys.exit(exit_code)


# ---------------------------------------------------------------- HTTP layer


def build_multipart(
    fields: dict[str, str], file_field: tuple[str, str, bytes, str]
) -> tuple[bytes, str]:
    """Build a multipart/form-data body.

    file_field is a tuple of (field name, filename, data, MIME type).
    """
    boundary = "dongniao-" + uuid.uuid4().hex
    name, filename, data, content_type = file_field
    chunks: list[bytes] = []
    for key, value in fields.items():
        chunks.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{key}"\r\n\r\n'
                f"{value}\r\n"
            ).encode()
        )
    chunks.append(
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"; '
            f'filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode()
        + data
        + b"\r\n"
    )
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def parse_json_body(raw: bytes, http_status: int) -> Any:
    text = raw.decode("utf-8", errors="replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        fail(f"server returned a non-JSON response (HTTP {http_status}): {text[:300]}")


def post_form(
    url: str, headers: dict[str, str], body: bytes, content_type: str
) -> tuple[int, Any]:
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", content_type)
    for key, value in headers.items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
            return response.status, parse_json_body(response.read(), response.status)
    except urllib.error.HTTPError as exc:
        # the API also answers 4xx/5xx with a [code, message] JSON body
        return exc.code, parse_json_body(exc.read(), exc.code)
    except urllib.error.URLError as exc:
        fail(f"cannot connect to {url}: {exc.reason}")
    except TimeoutError:
        fail(f"request to {url} timed out after {HTTP_TIMEOUT}s")


def expect_pair(payload: Any, http_status: int, action: str) -> tuple[int, Any]:
    """Check that the response matches the API's [code, data] shape."""
    # Unpack defensively instead of isinstance() narrowing: payload is Any,
    # and isinstance() would narrow it to list[Unknown] under strict mode.
    # Any 2-element iterable unpacks; lists/dicts/strings that don't match
    # the [int, ...] shape end up in the failure branch below.
    code: Any = None
    data: Any = None
    try:
        code, data = payload
        valid = isinstance(code, int)
    except (TypeError, ValueError):
        valid = False
    if not valid:
        fail(
            f"{action}: unexpected response format (HTTP {http_status}): "
            f"{json.dumps(payload, ensure_ascii=False)[:300]}"
        )
    return code, data


# ---------------------------------------------------------------- workflow


def upload_image(
    url: str, headers: dict[str, str], jpeg_bytes: bytes, args: argparse.Namespace
) -> tuple[int, Any]:
    """Submit the recognition task; returns the [code, data] pair."""
    fields: dict[str, str] = {"upload": "1", "class": args.animal_class}
    if args.area:
        fields["area"] = args.area
    if args.did:
        fields["did"] = args.did
    body, content_type = build_multipart(
        fields, ("image", "image.jpg", jpeg_bytes, "image/jpeg")
    )
    http_status, payload = post_form(url, headers, body, content_type)
    return expect_pair(payload, http_status, "task submission")


def poll_result(
    url: str,
    headers: dict[str, str],
    resultid: str,
    interval: float,
    max_retries: int,
) -> tuple[int, Any]:
    """Poll for the recognition result; returns the terminal [code, data]."""
    body = urllib.parse.urlencode({"resultid": resultid}).encode()
    for _ in range(max_retries):
        http_status, payload = post_form(
            url, headers, body, "application/x-www-form-urlencoded"
        )
        code, data = expect_pair(payload, http_status, "result polling")
        if code == CODE_PENDING:
            time.sleep(interval)
            continue
        return code, data  # 1000 = result ready, anything else = terminal
    fail(f"no result after {max_retries} polls; giving up", exit_code=1)


# ---------------------------------------------------------------- CLI wiring


def register(
    # typeshed exposes no public alias for the subparsers action type
    subparsers: argparse._SubParsersAction[  # pyright: ignore[reportPrivateUsage]
        argparse.ArgumentParser
    ],
) -> None:
    """Register the `dongniao` subcommand on the wbaila CLI parser."""
    parser = subparsers.add_parser(
        "dongniao",
        help="identify animals with the Dongniao (懂鸟) recognition API",
        description="Dongniao (懂鸟) animal recognition API client: preprocess "
        "the image, submit it, poll and print the final JSON.",
    )
    parser.add_argument("image", help="path of the image to recognize")
    parser.add_argument(
        "--class",
        dest="animal_class",
        default="BM",
        help="animal classes, a combination of B(bird)/M(mammal)/"
        "A(amphibian)/R(reptile) (default: BM)",
    )
    parser.add_argument(
        "--area", default="", help="area code to filter results (optional)"
    )
    parser.add_argument(
        "--did",
        default="",
        help="unique device/client ID, alphanumeric only (optional)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="polling interval in seconds (default: 2)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=30,
        help="maximum number of polls (default: 30)",
    )
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    """Execute the dongniao workflow; returns the process exit code."""
    if set(args.animal_class) - set("BMARF"):
        fail("--class must be a combination of B/M/A/R/F")
    if args.did and not (args.did.isascii() and args.did.isalnum()):
        fail("--did must contain ASCII letters and digits only")

    base = os.environ.get(ENV_API_BASE, "").strip() or DEFAULT_API_BASE
    url = base.rstrip("/") + "/dongniao"
    api_key = os.environ.get(ENV_API_KEY, "").strip()
    headers: dict[str, str] = {"api_key": api_key} if api_key else {}

    try:
        im = imageprep.load_rgb(args.image)
        jpeg_bytes, _, _ = imageprep.prepare_image(im, imageprep.Constraints())
    except imageprep.ImageError as exc:
        fail(str(exc))
    code, data = upload_image(url, headers, jpeg_bytes, args)
    if code == CODE_OK:
        code, data = poll_result(url, headers, data, args.interval, args.max_retries)

    print(json.dumps([code, data], ensure_ascii=False, indent=2))
    return 0 if code == CODE_OK else 1
