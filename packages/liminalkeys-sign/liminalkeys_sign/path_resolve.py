"""Resolve signing work paths independent of shell cwd."""

from __future__ import annotations

from pathlib import Path


def resolve_session_dir(*, work_dir: Path | None, state_out: Path | None) -> Path | None:
    if work_dir is not None:
        return work_dir.expanduser().resolve()
    if state_out is not None:
        return state_out.expanduser().resolve().parent
    return None


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_existing_file(path: Path, *, session_dir: Path | None) -> Path:
    """Resolve a user path; prefer session_dir for relative paths that are not in cwd."""
    expanded = path.expanduser()
    if expanded.is_absolute():
        candidate = expanded.resolve()
        if not candidate.is_file():
            raise FileNotFoundError(str(candidate))
        return candidate

    cwd_path = (Path.cwd() / expanded).resolve()
    if cwd_path.is_file():
        return cwd_path

    if session_dir is not None:
        session_path = (session_dir / expanded).resolve()
        if session_path.is_file():
            return session_path
        raise FileNotFoundError(
            f"{expanded} not found in cwd ({Path.cwd()}) or session dir ({session_dir})"
        )

    if not cwd_path.is_file():
        raise FileNotFoundError(str(cwd_path))
    return cwd_path


def resolve_input_file(path: Path, *, session_dir: Path | None) -> Path:
    """Resolve PDF or other input; try cwd then session_dir."""
    expanded = path.expanduser()
    if expanded.is_absolute():
        candidate = expanded.resolve()
        if not candidate.is_file():
            raise FileNotFoundError(str(candidate))
        return candidate

    cwd_path = (Path.cwd() / expanded).resolve()
    if cwd_path.is_file():
        return cwd_path

    if session_dir is not None:
        session_path = (session_dir / expanded).resolve()
        if session_path.is_file():
            return session_path

    if cwd_path.is_file():
        return cwd_path
    if session_dir is not None:
        session_path = (session_dir / expanded).resolve()
        if session_path.is_file():
            return session_path
    tried = str(cwd_path)
    if session_dir is not None:
        tried += f", {session_dir / expanded}"
    raise FileNotFoundError(f"{path} not found (tried {tried})")


def resolve_output_path(path: Path, *, session_dir: Path | None) -> Path:
    expanded = path.expanduser()
    if expanded.is_absolute():
        return expanded.resolve()
    if session_dir is not None:
        return (session_dir / expanded).resolve()
    return (Path.cwd() / expanded).resolve()