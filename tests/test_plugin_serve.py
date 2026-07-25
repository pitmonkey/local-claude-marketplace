from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.marketplace.api.marketplace import router
from src.marketplace.api.plugin_serve import router as plugin_serve_router
from src.marketplace.storage.base import PluginRecord
from src.marketplace.storage.sqlite import SqliteRepository


def _make_plugin(
    name: str = "test-plugin",
    type: str = "skill",
    description: str = "A test plugin",
    source_url: str = "https://github.com/example/repo",
    source_path: str = "plugins/test-plugin",
    repo_sha: str = "abc123def456",
    content: str = "# Test Plugin\n\nThis is the plugin content.",
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
        content=content,
        repo_sha=repo_sha,
        file_sha="xyz789",
        version_counter=1,
        updated_at=datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC),
    )


@pytest.fixture
def app_with_repo(tmp_path: Path) -> FastAPI:
    """Create a FastAPI app with both marketplace and plugin_serve routers and a seeded SQLite repo."""
    repo = SqliteRepository(tmp_path / "test.db")
    asyncio.run(repo.init())

    app = FastAPI()
    app.state.repo = repo
    app.include_router(router)
    app.include_router(plugin_serve_router)
    return app


def test_plugin_json_skill(app_with_repo: FastAPI) -> None:
    """GET /plugins/{name}/.claude-plugin/plugin.json returns correct skill manifest without agents key."""
    repo = app_with_repo.state.repo
    plugin = _make_plugin(name="test-skill", type="skill", description="A useful skill")
    asyncio.run(repo.upsert_plugin(plugin))

    client = TestClient(app_with_repo)
    response = client.get("/plugins/test-skill/.claude-plugin/plugin.json")
    assert response.status_code == 200

    data = response.json()
    assert data["name"] == "test-skill"
    assert data["version"] == "1.0.0"
    assert data["description"] == "A useful skill"
    assert data["author"] == {"name": "tester"}
    assert "agents" not in data


def test_plugin_json_subagent(app_with_repo: FastAPI) -> None:
    """GET /plugins/{name}/.claude-plugin/plugin.json returns manifest with agents list for subagent."""
    repo = app_with_repo.state.repo
    plugin = _make_plugin(name="my-agent", type="subagent", description="An agent")
    asyncio.run(repo.upsert_plugin(plugin))

    client = TestClient(app_with_repo)
    response = client.get("/plugins/my-agent/.claude-plugin/plugin.json")
    assert response.status_code == 200

    data = response.json()
    assert data["name"] == "my-agent"
    assert data["agents"] == ["./my-agent.md"]


def test_plugin_json_not_found(app_with_repo: FastAPI) -> None:
    """GET /plugins/{name}/.claude-plugin/plugin.json returns 404 for unknown plugin."""
    client = TestClient(app_with_repo)
    response = client.get("/plugins/nonexistent/.claude-plugin/plugin.json")
    assert response.status_code == 404


def test_skill_content(app_with_repo: FastAPI) -> None:
    """GET /plugins/{name}/skills/{skill_name}/SKILL.md returns raw skill content."""
    repo = app_with_repo.state.repo
    plugin = _make_plugin(
        name="test-skill",
        type="skill",
        content="# My Skill\n\nDo amazing things.",
    )
    asyncio.run(repo.upsert_plugin(plugin))

    client = TestClient(app_with_repo)
    response = client.get("/plugins/test-skill/skills/test-skill/SKILL.md")
    assert response.status_code == 200
    assert "My Skill" in response.text
    assert response.headers["content-type"].startswith("text/plain")


def test_agent_content(app_with_repo: FastAPI) -> None:
    """GET /plugins/{name}/{agent_name}.md returns raw agent content."""
    repo = app_with_repo.state.repo
    plugin = _make_plugin(
        name="my-agent",
        type="subagent",
        content="# My Agent\n\nDoes agent things.",
    )
    asyncio.run(repo.upsert_plugin(plugin))

    client = TestClient(app_with_repo)
    response = client.get("/plugins/my-agent/my-agent.md")
    assert response.status_code == 200
    assert "My Agent" in response.text
    assert response.headers["content-type"].startswith("text/plain")


def test_agent_wrong_name_404(app_with_repo: FastAPI) -> None:
    """GET /plugins/{name}/{agent_name}.md returns 404 when agent_name != plugin name."""
    repo = app_with_repo.state.repo
    plugin = _make_plugin(name="my-agent", type="subagent")
    asyncio.run(repo.upsert_plugin(plugin))

    client = TestClient(app_with_repo)
    response = client.get("/plugins/my-agent/other-name.md")
    assert response.status_code == 404


def test_skill_content_not_found(app_with_repo: FastAPI) -> None:
    """GET /plugins/{name}/skills/{skill_name}/SKILL.md returns 404 for unknown plugin."""
    client = TestClient(app_with_repo)
    response = client.get("/plugins/nonexistent/skills/nonexistent/SKILL.md")
    assert response.status_code == 404


def test_agent_content_wrong_type_404(app_with_repo: FastAPI) -> None:
    """GET /plugins/{name}/{agent_name}.md returns 404 when plugin is a skill, not a subagent."""
    repo = app_with_repo.state.repo
    plugin = _make_plugin(name="test-skill", type="skill")
    asyncio.run(repo.upsert_plugin(plugin))

    client = TestClient(app_with_repo)
    response = client.get("/plugins/test-skill/test-skill.md")
    assert response.status_code == 404


def test_skill_content_wrong_type_404(app_with_repo: FastAPI) -> None:
    """GET /plugins/{name}/skills/{skill_name}/SKILL.md returns 404 when plugin is a subagent."""
    repo = app_with_repo.state.repo
    plugin = _make_plugin(name="my-agent", type="subagent")
    asyncio.run(repo.upsert_plugin(plugin))

    client = TestClient(app_with_repo)
    response = client.get("/plugins/my-agent/skills/my-agent/SKILL.md")
    assert response.status_code == 404
