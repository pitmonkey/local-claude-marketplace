from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import yaml

from .storage.base import SourceRecord

_settings: Settings | None = None


@dataclass
class Settings:
    DATA_DIR: Path
    CONFIG_DIR: Path
    PORT: int
    STORAGE_BACKEND: str
    DB_PATH: Path
    S3_ENDPOINT: str | None
    S3_BUCKET: str
    S3_ACCESS_KEY: str | None
    S3_SECRET_KEY: str | None


def get_settings() -> Settings:
    global _settings
    if _settings is not None:
        return _settings

    data_dir = Path(os.getenv("DATA_DIR", "/data"))
    config_dir = Path(os.getenv("CONFIG_DIR", "/config"))
    port = int(os.getenv("PORT", "8080"))
    storage_backend = os.getenv("STORAGE_BACKEND", "sqlite")
    db_path = Path(os.getenv("DB_PATH", str(data_dir / "db" / "marketplace.db")))
    s3_endpoint = os.getenv("S3_ENDPOINT")
    s3_bucket = os.getenv("S3_BUCKET", "marketplace")
    s3_access_key = os.getenv("S3_ACCESS_KEY")
    s3_secret_key = os.getenv("S3_SECRET_KEY")

    _settings = Settings(
        DATA_DIR=data_dir,
        CONFIG_DIR=config_dir,
        PORT=port,
        STORAGE_BACKEND=storage_backend,
        DB_PATH=db_path,
        S3_ENDPOINT=s3_endpoint,
        S3_BUCKET=s3_bucket,
        S3_ACCESS_KEY=s3_access_key,
        S3_SECRET_KEY=s3_secret_key,
    )
    return _settings


def _reset_settings() -> None:
    global _settings
    _settings = None


def load_repos_yaml(config_dir: Path) -> list[SourceRecord]:
    repos_path = config_dir / "repos.yaml"

    if not repos_path.exists():
        return []

    with open(repos_path) as f:
        data = yaml.safe_load(f)

    if data is None or "repos" not in data:
        return []

    records = []
    for entry in data["repos"]:
        record = SourceRecord(
            id=str(uuid5(NAMESPACE_URL, entry["url"])),
            name=entry["name"],
            url=entry["url"],
            description=entry.get("description", ""),
            ownership=entry.get("ownership", "remote"),
            format=entry.get("format", "auto"),
            is_system=True,
            last_indexed_at=None,
        )
        records.append(record)

    return records
