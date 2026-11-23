"""Two-phase prepare → REST-shaped host sign → embed → validate (no live LK credentials)."""

from __future__ import annotations

import base64

from liminalkeys_sign.embed import run_embed
from liminalkeys_sign.prepare import run_prepare
from liminalkeys_sign.rest_host import digest_base64_from_work_dir, signature_bytes_from_rest
from liminalkeys_sign.validate import run_validate
from liminalkeys_sign.verify import verify_sha256_rsa_pkcs1v15


def test_rest_signature_decode_roundtrip():
    payload = base64.b64encode(b"\xab" * 256).decode()
    assert signature_bytes_from_rest(payload) == b"\xab" * 256


def test_two_phase_prepare_rest_embed_validate(signing_material, input_pdf, work_dir):
    """Phase 1 (sandbox): prepare. Host: mock POST /v1/sign. Phase 2 (sandbox): embed."""
    prep = run_prepare(input_pdf, signing_material["leaf_path"], work_dir)
    digest_b64 = digest_base64_from_work_dir(prep.digest_path)
    assert len(base64.b64decode(digest_b64)) == 32

    # Host would POST /v1/sign with digest=digest_b64; we mock KMS with local key.
    digest = prep.digest_path.read_bytes()
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding, utils

    signature = signing_material["key"].sign(
        digest,
        padding.PKCS1v15(),
        utils.Prehashed(hashes.SHA256()),
    )
    rest_payload_b64 = base64.b64encode(signature).decode()
    sig_bytes = signature_bytes_from_rest(rest_payload_b64)
    verify_sha256_rsa_pkcs1v15(signing_material["cert_pem"], digest, sig_bytes)

    sig_path = work_dir / "signature.bin"
    sig_path.write_bytes(sig_bytes)
    out_pdf = work_dir / "signed.pdf"
    run_embed(work_dir, signing_material["leaf_path"], sig_path, out_pdf)

    outcome = run_validate(out_pdf, [signing_material["leaf_path"]])
    assert outcome.ok, outcome.report
