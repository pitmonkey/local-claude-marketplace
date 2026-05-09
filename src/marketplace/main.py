from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates

from .api.marketplace import router as marketplace_router
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

    yield

    # Shutdown: nothing to do (aiosqlite closes on GC, boto3 is sync)


app = FastAPI(title="Claude Marketplace", lifespan=lifespan)

# rest_router already carries prefix="/api" internally
app.include_router(marketplace_router)
app.include_router(rest_router)
app.include_router(ui_router)
