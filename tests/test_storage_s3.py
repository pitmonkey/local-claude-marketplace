from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from moto import mock_aws

from src.marketplace.storage.base import PluginRecord, SourceRecord
from src.marketplace.storage.s3 import S3Repository


def _make_plugin(
    name: str = "my-plugin",
    type: str = "skill",
    tags: list[str] | None = None,
    description: str = "A useful plugin",
) -> PluginRecord:
    return PluginRecord(
        name=name,
        version="1.0.0",
        type=type,
        description=description,
        tags=tags or ["python", "dev"],
        author="alice",
        source_id="src-1",
        source_url="https://github.com/example/repo",
        source_path="skills/my-plugin/SKILL.md",
        plugin_format="proper",
        source_ownership="remote",
        content="# My Plugin\nDoes stuff.",
        repo_sha="abc123",
        file_sha="def456",
        version_counter=3,
        updated_at=datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC),
    )


def _make_source(id: str = "src-1") -> SourceRecord:
    return SourceRecord(
        id=id,
        name="Main Source",
        url="https://github.com/example/repo",
        description="The primary plugin source",
        ownership="remote",
        format="proper",
        is_system=True,
        last_indexed_at=datetime(2024, 5, 20, 8, 30, 0, tzinfo=UTC),
    )


@pytest.fixture
async def repo() -> AsyncGenerator[S3Repository, None]:
    with mock_aws():
        r = S3Repository(endpoint_url=None, bucket="test-bucket", access_key=None, secret_key=None)
        await r.init()
        yield r


async def test_upsert_and_get_plugin(repo: S3Repository) -> None:
    plugin = _make_plugin()
    await repo.upsert_plugin(plugin)
    result = await repo.get_plugin(plugin.name)
    assert result is not None
    assert result.name == plugin.name
    assert result.version == plugin.version
    assert result.type == plugin.type
    assert result.description == plugin.description
    assert result.tags == plugin.tags
    assert result.author == plugin.author
    assert result.source_id == plugin.source_id
    assert result.source_url == plugin.source_url
    assert result.source_path == plugin.source_path
    assert result.plugin_format == plugin.plugin_format
    assert result.source_ownership == plugin.source_ownership
    assert result.content == plugin.content
    assert result.repo_sha == plugin.repo_sha
    assert result.file_sha == plugin.file_sha
    assert result.version_counter == plugin.version_counter
    assert result.updated_at == plugin.updated_at


async def test_list_plugins_type_filter(repo: S3Repository) -> None:
    await repo.upsert_plugin(_make_plugin(name="skill-one", type="skill"))
    await repo.upsert_plugin(_make_plugin(name="subagent-one", type="subagent"))
    await repo.upsert_plugin(_make_plugin(name="subagent-two", type="subagent"))

    skills = await repo.list_plugins(type_filter="skill")
    assert len(skills) == 1
    assert skills[0].name == "skill-one"

    subagents = await repo.list_plugins(type_filter="subagent")
    assert len(subagents) == 2


async def test_list_plugins_query(repo: S3Repository) -> None:
    await repo.upsert_plugin(_make_plugin(name="alpha-tool", description="does alpha stuff"))
    await repo.upsert_plugin(_make_plugin(name="beta-tool", description="does beta things"))
    await repo.upsert_plugin(_make_plugin(name="gamma", description="unrelated content"))

    by_name = await repo.list_plugins(query="alpha")
    assert len(by_name) == 1
    assert by_name[0].name == "alpha-tool"

    by_desc = await repo.list_plugins(query="beta things")
    assert len(by_desc) == 1
    assert by_desc[0].name == "beta-tool"

    no_match = await repo.list_plugins(query="zzz-nonexistent")
    assert len(no_match) == 0


async def test_list_plugins_tags(repo: S3Repository) -> None:
    await repo.upsert_plugin(_make_plugin(name="p1", tags=["python", "dev"]))
    await repo.upsert_plugin(_make_plugin(name="p2", tags=["python", "web"]))
    await repo.upsert_plugin(_make_plugin(name="p3", tags=["rust"]))

    python_matches = await repo.list_plugins(tags=["python"])
    assert {r.name for r in python_matches} == {"p1", "p2"}

    python_dev = await repo.list_plugins(tags=["python", "dev"])
    assert len(python_dev) == 1
    assert python_dev[0].name == "p1"

    no_match = await repo.list_plugins(tags=["python", "nonexistent"])
    assert len(no_match) == 0


async def test_delete_plugin(repo: S3Repository) -> None:
    plugin = _make_plugin()
    await repo.upsert_plugin(plugin)
    await repo.delete_plugin(plugin.name)
    result = await repo.get_plugin(plugin.name)
    assert result is None

    plugins = await repo.list_plugins()
    assert len(plugins) == 0


async def test_upsert_and_get_source(repo: S3Repository) -> None:
    source = _make_source()
    await repo.upsert_source(source)
    result = await repo.get_source(source.id)
    assert result is not None
    assert result.id == source.id
    assert result.name == source.name
    assert result.url == source.url
    assert result.description == source.description
    assert result.ownership == source.ownership
    assert result.format == source.format
    assert result.is_system == source.is_system
    assert result.last_indexed_at == source.last_indexed_at


async def test_upsert_is_idempotent(repo: S3Repository) -> None:
    plugin = _make_plugin()
    await repo.upsert_plugin(plugin)
    await repo.upsert_plugin(plugin)
    results = await repo.list_plugins()
    assert len(results) == 1
    assert repo._index["plugins"].count(plugin.name) == 1
