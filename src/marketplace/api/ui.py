from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from markdown_it import MarkdownIt

from ..core.sources import add_user_source, index_source, remove_user_source
from ..storage.base import PluginRepository

router = APIRouter()

_md = MarkdownIt()


@router.get("/")
async def index(
    request: Request,
    q: str | None = None,
    type: str | None = None,
    tags: str | None = None,
) -> object:
    """Render the plugin browsing index page."""
    repo: PluginRepository = request.app.state.repo
    templates: Jinja2Templates = request.app.state.templates

    tags_list: list[str] | None = None
    if tags:
        tags_list = [t.strip() for t in tags.split(",") if t.strip()]

    plugins = await repo.list_plugins(type_filter=type, query=q, tags=tags_list)
    return templates.TemplateResponse(
        request,
        "index.html",
        {"plugins": plugins, "q": q, "type": type, "tags": tags},
    )


@router.get("/plugins/{name}")
async def plugin_detail(request: Request, name: str) -> object:
    """Render the plugin detail page."""
    repo: PluginRepository = request.app.state.repo
    templates: Jinja2Templates = request.app.state.templates

    plugin = await repo.get_plugin(name)
    if plugin is None:
        raise HTTPException(status_code=404, detail=f"Plugin {name!r} not found")

    content_html = _md.render(plugin.content)
    return templates.TemplateResponse(
        request,
        "plugin.html",
        {"plugin": plugin, "content_html": content_html},
    )


@router.get("/sources")
async def sources(request: Request, error: str | None = None) -> object:
    """Render the sources management page."""
    repo: PluginRepository = request.app.state.repo
    templates: Jinja2Templates = request.app.state.templates

    sources_list = await repo.list_sources()
    all_plugins = await repo.list_plugins()

    plugin_counts: dict[str, dict[str, int]] = {}
    for p in all_plugins:
        counts = plugin_counts.setdefault(p.source_id, {"skill": 0, "subagent": 0})
        if p.type in counts:
            counts[p.type] += 1

    return templates.TemplateResponse(
        request,
        "sources.html",
        {"sources": sources_list, "error": error, "plugin_counts": plugin_counts},
    )


@router.get("/ui/search")
async def search_partial(
    request: Request,
    q: str | None = None,
    type: str | None = None,
    tags: str | None = None,
) -> object:
    """Return HTMX partial with plugin cards for live search."""
    repo: PluginRepository = request.app.state.repo
    templates: Jinja2Templates = request.app.state.templates

    tags_list: list[str] | None = None
    if tags:
        tags_list = [t.strip() for t in tags.split(",") if t.strip()]

    plugins = await repo.list_plugins(type_filter=type, query=q, tags=tags_list)
    return templates.TemplateResponse(
        request,
        "partials/plugin_cards.html",
        {"plugins": plugins},
    )


@router.post("/ui/sources")
async def add_source(
    request: Request,
    url: str = Form(...),
    name: str = Form(...),
    description: str = Form(...),
    ownership: str = Form(...),
    format: str = Form(...),
    requires_auth: str = Form(default=""),
    subpath: str = Form(default=""),
) -> RedirectResponse:
    """Handle Add Source form submission."""
    repo: PluginRepository = request.app.state.repo
    data_dir: Path = request.app.state.data_dir

    try:
        await add_user_source(
            repo=repo,
            data_dir=data_dir,
            url=url,
            name=name,
            description=description,
            ownership=ownership,
            fmt=format,
            requires_auth=requires_auth.lower() == "true",
            subpath=subpath or None,
        )
    except (ValueError, RuntimeError) as exc:
        return RedirectResponse(f"/sources?error={exc}", status_code=303)

    return RedirectResponse("/sources", status_code=303)


@router.post("/ui/sources/{id}/delete")
async def delete_source(request: Request, id: str) -> RedirectResponse:
    """Handle source deletion form submission."""
    repo: PluginRepository = request.app.state.repo
    await remove_user_source(repo, id)
    return RedirectResponse("/sources", status_code=303)


@router.post("/ui/sources/{id}/reindex")
async def reindex_source(request: Request, id: str) -> RedirectResponse:
    """Handle source reindex form submission."""
    repo: PluginRepository = request.app.state.repo
    data_dir: Path = request.app.state.data_dir

    source = await repo.get_source(id)
    if source is not None:
        try:
            await index_source(source, repo, data_dir)
        except (ValueError, RuntimeError) as exc:
            return RedirectResponse(f"/sources?error={exc}", status_code=303)

    return RedirectResponse("/sources", status_code=303)
