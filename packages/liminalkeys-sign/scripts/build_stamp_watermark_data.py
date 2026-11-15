#!/usr/bin/env python3
"""Bake cropped LK mark PNG into the package for offline installs."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_LOGO = ROOT / "branding" / "ciam" / "square-logo.png"
OUT = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "liminalkeys_sign"
    / "data"
    / "lk-square-mark-cropped.png"
)


def main() -> int:
    from PIL import Image

    if not SRC_LOGO.is_file():
        print(f"missing {SRC_LOGO}", file=sys.stderr)
        return 1
    img = Image.open(SRC_LOGO).convert("RGBA").crop((28, 28, 212, 212))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, optimize=True)
    print(f"wrote {OUT} ({img.size[0]}x{img.size[1]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
