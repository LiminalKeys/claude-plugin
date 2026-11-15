"""Centered watermark from branding/ciam/square-logo.png (cropped mark)."""

from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None  # type: ignore

# Authoritative brand asset (no SVG in repo for this mark).
BRAND_LOGO_SOURCE = "branding/ciam/square-logo.png"
MARK_CROP_BOX = (28, 28, 212, 212)  # left, top, right, bottom
WATERMARK_VISIBLE_FRAC = 0.16  # ~16% on white — LK legible, still a watermark


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _bundled_cropped_logo() -> Path:
    return Path(__file__).resolve().parent / "data" / "lk-square-mark-cropped.png"


def resolve_logo_source() -> Path:
    src = _repo_root() / "branding" / "ciam" / "square-logo.png"
    if src.is_file():
        return src
    bundled = _bundled_cropped_logo()
    if bundled.is_file():
        return bundled
    raise FileNotFoundError(
        f"LK square logo not found at {BRAND_LOGO_SOURCE} or package data"
    )


def crop_mark(img: Image.Image) -> Image.Image:
    return img.crop(MARK_CROP_BOX)


def soften_on_white(img: Image.Image, visible: float = WATERMARK_VISIBLE_FRAC) -> Image.Image:
    """Pre-blend mark onto white so viewers without alpha stacks see ~visible strength."""
    mark = img.convert("RGBA")
    base = Image.new("RGBA", mark.size, (255, 255, 255, 255))
    faded = mark.copy()
    alpha = faded.getchannel("A")
    faded.putalpha(alpha.point(lambda a: int(a * visible)))
    blended = Image.alpha_composite(base, faded)
    return blended.convert("RGB")


@lru_cache(maxsize=4)
def watermark_rgb_png_bytes(custom_path: str | None = None) -> bytes:
    if Image is None:  # pragma: no cover
        raise ImportError("Pillow required for stamp watermark")
    if custom_path:
        img = Image.open(custom_path).convert("RGBA")
    else:
        src = resolve_logo_source()
        img = Image.open(src).convert("RGBA")
        if src.name == "square-logo.png" or img.size[0] > 200:
            img = crop_mark(img)
    out = soften_on_white(img)
    buf = BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()
