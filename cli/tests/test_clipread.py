"""Offline unit tests for the wbaila.clipread module.

The real system clipboard is never touched: ImageGrab.grabclipboard()
and the macOS osascript layer are mocked, and the Windows file-path
branch runs on real files in a temporary directory. Run from cli/ with:

    uv run python -m unittest discover -s tests
"""

import binascii
import io
import subprocess
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from unittest import mock

from PIL import Image

from wbaila import clipread
from wbaila.imageprep import ImageError


def grab_mocked(value: object) -> mock._patch:
    """Patch grabclipboard() to return value (use with `with`)."""
    return mock.patch.object(clipread.ImageGrab, "grabclipboard", return_value=value)


class GrabClipboardTests(unittest.TestCase):
    """Handling of the ImageGrab.grabclipboard() result shapes."""

    def test_returns_rgb_image(self) -> None:
        with grab_mocked(Image.new("RGB", (8, 5), (1, 2, 3))):
            out = clipread.grab_image()
        self.assertEqual(out.mode, "RGB")
        self.assertEqual(out.size, (8, 5))

    def test_converts_non_rgb(self) -> None:
        with grab_mocked(Image.new("RGBA", (8, 5), (255, 0, 0, 128))):
            out = clipread.grab_image()
        self.assertEqual(out.mode, "RGB")
        self.assertEqual(out.size, (8, 5))

    def test_no_image(self) -> None:
        # platform pinned so the macOS fallback cannot hijack the test
        with mock.patch("sys.platform", "linux"), grab_mocked(None):
            with self.assertRaises(ImageError) as ctx:
                clipread.grab_image()
        self.assertIn("no image found in the clipboard", str(ctx.exception))

    def test_missing_helper_tool(self) -> None:
        err = NotImplementedError("wl-paste or xclip is required for ...")
        with mock.patch.object(clipread.ImageGrab, "grabclipboard", side_effect=err):
            with self.assertRaises(ImageError) as ctx:
                clipread.grab_image()
        self.assertIn("cannot read the clipboard", str(ctx.exception))
        self.assertIn("install xclip", str(ctx.exception))

    def test_tool_failure(self) -> None:
        with mock.patch.object(
            clipread.ImageGrab, "grabclipboard", side_effect=ChildProcessError("boom")
        ):
            with self.assertRaises(ImageError) as ctx:
                clipread.grab_image()
        self.assertIn("cannot read the clipboard", str(ctx.exception))


class FilePathsTests(unittest.TestCase):
    """Windows CF_HDROP branch: the clipboard carries copied file paths."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def grab_paths(self, paths: list[str]) -> Image.Image:
        with grab_mocked(paths):
            return clipread.grab_image()

    def test_loads_image_path(self) -> None:
        path = self.dir / "shot.png"
        Image.new("RGB", (7, 3), (9, 9, 9)).save(path)
        out = self.grab_paths([str(path)])
        self.assertEqual(out.size, (7, 3))

    def test_prefers_image_suffixes(self) -> None:
        notes = self.dir / "notes.txt"
        notes.write_text("not an image")
        shot = self.dir / "shot.png"
        Image.new("RGB", (5, 5)).save(shot)
        out = self.grab_paths([str(notes), str(shot)])
        self.assertEqual(out.size, (5, 5))

    def test_no_readable_file(self) -> None:
        notes = self.dir / "notes.txt"
        notes.write_text("not an image")
        with self.assertRaises(ImageError) as ctx:
            self.grab_paths([str(notes)])
        self.assertIn("no readable image among the clipboard files", str(ctx.exception))


class MacosFallbackTests(unittest.TestCase):
    """osascript TIFF/JPEG fallback for apps that do not offer PNG."""

    @staticmethod
    def osascript_stdout(im: Image.Image, flavor: str) -> bytes:
        """Build the «data <flavor><hex>» line osascript would print."""
        buf = io.BytesIO()
        im.save(buf, "TIFF" if flavor.startswith("TIFF") else "JPEG")
        marker = flavor.split()[0] + binascii.hexlify(buf.getvalue()).decode().upper()
        return f"«data {marker}»\n".encode()

    @staticmethod
    def run_factory(
        responses: dict[str, bytes | None],
    ) -> Callable[..., subprocess.CompletedProcess[bytes]]:
        """Fake subprocess.run answering each AppleScript flavor."""

        def fake_run(
            cmd: list[str], **_kwargs: object
        ) -> subprocess.CompletedProcess[bytes]:
            script = next(p for p in cmd if "clipboard" in p)
            flavor = script.rsplit(" as ", 1)[1]
            data = responses.get(flavor)
            if data is None:
                return subprocess.CompletedProcess(cmd, 1, b"", b"error")
            return subprocess.CompletedProcess(cmd, 0, data, b"")

        return fake_run

    def grab(self, responses: dict[str, bytes | None]) -> Image.Image:
        with (
            mock.patch("sys.platform", "darwin"),
            grab_mocked(None),
            mock.patch(
                "wbaila.clipread.subprocess.run",
                side_effect=self.run_factory(responses),
            ),
        ):
            return clipread.grab_image()

    def test_tiff_fallback(self) -> None:
        im = Image.new("RGB", (6, 4), (1, 200, 3))
        out = self.grab({"TIFF picture": self.osascript_stdout(im, "TIFF picture")})
        self.assertEqual(out.mode, "RGB")
        self.assertEqual(out.size, (6, 4))

    def test_jpeg_when_tiff_fails(self) -> None:
        im = Image.new("RGB", (4, 4), (0, 0, 255))
        out = self.grab(
            {
                "TIFF picture": None,
                "JPEG picture": self.osascript_stdout(im, "JPEG picture"),
            }
        )
        self.assertEqual(out.mode, "RGB")
        self.assertEqual(out.size, (4, 4))

    def test_no_image_when_all_flavors_fail(self) -> None:
        with self.assertRaises(ImageError) as ctx:
            self.grab({"TIFF picture": None, "JPEG picture": None})
        self.assertIn("no image found in the clipboard", str(ctx.exception))

    def test_undecodable_payload_is_skipped(self) -> None:
        bad = "«data TIFFzznot-hex»\n".encode()
        with self.assertRaises(ImageError) as ctx:
            self.grab({"TIFF picture": bad, "JPEG picture": None})
        self.assertIn("no image found in the clipboard", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
