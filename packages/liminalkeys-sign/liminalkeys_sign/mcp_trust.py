"""Verify signed MCP tool responses (mutual authentication with LK MCP)."""

from __future__ import annotations

import base64
import json
import re
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from liminalkeys_sign.mcp_canonical import MCP_RESPONSE_SIGNING_VERSION, build_signing_message


class McpTrustError(Exception):
    """Fail-closed MCP response trust failure."""


DEFAULT_MAX_SKEW_SECONDS = 300
JWKS_WELL_KNOWN_PATH = "/.well-known/liminalkeys-mcp-keys.json"
DEFAULT_TRUST_RESOURCE = "liminalkeys_mcp_trust.json"
DEFAULT_JWKS_RESOURCE = "liminalkeys-mcp-keys.json"
SKILL_TRUST_FILENAME = "liminalkeys_mcp_trust.prod.json"
SKILL_JWKS_FILENAME = "liminalkeys-mcp-keys.json"


def _parse_trust_raw(raw: dict[str, Any]) -> McpTrustConfig:
    hosts = tuple(raw.get("allowed_hosts") or ())
    keys = dict(raw.get("keys") or {})
    skew = int(raw.get("max_skew_seconds") or DEFAULT_MAX_SKEW_SECONDS)
    if not hosts:
        raise McpTrustError("Trust config must list at least one allowed_hosts entry.")
    return McpTrustConfig(allowed_hosts=hosts, pinned_keys=keys, max_skew_seconds=skew)


def _load_bundled_trust_raw() -> dict[str, Any]:
    ref = files("liminalkeys_sign.data").joinpath(DEFAULT_TRUST_RESOURCE)
    raw = json.loads(ref.read_text(encoding="utf-8"))
    if not raw.get("keys"):
        raw = {**raw, "keys": _jwks_to_pinned_keys(_load_bundled_jwks_raw())}
    return raw


def _load_bundled_jwks_raw() -> dict[str, Any]:
    ref = files("liminalkeys_sign.data").joinpath(DEFAULT_JWKS_RESOURCE)
    return json.loads(ref.read_text(encoding="utf-8"))


def _jwks_to_pinned_keys(jwks: dict[str, Any]) -> dict[str, dict[str, Any]]:
    pinned: dict[str, dict[str, Any]] = {}
    for entry in jwks.get("keys") or []:
        kid = entry.get("kid")
        if kid:
            pinned[str(kid)] = dict(entry)
    return pinned


@dataclass(frozen=True)
class McpTrustConfig:
    allowed_hosts: tuple[str, ...]
    pinned_keys: dict[str, dict[str, Any]]
    max_skew_seconds: int = DEFAULT_MAX_SKEW_SECONDS

    @classmethod
    def load(cls, path: Path) -> McpTrustConfig:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return _parse_trust_raw(raw)

    @classmethod
    def load_optional(cls, path: Path | None) -> McpTrustConfig:
        if path is None:
            return _parse_trust_raw(_load_bundled_trust_raw())
        return cls.load(path)


def _assert_allowed_host(mcp_host: str, config: McpTrustConfig) -> None:
    host = mcp_host.lower().strip()
    if host.startswith("https://"):
        host = urlparse(host).hostname or ""
    if host.startswith("http://"):
        raise McpTrustError("MCP host must use HTTPS.")
    if not host or host not in {h.lower() for h in config.allowed_hosts}:
        raise McpTrustError(
            f"MCP host {host!r} is not in the pinned allow list {config.allowed_hosts!r}."
        )


def _parse_rfc3339(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _ec_public_key(jwk: dict[str, Any]):
    if jwk.get("kty") != "EC" or jwk.get("crv") not in (None, "P-256"):
        raise McpTrustError("Only EC P-256 (ES256) MCP response keys are supported in v1.")
    x = int.from_bytes(_b64url_decode(jwk["x"]), "big")
    y = int.from_bytes(_b64url_decode(jwk["y"]), "big")
    return ec.EllipticCurvePublicNumbers(x, y, ec.SECP256R1()).public_key()


def _b64url_decode(value: str) -> bytes:
    pad = "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode(value + pad)


def _b64_decode(value: str) -> bytes:
    return base64.b64decode(value, validate=False)


def _fetch_jwks(host: str) -> dict[str, Any]:
    url = f"https://{host}{JWKS_WELL_KNOWN_PATH}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, context=ssl.create_default_context(), timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise McpTrustError(f"Unable to fetch JWKS from pinned host: {exc}") from exc


def _resolve_jwk(kid: str, config: McpTrustConfig, mcp_host: str) -> dict[str, Any]:
    if kid in config.pinned_keys:
        return config.pinned_keys[kid]
    bundled = _jwks_to_pinned_keys(_load_bundled_jwks_raw())
    if kid in bundled:
        return bundled[kid]
    try:
        doc = _fetch_jwks(mcp_host)
    except McpTrustError as exc:
        raise McpTrustError(f"No trusted public key for kid {kid!r}.") from exc
    for key in doc.get("keys") or []:
        if key.get("kid") == kid:
            return key
    raise McpTrustError(f"No trusted public key for kid {kid!r}.")


def _envelope_err(envelope_label: str | None, message: str) -> McpTrustError:
    if envelope_label:
        return McpTrustError(f"{envelope_label}: {message}")
    return McpTrustError(message)


def verify_signed_mcp_envelope(
    envelope: dict[str, Any],
    *,
    expected_tool: str,
    expected_nonce: str,
    mcp_host: str,
    trust: McpTrustConfig,
    now: datetime | None = None,
    check_issued_at_skew: bool = True,
    envelope_label: str | None = None,
) -> dict[str, Any]:
    _assert_allowed_host(mcp_host, trust)
    for field in ("v", "tool", "agent_id", "nonce", "issued_at", "payload", "kid", "alg", "signature"):
        if field not in envelope:
            raise _envelope_err(envelope_label, f"Signed MCP response missing field {field!r}.")

    if int(envelope["v"]) != MCP_RESPONSE_SIGNING_VERSION:
        raise _envelope_err(envelope_label, "Unsupported MCP response envelope version.")

    if envelope["tool"] != expected_tool:
        raise _envelope_err(
            envelope_label,
            f"MCP response tool mismatch: expected {expected_tool!r}, got {envelope['tool']!r}.",
        )
    if envelope["nonce"] != expected_nonce:
        raise _envelope_err(
            envelope_label,
            "MCP response nonce mismatch (possible replay or wrong request).",
        )

    if check_issued_at_skew:
        issued = _parse_rfc3339(str(envelope["issued_at"]))
        clock = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        skew = abs((clock - issued).total_seconds())
        if skew > trust.max_skew_seconds:
            raise _envelope_err(
                envelope_label,
                "MCP response timestamp outside allowed skew "
                f"({skew:.0f}s > {trust.max_skew_seconds}s).",
            )

    if envelope["alg"] != "ES256":
        raise _envelope_err(
            envelope_label,
            f"Unsupported MCP response algorithm {envelope['alg']!r}.",
        )

    message = build_signing_message(
        v=int(envelope["v"]),
        tool=str(envelope["tool"]),
        agent_id=str(envelope["agent_id"]),
        nonce=str(envelope["nonce"]),
        issued_at=str(envelope["issued_at"]),
        payload=envelope["payload"],
    )
    jwk = _resolve_jwk(str(envelope["kid"]), trust, mcp_host.split("://")[-1].split("/")[0])
    pub = _ec_public_key(jwk)
    sig = _b64_decode(str(envelope["signature"]))
    try:
        pub.verify(sig, message, ec.ECDSA(hashes.SHA256()))
    except InvalidSignature as exc:
        raise _envelope_err(envelope_label, "MCP response signature is invalid.") from exc

    return envelope["payload"]


def load_envelope_json(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8").strip()
    # Allow MCP text wrapper: extract first JSON object if wrapped in markdown.
    if text.startswith("{"):
        return json.loads(text)
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise McpTrustError("No JSON envelope found in MCP response file.")
    return json.loads(match.group(0))
