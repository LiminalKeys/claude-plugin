"""Canonical MCP response signing input (must match src/mcp responseSigning/canonical.ts)."""

from __future__ import annotations

import json
from typing import Any


MCP_RESPONSE_SIGNING_VERSION = 1


def _sort_keys(value: Any) -> Any:
    if isinstance(value, list):
        return [_sort_keys(v) for v in value]
    if isinstance(value, dict):
        return {k: _sort_keys(value[k]) for k in sorted(value.keys())}
    return value


def stable_payload_json(payload: Any) -> str:
    # Match JSON.stringify(sortKeys(payload)) in canonical.ts (compact separators).
    return json.dumps(_sort_keys(payload), ensure_ascii=False, separators=(",", ":"))


def build_signing_message(
    *,
    v: int,
    tool: str,
    agent_id: str,
    nonce: str,
    issued_at: str,
    payload: Any,
) -> bytes:
    payload_json = stable_payload_json(payload)
    body = "\n".join([str(v), tool, agent_id, nonce, issued_at, payload_json])
    return body.encode("utf-8")
