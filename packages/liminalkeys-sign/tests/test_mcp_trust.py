"""MCP mutual-auth verification (signed tool responses)."""

from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from liminalkeys_sign.chain_anchor import ChainAnchorError, verify_chain_anchors
from liminalkeys_sign.mcp_canonical import MCP_RESPONSE_SIGNING_VERSION, build_signing_message
from liminalkeys_sign.mcp_trust import (
    McpTrustConfig,
    McpTrustError,
    verify_signed_mcp_envelope,
)
from liminalkeys_sign.verify import SignatureVerificationError, verify_sha256_rsa_pkcs1v15


@pytest.fixture
def ec_signing_key():
    key = ec.generate_private_key(ec.SECP256R1())
    pub = key.public_key()
    numbers = pub.public_numbers()
    x = base64.urlsafe_b64encode(numbers.x.to_bytes(32, "big")).decode().rstrip("=")
    y = base64.urlsafe_b64encode(numbers.y.to_bytes(32, "big")).decode().rstrip("=")
    jwk = {"kty": "EC", "crv": "P-256", "x": x, "y": y, "kid": "test-kid", "use": "sig", "alg": "ES256"}
    return key, jwk


def _sign_envelope(
    key,
    *,
    tool: str,
    agent_id: str,
    nonce: str,
    payload: dict,
    kid: str = "test-kid",
    issued_at: str | None = None,
) -> dict:
    if issued_at is None:
        issued_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    message = build_signing_message(
        v=MCP_RESPONSE_SIGNING_VERSION,
        tool=tool,
        agent_id=agent_id,
        nonce=nonce,
        issued_at=issued_at,
        payload=payload,
    )
    sig = key.sign(message, ec.ECDSA(hashes.SHA256()))
    return {
        "v": MCP_RESPONSE_SIGNING_VERSION,
        "tool": tool,
        "agent_id": agent_id,
        "nonce": nonce,
        "issued_at": issued_at,
        "payload": payload,
        "kid": kid,
        "alg": "ES256",
        "signature": base64.b64encode(sig).decode(),
    }


@pytest.fixture
def trust_config(tmp_path: Path, ec_signing_key) -> Path:
    _, jwk = ec_signing_key
    cfg = {
        "allowed_hosts": ["mcp.test.liminalkeys.com"],
        "max_skew_seconds": 300,
        "keys": {"test-kid": jwk},
    }
    path = tmp_path / "trust.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    return path


def test_bundled_default_trust_config():
    trust = McpTrustConfig.load_optional(None)
    assert "mcp.liminalkeys.com" in trust.allowed_hosts
    assert "mcp-response-v1" in trust.pinned_keys
    assert trust.pinned_keys["mcp-response-v1"]["kty"] == "EC"


def test_bundled_jwks_resolves_without_network(ec_signing_key, monkeypatch):
    key, jwk = ec_signing_key
    trust = McpTrustConfig(
        allowed_hosts=("mcp.test.liminalkeys.com",),
        pinned_keys={},
        max_skew_seconds=300,
    )
    nonce = base64.b64encode(b"j" * 16).decode()
    env = _sign_envelope(
        key,
        tool="sign_hash",
        agent_id="agent01",
        nonce=nonce,
        payload={"signature": "AQ=="},
    )

    def fail_fetch(_host: str):
        raise AssertionError("network JWKS fetch should not run for bundled kid")

    monkeypatch.setattr("liminalkeys_sign.mcp_trust._fetch_jwks", fail_fetch)
    monkeypatch.setattr(
        "liminalkeys_sign.mcp_trust._load_bundled_jwks_raw",
        lambda: {"keys": [jwk]},
    )
    payload = verify_signed_mcp_envelope(
        env,
        expected_tool="sign_hash",
        expected_nonce=nonce,
        mcp_host="mcp.test.liminalkeys.com",
        trust=trust,
    )
    assert payload["signature"] == "AQ=="


def test_jwks_bootstrap_for_unknown_kid(ec_signing_key, trust_config, monkeypatch):
    key, jwk = ec_signing_key
    trust = McpTrustConfig.load(trust_config)
    # Empty pinned keys: resolve via JWKS fetch mock.
    trust_no_pins = McpTrustConfig(
        allowed_hosts=trust.allowed_hosts,
        pinned_keys={},
        max_skew_seconds=trust.max_skew_seconds,
    )
    nonce = base64.b64encode(b"j" * 16).decode()
    env = _sign_envelope(
        key,
        tool="sign_hash",
        agent_id="agent01",
        nonce=nonce,
        payload={"signature": "AQ=="},
    )

    def fake_fetch(host: str):
        assert host == "mcp.test.liminalkeys.com"
        return {"keys": [jwk]}

    monkeypatch.setattr("liminalkeys_sign.mcp_trust._fetch_jwks", fake_fetch)
    payload = verify_signed_mcp_envelope(
        env,
        expected_tool="sign_hash",
        expected_nonce=nonce,
        mcp_host="mcp.test.liminalkeys.com",
        trust=trust_no_pins,
    )
    assert payload["signature"] == "AQ=="


def test_reject_stale_envelope_skew_on_first_verify(ec_signing_key, trust_config):
    key, _ = ec_signing_key
    nonce = base64.b64encode(b"s" * 16).decode()
    stale = (datetime.now(timezone.utc) - timedelta(seconds=400)).isoformat().replace("+00:00", "Z")
    env = _sign_envelope(
        key,
        tool="get_certificate_chain",
        agent_id="agent01",
        nonce=nonce,
        payload={"leafPem": "-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----\n"},
        issued_at=stale,
    )
    trust = McpTrustConfig.load(trust_config)
    with pytest.raises(McpTrustError, match="get_certificate_chain MCP envelope.*skew"):
        verify_signed_mcp_envelope(
            env,
            expected_tool="get_certificate_chain",
            expected_nonce=nonce,
            mcp_host="mcp.test.liminalkeys.com",
            trust=trust,
            envelope_label="get_certificate_chain MCP envelope",
        )


def test_stale_envelope_ok_when_skew_check_disabled(ec_signing_key, trust_config):
    key, _ = ec_signing_key
    nonce = base64.b64encode(b"t" * 16).decode()
    stale = (datetime.now(timezone.utc) - timedelta(seconds=400)).isoformat().replace("+00:00", "Z")
    env = _sign_envelope(
        key,
        tool="sign_hash",
        agent_id="agent01",
        nonce=nonce,
        payload={"signature": "AQ=="},
        issued_at=stale,
    )
    trust = McpTrustConfig.load(trust_config)
    payload = verify_signed_mcp_envelope(
        env,
        expected_tool="sign_hash",
        expected_nonce=nonce,
        mcp_host="mcp.test.liminalkeys.com",
        trust=trust,
        check_issued_at_skew=False,
        envelope_label="sign_hash MCP envelope",
    )
    assert payload["signature"] == "AQ=="


def test_verify_signed_envelope_ok(ec_signing_key, trust_config):
    key, _ = ec_signing_key
    nonce = base64.b64encode(b"n" * 16).decode()
    env = _sign_envelope(
        key,
        tool="sign_hash",
        agent_id="agent01",
        nonce=nonce,
        payload={"signature": "AQ=="},
    )
    trust = McpTrustConfig.load(trust_config)
    payload = verify_signed_mcp_envelope(
        env,
        expected_tool="sign_hash",
        expected_nonce=nonce,
        mcp_host="mcp.test.liminalkeys.com",
        trust=trust,
    )
    assert payload["signature"] == "AQ=="


def test_reject_tampered_payload(ec_signing_key, trust_config):
    key, _ = ec_signing_key
    nonce = base64.b64encode(b"x" * 16).decode()
    env = _sign_envelope(key, tool="sign_hash", agent_id="a", nonce=nonce, payload={"signature": "AQ=="})
    env["payload"] = {"signature": "Aw=="}
    trust = McpTrustConfig.load(trust_config)
    with pytest.raises(McpTrustError, match="invalid"):
        verify_signed_mcp_envelope(
            env,
            expected_tool="sign_hash",
            expected_nonce=nonce,
            mcp_host="mcp.test.liminalkeys.com",
            trust=trust,
        )


def test_reject_wrong_nonce(ec_signing_key, trust_config):
    key, _ = ec_signing_key
    nonce = base64.b64encode(b"y" * 16).decode()
    env = _sign_envelope(key, tool="sign_hash", agent_id="a", nonce=nonce, payload={"signature": "AQ=="})
    trust = McpTrustConfig.load(trust_config)
    with pytest.raises(McpTrustError, match="nonce"):
        verify_signed_mcp_envelope(
            env,
            expected_tool="sign_hash",
            expected_nonce=base64.b64encode(b"z" * 16).decode(),
            mcp_host="mcp.test.liminalkeys.com",
            trust=trust,
        )


def test_reject_wrong_host(ec_signing_key, trust_config):
    key, _ = ec_signing_key
    nonce = base64.b64encode(b"h" * 16).decode()
    env = _sign_envelope(key, tool="sign_hash", agent_id="a", nonce=nonce, payload={"signature": "AQ=="})
    trust = McpTrustConfig.load(trust_config)
    with pytest.raises(McpTrustError, match="allow list"):
        verify_signed_mcp_envelope(
            env,
            expected_tool="sign_hash",
            expected_nonce=nonce,
            mcp_host="evil.example",
            trust=trust,
        )


def test_reject_wrong_kid(ec_signing_key, trust_config):
    key, _ = ec_signing_key
    nonce = base64.b64encode(b"k" * 16).decode()
    env = _sign_envelope(key, tool="sign_hash", agent_id="a", nonce=nonce, payload={"signature": "AQ=="})
    env["kid"] = "unknown-kid"
    trust = McpTrustConfig.load(trust_config)
    with pytest.raises(McpTrustError, match="trusted public key"):
        verify_signed_mcp_envelope(
            env,
            expected_tool="sign_hash",
            expected_nonce=nonce,
            mcp_host="mcp.test.liminalkeys.com",
            trust=trust,
        )


def test_signature_not_matching_cert(signing_material, input_pdf, work_dir):
    from liminalkeys_sign.prepare import run_prepare

    prep = run_prepare(input_pdf, signing_material["leaf_path"], work_dir)
    bad_sig = b"\x01" * 256
    with pytest.raises(SignatureVerificationError):
        verify_sha256_rsa_pkcs1v15(
            signing_material["cert_pem"],
            prep.digest_path.read_bytes(),
            bad_sig,
        )


def test_chain_not_anchoring(signing_material, work_dir):
    import datetime

    from cryptography import x509
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    leaf = signing_material["cert_pem"]
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Other Trust Anchor")])
    now = datetime.datetime.now(datetime.timezone.utc)
    other_cert = (
        x509.CertificateBuilder()
        .subject_name(other_name)
        .issuer_name(other_name)
        .public_key(other_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=30))
        .sign(other_key, hashes.SHA256())
    )
    other_pem = other_cert.public_bytes(serialization.Encoding.PEM)
    with pytest.raises(ChainAnchorError):
        verify_chain_anchors(leaf, [], [other_pem])
