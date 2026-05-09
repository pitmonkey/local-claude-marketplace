from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.marketplace.api.marketplace import router
from src.marketplace.storage.base import PluginRecord
from src.marketplace.storage.sqlite import SqliteRepository


def _make_plugin(
    name: str = "test-plugin",
    type: str = "skill",
    description: str = "A test plugin",
    source_url: str = "https://github.com/example/repo",
    source_path: str = "plugins/test-plugin",
    repo_sha: str = "abc123def456",
) -> PluginRecord:
    return PluginRecord(
        name=name,
        version="1.0.0",
        type=type,
        description=description,
        tags=["test"],
        author="tester",
        source_id="src-1",
        source_url=source_url,
        source_path=source_path,
        plugin_format="proper",
        source_ownership="remote",
        content="# Test Plugin",
        repo_sha=repo_sha,
        file_sha="xyz789",
        version_counter=1,
        updated_at=datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC),
    )


@pytest.fixture
def app_with_repo(tmp_path: Path) -> FastAPI:
    """Create a FastAPI app with a seeded SQLite repo."""
    repo = SqliteRepository(tmp_path / "test.db")
    asyncio.get_event_loop().run_until_complete(repo.init())

    app = FastAPI()
    app.state.repo = repo
    app.include_router(router)
    return app


def test_marketplace_json_has_required_fields(app_with_repo: FastAPI) -> None:
    client = TestClient(app_with_repo)
    response = client.get("/.claude-plugin/marketplace.json")
    assert response.status_code == 200

    data = response.json()
    assert "name" in data
    assert "owner" in data
    assert "plugins" in data


def test_marketplace_json_alias_also_works(app_with_repo: FastAPI) -> None:
    """Legacy /marketplace.json alias must return the same payload."""
    client = TestClient(app_with_repo)
    response = client.get("/marketplace.json")
    assert response.status_code == 200

    data = response.json()
    assert "name" in data
    assert "owner" in data
    assert "plugins" in data


def test_marketplace_json_excludes_local_plugins(app_with_repo: FastAPI) -> None:
    """Plugin with local filesystem path should be excluded."""
    client = TestClient(app_with_repo)
    repo = app_with_repo.state.repo

    local_plugin = _make_plugin(
        name="local-plugin",
        source_url="/mnt/local",
    )
    asyncio.get_event_loop().run_until_complete(repo.upsert_plugin(local_plugin))

    response = client.get("/.claude-plugin/marketplace.json")
    assert response.status_code == 200

    data = response.json()
    plugin_names = [p["name"] for p in data["plugins"]]
    assert "local-plugin" not in plugin_names


def test_marketplace_json_includes_http_plugins(app_with_repo: FastAPI) -> None:
    """Plugin with http/https URL should be included."""
    client = TestClient(app_with_repo)
    repo = app_with_repo.state.repo

    https_plugin = _make_plugin(
        name="https-plugin",
        source_url="https://github.com/example/https-repo",
    )
    http_plugin = _make_plugin(
        name="http-plugin",
        source_url="http://example.com/plugin",
    )

    asyncio.get_event_loop().run_until_complete(repo.upsert_plugin(https_plugin))
    asyncio.get_event_loop().run_until_complete(repo.upsert_plugin(http_plugin))

    response = client.get("/.claude-plugin/marketplace.json")
    assert response.status_code == 200

    data = response.json()
    plugin_names = [p["name"] for p in data["plugins"]]
    assert "https-plugin" in plugin_names
    assert "http-plugin" in plugin_names


def test_marketplace_json_plugin_fields(app_with_repo: FastAPI) -> None:
    """Verify plugin fields in response match the correct Claude Code protocol format."""
    client = TestClient(app_with_repo)
    repo = app_with_repo.state.repo

    plugin = _make_plugin(
        name="test-skill",
        type="skill",
        description="A useful skill",
        source_url="https://github.com/example/repo",
        source_path="skills/test-skill",
        repo_sha="sha123456",
    )
    asyncio.get_event_loop().run_until_complete(repo.upsert_plugin(plugin))

    response = client.get("/.claude-plugin/marketplace.json")
    assert response.status_code == 200

    data = response.json()
    plugins = data["plugins"]
    assert len(plugins) == 1

    p = plugins[0]
    assert p["name"] == "test-skill"
    assert p["description"] == "A useful skill"
    assert p["category"] == "productivity"
    assert p["version"] == "1.0.0"
    assert p["source"]["source"] == "git-subdir"
    assert "git.git" in p["source"]["url"]
    assert p["source"]["path"] == "plugins/test-skill"
    assert p["source"]["ref"] == "main"
    assert "homepage" in p


def test_marketplace_json_category_mapping(app_with_repo: FastAPI) -> None:
    """Test category mapping: skill->productivity, subagent->development."""
    client = TestClient(app_with_repo)
    repo = app_with_repo.state.repo

    skill = _make_plugin(name="my-skill", type="skill")
    subagent = _make_plugin(name="my-agent", type="subagent")

    asyncio.get_event_loop().run_until_complete(repo.upsert_plugin(skill))
    asyncio.get_event_loop().run_until_complete(repo.upsert_plugin(subagent))

    response = client.get("/.claude-plugin/marketplace.json")
    assert response.status_code == 200

    data = response.json()
    plugins_by_name = {p["name"]: p for p in data["plugins"]}

    assert plugins_by_name["my-skill"]["category"] == "productivity"
    assert plugins_by_name["my-agent"]["category"] == "development"


def test_homepage_url_uses_request_host(app_with_repo: FastAPI) -> None:
    """Homepage URL should use the request base URL."""
    client = TestClient(app_with_repo)
    repo = app_with_repo.state.repo

    plugin = _make_plugin(name="test-plugin")
    asyncio.get_event_loop().run_until_complete(repo.upsert_plugin(plugin))

    response = client.get("/.claude-plugin/marketplace.json")
    assert response.status_code == 200

    data = response.json()
    plugins = data["plugins"]
    assert len(plugins) == 1

    homepage = plugins[0]["homepage"]
    assert homepage.startswith("http://")
    assert "/plugins/test-plugin" in homepage


def test_marketplace_json_includes_flat_plugins(app_with_repo: FastAPI) -> None:
    """Flat-format plugins are served virtually so must be included."""
    client = TestClient(app_with_repo)
    repo = app_with_repo.state.repo

    flat_plugin = PluginRecord(
        name="flat-plugin",
        version="1.0.0",
        type="skill",
        description="A flat plugin",
        tags=[],
        author="tester",
        source_id="src-1",
        source_url="https://github.com/example/repo",
        source_path="categories/flat-plugin.md",
        plugin_format="flat",
        source_ownership="remote",
        content="# Flat",
        repo_sha="abc",
        file_sha="xyz",
        version_counter=0,
        updated_at=datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC),
    )
    asyncio.get_event_loop().run_until_complete(repo.upsert_plugin(flat_plugin))

    response = client.get("/.claude-plugin/marketplace.json")
    assert response.status_code == 200

    data = response.json()
    plugin_names = [p["name"] for p in data["plugins"]]
    assert "flat-plugin" in plugin_names
