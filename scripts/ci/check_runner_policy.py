#!/usr/bin/env python3
"""Fail if workflow jobs use non-standard runs-on labels (org self-hosted policy)."""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("::error::PyYAML required (pip install pyyaml)")
    raise SystemExit(2)


def _norm_labels(runs_on: object) -> list[str] | None:
    if runs_on is None:
        return None
    if isinstance(runs_on, str):
        s = runs_on.strip()
        if s.startswith("${{"):
            return None
        return [s]
    if isinstance(runs_on, list):
        return [str(x).strip() for x in runs_on]
    return None


def _allowlist_keys(path: Path) -> set[tuple[str, str]]:
    if not path.is_file():
        return set()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: set[tuple[str, str]] = set()
    for entry in data.get("jobs") or []:
        wf = entry.get("workflow")
        job = entry.get("job")
        if wf and job:
            out.add((str(wf), str(job)))
    return out


def _is_plain_self_hosted(labels: list[str]) -> bool:
    return labels == ["self-hosted"]


def _is_allowlisted_macos(labels: list[str]) -> bool:
    lower = [x.lower() for x in labels]
    return "self-hosted" in lower and "macos" in lower


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    allow_path = root / ".github" / "runner-allowlist.yml"
    allowed = _allowlist_keys(allow_path)
    wf_dir = root / ".github" / "workflows"
    errors: list[str] = []

    for wf_path in sorted(wf_dir.glob("*.yml")) + sorted(wf_dir.glob("*.yaml")):
        doc = yaml.safe_load(wf_path.read_text(encoding="utf-8"))
        if not isinstance(doc, dict):
            continue
        jobs = doc.get("jobs") or {}
        if not isinstance(jobs, dict):
            continue
        wf_name = wf_path.name
        for job_id, job in jobs.items():
            if not isinstance(job, dict):
                continue
            labels = _norm_labels(job.get("runs-on"))
            if labels is None:
                continue
            key = (wf_name, job_id)
            if _is_plain_self_hosted(labels):
                continue
            if key in allowed and _is_allowlisted_macos(labels):
                continue
            errors.append(
                f"{wf_name} job '{job_id}': runs-on={labels!r} "
                f"(want 'self-hosted' or allowlisted [self-hosted, macOS…])"
            )

    if errors:
        print("::error::Runner policy violations:")
        for line in errors:
            print(f"::error::{line}")
        return 1
    print("Runner policy OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())