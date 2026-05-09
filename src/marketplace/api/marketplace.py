from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


async def _build_marketplace_response(request: Request) -> dict[str, Any]:
    """Build the marketplace JSON response payload."""
    repo: Any = request.app.state.repo
    plugins = await repo.list_plugins()

    base_url = str(request.base_url).rstrip("/")
    plugin_list = []
    for plugin in plugins:
        if not (
            plugin.source_url.startswith("http://") or plugin.source_url.startswith("https://")
        ):
            continue

        category = "development" if plugin.type == "subagent" else "productivity"

        plugin_entry: dict[str, Any] = {
            "name": plugin.name,
            "description": plugin.description,
            "version": plugin.version,
            "category": category,
            "source": {
                "source": "git-subdir",
                "url": f"{base_url}/git.git",
                "path": f"plugins/{plugin.name}",
                "ref": "main",
                "sha": plugin.repo_sha,
            },
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
