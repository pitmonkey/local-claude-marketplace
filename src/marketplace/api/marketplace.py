from pathlib import Path
from typing import Any

from dulwich.errors import NotGitRepository
from dulwich.repo import Repo as DulwichRepo
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


def _plugin_repo_head_sha(repo_path: Path) -> str | None:
    try:
        return DulwichRepo(str(repo_path)).head().decode()
    except (NotGitRepository, KeyError):
        return None


async def _build_marketplace_response(request: Request) -> dict[str, Any]:
    """Build the marketplace JSON response payload."""
    repo: Any = request.app.state.repo
    plugins = await repo.list_plugins()

    base_url = str(request.base_url).rstrip("/")
    git_repo_path: Path = request.app.state.git_repo_path
    head_sha = _plugin_repo_head_sha(git_repo_path)

    plugin_list = []
    for plugin in plugins:
        if not (
            plugin.source_url.startswith("http://") or plugin.source_url.startswith("https://")
        ):
            continue

        category = "development" if plugin.type == "subagent" else "productivity"

        if plugin.plugin_format == "manifest":
            source: dict[str, Any] = {"source": "url", "url": plugin.source_url}
        else:
            source = {
                "source": "git-subdir",
                "url": f"{base_url}/git.git",
                "path": f"plugins/{plugin.name}",
                "ref": "main",
            }
            if head_sha:
                source["sha"] = head_sha

        plugin_entry: dict[str, Any] = {
            "name": plugin.name,
            "description": plugin.description,
            "version": plugin.version,
            "category": category,
            "source": source,
            "homepage": f"{base_url}/plugins/{plugin.name}",
        }
        plugin_list.append(plugin_entry)

    return {
        "name": "local-claude-marketplace",
        "owner": {"name": "local"},
        "plugins": plugin_list,
    }


@router.get("/.claude-plugin/marketplace.json")
async def marketplace_json_canonical(request: Request) -> JSONResponse:
    """Return the marketplace feed at the canonical Claude Code path."""
    return JSONResponse(content=await _build_marketplace_response(request))


@router.get("/marketplace.json")
async def marketplace_json_alias(request: Request) -> JSONResponse:
    """Legacy alias — same payload as the canonical endpoint."""
    return JSONResponse(content=await _build_marketplace_response(request))
