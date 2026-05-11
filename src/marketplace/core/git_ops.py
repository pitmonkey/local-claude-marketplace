from __future__ import annotations

from pathlib import Path
from typing import cast
from urllib.parse import urlparse, urlunparse

import git


def _inject_token(url: str, token: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme in ("https", "http"):
        netloc = f"token:{token}@{parsed.hostname}"
        if parsed.port:
            netloc = f"{netloc}:{parsed.port}"
        return urlunparse(parsed._replace(netloc=netloc))
    return url


def clone_repo(url: str, dest: Path, token: str | None = None) -> None:
    """Clone url to dest. No-op if dest already exists."""
    if dest.exists():
        return
    effective_url = _inject_token(url, token) if token else url
    git.Repo.clone_from(effective_url, str(dest))


def pull_repo(repo_path: Path, token: str | None = None) -> str:
    """git pull --ff-only. Returns new HEAD sha."""
    repo = git.Repo(repo_path)
    origin = repo.remotes.origin
    if token:
        original_url = origin.url
        with origin.config_writer as cw:
            cw.set("url", _inject_token(original_url, token))
        try:
            origin.pull(ff_only=True)
        finally:
            with origin.config_writer as cw:
                cw.set("url", original_url)
    else:
        origin.pull(ff_only=True)
    return str(repo.head.commit.hexsha)


def get_repo_sha(repo_path: Path) -> str:
    """Returns current HEAD sha."""
    repo = git.Repo(repo_path)
    return str(repo.head.commit.hexsha)


def get_file_sha(repo_path: Path, file_path: str) -> str:
    """SHA of the last commit that touched file_path. Returns '' if file has no commits yet."""
    repo = git.Repo(repo_path)
    try:
        result = cast(str, repo.git.log("-1", "--format=%H", "--", file_path))
        return result
    except git.GitCommandError:
        return ""
