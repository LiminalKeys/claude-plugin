#!/usr/bin/env python3
"""Regenerate ``helvetica_winansi_widths.json`` from ReportLab's bundled AFM data."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "src" / "liminalkeys_sign" / "data" / "helvetica_winansi_widths.json"


def main() -> int:
    try:
        import reportlab.pdfbase.pdfmetrics as pm
    except ImportError:
        print("reportlab is required for this maintainer script", file=sys.stderr)
        return 1
    data: dict[str, dict[int, int]] = {}
    for fname in ("Helvetica", "Helvetica-Bold"):
        gw = pm.getFont(fname).face.glyphWidths
        data[fname] = {k: gw.get(chr(k), gw.get("space", 278)) for k in range(32, 256)}
    OUT.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())