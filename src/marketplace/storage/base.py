from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable


@dataclass
class PluginRecord:
    """Represents a plugin (skill or subagent) record in the marketplace."""

    name: str
    version: str
    type: str  # "skill" | "subagent"
    description: str
    tags: list[str]
    author: str
    source_id: str
    source_url: str
    source_path: str
    plugin_format: str  # "flat" | "proper"
    source_ownership: str  # "mine" | "remote"
    content: str
    repo_sha: str
    file_sha: str | None = None
    version_counter: int = 0
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class SourceRecord:
    """Represents a source (repository or collection) record in the marketplace."""

    id: str
    name: str
    url: str
    description: str
    ownership: str  # "mine" | "remote"
    format: str  # "flat" | "proper" | "auto"
    is_system: bool = False
    last_indexed_at: datetime | None = None


@runtime_checkable
class PluginRepository(Protocol):
    """Abstract protocol for plugin repository storage backends."""

    async def init(self) -> None:
        """Initialize the repository storage."""
        ...

    async def list_plugins(
        self,
        type_filter: str | None = None,
        tags: list[str] | None = None,
        query: str | None = None,
    ) -> list[PluginRecord]:
        """List plugins with optional filtering by type, tags, and search query.

        Args:
            type_filter: Optional plugin type filter ("skill" or "subagent").
            tags: Optional list of tags to filter by.
            query: Optional search query string.

        Returns:
            List of matching PluginRecord instances.
        """
        ...

    async def get_plugin(self, name: str) -> PluginRecord | None:
        """Retrieve a single plugin by name.

        Args:
            name: The plugin name.

        Returns:
            PluginRecord if found, None otherwise.
        """
        ...

    async def upsert_plugin(self, record: PluginRecord) -> None:
        """Insert or update a plugin record.

        Args:
            record: The PluginRecord to insert or update.
        """
        ...

    async def delete_plugin(self, name: str) -> None:
        """Delete a plugin by name.

        Args:
            name: The plugin name.
        """
        ...

    async def list_sources(self) -> list[SourceRecord]:
        """List all configured sources.

        Returns:
            List of SourceRecord instances.
        """
        ...

    async def get_source(self, id: str) -> SourceRecord | None:
        """Retrieve a single source by ID.

        Args:
            id: The source ID.

        Returns:
            SourceRecord if found, None otherwise.
        """
        ...

    async def upsert_source(self, record: SourceRecord) -> None:
        """Insert or update a source record.

        Args:
            record: The SourceRecord to insert or update.
        """
        ...

    async def delete_source(self, id: str) -> None:
        """Delete a source by ID.

        Args:
            id: The source ID.
        """
        ...
