"""CLI smoke tests."""

from __future__ import annotations

import subprocess
import sys


def test_cli_version():
    proc = subprocess.run(
        [sys.executable, "-m", "liminalkeys_sign", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "liminalkeys-sign" in proc.stdout
