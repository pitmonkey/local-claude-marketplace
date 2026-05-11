from __future__ import annotations

import tempfile
from collections.abc import Generator
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pytest
import yaml

from src.marketplace.config import (
    Settings,
    _reset_settings,
    get_settings,
    load_repos_yaml,
)
from src.marketplace.storage.base import SourceRecord


@pytest.fixture(autouse=True)
def reset_settings() -> Generator[None, None, None]:
    _reset_settings()
    yield
    _reset_settings()


class TestGetSettingsDefaults:
    def test_get_settings_defaults(self) -> None:
        with pytest.MonkeyPatch.context() as mp:
            mp.delenv("DATA_DIR", raising=False)
            mp.delenv("CONFIG_FILE", raising=False)
            mp.delenv("PORT", raising=False)
            mp.delenv("STORAGE_BACKEND", raising=False)
            mp.delenv("DB_PATH", raising=False)
            mp.delenv("S3_ENDPOINT", raising=False)
            mp.delenv("S3_BUCKET", raising=False)
            mp.delenv("S3_ACCESS_KEY", raising=False)
            mp.delenv("S3_SECRET_KEY", raising=False)

            settings = get_settings()

            assert Path("/data") == settings.DATA_DIR
            assert Path("/config/repos.yaml") == settings.CONFIG_FILE
            assert settings.PORT == 8080
            assert settings.STORAGE_BACKEND == "sqlite"
            assert Path("/data/db/marketplace.db") == settings.DB_PATH
            assert settings.S3_ENDPOINT is None
            assert settings.S3_BUCKET == "marketplace"
            assert settings.S3_ACCESS_KEY is None
            assert settings.S3_SECRET_KEY is None

    def test_get_settings_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATA_DIR", "/custom/data")
        monkeypatch.setenv("CONFIG_FILE", "/custom/config/repos.yaml")
        monkeypatch.setenv("PORT", "9000")
        monkeypatch.setenv("STORAGE_BACKEND", "s3")
        monkeypatch.setenv("DB_PATH", "/custom/data/db/custom.db")
        monkeypatch.setenv("S3_ENDPOINT", "https://s3.example.com")
        monkeypatch.setenv("S3_BUCKET", "custom-bucket")
        monkeypatch.setenv("S3_ACCESS_KEY", "access-key")
        monkeypatch.setenv("S3_SECRET_KEY", "secret-key")

        settings = get_settings()

        assert Path("/custom/data") == settings.DATA_DIR
        assert Path("/custom/config/repos.yaml") == settings.CONFIG_FILE
        assert settings.PORT == 9000
        assert settings.STORAGE_BACKEND == "s3"
        assert Path("/custom/data/db/custom.db") == settings.DB_PATH
        assert settings.S3_ENDPOINT == "https://s3.example.com"
        assert settings.S3_BUCKET == "custom-bucket"
        assert settings.S3_ACCESS_KEY == "access-key"
        assert settings.S3_SECRET_KEY == "secret-key"

    def test_get_settings_caching(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PORT", "9000")
        settings1 = get_settings()
        assert settings1.PORT == 9000

        monkeypatch.setenv("PORT", "8000")
        settings2 = get_settings()
        assert settings2.PORT == 9000
        assert settings1 is settings2

    def test_get_settings_db_path_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DB_PATH", raising=False)
        monkeypatch.setenv("DATA_DIR", "/custom/data")

        settings = get_settings()

        assert Path("/custom/data/db/marketplace.db") == settings.DB_PATH

    def test_get_settings_returns_settings_instance(self) -> None:
        settings = get_settings()
        assert isinstance(settings, Settings)

    def test_get_settings_singleton_pattern(self) -> None:
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2


class TestLoadReposYaml:
    def test_load_repos_yaml_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = load_repos_yaml(Path(tmpdir) / "repos.yaml")
            assert result == []

    def test_load_repos_yaml_parses_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            repos_data: dict[str, list[dict[str, str]]] = {
                "repos": [
                    {
                        "name": "Test Repo 1",
                        "url": "https://github.com/test/repo1",
                        "description": "Test repository 1",
                    },
                    {
                        "name": "Test Repo 2",
                        "url": "https://github.com/test/repo2",
                        "description": "Test repository 2",
                    },
                ]
            }

            repos_file = config_dir / "repos.yaml"
            with open(repos_file, "w") as f:
                yaml.dump(repos_data, f)

            records = load_repos_yaml(config_dir / "repos.yaml")

            assert len(records) == 2
            assert all(isinstance(r, SourceRecord) for r in records)

            assert records[0].name == "Test Repo 1"
            assert records[0].url == "https://github.com/test/repo1"
            assert records[0].description == "Test repository 1"
            assert records[0].is_system is True
            assert records[0].last_indexed_at is None

            assert records[1].name == "Test Repo 2"
            assert records[1].url == "https://github.com/test/repo2"
            assert records[1].description == "Test repository 2"
            assert records[1].is_system is True
            assert records[1].last_indexed_at is None

            assert records[0].id == str(
                uuid5(
                    NAMESPACE_URL,
                    "https://github.com/test/repo1",
                )
            )
            assert records[1].id == str(
                uuid5(
                    NAMESPACE_URL,
                    "https://github.com/test/repo2",
                )
            )

    def test_load_repos_yaml_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            repos_data: dict[str, list[dict[str, str]]] = {
                "repos": [
                    {
                        "name": "Minimal Repo",
                        "url": "https://github.com/test/minimal",
                    }
                ]
            }

            repos_file = config_dir / "repos.yaml"
            with open(repos_file, "w") as f:
                yaml.dump(repos_data, f)

            records = load_repos_yaml(config_dir / "repos.yaml")

            assert len(records) == 1
            record = records[0]
            assert record.description == ""
            assert record.ownership == "remote"
            assert record.format == "auto"
            assert record.is_system is True
            assert record.last_indexed_at is None

    def test_load_repos_yaml_deterministic_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            repos_data: dict[str, list[dict[str, str]]] = {
                "repos": [
                    {
                        "name": "Repo A",
                        "url": "https://github.com/test/a",
                    }
                ]
            }

            repos_file = config_dir / "repos.yaml"
            with open(repos_file, "w") as f:
                yaml.dump(repos_data, f)

            records1 = load_repos_yaml(config_dir / "repos.yaml")
            records2 = load_repos_yaml(config_dir / "repos.yaml")

            assert records1[0].id == records2[0].id

    def test_load_repos_yaml_empty_repos_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            repos_data: dict[str, list[dict[str, str]]] = {"repos": []}

            repos_file = config_dir / "repos.yaml"
            with open(repos_file, "w") as f:
                yaml.dump(repos_data, f)

            records = load_repos_yaml(config_dir / "repos.yaml")
            assert records == []

    def test_load_repos_yaml_no_repos_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            repos_data: dict[str, list[dict[str, str]]] = {"other_key": []}

            repos_file = config_dir / "repos.yaml"
            with open(repos_file, "w") as f:
                yaml.dump(repos_data, f)

            records = load_repos_yaml(config_dir / "repos.yaml")
            assert records == []

    def test_load_repos_yaml_multiple_entries_different_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            repos_data: dict[str, list[dict[str, str]]] = {
                "repos": [
                    {
                        "name": "Repo 1",
                        "url": "https://github.com/test/repo1",
                    },
                    {
                        "name": "Repo 2",
                        "url": "https://github.com/test/repo2",
                    },
                ]
            }

            repos_file = config_dir / "repos.yaml"
            with open(repos_file, "w") as f:
                yaml.dump(repos_data, f)

            records = load_repos_yaml(config_dir / "repos.yaml")

            assert records[0].id != records[1].id

    def test_load_repos_yaml_requires_auth_true(self) -> None:
        """YAML entry with requires_auth: true → record.requires_auth == True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            repos_data = {
                "repos": [
                    {
                        "name": "Private Repo",
                        "url": "https://github.com/example/private",
                        "requires_auth": True,
                    }
                ]
            }

            repos_file = config_dir / "repos.yaml"
            with open(repos_file, "w") as f:
                yaml.dump(repos_data, f)

            records = load_repos_yaml(config_dir / "repos.yaml")
            assert len(records) == 1
            assert records[0].requires_auth is True

    def test_load_repos_yaml_requires_auth_absent_defaults_false(self) -> None:
        """YAML entry without requires_auth → record.requires_auth == False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            repos_data = {
                "repos": [
                    {
                        "name": "Public Repo",
                        "url": "https://github.com/example/public",
                    }
                ]
            }

            repos_file = config_dir / "repos.yaml"
            with open(repos_file, "w") as f:
                yaml.dump(repos_data, f)

            records = load_repos_yaml(config_dir / "repos.yaml")
            assert len(records) == 1
            assert records[0].requires_auth is False
