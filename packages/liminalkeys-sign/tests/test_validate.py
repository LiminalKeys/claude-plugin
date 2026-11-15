"""Validation gate: pyHanko bottom_line, signer vs TSA trust."""

from __future__ import annotations

import datetime

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from liminalkeys_sign.embed import run_embed
from liminalkeys_sign.prepare import run_prepare
from liminalkeys_sign.validate import resolve_validation_ok, run_validate
from test_sign_flow import _build_timestamp_response, _mock_sign_hash


def _self_signed_cert(common_name: str, *, eku_time_stamping: bool = False):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.datetime.now(datetime.timezone.utc)
    builder = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
    )
    if eku_time_stamping:
        builder = builder.add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.TIME_STAMPING]),
            critical=True,
        )
    cert = builder.sign(key, hashes.SHA256())
    pem = cert.public_bytes(serialization.Encoding.PEM)
    return key, pem


@pytest.fixture
def tsa_material(work_dir):
    key, pem = _self_signed_cert("Test TSA", eku_time_stamping=True)
    path = work_dir / "tsa.pem"
    path.write_bytes(pem)
    return {"key": key, "cert_pem": pem, "path": path}


def _signed_pdf_with_timestamp(
    signing_material,
    input_pdf,
    work_dir,
    *,
    tsa_material,
):
    prep = run_prepare(input_pdf, signing_material["leaf_path"], work_dir)
    signature = _mock_sign_hash(signing_material["key"], prep.digest_path)
    sig_path = work_dir / "signature.bin"
    sig_path.write_bytes(signature)
    ts_der = _build_timestamp_response(
        signature,
        tsa_material["cert_pem"],
        tsa_material["key"],
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
    return out_pdf


def test_validate_fails_when_tsa_not_trusted(signing_material, input_pdf, work_dir, tsa_material):
    out_pdf = _signed_pdf_with_timestamp(
        signing_material, input_pdf, work_dir, tsa_material=tsa_material
    )
    outcome = run_validate(out_pdf, [signing_material["leaf_path"]])
    assert not outcome.ok
    assert "INVALID" in outcome.summary
    assert "TSA chain trusted" in outcome.summary
    assert "judged INVALID" in outcome.report


def test_validate_passes_with_tsa_trust_anchors(signing_material, input_pdf, work_dir, tsa_material):
    out_pdf = _signed_pdf_with_timestamp(
        signing_material, input_pdf, work_dir, tsa_material=tsa_material
    )
    outcome = run_validate(
        out_pdf,
        [signing_material["leaf_path"]],
        tsa_trust_pems=[tsa_material["path"]],
    )
    assert outcome.ok
    assert outcome.warning is None
    assert "Judgment: VALID" in outcome.summary


def test_allow_untrusted_timestamp_warning_tier(signing_material, input_pdf, work_dir, tsa_material):
    out_pdf = _signed_pdf_with_timestamp(
        signing_material, input_pdf, work_dir, tsa_material=tsa_material
    )
    outcome = run_validate(
        out_pdf,
        [signing_material["leaf_path"]],
        allow_untrusted_timestamp=True,
    )
    assert outcome.ok
    assert outcome.warning is not None
    assert "WARNING" in outcome.warning


def test_signer_invalid_still_fails(input_pdf, signing_material, work_dir):
    outcome = run_validate(input_pdf, [signing_material["leaf_path"]])
    assert not outcome.ok


def test_resolve_validation_ok_uses_bottom_line(monkeypatch):
    class FakeStatus:
        bottom_line = False

        intact = True
        valid = True
        trusted = True
        seed_value_ok = True
        docmdp_ok = True
        timestamp_validity = object()
        content_timestamp_validity = None

    class FakeTs:
        intact = True
        valid = True
        trusted = False

    fake = FakeStatus()
    fake.timestamp_validity = FakeTs()
    ok, warning = resolve_validation_ok(fake, allow_untrusted_timestamp=False)  # type: ignore[arg-type]
    assert not ok
    ok2, warning2 = resolve_validation_ok(fake, allow_untrusted_timestamp=True)  # type: ignore[arg-type]
    assert ok2
    assert warning2
