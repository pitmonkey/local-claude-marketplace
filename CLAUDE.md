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
| `main.py` | Root shim — re-exports `app` from `src/marketplace/main.py` |
| `config.py` | Placeholder — real config in `src/marketplace/config.py` |
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

## Code changes

All Python code changes must be handed off to the `python-pro` subagent. Do not write Python inline.
