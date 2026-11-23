import base64

from liminalkeys_sign.pdf_preview import MAX_SIGN_HASH_PREVIEW_BYTES, build_sign_hash_previews


def test_preview_decoded_size_within_mcp_budget(signing_material, input_pdf) -> None:
    previews = build_sign_hash_previews(
        pdf=input_pdf,
        digest_hex="ab" * 32,
        document_label="Contract",
    )
    raw = base64.standard_b64decode(previews[0]["content_base64"])
    assert len(raw) <= MAX_SIGN_HASH_PREVIEW_BYTES


def test_placeholder_preview_is_small() -> None:
    previews = build_sign_hash_previews(pdf=None, digest_hex="cd" * 32)
    raw = base64.standard_b64decode(previews[0]["content_base64"])
    assert len(raw) <= MAX_SIGN_HASH_PREVIEW_BYTES