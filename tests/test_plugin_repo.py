"""Tests for src/marketplace/core/plugin_repo.py."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from dulwich.repo import Repo

from src.marketplace.core.plugin_repo import rebuild_plugin_repo, write_plugin_files
from src.marketplace.storage.base import PluginRecord


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


def test_write_skill_plugin(tmp_path: Path) -> None:
    """write_plugin_files writes SKILL.md and plugin.json for a skill plugin."""
    plugin = _make_plugin(name="my-skill", type="skill", content="# My Skill\n\nContent here.")
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()

    write_plugin_files(plugin, plugins_dir)

    plugin_dir = plugins_dir / "my-skill"
    assert plugin_dir.is_dir()

    plugin_json_path = plugin_dir / ".claude-plugin" / "plugin.json"
    assert plugin_json_path.exists()

    plugin_json = json.loads(plugin_json_path.read_text(encoding="utf-8"))
    assert plugin_json["name"] == "my-skill"
    assert plugin_json["version"] == "1.0.0"
    assert plugin_json["description"] == "A test plugin"
    assert plugin_json["author"]["name"] == "tester"
    assert "agents" not in plugin_json

    skill_md = plugin_dir / "skills" / "my-skill" / "SKILL.md"
    assert skill_md.exists()
    assert skill_md.read_text(encoding="utf-8") == "# My Skill\n\nContent here."


def test_write_subagent_plugin(tmp_path: Path) -> None:
    """write_plugin_files writes {name}.md and plugin.json with agents field for subagent."""
    plugin = _make_plugin(
        name="my-agent",
        type="subagent",
        content="# My Agent\n\nAgent instructions.",
    )
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()

    write_plugin_files(plugin, plugins_dir)

    plugin_dir = plugins_dir / "my-agent"
    assert plugin_dir.is_dir()

    plugin_json_path = plugin_dir / ".claude-plugin" / "plugin.json"
    assert plugin_json_path.exists()

    plugin_json = json.loads(plugin_json_path.read_text(encoding="utf-8"))
    assert plugin_json["name"] == "my-agent"
    assert "agents" in plugin_json
    assert plugin_json["agents"] == ["./my-agent.md"]

    agent_md = plugin_dir / "my-agent.md"
    assert agent_md.exists()
    assert agent_md.read_text(encoding="utf-8") == "# My Agent\n\nAgent instructions."


def test_rebuild_creates_git_repo(tmp_path: Path) -> None:
    """rebuild_plugin_repo creates a valid git repository at repo_path."""
    repo_path = tmp_path / "plugin_repo"

    plugins = [_make_plugin(name="sample-skill", type="skill")]
    rebuild_plugin_repo(plugins, repo_path)

    # Should be openable as a dulwich Repo without error.
    r = Repo(str(repo_path))
    assert r is not None


def test_rebuild_writes_plugins(tmp_path: Path) -> None:
    """rebuild_plugin_repo writes plugin files under plugins/ and commits them."""
    repo_path = tmp_path / "plugin_repo"

    plugins = [
        _make_plugin(name="skill-one", type="skill"),
        _make_plugin(name="agent-one", type="subagent"),
    ]
    sha = rebuild_plugin_repo(plugins, repo_path)

    # Commit SHA should be a non-empty hex string.
    assert isinstance(sha, str)
    assert len(sha) == 40

    # Plugin files should exist on disk.
    assert (repo_path / "plugins" / "skill-one" / ".claude-plugin" / "plugin.json").exists()
    assert (repo_path / "plugins" / "skill-one" / "skills" / "skill-one" / "SKILL.md").exists()
    assert (repo_path / "plugins" / "agent-one" / "agent-one.md").exists()


def test_rebuild_excludes_local_plugins(tmp_path: Path) -> None:
    """rebuild_plugin_repo skips plugins with non-HTTP source URLs."""
    repo_path = tmp_path / "plugin_repo"

    plugins = [
        _make_plugin(name="remote-skill", source_url="https://github.com/example/repo"),
        _make_plugin(name="local-skill", source_url="/mnt/local/repo"),
    ]
    rebuild_plugin_repo(plugins, repo_path)

    assert (repo_path / "plugins" / "remote-skill").is_dir()
    assert not (repo_path / "plugins" / "local-skill").exists()


def test_rebuild_is_idempotent(tmp_path: Path) -> None:
    """Calling rebuild_plugin_repo twice does not raise and produces a valid repo."""
    repo_path = tmp_path / "plugin_repo"
    plugins = [_make_plugin(name="stable-skill")]

    first_sha = rebuild_plugin_repo(plugins, repo_path)
    second_sha = rebuild_plugin_repo(plugins, repo_path)

    # Each rebuild creates a new commit (even with the same content dulwich
    # will produce a different SHA due to timestamp), so just verify both are
    # valid 40-char hex strings.
    assert len(first_sha) == 40
    assert len(second_sha) == 40

    r = Repo(str(repo_path))
    assert r is not None
