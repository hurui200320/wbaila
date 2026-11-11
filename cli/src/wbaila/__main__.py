"""WBAILA command-line entry point.

Dispatches identification backends as subcommands. Every backend prints
exactly one JSON document to stdout — the backend API's own
[code, payload] shape — and exits 0/1/2; see cli/AGENTS.md.
"""

import argparse
import json
import sys

from wbaila import dongniao


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level wbaila parser with one subcommand per backend."""
    parser = argparse.ArgumentParser(
        prog="wbaila",
        description="WBAILA — What Bird Am I Looking At? Identify the bird "
        "or other animal you are looking at.",
    )
    subparsers = parser.add_subparsers(dest="backend", required=True, metavar="backend")
    dongniao.register(subparsers)
    return parser


def main() -> int:
    """Console-script entry point; returns the process exit code."""
    try:
        args = build_parser().parse_args()
        return args.func(args)
    except KeyboardInterrupt:
        print(json.dumps([0, "interrupted"], ensure_ascii=False, indent=2))
        return 130


if __name__ == "__main__":
    sys.exit(main())
