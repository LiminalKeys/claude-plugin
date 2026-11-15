"""Visible PAdES signature placement and appearance for prepare."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.pdf_utils.rw_common import find_inherited_value_in_tree
from pyhanko.stamp import TextStampStyle

if TYPE_CHECKING:
    from pyhanko.pdf_utils.content import PdfContent

STAMP_ANCHORS = frozenset({"bottom-right", "bottom-left", "top-right", "top-left"})

DEFAULT_STAMP_WIDTH_PT = 248.0
DEFAULT_STAMP_HEIGHT_PT = 84.0

_LOCALE_TS_FORMATS: dict[str, str] = {
    "en": "%m/%d/%Y %H:%M",
    "en-us": "%m/%d/%Y %H:%M",
    "en-gb": "%d/%m/%Y %H:%M",
    "de": "%d.%m.%Y %H:%M",
    "de-de": "%d.%m.%Y %H:%M",
    "fr": "%d/%m/%Y %H:%M",
    "fr-fr": "%d/%m/%Y %H:%M",
    "es": "%d/%m/%Y %H:%M",
    "es-es": "%d/%m/%Y %H:%M",
    "ja": "%Y/%m/%d %H:%M",
    "ja-jp": "%Y/%m/%d %H:%M",
}


@dataclass(frozen=True)
class VisibleStampOptions:
    page: str = "last"
    anchor: str = "bottom-right"
    margin_pt: float = 36.0
    width_pt: float = DEFAULT_STAMP_WIDTH_PT
    height_pt: float = DEFAULT_STAMP_HEIGHT_PT
    reason: str | None = None
    logo_path: Path | None = None
    locale: str = "en-US"


def normalize_anchor(anchor: str) -> str:
    normalized = anchor.strip().lower().replace("_", "-")
    if normalized not in STAMP_ANCHORS:
        allowed = ", ".join(sorted(STAMP_ANCHORS))
        raise ValueError(f"stamp anchor must be one of {allowed}, got {anchor!r}")
    return normalized


def parse_stamp_page(spec: str, page_count: int) -> int:
    token = spec.strip().lower()
    if token == "first":
        return 0
    if token == "last":
        return -1
    if not re.fullmatch(r"[0-9]+", token):
        raise ValueError(f"stamp page must be first, last, or a positive integer, got {spec!r}")
    page_num = int(token)
    if page_num < 1 or page_num > page_count:
        raise ValueError(f"stamp page {page_num} out of range (document has {page_count} page(s))")
    return page_num - 1


def _media_box_for_page(reader: PdfFileReader, page_index: int) -> tuple[float, float, float, float]:
    if page_index < 0:
        page_index = int(reader.root["/Pages"]["/Count"]) + page_index
    kids = reader.root["/Pages"]["/Kids"]
    if page_index < 0 or page_index >= len(kids):
        raise ValueError(f"page index {page_index} out of range")
    page_obj = kids[page_index].get_object()
    mb = find_inherited_value_in_tree(page_obj, "/MediaBox", "/Parent")
    return tuple(float(x) for x in mb)


def pdf_page_count(reader: PdfFileReader) -> int:
    return int(reader.root["/Pages"]["/Count"])


def compute_visible_box(
    media_box: tuple[float, float, float, float],
    anchor: str,
    margin_pt: float,
    width_pt: float,
    height_pt: float,
) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = media_box
    page_w = x1 - x0
    page_h = y1 - y0
    anchor_norm = normalize_anchor(anchor)
    if anchor_norm == "bottom-right":
        ll_x = x0 + page_w - margin_pt - width_pt
        ll_y = y0 + margin_pt
    elif anchor_norm == "bottom-left":
        ll_x = x0 + margin_pt
        ll_y = y0 + margin_pt
    elif anchor_norm == "top-right":
        ll_x = x0 + page_w - margin_pt - width_pt
        ll_y = y0 + page_h - margin_pt - height_pt
    else:  # top-left
        ll_x = x0 + margin_pt
        ll_y = y0 + page_h - margin_pt - height_pt
    ur_x = ll_x + width_pt
    ur_y = ll_y + height_pt
    return int(ll_x), int(ll_y), int(ur_x), int(ur_y)


def locale_timestamp_format(bcp47: str) -> str:
    tag = bcp47.strip().replace("_", "-").lower()
    if tag in _LOCALE_TS_FORMATS:
        return _LOCALE_TS_FORMATS[tag]
    primary = tag.split("-", 1)[0]
    return _LOCALE_TS_FORMATS.get(primary, "%Y-%m-%d %H:%M")


def _logo_background(logo_path: Path) -> PdfContent:
    from PIL import Image
    from pyhanko.pdf_utils.images import PdfImage

    img = Image.open(logo_path)
    return PdfImage(img, writer=None)


def build_text_stamp_style(options: VisibleStampOptions) -> TextStampStyle:
    ts_format = locale_timestamp_format(options.locale)
    background: PdfContent | None = None
    if options.logo_path is not None:
        background = _logo_background(options.logo_path)

    lines = ["%(signer)s", "%(ts)s"]
    if options.reason:
        lines.append("%(reason)s")
    stamp_text = "\n".join(lines)
    height_note = options.logo_path is not None
    return TextStampStyle(
        stamp_text=stamp_text,
        timestamp_format=ts_format,
        background=background,
        background_opacity=0.35 if height_note else 0.6,
    )


def resolve_field_placement(
    input_pdf: Path,
    options: VisibleStampOptions,
) -> tuple[int, tuple[int, int, int, int]]:
    with input_pdf.open("rb") as inf:
        reader = PdfFileReader(inf)
        count = pdf_page_count(reader)
        on_page = parse_stamp_page(options.page, count)
        media_box = _media_box_for_page(reader, on_page if on_page >= 0 else count - 1)
    box = compute_visible_box(
        media_box,
        options.anchor,
        options.margin_pt,
        options.width_pt,
        options.height_pt,
    )
    return on_page, box


def stamp_appearance_text_params(reason: str | None) -> dict[str, str] | None:
    if not reason:
        return None
    return {"reason": reason}
