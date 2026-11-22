"""Render a small first-page preview for sign_hash approval flows."""

from __future__ import annotations

import base64
import shutil
import subprocess
import tempfile
from pathlib import Path

from liminalkeys_sign.approval_preview import approval_preview_base64, grayscale_png_bytes

# Default: one page, low DPI, compressed WebP when Pillow is available.
DEFAULT_MAX_EDGE = 480
DEFAULT_WEBP_QUALITY = 55


def _encode_preview_bytes(data: bytes, *, content_type: str) -> dict[str, str]:
    return {
        "content_type": content_type,
        "content_base64": base64.standard_b64encode(data).decode("ascii"),
    }


def _pdftoppm_png(pdf: Path, *, dpi: int = 72) -> bytes | None:
    if not shutil.which("pdftoppm"):
        return None
    with tempfile.TemporaryDirectory(prefix="lk-preview-") as tmp:
        prefix = Path(tmp) / "page"
        proc = subprocess.run(
            [
                "pdftoppm",
                "-png",
                "-singlefile",
                "-r",
                str(dpi),
                "-f",
                "1",
                "-l",
                "1",
                str(pdf),
                str(prefix),
            ],
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            return None
        png_path = prefix.with_suffix(".png")
        if not png_path.is_file():
            return None
        return png_path.read_bytes()


def _shrink_image(png_bytes: bytes) -> tuple[bytes, str]:
    try:
        from PIL import Image  # optional; bundled WebP shrink when Pillow is present
    except ImportError:
        return png_bytes, "image/png"
    import io

    with Image.open(io.BytesIO(png_bytes)) as img:
        img = img.convert("RGB")
        img.thumbnail((DEFAULT_MAX_EDGE, DEFAULT_MAX_EDGE), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="WEBP", quality=DEFAULT_WEBP_QUALITY, method=6)
        return buf.getvalue(), "image/webp"


def build_sign_hash_previews(
    *,
    pdf: Path | None,
    digest_hex: str,
    document_label: str | None = None,
) -> list[dict[str, str]]:
    """Return one small preview item for sign_hash `previews` (≤ ~32 KiB target)."""
    if pdf is not None and pdf.is_file():
        raw_png = _pdftoppm_png(pdf)
        if raw_png:
            body, content_type = _shrink_image(raw_png)
            if len(body) <= 1_048_576:
                return [_encode_preview_bytes(body, content_type=content_type)]
    placeholder = grayscale_png_bytes(width=160, height=200)
    return [_encode_preview_bytes(placeholder, content_type="image/png")]


def preview_base64_for_prepare(
    *,
    pdf: Path | None,
    digest_hex: str,
    document_label: str | None = None,
) -> str:
    items = build_sign_hash_previews(pdf=pdf, digest_hex=digest_hex, document_label=document_label)
    return items[0]["content_base64"]