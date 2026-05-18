from __future__ import annotations

import contextlib
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import (
    Boolean,
    Column,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    delete,
    select,
    text,
)
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from .base import PluginRecord, SourceRecord

metadata = MetaData()

plugins_table = Table(
    "plugins",
    metadata,
    Column("name", String, primary_key=True),
    Column("version", String, nullable=False),
    Column("type", String, nullable=False),
    Column("description", Text, nullable=False),
    Column("tags", Text, nullable=False),
    Column("author", String, nullable=False),
    Column("source_id", String, nullable=False),
    Column("source_url", String, nullable=False),
    Column("source_path", String, nullable=False),
    Column("plugin_format", String, nullable=False),
    Column("source_ownership", String, nullable=False),
    Column("content", Text, nullable=False),
    Column("repo_sha", String, nullable=False),
    Column("file_sha", String, nullable=True),
    Column("version_counter", Integer, nullable=False, default=0),
    Column("updated_at", String, nullable=False),
)

sources_table = Table(
    "sources",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("url", String, nullable=False),
    Column("description", Text, nullable=False),
    Column("ownership", String, nullable=False),
    Column("format", String, nullable=False),
    Column("is_system", Boolean, nullable=False, default=False),
    Column("last_indexed_at", String, nullable=True),
    Column("requires_auth", Boolean, nullable=False, default=False),
    Column("subpath", String, nullable=True),
)


def _plugin_row_to_record(row: Row[tuple[object, ...]]) -> PluginRecord:
    r = row._mapping
    return PluginRecord(
        name=r["name"],
        version=r["version"],
        type=r["type"],
        description=r["description"],
        tags=json.loads(r["tags"]),
        author=r["author"],
        source_id=r["source_id"],
        source_url=r["source_url"],
        source_path=r["source_path"],
        plugin_format=r["plugin_format"],
        source_ownership=r["source_ownership"],
        content=r["content"],
        repo_sha=r["repo_sha"],
        file_sha=r["file_sha"],
        version_counter=r["version_counter"],
        updated_at=datetime.fromisoformat(r["updated_at"]),
    )


def _source_row_to_record(row: Row[tuple[object, ...]]) -> SourceRecord:
    r = row._mapping
    last_indexed_at: datetime | None = None
    if r["last_indexed_at"] is not None:
        last_indexed_at = datetime.fromisoformat(r["last_indexed_at"])
    return SourceRecord(
        id=r["id"],
        name=r["name"],
        url=r["url"],
        description=r["description"],
        ownership=r["ownership"],
        format=r["format"],
        is_system=bool(r["is_system"]),
        last_indexed_at=last_indexed_at,
        requires_auth=bool(r["requires_auth"]),
        subpath=r["subpath"],
    )


class SqliteRepository:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._engine: AsyncEngine = create_async_engine(
            f"sqlite+aiosqlite:///{db_path}",
            echo=False,
            poolclass=NullPool,
        )

    async def init(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(metadata.create_all)
            with contextlib.suppress(Exception):
                await conn.execute(
                    text("ALTER TABLE sources ADD COLUMN requires_auth INTEGER NOT NULL DEFAULT 0")
                )
            with contextlib.suppress(Exception):
                await conn.execute(text("ALTER TABLE sources ADD COLUMN subpath TEXT NULL"))

    async def list_plugins(
        self,
        type_filter: str | None = None,
        tags: list[str] | None = None,
        query: str | None = None,
    ) -> list[PluginRecord]:
        stmt = select(plugins_table)
        if type_filter:
            stmt = stmt.where(plugins_table.c.type == type_filter)
        async with self._engine.connect() as conn:
            result = await conn.execute(stmt)
            rows = result.fetchall()

        records = [_plugin_row_to_record(r) for r in rows]

        if tags:
            records = [r for r in records if all(t in r.tags for t in tags)]

        if query:
            q = query.lower()

            def _score(r: PluginRecord) -> int:
                if q in r.name.lower():
                    return 0
                if q in r.description.lower():
                    return 1
                if q in (r.content or "").lower():
                    return 2
                return 99

            records = [r for r in records if _score(r) < 99]
            records = sorted(records, key=_score)

        return records

    async def get_plugin(self, name: str) -> PluginRecord | None:
        stmt = select(plugins_table).where(plugins_table.c.name == name)
        async with self._engine.connect() as conn:
            result = await conn.execute(stmt)
            row = result.fetchone()
        if row is None:
            return None
        return _plugin_row_to_record(row)

    async def upsert_plugin(self, record: PluginRecord) -> None:
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        values = dict(
            name=record.name,
            version=record.version,
            type=record.type,
            description=record.description,
            tags=json.dumps(record.tags),
            author=record.author,
            source_id=record.source_id,
            source_url=record.source_url,
            source_path=record.source_path,
            plugin_format=record.plugin_format,
            source_ownership=record.source_ownership,
            content=record.content,
            repo_sha=record.repo_sha,
            file_sha=record.file_sha,
            version_counter=record.version_counter,
            updated_at=record.updated_at.isoformat(),
        )
        stmt = sqlite_insert(plugins_table).values(**values)
        update_cols = {k: v for k, v in values.items() if k != "name"}
        stmt = stmt.on_conflict_do_update(index_elements=["name"], set_=update_cols)
        async with self._engine.begin() as conn:
            await conn.execute(stmt)

    async def delete_plugin(self, name: str) -> None:
        stmt = delete(plugins_table).where(plugins_table.c.name == name)
        async with self._engine.begin() as conn:
            await conn.execute(stmt)

    async def list_sources(self) -> list[SourceRecord]:
        stmt = select(sources_table)
        async with self._engine.connect() as conn:
            result = await conn.execute(stmt)
            rows = result.fetchall()
        return [_source_row_to_record(r) for r in rows]

    async def get_source(self, id: str) -> SourceRecord | None:
        stmt = select(sources_table).where(sources_table.c.id == id)
        async with self._engine.connect() as conn:
            result = await conn.execute(stmt)
            row = result.fetchone()
        if row is None:
            return None
        return _source_row_to_record(row)

    async def upsert_source(self, record: SourceRecord) -> None:
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        last_indexed_at = (
            record.last_indexed_at.isoformat() if record.last_indexed_at is not None else None
        )
        values = dict(
            id=record.id,
            name=record.name,
            url=record.url,
            description=record.description,
            ownership=record.ownership,
            format=record.format,
            is_system=int(record.is_system),
            last_indexed_at=last_indexed_at,
            requires_auth=int(record.requires_auth),
            subpath=record.subpath,
        )
        stmt = sqlite_insert(sources_table).values(**values)
        update_cols = {k: v for k, v in values.items() if k != "id"}
        stmt = stmt.on_conflict_do_update(index_elements=["id"], set_=update_cols)
        async with self._engine.begin() as conn:
            await conn.execute(stmt)

    async def delete_source(self, id: str) -> None:
        stmt = delete(sources_table).where(sources_table.c.id == id)
        async with self._engine.begin() as conn:
            await conn.execute(stmt)


__all__ = ["SqliteRepository"]
