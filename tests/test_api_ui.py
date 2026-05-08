from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.testclient import TestClient

from src.marketplace.api.ui import router
from src.marketplace.storage.base import PluginRecord, SourceRecord
from src.marketplace.storage.sqlite import SqliteRepository


def _make_plugin(name: str = "my-plugin", type: str = "skill") -> PluginRecord:
    return PluginRecord(
        name=name,
        version="1.0.0",
        type=type,
        description="A useful plugin",
        tags=["python", "dev"],
        author="alice",
        source_id="src-1",
        source_url="https://github.com/example/repo",
        source_path="skills/my-plugin/SKILL.md",
        plugin_format="proper",
        source_ownership="remote",
        content="# My Plugin\nDoes stuff.",
        repo_sha="abc123",
        file_sha="def456",
        version_counter=1,
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
    app.state.templates = Jinja2Templates(directory=Path("src/marketplace/templates"))
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


async def test_ui_index_returns_200(repo: SqliteRepository, client: TestClient) -> None:
    await repo.upsert_plugin(_make_plugin(name="test-plugin"))
    response = client.get("/")
    assert response.status_code == 200
    assert "Claude Marketplace" in response.text


async def test_ui_plugin_detail_returns_200(repo: SqliteRepository, client: TestClient) -> None:
    await repo.upsert_plugin(_make_plugin(name="detail-plugin"))
    response = client.get("/plugins/detail-plugin")
    assert response.status_code == 200
    assert "detail-plugin" in response.text


async def test_ui_sources_returns_200(repo: SqliteRepository, client: TestClient) -> None:
    await repo.upsert_source(_make_source())
    response = client.get("/sources")
    assert response.status_code == 200
    assert "Sources" in response.text


async def test_ui_plugin_not_found(client: TestClient) -> None:
    response = client.get("/plugins/nonexistent")
    assert response.status_code == 404
