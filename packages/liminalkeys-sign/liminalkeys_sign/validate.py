"""Mandatory pyHanko validation gate."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from pyhanko.keys import load_cert_from_pemder
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko.sign.validation.status import PdfSignatureStatus, TimestampSignatureStatus
from pyhanko_certvalidator import ValidationContext


@dataclass(frozen=True)
class ValidationOutcome:
    ok: bool
    report: str
    summary: str
    signature_index: int = 0
    warning: str | None = None


def _load_trust_roots(trust_pems: Sequence[Path], tsa_trust_pems: Sequence[Path]) -> list:
    seen: set[bytes] = set()
    roots = []
    for path in (*trust_pems, *tsa_trust_pems):
        cert = load_cert_from_pemder(str(path))
        fp = cert.dump()
        if fp not in seen:
            seen.add(fp)
            roots.append(cert)
    return roots


def _timestamp_trusted(ts: TimestampSignatureStatus | None) -> bool | None:
    if ts is None:
        return None
    return bool(ts.intact and ts.valid and ts.trusted)


def _describe_timestamp(ts: TimestampSignatureStatus | None) -> str:
    if ts is None:
        return "Timestamp: not embedded in signature."
    trusted = _timestamp_trusted(ts)
    parts = [
        "Timestamp: present.",
        f"  Token cryptographically intact: {ts.intact}",
        f"  Token cryptographically valid: {ts.valid}",
        f"  TSA chain trusted (path to anchor): {trusted}",
    ]
    if ts.trust_problem_indic is not None:
        parts.append(f"  TSA trust problem: {ts.trust_problem_indic}")
    if ts.validation_path is None and not ts.trusted:
        parts.append("  TSA path: no path to a trust anchor (PathBuildingError).")
    return "\n".join(parts)


def build_validation_summary(status: PdfSignatureStatus) -> str:
    signer_lines = [
        "=== Signer / document integrity ===",
        f"Document digest intact: {status.intact}",
        f"CMS signature valid: {status.valid}",
        f"Signer certificate trusted (path to --trust anchor): {status.trusted}",
    ]
    if status.trust_problem_indic is not None:
        signer_lines.append(f"Signer trust problem: {status.trust_problem_indic}")
    if status.validation_path is None and not status.trusted:
        signer_lines.append("Signer path: no path to a trust anchor.")

    ts_lines = [
        "=== RFC 3161 timestamp (PAdES B-T) ===",
        _describe_timestamp(status.timestamp_validity),
    ]
    if status.content_timestamp_validity is not None:
        ts_lines.append(_describe_timestamp(status.content_timestamp_validity).replace(
            "Timestamp:", "Content timestamp:", 1
        ))

    overall = (
        "=== Overall (pyHanko bottom_line) ===",
        f"Judgment: {'VALID' if status.bottom_line else 'INVALID'}",
    )
    return "\n".join([*signer_lines, "", *ts_lines, "", *overall])


def _signer_checks_pass(status: PdfSignatureStatus) -> bool:
    return bool(status.intact and status.valid and status.trusted and status.seed_value_ok)


def _pdf_modification_checks_pass(status: PdfSignatureStatus) -> bool:
    return status.docmdp_ok is not False


def _timestamp_trust_checks_pass(status: PdfSignatureStatus) -> bool:
    for ts in (status.timestamp_validity, status.content_timestamp_validity):
        if ts is None:
            continue
        if not (ts.intact and ts.valid and ts.trusted):
            return False
    return True


def _only_timestamp_trust_failure(status: PdfSignatureStatus) -> bool:
    if status.bottom_line:
        return False
    if not _signer_checks_pass(status) or not _pdf_modification_checks_pass(status):
        return False
    if status.timestamp_validity is None and status.content_timestamp_validity is None:
        return False
    return not _timestamp_trust_checks_pass(status)


def resolve_validation_ok(
    status: PdfSignatureStatus,
    *,
    allow_untrusted_timestamp: bool,
) -> tuple[bool, str | None]:
    """
    Match pyHanko pretty-print bottom line; optional warning tier for TSA-only failures.
    """
    if status.bottom_line:
        return True, None
    if allow_untrusted_timestamp and _only_timestamp_trust_failure(status):
        warning = (
            "WARNING: Signer and document checks passed, but the embedded timestamp "
            "TSA chain is not trusted. Re-run with --tsa-trust for the TSA root/intermediate, "
            "or omit --allow-untrusted-timestamp to fail closed."
        )
        return True, warning
    return False, None


def run_validate(
    pdf_path: Path,
    trust_pems: Sequence[Path],
    *,
    tsa_trust_pems: Sequence[Path] | None = None,
    signature_index: int = 0,
    allow_untrusted_timestamp: bool = False,
) -> ValidationOutcome:
    if not trust_pems:
        raise ValueError("At least one --trust PEM is required.")
    roots = _load_trust_roots(trust_pems, tsa_trust_pems or ())
    vc = ValidationContext(trust_roots=roots)
    with pdf_path.open("rb") as inf:
        reader = PdfFileReader(inf)
        if not reader.embedded_signatures:
            report = "No embedded PDF signatures found.\n"
            summary = "=== Overall ===\nJudgment: INVALID (no signatures)\n"
            return ValidationOutcome(ok=False, report=report, summary=summary)
        if signature_index >= len(reader.embedded_signatures):
            report = (
                f"Signature index {signature_index} out of range "
                f"(found {len(reader.embedded_signatures)}).\n"
            )
            summary = "=== Overall ===\nJudgment: INVALID (bad signature index)\n"
            return ValidationOutcome(
                ok=False, report=report, summary=summary, signature_index=signature_index
            )
        sig = reader.embedded_signatures[signature_index]
        status = validate_pdf_signature(sig, vc)
    report = status.pretty_print_details()
    summary = build_validation_summary(status)
    ok, warning = resolve_validation_ok(status, allow_untrusted_timestamp=allow_untrusted_timestamp)
    return ValidationOutcome(
        ok=ok,
        report=report,
        summary=summary,
        signature_index=signature_index,
        warning=warning,
    )
