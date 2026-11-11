"""System-clipboard image grabbing for WBAILA backends.

Provides the `--clipboard` input source: returns whatever image the
user last copied (e.g. a crop in a photo editor, a screenshot, or a
copied image file on Windows) as an RGB PIL image, ready for the usual
imageprep pipeline. No temporary files are involved; everything stays
in memory.

How it reads the clipboard:
    Windows  natively via Pillow (PNG / DIB flavors; copying files in
             Explorer yields their paths, which are loaded instead)
    Linux    via Pillow shelling out to wl-paste (Wayland) or xclip
             (X11); one of those helper tools must be installed
    macOS    via Pillow (osascript, PNG flavor), plus a fallback that
             reads the TIFF/JPEG flavors for apps (Preview, Firefox,
             MS Office, ...) that do not offer PNG data on the board

This module is a pure library layer like `wbaila.imageprep`: any
failure raises `ImageError` and never touches stdout or the process
exit code. Backends catch it and translate the message into their own
output contract (see the `fail()` helper in `dongniao.py`).

Dependencies: Python 3.14 standard library + Pillow (declared in
pyproject.toml).

Code style: see cli/AGENTS.md (pyright strict, ruff check + ruff format).
"""

import binascii
import io
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageGrab

from wbaila import imageprep
from wbaila.imageprep import ImageError

# AppleScript data marker: «data <4-char OSType><hex payload>», e.g.
# «data TIFF4d4d002a...». osascript prints exactly this shape.
_OSADATA_RE = re.compile(r"«data ([0-9A-Za-z]*)»")

# macOS fallback flavors, tried in order; "TIFF picture" is what most
# macOS apps put on the board first, JPEG covers the rest.
_MACOS_FLAVORS = ("TIFF picture", "JPEG picture")

# Suffixes preferred when the clipboard carries file paths (Windows
# CF_HDROP after copying files in Explorer).
_IMAGE_SUFFIXES = frozenset(
    {".png", ".jpg", ".jpeg", ".jfif", ".bmp", ".gif", ".webp", ".tif", ".tiff"}
)


def grab_image() -> Image.Image:
    """Return the clipboard contents as an RGB image.

    Raises ImageError when the clipboard holds no readable image or
    the platform cannot be read (e.g. Linux without xclip/wl-paste).
    """
    try:
        grabbed = ImageGrab.grabclipboard()
    except NotImplementedError as exc:
        raise ImageError(
            f"cannot read the clipboard: {exc}; install xclip (X11) or "
            "wl-clipboard (Wayland) with your package manager"
        ) from None
    except OSError as exc:  # ChildProcessError and friends
        raise ImageError(f"cannot read the clipboard: {exc}") from None

    if isinstance(grabbed, Image.Image):
        return _as_rgb(grabbed)
    if isinstance(grabbed, list):
        return _image_from_paths(grabbed)

    # None: no image in the clipboard — or none in the flavor Pillow
    # asks for. On macOS several apps only offer TIFF/JPEG, so try
    # those flavors before giving up.
    if sys.platform == "darwin":
        fallback = _macos_fallback()
        if fallback is not None:
            return _as_rgb(fallback)
    raise ImageError("no image found in the clipboard; copy an image first")


# ---------------------------------------------------------------- helpers


def _as_rgb(im: Image.Image) -> Image.Image:
    """Force eager loading and RGB mode (JPEG encoding needs RGB)."""
    im.load()
    return im if im.mode == "RGB" else im.convert("RGB")


def _image_from_paths(paths: list[str]) -> Image.Image:
    """Load the clipboard image from copied file paths (Windows CF_HDROP).

    Image-looking files are tried first; the first readable one wins.
    Raises ImageError when none of the paths is a readable image.
    """
    candidates = [p for p in paths if Path(p).suffix.lower() in _IMAGE_SUFFIXES]
    if not candidates:
        candidates = paths[:1]
    errors: list[str] = []
    for path in candidates:
        try:
            return imageprep.load_rgb(path)
        except imageprep.ImageError as exc:
            errors.append(str(exc))
    raise ImageError(
        "no readable image among the clipboard files: " + "; ".join(errors)
    )


def _macos_fallback() -> Image.Image | None:
    """Read the clipboard as TIFF/JPEG for apps that do not offer PNG.

    Returns None when no flavor decodes (caller reports "no image").
    """
    for flavor in _MACOS_FLAVORS:
        data = _osascript_clipboard(flavor)
        if data is None:
            continue
        try:
            im = Image.open(io.BytesIO(data))
            im.load()
        except Exception:
            # flavor present but payload undecodable; try the next one
            continue
        return im
    return None


def _osascript_clipboard(flavor: str) -> bytes | None:
    """Return raw clipboard bytes for an AppleScript flavor, or None."""
    try:
        proc = subprocess.run(
            ["osascript", "-e", f"get the clipboard as {flavor}"],
            capture_output=True,
            check=False,
        )
    except OSError:  # osascript missing entirely
        return None
    if proc.returncode != 0:
        return None
    match = _OSADATA_RE.search(proc.stdout.decode("utf-8", errors="replace"))
    if match is None:
        return None
    # the marker embeds the 4-char OSType (e.g. TIFF/JPEG) before the
    # hex payload; strip it like Pillow's own macOS reader does
    try:
        return binascii.unhexlify(match.group(1)[4:])
    except ValueError:  # binascii.Error is a ValueError subclass
        return None
