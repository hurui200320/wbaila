"""Shared local image preprocessing for WBAILA backends.

Loads an image file as an RGB image (with EXIF orientation fix), fits
its edges into a pixel-size range, and encodes it as a JPEG under a
byte limit — stepping down quality first, then shrinking.

This module is a pure library layer: any local failure raises
`ImageError` and never touches stdout or the process exit code.
Backends catch it and translate the message into their own output
contract (see the `fail()` helper in `dongniao.py`).

Dependencies: Python 3.13 standard library + Pillow (declared in
pyproject.toml; a missing Pillow surfaces as a normal ImportError).

Code style: see cli/AGENTS.md (pyright strict, ruff check + ruff format).
"""

import io
from dataclasses import dataclass

from PIL import Image, ImageOps


class ImageError(Exception):
    """A local image preprocessing failure; the message is user-facing."""


@dataclass(frozen=True)
class Constraints:
    """Limits and tuning knobs for image preparation.

    The edge and byte defaults mirror the Dongniao API's current
    requirements; backends with different limits pass their own values.
    """

    min_edge: int = 11  # minimum pixels per edge
    max_edge: int = 8192  # maximum pixels per edge
    max_bytes: int = 2_000_000  # encoded size limit (2MB with a small margin)
    qualities: tuple[int, ...] = (90, 85, 80, 75, 70, 60, 50, 40, 30)
    shrink_factor: float = 0.8  # edge scale-down factor when still over max_bytes


# ---------------------------------------------------------------- image prep


def load_rgb(path: str) -> Image.Image:
    """Open the image, fix EXIF orientation, convert to RGB.

    Returns an image object that no longer depends on the file handle.

    Raises ImageError when the file is missing or unreadable.
    """
    try:
        src = Image.open(path)
    except FileNotFoundError:
        raise ImageError(f"image file not found: {path}") from None
    except OSError as exc:
        raise ImageError(f"cannot open image {path}: {exc}") from None
    with src:
        im = ImageOps.exif_transpose(src)
        if im.mode != "RGB":
            im = im.convert("RGB")
        if im is src:
            # exif_transpose may return the original object when nothing
            # needs transposing; copy to detach from the file handle
            im = src.copy()
    return im


def fit_edges(im: Image.Image, constraints: Constraints) -> Image.Image:
    """Clamp every edge into the constrained pixel range (aspect kept).

    Oversized images are scaled down so the longest edge is max_edge;
    undersized ones are scaled up so the shortest edge is min_edge.

    Raises ImageError when the aspect ratio makes the range unreachable.
    """
    lo, hi = constraints.min_edge, constraints.max_edge
    width, height = im.size
    longest, shortest = max(width, height), min(width, height)
    if longest > hi and shortest < lo:
        raise ImageError(
            f"image {width}x{height} cannot fit the {lo}~{hi} px requirement"
        )
    if longest > hi:
        factor = hi / longest
    elif shortest < lo:
        factor = lo / shortest
    else:
        return im
    new_size = (round(width * factor), round(height * factor))
    if min(new_size) < lo or max(new_size) > hi:
        raise ImageError(
            f"extreme aspect ratio ({width}x{height}) cannot fit the "
            f"{lo}~{hi} px requirement"
        )
    return im.resize(new_size, Image.Resampling.LANCZOS)


def encode_jpeg(
    im: Image.Image, constraints: Constraints
) -> tuple[bytes, int, tuple[int, int]]:
    """Encode as JPEG under max_bytes: step down quality first, then shrink.

    Returns (jpeg_bytes, quality, (width, height)).

    Raises ImageError when even the minimum size cannot fit the limit.
    """
    while True:
        for quality in constraints.qualities:
            buffer = io.BytesIO()
            im.save(buffer, "JPEG", quality=quality, optimize=True)
            data = buffer.getvalue()
            if len(data) <= constraints.max_bytes:
                return data, quality, im.size
        width, height = im.size
        factor = constraints.shrink_factor
        new_size = (round(width * factor), round(height * factor))
        if min(new_size) < constraints.min_edge:
            raise ImageError(
                f"cannot get the image under {constraints.max_bytes} bytes "
                "even at the minimum size; please shrink it manually"
            )
        im = im.resize(new_size, Image.Resampling.LANCZOS)


def prepare_image(
    im: Image.Image, constraints: Constraints
) -> tuple[bytes, int, tuple[int, int]]:
    """Fit the edges and encode; return (jpeg_bytes, quality, (w, h))."""
    return encode_jpeg(fit_edges(im, constraints), constraints)
