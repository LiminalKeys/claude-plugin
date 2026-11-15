"""End-to-end prepare → mock sign_hash → embed → validate."""

from __future__ import annotations

import pytest
from asn1crypto import algos, keys, tsp, x509 as asn1_x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.x509 import load_pem_x509_certificate
from cryptography.hazmat.primitives.asymmetric import padding, utils
from pyhanko.sign.timestamps.dummy_client import DummyTimeStamper

from liminalkeys_sign.embed import run_embed
from liminalkeys_sign.prepare import DEFAULT_BYTES_RESERVED, run_prepare
from liminalkeys_sign.validate import run_validate
from liminalkeys_sign.verify import SignatureVerificationError, verify_sha256_rsa_pkcs1v15


def _mock_sign_hash(private_key, digest_path):
    digest = digest_path.read_bytes()
    assert len(digest) == 32
    return private_key.sign(
        digest,
        padding.PKCS1v15(),
        utils.Prehashed(hashes.SHA256()),
    )


def _build_timestamp_response(signature: bytes, cert_pem: bytes, private_key) -> bytes:
    """Simulate MCP timestamp passthrough for PAdES B-T (SHA-256 of signature bytes)."""
    md = hashes.Hash(hashes.SHA256())
    md.update(signature)
    imprint = md.finalize()
    req = tsp.TimeStampReq(
        {
            "version": 1,
            "message_imprint": tsp.MessageImprint(
                {
                    "hash_algorithm": algos.DigestAlgorithm({"algorithm": "sha256"}),
                    "hashed_message": imprint,
                }
            ),
            "cert_req": True,
        }
    )
    key_der = private_key.private_bytes(
        serialization.Encoding.DER,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    cert_der = load_pem_x509_certificate(cert_pem).public_bytes(Encoding.DER)
    timestamper = DummyTimeStamper(
        tsa_cert=asn1_x509.Certificate.load(cert_der),
        tsa_key=keys.PrivateKeyInfo.load(key_der),
        include_nonce=False,
    )
    resp = timestamper.request_tsa_response(req)
    return resp.dump()


def test_prepare_default_bytes_reserved_supports_bt():
    assert DEFAULT_BYTES_RESERVED >= 40_000


def test_prepare_embed_validate_baseline(signing_material, input_pdf, work_dir):
    prep = run_prepare(input_pdf, signing_material["leaf_path"], work_dir)
    assert len(bytes.fromhex(prep.digest_hex)) == 32
    assert prep.digest_path.read_bytes() == bytes.fromhex(prep.digest_hex)

    signature = _mock_sign_hash(signing_material["key"], prep.digest_path)
    verify_sha256_rsa_pkcs1v15(signing_material["cert_pem"], prep.digest_path.read_bytes(), signature)

    sig_path = work_dir / "signature.bin"
    sig_path.write_bytes(signature)
    out_pdf = work_dir / "signed.pdf"
    run_embed(work_dir, signing_material["leaf_path"], sig_path, out_pdf)

    outcome = run_validate(out_pdf, [signing_material["leaf_path"]])
    assert outcome.ok, outcome.report


def test_embed_rejects_bad_signature(signing_material, input_pdf, work_dir):
    run_prepare(input_pdf, signing_material["leaf_path"], work_dir)
    bad_sig = work_dir / "signature.bin"
    bad_sig.write_bytes(b"\x00" * 256)
    with pytest.raises(SignatureVerificationError):
        verify_sha256_rsa_pkcs1v15(
            signing_material["cert_pem"],
            (work_dir / "tbs_digest.bin").read_bytes(),
            bad_sig.read_bytes(),
        )


def test_prepare_embed_validate_with_timestamp(signing_material, input_pdf, work_dir):
    prep = run_prepare(input_pdf, signing_material["leaf_path"], work_dir)
    signature = _mock_sign_hash(signing_material["key"], prep.digest_path)
    sig_path = work_dir / "signature.bin"
    sig_path.write_bytes(signature)

    ts_der = _build_timestamp_response(
        signature,
        signing_material["cert_pem"],
        signing_material["key"],
    )
    ts_path = work_dir / "timestamp.der"
    ts_path.write_bytes(ts_der)

    out_pdf = work_dir / "signed_bt.pdf"
    run_embed(
        work_dir,
        signing_material["leaf_path"],
        sig_path,
        out_pdf,
        timestamp_response=ts_path,
    )
    outcome = run_validate(out_pdf, [signing_material["leaf_path"]])
    assert outcome.ok, outcome.report
    assert "timestamp" in outcome.report.lower() or "Timestamp" in outcome.report


def test_validate_fails_on_unsigned(input_pdf, signing_material, work_dir):
    outcome = run_validate(input_pdf, [signing_material["leaf_path"]])
    assert not outcome.ok
