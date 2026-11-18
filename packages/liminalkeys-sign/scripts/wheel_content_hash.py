#!/usr/bin/env python3
"""Print the sha256 prefix used by bin/liminal-sign cache keys (16 hex chars)."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: wheel_content_hash.py WHEEL_PATH", file=sys.stderr)
        return 2
    path = Path(argv[1])
    if not path.is_file():
        print(f"missing wheel: {path}", file=sys.stderr)
        return 1
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    print(digest[:16])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))