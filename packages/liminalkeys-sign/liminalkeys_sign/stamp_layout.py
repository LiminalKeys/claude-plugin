"""Layout constants and helpers for visible stamp appearance (scale by height/60)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from liminalkeys_sign.stamp_font_metrics import measure_text_width

try:
    import tzlocal
except ImportError:  # pragma: no cover
    tzlocal = None  # type: ignore

STAMP_FOOTER_LEFT = "Signed with Liminal Keys"

BASE_HEIGHT_PT = 60.0

COLOR_BORDER = (208 / 255, 213 / 255, 221 / 255)  # #D0D5DD
COLOR_LABEL = (102 / 255, 112 / 255, 133 / 255)  # #667085
COLOR_VALUE = (16 / 255, 24 / 255, 40 / 255)  # #101828
COLOR_FOOTER = COLOR_LABEL

PAD_PT = 8.0
X_LABEL = 8.0
X_VALUE = 42.0
SERIAL_MIN_HEIGHT_PT = 80.0
DEFAULT_LOCALE_TAG = "en-us"
ELLIPSIS = "\u2026"

# Apple code-signing certificate CN prefixes (longest first for matching).
APPLE_CODE_SIGN_CN_PREFIXES: tuple[str, ...] = (
    "3rd Party Mac Developer Application: ",
    "3rd Party Mac Developer Installer: ",
    "Developer ID Application: ",
    "Developer ID Installer: ",
    "Apple Distribution: ",
    "Apple Development: ",
    "iPhone Distribution: ",
    "iPhone Developer: ",
    "Mac Developer: ",
)

MIN_FONT_SCALE = 0.7
FONT_FIT_STEP_PT = 0.25


def _clamp_pt(base: float, s: float, floor: float = 5.0) -> float:
    return max(floor, base * s)


MIN_FIELD_PT = 5.0
SIGNER_ROW_EXTRA_PT = 1.5


def scaled_layout(height_pt: float) -> dict[str, float]:
    s = float(height_pt) / BASE_HEIGHT_PT
    return {
        "s": s,
        "pad": PAD_PT * s,
        "border": max(0.25, 0.5 * s),
        "x_label": X_LABEL * s,
        "x_value": X_VALUE * s,
        "label_size": _clamp_pt(5.5, s),
        "body_value_size": _clamp_pt(6.5, s),
        "signer_value_size": _clamp_pt(8.0, s),
        "footer_size": _clamp_pt(5.0, s),
        "row_lead": _clamp_pt(7.5, s),
        "footer_drop_180": 2.0 * min(s, 1.0),
    }


def value_column_max_width(box_width: float, scale: float) -> float:
    """Single-line value width: from value column to inner edge (box width − 8pt padding)."""
    pad = PAD_PT * scale
    x_val = X_VALUE * scale
    return max(16.0, float(box_width) - pad - x_val)


def resolve_display_tz(timezone_name: str | None) -> ZoneInfo:
    if timezone_name:
        return ZoneInfo(timezone_name)
    if tzlocal is not None:
        try:
            return ZoneInfo(str(tzlocal.get_localzone()))
        except Exception:
            pass
    return ZoneInfo("UTC")


def _utc_offset_label(dt: datetime) -> str:
    offset = dt.utcoffset()
    if offset is None:
        return "UTC"
    total_min = int(offset.total_seconds() // 60)
    sign = "+" if total_min >= 0 else "-"
    total_min = abs(total_min)
    hours, mins = divmod(total_min, 60)
    if mins:
        return f"UTC{sign}{hours}:{mins:02d}"
    return f"UTC{sign}{hours}"


def _tz_abbrev(dt: datetime) -> str:
    try:
        return dt.tzname() or "UTC"
    except Exception:
        return "UTC"


def format_stamp_datetime(
    dt: datetime,
    bcp47: str,
    *,
    timezone_name: str | None = None,
) -> str:
    tag = bcp47.strip().replace("_", "-").lower()
    aware = dt if dt.tzinfo is not None else dt.replace(tzinfo=ZoneInfo("UTC"))
    aware = aware.replace(second=0, microsecond=0)

    if tag == DEFAULT_LOCALE_TAG:
        utc = aware.astimezone(ZoneInfo("UTC"))
        return f"{utc:%Y-%m-%d %H:%M} UTC"

    tz = resolve_display_tz(timezone_name)
    local = aware.astimezone(tz)
    month = local.strftime("%b")
    primary = tag.split("-", 1)[0]
    if primary == "de" or tag.startswith("de"):
        date_part = local.strftime("%d. %b %Y")
    else:
        date_part = f"{local.day} {month} {local.year}"
    tz_name = _tz_abbrev(local)
    off = _utc_offset_label(local)
    time_part = f"{local:%H:%M}"
    if tz_name == "UTC" or off in {"UTC", "UTC+0", "UTC+00"}:
        return f"{date_part}, {time_part} UTC"
  # Named zone (e.g. CET) — include numeric offset when not plain UTC.
    return f"{date_part}, {time_part} {tz_name} ({off})"


def pdf_winansi_literal(text: str) -> str:
    """Encode text for PDF literal strings with /WinAnsiEncoding (CP1252 bytes)."""
    data = text.encode("cp1252", errors="replace")
    parts: list[str] = []
    for b in data:
        if b == ord("\\"):
            parts.append("\\\\")
        elif b == ord("("):
            parts.append("\\(")
        elif b == ord(")"):
            parts.append("\\)")
        elif 32 <= b <= 126:
            parts.append(chr(b))
        else:
            parts.append(f"\\{b:03o}")
    return "".join(parts)


def pdf_escape(text: str) -> str:
    return pdf_winansi_literal(text)


def text_width(text: str, font: str, size: float, *, hex_mode: bool = False) -> float:
    """Width in pt matching PDF Type1 Helvetica strings (``hex_mode`` kept for callers)."""
    del hex_mode
    return measure_text_width(text, font, size)


def strip_apple_code_sign_cn_prefix(common_name: str) -> str:
    """Drop known Apple CS prefix so stamp Signed-by shows the org / team id."""
    cn = common_name.replace("\n", " ").strip()
    for prefix in APPLE_CODE_SIGN_CN_PREFIXES:
        if cn.startswith(prefix):
            return cn[len(prefix) :].strip()
    return cn


def truncate_ellipsis(text: str, font: str, size: float, max_width: float) -> str:
    if max_width <= 0:
        return ELLIPSIS
    text = text.replace("\n", " ").strip()
    if text_width(text, font, size) <= max_width:
        return text
    ell = ELLIPSIS
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        body = text[:mid].rstrip()
        if text_width(body + ell, font, size) <= max_width:
            lo = mid
        else:
            hi = mid - 1
    body = text[:lo].rstrip()
    return body + ell if body else ell


@dataclass(frozen=True)
class FittedValue:
    text: str
    size_pt: float


def fit_value_in_column(
    text: str,
    font: str,
    nominal_size: float,
    max_width: float,
    *,
    min_scale: float = MIN_FONT_SCALE,
) -> FittedValue:
    """Shrink point size down to ``min_scale``, then truncate with a single ellipsis."""
    cleaned = text.replace("\n", " ").strip()
    if not cleaned:
        return FittedValue(cleaned, nominal_size)
    floor = max(MIN_FIELD_PT, nominal_size * min_scale)
    size = float(nominal_size)
    while size > floor + 1e-6:
        if text_width(cleaned, font, size) <= max_width:
            return FittedValue(cleaned, size)
        size -= FONT_FIT_STEP_PT
    size = max(floor, size)
    if text_width(cleaned, font, size) <= max_width:
        return FittedValue(cleaned, size)
    return FittedValue(truncate_ellipsis(cleaned, font, size, max_width), size)


def _hex_grouped(token: str, group: int) -> str:
    return " ".join(token[i : i + group] for i in range(0, len(token), group))


def truncate_cert_serial(
    serial: str,
    font: str,
    nominal_size: float,
    max_width: float,
    *,
    min_scale: float = MIN_FONT_SCALE,
) -> FittedValue:
    """
    Uppercase hex; show groups of 4 or pairs when they fit; else first 16 chars + ….
    Uses the same shrink-then-ellipsis strategy as other value rows.
    """
    token = re.sub(r"[^0-9A-Fa-f]", "", serial).upper()
    if not token:
        return FittedValue("n/a", nominal_size)

    floor = max(MIN_FIELD_PT, nominal_size * min_scale)
    candidates = (_hex_grouped(token, 4), _hex_grouped(token, 2), token)
    size = float(nominal_size)
    while size >= floor - 1e-6:
        for candidate in candidates:
            if text_width(candidate, font, size) <= max_width:
                return FittedValue(candidate, size)
        size -= FONT_FIT_STEP_PT

    size = max(floor, size)

    def tw(t: str) -> float:
        return text_width(t, font, size)

    short = token[:16] + ELLIPSIS
    if tw(short) <= max_width:
        return FittedValue(short, size)
    body = token[:16]
    while body and tw(body + ELLIPSIS) > max_width:
        body = body[:-2] if len(body) > 2 else body[:-1]
    text = (body + ELLIPSIS) if body else ELLIPSIS
    return FittedValue(text, size)


def footer_reserved_height(footer_size: float, pad: float, scale: float) -> float:
    gap = max(3.0, 3.0 * scale)
    return pad + footer_size + gap


def _min_value_baseline(
    *,
    fields_top: float,
    label_size: float,
    row_lead: float,
    signer_extra: float,
    value_sizes: list[float],
) -> float:
    y = fields_top - label_size
    min_val = y
    for i, val_size in enumerate(value_sizes):
        val_y = y - max(0.0, (val_size - label_size) * 0.85)
        min_val = min(min_val, val_y)
        y -= row_lead + (signer_extra if i == 0 else 0.0)
    return min_val


def fit_field_typography(height_pt: float, value_sizes: list[float]) -> dict[str, float]:
    """
    Shrink field font sizes and row lead uniformly (floor 5pt) so every row fits
    between the top padding band and the footer reserve.
    """
    ly = scaled_layout(height_pt)
    scale = ly["s"]
    pad = ly["pad"]
    body_floor = footer_reserved_height(ly["footer_size"], pad, scale)
    fields_top = float(height_pt) - pad

    def metrics(shrink: float) -> dict[str, float]:
        return {
            "label_size": max(MIN_FIELD_PT, ly["label_size"] * shrink),
            "body_value_size": max(MIN_FIELD_PT, ly["body_value_size"] * shrink),
            "signer_value_size": max(MIN_FIELD_PT, ly["signer_value_size"] * shrink),
            "row_lead": max(MIN_FIELD_PT, ly["row_lead"] * shrink),
            "signer_extra": SIGNER_ROW_EXTRA_PT * shrink,
        }

    lo, hi = 0.05, 1.0
    for _ in range(20):
        mid = (lo + hi) / 2.0
        m = metrics(mid)
        min_y = _min_value_baseline(
            fields_top=fields_top,
            label_size=m["label_size"],
            row_lead=m["row_lead"],
            signer_extra=m["signer_extra"],
            value_sizes=value_sizes,
        )
        if min_y >= body_floor:
            lo = mid
        else:
            hi = mid
    chosen = metrics(lo)
    chosen.update(
        {
            "s": scale,
            "pad": pad,
            "border": ly["border"],
            "x_label": ly["x_label"],
            "x_value": ly["x_value"],
            "footer_size": ly["footer_size"],
            "footer_drop_180": ly["footer_drop_180"],
        }
    )
    return chosen
