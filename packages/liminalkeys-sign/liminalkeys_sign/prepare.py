"""Prepare PAdES signature: signed attributes hash and signing state."""

from __future__ import annotations

import asyncio
import hashlib
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from pyhanko.keys import load_cert_from_pemder
from pyhanko.sign import fields, signers
from pyhanko_certvalidator.registry import SimpleCertificateStore
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter

from liminalkeys_sign.visible_stamp import (
    VisibleStampOptions,
    build_text_stamp_style,
    resolve_field_placement,
    stamp_appearance_text_params,
)

# PAdES B-T (RFC 3161 token + multi-cert chain) needs more CMS space than baseline-B.
DEFAULT_BYTES_RESERVED = 40_000

@dataclass(frozen=True)
class PrepareResult:
    digest_hex: str
    signed_attrs_path: Path
    digest_path: Path
    state_path: Path


def _load_cert_store(leaf_path: Path, chain_paths: Sequence[Path]) -> SimpleCertificateStore:
    certs = [load_cert_from_pemder(str(leaf_path))]
    for p in chain_paths:
        certs.append(load_cert_from_pemder(str(p)))
    return SimpleCertificateStore.from_certs(certs)


async def _prepare_async(
    input_pdf: Path,
    leaf_cert: Path,
    chain_paths: Sequence[Path],
    work_dir: Path,
    field_name: str,
    bytes_reserved: int,
    *,
    visible_signature: bool = False,
    stamp_options: VisibleStampOptions | None = None,
) -> PrepareResult:
    work_dir.mkdir(parents=True, exist_ok=True)
    cert = load_cert_from_pemder(str(leaf_cert))
    registry = _load_cert_store(leaf_cert, chain_paths)
    ext = signers.ExternalSigner(
        signing_cert=cert,
        cert_registry=registry,
        signature_value=bytes(256),
    )
    with input_pdf.open("rb") as inf:
        writer = IncrementalPdfFileWriter(inf)
        stamp = stamp_options or VisibleStampOptions()
        meta = signers.PdfSignatureMetadata(
            field_name=field_name,
            subfilter=fields.SigSeedSubFilter.PADES,
            md_algorithm="sha256",
            reason=stamp.reason,
        )
        stamp_style = None
        if visible_signature:
            on_page, box = resolve_field_placement(input_pdf, stamp)
            field_spec = fields.SigFieldSpec(
                field_name,
                on_page=on_page,
                box=box,
            )
            stamp_style = build_text_stamp_style(stamp)
        else:
            field_spec = fields.SigFieldSpec(
                field_name,
                invis_sig_settings=fields.InvisSigSettings(box_out_of_bounds=True),
            )
        pdf_signer = signers.PdfSigner(
            meta,
            signer=ext,
            new_field_spec=field_spec,
            stamp_style=stamp_style,
        )
        appearance_text_params = stamp_appearance_text_params(stamp.reason) if visible_signature else None
        prep, tbs, output = await pdf_signer.async_digest_doc_for_signing(
            writer,
            bytes_reserved=bytes_reserved,
            appearance_text_params=appearance_text_params,
        )
    signed_attrs = await ext.signed_attrs(
        prep.document_digest, "sha256", use_pades=True
    )
    der = signed_attrs.dump()
    digest = hashlib.sha256(der).digest()

    signed_attrs_path = work_dir / "signed_attrs.der"
    digest_path = work_dir / "tbs_digest.bin"
    state_path = work_dir / "state.pkl"
    signed_attrs_path.write_bytes(der)
    digest_path.write_bytes(digest)
    state = {
        "version": 1,
        "prep": prep,
        "psi": tbs.post_sign_instructions,
        "pdf": output.getvalue(),
        "field_name": field_name,
        "md_algorithm": "sha256",
    }
    state_path.write_bytes(pickle.dumps(state, protocol=pickle.HIGHEST_PROTOCOL))
    return PrepareResult(
        digest_hex=digest.hex(),
        signed_attrs_path=signed_attrs_path,
        digest_path=digest_path,
        state_path=state_path,
    )


def run_prepare(
    input_pdf: Path,
    leaf_cert: Path,
    work_dir: Path,
    *,
    chain_paths: Sequence[Path] | None = None,
    field_name: str = "LiminalAgentSig",
    bytes_reserved: int = DEFAULT_BYTES_RESERVED,
    visible_signature: bool = False,
    stamp_options: VisibleStampOptions | None = None,
) -> PrepareResult:
    return asyncio.run(
        _prepare_async(
            input_pdf,
            leaf_cert,
            chain_paths or (),
            work_dir,
            field_name,
            bytes_reserved,
            visible_signature=visible_signature,
            stamp_options=stamp_options,
        )
    )
