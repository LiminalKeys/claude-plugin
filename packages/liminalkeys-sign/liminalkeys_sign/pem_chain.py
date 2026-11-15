"""Parse PEM certificate chain files."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_PEM_BLOCK = re.compile(
    rb"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",
    re.DOTALL,
)


@dataclass(frozen=True)
class PemChainPaths:
    leaf: Path
    intermediates: tuple[Path, ...]
    work_dir: Path


def split_pem_chain_file(chain_path: Path, work_dir: Path) -> PemChainPaths:
    raw = chain_path.read_bytes()
    blocks = _PEM_BLOCK.findall(raw)
    if not blocks:
        raise ValueError(f"No PEM certificates found in {chain_path}")
    work_dir.mkdir(parents=True, exist_ok=True)
    leaf_path = work_dir / "leaf.pem"
    leaf_path.write_bytes(blocks[0] + b"\n")
    intermediate_paths: list[Path] = []
    for index, block in enumerate(blocks[1:], start=1):
        path = work_dir / f"chain-{index}.pem"
        path.write_bytes(block + b"\n")
        intermediate_paths.append(path)
    return PemChainPaths(leaf=leaf_path, intermediates=tuple(intermediate_paths), work_dir=work_dir)