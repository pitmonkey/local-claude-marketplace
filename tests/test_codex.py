import json
from pathlib import Path

import pytest
from dulwich.repo import Repo

from src.marketplace.core.compatibility import assess_compatibility
from src.marketplace.core.plugin_repo import rebuild_plugin_repo
from tests.test_plugin_repo import _make_plugin


def test_codex_catalog_and_shared_content(tmp_path: Path) -> None:
    content = (
        "---\nname: portable\ndescription: Portable skill\n---\n"
        + "Useful workflow instructions. " * 5
    )
    skill = _make_plugin(name="portable", content=content)
    agent = _make_plugin(name="agent", type="subagent")
    rebuild_plugin_repo([skill, agent], tmp_path / "repo")
    root = tmp_path / "repo"
    catalog = json.loads((root / ".agents/plugins/marketplace.json").read_text())
    assert [p["name"] for p in catalog["plugins"]] == ["portable"]
    assert catalog["plugins"][0]["source"]["path"] == "./plugins/portable"
    assert (root / "plugins/portable/.codex-plugin/plugin.json").exists()
    assert (root / "plugins/portable/skills/portable/SKILL.md").read_text() == content
    assert assess_compatibility(skill).supported_clients == ["claude", "codex"]


def test_invalid_skill_remains_claude_only() -> None:
    assert assess_compatibility(_make_plugin()).supported_clients == ["claude"]
    assert assess_compatibility(_make_plugin(name="../escape")).supported_clients == []


def test_failed_publication_preserves_head(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import src.marketplace.core.plugin_repo as publication

    root = tmp_path / "repo"
    sha = rebuild_plugin_repo([_make_plugin()], root)

    def fail(*args: object) -> None:
        raise RuntimeError("publication failed")

    monkeypatch.setattr(publication, "write_plugin_files", fail)
    with pytest.raises(RuntimeError):
        rebuild_plugin_repo([_make_plugin(name="new")], root)
    assert Repo(str(root)).head().decode() == sha


@pytest.mark.parametrize("backend", ["sqlite", "s3"])
async def test_rest_compatibility_and_filter(tmp_path: Path, backend: str) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from moto import mock_aws

    from src.marketplace.api.rest import router
    from src.marketplace.storage.s3 import S3Repository
    from src.marketplace.storage.sqlite import SqliteRepository

    with mock_aws():
        repo = (
            SqliteRepository(tmp_path / "test.db")
            if backend == "sqlite"
            else S3Repository(
                endpoint_url=None, bucket="test-bucket", access_key=None, secret_key=None
            )
        )
        await repo.init()
        await repo.upsert_plugin(
            _make_plugin(
                name="portable",
                content="---\nname: portable\ndescription: Example\n---\nInstructions",
            )
        )
        await repo.upsert_plugin(_make_plugin(name="agent", type="subagent"))
        app = FastAPI()
        app.state.repo = repo
        app.include_router(router)
        with TestClient(app) as client:
            result = client.get("/api/plugins?client=codex")
            assert result.status_code == 200
            assert [p["name"] for p in result.json()] == ["portable"]
            assert result.json()[0]["supported_clients"] == ["claude", "codex"]
            assert result.json()[0]["compatibility_warnings"]
            assert client.get("/api/plugins?client=invalid").status_code == 422
            assert client.get("/api/plugins/agent").json()["supported_clients"] == ["claude"]
