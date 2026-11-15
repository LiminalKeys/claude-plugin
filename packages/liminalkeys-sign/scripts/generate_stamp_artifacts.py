#!/usr/bin/env python3
"""Sign a sample PDF and export stamp appearance PNGs (180×60, 248×96, signed crop)."""

from __future__ import annotations

import argparse
import datetime
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TESTS = ROOT / "tests"
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from pyhanko.pdf_utils import generic, layout, writer
from pyhanko.pdf_utils.writer import PdfFileWriter
from pyhanko.stamp import TextStampStyle
from pyhanko.stamp.art import STAMP_ART_CONTENT

from liminalkeys_sign.embed import run_embed
from liminalkeys_sign.prepare import run_prepare
from liminalkeys_sign.stamp_layout import format_stamp_datetime
from liminalkeys_sign.validate import run_validate
from liminalkeys_sign.stamp_crop import render_stamp_crop_png
from liminalkeys_sign.visible_stamp import VisibleStampOptions, build_text_stamp_style, resolve_field_placement
from test_sign_flow import _mock_sign_hash

LONG_CN = "Developer ID Application: Example Corp (TEAMID)"
LONG_ISSUER = "José Muñoz Certificación Ibérica SL"
LONG_SERIAL_STR = "5A327F21E483F0AAAF4F767BE932F"
LONG_SERIAL_INT = int(LONG_SERIAL_STR, 16)


def _minimal_pdf(path: Path) -> None:
    w = writer.PdfFileWriter()
    stream = generic.StreamObject(stream_data=b"BT /F1 14 Tf 72 700 Td (Liminal Keys stamp sample) Tj ET")
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


def _ephemeral_signer(work_dir: Path, *, cn: str | None = None, serial: int | None = None):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    cn_val = cn or "Liminal Keys Demo Signer"
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn_val)])
    now = datetime.datetime.now(datetime.timezone.utc)
    serial_num = serial if serial is not None else x509.random_serial_number()
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(serial_num)
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
    leaf = work_dir / "leaf.pem"
    leaf.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return key, leaf, cn_val


def _key_usage(*, ca: bool) -> x509.KeyUsage:
    return x509.KeyUsage(
        digital_signature=True,
        content_commitment=ca,
        key_encipherment=False,
        data_encipherment=False,
        key_agreement=False,
        key_cert_sign=ca,
        crl_sign=False,
        encipher_only=False,
        decipher_only=False,
    )


def _ephemeral_chain(
    work_dir: Path,
    *,
    subject_cn: str,
    issuer_cn: str,
    serial: int,
) -> tuple[rsa.RSAPrivateKey, Path, Path]:
    """Demo CA + leaf for appearance proofs (distinct subject vs issuer CN)."""
    now = datetime.datetime.now(datetime.timezone.utc)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    issuer_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, issuer_cn)])
    subject_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, subject_cn)])
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(issuer_name)
        .issuer_name(issuer_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(_key_usage(ca=True), critical=True)
        .sign(ca_key, hashes.SHA256())
    )
    leaf_cert = (
        x509.CertificateBuilder()
        .subject_name(subject_name)
        .issuer_name(issuer_name)
        .public_key(leaf_key.public_key())
        .serial_number(serial)
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=90))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(_key_usage(ca=False), critical=True)
        .sign(ca_key, hashes.SHA256())
    )
    ca_path = work_dir / "issuer-ca.pem"
    leaf_path = work_dir / "leaf-longcn.pem"
    ca_path.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
    leaf_path.write_bytes(leaf_cert.public_bytes(serialization.Encoding.PEM))
    return leaf_key, leaf_path, ca_path


def _sign_visible_pdf(
    *,
    input_pdf: Path,
    work_root: Path,
    tag: str,
    out_pdf: Path,
    crop_png: Path,
    stamp_options: VisibleStampOptions,
    signing_key: rsa.RSAPrivateKey,
    leaf_pem: Path,
    chain_pem: Path,
) -> bool:
    work = work_root / f"sign-{tag}"
    prep = run_prepare(
        input_pdf,
        leaf_pem,
        work,
        visible_signature=True,
        stamp_options=stamp_options,
        chain_paths=[chain_pem],
    )
    sig = _mock_sign_hash(signing_key, prep.digest_path)
    sig_path = work / "signature.bin"
    sig_path.write_bytes(sig)
    run_embed(
        work,
        leaf_pem,
        sig_path,
        out_pdf,
        signed_attrs_path=prep.signed_attrs_path,
        digest_path=prep.digest_path,
    )
    trust = [leaf_pem, chain_pem]
    outcome = run_validate(out_pdf, trust)
    if not outcome.ok:
        print(f"validate failed ({tag})", outcome.summary, file=sys.stderr)
        return False
    _, box = resolve_field_placement(input_pdf, stamp_options)
    render_stamp_crop_png(out_pdf, crop_png, fallback_box=box)
    return True


def _render_lk_stamp_png(
    style,
    out_png: Path,
    *,
    width: float,
    height: float,
    signer: str,
    reason: str | None,
    issuer: str,
    serial: str,
) -> None:
    import fitz

    w = PdfFileWriter()
    box = layout.BoxConstraints(width=width, height=height)
    now = datetime.datetime.now(datetime.timezone.utc)
    params = {
        "signer": signer,
        "date_display": format_stamp_datetime(
            now, style.locale, timezone_name=style.timezone
        ),
        "cert_issuer": issuer,
        "cert_serial": serial,
    }
    if reason:
        params["reason"] = reason
    stamp = style.create_stamp(w, box, params)
    ref = stamp.register()
    xname = generic.pdf_name("/StampFm")
    resources = generic.DictionaryObject(
        {generic.pdf_name("/XObject"): generic.DictionaryObject({xname: ref})}
    )
    paint = generic.StreamObject(stream_data=f"q 1 0 0 1 0 0 cm {xname} Do Q".encode("ascii"))
    page = writer.PageObject(
        contents=w.add_object(paint),
        media_box=[0, 0, box.width, box.height],
        resources=resources,
    )
    w.insert_page(page)
    buf = io.BytesIO()
    w.write(buf)
    doc = fitz.open(stream=buf.getvalue(), filetype="pdf")
    pix = doc[0].get_pixmap(matrix=fitz.Matrix(4, 4), alpha=False)
    pix.save(str(out_png))
    doc.close()


def _render_before_png(out_png: Path, signer: str, reason: str) -> None:
    import fitz

    style = TextStampStyle(
        stamp_text="%(signer)s\n%(ts)s\n%(reason)s",
        background=STAMP_ART_CONTENT,
        background_opacity=0.6,
    )
    w = PdfFileWriter()
    box = layout.BoxConstraints(width=180, height=60)
    stamp = style.create_stamp(w, box, {"signer": signer, "reason": reason, "ts": "2026-11-13 19:10"})
    ref = stamp.register()
    xname = generic.pdf_name("/StampFm")
    resources = generic.DictionaryObject(
        {generic.pdf_name("/XObject"): generic.DictionaryObject({xname: ref})}
    )
    paint = generic.StreamObject(stream_data=f"q 1 0 0 1 0 0 cm {xname} Do Q".encode("ascii"))
    page = writer.PageObject(
        contents=w.add_object(paint),
        media_box=[0, 0, 180, 60],
        resources=resources,
    )
    w.insert_page(page)
    buf = io.BytesIO()
    w.write(buf)
    doc = fitz.open(stream=buf.getvalue(), filetype="pdf")
    doc[0].get_pixmap(matrix=fitz.Matrix(4, 4)).save(str(out_png))
    doc.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    work = args.out_dir / "work"
    work.mkdir(exist_ok=True)

    input_pdf = work / "input.pdf"
    _minimal_pdf(input_pdf)
    key, leaf, _ = _ephemeral_signer(work)

    opts = VisibleStampOptions(
        page="first",
        anchor="bottom-left",
        margin_pt=48.0,
        reason="Demo approval",
        locale="en-GB",
        timezone="Europe/Madrid",
    )
    _, box = resolve_field_placement(input_pdf, opts)
    after_style = build_text_stamp_style(opts)
    demo = {
        "signer": "Jane Doe",
        "reason": "Demo approval",
        "issuer": "Liminal Keys Demo Signer",
        "serial": "5A327F21E483F0AAAF4F767BE932F",
    }

    _render_before_png(args.out_dir / "stamp-appearance-before.png", demo["signer"], demo["reason"])
    _render_lk_stamp_png(
        after_style,
        args.out_dir / "stamp-appearance-after-180x60.png",
        width=180,
        height=60,
        **demo,
    )
    _render_lk_stamp_png(
        after_style,
        args.out_dir / "stamp-appearance-after-248x96.png",
        width=248,
        height=96,
        **demo,
    )

    long_style = build_text_stamp_style(VisibleStampOptions(locale="en-US"))
    long_demo = {
        "signer": LONG_CN,
        "reason": None,
        "issuer": LONG_ISSUER,
        "serial": LONG_SERIAL_STR,
    }
    _render_lk_stamp_png(
        long_style,
        args.out_dir / "stamp-appearance-long-cn-180x60.png",
        width=180,
        height=60,
        **long_demo,
    )
    _render_lk_stamp_png(
        long_style,
        args.out_dir / "stamp-appearance-long-cn-248x96.png",
        width=248,
        height=96,
        **long_demo,
    )

    import shutil

    shutil.copy(
        args.out_dir / "stamp-appearance-after-248x96.png",
        args.out_dir / "stamp-appearance-after.png",
    )

    branded_work = work / "branded"
    prep = run_prepare(
        input_pdf,
        leaf,
        branded_work,
        visible_signature=True,
        stamp_options=opts,
    )
    sig = _mock_sign_hash(key, prep.digest_path)
    sig_path = branded_work / "signature.bin"
    sig_path.write_bytes(sig)
    signed = args.out_dir / "sample-signed-visible.pdf"
    run_embed(
        branded_work,
        leaf,
        sig_path,
        signed,
        signed_attrs_path=prep.signed_attrs_path,
        digest_path=prep.digest_path,
    )
    outcome = run_validate(signed, [leaf])
    if not outcome.ok:
        print("validate failed", outcome.summary, file=sys.stderr)
        return 1
    render_stamp_crop_png(
        signed,
        args.out_dir / "stamp-from-signed-pdf.png",
        fallback_box=box,
    )

    long_key, long_leaf, long_ca = _ephemeral_chain(
        work,
        subject_cn=LONG_CN,
        issuer_cn=LONG_ISSUER,
        serial=LONG_SERIAL_INT,
    )
    long_stamp_gb = VisibleStampOptions(
        page="first",
        anchor="bottom-left",
        margin_pt=48.0,
        width_pt=248.0,
        height_pt=96.0,
        locale="en-GB",
        timezone="Europe/Madrid",
    )
    long_stamp_gb_reason = VisibleStampOptions(
        page="first",
        anchor="bottom-left",
        margin_pt=48.0,
        width_pt=248.0,
        height_pt=96.0,
        locale="en-GB",
        timezone="Europe/Madrid",
        reason="UX proof approval",
    )
    long_stamp_180 = VisibleStampOptions(
        page="first",
        anchor="bottom-left",
        margin_pt=48.0,
        width_pt=180.0,
        height_pt=60.0,
        locale="en-GB",
        timezone="Europe/Madrid",
    )
    if not _sign_visible_pdf(
        input_pdf=input_pdf,
        work_root=work,
        tag="longcn-248x96",
        out_pdf=args.out_dir / "long-cn-signed-248x96.pdf",
        crop_png=args.out_dir / "stamp-proof-signed-long-cn-248x96.png",
        stamp_options=long_stamp_gb,
        signing_key=long_key,
        leaf_pem=long_leaf,
        chain_pem=long_ca,
    ):
        return 1
    if not _sign_visible_pdf(
        input_pdf=input_pdf,
        work_root=work,
        tag="longcn-248x96-reason",
        out_pdf=args.out_dir / "long-cn-signed-248x96-reason.pdf",
        crop_png=args.out_dir / "stamp-proof-signed-long-cn-248x96-reason.png",
        stamp_options=long_stamp_gb_reason,
        signing_key=long_key,
        leaf_pem=long_leaf,
        chain_pem=long_ca,
    ):
        return 1
    if not _sign_visible_pdf(
        input_pdf=input_pdf,
        work_root=work,
        tag="longcn-180x60",
        out_pdf=args.out_dir / "long-cn-signed-180x60.pdf",
        crop_png=args.out_dir / "stamp-proof-signed-long-cn-180x60.png",
        stamp_options=long_stamp_180,
        signing_key=long_key,
        leaf_pem=long_leaf,
        chain_pem=long_ca,
    ):
        return 1

    print(f"signed_pdf={signed}")
    print(f"long_cn_248={args.out_dir / 'long-cn-signed-248x96.pdf'}")
    print(f"long_cn_180={args.out_dir / 'long-cn-signed-180x60.pdf'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
