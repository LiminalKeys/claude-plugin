"""Pre-baked DeviceRGB image XObject for the default LK watermark (no Pillow)."""

from __future__ import annotations

import struct
from functools import lru_cache
from pathlib import Path

from pyhanko.pdf_utils import content, generic
from pyhanko.pdf_utils.content import AppearanceContent
from pyhanko.pdf_utils.generic import pdf_name
from pyhanko.pdf_utils.writer import BasePdfFileWriter

_DATA_DIR = Path(__file__).resolve().parent / "data"
_RGB_PACKED = _DATA_DIR / "lk-watermark-device-rgb.bin"
WM_XOBJ_PDF_NAME = pdf_name("/LkWm0")
_HEADER = struct.Struct(">II")  # width, height (pixels)


@lru_cache(maxsize=1)
def baked_watermark_pixels() -> tuple[int, int, bytes]:
    if not _RGB_PACKED.is_file():
        raise FileNotFoundError(f"Missing bundled watermark pixels: {_RGB_PACKED}")
    raw = _RGB_PACKED.read_bytes()
    width, height = _HEADER.unpack_from(raw)
    rgb = raw[_HEADER.size :]
    expected = width * height * 3
    if len(rgb) != expected:
        raise ValueError(
            f"Watermark pixel buffer length {len(rgb)} != {width}x{height}x3 ({expected})"
        )
    return width, height, rgb


def draw_baked_watermark_ops(
    stamp: AppearanceContent,
    writer: BasePdfFileWriter,
    *,
    wm_x: float,
    wm_y: float,
    wm_size: float,
) -> bytes:
    """Register pre-baked /Image XObject and return placement operators."""
    width, height, rgb = baked_watermark_pixels()
    stream = generic.StreamObject(
        {
            pdf_name("/Type"): pdf_name("/XObject"),
            pdf_name("/Subtype"): pdf_name("/Image"),
            pdf_name("/Width"): generic.NumberObject(width),
            pdf_name("/Height"): generic.NumberObject(height),
            pdf_name("/ColorSpace"): pdf_name("/DeviceRGB"),
            pdf_name("/BitsPerComponent"): generic.NumberObject(8),
        },
        stream_data=rgb,
    )
    stream.compress()
    ref = writer.add_object(stream)
    stamp.set_resource(
        category=content.ResourceType.XOBJECT,
        name=WM_XOBJ_PDF_NAME,
        value=ref,
    )
    inner = b"%g 0 0 %g 0 0 cm /LkWm0 Do" % (wm_size, wm_size)
    return b"q 1 0 0 1 %g %g cm %s Q" % (wm_x, wm_y, inner)


def appearance_stream_has_baked_watermark(stream: bytes) -> bool:
    """True when the form-paint stream references the default LK watermark XObject."""
    return b"/LkWm0" in stream and b" Do" in stream