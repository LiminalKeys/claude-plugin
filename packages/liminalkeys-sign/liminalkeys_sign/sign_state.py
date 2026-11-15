"""JSON signing state written by `prepare` for MCP sign_hash and `finish`."""

from __future__ import annotations

import base64
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

STATE_VERSION = 2


@dataclass(frozen=True)
class SignState:
    version: int
    digest_hex: str
    digest_base64: str
    work_dir: str
    leaf_cert_path: str
    chain_pem_paths: list[str]
    previews: list[dict[str, str]]
    paths: dict[str, str]
    package_version: str
    document_label: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)

    @classmethod
    def from_path(cls, path: Path) -> SignState:
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(**data)


def digest_base64_from_file(digest_path: Path) -> str:
    raw = digest_path.read_bytes()
    if len(raw) != 32:
        raise ValueError(f"Expected 32-byte digest, got {len(raw)} bytes")
    return base64.standard_b64encode(raw).decode("ascii")


def write_sign_state(
    output: Path,
    *,
    digest_hex: str,
    digest_path: Path,
    work_dir: Path,
    leaf_cert: Path,
    chain_paths: list[Path],
    previews: list[dict[str, str]],
    signed_attrs_path: Path,
    state_pkl_path: Path,
    package_version: str,
    document_label: str | None = None,
    approval_preview_path: Path | None = None,
) -> SignState:
    paths: dict[str, str] = {
        "signed_attrs": str(signed_attrs_path.resolve()),
        "tbs_digest": str(digest_path.resolve()),
        "state_pkl": str(state_pkl_path.resolve()),
    }
    if approval_preview_path is not None:
        paths["approval_preview"] = str(approval_preview_path.resolve())
    state = SignState(
        version=STATE_VERSION,
        digest_hex=digest_hex,
        digest_base64=digest_base64_from_file(digest_path),
        work_dir=str(work_dir.resolve()),
        leaf_cert_path=str(leaf_cert.resolve()),
        chain_pem_paths=[str(p.resolve()) for p in chain_paths],
        previews=previews,
        paths=paths,
        package_version=package_version,
        document_label=document_label,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(state.to_json(), encoding="utf-8")
    return state