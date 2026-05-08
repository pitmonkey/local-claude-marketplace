from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from src.marketplace.storage.base import (
    PluginRecord,
    PluginRepository,
    SourceRecord,
)

if TYPE_CHECKING:
    pass


class TestPluginRecord:
    """Tests for PluginRecord dataclass."""

    def test_plugin_record_creation_with_all_fields(self) -> None:
        """Test creating a PluginRecord with all fields."""
        now = datetime.now(UTC)
        record = PluginRecord(
            name="test-plugin",
            version="1.0.0",
            type="skill",
            description="Test plugin",
            tags=["test", "example"],
            author="Test Author",
            source_id="source-123",
            source_url="https://example.com/source",
            source_path="path/to/plugin",
            plugin_format="proper",
            source_ownership="mine",
            content="plugin content",
            repo_sha="abc123",
            file_sha="def456",
            version_counter=5,
            updated_at=now,
        )

        assert record.name == "test-plugin"
        assert record.version == "1.0.0"
        assert record.type == "skill"
        assert record.description == "Test plugin"
        assert record.tags == ["test", "example"]
        assert record.author == "Test Author"
        assert record.source_id == "source-123"
        assert record.source_url == "https://example.com/source"
        assert record.source_path == "path/to/plugin"
        assert record.plugin_format == "proper"
        assert record.source_ownership == "mine"
        assert record.content == "plugin content"
        assert record.repo_sha == "abc123"
        assert record.file_sha == "def456"
        assert record.version_counter == 5
        assert record.updated_at == now

    def test_plugin_record_defaults(self) -> None:
        """Test that PluginRecord defaults work correctly."""
        record = PluginRecord(
            name="test",
            version="1.0.0",
            type="skill",
            description="Test",
            tags=[],
            author="Author",
            source_id="source-1",
            source_url="http://example.com",
            source_path="path",
            plugin_format="flat",
            source_ownership="remote",
            content="content",
            repo_sha="sha1",
        )

        assert record.file_sha is None
        assert record.version_counter == 0
        assert isinstance(record.updated_at, datetime)
        assert record.updated_at.tzinfo is not None

    def test_plugin_record_updated_at_default(self) -> None:
        """Test that updated_at default is current UTC time."""
        before = datetime.now(UTC)
        record = PluginRecord(
            name="test",
            version="1.0.0",
            type="subagent",
            description="Test",
            tags=[],
            author="Author",
            source_id="source-1",
            source_url="http://example.com",
            source_path="path",
            plugin_format="proper",
            source_ownership="mine",
            content="content",
            repo_sha="sha1",
        )
        after = datetime.now(UTC)

        assert before <= record.updated_at <= after

    def test_plugin_record_tags_list_mutation(self) -> None:
        """Test that tags list is properly stored and can be mutated."""
        tags = ["tag1", "tag2"]
        record = PluginRecord(
            name="test",
            version="1.0.0",
            type="skill",
            description="Test",
            tags=tags,
            author="Author",
            source_id="source-1",
            source_url="http://example.com",
            source_path="path",
            plugin_format="flat",
            source_ownership="remote",
            content="content",
            repo_sha="sha1",
        )

        assert record.tags == ["tag1", "tag2"]
        record.tags.append("tag3")
        assert record.tags == ["tag1", "tag2", "tag3"]


class TestSourceRecord:
    """Tests for SourceRecord dataclass."""

    def test_source_record_creation_with_all_fields(self) -> None:
        """Test creating a SourceRecord with all fields."""
        now = datetime.now(UTC)
        record = SourceRecord(
            id="source-123",
            name="Test Source",
            url="https://example.com",
            description="A test source",
            ownership="mine",
            format="proper",
            is_system=True,
            last_indexed_at=now,
        )

        assert record.id == "source-123"
        assert record.name == "Test Source"
        assert record.url == "https://example.com"
        assert record.description == "A test source"
        assert record.ownership == "mine"
        assert record.format == "proper"
        assert record.is_system is True
        assert record.last_indexed_at == now

    def test_source_record_defaults(self) -> None:
        """Test that SourceRecord defaults work correctly."""
        record = SourceRecord(
            id="source-1",
            name="Source",
            url="http://example.com",
            description="Test",
            ownership="remote",
            format="auto",
        )

        assert record.is_system is False
        assert record.last_indexed_at is None

    def test_source_record_is_system_default_false(self) -> None:
        """Test that is_system defaults to False."""
        record = SourceRecord(
            id="source-1",
            name="Source",
            url="http://example.com",
            description="Test",
            ownership="mine",
            format="flat",
        )

        assert record.is_system is False

    def test_source_record_last_indexed_at_none_by_default(self) -> None:
        """Test that last_indexed_at is None by default."""
        record = SourceRecord(
            id="source-1",
            name="Source",
            url="http://example.com",
            description="Test",
            ownership="remote",
            format="proper",
        )

        assert record.last_indexed_at is None


class TestPluginRepository:
    """Tests for PluginRepository protocol."""

    def test_plugin_repository_is_protocol(self) -> None:
        """Test that PluginRepository is a runtime-checkable protocol."""
        assert hasattr(PluginRepository, "__protocol_attrs__")

    def test_plugin_repository_protocol_methods(self) -> None:
        """Test that PluginRepository defines all required methods."""
        protocol_methods = {
            "init",
            "list_plugins",
            "get_plugin",
            "upsert_plugin",
            "delete_plugin",
            "list_sources",
            "get_source",
            "upsert_source",
            "delete_source",
        }

        protocol_attrs: set[str] = getattr(PluginRepository, "__protocol_attrs__", set())
        assert protocol_methods.issubset(protocol_attrs)

    def test_plugin_repository_structural_check(self) -> None:
        """Test that a class can be checked against PluginRepository protocol."""

        class FakeRepository:
            async def init(self) -> None:
                pass

            async def list_plugins(
                self,
                type_filter: str | None = None,
                tags: list[str] | None = None,
                query: str | None = None,
            ) -> list[PluginRecord]:
                return []

            async def get_plugin(self, name: str) -> PluginRecord | None:
                return None

            async def upsert_plugin(self, record: PluginRecord) -> None:
                pass

            async def delete_plugin(self, name: str) -> None:
                pass

            async def list_sources(self) -> list[SourceRecord]:
                return []

            async def get_source(self, id: str) -> SourceRecord | None:
                return None

            async def upsert_source(self, record: SourceRecord) -> None:
                pass

            async def delete_source(self, id: str) -> None:
                pass

        repo = FakeRepository()
        assert isinstance(repo, PluginRepository)

    def test_plugin_repository_missing_method_check(self) -> None:
        """Test that a class missing methods fails protocol check."""

        class IncompleteRepository:
            async def init(self) -> None:
                pass

        repo = IncompleteRepository()
        assert not isinstance(repo, PluginRepository)
