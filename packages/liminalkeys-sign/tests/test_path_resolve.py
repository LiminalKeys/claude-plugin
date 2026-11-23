from pathlib import Path

import pytest

from liminalkeys_sign.path_resolve import resolve_existing_file, resolve_output_path, resolve_session_dir


def test_resolve_session_dir_prefers_work_dir(tmp_path: Path) -> None:
    work = tmp_path / "session"
    out = tmp_path / "other" / "state.json"
    assert resolve_session_dir(work_dir=work, state_out=out) == work.resolve()


def test_resolve_session_dir_from_state_out_parent(tmp_path: Path) -> None:
    out = tmp_path / "lk-sign-work" / "state.json"
    assert resolve_session_dir(work_dir=None, state_out=out) == out.parent.resolve()


def test_chain_resolved_in_session_not_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    session = tmp_path / "lk-sign-work"
    session.mkdir()
    chain = session / "chain.pem"
    chain.write_text("pem")
    nested = session / "lk-sign-work"
    nested.mkdir()
    monkeypatch.chdir(nested)
    assert resolve_existing_file(Path("chain.pem"), session_dir=session) == chain.resolve()


def test_state_out_relative_to_session(tmp_path: Path) -> None:
    session = tmp_path / "work"
    session.mkdir()
    out = resolve_output_path(Path("state.json"), session_dir=session)
    assert out == (session / "state.json").resolve()