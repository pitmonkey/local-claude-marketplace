from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from ..storage.base import PluginRecord, PluginRepository, SourceRecord
from .git_ops import clone_repo, get_repo_sha, pull_repo
from .scanner import scan_repo


async def index_source(source: SourceRecord, repo: PluginRepository, data_dir: Path) -> int:
    """Clone or pull source repo, scan for plugins, upsert/delete in DB. Returns upsert count."""
    repo_path = data_dir / "repos" / source.name
    if repo_path.exists():
        pull_repo(repo_path)
    else:
        clone_repo(source.url, repo_path)

    repo_sha = get_repo_sha(repo_path)

    all_plugins = await repo.list_plugins()
    existing_plugins: dict[str, PluginRecord] = {
        p.name: p for p in all_plugins if p.source_id == source.id
    }

    records = scan_repo(repo_path, source, repo_sha, existing_plugins)

    scanned_names: set[str] = set()
    for record in records:
        await repo.upsert_plugin(record)
        scanned_names.add(record.name)

    for name in existing_plugins:
        if name not in scanned_names:
            await repo.delete_plugin(name)

    source.last_indexed_at = datetime.now(UTC)
    await repo.upsert_source(source)

    return len(records)


async def index_all_sources(repo: PluginRepository, data_dir: Path) -> dict[str, int]:
    """Index every source sequentially. Returns mapping of source name to plugin count."""
    sources = await repo.list_sources()
    results: dict[str, int] = {}
    for source in sources:
        results[source.name] = await index_source(source, repo, data_dir)
    return results


async def add_user_source(
    repo: PluginRepository,
    data_dir: Path,
    url: str,
    name: str,
    description: str,
    ownership: str,
    fmt: str,
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
    )
    await repo.upsert_source(record)
    await index_source(record, repo, data_dir)
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
