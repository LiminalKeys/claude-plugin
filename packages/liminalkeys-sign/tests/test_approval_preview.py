import base64

from liminalkeys_sign.approval_preview import (
    approval_preview_base64,
    grayscale_png_bytes,
    write_approval_preview_png,
)


def test_grayscale_png_is_valid_png():
    data = grayscale_png_bytes(width=8, height=8)
    assert data.startswith(b"\x89PNG\r\n\x1a\n")


def test_approval_preview_base64_roundtrip():
    b64 = approval_preview_base64(digest_hex="abcd1234")
    raw = base64.standard_b64decode(b64)
    assert raw.startswith(b"\x89PNG")


def test_write_approval_preview_png(tmp_path):
    out = tmp_path / "preview.png"
    write_approval_preview_png(out, digest_hex="deadbeef", document_label="Contract.pdf")
    assert out.stat().st_size < 32_000
    data = out.read_bytes()
    assert data.startswith(b"\x89PNG")
    assert len(set(data)) > 8


def test_write_approval_preview_png_not_uniform_grey(tmp_path):
    out = tmp_path / "preview.png"
    write_approval_preview_png(out, digest_hex="ab" * 32, document_label="Quarterly report")
    raw = out.read_bytes()
    assert raw.count(raw[100:200]) < len(raw) // 2
