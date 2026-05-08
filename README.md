# local-claude-marketplace

A self-hosted marketplace for [Claude Code](https://claude.ai/code) skills and agents. Point it at any number of Git repositories, and it indexes their skills and agents into a searchable web UI — plus a `marketplace.json` feed that Claude Code can install from directly.

## Why

Claude Code's marketplace protocol lets you add custom marketplace sources in settings. This project implements that protocol so you can:

- **Host your own private marketplace** — share internal skills and agents across a team without publishing them publicly.
- **Aggregate community sources** — pull from `awesome-claude-code-subagents` and other public repos into one searchable index; git changes are tracked and converted to version updates automatically.
- **Browse before you install** — read rendered skill docs, filter by type and tags, search by name.
- **Own your index** — no dependency on any external service; runs entirely on your infrastructure.

## Quick Start

```bash
# 1. Configure your sources
cp config/repos.yaml.example config/repos.yaml
# Edit config/repos.yaml to add the repos you want to index

# 2. Start the server
docker compose up --build

# 3. Open the web UI
open http://localhost:8080
```

## Add to Claude Code

Once running, register it as a marketplace source in Claude Code settings:

```
http://localhost:8080/marketplace.json
```

Skills and agents will then be available to browse and install from within Claude Code.

## Features

- **Web UI** — browse plugins as cards with live search and tag/type filtering (HTMX, no page reloads)
- **Plugin detail pages** — rendered Markdown docs for each skill or agent
- **Source management** — add, remove, and manually reindex Git repos via the UI or API
- **`marketplace.json` endpoint** — Claude Code-compatible plugin feed at `/marketplace.json`
- **REST API** — full JSON API at `/api` for plugins and sources
- **Two storage backends** — SQLite (default, zero config) or S3-compatible object storage
- **Docker-first** — single container, compose file included

### Supported repo layouts

The indexer handles three layouts, selected per-source via `ownership` and `format`:

**`remote` — third-party repos (e.g. community collections)**

Set `ownership: remote`. The indexer deep-walks the entire repo tree looking for `.md` files. Each file is treated as a plugin. If a sibling `skill.yaml` exists, its structured metadata (name, version, description, tags, author, type) is used; otherwise metadata is read from YAML frontmatter embedded in the `.md` file. Duplicate names across subdirectories are disambiguated with a parent-directory prefix. Use this for repos you don't control, like `awesome-claude-code-subagents`.

Version is auto-managed: each reindex computes a SHA of the file's content; if it changed since the last index, the version counter increments (`1.0.0` → `1.0.1` → ...).

**`mine` + `format: flat` — your own flat repo**

Set `ownership: mine`, `format: flat` (or omit `format` — auto-detected when no subdirs contain `skill.yaml`). The indexer scans only root-level `.md` files. Name, description, and type are read from YAML frontmatter at the top of each file. The simplest layout for a personal or team skills repo: one `.md` file per skill.

Version is auto-managed the same way as `remote`: file SHA tracked across reindexes, counter increments on change. Commit a change to the `.md` file, reindex, and the version bumps automatically.

**`mine` + `format: proper` — structured plugin repo**

Set `ownership: mine`, `format: proper` (or omit `format` — auto-detected when subdirs contain `skill.yaml` or `SKILL.md`). Each plugin is a subdirectory containing:

```
my-skill/
  skill.yaml   ← structured metadata (name, version, description, tags, author, type)
  SKILL.md     ← skill content (or <name>.md, or any single .md file)
```

Version is explicit: set the `version` field in `skill.yaml` and the indexer uses it as-is. If `version` is omitted, the same auto-increment behaviour as `flat` applies. This layout gives full control — bump the version in `skill.yaml` as part of your commit, and the marketplace reflects it on the next reindex.

## Configuration

Sources are defined in `config/repos.yaml`:

```yaml
repos:
  - url: https://github.com/VoltAgent/awesome-claude-code-subagents
    name: awesome-claude-code-subagents
    description: Community Claude Code skills and agents
    ownership: remote   # remote = deep-walk all .md files
    format: auto        # auto-detect repo layout

  - url: https://github.com/yourorg/internal-skills
    name: internal-skills
    description: Company-internal skills
    ownership: mine
    format: flat        # flat = .md files at repo root
```

See `config/repos.yaml.example` for all options.

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `DATA_DIR` | `/data` | Persistent data root — git clones and DB |
| `CONFIG_DIR` | `/config` | Directory containing `repos.yaml` |
| `PORT` | `8080` | HTTP listen port |
| `STORAGE_BACKEND` | `sqlite` | `sqlite` or `s3` |
| `DB_PATH` | `$DATA_DIR/db/marketplace.db` | SQLite DB path |
| `S3_ENDPOINT` | — | S3-compatible endpoint URL |
| `S3_BUCKET` | `marketplace` | S3 bucket name |
| `S3_ACCESS_KEY` | — | S3 credentials |
| `S3_SECRET_KEY` | — | S3 credentials |

## API

| Method | Path | Description |
|---|---|---|
| `GET` | `/marketplace.json` | Claude Code-compatible plugin feed |
| `GET` | `/api/plugins` | List plugins (`?q=`, `?type=`, `?tags=`) |
| `GET` | `/api/plugins/{name}` | Get single plugin |
| `GET` | `/api/sources` | List sources |
| `POST` | `/api/sources` | Add a source |
| `DELETE` | `/api/sources/{id}` | Remove a source |
| `POST` | `/api/sources/{id}/reindex` | Re-pull and reindex a source |

## Deployment

See [docs/deployment.md](docs/deployment.md) for Kubernetes manifests, S3 backend setup, and production configuration.

## Development

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run uvicorn src.marketplace.main:app --port 8080 --reload
uv run pytest
uv run ruff check src/
uv run mypy .
```

## License

MIT
