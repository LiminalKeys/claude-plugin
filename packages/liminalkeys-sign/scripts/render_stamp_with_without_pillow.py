#!/usr/bin/env python3
"""Export stamp-from-signed-pdf PNGs with and without Pillow available."""

from __future__ import annotations

import builtins
import datetime
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TESTS = ROOT / "tests"
sys.path.insert(0, str(TESTS))

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from liminalkeys_sign.embed import run_embed
from liminalkeys_sign.prepare import run_prepare
from liminalkeys_sign.stamp_crop import render_stamp_crop_png
from liminalkeys_sign.validate import run_validate
from liminalkeys_sign.visible_stamp import VisibleStampOptions, resolve_field_placement
from pyhanko.pdf_utils import generic, writer
from pyhanko.pdf_utils.writer import PdfFileWriter

from test_sign_flow import _mock_sign_hash


def _minimal_pdf(path: Path) -> None:
    w = PdfFileWriter()
    stream = generic.StreamObject(stream_data=b"BT /F1 14 Tf 72 700 Td (Stamp proof) Tj ET")
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
    with path.open("wb") as outf:
        w.write(outf)


def _ephemeral_signer(work_dir: Path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Liminal Keys Demo Signer")])
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
        .sign(key, hashes.SHA256())
    )
    leaf = work_dir / "leaf.pem"
    leaf.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return key, leaf


def _sign_and_crop(
    *,
    out_dir: Path,
    tag: str,
    block_pillow: bool,
) -> Path:
    real_import = builtins.__import__
    if block_pillow:

        def _guard(name, *args, **kwargs):
            if name == "PIL" or (isinstance(name, str) and name.startswith("PIL.")):
                raise ImportError("PIL blocked")
            return real_import(name, *args, **kwargs)

        builtins.__import__ = _guard

    try:
        work = out_dir / f"work-{tag}"
        work.mkdir(parents=True, exist_ok=True)
        pdf_in = work / "input.pdf"
        _minimal_pdf(pdf_in)
        key, leaf = _ephemeral_signer(work)
        opts = VisibleStampOptions(
            page="last",
            anchor="bottom-right",
            margin_pt=36.0,
            locale="en-GB",
            timezone="Europe/Madrid",
            reason="Artifact proof",
        )
        prep = run_prepare(pdf_in, leaf, work, visible_signature=True, stamp_options=opts)
        sig = _mock_sign_hash(key, prep.digest_path)
        sig_path = work / "signature.bin"
        sig_path.write_bytes(sig)
        signed = out_dir / f"sample-signed-{tag}.pdf"
        run_embed(
            work,
            leaf,
            sig_path,
            signed,
            signed_attrs_path=prep.signed_attrs_path,
            digest_path=prep.digest_path,
        )
        outcome = run_validate(signed, [leaf])
        if not outcome.ok:
            raise RuntimeError(outcome.summary)
        _, box = resolve_field_placement(pdf_in, opts)
        png = out_dir / f"stamp-from-signed-pdf-{tag}.png"
        render_stamp_crop_png(signed, png, fallback_box=box)
        return png
    finally:
        if block_pillow:
            builtins.__import__ = real_import


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/opt/cursor/artifacts/pdf-stamp-branding")
    out.mkdir(parents=True, exist_ok=True)
    with_pillow = _sign_and_crop(out_dir=out, tag="with-pillow", block_pillow=False)
    no_pillow = _sign_and_crop(out_dir=out, tag="without-pillow", block_pillow=True)
    print(f"with_pillow={with_pillow}")
    print(f"without_pillow={no_pillow}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())