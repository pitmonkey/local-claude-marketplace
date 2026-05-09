"""Git HTTP smart protocol server using git-http-backend CGI."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import Response

router = APIRouter()


async def _git_http_backend(request: Request, path: str) -> Response:
    repo_path: Path = request.app.state.git_repo_path
    body = await request.body()

    path_info = f"/{repo_path.name}/{path}" if path else f"/{repo_path.name}"

    env = {
        **os.environ,
        "GIT_HTTP_EXPORT_ALL": "1",
        "GIT_PROJECT_ROOT": str(repo_path.parent),
        "PATH_INFO": path_info,
        "REQUEST_METHOD": request.method,
        "QUERY_STRING": request.url.query or "",
        "CONTENT_TYPE": request.headers.get("content-type", ""),
        "CONTENT_LENGTH": str(len(body)),
        "SERVER_PROTOCOL": "HTTP/1.1",
        "SERVER_NAME": request.url.hostname or "localhost",
        "SERVER_PORT": str(request.url.port or 8080),
        "REMOTE_ADDR": request.client.host if request.client else "127.0.0.1",
    }
    for key, value in request.headers.items():
        env["HTTP_" + key.upper().replace("-", "_")] = value

    proc = await asyncio.create_subprocess_exec(
        "git",
        "http-backend",
        env=env,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate(input=body)

    for sep in (b"\r\n\r\n", b"\n\n"):
        idx = stdout.find(sep)
        if idx != -1:
            headers_raw = stdout[:idx].decode("latin-1")
            body_data = stdout[idx + len(sep) :]
            break
    else:
        return Response(content=stdout, status_code=500)

    headers: dict[str, str] = {}
    status_code = 200
    for line in headers_raw.splitlines():
        if ": " not in line:
            continue
        k, v = line.split(": ", 1)
        if k.lower() == "status":
            status_code = int(v.split()[0])
        else:
            headers[k] = v

    return Response(content=body_data, status_code=status_code, headers=headers)


@router.api_route("/git.git/{path:path}", methods=["GET", "POST"])
async def git_smart_http(request: Request, path: str) -> Response:
    return await _git_http_backend(request, path)


@router.api_route("/git.git", methods=["GET", "POST"])
async def git_smart_http_root(request: Request) -> Response:
    return await _git_http_backend(request, "")
