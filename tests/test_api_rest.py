from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.marketplace.api.rest import router
from src.marketplace.storage.base import PluginRecord, SourceRecord
from src.marketplace.storage.sqlite import SqliteRepository


def _make_plugin(
    name: str = "my-plugin",
    type: str = "skill",
    tags: list[str] | None = None,
    description: str = "A useful plugin",
    source_id: str = "src-1",
) -> PluginRecord:
    return PluginRecord(
        name=name,
        version="1.0.0",
        type=type,
        description=description,
        tags=tags or ["python", "dev"],
        author="alice",
        source_id=source_id,
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


def _make_source(id: str = "src-1", is_system: bool = False) -> SourceRecord:
    return SourceRecord(
        id=id,
        name="Main Source",
        url="https://github.com/example/repo",
        description="The primary plugin source",
        ownership="remote",
        format="proper",
        is_system=is_system,
        last_indexed_at=datetime(2024, 5, 20, 8, 30, 0, tzinfo=UTC),
    )


@pytest.fixture
async def repo(tmp_path: Path) -> SqliteRepository:
    r = SqliteRepository(tmp_path / "test.db")
    await r.init()
    return r


@pytest.fixture
def app(repo: SqliteRepository, tmp_path: Path) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.state.repo = repo
    app.state.data_dir = tmp_path / "data"
    app.state.data_dir.mkdir(exist_ok=True)
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


async def test_list_plugins_empty(app: FastAPI, client: TestClient) -> None:
    response = client.get("/api/plugins")
    assert response.status_code == 200
    assert response.json() == []


async def test_list_plugins_returns_plugins(
    repo: SqliteRepository, app: FastAPI, client: TestClient
) -> None:
    plugin = _make_plugin(name="test-plugin")
    await repo.upsert_plugin(plugin)

    response = client.get("/api/plugins")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "test-plugin"
    assert data[0]["type"] == "skill"
    assert data[0]["tags"] == ["python", "dev"]
    assert isinstance(data[0]["updated_at"], str)


async def test_list_plugins_type_filter(
    repo: SqliteRepository, app: FastAPI, client: TestClient
) -> None:
    await repo.upsert_plugin(_make_plugin(name="skill-one", type="skill"))
    await repo.upsert_plugin(_make_plugin(name="subagent-one", type="subagent"))

    response = client.get("/api/plugins?type=skill")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "skill-one"

    response = client.get("/api/plugins?type=subagent")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "subagent-one"


async def test_list_plugins_query(repo: SqliteRepository, app: FastAPI, client: TestClient) -> None:
    await repo.upsert_plugin(_make_plugin(name="alpha-tool", description="does alpha"))
    await repo.upsert_plugin(_make_plugin(name="beta-tool", description="does beta"))

    response = client.get("/api/plugins?q=alpha")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "alpha-tool"


async def test_list_plugins_tags(repo: SqliteRepository, app: FastAPI, client: TestClient) -> None:
    await repo.upsert_plugin(_make_plugin(name="p1", tags=["python", "dev"]))
    await repo.upsert_plugin(_make_plugin(name="p2", tags=["python", "web"]))
    await repo.upsert_plugin(_make_plugin(name="p3", tags=["rust"]))

    response = client.get("/api/plugins?tags=python")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    response = client.get("/api/plugins?tags=python,dev")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "p1"


async def test_get_plugin_found(repo: SqliteRepository, app: FastAPI, client: TestClient) -> None:
    plugin = _make_plugin(name="found-plugin")
    await repo.upsert_plugin(plugin)

    response = client.get("/api/plugins/found-plugin")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "found-plugin"
    assert data["type"] == "skill"
    assert isinstance(data["updated_at"], str)


async def test_get_plugin_not_found(client: TestClient) -> None:
    response = client.get("/api/plugins/nonexistent")
    assert response.status_code == 404


async def test_list_sources(repo: SqliteRepository, app: FastAPI, client: TestClient) -> None:
    source = _make_source(id="src-1")
    await repo.upsert_source(source)

    response = client.get("/api/sources")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "src-1"
    assert data[0]["name"] == "Main Source"
    assert isinstance(data[0]["last_indexed_at"], str)


async def test_create_source(
    repo: SqliteRepository, app: FastAPI, client: TestClient, tmp_path: Path
) -> None:
    source_repo = tmp_path / "source_repo"
    source_repo.mkdir()
    subprocess.run(["git", "init", "-b", "main", str(source_repo)], check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=source_repo, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=source_repo, check=True)
    (source_repo / "test-skill.md").write_text(
        "---\nname: test-skill\ndescription: Test\n---\n# Test"
    )
    subprocess.run(["git", "add", "."], cwd=source_repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=source_repo, check=True)

    payload = {
        "url": str(source_repo),
        "name": "new-source",
        "description": "A new source",
        "ownership": "mine",
        "format": "flat",
    }

    response = client.post("/api/sources", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "new-source"
    assert data["is_system"] is False

    stored_sources = await repo.list_sources()
    assert len(stored_sources) == 1
    assert stored_sources[0].name == "new-source"


async def test_delete_system_source_returns_400(
    repo: SqliteRepository, app: FastAPI, client: TestClient
) -> None:
    source = _make_source(id="sys-1", is_system=True)
    await repo.upsert_source(source)

    response = client.delete("/api/sources/sys-1")
    assert response.status_code == 400
    assert "Cannot remove system source" in response.json()["detail"]


async def test_delete_user_source_returns_204(
    repo: SqliteRepository, app: FastAPI, client: TestClient, tmp_path: Path
) -> None:
    source_repo = tmp_path / "source_repo_del"
    source_repo.mkdir()
    subprocess.run(["git", "init", "-b", "main", str(source_repo)], check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=source_repo, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=source_repo, check=True)
    (source_repo / "test.md").write_text("---\nname: test\ndescription: T\n---\n# Test")
    subprocess.run(["git", "add", "."], cwd=source_repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=source_repo, check=True)

    payload = {
        "url": str(source_repo),
        "name": "deletable-source",
        "description": "Will be deleted",
        "ownership": "mine",
        "format": "flat",
    }

    create_response = client.post("/api/sources", json=payload)
    assert create_response.status_code == 201
    source_id = create_response.json()["id"]

    response = client.delete(f"/api/sources/{source_id}")
    assert response.status_code == 204

    sources = await repo.list_sources()
    assert len(sources) == 0


async def test_delete_nonexistent_source_returns_204(client: TestClient) -> None:
    response = client.delete("/api/sources/nonexistent-id")
    assert response.status_code == 204


async def test_reindex_source_not_found(client: TestClient) -> None:
    response = client.post("/api/sources/nonexistent-id/reindex")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


async def test_reindex_source(
    repo: SqliteRepository, app: FastAPI, client: TestClient, tmp_path: Path
) -> None:
    source_repo = tmp_path / "source_repo_reindex"
    source_repo.mkdir()
    subprocess.run(["git", "init", "-b", "main", str(source_repo)], check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=source_repo, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=source_repo, check=True)
    (source_repo / "skill1.md").write_text("---\nname: skill1\ndescription: S1\n---\n# Skill 1")
    (source_repo / "skill2.md").write_text("---\nname: skill2\ndescription: S2\n---\n# Skill 2")
    subprocess.run(["git", "add", "."], cwd=source_repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=source_repo, check=True)

    payload = {
        "url": str(source_repo),
        "name": "reindex-source",
        "description": "For reindexing",
        "ownership": "mine",
        "format": "flat",
    }

    create_response = client.post("/api/sources", json=payload)
    assert create_response.status_code == 201
    source_id = create_response.json()["id"]

    plugins = await repo.list_plugins()
    assert len(plugins) == 2

    reindex_response = client.post(f"/api/sources/{source_id}/reindex")
    assert reindex_response.status_code == 200
    data = reindex_response.json()
    assert data["indexed"] == 2


async def test_create_source_with_requires_auth_string_true(
    repo: SqliteRepository,
    app: FastAPI,
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /api/sources with requires_auth='true' (string) stores flag correctly."""
    # Provide a dummy token so index_source passes the auth check (local paths ignore it)
    monkeypatch.setenv("GIT_AUTH_TOKEN", "dummy-token")

    source_repo = tmp_path / "source_repo_auth"
    source_repo.mkdir()
    subprocess.run(["git", "init", "-b", "main", str(source_repo)], check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=source_repo, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=source_repo, check=True)
    (source_repo / "auth-skill.md").write_text(
        "---\nname: auth-skill\ndescription: Auth test\n---\n# Auth Skill"
    )
    subprocess.run(["git", "add", "."], cwd=source_repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=source_repo, check=True)

    payload = {
        "url": str(source_repo),
        "name": "auth-source",
        "description": "A source requiring auth",
        "ownership": "mine",
        "format": "flat",
        "requires_auth": "true",
    }

    response = client.post("/api/sources", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["requires_auth"] is True


async def test_create_source_with_requires_auth_bool_true(
    repo: SqliteRepository,
    app: FastAPI,
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /api/sources with requires_auth=True (bool) stores flag correctly."""
    # Provide a dummy token so index_source passes the auth check (local paths ignore it)
    monkeypatch.setenv("GIT_AUTH_TOKEN", "dummy-token")

    source_repo = tmp_path / "source_repo_auth_bool"
    source_repo.mkdir()
    subprocess.run(["git", "init", "-b", "main", str(source_repo)], check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=source_repo, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=source_repo, check=True)
    (source_repo / "auth-skill2.md").write_text(
        "---\nname: auth-skill2\ndescription: Auth test 2\n---\n# Auth Skill 2"
    )
    subprocess.run(["git", "add", "."], cwd=source_repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=source_repo, check=True)

    payload = {
        "url": str(source_repo),
        "name": "auth-source-bool",
        "description": "A source requiring auth (bool)",
        "ownership": "mine",
        "format": "flat",
        "requires_auth": True,
    }

    response = client.post("/api/sources", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["requires_auth"] is True


async def test_create_source_without_requires_auth_defaults_false(
    repo: SqliteRepository, app: FastAPI, client: TestClient, tmp_path: Path
) -> None:
    """POST /api/sources without requires_auth field returns requires_auth=false."""
    source_repo = tmp_path / "source_repo_no_auth"
    source_repo.mkdir()
    subprocess.run(["git", "init", "-b", "main", str(source_repo)], check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=source_repo, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=source_repo, check=True)
    (source_repo / "public-skill.md").write_text(
        "---\nname: public-skill\ndescription: Public test\n---\n# Public Skill"
    )
    subprocess.run(["git", "add", "."], cwd=source_repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=source_repo, check=True)

    payload = {
        "url": str(source_repo),
        "name": "no-auth-source",
        "description": "A public source",
        "ownership": "mine",
        "format": "flat",
    }

    response = client.post("/api/sources", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["requires_auth"] is False


async def test_create_source_returns_400_on_runtime_error(
    repo: SqliteRepository, app: FastAPI, client: TestClient
) -> None:
    """POST /api/sources returns 400 when add_user_source raises RuntimeError."""
    from unittest.mock import AsyncMock, patch

    with patch(
        "src.marketplace.api.rest.add_user_source",
        new_callable=AsyncMock,
        side_effect=RuntimeError("GIT_AUTH_TOKEN not set"),
    ):
        response = client.post(
            "/api/sources",
            json={
                "url": "https://example.com/repo.git",
                "name": "failing-source",
                "description": "Will fail",
                "ownership": "mine",
                "format": "flat",
            },
        )

    assert response.status_code == 400
    assert "GIT_AUTH_TOKEN not set" in response.json()["detail"]


async def test_reindex_source_returns_400_on_runtime_error(
    repo: SqliteRepository, app: FastAPI, client: TestClient
) -> None:
    """POST /api/sources/{id}/reindex returns 400 when index_source raises RuntimeError."""
    from unittest.mock import AsyncMock, patch

    source = _make_source(id="src-err")
    await repo.upsert_source(source)

    with patch(
        "src.marketplace.api.rest.index_source",
        new_callable=AsyncMock,
        side_effect=RuntimeError("clone failed"),
    ):
        response = client.post("/api/sources/src-err/reindex")

    assert response.status_code == 400
    assert "clone failed" in response.json()["detail"]
