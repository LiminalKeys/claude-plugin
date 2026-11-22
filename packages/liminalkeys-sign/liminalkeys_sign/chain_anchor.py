"""Certificate chain anchoring checks before embed."""

from __future__ import annotations

from typing import Sequence

from cryptography.hazmat.primitives import hashes
from cryptography.x509 import Certificate, load_pem_x509_certificate


class ChainAnchorError(Exception):
    """Chain does not anchor to configured trust."""


def _load(pem: bytes) -> Certificate:
    return load_pem_x509_certificate(pem)


def verify_chain_anchors(
    leaf_pem: bytes,
    intermediate_pems: Sequence[bytes],
    trust_anchor_pems: Sequence[bytes],
) -> None:
    if not trust_anchor_pems:
        raise ChainAnchorError("At least one trust anchor PEM is required.")
    leaf = _load(leaf_pem)
    intermediates = [_load(p) for p in intermediate_pems]
    anchors = [_load(p) for p in trust_anchor_pems]

    for anchor in anchors:
        if leaf.fingerprint(hashes.SHA256()) == anchor.fingerprint(hashes.SHA256()):
            return

    pool = list(intermediates)
    current = leaf
    visited = {current.fingerprint(hashes.SHA256())}
    while True:
        for anchor in anchors:
            if current.issuer == anchor.subject:
                return
        next_cert = next((c for c in pool if c.subject == current.issuer), None)
        if next_cert is None:
            break
        fp = next_cert.fingerprint(hashes.SHA256())
        if fp in visited:
            break
        visited.add(fp)
        pool.remove(next_cert)
        current = next_cert

    raise ChainAnchorError(
        "Signing certificate chain does not anchor to the expected trust root."
    )
