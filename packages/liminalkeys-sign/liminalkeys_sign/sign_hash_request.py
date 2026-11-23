"""MCP sign_hash payload written to disk (never echoed to stdout by the agent)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def default_sign_hash_path(state_path: Path) -> Path:
    return state_path.with_name("sign_hash.json")


def build_sign_hash_request(
    *,
    digest_base64: str,
    document_label: str | None,
    previews: list[dict[str, str]],
    state_path: Path,
    poll_timeout_seconds: int = 120,
) -> dict[str, Any]:
    return {
        "digest_base64": digest_base64,
        "document_label": document_label or "",
        "previews": previews,
        "poll_timeout_seconds": poll_timeout_seconds,
        "paths": {
            "state_json": str(state_path.resolve()),
        },
    }


def write_sign_hash_request(
    output: Path,
    *,
    digest_base64: str,
    document_label: str | None,
    previews: list[dict[str, str]],
    state_path: Path,
    poll_timeout_seconds: int = 120,
) -> Path:
    payload = build_sign_hash_request(
        digest_base64=digest_base64,
        document_label=document_label,
        previews=previews,
        state_path=state_path,
        poll_timeout_seconds=poll_timeout_seconds,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return output.resolve()