"""Render a small first-page preview for sign_hash approval flows."""

from __future__ import annotations

import base64
import shutil
import subprocess
import tempfile
from pathlib import Path

from liminalkeys_sign.approval_preview import approval_preview_base64, grayscale_png_bytes

# Agent tool payloads truncate above ~8–32 KiB; keep decoded previews ≤ 4 KiB for sign_hash.
MAX_SIGN_HASH_PREVIEW_BYTES = 4096
DEFAULT_MAX_EDGE = 240
DEFAULT_WEBP_QUALITY = 45
FALLBACK_MAX_EDGE = 120
FALLBACK_WEBP_QUALITY = 35


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


def _shrink_image(
    png_bytes: bytes,
    *,
    max_edge: int = DEFAULT_MAX_EDGE,
    webp_quality: int = DEFAULT_WEBP_QUALITY,
) -> tuple[bytes, str]:
    try:
        from PIL import Image  # pillow bundled in skill wheels
    except ImportError:
        return png_bytes, "image/png"
    import io

    with Image.open(io.BytesIO(png_bytes)) as img:
        img = img.convert("RGB")
        img.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="WEBP", quality=webp_quality, method=6)
        return buf.getvalue(), "image/webp"


def _fit_preview_under_limit(body: bytes, content_type: str, *, raw_png: bytes | None) -> tuple[bytes, str]:
    if len(body) <= MAX_SIGN_HASH_PREVIEW_BYTES:
        return body, content_type
    if raw_png is not None:
        body, content_type = _shrink_image(
            raw_png, max_edge=FALLBACK_MAX_EDGE, webp_quality=FALLBACK_WEBP_QUALITY
        )
        if len(body) <= MAX_SIGN_HASH_PREVIEW_BYTES:
            return body, content_type
    if raw_png is not None:
        body, content_type = _shrink_image(raw_png, max_edge=96, webp_quality=30)
    return body, content_type


def build_sign_hash_previews(
    *,
    pdf: Path | None,
    digest_hex: str,
    document_label: str | None = None,
) -> list[dict[str, str]]:
    """Return one preview item sized for MCP tool calls (decoded ≤ 4 KiB)."""
    if pdf is not None and pdf.is_file():
        raw_png = _pdftoppm_png(pdf, dpi=48)
        if raw_png:
            body, content_type = _shrink_image(raw_png)
            body, content_type = _fit_preview_under_limit(body, content_type, raw_png=raw_png)
            return [_encode_preview_bytes(body, content_type=content_type)]
    placeholder = grayscale_png_bytes(width=120, height=150)
    return [_encode_preview_bytes(placeholder, content_type="image/png")]


def preview_base64_for_prepare(
    *,
    pdf: Path | None,
    digest_hex: str,
    document_label: str | None = None,
) -> str:
    items = build_sign_hash_previews(pdf=pdf, digest_hex=digest_hex, document_label=document_label)
    return items[0]["content_base64"]