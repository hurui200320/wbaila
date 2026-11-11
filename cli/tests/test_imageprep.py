"""Offline unit tests for the wbaila.imageprep module.

No network access and no API quota: everything runs on small
in-memory images, plus real files in a temporary directory for the
loading tests. Run from cli/ with:

    uv run python -m unittest discover -s tests
"""

import random
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from wbaila import imageprep
from wbaila.imageprep import Constraints, ImageError


def make_image(
    size: tuple[int, int], color: tuple[int, int, int] = (0, 0, 0)
) -> Image.Image:
    """Create a solid-color RGB image of the given size."""
    return Image.new("RGB", size, color)


class ConstraintsTests(unittest.TestCase):
    def test_defaults_match_dongniao_limits(self) -> None:
        c = Constraints()
        self.assertEqual((c.min_edge, c.max_edge, c.max_bytes), (11, 8192, 2_000_000))


class LoadRgbTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def test_missing_file(self) -> None:
        missing = str(self.dir / "nope.png")
        with self.assertRaises(ImageError) as ctx:
            imageprep.load_rgb(missing)
        self.assertIn("image file not found", str(ctx.exception))
        self.assertIn(missing, str(ctx.exception))

    def test_unreadable_path(self) -> None:
        # a directory is not an openable image -> OSError branch
        with self.assertRaises(ImageError) as ctx:
            imageprep.load_rgb(str(self.dir))
        self.assertIn("cannot open image", str(ctx.exception))

    def test_converts_to_rgb(self) -> None:
        path = self.dir / "alpha.png"
        Image.new("RGBA", (8, 6), (255, 0, 0, 128)).save(path)
        im = imageprep.load_rgb(str(path))
        self.assertEqual(im.mode, "RGB")
        self.assertEqual(im.size, (8, 6))

    def test_fixes_exif_orientation(self) -> None:
        src = make_image((20, 10), (0, 128, 255))
        exif = src.getexif()
        exif[274] = 6  # orientation: 90-degree rotation at capture time
        path = self.dir / "rotated.jpg"
        src.save(path, exif=exif)
        im = imageprep.load_rgb(str(path))
        self.assertEqual(im.size, (10, 20))  # dimensions swapped back


class FitEdgesTests(unittest.TestCase):
    def test_downscales_oversized(self) -> None:
        im = make_image((100, 20))
        out = imageprep.fit_edges(im, Constraints(min_edge=10, max_edge=50))
        self.assertEqual(out.size, (50, 10))

    def test_upscales_undersized(self) -> None:
        im = make_image((5, 4))
        out = imageprep.fit_edges(im, Constraints())
        self.assertEqual(out.size, (14, 11))

    def test_keeps_in_range_image(self) -> None:
        im = make_image((100, 50))
        out = imageprep.fit_edges(im, Constraints())
        self.assertEqual(out.size, (100, 50))

    def test_rejects_both_violations(self) -> None:
        im = make_image((60, 5))
        with self.assertRaises(ImageError) as ctx:
            imageprep.fit_edges(im, Constraints(min_edge=10, max_edge=50))
        self.assertIn("image 60x5 cannot fit the 10~50 px", str(ctx.exception))

    def test_rejects_extreme_aspect_ratio(self) -> None:
        im = make_image((1000, 20))
        with self.assertRaises(ImageError) as ctx:
            imageprep.fit_edges(im, Constraints(min_edge=10, max_edge=50))
        self.assertIn("extreme aspect ratio (1000x20)", str(ctx.exception))


class EncodeJpegTests(unittest.TestCase):
    JPEG_MAGIC = b"\xff\xd8"

    def test_first_quality_when_already_small(self) -> None:
        data, quality, size = imageprep.encode_jpeg(
            make_image((100, 100)), Constraints()
        )
        self.assertEqual(data[:2], self.JPEG_MAGIC)
        self.assertEqual(quality, 90)  # the first rung of the ladder
        self.assertEqual(size, (100, 100))
        self.assertLessEqual(len(data), Constraints().max_bytes)

    def test_shrinks_until_under_limit(self) -> None:
        # random noise is incompressible, so a tight limit forces shrinking
        rng = random.Random(42)
        noise = Image.frombytes("RGB", (300, 300), rng.randbytes(300 * 300 * 3))
        constraints = Constraints(max_bytes=4000)
        data, quality, size = imageprep.encode_jpeg(noise, constraints)
        self.assertLessEqual(len(data), 4000)
        self.assertLess(max(size), 300)  # shrunk at least once
        self.assertIn(quality, constraints.qualities)
        self.assertEqual(data[:2], self.JPEG_MAGIC)

    def test_fails_when_limit_unreachable(self) -> None:
        with self.assertRaises(ImageError) as ctx:
            imageprep.encode_jpeg(make_image((50, 50)), Constraints(max_bytes=1))
        self.assertIn("cannot get the image under 1 bytes", str(ctx.exception))


class PrepareImageTests(unittest.TestCase):
    def test_composes_fit_and_encode(self) -> None:
        data, quality, size = imageprep.prepare_image(
            make_image((100, 40)), Constraints(max_edge=50)
        )
        self.assertEqual(size, (50, 20))
        self.assertEqual(data[:2], b"\xff\xd8")
        self.assertEqual(quality, 90)  # solid color fits at the top quality


if __name__ == "__main__":
    unittest.main()
