import base64
import json
from pathlib import Path

from liminalkeys_sign.sign_state import SignState, digest_base64_from_file, write_sign_state


def test_digest_base64_from_file(tmp_path: Path) -> None:
    digest = tmp_path / "tbs_digest.bin"
    digest.write_bytes(b"\x01" * 32)
    assert digest_base64_from_file(digest) == base64.standard_b64encode(b"\x01" * 32).decode()


def test_write_sign_state_roundtrip(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    digest_path = work / "tbs_digest.bin"
    digest_path.write_bytes(b"\xab" * 32)
    out = tmp_path / "state.json"
    previews = [{"content_type": "image/png", "content_base64": "aGk="}]
    write_sign_state(
        out,
        digest_hex="ab" * 32,
        digest_path=digest_path,
        work_dir=work,
        leaf_cert=work / "leaf.pem",
        chain_paths=[],
        previews=previews,
        signed_attrs_path=work / "signed_attrs.der",
        state_pkl_path=work / "state.pkl",
        package_version="0.1.10",
    )
    data = json.loads(out.read_text())
    assert data["digest_base64"]
    assert data["previews"] == previews
    assert SignState.from_path(out).digest_hex == "ab" * 32