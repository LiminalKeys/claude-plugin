#!/usr/bin/env python3
"""Refresh bundled MCP JWKS + trust pins from production well-known endpoint."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src" / "liminalkeys_sign" / "data"
JWKS_PATH = DATA / "liminalkeys-mcp-keys.json"
TRUST_PATH = DATA / "liminalkeys_mcp_trust.json"

DEFAULT_URLS = (
    "https://mcp.liminalkeys.com/.well-known/liminalkeys-mcp-keys.json",
    "https://liminalkeys-prod-t5i5nng43cprc-mcp.azurewebsites.net/.well-known/liminalkeys-mcp-keys.json",
)


def fetch_jwks(urls: tuple[str, ...]) -> dict[str, Any]:
    last_err: Exception | None = None
    for url in urls:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_err = exc
    raise SystemExit(f"Unable to fetch MCP JWKS from {urls!r}: {last_err}") from last_err


def jwks_to_trust(jwks: dict[str, Any]) -> dict[str, Any]:
    keys: dict[str, Any] = {}
    for entry in jwks.get("keys") or []:
        kid = entry.get("kid")
        if not kid:
            continue
        keys[str(kid)] = entry
    if "mcp-response-v1" not in keys:
        raise SystemExit("JWKS document missing required kid mcp-response-v1.")
    return {
        "allowed_hosts": ["mcp.liminalkeys.com"],
        "max_skew_seconds": 300,
        "keys": keys,
        "_comment": (
            "Pinned production MCP response signing key (public JWK). "
            "Sync from /.well-known/liminalkeys-mcp-keys.json via "
            "scripts/sync_bundled_mcp_keys.py before skill releases."
        ),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if committed files differ from live JWKS (no writes).",
    )
    parser.add_argument(
        "--url",
        action="append",
        dest="urls",
        default=[],
        help="Override JWKS URL (repeatable). Defaults to production host + configured fallback.",
    )
    args = parser.parse_args()
    urls = tuple(args.urls) if args.urls else DEFAULT_URLS
    jwks = fetch_jwks(urls)
    trust = jwks_to_trust(jwks)

    if args.check:
        if not JWKS_PATH.is_file() or not TRUST_PATH.is_file():
            print("Bundled MCP key files missing.", file=sys.stderr)
            return 1
        on_disk_jwks = json.loads(JWKS_PATH.read_text(encoding="utf-8"))
        on_disk_trust = json.loads(TRUST_PATH.read_text(encoding="utf-8"))
        if on_disk_jwks != jwks or on_disk_trust.get("keys") != trust.get("keys"):
            print("Bundled MCP keys are stale; run sync_bundled_mcp_keys.py.", file=sys.stderr)
            return 1
        print("Bundled MCP keys match live JWKS.")
        return 0

    write_json(JWKS_PATH, jwks)
    write_json(TRUST_PATH, trust)
    print(f"Updated {JWKS_PATH.relative_to(ROOT)} and {TRUST_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
