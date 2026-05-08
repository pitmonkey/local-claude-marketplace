from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/marketplace.json")  # type: ignore[misc]
async def marketplace_json(request: Request) -> JSONResponse:
    """Return the marketplace schema with all public plugins."""
    repo: Any = request.app.state.repo
    plugins = await repo.list_plugins()

    plugin_list = []
    for plugin in plugins:
        if not (
            plugin.source_url.startswith("http://") or plugin.source_url.startswith("https://")
        ):
            continue

        category = "development" if plugin.type == "subagent" else "productivity"
        base_url = str(request.base_url).rstrip("/")
        homepage = f"{base_url}/plugins/{plugin.name}"

        plugin_entry = {
            "name": plugin.name,
            "description": plugin.description,
            "category": category,
            "source": {
                "source": "git-subdir",
                "url": plugin.source_url,
                "path": plugin.source_path,
                "ref": "main",
                "sha": plugin.repo_sha,
            },
            "homepage": homepage,
        }
        plugin_list.append(plugin_entry)

    response_data = {
        "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
        "name": "local-claude-marketplace",
        "owner": {"name": "local"},
        "plugins": plugin_list,
    }

    return JSONResponse(content=response_data)
