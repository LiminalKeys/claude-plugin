"""Branded stamp self-check (blocks pyHanko default appearance)."""

from __future__ import annotations

import pytest
from pyhanko.stamp.art import STAMP_ART_CONTENT

from liminalkeys_sign.stamp_branding_guard import (
    BrandedStampError,
    assert_branded_visible_stamp,
    pdf_bytes_has_liminal_branding,
    pdf_bytes_uses_pyhanko_default_stamp,
)


def test_detects_pyhanko_default_text():
    assert pdf_bytes_uses_pyhanko_default_stamp(b"%PDF-1.7 Digitally signed by Alice")


def test_detects_pyhanko_default_art():
    assert pdf_bytes_uses_pyhanko_default_stamp(b"%PDF" + STAMP_ART_CONTENT.data)


def test_branding_present_in_prepare_fixture(signing_material, input_pdf, work_dir):
    import pickle

    from liminalkeys_sign.prepare import run_prepare
    from liminalkeys_sign.visible_stamp import VisibleStampOptions

    prep = run_prepare(
        input_pdf,
        signing_material["leaf_path"],
        work_dir,
        visible_signature=True,
        stamp_options=VisibleStampOptions(),
    )
    pdf_bytes = pickle.loads(prep.state_path.read_bytes())["pdf"]
    assert pdf_bytes_has_liminal_branding(pdf_bytes)
    assert_branded_visible_stamp(pdf_bytes)


def test_rejects_pyhanko_default_bytes():
    with pytest.raises(BrandedStampError, match="pyHanko default"):
        assert_branded_visible_stamp(b"Digitally signed by %(signer)s")


def test_rejects_missing_watermark():
    with pytest.raises(BrandedStampError, match="missing Liminal Keys"):
        assert_branded_visible_stamp(b"%PDF-1.7 Signed with Liminal Keys only text")