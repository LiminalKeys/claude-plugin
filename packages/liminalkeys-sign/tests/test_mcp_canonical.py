"""Cross-language parity with src/mcp responseSigning/canonical.ts."""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

from liminalkeys_sign.mcp_canonical import (
    MCP_RESPONSE_SIGNING_VERSION,
    _sort_keys,
    build_signing_message,
    stable_payload_json,
)
from liminalkeys_sign.mcp_trust import McpTrustConfig, verify_signed_mcp_envelope

FIXTURE = Path(__file__).parent / "fixtures" / "mcp_canonical_ts_golden.json"


@pytest.fixture(scope="module")
def golden() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_stable_payload_json_matches_typescript_golden(golden: dict):
    payload = golden["payload"]
    assert stable_payload_json(payload) == golden["stablePayloadJson"]
    # Default json.dumps spacing would diverge from MCP server signatures.
    spaced = json.dumps(_sort_keys(payload), ensure_ascii=False)
    assert spaced != golden["stablePayloadJson"]
    assert ": " in spaced


def test_build_signing_message_matches_typescript_golden(golden: dict):
    msg = golden["signingMessage"]
    body = build_signing_message(
        v=msg["v"],
        tool=msg["tool"],
        agent_id=msg["agent_id"],
        nonce=msg["nonce"],
        issued_at=msg["issued_at"],
        payload=golden["payload"],
    )
    expected = base64.b64decode(golden["signingMessageUtf8Base64"])
    assert body == expected


def test_verify_server_shaped_envelope_signature(tmp_path: Path, golden: dict):
    """Envelope signed with compact TS-shaped message bytes must verify in Python."""
    key = ec.generate_private_key(ec.SECP256R1())
    pub = key.public_key()
    numbers = pub.public_numbers()
    x = base64.urlsafe_b64encode(numbers.x.to_bytes(32, "big")).decode().rstrip("=")
    y = base64.urlsafe_b64encode(numbers.y.to_bytes(32, "big")).decode().rstrip("=")
    jwk = {"kty": "EC", "crv": "P-256", "x": x, "y": y, "kid": "test-kid", "use": "sig", "alg": "ES256"}
    trust_path = tmp_path / "trust.json"
    trust_path.write_text(
        json.dumps(
            {
                "allowed_hosts": ["mcp.test.liminalkeys.com"],
                "max_skew_seconds": 300,
                "keys": {"test-kid": jwk},
            }
        ),
        encoding="utf-8",
    )

    msg = golden["signingMessage"]
    message = build_signing_message(
        v=msg["v"],
        tool=msg["tool"],
        agent_id=msg["agent_id"],
        nonce=msg["nonce"],
        issued_at=msg["issued_at"],
        payload=golden["payload"],
    )
    sig = key.sign(message, ec.ECDSA(hashes.SHA256()))
    env = {
        "v": MCP_RESPONSE_SIGNING_VERSION,
        "tool": msg["tool"],
        "agent_id": msg["agent_id"],
        "nonce": msg["nonce"],
        "issued_at": msg["issued_at"],
        "payload": golden["payload"],
        "kid": "test-kid",
        "alg": "ES256",
        "signature": base64.b64encode(sig).decode(),
    }
    trust = McpTrustConfig.load(trust_path)
    issued_at = datetime.fromisoformat(msg["issued_at"].replace("Z", "+00:00"))
    payload = verify_signed_mcp_envelope(
        env,
        expected_tool=msg["tool"],
        expected_nonce=msg["nonce"],
        mcp_host="mcp.test.liminalkeys.com",
        trust=trust,
        now=issued_at,
    )
    assert payload["signature"] == "AQID"
