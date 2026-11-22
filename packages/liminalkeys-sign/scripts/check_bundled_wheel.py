#!/usr/bin/env python3
"""Fail CI when skills/liminalkeys-sign/wheels is out of date vs package source."""

from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
BUNDLED_DIR = REPO / "skills" / "liminalkeys-sign" / "wheels"


def _normalize_payload_bytes(name: str, data: bytes) -> bytes:
    """LF-normalize text payloads so Linux/Windows wheel builds compare equal."""
    if name.endswith((".py", ".json", ".md", ".txt")):
        return data.replace(b"\r\n", b"\n")
    return data


def _wheel_payload_sha256(path: Path) -> str:
    """Hash liminalkeys_sign package files inside the wheel (ignores RECORD timestamps)."""
    h = hashlib.sha256()
    with zipfile.ZipFile(path) as zf:
        names = sorted(
            n
            for n in zf.namelist()
            if n.startswith("liminalkeys_sign/") and not n.endswith("/")
        )
        for name in names:
            h.update(name.encode("utf-8"))
            h.update(b"\0")
            h.update(_normalize_payload_bytes(name, zf.read(name)))
    return h.hexdigest()


def _package_version() -> str:
    for line in (ROOT / "pyproject.toml").read_text(encoding="utf-8").splitlines():
        if line.startswith("version = "):
            return line.split("=", 1)[1].strip().strip('"')
    raise RuntimeError("version not found in pyproject.toml")


def main() -> int:
    version = _package_version()
    expected_name = f"liminalkeys_sign-{version}-py3-none-any.whl"
    bundled = BUNDLED_DIR / expected_name
    stale = sorted(BUNDLED_DIR.glob("liminalkeys_sign-*.whl"))
    for old in stale:
        if old.name != expected_name:
            print(f"ERROR: remove stale bundled wheel {old.relative_to(REPO)}", file=sys.stderr)
            return 1

    if not bundled.is_file():
        print(
            f"ERROR: missing bundled wheel {bundled.relative_to(REPO)} "
            f"(run: cd packages/liminalkeys-sign && python -m build && "
            f"scripts/sync_bundled_wheel.py)",
            file=sys.stderr,
        )
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        subprocess.run(
            [sys.executable, "-m", "build", "--wheel", "--outdir", str(tmp_path)],
            cwd=ROOT,
            check=True,
        )
        built = tmp_path / expected_name
        if not built.is_file():
            wheels = list(tmp_path.glob("liminalkeys_sign-*.whl"))
            print(f"ERROR: build produced {wheels!r}, expected {expected_name}", file=sys.stderr)
            return 1
        if _wheel_payload_sha256(built) != _wheel_payload_sha256(bundled):
            print(
                f"ERROR: bundled wheel {bundled.relative_to(REPO)} "
                f"does not match a fresh build from packages/liminalkeys-sign "
                f"(package payload mismatch)",
                file=sys.stderr,
            )
            print(
                "  Fix: python -m build && python scripts/sync_bundled_wheel.py",
                file=sys.stderr,
            )
            return 1

    print(f"OK: bundled wheel matches source ({expected_name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())