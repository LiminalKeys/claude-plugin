"""Custom Liminal Keys visible signature stamp (neutral plate, structured fields)."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

from pyhanko.pdf_utils import content, generic, layout
from pyhanko.pdf_utils.content import AppearanceContent
from pyhanko.pdf_utils.generic import pdf_name
from pyhanko.pdf_utils.writer import BasePdfFileWriter
from pyhanko.stamp.base import BaseStampStyle

from liminalkeys_sign.stamp_layout import (
    BASE_HEIGHT_PT,
    COLOR_BORDER,
    COLOR_FOOTER,
    COLOR_LABEL,
    COLOR_VALUE,
    SERIAL_MIN_HEIGHT_PT,
    STAMP_FOOTER_LEFT,
    fit_value_in_column,
    footer_reserved_height,
    fit_field_typography,
    pdf_escape,
    scaled_layout,
    text_width,
    strip_apple_code_sign_cn_prefix,
    truncate_cert_serial,
    value_column_max_width,
)
from liminalkeys_sign.stamp_watermark import watermark_rgb_png_bytes
from liminalkeys_sign.watermark_xobject import draw_baked_watermark_ops


def _register_helvetica(stamp: AppearanceContent) -> None:
    stamp.set_resource(
        category=content.ResourceType.FONT,
        name=pdf_name("/F1"),
        value=generic.DictionaryObject(
            {
                pdf_name("/Type"): pdf_name("/Font"),
                pdf_name("/Subtype"): pdf_name("/Type1"),
                pdf_name("/BaseFont"): pdf_name("/Helvetica"),
                pdf_name("/Encoding"): pdf_name("/WinAnsiEncoding"),
            }
        ),
    )
    stamp.set_resource(
        category=content.ResourceType.FONT,
        name=pdf_name("/F2"),
        value=generic.DictionaryObject(
            {
                pdf_name("/Type"): pdf_name("/Font"),
                pdf_name("/Subtype"): pdf_name("/Type1"),
                pdf_name("/BaseFont"): pdf_name("/Helvetica-Bold"),
                pdf_name("/Encoding"): pdf_name("/WinAnsiEncoding"),
            }
        ),
    )


def _text_line(
    x: float,
    y: float,
    font: str,
    size: float,
    rgb: tuple[float, float, float],
    text: str,
) -> bytes:
    r, g, b = rgb
    return (
        f"BT {r:.4f} {g:.4f} {b:.4f} rg {font} {size:.2f} Tf "
        f"1 0 0 1 {x:.3f} {y:.3f} Tm ({pdf_escape(text)}) Tj ET"
    ).encode()


@dataclass(frozen=True)
class LiminalKeysStampStyle(BaseStampStyle):
    locale: str = "en-US"
    timezone: str | None = None
    reason: str | None = None
    logo_path: Path | None = None
    border_width: int = 0
    background: None = None
    background_opacity: float = 1.0

    def create_stamp(
        self,
        writer: BasePdfFileWriter,
        box: layout.BoxConstraints,
        text_params: dict[str, Any],
    ) -> "LiminalKeysStamp":
        return LiminalKeysStamp(
            writer=writer,
            style=self,
            box=box,
            text_params=dict(text_params),
        )


class LiminalKeysStamp(AppearanceContent):
    def __init__(
        self,
        writer: BasePdfFileWriter,
        style: LiminalKeysStampStyle,
        text_params: dict[str, Any],
        box: layout.BoxConstraints | None = None,
    ):
        super().__init__(box=box, writer=writer)
        self.style = style
        self.text_params = text_params

    def _embed_custom_logo_watermark(
        self,
        wm_data: bytes,
        wm_x: float,
        wm_y: float,
        wm_size: float,
    ) -> bytes:
        from pyhanko.pdf_utils.images import PdfImage

        try:
            from PIL import Image
        except ImportError as exc:
            raise ImportError(
                "--stamp-logo requires Pillow (image-support); default LK watermark does not"
            ) from exc
        wm_img = Image.open(BytesIO(wm_data))
        pdf_img = PdfImage(
            wm_img,
            writer=self.writer,
            box=layout.BoxConstraints(width=wm_size, height=wm_size),
        )
        wm_draw = pdf_img.render()
        self.import_resources(pdf_img.resources)
        if wm_draw.startswith(b"q ") and wm_draw.endswith(b" Q"):
            wm_draw = wm_draw[2:-2].strip()
        return b"q 1 0 0 1 %g %g cm %s Q" % (wm_x, wm_y, wm_draw)

    def render(self) -> bytes:
        w = float(self.box.width)
        h = float(self.box.height)
        base_ly = scaled_layout(h)
        pad = base_ly["pad"]
        border_w = base_ly["border"]
        scale = base_ly["s"]

        _register_helvetica(self)

        value_max_w = value_column_max_width(w, scale)

        reason = self.text_params.get("reason") or self.style.reason
        serial = str(self.text_params.get("cert_serial") or "")
        include_serial = bool(h >= SERIAL_MIN_HEIGHT_PT and serial)

        skeleton: list[tuple[str, str, bool]] = [
            ("Signed by", "/F2", True),
            ("Date", "/F1", False),
        ]
        if reason:
            skeleton.append(("Reason", "/F1", False))
        skeleton.append(("Issuer", "/F1", False))
        if include_serial:
            skeleton.append(("Serial", "/F1", False))

        nominal_sizes = [
            base_ly["signer_value_size"] if is_signer else base_ly["body_value_size"]
            for _, _, is_signer in skeleton
        ]
        ly = fit_field_typography(h, nominal_sizes)
        label_size = ly["label_size"]
        body_value_size = ly["body_value_size"]
        signer_value_size = ly["signer_value_size"]
        row_lead = ly["row_lead"]
        signer_extra = ly["signer_extra"]

        signer_raw = strip_apple_code_sign_cn_prefix(
            str(self.text_params.get("signer") or "Unknown")
        )
        signer_fit = fit_value_in_column(
            signer_raw,
            "Helvetica-Bold",
            signer_value_size,
            value_max_w,
        )
        date_fit = fit_value_in_column(
            str(self.text_params.get("date_display") or self.text_params.get("ts") or ""),
            "Helvetica",
            body_value_size,
            value_max_w,
        )
        issuer_fit = fit_value_in_column(
            str(self.text_params.get("cert_issuer") or "n/a"),
            "Helvetica",
            body_value_size,
            value_max_w,
        )

        fitted_fields: dict[str, tuple[str, float]] = {
            "Signed by": (signer_fit.text, signer_fit.size_pt),
            "Date": (date_fit.text, date_fit.size_pt),
            "Issuer": (issuer_fit.text, issuer_fit.size_pt),
        }
        if reason:
            reason_fit = fit_value_in_column(
                str(reason), "Helvetica", body_value_size, value_max_w
            )
            fitted_fields["Reason"] = (reason_fit.text, reason_fit.size_pt)
        if include_serial:
            serial_fit = truncate_cert_serial(
                serial, "Helvetica", body_value_size, value_max_w
            )
            fitted_fields["Serial"] = (serial_fit.text, serial_fit.size_pt)

        rows: list[tuple[str, str, str, float]] = []
        for label, font_res, _is_signer in skeleton:
            val_text, val_size = fitted_fields[label]
            rows.append((label, val_text, font_res, val_size))

        footer_size = ly["footer_size"]
        body_floor = footer_reserved_height(footer_size, pad, scale)
        fields_top = h - pad
        fields_height = max(8.0, fields_top - body_floor)

        ops: list[bytes] = [b"q"]
        ops.append(b"1 1 1 rg 0 0 %g %g re f" % (w, h))

        custom = str(self.style.logo_path) if self.style.logo_path else None
        wm_margin = 2.0 * scale
        avail_h = max(1.0, fields_height - 2 * wm_margin)
        avail_w = max(1.0, w - 2 * pad)
        wm_size = min(avail_h, avail_w)
        wm_x = (w - wm_size) / 2.0
        wm_y = body_floor + wm_margin + (avail_h - wm_size) / 2.0
        if custom:
            wm_data = watermark_rgb_png_bytes(custom)
            ops.append(self._embed_custom_logo_watermark(wm_data, wm_x, wm_y, wm_size))
        else:
            assert self.writer is not None
            ops.append(
                draw_baked_watermark_ops(
                    self, self.writer, wm_x=wm_x, wm_y=wm_y, wm_size=wm_size
                )
            )

        br, bg, bb = COLOR_BORDER
        ops.append(b"%g %g %g RG %g w 0 0 %g %g re S" % (br, bg, bb, border_w, w, h))

        def _draw_row(
            label: str,
            value: str,
            font_res: str,
            val_size: float,
            label_y: float,
        ) -> None:
            ops.append(_text_line(ly["x_label"], label_y, "/F1", label_size, COLOR_LABEL, label))
            val_y = label_y - max(0.0, (val_size - label_size) * 0.85)
            ops.append(_text_line(ly["x_value"], val_y, font_res, val_size, COLOR_VALUE, value))

        y = fields_top - label_size
        for idx, (label, value, font_res, val_size) in enumerate(rows):
            _draw_row(label, value, font_res, val_size, y)
            y -= row_lead + (signer_extra if idx == 0 else 0.0)

        footer_w = text_width(STAMP_FOOTER_LEFT, "Helvetica", footer_size)
        footer_x = w - pad - footer_w
        footer_y = pad
        if abs(h - BASE_HEIGHT_PT) < 0.5:
            footer_y = max(border_w + 1.0, pad - ly["footer_drop_180"])
        ops.append(
            _text_line(footer_x, footer_y, "/F1", footer_size, COLOR_FOOTER, STAMP_FOOTER_LEFT)
        )

        ops.append(b"Q")
        return b"\n".join(ops)


def patch_sig_appearance_setup() -> None:
    from pyhanko.sign.signers import cms_embedder

    if getattr(cms_embedder.SigAppearanceSetup, "_lk_patched", False):
        return

    _orig = cms_embedder.SigAppearanceSetup._appearance_stamp

    def _appearance_stamp(self, writer, box):
        style = self.style
        from liminalkeys_sign.stamp_layout import format_stamp_datetime

        text_params: dict[str, Any] = {}
        if self.name is not None:
            text_params["signer"] = self.name
        text_params.update(self.text_params or {})

        if isinstance(style, LiminalKeysStampStyle):
            text_params["date_display"] = format_stamp_datetime(
                self.timestamp,
                style.locale,
                timezone_name=style.timezone,
            )
            return style.create_stamp(writer, box, text_params)
        return _orig(self, writer, box)

    cms_embedder.SigAppearanceSetup._appearance_stamp = _appearance_stamp
    cms_embedder.SigAppearanceSetup._lk_patched = True  # type: ignore[attr-defined]
