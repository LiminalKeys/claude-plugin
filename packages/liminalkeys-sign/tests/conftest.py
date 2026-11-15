"""Test fixtures: ephemeral RSA certs and a minimal PDF (no committed key material)."""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from pyhanko.pdf_utils import generic, writer


@pytest.fixture
def work_dir(tmp_path: Path) -> Path:
    d = tmp_path / "work"
    d.mkdir()
    return d


@pytest.fixture
def signing_material(work_dir: Path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Liminal Keys Test Signer")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
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
                content_commitment=True,
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
        .sign(key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    leaf_path = work_dir / "leaf.pem"
    leaf_path.write_bytes(cert_pem)
    return {"key": key, "cert_pem": cert_pem, "leaf_path": leaf_path}


@pytest.fixture
def input_pdf(work_dir: Path) -> Path:
    w = writer.PdfFileWriter()
    stream = generic.StreamObject(stream_data=b"BT /F1 12 Tf 72 720 Td (test) Tj ET")
    font = generic.DictionaryObject(
        {
            generic.NameObject("/Type"): generic.NameObject("/Font"),
            generic.NameObject("/Subtype"): generic.NameObject("/Type1"),
            generic.NameObject("/BaseFont"): generic.NameObject("/Helvetica"),
        }
    )
    resources = generic.DictionaryObject(
        {generic.NameObject("/Font"): generic.DictionaryObject({generic.NameObject("/F1"): w.add_object(font)})}
    )
    page = writer.PageObject(
        contents=w.add_object(stream),
        media_box=[0, 0, 612, 792],
        resources=resources,
    )
    w.insert_page(page)
    pdf_path = work_dir / "input.pdf"
    with pdf_path.open("wb") as outf:
        w.write(outf)
    return pdf_path
