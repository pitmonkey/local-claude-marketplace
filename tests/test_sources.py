from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from src.marketplace.core.sources import (
    add_user_source,
    index_all_sources,
    index_source,
    remove_user_source,
)
from src.marketplace.storage.base import SourceRecord

if TYPE_CHECKING:
    from src.marketplace.storage.sqlite import SqliteRepository


@pytest.fixture
async def db(tmp_path: Path):  # type: ignore[no-untyped-def]
    from src.marketplace.storage.sqlite import SqliteRepository

    repo = SqliteRepository(tmp_path / "test.db")
    await repo.init()
    return repo


@pytest.fixture
def source_repo(tmp_path: Path) -> Path:
    """A real git repo containing some .md files to index."""
    repo_path = tmp_path / "source_repo"
    repo_path.mkdir()
    subprocess.run(["git", "init", "-b", "main", str(repo_path)], check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo_path, check=True)
    (repo_path / "python-pro.md").write_text(
        "---\nname: python-pro\ndescription: Python expert\n---\n# Python Pro\nContent here"
    )
    (repo_path / "django-dev.md").write_text(
        "---\nname: django-dev\ndescription: Django developer\n---\n# Django Dev\nContent"
    )
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo_path, check=True)
    return repo_path


def _commit_all(repo_path: Path, message: str = "update") -> None:
    subprocess.run(["git", "add", "-A"], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-m", message], cwd=repo_path, check=True)


async def test_index_source_basic(db: SqliteRepository, source_repo: Path, tmp_path: Path) -> None:
    source = SourceRecord(
        id="src-1",
        name="my-source",
        url=str(source_repo),
        description="Test",
        ownership="mine",
        format="flat",
    )
    await db.upsert_source(source)

    data_dir = tmp_path / "data"
    data_dir.mkdir()

    count = await index_source(source, db, data_dir)

    assert count == 2
    plugins = await db.list_plugins()
    names = {p.name for p in plugins}
    assert "python-pro" in names
    assert "django-dev" in names

    updated_source = await db.get_source("src-1")
    assert updated_source is not None
    assert updated_source.last_indexed_at is not None


async def test_index_source_removes_deleted_plugin(
    db: SqliteRepository, source_repo: Path, tmp_path: Path
) -> None:
    source = SourceRecord(
        id="src-2",
        name="my-source2",
        url=str(source_repo),
        description="Test",
        ownership="mine",
        format="flat",
    )
    await db.upsert_source(source)

    data_dir = tmp_path / "data"
    data_dir.mkdir()

    await index_source(source, db, data_dir)

    plugins_before = await db.list_plugins()
    assert any(p.name == "django-dev" for p in plugins_before)

    (source_repo / "django-dev.md").unlink()
    _commit_all(source_repo, "remove django-dev")

    count = await index_source(source, db, data_dir)

    assert count == 1
    plugins_after = await db.list_plugins()
    names_after = {p.name for p in plugins_after}
    assert "django-dev" not in names_after
    assert "python-pro" in names_after


async def test_index_source_updates_version_counter(
    db: SqliteRepository, source_repo: Path, tmp_path: Path
) -> None:
    source = SourceRecord(
        id="src-3",
        name="my-source3",
        url=str(source_repo),
        description="Test",
        ownership="mine",
        format="flat",
    )
    await db.upsert_source(source)

    data_dir = tmp_path / "data"
    data_dir.mkdir()

    await index_source(source, db, data_dir)

    plugin_before = await db.get_plugin("python-pro")
    assert plugin_before is not None
    counter_before = plugin_before.version_counter

    (source_repo / "python-pro.md").write_text(
        "---\nname: python-pro\ndescription: Python expert v2\n---\n# Python Pro\nUpdated content"
    )
    _commit_all(source_repo, "update python-pro")

    await index_source(source, db, data_dir)

    plugin_after = await db.get_plugin("python-pro")
    assert plugin_after is not None
    assert plugin_after.version_counter == counter_before + 1


async def test_index_all_sources(tmp_path: Path, source_repo: Path) -> None:
    from src.marketplace.storage.sqlite import SqliteRepository

    db1 = SqliteRepository(tmp_path / "test_all.db")
    await db1.init()

    source_repo2 = tmp_path / "source_repo2"
    source_repo2.mkdir()
    subprocess.run(["git", "init", "-b", "main", str(source_repo2)], check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=source_repo2, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=source_repo2, check=True)
    (source_repo2 / "rust-pro.md").write_text(
        "---\nname: rust-pro\ndescription: Rust expert\n---\nContent"
    )
    subprocess.run(["git", "add", "."], cwd=source_repo2, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=source_repo2, check=True)

    src_a = SourceRecord(
        id="src-a",
        name="source-a",
        url=str(source_repo),
        description="Source A",
        ownership="mine",
        format="flat",
    )
    src_b = SourceRecord(
        id="src-b",
        name="source-b",
        url=str(source_repo2),
        description="Source B",
        ownership="mine",
        format="flat",
    )
    await db1.upsert_source(src_a)
    await db1.upsert_source(src_b)

    data_dir = tmp_path / "data_all"
    data_dir.mkdir()

    results = await index_all_sources(db1, data_dir)

    assert results["source-a"] == 2
    assert results["source-b"] == 1


async def test_add_user_source(tmp_path: Path, source_repo: Path) -> None:
    from src.marketplace.storage.sqlite import SqliteRepository

    db2 = SqliteRepository(tmp_path / "test_add.db")
    await db2.init()

    data_dir = tmp_path / "data_add"
    data_dir.mkdir()

    record = await add_user_source(
        repo=db2,
        data_dir=data_dir,
        url=str(source_repo),
        name="added-source",
        description="An added source",
        ownership="mine",
        fmt="flat",
    )

    assert record.name == "added-source"
    assert record.is_system is False

    stored = await db2.get_source(record.id)
    assert stored is not None
    assert stored.last_indexed_at is not None

    plugins = await db2.list_plugins()
    assert len(plugins) == 2


async def test_remove_user_source(tmp_path: Path, source_repo: Path) -> None:
    from src.marketplace.storage.sqlite import SqliteRepository

    db3 = SqliteRepository(tmp_path / "test_remove.db")
    await db3.init()

    data_dir = tmp_path / "data_remove"
    data_dir.mkdir()

    record = await add_user_source(
        repo=db3,
        data_dir=data_dir,
        url=str(source_repo),
        name="removable-source",
        description="Will be removed",
        ownership="mine",
        fmt="flat",
    )

    plugins_before = await db3.list_plugins()
    assert len(plugins_before) == 2

    await remove_user_source(db3, record.id)

    source_after = await db3.get_source(record.id)
    assert source_after is None

    plugins_after = await db3.list_plugins()
    assert len(plugins_after) == 0


async def test_remove_user_source_already_gone(tmp_path: Path) -> None:
    from src.marketplace.storage.sqlite import SqliteRepository

    db4 = SqliteRepository(tmp_path / "test_gone.db")
    await db4.init()

    await remove_user_source(db4, "nonexistent-id")


async def test_remove_system_source_raises(tmp_path: Path) -> None:
    from src.marketplace.storage.sqlite import SqliteRepository

    db5 = SqliteRepository(tmp_path / "test_sys.db")
    await db5.init()

    sys_source = SourceRecord(
        id="sys-1",
        name="system-source",
        url="https://example.com/sys",
        description="System source",
        ownership="remote",
        format="flat",
        is_system=True,
    )
    await db5.upsert_source(sys_source)

    with pytest.raises(ValueError, match="Cannot remove system source"):
        await remove_user_source(db5, "sys-1")


async def test_index_source_raises_when_requires_auth_and_no_token(
    tmp_path: Path, source_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """index_source raises RuntimeError when requires_auth=True but GIT_AUTH_TOKEN not set."""
    from src.marketplace.storage.sqlite import SqliteRepository

    monkeypatch.delenv("GIT_AUTH_TOKEN", raising=False)

    db = SqliteRepository(tmp_path / "test_auth.db")
    await db.init()

    source = SourceRecord(
        id="auth-src-1",
        name="auth-source",
        url=str(source_repo),
        description="Auth required source",
        ownership="mine",
        format="flat",
        requires_auth=True,
    )
    await db.upsert_source(source)

    data_dir = tmp_path / "data_auth"
    data_dir.mkdir()

    with pytest.raises(RuntimeError, match="GIT_AUTH_TOKEN is not set"):
        await index_source(source, db, data_dir)


async def test_add_user_source_with_requires_auth_stores_flag(
    tmp_path: Path, source_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """add_user_source with requires_auth=True stores the flag correctly."""
    from src.marketplace.storage.sqlite import SqliteRepository

    # Set a dummy token so index_source doesn't raise (local paths ignore the token anyway)
    monkeypatch.setenv("GIT_AUTH_TOKEN", "dummy-token")

    db = SqliteRepository(tmp_path / "test_flag.db")
    await db.init()

    data_dir = tmp_path / "data_flag"
    data_dir.mkdir()

    record = await add_user_source(
        repo=db,
        data_dir=data_dir,
        url=str(source_repo),
        name="auth-flagged-source",
        description="Source with auth flag",
        ownership="mine",
        fmt="flat",
        requires_auth=True,
    )

    assert record.requires_auth is True

    stored = await db.get_source(record.id)
    assert stored is not None
    assert stored.requires_auth is True


async def test_add_user_source_default_requires_auth_is_false(
    tmp_path: Path, source_repo: Path
) -> None:
    """add_user_source without requires_auth defaults to False."""
    from src.marketplace.storage.sqlite import SqliteRepository

    db = SqliteRepository(tmp_path / "test_default_auth.db")
    await db.init()

    data_dir = tmp_path / "data_default_auth"
    data_dir.mkdir()

    record = await add_user_source(
        repo=db,
        data_dir=data_dir,
        url=str(source_repo),
        name="no-auth-source",
        description="No auth source",
        ownership="mine",
        fmt="flat",
    )

    assert record.requires_auth is False
