"""Crop helpers for visible signature field PNGs."""

from __future__ import annotations

from pathlib import Path


def signature_widget_rect_fitz(page, field_name: str | None = None):
    """Return widget rect in PyMuPDF coordinates (origin top-left, y down)."""
    import fitz

    for widget in page.widgets() or []:
        if widget.field_type != fitz.PDF_WIDGET_TYPE_SIGNATURE:
            continue
        if field_name is None or widget.field_name == field_name:
            return widget.rect
    raise ValueError("No matching signature widget on page")


def pdf_box_to_fitz_rect(
    box: tuple[int, int, int, int],
    page_height_pt: float,
):
    """Convert PDF box (llx, lly, urx, ury) with bottom-left origin to fitz Rect."""
    import fitz

    x0, y0, x1, y1 = box
    return fitz.Rect(x0, page_height_pt - y1, x1, page_height_pt - y0)


def render_stamp_crop_png(
    pdf_path: Path,
    out_png: Path,
    *,
    field_name: str | None = "LiminalAgentSig",
    page_index: int = 0,
    zoom: float = 4.0,
    fallback_box: tuple[int, int, int, int] | None = None,
) -> None:
    import fitz

    doc = fitz.open(pdf_path)
    try:
        page = doc[page_index]
        try:
            rect = signature_widget_rect_fitz(page, field_name=field_name)
        except ValueError:
            if fallback_box is None:
                raise
            rect = pdf_box_to_fitz_rect(fallback_box, page.rect.height)
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=rect, alpha=False)
        pix.save(str(out_png))
    finally:
        doc.close()
