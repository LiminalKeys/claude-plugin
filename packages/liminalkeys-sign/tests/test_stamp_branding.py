"""Visible signature appearance (neutral plate + LK watermark)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from pyhanko.pdf_utils import layout
from pyhanko.pdf_utils.writer import PdfFileWriter
from pyhanko.sign.signers.constants import DEFAULT_SIGNING_STAMP_STYLE
from pyhanko.stamp.art import STAMP_ART_CONTENT

from liminalkeys_sign.liminal_stamp import LiminalKeysStampStyle
from liminalkeys_sign.stamp_layout import STAMP_FOOTER_LEFT, format_stamp_datetime
from liminalkeys_sign.stamp_watermark import BRAND_LOGO_SOURCE, MARK_CROP_BOX, watermark_rgb_png_bytes
from liminalkeys_sign.visible_stamp import VisibleStampOptions, build_text_stamp_style, LK_LOGO_ASSET


def test_style_is_liminal_not_pyhanko_default():
    style = build_text_stamp_style(VisibleStampOptions(reason="Contract"))
    assert isinstance(style, LiminalKeysStampStyle)
    assert style is not DEFAULT_SIGNING_STAMP_STYLE
    assert style.background is None


def test_footer_copy():
    assert STAMP_FOOTER_LEFT == "Signed with Liminal Keys"
    assert LK_LOGO_ASSET == BRAND_LOGO_SOURCE


def test_watermark_from_square_logo():
    pytest = __import__("pytest")
    pytest.importorskip("PIL")
    data = watermark_rgb_png_bytes()
    assert len(data) > 500
    assert MARK_CROP_BOX == (28, 28, 212, 212)


def test_default_watermark_xobject_without_pillow(monkeypatch):
    """Default stamp must embed LkWm0 via pre-baked DeviceRGB (no Pillow)."""
    import sys

    for name in list(sys.modules):
        if name == "PIL" or name.startswith("PIL."):
            monkeypatch.delitem(sys.modules, name, raising=False)

    # Block Pillow imports used only for custom logos.
    import builtins

    _real_import = builtins.__import__

    def _block_pil(name, *args, **kwargs):
        if name == "PIL" or (isinstance(name, str) and name.startswith("PIL.")):
            raise ImportError("PIL blocked for test")
        return _real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _block_pil)

    from liminalkeys_sign.watermark_xobject import appearance_stream_has_baked_watermark

    w = PdfFileWriter()
    style = build_text_stamp_style(VisibleStampOptions(reason="QA"))
    stream = style.create_stamp(
        w,
        layout.BoxConstraints(width=248, height=96),
        {
            "signer": "Jane Doe",
            "date_display": "2026-11-13 19:10 UTC",
            "cert_issuer": "Liminal Keys Test CA",
            "cert_serial": "A1B2",
        },
    ).render()
    assert appearance_stream_has_baked_watermark(stream)


def test_prepare_pdf_contains_watermark_image_without_pillow(
    signing_material, input_pdf, work_dir, monkeypatch
):
    import builtins

    _real_import = builtins.__import__

    def _block_pil(name, *args, **kwargs):
        if name == "PIL" or (isinstance(name, str) and name.startswith("PIL.")):
            raise ImportError("PIL blocked for test")
        return _real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _block_pil)

    import pickle

    from liminalkeys_sign.prepare import run_prepare

    prep = run_prepare(
        input_pdf,
        signing_material["leaf_path"],
        work_dir,
        visible_signature=True,
        stamp_options=VisibleStampOptions(),
    )
    state = pickle.loads(prep.state_path.read_bytes())
    pdf_bytes = state["pdf"]
    assert b"/LkWm0" in pdf_bytes
    assert b"/Image" in pdf_bytes
    assert b"/DeviceRGB" in pdf_bytes


def test_branded_appearance_stream_renders():
    w = PdfFileWriter()
    style = build_text_stamp_style(VisibleStampOptions(reason="QA"))
    box = layout.BoxConstraints(width=248, height=96)
    stamp = style.create_stamp(
        w,
        box,
        {
            "signer": "Jane Doe",
            "date_display": "2026-11-13 19:10 UTC",
            "cert_issuer": "Liminal Keys Test CA",
            "cert_serial": "A1B2",
            "reason": "QA",
        },
    )
    stream = stamp.render()
    assert STAMP_ART_CONTENT.data not in stream
    assert len(stream) > 400
    assert b"Signed by" in stream
    assert b"Helvetica" in stream or b"/F1" in stream


def test_format_stamp_datetime_default_utc():
    dt = datetime(2026, 11, 13, 19, 10, tzinfo=ZoneInfo("UTC"))
    assert format_stamp_datetime(dt, "en-US") == "2026-11-13 19:10 UTC"


def test_format_stamp_datetime_cet_madrid():
    dt = datetime(2026, 11, 13, 18, 20, tzinfo=ZoneInfo("UTC"))
    s = format_stamp_datetime(dt, "en-GB", timezone_name="Europe/Madrid")
    assert "Nov" in s
    assert "CET" in s
    assert "(UTC+1)" in s
    assert "UTC (UTC" not in s


def test_format_stamp_datetime_locale_utc_no_redundant_paren():
    dt = datetime(2026, 11, 13, 18, 23, tzinfo=ZoneInfo("UTC"))
    s = format_stamp_datetime(dt, "en-GB", timezone_name="UTC")
    assert s.endswith("UTC")
    assert "(UTC" not in s


def test_pdf_winansi_ellipsis_and_accents():
    from liminalkeys_sign.stamp_layout import ELLIPSIS, pdf_winansi_literal

    lit = pdf_winansi_literal(f"José Núñez{ELLIPSIS}")
    assert r"\205" in lit  # WinAnsi ellipsis (0x85)
    assert r"\351" in lit  # é
    assert "â" not in lit

    assert r"\374" in pdf_winansi_literal(f"Müller{ELLIPSIS}")  # ü


def test_stamp_renders_winansi_signer_and_ellipsis():
    w = PdfFileWriter()
    style = build_text_stamp_style(VisibleStampOptions())
    cn = (
        "Developer ID Application: Example Corp (TEAMID) "
        "Regional Office European Operations Division"
    )
    stream = style.create_stamp(
        w,
        layout.BoxConstraints(width=180, height=60),
        {
            "signer": cn,
            "date_display": "2026-11-13 19:10 UTC",
            "cert_issuer": cn,
            "cert_serial": "AB",
        },
    ).render()
    assert b"\\205" in stream
    assert b"\xe2\x80\xa6" not in stream  # UTF-8 ellipsis (mojibake if WinAnsi missing)


def test_truncate_cert_serial_long_hex():
    from liminalkeys_sign.stamp_layout import ELLIPSIS, truncate_cert_serial

    raw = "5A327F21E483F0AAAF4F767BE932F"
    fitted = truncate_cert_serial(raw, "Helvetica", 6.5, 48.0)
    out = fitted.text
    assert out.endswith(ELLIPSIS)
    assert "5A32" in out
    assert len(out) <= 20


def test_truncate_long_common_name():
    from liminalkeys_sign.stamp_layout import ELLIPSIS, truncate_ellipsis

    cn = "Example Corp (TEAMID)"
    out = truncate_ellipsis(cn, "Helvetica-Bold", 8.0, 72.0)
    assert out.endswith(ELLIPSIS)
    assert "Example" in out


def test_truncate_ellipsis_rstrip_before_ellipsis():
    from liminalkeys_sign.stamp_layout import ELLIPSIS, truncate_ellipsis

    out = truncate_ellipsis("Hello brave world   ", "Helvetica", 6.5, 36.0)
    assert out.endswith(ELLIPSIS)
    assert not out.endswith(" " + ELLIPSIS)
    assert " …" not in out


@pytest.mark.parametrize(
    "raw,expected",
    [
        (
            "Developer ID Application: Example Corp (TEAMID)",
            "Example Corp (TEAMID)",
        ),
        (
            "3rd Party Mac Developer Application: Acme Inc.",
            "Acme Inc.",
        ),
        ("Apple Distribution: Acme Inc.", "Acme Inc."),
        ("Plain Signer", "Plain Signer"),
    ],
)
def test_strip_apple_code_sign_cn_prefix(raw, expected):
    from liminalkeys_sign.stamp_layout import strip_apple_code_sign_cn_prefix

    assert strip_apple_code_sign_cn_prefix(raw) == expected


def test_stamp_signer_uses_stripped_apple_cn():
    w = PdfFileWriter()
    style = build_text_stamp_style(VisibleStampOptions())
    stream = style.create_stamp(
        w,
        layout.BoxConstraints(width=248, height=96),
        {
            "signer": "Developer ID Application: Example Corp (TEAMID)",
            "date_display": "2026-11-13 19:10 UTC",
            "cert_issuer": "CA",
            "cert_serial": "AB",
        },
    ).render()
    decoded = stream.decode("latin-1", errors="replace")
    assert "Example Corp" in decoded
    assert "Developer ID Application" not in decoded


def test_serial_truncation_respects_value_column_width():
    from liminalkeys_sign.stamp_layout import text_width, truncate_cert_serial, value_column_max_width

    w = 248.0
    scale = 96.0 / 60.0
    max_w = value_column_max_width(w, scale)
    raw = "5A327F21E483F0AAAF4F767BE932F"
    fitted = truncate_cert_serial(raw, "Helvetica", 6.5, max_w)
    assert text_width(fitted.text, "Helvetica", fitted.size_pt) <= max_w + 0.5


def test_serial_row_only_when_tall_enough():
    w = PdfFileWriter()
    style = build_text_stamp_style(VisibleStampOptions())
    short = style.create_stamp(
        w,
        layout.BoxConstraints(width=180, height=60),
        {
            "signer": "A",
            "date_display": "2026-11-13 19:10 UTC",
            "cert_issuer": "CA",
            "cert_serial": "SERIAL123",
        },
    ).render()
    tall = style.create_stamp(
        w,
        layout.BoxConstraints(width=248, height=96),
        {
            "signer": "A",
            "date_display": "2026-11-13 19:10 UTC",
            "cert_issuer": "CA",
            "cert_serial": "SERIAL123",
        },
    ).render()
    tall_with_reason = build_text_stamp_style(VisibleStampOptions(reason="Approved")).create_stamp(
        w,
        layout.BoxConstraints(width=248, height=96),
        {
            "signer": "A",
            "date_display": "2026-11-13 19:10 UTC",
            "cert_issuer": "CA",
            "cert_serial": "SERIAL123",
        },
    ).render()
    assert b"Serial" not in short
    assert b"Serial" in tall
    assert b"Serial" in tall_with_reason


def test_long_signer_name_fits_value_column():
    from liminalkeys_sign.stamp_layout import (
        ELLIPSIS,
        fit_value_in_column,
        scaled_layout,
        text_width,
        value_column_max_width,
    )

    name = "PERONA REQUENA ALMUDENA"
    w, h = 248.0, 96.0
    max_w = value_column_max_width(w, h / 60.0)
    ly = scaled_layout(h)
    nominal = ly["signer_value_size"]
    fitted = fit_value_in_column(name, "Helvetica-Bold", nominal, max_w)
    assert text_width(fitted.text, "Helvetica-Bold", fitted.size_pt) <= max_w + 0.05
    nominal_w = text_width(name, "Helvetica-Bold", nominal)
    if nominal_w > max_w:
        assert fitted.size_pt < nominal or fitted.text.endswith(ELLIPSIS)


def test_fit_value_accented_name_shrink_or_ellipsis():
    from liminalkeys_sign.stamp_layout import ELLIPSIS, fit_value_in_column, text_width

    name = "GARCÍA PÉREZ MARÍA DOLORES DE LA CRUZ"
    fitted = fit_value_in_column(name, "Helvetica-Bold", 10.4, 90.0)
    assert text_width(fitted.text, "Helvetica-Bold", fitted.size_pt) <= 90.05
    assert fitted.text  # cp1252 path
    if text_width(name, "Helvetica-Bold", 10.4) > 90.0:
        assert fitted.size_pt < 10.4 or fitted.text.endswith(ELLIPSIS)


def test_stamp_long_signer_stream_contains_no_clipped_tail():
    from liminalkeys_sign.stamp_layout import fit_value_in_column, scaled_layout, value_column_max_width

    w = PdfFileWriter()
    style = build_text_stamp_style(VisibleStampOptions(reason="Contrato de trabajo importante"))
    name = "PERONA REQUENA ALMUDENA"
    box = layout.BoxConstraints(width=248, height=96)
    stream = style.create_stamp(
        w,
        box,
        {
            "signer": name,
            "date_display": "2026-11-22 18:30 UTC",
            "cert_issuer": "ACME LONG ISSUER AUTHORITY ROOT CERTIFICATION UNIT",
            "cert_serial": "5A327F21E483F0AAAF4F767BE932F",
            "reason": "Contrato de trabajo importante",
        },
    ).render()
    assert b"PERONA" in stream
    max_w = value_column_max_width(248.0, 96.0 / 60.0)
    nominal = scaled_layout(96.0)["signer_value_size"]
    fitted = fit_value_in_column(name, "Helvetica-Bold", nominal, max_w)
    assert fitted.size_pt <= nominal + 0.01
    assert fitted.size_pt >= nominal * 0.7 - 0.01
