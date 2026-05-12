"""Manages a local git repository that contains generated plugin files for cloning.

Claude Code clones this repo and extracts subdirectories to install plugins.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import dulwich.porcelain as porcelain
from dulwich.refs import Ref
from dulwich.repo import Repo

from ..storage.base import PluginRecord


def write_plugin_files(plugin: PluginRecord, plugins_dir: Path) -> None:
    """Write one plugin's files to plugins_dir/{plugin.name}/.

    For skills, the layout is:
        plugins/{name}/.claude-plugin/plugin.json
        plugins/{name}/skills/{name}/SKILL.md

    For subagents, the layout is:
        plugins/{name}/.claude-plugin/plugin.json
        plugins/{name}/{name}.md

    Args:
        plugin: The plugin record to write.
        plugins_dir: Base directory under which the plugin's subdirectory is created.
    """
    plugin_dir = plugins_dir / plugin.name
    plugin_dir.mkdir(parents=True, exist_ok=True)

    claude_plugin_dir = plugin_dir / ".claude-plugin"
    claude_plugin_dir.mkdir(exist_ok=True)

    if plugin.type == "subagent":
        plugin_json: dict[str, object] = {
            "name": plugin.name,
            "version": plugin.version,
            "description": plugin.description,
            "author": {"name": plugin.author},
            "agents": [f"./{plugin.name}.md"],
        }
        (claude_plugin_dir / "plugin.json").write_text(
            json.dumps(plugin_json, indent=2), encoding="utf-8"
        )
        (plugin_dir / f"{plugin.name}.md").write_text(plugin.content, encoding="utf-8")
    else:
        plugin_json = {
            "name": plugin.name,
            "version": plugin.version,
            "description": plugin.description,
            "author": {"name": plugin.author},
        }
        (claude_plugin_dir / "plugin.json").write_text(
            json.dumps(plugin_json, indent=2), encoding="utf-8"
        )
        skill_dir = plugin_dir / "skills" / plugin.name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(plugin.content, encoding="utf-8")


def rebuild_plugin_repo(plugins: list[PluginRecord], repo_path: Path) -> str:
    """Write all plugin files to repo_path/plugins/, commit to git, return commit SHA.

    Only plugins whose ``source_url`` starts with ``http://`` or ``https://`` are
    written — local-only plugins are excluded (same filter used by the
    ``marketplace.json`` endpoint).

    Steps:
    1. Create the git repo at *repo_path* if it does not yet exist.
    2. Clear the ``plugins/`` subdirectory (delete + recreate).
    3. Write each qualifying plugin's files.
    4. Stage all files via ``dulwich.porcelain.add``.
    5. Commit with message ``"rebuild: {n} plugins"``.
    6. Return the commit SHA as a hex string.

    Args:
        plugins: Full list of plugin records from the database.
        repo_path: Filesystem path to the managed git repository.

    Returns:
        The new commit SHA as a lowercase hex string.
    """
    repo_path.mkdir(parents=True, exist_ok=True)

    # Initialise repository if needed, ensuring HEAD points to main.
    try:
        dulwich_repo = Repo(str(repo_path))
    except Exception:
        dulwich_repo = Repo.init(str(repo_path))
        dulwich_repo.refs.set_symbolic_ref(Ref(b"HEAD"), Ref(b"refs/heads/main"))

    # Clear and recreate the plugins directory.
    plugins_dir = repo_path / "plugins"
    if plugins_dir.exists():
        shutil.rmtree(plugins_dir)
    plugins_dir.mkdir()

    # Filter to only remote-source plugins, excluding manifest plugins.
    remote_plugins = [
        p
        for p in plugins
        if (p.source_url.startswith("http://") or p.source_url.startswith("https://"))
        and p.plugin_format != "manifest"
    ]

    for plugin in remote_plugins:
        write_plugin_files(plugin, plugins_dir)

    # Stage everything.
    porcelain.add(str(repo_path))

    # Commit.
    message = f"rebuild: {len(remote_plugins)} plugins".encode()
    sha_bytes = porcelain.commit(
        str(repo_path),
        message=message,
        author=b"marketplace <marketplace@local>",
        committer=b"marketplace <marketplace@local>",
    )

    return sha_bytes.decode()
