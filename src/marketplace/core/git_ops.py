from __future__ import annotations

import json
import logging
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from urllib.parse import urlparse, urlunparse

import git

logger = logging.getLogger(__name__)


def _inject_token(url: str, token: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme in ("https", "http"):
        netloc = f"token:{token}@{parsed.hostname}"
        if parsed.port:
            netloc = f"{netloc}:{parsed.port}"
        return urlunparse(parsed._replace(netloc=netloc))
    return url


def check_token_expiry(token: str, source_url: str) -> None:
    """Check PAT expiry via provider API. Logs warning if within 42 days. Best-effort."""
    try:
        parsed = urlparse(source_url)
        host = parsed.hostname or ""
        expiry: datetime | None = None

        if host == "github.com":
            req = urllib.request.Request(
                "https://api.github.com/rate_limit",
                headers={
                    "Authorization": f"Bearer {token}",
                    "User-Agent": "local-claude-marketplace",
                },
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                header = resp.headers.get("GitHub-Authentication-Token-Expiration")
            if header:
                expiry = datetime.strptime(header.strip(), "%Y-%m-%d %H:%M:%S %Z").replace(
                    tzinfo=UTC
                )

        elif "gitlab" in host:
            api_url = f"https://{host}/api/v4/personal_access_tokens/self"
            req = urllib.request.Request(
                api_url,
                headers={
                    "PRIVATE-TOKEN": token,
                    "User-Agent": "local-claude-marketplace",
                },
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data: dict[str, object] = json.loads(resp.read())
            expires_at = data.get("expires_at")
            if expires_at and isinstance(expires_at, str):
                expiry = datetime.strptime(expires_at, "%Y-%m-%d").replace(tzinfo=UTC)

        if expiry is not None:
            days_left = (expiry - datetime.now(UTC)).days
            if days_left <= 42:
                logger.warning(
                    "PAT expiry in %d day%s (expires %s) — rotate GIT_AUTH_TOKEN",
                    days_left,
                    "" if days_left == 1 else "s",
                    expiry.strftime("%Y-%m-%d"),
                )
    except Exception as exc:
        logger.debug("PAT expiry check failed (non-fatal): %s", exc)


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
