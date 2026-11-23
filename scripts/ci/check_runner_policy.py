#!/usr/bin/env python3
"""Fail if workflow jobs use non-standard runs-on labels (org self-hosted policy)."""
from __future__ import annotations

import re
from pathlib import Path


GITHUB_HOSTED_LABELS = frozenset(
    {
        "ubuntu-latest",
        "ubuntu-24.04",
        "ubuntu-22.04",
        "ubuntu-20.04",
        "macos-latest",
        "macos-14",
        "macos-13",
        "windows-latest",
        "windows-2022",
    }
)


def _load_policy(path: Path) -> tuple[set[tuple[str, str]], bool]:
    if not path.is_file():
        return set(), False
    wf = job = None
    out: set[tuple[str, str]] = set()
    allow_github = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if re.match(r"^allow_github_hosted:\s*true\s*$", line, re.IGNORECASE):
            allow_github = True
            continue
        if m := re.match(r"^\s+-\s+workflow:\s*(\S+)\s*$", line):
            wf = m.group(1)
        elif m := re.match(r"^\s+workflow:\s*(\S+)\s*$", line):
            wf = m.group(1)
        elif m := re.match(r"^\s+job:\s*(\S+)\s*$", line):
            job = m.group(1)
        if wf and job:
            out.add((wf, job))
            wf = job = None
    return out, allow_github


def _is_github_hosted(labels: list[str]) -> bool:
    return len(labels) == 1 and labels[0] in GITHUB_HOSTED_LABELS


def _parse_runs_on_block(lines: list[str], start: int) -> tuple[object, int]:
    line = lines[start]
    if m := re.match(r"^\s+runs-on:\s*(.+)\s*$", line):
        rest = m.group(1).strip()
        if rest.startswith("${{"):
            return None, start + 1
        if rest.startswith("["):
            inner = rest.strip("[]")
            parts = [p.strip().strip("'\"") for p in inner.split(",") if p.strip()]
            return parts, start + 1
        return [rest.strip("'\"")], start + 1
    if re.match(r"^\s+runs-on:\s*$", line):
        labels: list[str] = []
        i = start + 1
        while i < len(lines):
            if m := re.match(r"^\s+-\s+(.+)\s*$", lines[i]):
                labels.append(m.group(1).strip().strip("'\""))
                i += 1
                continue
            break
        return labels, i
    return None, start + 1


def _workflow_jobs(path: Path) -> list[tuple[str, object]]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    jobs_start = None
    for i, line in enumerate(lines):
        if re.match(r"^jobs:\s*$", line):
            jobs_start = i + 1
            break
    if jobs_start is None:
        return []
    results: list[tuple[str, object]] = []
    i = jobs_start
    current_job: str | None = None
    while i < len(lines):
        line = lines[i]
        if re.match(r"^[A-Za-z]", line) and not line.startswith(" "):
            break
        if m := re.match(r"^  ([\w][\w-]*):\s*$", line):
            current_job = m.group(1)
            i += 1
            continue
        if current_job and re.match(r"^\s+runs-on:", line):
            runs_on, i = _parse_runs_on_block(lines, i)
            if runs_on is not None:
                results.append((current_job, runs_on))
            continue
        i += 1
    return results


def _norm_labels(runs_on: object) -> list[str] | None:
    if isinstance(runs_on, list):
        return [str(x).strip() for x in runs_on]
    if isinstance(runs_on, str):
        return [runs_on.strip()]
    return None


def _is_plain_self_hosted(labels: list[str]) -> bool:
    return labels == ["self-hosted"]


def _is_allowlisted_macos(labels: list[str]) -> bool:
    lower = [x.lower() for x in labels]
    return "self-hosted" in lower and "macos" in lower


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    allowed, allow_github = _load_policy(root / ".github" / "runner-allowlist.yml")
    wf_dir = root / ".github" / "workflows"
    errors: list[str] = []

    for wf_path in sorted(wf_dir.glob("*.yml")) + sorted(wf_dir.glob("*.yaml")):
        wf_name = wf_path.name
        for job_id, runs_on in _workflow_jobs(wf_path):
            labels = _norm_labels(runs_on)
            if not labels:
                continue
            key = (wf_name, job_id)
            if allow_github and _is_github_hosted(labels):
                continue
            if _is_plain_self_hosted(labels):
                continue
            if key in allowed and _is_allowlisted_macos(labels):
                continue
            hint = (
                "GitHub-hosted allowlist"
                if allow_github
                else "self-hosted or allowlisted [self-hosted, macOS…]"
            )
            errors.append(f"{wf_name} job '{job_id}': runs-on={labels!r} (want {hint})")

    if errors:
        print("::error::Runner policy violations:")
        for line in errors:
            print(f"::error::{line}")
        return 1
    print("Runner policy OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())