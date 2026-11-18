"""Detect pyHanko default stamps vs Liminal Keys branded appearance in PDF bytes."""

from __future__ import annotations

from pathlib import Path

from pyhanko.stamp.art import STAMP_ART_CONTENT

from liminalkeys_sign.stamp_layout import STAMP_FOOTER_LEFT
PYHANKO_DEFAULT_STAMP_TEXT = b"Digitally signed by"
_FOOTER_UTF8 = STAMP_FOOTER_LEFT.encode("utf-8")
_WM_NAME = b"/LkWm0"


class BrandedStampError(RuntimeError):
    """Raised when a visible signature lacks Liminal Keys branding."""


def pdf_bytes_uses_pyhanko_default_stamp(pdf_bytes: bytes) -> bool:
    """True when PDF bytes match pyHanko's default text stamp (forbidden for LK signing)."""
    if PYHANKO_DEFAULT_STAMP_TEXT in pdf_bytes:
        return True
    art = getattr(STAMP_ART_CONTENT, "data", None)
    if art and art in pdf_bytes:
        return True
    return False


def pdf_bytes_has_liminal_branding(pdf_bytes: bytes) -> bool:
    """True when the bundled LK watermark XObject and footer copy are present."""
    if _WM_NAME not in pdf_bytes:
        return False
    if _FOOTER_UTF8 not in pdf_bytes:
        return False
    return True


def assert_branded_visible_stamp(pdf_bytes: bytes, *, context: str = "PDF") -> None:
    """
    Fail loudly if a visible signature would show the pyHanko default stamp
    or is missing Liminal Keys branding.
    """
    if pdf_bytes_uses_pyhanko_default_stamp(pdf_bytes):
        raise BrandedStampError(
            f"{context}: pyHanko default stamp detected "
            f"({PYHANKO_DEFAULT_STAMP_TEXT.decode('ascii', errors='replace')!r}). "
            "Use only `liminal-sign prepare` / `finish` from the bundled skill — "
            "never hand-written pyHanko signing code."
        )
    if not pdf_bytes_has_liminal_branding(pdf_bytes):
        raise BrandedStampError(
            f"{context}: missing Liminal Keys branded stamp "
            f"(expected {_WM_NAME!r} and {STAMP_FOOTER_LEFT!r}). "
            "Re-run `liminal-sign prepare` with the bundled wheel; clear "
            "~/.cache/liminalkeys-sign if the install is stale."
        )


def assert_branded_visible_stamp_file(pdf_path: Path, *, context: str | None = None) -> None:
    label = context or str(pdf_path)
    assert_branded_visible_stamp(pdf_path.read_bytes(), context=label)