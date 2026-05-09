from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from dulwich.errors import NotGitRepository
from dulwich.refs import Ref
from dulwich.repo import Repo as DulwichRepo
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates

from .api.git_serve import create_git_wsgi_app
from .api.marketplace import router as marketplace_router
from .api.plugin_serve import router as plugin_serve_router
from .api.rest import router as rest_router
from .api.ui import router as ui_router
from .config import get_settings, load_repos_yaml
from .core.sources import index_all_sources
from .storage.base import PluginRepository
from .storage.s3 import S3Repository
from .storage.sqlite import SqliteRepository


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown lifecycle manager for the FastAPI application."""
    settings = get_settings()

    # Create data directories
    (settings.DATA_DIR / "repos").mkdir(parents=True, exist_ok=True)
    (settings.DATA_DIR / "db").mkdir(parents=True, exist_ok=True)

    # Init storage backend
    repo: PluginRepository
    if settings.STORAGE_BACKEND == "s3":
        repo = S3Repository(
            endpoint_url=settings.S3_ENDPOINT,
            bucket=settings.S3_BUCKET,
            access_key=settings.S3_ACCESS_KEY,
            secret_key=settings.S3_SECRET_KEY,
        )
    else:
        repo = SqliteRepository(settings.DB_PATH)
    await repo.init()

    # Load and upsert system repos from repos.yaml
    system_sources = load_repos_yaml(settings.CONFIG_FILE)
    for source in system_sources:
        await repo.upsert_source(source)

    # Index all sources
    await index_all_sources(repo, settings.DATA_DIR)

    # Store on app state for routes
    app.state.repo = repo
    app.state.data_dir = settings.DATA_DIR
    app.state.templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

    async def _reindex_loop() -> None:
        try:
            while True:
                await asyncio.sleep(3600)
                await index_all_sources(repo, settings.DATA_DIR)
        except asyncio.CancelledError:
            pass

    reindex_task = asyncio.create_task(_reindex_loop())

    yield

    # Shutdown: cancel the periodic reindex task, then wait for it to finish.
    reindex_task.cancel()
    await asyncio.gather(reindex_task, return_exceptions=True)


app = FastAPI(title="Claude Marketplace", lifespan=lifespan)

# rest_router already carries prefix="/api" internally
app.include_router(marketplace_router)
app.include_router(plugin_serve_router)
app.include_router(rest_router)
app.include_router(ui_router)

# Mount git HTTP smart protocol server at construction time.
# The plugin repo directory is created here so it exists before the first request.
_settings = get_settings()
_plugin_repo_path = _settings.DATA_DIR / "plugin_repo"
_plugin_repo_path.mkdir(parents=True, exist_ok=True)

try:
    DulwichRepo(str(_plugin_repo_path))
except NotGitRepository:
    _dulwich_repo = DulwichRepo.init(str(_plugin_repo_path))
    _dulwich_repo.refs.set_symbolic_ref(Ref(b"HEAD"), Ref(b"refs/heads/main"))

app.mount("/git.git", create_git_wsgi_app(_plugin_repo_path))  # type: ignore[arg-type]
