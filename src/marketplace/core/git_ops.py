from __future__ import annotations

from pathlib import Path
from typing import cast

import git


def clone_repo(url: str, dest: Path) -> None:
    """Clone url to dest. No-op if dest already exists."""
    if dest.exists():
        return
    git.Repo.clone_from(url, str(dest))


def pull_repo(repo_path: Path) -> str:
    """git pull --ff-only. Returns new HEAD sha."""
    repo = git.Repo(repo_path)
    repo.remotes.origin.pull(ff_only=True)
    return repo.head.commit.hexsha  # type: ignore[no-any-return]


def get_repo_sha(repo_path: Path) -> str:
    """Returns current HEAD sha."""
    repo = git.Repo(repo_path)
    return repo.head.commit.hexsha  # type: ignore[no-any-return]


def get_file_sha(repo_path: Path, file_path: str) -> str:
    """SHA of the last commit that touched file_path. Returns '' if file has no commits yet."""
    repo = git.Repo(repo_path)
    try:
        result = cast(str, repo.git.log("-1", "--format=%H", "--", file_path))
        return result
    except git.GitCommandError:
        return ""
