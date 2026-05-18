# local-claude-marketplace

A self-hosted marketplace for [Claude Code](https://claude.ai/code) skills and agents. Point it at any number of Git repositories, and it indexes their skills and agents into a searchable web UI — plus a `marketplace.json` feed that Claude Code can install from directly.

## Why

Claude Code's marketplace protocol lets you add custom marketplace sources in settings. This project implements that protocol so you can:

- **Host your own private marketplace** — share internal skills and agents across a team without publishing them publicly.
- **Aggregate community sources** — pull from `awesome-claude-code-subagents` and other public repos into one searchable index; git changes are tracked and converted to version updates automatically.
- **Browse before you install** — read rendered skill docs, filter by type and tags, search by name or skill content.
- **Own your index** — no dependency on any external service; runs entirely on your infrastructure.
- **Versioned skills via git** — every reindex computes a file SHA; versions increment automatically when content changes, no manual tagging needed.

**Limitation:** Skills and agents must be self-contained Markdown files. Plugins that depend on companion scripts or binaries are not supported.

## Quick Start

Sources can be configured in `config/repos.yaml` or via the UI at runtime. By default the docker image comes bundles with the [VoltAgents](https://github.com/VoltAgent/awesome-claude-code-subagents)

**Docker:**
```bash
# 1. Edit config/repos.yaml to add the repos you want to index (one is included by default)

# 2. Start the server
docker compose up --build

# 3. Open the web UI
open http://localhost:8080
```

**Local (uv):**
```bash
# 1. Edit config/repos.yaml if needed, then:
uv run uvicorn src.marketplace.main:app --host 0.0.0.0 --port 8080 --reload

# 2. Open the web UI
open http://127.0.0.1:8080
```

## Add to Claude Code

Once running, register it as a marketplace source in Claude Code settings:

```
http://localhost:8080/marketplace.json
```

Skills and agents will then be available to browse and install from within Claude Code.

## Screenshots

![Browse skills and agents](docs/images/browse.png)

![Manage sources](docs/images/sources.png)

## Features

- **Web UI** — browse plugins as cards with live search (name, description, and skill content, ranked by match relevance) and tag/type filtering (HTMX, no page reloads)
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

**Note:** If you already manage your own skills repo and add it directly to Claude Code as a marketplace source, you don't need `ownership: mine` — that layout is mainly useful when you want a single centralized marketplace serving multiple users.

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

Edit `config/repos.yaml` directly — `repos.yaml.example` has annotated options for reference. For private repos, set `requires_auth: true` on the source and supply `GIT_AUTH_TOKEN` at runtime — the token is injected ephemerally at clone/pull time and never written to disk or config.

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `DATA_DIR` | `/data` | Persistent data root — git clones and DB |
| `CONFIG_FILE` | `/config/repos.yaml` | Path to `repos.yaml` |
| `PORT` | `8080` | HTTP listen port |
| `STORAGE_BACKEND` | `sqlite` | `sqlite` or `s3` |
| `DB_PATH` | `$DATA_DIR/db/marketplace.db` | SQLite DB path |
| `S3_ENDPOINT` | — | S3-compatible endpoint URL |
| `S3_BUCKET` | `marketplace` | S3 bucket name |
| `S3_ACCESS_KEY` | — | S3 credentials |
| `S3_SECRET_KEY` | — | S3 credentials |
| `GIT_AUTH_TOKEN` | — | PAT for sources with `requires_auth: true` — never stored, injected at clone/pull time |

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

MIT — see [LICENSE](LICENSE)
