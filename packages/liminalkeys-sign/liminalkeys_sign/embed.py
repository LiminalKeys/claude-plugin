"""Embed externally signed CMS into a prepared PDF."""

from __future__ import annotations

import asyncio
import io
import pickle
from pathlib import Path
from typing import Sequence

from asn1crypto import cms
from pyhanko.keys import load_cert_from_pemder
from pyhanko.sign import signers
from pyhanko.sign.signers.pdf_signer import PdfTBSDocument
from pyhanko_certvalidator.registry import SimpleCertificateStore

from liminalkeys_sign.timestamps import PassthroughTimeStamper
from liminalkeys_sign.verify import SignatureVerificationError, verify_sha256_rsa_pkcs1v15


async def _embed_async(
    work_dir: Path,
    leaf_cert: Path,
    signature: bytes,
    output_pdf: Path,
    chain_paths: Sequence[Path],
    signed_attrs_path: Path | None,
    timestamp_response: Path | None,
    digest_path: Path | None,
) -> None:
    state_path = work_dir / "state.pkl"
    if not state_path.is_file():
        raise FileNotFoundError(f"Missing prepare state: {state_path}")
    state = pickle.loads(state_path.read_bytes())
    if state.get("version") != 1:
        raise ValueError("Unsupported state.pkl version; re-run prepare.")

    attrs_path = signed_attrs_path or (work_dir / "signed_attrs.der")
    digest_file = digest_path or (work_dir / "tbs_digest.bin")
    if not attrs_path.is_file():
        raise FileNotFoundError(f"Missing signed attributes: {attrs_path}")
    if not digest_file.is_file():
        raise FileNotFoundError(f"Missing digest: {digest_file}")

    digest_32 = digest_file.read_bytes()
    cert_pem = leaf_cert.read_bytes()
    verify_sha256_rsa_pkcs1v15(cert_pem, digest_32, signature)

    cert = load_cert_from_pemder(str(leaf_cert))
    chain = [load_cert_from_pemder(str(p)) for p in chain_paths]
    registry = SimpleCertificateStore.from_certs([cert, *chain])
    ext = signers.ExternalSigner(
        signing_cert=cert,
        cert_registry=registry,
        signature_value=signature,
    )
    signed_attrs = cms.CMSAttributes.load(attrs_path.read_bytes())

    timestamper = None
    if timestamp_response is not None:
        timestamper = PassthroughTimeStamper(timestamp_response.read_bytes())

    sig_cms = await ext.async_sign_prescribed_attributes(
        "sha256",
        signed_attrs=signed_attrs,
        timestamper=timestamper,
    )
    out = io.BytesIO(state["pdf"])
    await PdfTBSDocument.async_finish_signing(
        out,
        prepared_digest=state["prep"],
        signature_cms=sig_cms,
        post_sign_instr=state["psi"],
    )
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    output_pdf.write_bytes(out.getvalue())


def run_embed(
    work_dir: Path,
    leaf_cert: Path,
    signature_path: Path,
    output_pdf: Path,
    *,
    chain_paths: Sequence[Path] | None = None,
    signed_attrs_path: Path | None = None,
    timestamp_response: Path | None = None,
    digest_path: Path | None = None,
) -> None:
    signature = signature_path.read_bytes()
    try:
        asyncio.run(
            _embed_async(
                work_dir,
                leaf_cert,
                signature,
                output_pdf,
                chain_paths or (),
                signed_attrs_path,
                timestamp_response,
                digest_path,
            )
        )
    except SignatureVerificationError:
        raise
