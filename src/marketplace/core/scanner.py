from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import yaml

from ..storage.base import PluginRecord, SourceRecord
from .git_ops import get_file_sha
from .validator import parse_frontmatter, validate_plugin_file

_SKIP_FILES = {
    "readme.md",
    "changelog.md",
    "license.md",
    "contributing.md",
    "agents.md",
    "claude.md",
    "gemini.md",
    "copilot-instructions.md",
    "todo.md",
    "roadmap.md",
    "security.md",
    "code_of_conduct.md",
    "support.md",
    "maintainers.md",
    "codeowners.md",
}
_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv"}


def detect_layout(repo_path: Path, ownership: str, format_hint: str) -> str:
    if format_hint in ("flat", "proper"):
        return format_hint
    if ownership == "remote":
        return "flat"
    for subdir in repo_path.iterdir():
        if subdir.is_dir() and ((subdir / "skill.yaml").exists() or (subdir / "SKILL.md").exists()):
            return "proper"
    return "flat"


def _find_skill_md(subdir: Path, name: str) -> Path | None:
    for candidate in (subdir / "SKILL.md", subdir / f"{name}.md"):
        if candidate.exists():
            return candidate
    md_files = list(subdir.glob("*.md"))
    return md_files[0] if md_files else None


def _build_record(
    name: str,
    version: str,
    version_counter: int,
    plugin_type: str,
    description: str,
    tags: list[str],
    author: str,
    source: SourceRecord,
    source_path: str,
    plugin_format: str,
    content: str,
    repo_sha: str,
    file_sha: str,
) -> PluginRecord:
    return PluginRecord(
        name=name,
        version=version,
        version_counter=version_counter,
        type=plugin_type,
        description=description,
        tags=tags,
        author=author,
        source_id=source.id,
        source_url=source.url,
        source_path=source_path,
        plugin_format=plugin_format,
        source_ownership=source.ownership,
        content=content,
        repo_sha=repo_sha,
        file_sha=file_sha,
        updated_at=datetime.now(UTC),
    )


def _resolve_version(
    existing_plugins: dict[str, PluginRecord],
    name: str,
    file_sha: str,
    yaml_version: str | None,
) -> tuple[int, str]:
    existing = existing_plugins.get(name)
    if existing is None:
        counter = 0
    elif existing.file_sha == file_sha:
        counter = existing.version_counter
    else:
        counter = existing.version_counter + 1

    version = yaml_version if yaml_version else f"1.0.{counter}"
    return counter, version


def _scan_proper(
    repo_path: Path,
    source: SourceRecord,
    repo_sha: str,
    existing_plugins: dict[str, PluginRecord],
) -> list[PluginRecord]:
    records: list[PluginRecord] = []
    for subdir in repo_path.iterdir():
        if not subdir.is_dir():
            continue
        yaml_file = subdir / "skill.yaml"
        skill_md_file = subdir / "SKILL.md"
        yaml_version: str | None = None

        if yaml_file.exists():
            try:
                raw_yaml = yaml.safe_load(yaml_file.read_text())
            except yaml.YAMLError:
                continue
            meta: dict[str, object] = raw_yaml if isinstance(raw_yaml, dict) else {}
            name = str(meta.get("name", subdir.name))
            yaml_version = str(meta["version"]) if "version" in meta else None
            description = str(meta.get("description", ""))
            raw_tags = meta.get("tags", [])
            tags = [str(t) for t in raw_tags] if isinstance(raw_tags, list) else []
            author = str(meta.get("author", source.name))
            plugin_type = str(meta.get("type", "skill"))
            md_file = _find_skill_md(subdir, name)
        elif skill_md_file.exists():
            fm = parse_frontmatter(skill_md_file.read_text())
            meta = dict(fm)
            name = str(meta.get("name", subdir.name))
            description = str(meta.get("description", ""))
            raw_tags = meta.get("tags", [])
            tags = [str(t) for t in raw_tags] if isinstance(raw_tags, list) else []
            author = str(meta.get("author", source.name))
            plugin_type = str(meta.get("type", "skill"))
            md_file = skill_md_file
        else:
            continue

        if md_file is None:
            continue
        content = md_file.read_text()
        source_path = subdir.name
        file_sha = get_file_sha(repo_path, subdir)
        counter, version = _resolve_version(existing_plugins, name, file_sha, yaml_version)

        records.append(
            _build_record(
                name=name,
                version=version,
                version_counter=counter,
                plugin_type=plugin_type,
                description=description,
                tags=tags,
                author=author,
                source=source,
                source_path=source_path,
                plugin_format="proper",
                content=content,
                repo_sha=repo_sha,
                file_sha=file_sha,
            )
        )
    return records


def _scan_flat(
    repo_path: Path,
    source: SourceRecord,
    repo_sha: str,
    existing_plugins: dict[str, PluginRecord],
) -> list[PluginRecord]:
    records: list[PluginRecord] = []
    for md_file in repo_path.glob("*.md"):
        if md_file.name.lower() in _SKIP_FILES:
            continue
        content = md_file.read_text()
        meta = parse_frontmatter(content)
        name_raw = meta.get("name")
        name = str(name_raw) if name_raw else md_file.stem
        if not name:
            continue
        description = str(meta.get("description", ""))
        vr = validate_plugin_file(content, name)
        plugin_type = str(meta.get("type", vr.plugin_type))
        source_path = md_file.name
        file_sha = get_file_sha(repo_path, source_path)
        counter, version = _resolve_version(existing_plugins, name, file_sha, None)

        records.append(
            _build_record(
                name=name,
                version=version,
                version_counter=counter,
                plugin_type=plugin_type,
                description=description,
                tags=[],
                author=source.name,
                source=source,
                source_path=source_path,
                plugin_format="flat",
                content=content,
                repo_sha=repo_sha,
                file_sha=file_sha,
            )
        )
    return records


def _scan_remote(
    repo_path: Path,
    source: SourceRecord,
    repo_sha: str,
    existing_plugins: dict[str, PluginRecord],
) -> list[PluginRecord]:
    records: list[PluginRecord] = []
    seen_names: dict[str, str] = {}

    def walk(directory: Path) -> None:
        for entry in sorted(directory.iterdir()):
            if entry.is_dir():
                if entry.name in _SKIP_DIRS:
                    continue
                walk(entry)
            elif entry.suffix == ".md":
                if entry.name.lower() in _SKIP_FILES:
                    continue
                rel = entry.relative_to(repo_path)
                content = entry.read_text()
                yaml_version: str | None = None
                plugin_format: str
                description: str
                tags: list[str]
                author: str
                plugin_type: str
                yaml_file = entry.parent / "skill.yaml"
                if yaml_file.exists():
                    plugin_format = "proper"
                    source_path = str(entry.parent.relative_to(repo_path))
                    try:
                        raw_yaml = yaml.safe_load(yaml_file.read_text())
                    except yaml.YAMLError:
                        raw_yaml = None
                    meta_yaml: dict[str, object] = raw_yaml if isinstance(raw_yaml, dict) else {}
                    name = str(meta_yaml.get("name", entry.stem))
                    yaml_version = str(meta_yaml["version"]) if "version" in meta_yaml else None
                    description = str(meta_yaml.get("description", ""))
                    raw_tags = meta_yaml.get("tags", [])
                    tags = [str(t) for t in raw_tags] if isinstance(raw_tags, list) else []
                    author = str(meta_yaml.get("author", source.name))
                    plugin_type = str(meta_yaml.get("type", "skill"))
                else:
                    result = validate_plugin_file(content, entry.stem)
                    if not result.valid:
                        continue
                    plugin_format = "flat"
                    source_path = str(rel)
                    meta = parse_frontmatter(content)
                    name = str(meta["name"])
                    description = str(meta.get("description", ""))
                    plugin_type = result.plugin_type
                    tags = []
                    author = source.name

                if not name:
                    continue

                if name in seen_names and seen_names[name] != source_path:
                    parent = entry.parent.name
                    name = f"{parent}_{name}"

                seen_names[name] = source_path
                file_sha = get_file_sha(repo_path, source_path)
                counter, version = _resolve_version(existing_plugins, name, file_sha, yaml_version)

                records.append(
                    _build_record(
                        name=name,
                        version=version,
                        version_counter=counter,
                        plugin_type=plugin_type,
                        description=description,
                        tags=tags,
                        author=author,
                        source=source,
                        source_path=source_path,
                        plugin_format=plugin_format,
                        content=content,
                        repo_sha=repo_sha,
                        file_sha=file_sha,
                    )
                )

    walk(repo_path)
    return records


def scan_repo(
    repo_path: Path,
    source: SourceRecord,
    repo_sha: str,
    existing_plugins: dict[str, PluginRecord],
) -> list[PluginRecord]:
    layout = detect_layout(repo_path, source.ownership, source.format)
    if source.ownership == "remote":
        return _scan_remote(repo_path, source, repo_sha, existing_plugins)
    if layout == "proper":
        return _scan_proper(repo_path, source, repo_sha, existing_plugins)
    return _scan_flat(repo_path, source, repo_sha, existing_plugins)
