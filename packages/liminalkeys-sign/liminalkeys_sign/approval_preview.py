"""Small PNG thumbnails for Console approval previews (stdlib only)."""

from __future__ import annotations

import base64
import struct
import zlib
from pathlib import Path


def _chunk(chunk_type: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)


def grayscale_png_bytes(*, width: int = 160, height: int = 200, shade: int = 210) -> bytes:
    """Return a valid grayscale PNG (uncompressed rows, filter type 0 per scanline)."""
    if width < 1 or height < 1 or width > 2048 or height > 2048:
        raise ValueError("width and height must be between 1 and 2048")
    shade = max(0, min(255, shade))
    row = bytes([0, shade]) * width
    raw = row * height
    compressed = zlib.compress(raw, level=9)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            _chunk(b"IHDR", ihdr),
            _chunk(b"IDAT", compressed),
            _chunk(b"IEND", b""),
        ]
    )


def write_approval_preview_png(
    output: Path,
    *,
    digest_hex: str | None = None,
    document_label: str | None = None,
) -> Path:
    """Write a small placeholder PNG approvers can open (not a cryptographic proof)."""
    # Shade varies slightly with digest prefix so repeated runs are distinguishable in QA.
    shade = 200
    if digest_hex:
        try:
            shade = 180 + (int(digest_hex[:4], 16) % 50)
        except ValueError:
            pass
    elif document_label:
        shade = 180 + (sum(ord(c) for c in document_label[:8]) % 50)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(grayscale_png_bytes(shade=shade))
    return output


def approval_preview_base64(
    *,
    digest_hex: str | None = None,
    document_label: str | None = None,
) -> str:
    return base64.standard_b64encode(
        grayscale_png_bytes(
            shade=190
            + (
                (int(digest_hex[:4], 16) % 40)
                if digest_hex
                else (sum(ord(c) for c in (document_label or "")[:8]) % 40)
            )
        )
    ).decode("ascii")
