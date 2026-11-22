"""Helvetica / Helvetica-Bold widths (WinAnsi / CP1252) for stamp layout."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Final

FONT_HELVETICA: Final = "Helvetica"
FONT_HELVETICA_BOLD: Final = "Helvetica-Bold"
_DEFAULT_WIDTH: Final = 600  # per 1000 design units

_DATA_PACKAGE = "liminalkeys_sign.data"
_WIDTHS_FILE = "helvetica_winansi_widths.json"


@lru_cache(maxsize=1)
def _width_tables() -> dict[str, dict[int, int]]:
    raw = resources.files(_DATA_PACKAGE).joinpath(_WIDTHS_FILE).read_text(encoding="utf-8")
    parsed: dict[str, dict[str, int]] = json.loads(raw)
    return {
        font: {int(codept): width for codept, width in table.items()}
        for font, table in parsed.items()
    }


def _encoded_bytes(text: str) -> bytes:
    return text.encode("cp1252", errors="replace")


def measure_text_width(text: str, font: str, size_pt: float) -> float:
    """Sum Adobe AFM glyph widths (1000 UPEM) for bytes on the PDF string path."""
    if not text:
        return 0.0
    table = _width_tables().get(font)
    if table is None:
        raise ValueError(f"unknown stamp font metrics: {font!r}")
    units = sum(table.get(byte, _DEFAULT_WIDTH) for byte in _encoded_bytes(text))
    return units * float(size_pt) / 1000.0