from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from ..storage.base import PluginRecord, PluginRepository, SourceRecord
from .git_ops import check_token_expiry, clone_repo, get_repo_sha, pull_repo
from .plugin_repo import rebuild_plugin_repo
from .scanner import scan_repo

logger = logging.getLogger(__name__)


async def index_source(source: SourceRecord, repo: PluginRepository, data_dir: Path) -> int:
    """Clone or pull source repo, scan for plugins, upsert/delete in DB. Returns upsert count."""
    repo_path = data_dir / "repos" / source.name
    scan_root = repo_path / source.subpath if source.subpath else repo_path
    logger.info(
        "Indexing source %r (url=%s, format=%s, auth=%s, subpath=%s)",
        source.name,
        source.url,
        source.format,
        source.requires_auth,
        source.subpath or "",
    )
    token: str | None = None
    if source.requires_auth:
        token = os.environ.get("GIT_AUTH_TOKEN")
        if not token:
            logger.error(
                "Source %r requires auth but GIT_AUTH_TOKEN is not set",
                source.name,
            )
            raise RuntimeError(
                f"Source {source.name!r} requires auth but GIT_AUTH_TOKEN is not set"
            )
        check_token_expiry(token, source.url)

    if repo_path.exists():
        pull_repo(repo_path, token=token)
    else:
        clone_repo(source.url, repo_path, token=token)

    repo_sha = get_repo_sha(repo_path)
    logger.info("Source %r at sha=%s", source.name, repo_sha[:12])

    all_plugins = await repo.list_plugins()
    existing_plugins: dict[str, PluginRecord] = {
        p.name: p for p in all_plugins if p.source_id == source.id
    }

    records = scan_repo(scan_root, source, repo_sha, existing_plugins)
    logger.info(
        "Source %r scan complete: %d plugin(s) found",
        source.name,
        len(records),
    )

    scanned_names: set[str] = set()
    for record in records:
        await repo.upsert_plugin(record)
        scanned_names.add(record.name)

    stale = [n for n in existing_plugins if n not in scanned_names]
    if stale:
        logger.info(
            "Source %r: removing %d stale plugin(s): %s",
            source.name,
            len(stale),
            stale,
        )
    for name in existing_plugins:
        if name not in scanned_names:
            await repo.delete_plugin(name)

    source.last_indexed_at = datetime.now(UTC)
    await repo.upsert_source(source)

    return len(records)


async def index_all_sources(repo: PluginRepository, data_dir: Path) -> dict[str, int]:
    """Index every source sequentially, then rebuild the plugin git repo.

    Returns mapping of source name to plugin count.
    """
    sources = await repo.list_sources()
    results: dict[str, int] = {}
    for source in sources:
        try:
            results[source.name] = await index_source(source, repo, data_dir)
        except Exception:
            logger.exception("Failed to index source %r — skipping", source.name)
            results[source.name] = -1

    all_plugins = await repo.list_plugins()
    rebuild_plugin_repo(all_plugins, data_dir / "plugin_repo")

    return results


async def add_user_source(
    repo: PluginRepository,
    data_dir: Path,
    url: str,
    name: str,
    description: str,
    ownership: str,
    fmt: str,
    requires_auth: bool = False,
    subpath: str | None = None,
) -> SourceRecord:
    """Create a user-owned source, persist it, index it, and return the record."""
    record = SourceRecord(
        id=str(uuid4()),
        name=name,
        url=url,
        description=description,
        ownership=ownership,
        format=fmt,
        is_system=False,
        requires_auth=requires_auth,
        subpath=subpath,
    )
    await repo.upsert_source(record)
    try:
        await index_source(record, repo, data_dir)
    except Exception:
        await repo.delete_source(record.id)
        raise
    return record


async def remove_user_source(repo: PluginRepository, source_id: str) -> None:
    """Delete a user-owned source and all its plugins. Raises ValueError for system sources."""
    source = await repo.get_source(source_id)
    if source is None:
        return
    if source.is_system:
        raise ValueError(f"Cannot remove system source {source.name!r}")

    all_plugins = await repo.list_plugins()
    for plugin in all_plugins:
        if plugin.source_id == source_id:
            await repo.delete_plugin(plugin.name)

    await repo.delete_source(source_id)
