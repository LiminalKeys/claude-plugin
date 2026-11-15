from pathlib import Path

from liminalkeys_sign.pem_chain import split_pem_chain_file

LEAF = b"""-----BEGIN CERTIFICATE-----
MIIBkTCB+wIJAKexampleleaf
-----END CERTIFICATE-----
"""

INTERM = b"""-----BEGIN CERTIFICATE-----
MIIBkTCB+wIJAKexampleinterm
-----END CERTIFICATE-----
"""


def test_split_pem_chain_file(tmp_path: Path) -> None:
    chain = tmp_path / "chain.pem"
    chain.write_bytes(LEAF + b"\n" + INTERM + b"\n")
    work = tmp_path / "work"
    result = split_pem_chain_file(chain, work)
    assert result.leaf.read_bytes().startswith(b"-----BEGIN CERTIFICATE-----")
    assert len(result.intermediates) == 1
    assert result.intermediates[0].is_file()