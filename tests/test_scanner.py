from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from src.marketplace.core.scanner import detect_layout, parse_frontmatter, scan_repo
from src.marketplace.storage.base import PluginRecord, SourceRecord


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    return repo


def _commit_all(repo: Path, message: str = "commit") -> None:
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", message], cwd=repo, check=True)


def _make_source(
    ownership: str = "mine",
    fmt: str = "auto",
    name: str = "test-source",
) -> SourceRecord:
    return SourceRecord(
        id="src-1",
        name=name,
        url="https://example.com/repo",
        description="Test source",
        ownership=ownership,
        format=fmt,
    )


def test_parse_frontmatter_valid() -> None:
    content = "---\nname: my-skill\ndescription: Does stuff\n---\nBody"
    result = parse_frontmatter(content)
    assert result["name"] == "my-skill"
    assert result["description"] == "Does stuff"


def test_parse_frontmatter_no_frontmatter() -> None:
    result = parse_frontmatter("# Just a markdown file\nNo frontmatter here.")
    assert result == {}


def test_detect_layout_proper(git_repo: Path) -> None:
    subdir = git_repo / "my-skill"
    subdir.mkdir()
    (subdir / "skill.yaml").write_text("name: my-skill\n")
    _commit_all(git_repo)
    assert detect_layout(git_repo, "mine", "auto") == "proper"


def test_detect_layout_flat(git_repo: Path) -> None:
    (git_repo / "my-skill.md").write_text("# My skill\n")
    _commit_all(git_repo)
    assert detect_layout(git_repo, "mine", "auto") == "flat"


def test_detect_layout_remote_always_flat(git_repo: Path) -> None:
    subdir = git_repo / "my-skill"
    subdir.mkdir()
    (subdir / "skill.yaml").write_text("name: my-skill\n")
    _commit_all(git_repo)
    assert detect_layout(git_repo, "remote", "auto") == "flat"


def test_detect_layout_hint_overrides(git_repo: Path) -> None:
    assert detect_layout(git_repo, "mine", "flat") == "flat"
    assert detect_layout(git_repo, "mine", "proper") == "proper"


def test_scan_flat_repo(git_repo: Path) -> None:
    (git_repo / "python-pro.md").write_text(
        "---\nname: python-pro\ndescription: Python expert\n---\nContent here"
    )
    (git_repo / "go-pro.md").write_text(
        "---\nname: go-pro\ndescription: Go expert\n---\nContent here"
    )
    (git_repo / "README.md").write_text("# Readme")
    _commit_all(git_repo)

    source = _make_source()
    from src.marketplace.core.git_ops import get_repo_sha

    repo_sha = get_repo_sha(git_repo)
    records = scan_repo(git_repo, source, repo_sha, {})

    names = {r.name for r in records}
    assert names == {"python-pro", "go-pro"}
    for r in records:
        assert r.plugin_format == "flat"
        assert r.source_id == "src-1"


def test_scan_proper_repo(git_repo: Path) -> None:
    subdir = git_repo / "python-pro"
    subdir.mkdir()
    (subdir / "skill.yaml").write_text(
        "name: python-pro\nversion: 2.1.0\ndescription: Python expert\ntags: [python]\nauthor: alice\ntype: skill\n"
    )
    (subdir / "SKILL.md").write_text("# Python Pro Skill\n\nContent here.")
    _commit_all(git_repo)

    source = _make_source()
    from src.marketplace.core.git_ops import get_repo_sha

    repo_sha = get_repo_sha(git_repo)
    records = scan_repo(git_repo, source, repo_sha, {})

    assert len(records) == 1
    r = records[0]
    assert r.name == "python-pro"
    assert r.version == "2.1.0"
    assert r.description == "Python expert"
    assert r.tags == ["python"]
    assert r.author == "alice"
    assert r.plugin_format == "proper"
    assert r.source_path == "python-pro"


def test_version_counter_starts_at_0(git_repo: Path) -> None:
    (git_repo / "new-skill.md").write_text("---\nname: new-skill\n---\nContent")
    _commit_all(git_repo)

    source = _make_source()
    from src.marketplace.core.git_ops import get_repo_sha

    records = scan_repo(git_repo, source, get_repo_sha(git_repo), {})

    assert len(records) == 1
    assert records[0].version_counter == 0
    assert records[0].version == "1.0.0"


def test_version_counter_increments(git_repo: Path) -> None:
    md = git_repo / "my-skill.md"
    md.write_text("---\nname: my-skill\n---\nOriginal content")
    _commit_all(git_repo, "first commit")

    source = _make_source()
    from src.marketplace.core.git_ops import get_file_sha, get_repo_sha

    first_sha = get_file_sha(git_repo, "my-skill.md")
    old_record = PluginRecord(
        name="my-skill",
        version="1.0.0",
        version_counter=0,
        type="skill",
        description="",
        tags=[],
        author="test-source",
        source_id="src-1",
        source_url="https://example.com/repo",
        source_path="my-skill.md",
        plugin_format="flat",
        source_ownership="mine",
        content="Original content",
        repo_sha="old-sha",
        file_sha=first_sha,
    )

    md.write_text("---\nname: my-skill\n---\nUpdated content")
    _commit_all(git_repo, "second commit")

    records = scan_repo(git_repo, source, get_repo_sha(git_repo), {"my-skill": old_record})
    assert len(records) == 1
    assert records[0].version_counter == 1
    assert records[0].version == "1.0.1"


def test_version_counter_unchanged_if_no_change(git_repo: Path) -> None:
    md = git_repo / "stable-skill.md"
    md.write_text("---\nname: stable-skill\n---\nContent")
    _commit_all(git_repo)

    source = _make_source()
    from src.marketplace.core.git_ops import get_file_sha, get_repo_sha

    file_sha = get_file_sha(git_repo, "stable-skill.md")
    old_record = PluginRecord(
        name="stable-skill",
        version="1.0.5",
        version_counter=5,
        type="skill",
        description="",
        tags=[],
        author="test-source",
        source_id="src-1",
        source_url="https://example.com/repo",
        source_path="stable-skill.md",
        plugin_format="flat",
        source_ownership="mine",
        content="Content",
        repo_sha="same-sha",
        file_sha=file_sha,
    )

    records = scan_repo(git_repo, source, get_repo_sha(git_repo), {"stable-skill": old_record})
    assert len(records) == 1
    assert records[0].version_counter == 5
    assert records[0].version == "1.0.5"


def test_remote_deep_walk(git_repo: Path) -> None:
    categories = git_repo / "categories"
    py_dir = categories / "python"
    py_dir.mkdir(parents=True)
    go_dir = categories / "golang"
    go_dir.mkdir()

    (py_dir / "python-pro.md").write_text(
        "---\nname: python-pro\ndescription: Python\n---\nContent"
    )
    (go_dir / "go-pro.md").write_text("---\nname: go-pro\ndescription: Go\n---\nContent")
    (git_repo / "README.md").write_text("# Readme")
    _commit_all(git_repo)

    source = _make_source(ownership="remote")
    from src.marketplace.core.git_ops import get_repo_sha

    records = scan_repo(git_repo, source, get_repo_sha(git_repo), {})

    names = {r.name for r in records}
    assert "python-pro" in names
    assert "go-pro" in names
    assert all(r.plugin_format == "flat" for r in records)
    assert all("categories/" in r.source_path for r in records)
