# CLAUDE.md

## Project

local-claude-marketplace — Local Claude Code skill and agent marketplace: browse, search, and install community plugins via a self-hosted web UI and JSON API.

## Commands

```bash
uv run uvicorn src.marketplace.main:app --port 8080 --reload  # run dev server
uv run pytest                                                  # run tests
uv run pytest -q --no-header                                   # quiet test run
uv run ruff check src/                                         # lint
uv run mypy src/                                               # type check
```

## Architecture

| File | Role |
|------|------|
| `src/marketplace/main.py` | FastAPI app with lifespan startup |
| `src/marketplace/config.py` | Settings dataclass, `get_settings()`, `load_repos_yaml()` |
| `src/marketplace/api/marketplace.py` | `GET /marketplace.json` — plugin feed endpoint |
| `src/marketplace/api/rest.py` | REST API under `/api` prefix (plugins, sources CRUD) |
| `src/marketplace/api/ui.py` | Server-rendered HTML routes (Jinja2 + HTMX) |
| `src/marketplace/core/sources.py` | Source indexing logic (clone/pull, scan, upsert) |
| `src/marketplace/core/git_ops.py` | Git clone/pull/sha helpers |
| `src/marketplace/core/scanner.py` | Repo scanner — discovers SKILL.md / agent manifest files |
| `src/marketplace/storage/base.py` | `PluginRepository` protocol, `PluginRecord`, `SourceRecord` |
| `src/marketplace/storage/sqlite.py` | SQLite backend via async SQLAlchemy |
| `src/marketplace/storage/s3.py` | S3 backend via boto3 |
| `src/marketplace/templates/` | Jinja2 HTML templates |

## Scanner layouts

`scanner.py` detects one of three layouts per source:

| Layout | Trigger | What gets indexed |
|--------|---------|-------------------|
| `remote` | `ownership: remote` | Deep-walk entire tree; each `.md` is a plugin; sibling `skill.yaml` supplies rich metadata if present |
| `flat` | `ownership: mine` + no subdirs with `skill.yaml` | Root-level `.md` files only; metadata from YAML frontmatter |
| `proper` | `ownership: mine` + subdirs contain `skill.yaml` or `SKILL.md` | One subdir per plugin; `skill.yaml` for metadata + `SKILL.md` for content |

Versioning: all layouts track a git file SHA per plugin. Counter increments on SHA change (`1.0.0 → 1.0.1`). `proper` layout can override with explicit `version` in `skill.yaml`.

## Testing

- `asyncio_mode = "auto"` in `pyproject.toml` — all test functions can be `async` without decorators
- REST and UI tests use `fastapi.testclient.TestClient` (sync) — not `httpx.AsyncClient`
- S3 tests use `moto[s3]` to mock AWS; no real credentials needed
- `SqliteRepository` with an in-memory or tmp-path DB is the standard fixture for storage tests

## Known constraints

- **SQLite is single-writer** — do not run multiple replicas with `STORAGE_BACKEND=sqlite`; use `s3` backend for horizontal scaling

## Deployment

For Docker, Kubernetes, and S3 backend setup, read `docs/deployment.md`.

## Code changes

All Python code changes must be handed off to the `python-pro` subagent. Do not write Python inline.
