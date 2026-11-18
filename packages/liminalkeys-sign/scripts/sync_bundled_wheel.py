#!/usr/bin/env python3
"""Build liminalkeys_sign wheel and copy into skills/liminalkeys-sign/wheels."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
BUNDLED_DIR = REPO / "skills" / "liminalkeys-sign" / "wheels"


def _package_version() -> str:
    for line in (ROOT / "pyproject.toml").read_text(encoding="utf-8").splitlines():
        if line.startswith("version = "):
            return line.split("=", 1)[1].strip().strip('"')
    raise RuntimeError("version not found in pyproject.toml")


def main() -> int:
    version = _package_version()
    wheel_name = f"liminalkeys_sign-{version}-py3-none-any.whl"
    BUNDLED_DIR.mkdir(parents=True, exist_ok=True)
    for old in BUNDLED_DIR.glob("liminalkeys_sign-*.whl"):
        if old.name != wheel_name:
            old.unlink()
    dest = BUNDLED_DIR / wheel_name
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        subprocess.run(
            [sys.executable, "-m", "build", "--wheel", "--outdir", str(out)],
            cwd=ROOT,
            check=True,
        )
        built = out / wheel_name
        if not built.is_file():
            print(f"build missing {wheel_name}", file=sys.stderr)
            return 1
        shutil.copy2(built, dest)
    print(dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())