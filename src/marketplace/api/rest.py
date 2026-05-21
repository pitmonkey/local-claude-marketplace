from __future__ import annotations

import dataclasses
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from ..core.sources import (
    add_user_source,
    reindex_source_and_rebuild,
    remove_user_source,
)
from ..storage.base import PluginRepository

router = APIRouter(prefix="/api")


def _record_to_dict(record: object) -> dict[str, Any]:
    """Convert dataclass to dict with datetime → ISO string."""
    if not dataclasses.is_dataclass(record):
        raise TypeError(f"{record} is not a dataclass")

    data: dict[str, Any] = dataclasses.asdict(record)  # type: ignore[arg-type]

    def convert_datetime(obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, dict):
            return {k: convert_datetime(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [convert_datetime(item) for item in obj]
        return obj

    result: dict[str, Any] = convert_datetime(data)
    return result


@router.get("/plugins")
async def list_plugins(
    request: Request,
    q: str | None = None,
    type: str | None = None,
    tags: str | None = None,
) -> list[dict[str, Any]]:
    """List plugins with optional filtering by type, tags, and query."""
    repo: PluginRepository = request.app.state.repo

    tags_list: list[str] | None = None
    if tags:
        tags_list = [t.strip() for t in tags.split(",") if t.strip()]

    plugins = await repo.list_plugins(type_filter=type, tags=tags_list, query=q)
    return [_record_to_dict(plugin) for plugin in plugins]


@router.get("/plugins/{name}")
async def get_plugin(request: Request, name: str) -> dict[str, Any]:
    """Get a single plugin by name."""
    repo: PluginRepository = request.app.state.repo
    plugin = await repo.get_plugin(name)
    if plugin is None:
        raise HTTPException(status_code=404, detail=f"Plugin {name!r} not found")
    return _record_to_dict(plugin)


@router.get("/sources")
async def list_sources(request: Request) -> list[dict[str, Any]]:
    """List all sources."""
    repo: PluginRepository = request.app.state.repo
    sources = await repo.list_sources()
    return [_record_to_dict(source) for source in sources]


@router.post("/sources", status_code=201)
async def create_source(request: Request, body: dict[str, Any]) -> JSONResponse:
    """Create a new user-owned source."""
    repo: PluginRepository = request.app.state.repo
    data_dir: Path = request.app.state.data_dir

    url = body.get("url")
    name = body.get("name")
    description = body.get("description")
    ownership = body.get("ownership")
    fmt = body.get("format")
    raw_auth = body.get("requires_auth", "")
    requires_auth = (
        raw_auth.lower() in ("true", "1", "yes") if isinstance(raw_auth, str) else bool(raw_auth)
    )
    subpath = body.get("subpath") or None

    if not all([url, name, description, ownership, fmt]):
        raise HTTPException(status_code=400, detail="Missing required fields")

    assert url is not None
    assert name is not None
    assert description is not None
    assert ownership is not None
    assert fmt is not None

    try:
        record = await add_user_source(
            repo=repo,
            data_dir=data_dir,
            url=url,
            name=name,
            description=description,
            ownership=ownership,
            fmt=fmt,
            requires_auth=requires_auth,
            subpath=subpath,
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return JSONResponse(content=_record_to_dict(record), status_code=201)


@router.delete("/sources/{id}")
async def delete_source(request: Request, id: str) -> Response:
    """Delete a user-owned source."""
    repo: PluginRepository = request.app.state.repo
    data_dir: Path = request.app.state.data_dir

    try:
        await remove_user_source(repo, id, data_dir)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Cannot remove system source") from e

    return Response(status_code=204)


@router.post("/sources/{id}/reindex")
async def reindex_source(request: Request, id: str) -> dict[str, int]:
    """Reindex a source."""
    repo: PluginRepository = request.app.state.repo
    data_dir: Path = request.app.state.data_dir

    source = await repo.get_source(id)
    if source is None:
        raise HTTPException(status_code=404, detail=f"Source {id!r} not found")

    try:
        count = await reindex_source_and_rebuild(source, repo, data_dir)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"indexed": count}
