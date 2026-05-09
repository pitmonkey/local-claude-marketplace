from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse

router = APIRouter()


@router.get("/plugins/{name}/.claude-plugin/plugin.json")
async def plugin_json(name: str, request: Request) -> JSONResponse:
    """Return the plugin manifest for a single plugin."""
    repo: Any = request.app.state.repo
    plugin = await repo.get_plugin(name)

    if plugin is None:
        return JSONResponse(status_code=404, content={"detail": "Plugin not found"})

    manifest: dict[str, Any] = {
        "name": plugin.name,
        "version": plugin.version,
        "description": plugin.description,
        "author": {"name": plugin.author},
    }

    if plugin.type == "subagent":
        manifest["agents"] = [f"./{name}.md"]

    return JSONResponse(content=manifest)


@router.get("/plugins/{name}/skills/{skill_name}/SKILL.md")
async def skill_content(name: str, skill_name: str, request: Request) -> PlainTextResponse:
    """Serve the raw SKILL.md content for a skill plugin."""
    repo: Any = request.app.state.repo
    plugin = await repo.get_plugin(name)

    if plugin is None or plugin.type != "skill":
        return PlainTextResponse(status_code=404, content="Not found")

    return PlainTextResponse(plugin.content, media_type="text/plain; charset=utf-8")


@router.get("/plugins/{name}/{agent_name}.md")
async def agent_content(name: str, agent_name: str, request: Request) -> PlainTextResponse:
    """Serve the raw agent Markdown content for a subagent plugin."""
    repo: Any = request.app.state.repo
    plugin = await repo.get_plugin(name)

    if plugin is None or plugin.type != "subagent":
        return PlainTextResponse(status_code=404, content="Not found")

    if agent_name != name:
        return PlainTextResponse(status_code=404, content="Not found")

    return PlainTextResponse(plugin.content, media_type="text/plain; charset=utf-8")
