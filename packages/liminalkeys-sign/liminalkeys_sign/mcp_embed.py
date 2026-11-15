"""Bridge MCP signed envelopes into embed (verify then extract signature)."""

from __future__ import annotations

import base64
from pathlib import Path

from liminalkeys_sign.chain_anchor import ChainAnchorError, verify_chain_anchors
from liminalkeys_sign.mcp_trust import (
    McpTrustConfig,
    McpTrustError,
    load_envelope_json,
    verify_signed_mcp_envelope,
)


def resolve_signature_from_mcp(
    *,
    sign_envelope_path: Path,
    expected_tool: str,
    expected_nonce: str,
    mcp_host: str,
    trust_config: Path | None,
) -> bytes:
    trust = McpTrustConfig.load_optional(trust_config)
    envelope = load_envelope_json(sign_envelope_path)
    payload = verify_signed_mcp_envelope(
        envelope,
        expected_tool=expected_tool,
        expected_nonce=expected_nonce,
        mcp_host=mcp_host,
        trust=trust,
        check_issued_at_skew=False,
        envelope_label=f"{expected_tool} MCP envelope",
    )
    if expected_tool == "sign_hash":
        sig_b64 = payload.get("signature")
        if not sig_b64:
            raise McpTrustError("sign_hash MCP payload missing signature.")
        return base64.b64decode(sig_b64)
    raise McpTrustError(f"Tool {expected_tool!r} does not yield a CMS signature.")


def verify_identity_chain_from_mcp(
    *,
    chain_envelope_path: Path,
    expected_nonce: str,
    mcp_host: str,
    trust_config: Path | None,
    trust_anchors: list[Path],
    leaf_cert: Path,
    chain_pem_paths: list[Path] | None = None,
) -> None:
    trust = McpTrustConfig.load_optional(trust_config)
    envelope = load_envelope_json(chain_envelope_path)
    payload = verify_signed_mcp_envelope(
        envelope,
        expected_tool="get_certificate_chain",
        expected_nonce=expected_nonce,
        mcp_host=mcp_host,
        trust=trust,
        check_issued_at_skew=False,
        envelope_label="get_certificate_chain MCP envelope",
    )
    leaf_pem = (payload.get("leafPem") or "").encode("utf-8")
    if not leaf_pem.strip():
        raise McpTrustError("Certificate chain payload missing leafPem.")
    on_disk_leaf = leaf_cert.read_bytes()
    if leaf_pem.strip() != on_disk_leaf.strip():
        raise McpTrustError("Leaf certificate does not match signed MCP chain payload.")

    inter_pems = [p.encode("utf-8") for p in (payload.get("intermediatePems") or [])]
    if chain_pem_paths:
        for path in chain_pem_paths:
            inter_pems.append(path.read_bytes())
    anchors = [p.read_bytes() for p in trust_anchors]
    try:
        verify_chain_anchors(leaf_pem, inter_pems, anchors)
    except ChainAnchorError as exc:
        raise McpTrustError(str(exc)) from exc
