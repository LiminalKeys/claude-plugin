"""Verify RS256 (PKCS#1 v1.5) signatures over a pre-hashed SHA-256 digest."""

from __future__ import annotations

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, utils
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.x509 import load_pem_x509_certificate


class SignatureVerificationError(Exception):
    """Raised when the signature does not match the leaf certificate."""


def load_leaf_public_key(cert_pem: bytes) -> RSAPublicKey:
    cert = load_pem_x509_certificate(cert_pem)
    pub = cert.public_key()
    if not isinstance(pub, RSAPublicKey):
        raise SignatureVerificationError(
            "v1 supports RSA leaf certificates only (sha256_rsa)."
        )
    return pub


def verify_sha256_rsa_pkcs1v15(
    cert_pem: bytes,
    digest_32: bytes,
    signature: bytes,
) -> None:
    """
    Verify an RSASSA-PKCS1-v1_5 signature where LK signed DigestInfo(SHA-256, digest).

    ``digest_32`` must be exactly the 32-byte SHA-256 of the DER CMS signed attributes
    (the ``sign_hash`` MCP input).
    """
    if len(digest_32) != 32:
        raise SignatureVerificationError(
            f"Expected 32-byte digest for sign_hash, got {len(digest_32)} bytes."
        )
    pub = load_leaf_public_key(cert_pem)
    try:
        pub.verify(
            signature,
            digest_32,
            padding.PKCS1v15(),
            utils.Prehashed(hashes.SHA256()),
        )
    except InvalidSignature as exc:
        raise SignatureVerificationError(
            "RSA signature does not verify against the leaf certificate; refusing to embed."
        ) from exc
