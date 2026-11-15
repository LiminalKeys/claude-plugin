#!/usr/bin/env python3
"""Bake cropped LK mark PNG into the package for offline installs."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_LOGO = ROOT / "branding" / "ciam" / "square-logo.png"
PKG_DATA = Path(__file__).resolve().parents[1] / "liminalkeys_sign" / "data"
OUT = PKG_DATA / "lk-square-mark-cropped.png"
BAKED = PKG_DATA / "lk-watermark-baked-rgb.png"


def main() -> int:
    from PIL import Image

    if not SRC_LOGO.is_file():
        print(f"missing {SRC_LOGO}", file=sys.stderr)
        return 1
    img = Image.open(SRC_LOGO).convert("RGBA").crop((28, 28, 212, 212))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, optimize=True)
    print(f"wrote {OUT} ({img.size[0]}x{img.size[1]})")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from liminalkeys_sign.stamp_watermark import soften_on_white

    baked = soften_on_white(img)
    baked.save(BAKED, optimize=True)
    print(f"wrote {BAKED}")
    import struct

    rgb = baked.convert("RGB")
    packed = PKG_DATA / "lk-watermark-device-rgb.bin"
    packed.write_bytes(
        struct.pack(">II", rgb.size[0], rgb.size[1]) + rgb.tobytes()
    )
    print(f"wrote {packed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
