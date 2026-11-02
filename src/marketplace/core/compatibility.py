"""Client compatibility is derived from catalog records, never persisted."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..storage.base import PluginRecord
from .validator import parse_frontmatter

PORTABILITY_NOTICE = "Installation compatibility does not guarantee instruction portability; Claude-specific tools or instructions may need adaptation."


def safe_name(name: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", name))


@dataclass
class Compatibility:
    supported_clients: list[str]
    compatibility_warnings: list[str]


def assess_compatibility(plugin: PluginRecord) -> Compatibility:
    warnings: list[str] = []
    clients: list[str] = []
    if not safe_name(plugin.name):
        return Compatibility([], ["Unsafe package name; publication disabled."])
    if not plugin.source_url.startswith(("http://", "https://")):
        return Compatibility([], ["Only HTTP Git sources can be published."])
    clients.append("claude")
    if plugin.type != "skill" or plugin.plugin_format == "manifest":
        return Compatibility(clients, ["Claude-only package in this release."])
    meta = parse_frontmatter(plugin.content)
    name, description = meta.get("name"), meta.get("description")
    if (
        not isinstance(name, str)
        or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name)
        or len(name) > 64
    ):
        warnings.append("Codex requires a valid skill name in YAML frontmatter.")
    if not isinstance(description, str) or not description.strip():
        warnings.append("Codex requires a description in YAML frontmatter.")
    if not warnings:
        clients.append("codex")
        warnings.append(PORTABILITY_NOTICE)
    return Compatibility(clients, warnings)
