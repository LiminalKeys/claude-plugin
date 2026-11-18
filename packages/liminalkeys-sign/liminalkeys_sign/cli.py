"""Command-line interface for liminalkeys-sign."""

from __future__ import annotations

import argparse
import base64
import sys
import tempfile
from pathlib import Path

from liminalkeys_sign import __version__
from liminalkeys_sign.embed import run_embed
from liminalkeys_sign.mcp_embed import (
    resolve_signature_from_mcp,
    verify_identity_chain_from_mcp,
)
from liminalkeys_sign.mcp_trust import McpTrustError, load_envelope_json, verify_signed_mcp_envelope
from liminalkeys_sign.mcp_trust import McpTrustConfig
from liminalkeys_sign.approval_preview import approval_preview_base64, write_approval_preview_png
from liminalkeys_sign.pem_chain import split_pem_chain_file
from liminalkeys_sign.pdf_preview import build_sign_hash_previews
from liminalkeys_sign.prepare import DEFAULT_BYTES_RESERVED, run_prepare
from liminalkeys_sign.sign_state import write_sign_state
from liminalkeys_sign.visible_stamp import VisibleStampOptions, normalize_anchor
from liminalkeys_sign.stamp_branding_guard import (
    BrandedStampError,
    assert_branded_visible_stamp,
)
from liminalkeys_sign.validate import run_validate
from liminalkeys_sign.verify import SignatureVerificationError


def _path_arg(value: str) -> Path:
    return Path(value).expanduser()


def _cmd_approval_preview(args: argparse.Namespace) -> int:
    if args.output:
        write_approval_preview_png(
            args.output,
            digest_hex=args.digest_hex,
            document_label=args.document_label,
        )
        print(args.output, file=sys.stderr)
        return 0
    print(approval_preview_base64(digest_hex=args.digest_hex, document_label=args.document_label))
    return 0


def _stamp_visible(args: argparse.Namespace) -> bool:
    if getattr(args, "invisible_signature", False):
        return False
    return True


def _stamp_options_from_args(args: argparse.Namespace) -> VisibleStampOptions:
    return VisibleStampOptions(
        page=args.stamp_page,
        anchor=normalize_anchor(args.stamp_anchor),
        margin_pt=args.stamp_margin,
        reason=(args.stamp_reason or args.document_label),
        logo_path=args.stamp_logo,
        locale=args.stamp_locale,
        timezone=getattr(args, "stamp_timezone", None),
    )


def _resolve_prepare_paths(args: argparse.Namespace) -> tuple[Path, Path, Path, list[Path]]:
    input_pdf = args.pdf or args.input_pdf
    if input_pdf is None:
        raise ValueError("prepare requires the PDF path (positional or --pdf)")
    if args.cert_chain:
        if args.cert is not None:
            raise ValueError("prepare: use --cert-chain or --cert, not both")
        base_work = args.work_dir or (args.out.parent / ".lk-work" if args.out else None)
        if base_work is None:
            raise ValueError("prepare with --cert-chain requires --work-dir or --out state.json")
        chain_files = split_pem_chain_file(args.cert_chain, base_work)
        work_dir = args.work_dir or chain_files.work_dir
        chain_paths = list(chain_files.intermediates) + list(args.chain or [])
        return input_pdf, chain_files.leaf, work_dir, chain_paths
    if args.cert is None or args.work_dir is None:
        raise ValueError("prepare requires --cert and --work-dir (or --cert-chain with --out)")
    return input_pdf, args.cert, args.work_dir, list(args.chain or [])


def _cmd_prepare(args: argparse.Namespace) -> int:
    visible = _stamp_visible(args)
    stamp_opts = _stamp_options_from_args(args) if visible else None
    if args.stamp_reason and not visible:
        print("prepare: --stamp-reason requires a visible stamp (omit --invisible-signature)", file=sys.stderr)
        return 2
    if args.stamp_logo and not visible:
        print("prepare: --stamp-logo requires a visible stamp (omit --invisible-signature)", file=sys.stderr)
        return 2
    try:
        input_pdf, leaf_cert, work_dir, chain_paths = _resolve_prepare_paths(args)
        result = run_prepare(
            input_pdf,
            leaf_cert,
            work_dir,
            chain_paths=chain_paths,
            field_name=args.field_name,
            bytes_reserved=args.bytes_reserved,
            visible_signature=visible,
            stamp_options=stamp_opts,
        )
    except ValueError as exc:
        print(f"prepare failed: {exc}", file=sys.stderr)
        return 2
    if visible:
        import pickle

        try:
            prepared = pickle.loads(result.state_path.read_bytes())
            assert_branded_visible_stamp(
                prepared["pdf"],
                context="prepare (prepared PDF appearance)",
            )
        except BrandedStampError as exc:
            print(f"prepare failed: {exc}", file=sys.stderr)
            return 2
    print(result.digest_hex)
    if args.out:
        previews = build_sign_hash_previews(
            pdf=input_pdf,
            digest_hex=result.digest_hex,
            document_label=args.document_label,
        )
        preview_path = work_dir / "approval_preview.bin"
        preview_path.write_bytes(base64.standard_b64decode(previews[0]["content_base64"]))
        write_sign_state(
            args.out,
            digest_hex=result.digest_hex,
            digest_path=result.digest_path,
            work_dir=work_dir,
            leaf_cert=leaf_cert,
            chain_paths=chain_paths,
            previews=previews,
            signed_attrs_path=result.signed_attrs_path,
            state_pkl_path=result.state_path,
            package_version=__version__,
            document_label=args.document_label,
            approval_preview_path=preview_path,
            visible_signature=visible,
        )
        print(str(args.out), file=sys.stderr)
    print(
        f"signed_attrs: {result.signed_attrs_path}",
        f"digest: {result.digest_path}",
        f"state: {result.state_path}",
        sep="\n",
        file=sys.stderr,
    )
    return 0


def _cmd_finish(args: argparse.Namespace) -> int:
    from liminalkeys_sign.sign_state import SignState

    try:
        state = SignState.from_path(args.state)
    except (OSError, ValueError, TypeError) as exc:
        print(f"finish failed: invalid --state ({exc})", file=sys.stderr)
        return 2
    work_dir = Path(state.work_dir)
    leaf_cert = Path(state.leaf_cert_path)
    output_pdf = args.output
    chain_paths = [Path(p) for p in state.chain_pem_paths]
    host = args.mcp_host or "mcp.liminalkeys.com"
    embed_args = argparse.Namespace(
        work_dir=work_dir,
        cert=leaf_cert,
        signature=args.signature,
        mcp_sign_envelope=args.mcp_sign_envelope,
        mcp_chain_envelope=args.mcp_chain_envelope,
        expected_nonce=args.expected_nonce,
        chain_nonce=args.chain_nonce,
        mcp_host=host,
        mcp_trust_config=args.mcp_trust_config,
        chain_trust=args.chain_trust,
        trust=args.trust,
        output=output_pdf,
        chain=chain_paths if chain_paths else args.chain or [],
        signed_attrs=Path(state.paths["signed_attrs"]) if state.paths.get("signed_attrs") else None,
        timestamp_response=args.timestamp_response,
        digest=Path(state.paths["tbs_digest"]) if state.paths.get("tbs_digest") else None,
    )
    code = _cmd_embed(embed_args)
    if code != 0:
        return code
    if state.visible_signature:
        try:
            assert_branded_visible_stamp(
                output_pdf.read_bytes(),
                context="finish (signed PDF)",
            )
        except BrandedStampError as exc:
            print(f"finish failed: {exc}", file=sys.stderr)
            return 2
    report_path = args.report or output_pdf.with_suffix(".validation.txt")
    trust = args.trust or [leaf_cert]
    validate_args = argparse.Namespace(
        input_pdf=output_pdf,
        trust=trust,
        tsa_trust=args.tsa_trust or [],
        allow_untrusted_timestamp=args.allow_untrusted_timestamp,
        report=report_path,
        signature_index=args.signature_index,
    )
    return _cmd_validate(validate_args)


def _cmd_embed(args: argparse.Namespace) -> int:
    try:
        if not args.signature and not args.mcp_sign_envelope:
            print("embed requires --signature or --mcp-sign-envelope", file=sys.stderr)
            return 2
        signature_path = args.signature
        if args.mcp_sign_envelope:
            if not args.expected_nonce or not args.mcp_host:
                print(
                    "embed with --mcp-sign-envelope requires --expected-nonce and --mcp-host "
                    "(--mcp-trust-config optional; defaults to bundled production trust + JWKS bootstrap)",
                    file=sys.stderr,
                )
                return 2
            sig_bytes = resolve_signature_from_mcp(
                sign_envelope_path=args.mcp_sign_envelope,
                expected_tool="sign_hash",
                expected_nonce=args.expected_nonce,
                mcp_host=args.mcp_host,
                trust_config=args.mcp_trust_config,
            )
            if args.mcp_chain_envelope:
                verify_identity_chain_from_mcp(
                    chain_envelope_path=args.mcp_chain_envelope,
                    expected_nonce=args.chain_nonce or args.expected_nonce,
                    mcp_host=args.mcp_host,
                    trust_config=args.mcp_trust_config,
                    trust_anchors=args.chain_trust or args.trust or [],
                    leaf_cert=args.cert,
                    chain_pem_paths=args.chain or [],
                )
            tmp = Path(tempfile.gettempdir()) / f"lk-mcp-sig-{args.work_dir.name}.bin"
            tmp.write_bytes(sig_bytes)
            signature_path = tmp
        run_embed(
            args.work_dir,
            args.cert,
            signature_path,
            args.output,
            chain_paths=args.chain or [],
            signed_attrs_path=args.signed_attrs,
            timestamp_response=args.timestamp_response,
            digest_path=args.digest,
        )
    except (SignatureVerificationError, McpTrustError) as exc:
        print(f"embed failed: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"embed failed: {exc}", file=sys.stderr)
        return 2
    return 0


def _cmd_mcp_verify(args: argparse.Namespace) -> int:
    try:
        trust = McpTrustConfig.load_optional(args.mcp_trust_config)
        envelope = load_envelope_json(args.envelope)
        payload = verify_signed_mcp_envelope(
            envelope,
            expected_tool=args.tool,
            expected_nonce=args.expected_nonce,
            mcp_host=args.mcp_host,
            trust=trust,
            envelope_label=f"{args.tool} MCP envelope",
        )
        if args.output:
            import json

            args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print("MCP RESPONSE VERIFIED", file=sys.stderr)
        return 0
    except McpTrustError as exc:
        print(f"mcp-verify failed: {exc}", file=sys.stderr)
        return 2


def _cmd_validate(args: argparse.Namespace) -> int:
    outcome = run_validate(
        args.input_pdf,
        args.trust,
        tsa_trust_pems=args.tsa_trust or [],
        signature_index=args.signature_index,
        allow_untrusted_timestamp=args.allow_untrusted_timestamp,
    )
    if args.report:
        args.report.write_text(outcome.report, encoding="utf-8")
    print(outcome.report)
    print(outcome.summary, file=sys.stderr)
    if outcome.warning:
        print(outcome.warning, file=sys.stderr)
    if outcome.ok:
        if outcome.warning:
            print("VALIDATION PASSED (timestamp trust warning)", file=sys.stderr)
        else:
            print("VALIDATION PASSED", file=sys.stderr)
        return 0
    print("VALIDATION FAILED", file=sys.stderr)
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="liminalkeys-sign",
        description="PAdES helper for Liminal Keys AI agent signing (hash-only, pyHanko).",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    sub = parser.add_subparsers(dest="command", required=True)

    p_prepare = sub.add_parser(
        "prepare",
        help="Hash CMS signed attributes, optional approval preview, and sign_hash state.json",
    )
    p_prepare.add_argument("input_pdf", type=_path_arg, nargs="?", default=None, help="PDF to sign")
    p_prepare.add_argument("--pdf", type=_path_arg, default=None, help="PDF to sign (alias for positional)")
    p_prepare.add_argument("--cert", type=_path_arg, default=None, help="Leaf signing certificate (PEM)")
    p_prepare.add_argument(
        "--cert-chain",
        type=_path_arg,
        default=None,
        help="Full PEM chain (leaf first); writes leaf.pem under work dir",
    )
    p_prepare.add_argument(
        "--out",
        type=_path_arg,
        default=None,
        metavar="STATE.json",
        help="Write sign_hash-ready JSON (digest_base64, previews, paths)",
    )
    p_prepare.add_argument(
        "--document-label",
        default=None,
        help="Optional label stored in state.json and used for preview shading",
    )
    p_prepare.add_argument(
        "--work-dir",
        type=_path_arg,
        default=None,
        help="Directory for signed_attrs.der, tbs_digest.bin, state.pkl (default: parent of --out/.lk-work)",
    )
    p_prepare.add_argument(
        "--chain",
        type=_path_arg,
        nargs="*",
        default=[],
        help="Additional chain certificates (PEM)",
    )
    p_prepare.add_argument("--field-name", default="LiminalAgentSig")
    p_prepare.add_argument(
        "--invisible-signature",
        action="store_true",
        help="Omit visible stamp (default: branded Liminal Keys stamp, last page bottom-right)",
    )
    p_prepare.add_argument(
        "--visible-signature",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    p_prepare.add_argument(
        "--stamp-page",
        default="last",
        metavar="SPEC",
        help='Page for the stamp: first, last, or 1-based page number (default: last)',
    )
    p_prepare.add_argument(
        "--stamp-anchor",
        default="bottom-right",
        help="Corner anchor: bottom-right, bottom-left, top-right, top-left (default: bottom-right)",
    )
    p_prepare.add_argument(
        "--stamp-margin",
        type=float,
        default=36.0,
        metavar="PT",
        help="Inset from the page MediaBox edge in PDF points (default: 36)",
    )
    p_prepare.add_argument(
        "--stamp-reason",
        default=None,
        metavar="TEXT",
        help="Optional reason line on the visible stamp (name, date, reason block)",
    )
    p_prepare.add_argument(
        "--stamp-logo",
        type=_path_arg,
        default=None,
        metavar="PATH",
        help="Optional logo image (PNG/JPEG) rendered on the stamp background",
    )
    p_prepare.add_argument(
        "--stamp-locale",
        default="en-US",
        metavar="BCP47",
        help="BCP47 locale for stamp date formatting (default: en-US)",
    )
    p_prepare.add_argument(
        "--stamp-timezone",
        default=None,
        metavar="IANA",
        help="IANA timezone for stamp date (e.g. Europe/Madrid); default: system local",
    )
    p_prepare.add_argument(
        "--bytes-reserved",
        type=int,
        default=DEFAULT_BYTES_RESERVED,
        help=(
            "CMS signature placeholder size in the prepared PDF "
            f"(default {DEFAULT_BYTES_RESERVED} for PAdES B-T + typical TSA token; override if needed)"
        ),
    )
    p_prepare.set_defaults(func=_cmd_prepare)

    p_preview = sub.add_parser(
        "approval-preview",
        help="Write a small PNG for sign_hash previews (agent-rendered, unverified)",
    )
    p_preview.add_argument(
        "--output",
        type=_path_arg,
        help="PNG path (default: stdout base64 when omitted)",
    )
    p_preview.add_argument("--digest-hex", default=None, help="TBS digest hex from prepare stdout")
    p_preview.add_argument("--document-label", default=None, help="Optional label for shade variation")
    p_preview.set_defaults(func=_cmd_approval_preview)

    p_embed = sub.add_parser("embed", help="Verify signature and embed CMS (+ optional timestamp)")
    p_embed.add_argument("--work-dir", type=_path_arg, required=True)
    p_embed.add_argument("--cert", type=_path_arg, required=True)
    p_embed.add_argument("--signature", type=_path_arg, required=False)
    p_embed.add_argument(
        "--mcp-sign-envelope",
        type=_path_arg,
        default=None,
        help="Signed MCP sign_hash JSON envelope (mutual auth)",
    )
    p_embed.add_argument("--mcp-chain-envelope", type=_path_arg, default=None)
    p_embed.add_argument("--expected-nonce", default=None)
    p_embed.add_argument("--chain-nonce", default=None)
    p_embed.add_argument(
        "--mcp-host",
        default=None,
        help="HTTPS MCP host (must match trust config allow list)",
    )
    p_embed.add_argument(
        "--mcp-trust-config",
        type=_path_arg,
        default=None,
        help=(
            "JSON trust pins (allowed_hosts + optional keys by kid). "
            "Omit to use bundled production config (host allow list + JWKS from pinned host)."
        ),
    )
    p_embed.add_argument(
        "--chain-trust",
        type=_path_arg,
        nargs="*",
        default=None,
        help="Trust anchor PEMs for chain anchoring with MCP chain envelope",
    )
    p_embed.add_argument(
        "--trust",
        type=_path_arg,
        nargs="*",
        default=None,
        help="Fallback trust anchors when --chain-trust omitted",
    )
    p_embed.add_argument("--output", type=_path_arg, required=True)
    p_embed.add_argument("--chain", type=_path_arg, nargs="*", default=[])
    p_embed.add_argument("--signed-attrs", type=_path_arg, default=None)
    p_embed.add_argument(
        "--timestamp-response",
        type=_path_arg,
        default=None,
        help="DER RFC 3161 TimeStampResp from MCP timestamp tool (PAdES B-T)",
    )
    p_embed.add_argument("--digest", type=_path_arg, default=None)
    p_embed.set_defaults(func=_cmd_embed)

    p_mcp = sub.add_parser("mcp-verify", help="Verify a signed MCP tool response envelope")
    p_mcp.add_argument("--envelope", type=_path_arg, required=True)
    p_mcp.add_argument("--tool", required=True, choices=["sign_hash", "get_certificate_chain", "timestamp"])
    p_mcp.add_argument("--expected-nonce", required=True)
    p_mcp.add_argument("--mcp-host", required=True)
    p_mcp.add_argument(
        "--mcp-trust-config",
        type=_path_arg,
        default=None,
        help="Trust JSON path (default: bundled production config + JWKS bootstrap)",
    )
    p_mcp.add_argument("--output", type=_path_arg, default=None)
    p_mcp.set_defaults(func=_cmd_mcp_verify)

    p_validate = sub.add_parser("validate", help="Mandatory pyHanko validation gate")
    p_validate.add_argument("input_pdf", type=_path_arg)
    p_validate.add_argument(
        "--trust",
        type=_path_arg,
        nargs="+",
        required=True,
        help="Trust anchor PEM(s) for the signer certificate chain (typically leaf or tenant CA)",
    )
    p_validate.add_argument(
        "--tsa-trust",
        type=_path_arg,
        nargs="*",
        default=None,
        help=(
            "Additional trust anchor PEM(s) for RFC 3161 timestamp (TSA) path building. "
            "Required for PAdES B-T when the TSA root (e.g. FreeTSA) is not the same as --trust."
        ),
    )
    p_validate.add_argument(
        "--allow-untrusted-timestamp",
        action="store_true",
        help=(
            "Warning tier: exit 0 when signer/document checks pass but only TSA trust failed. "
            "Default is fail-closed (matches pyHanko INVALID bottom line)."
        ),
    )
    p_validate.add_argument("--report", type=_path_arg, default=None)
    p_validate.add_argument("--signature-index", type=int, default=0)
    p_validate.set_defaults(func=_cmd_validate)

    p_finish = sub.add_parser("finish", help="embed + validate in one step (after sign_hash)")
    p_finish.add_argument("--state", type=_path_arg, required=True, help="state.json from prepare --out")
    p_finish.add_argument("--mcp-sign-envelope", type=_path_arg, required=True)
    p_finish.add_argument("--expected-nonce", required=True)
    p_finish.add_argument("--mcp-host", default="mcp.liminalkeys.com")
    p_finish.add_argument("--mcp-trust-config", type=_path_arg, default=None)
    p_finish.add_argument("--mcp-chain-envelope", type=_path_arg, default=None)
    p_finish.add_argument("--chain-nonce", default=None)
    p_finish.add_argument("--chain-trust", type=_path_arg, nargs="*", default=None)
    p_finish.add_argument("--trust", type=_path_arg, nargs="*", default=None)
    p_finish.add_argument("--signature", type=_path_arg, default=None)
    p_finish.add_argument("--chain", type=_path_arg, nargs="*", default=[])
    p_finish.add_argument("--timestamp-response", type=_path_arg, default=None)
    p_finish.add_argument("--output", type=_path_arg, required=True, metavar="SIGNED.pdf")
    p_finish.add_argument(
        "--report",
        type=_path_arg,
        default=None,
        help="Validation report path (default: <signed>.validation.txt)",
    )
    p_finish.add_argument("--tsa-trust", type=_path_arg, nargs="*", default=None)
    p_finish.add_argument("--allow-untrusted-timestamp", action="store_true")
    p_finish.add_argument("--signature-index", type=int, default=0)
    p_finish.set_defaults(func=_cmd_finish)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    code = args.func(args)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
