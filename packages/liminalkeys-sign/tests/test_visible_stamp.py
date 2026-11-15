"""Visible signature placement and prepare integration."""

from __future__ import annotations

from liminalkeys_sign.prepare import run_prepare
from liminalkeys_sign.validate import run_validate
from liminalkeys_sign.stamp_layout import STAMP_FOOTER_LEFT, format_stamp_datetime
from liminalkeys_sign.visible_stamp import (
    VisibleStampOptions,
    build_text_stamp_style,
    compute_visible_box,
    parse_stamp_page,
    resolve_field_placement,
)
from test_sign_flow import _mock_sign_hash


def test_parse_stamp_page_tokens():
    assert parse_stamp_page("first", 3) == 0
    assert parse_stamp_page("last", 3) == -1
    assert parse_stamp_page("2", 3) == 1


def test_compute_visible_box_bottom_right():
    mbox = (0.0, 0.0, 612.0, 792.0)
    box = compute_visible_box(mbox, "bottom-right", 36.0, 248.0, 96.0)
    assert box == (328, 36, 576, 132)


def test_compute_visible_box_top_left():
    mbox = (0.0, 0.0, 612.0, 792.0)
    box = compute_visible_box(mbox, "top-left", 36.0, 200.0, 60.0)
    assert box == (36, 696, 236, 756)


def test_format_stamp_datetime_en_gb_shape():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    dt = datetime(2026, 11, 13, 19, 10, tzinfo=ZoneInfo("UTC"))
    s = format_stamp_datetime(dt, "en-GB")
    assert "Nov" in s
    assert "2026" in s
    assert ":" in s
    assert "UTC" in s


def test_build_text_stamp_style_footer():
    style = build_text_stamp_style(VisibleStampOptions(reason="QA release"))
    assert style.reason == "QA release"
    assert style.background is None


def test_prepare_visible_with_logo(signing_material, input_pdf, work_dir, tmp_path):
    __import__("pytest").importorskip("PIL")
    from PIL import Image

    logo = tmp_path / "logo.png"
    Image.new("RGB", (40, 40), color=(0, 120, 200)).save(logo)
    opts = VisibleStampOptions(page="last", logo_path=logo, locale="en-GB")
    prep = run_prepare(
        input_pdf,
        signing_material["leaf_path"],
        work_dir,
        visible_signature=True,
        stamp_options=opts,
    )
    assert len(prep.digest_hex) == 64


def test_resolve_field_placement_last_page(input_pdf):
    _page, box = resolve_field_placement(
        input_pdf,
        VisibleStampOptions(page="last", anchor="bottom-right", margin_pt=36.0),
    )
    assert box[0] >= 300


def test_prepare_visible_signature_embed_validate(signing_material, input_pdf, work_dir):
    opts = VisibleStampOptions(
        page="first",
        anchor="bottom-left",
        margin_pt=48.0,
        reason="Vendor approval",
    )
    prep = run_prepare(
        input_pdf,
        signing_material["leaf_path"],
        work_dir,
        visible_signature=True,
        stamp_options=opts,
    )
    sig = _mock_sign_hash(signing_material["key"], prep.digest_path)
    sig_path = work_dir / "signature.bin"
    sig_path.write_bytes(sig)
    from liminalkeys_sign.embed import run_embed

    out = work_dir / "signed-visible.pdf"
    run_embed(
        work_dir,
        signing_material["leaf_path"],
        sig_path,
        out,
        signed_attrs_path=prep.signed_attrs_path,
        digest_path=prep.digest_path,
    )
    outcome = run_validate(out, [signing_material["leaf_path"]])
    assert outcome.ok
    blob = out.read_bytes()
    assert STAMP_FOOTER_LEFT.encode("latin-1", "ignore") in blob or b"Signed with" in blob
