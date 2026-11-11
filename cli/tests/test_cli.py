"""Offline tests for the wbaila CLI argument wiring (no network)."""

import argparse
import unittest

from wbaila.__main__ import build_parser


class DongniaoArgsTests(unittest.TestCase):
    """--image / --clipboard are mutually exclusive and required."""

    def parse(self, argv: list[str]) -> argparse.Namespace:
        return build_parser().parse_args(argv)

    def test_image_flag(self) -> None:
        args = self.parse(["dongniao", "--image", "photo.png"])
        self.assertEqual(args.image, "photo.png")
        self.assertFalse(args.clipboard)

    def test_clipboard_flag(self) -> None:
        args = self.parse(["dongniao", "--clipboard"])
        self.assertTrue(args.clipboard)
        self.assertIsNone(args.image)

    def test_short_clipboard_flag(self) -> None:
        args = self.parse(["dongniao", "-c"])
        self.assertTrue(args.clipboard)

    def test_no_input_is_a_usage_error(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            self.parse(["dongniao"])
        self.assertEqual(ctx.exception.code, 2)

    def test_both_inputs_are_a_usage_error(self) -> None:
        with self.assertRaises(SystemExit):
            self.parse(["dongniao", "--image", "a.png", "--clipboard"])


if __name__ == "__main__":
    unittest.main()
