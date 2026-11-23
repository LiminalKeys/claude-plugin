"""Host-side helpers for Liminal Keys REST /v1/sign (outside code-execution sandboxes)."""

from __future__ import annotations

import base64
import binascii


class RestSignResponseError(ValueError):
    """REST sign response could not be decoded into raw RSA signature bytes."""


def signature_bytes_from_rest(signature_base64: str) -> bytes:
    """Decode the ``signature`` field from POST /v1/sign (200 OK)."""
    if not signature_base64 or not str(signature_base64).strip():
        raise RestSignResponseError("empty signature field")
    try:
        raw = base64.b64decode(signature_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise RestSignResponseError("signature is not valid base64") from exc
    if len(raw) < 64:
        raise RestSignResponseError(f"signature too short ({len(raw)} bytes)")
    return raw


def digest_base64_from_work_dir(tbs_digest_path) -> str:
    """Base64-encode ``tbs_digest.bin`` from a liminalkeys-sign work directory."""
    data = tbs_digest_path.read_bytes()
    if len(data) != 32:
        raise ValueError(f"expected 32-byte tbs digest, got {len(data)}")
    return base64.b64encode(data).decode("ascii")
