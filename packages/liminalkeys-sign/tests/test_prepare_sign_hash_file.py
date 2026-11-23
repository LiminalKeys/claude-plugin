import base64
import json
import subprocess
import sys
from pathlib import Path


def test_prepare_writes_sign_hash_json(signing_material, input_pdf, tmp_path: Path) -> None:
    work = tmp_path / "lk-sign-work"
    work.mkdir()
    chain = work / "chain.pem"
    chain.write_bytes(signing_material["cert_pem"])
    state = work / "state.json"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "liminalkeys_sign",
            "prepare",
            "--pdf",
            str(input_pdf),
            "--cert-chain",
            "chain.pem",
            "--work-dir",
            str(work),
            "--out",
            "state.json",
            "--document-label",
            "Demo",
        ],
        cwd=work,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    sign_hash = work / "sign_hash.json"
    assert sign_hash.is_file()
    body = json.loads(sign_hash.read_text())
    assert body["digest_base64"]
    assert body["document_label"] == "Demo"
    assert len(body["previews"]) == 1
    decoded = base64.standard_b64decode(body["previews"][0]["content_base64"])
    assert len(decoded) <= 4096
    state_data = json.loads(state.read_text())
    assert state_data["sign_hash_path"] == str(sign_hash.resolve())