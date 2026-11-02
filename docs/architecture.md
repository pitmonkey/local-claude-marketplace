# Architecture

## Components

| File | Role |
| --- | --- |
| `src/marketplace/main.py` | FastAPI app with lifespan startup |
| `src/marketplace/config.py` | Settings dataclass, `get_settings()`, `load_repos_yaml()` |
| `src/marketplace/api/marketplace.py` | `GET /.claude-plugin/marketplace.json` — Claude Code plugin feed (also aliased at `/marketplace.json`) |
| `src/marketplace/api/plugin_serve.py` | Virtual plugin file server — `GET /plugins/{name}/.claude-plugin/plugin.json`, SKILL.md, agent .md |
| `src/marketplace/api/git_serve.py` | Git HTTP smart protocol at `/git.git` via dulwich — Claude Code clones this to install plugins |
| `src/marketplace/api/rest.py` | REST API under `/api` prefix (plugins, sources CRUD) |
| `src/marketplace/api/ui.py` | Server-rendered HTML routes (Jinja2 + HTMX) |
| `src/marketplace/core/sources.py` | Source indexing logic (clone/pull, scan, upsert); reads `GIT_AUTH_TOKEN` env var for `requires_auth` sources; calls `rebuild_plugin_repo` after each full index |
| `src/marketplace/core/plugin_repo.py` | Writes plugin files to `data/plugin_repo/` and commits via dulwich — git repo Claude Code clones |
| `src/marketplace/core/git_ops.py` | Git clone/pull/sha helpers; `_inject_token()` injects PAT into HTTPS URLs ephemerally |
| `src/marketplace/core/scanner.py` | Repo scanner — discovers SKILL.md / agent manifest files |
| `src/marketplace/core/validator.py` | Plugin file validator — `ValidationResult`, `validate_plugin_file()`, `parse_frontmatter()` |
| `src/marketplace/storage/base.py` | `PluginRepository` protocol, `PluginRecord`, `SourceRecord` |
| `src/marketplace/storage/sqlite.py` | SQLite backend via async SQLAlchemy |
| `src/marketplace/storage/s3.py` | S3 backend via boto3 |
| `src/marketplace/templates/` | Jinja2 HTML templates |

## Scanner

`scan_repo()` uses recursive scanning for remote sources. Owned sources select flat scanning when explicitly requested, then manifest scanning when `.claude-plugin/plugin.json` exists, then proper scanning based on the format hint or child `skill.yaml` / `SKILL.md` files; otherwise they use flat scanning. See [configuration.md](configuration.md) for source configuration and versioning.
