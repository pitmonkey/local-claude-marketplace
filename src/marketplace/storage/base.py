from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable


@dataclass
class PluginRecord:
    name: str
    version: str
    type: str  # "skill" | "subagent"
    description: str
    tags: list[str]
    author: str
    source_id: str
    source_url: str
    source_path: str
    plugin_format: str  # "flat" | "proper" | "manifest"
    source_ownership: str  # "mine" | "remote"
    content: str
    repo_sha: str
    file_sha: str | None = None
    version_counter: int = 0
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class SourceRecord:
    id: str
    name: str
    url: str
    description: str
    ownership: str  # "mine" | "remote"
    format: str  # "flat" | "proper" | "auto"
    is_system: bool = False
    last_indexed_at: datetime | None = None
    requires_auth: bool = False
    subpath: str | None = None


@runtime_checkable
class PluginRepository(Protocol):
    async def init(self) -> None: ...

    async def list_plugins(
        self,
        type_filter: str | None = None,
        tags: list[str] | None = None,
        query: str | None = None,
    ) -> list[PluginRecord]: ...

    async def get_plugin(self, name: str) -> PluginRecord | None: ...

    async def upsert_plugin(self, record: PluginRecord) -> None: ...

    async def delete_plugin(self, name: str) -> None: ...

    async def list_sources(self) -> list[SourceRecord]: ...

    async def get_source(self, id: str) -> SourceRecord | None: ...

    async def upsert_source(self, record: SourceRecord) -> None: ...

    async def delete_source(self, id: str) -> None: ...
