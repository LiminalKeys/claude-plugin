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

_DATA_DIR = Path(__file__).resolve().parent / "data"
BAKED_WATERMARK_RGB = _DATA_DIR / "lk-watermark-baked-rgb.png"
CROPPED_MARK = _DATA_DIR / "lk-square-mark-cropped.png"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _bundled_cropped_logo() -> Path:
    return CROPPED_MARK


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


def _baked_watermark_bytes() -> bytes:
    if BAKED_WATERMARK_RGB.is_file():
        return BAKED_WATERMARK_RGB.read_bytes()
    if CROPPED_MARK.is_file():
        return CROPPED_MARK.read_bytes()
    raise FileNotFoundError("Bundled LK watermark PNG missing from package data")


def _watermark_via_pillow(custom_path: str | None) -> bytes:
    assert Image is not None
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


@lru_cache(maxsize=4)
def watermark_rgb_png_bytes(custom_path: str | None = None) -> bytes:
    """RGB PNG bytes for the stamp watermark (Pillow optional for default LK mark)."""
    if custom_path:
        path = Path(custom_path)
        if not path.is_file():
            raise FileNotFoundError(custom_path)
        suffix = path.suffix.lower()
        if Image is not None and suffix in {".png", ".jpg", ".jpeg", ".webp"}:
            return _watermark_via_pillow(custom_path)
        return path.read_bytes()
    if Image is not None:
        try:
            return _watermark_via_pillow(None)
        except FileNotFoundError:
            pass
    return _baked_watermark_bytes()