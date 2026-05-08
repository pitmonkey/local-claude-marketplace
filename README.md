# local-claude-marketplace

A self-hosted marketplace for Claude Code skills and agents. Browse, search, and install community plugins via a web UI. Serves a `marketplace.json` endpoint compatible with Claude Code's marketplace protocol.

## Quick Start

```bash
cp config/repos.yaml.example config/repos.yaml
# Edit config/repos.yaml to add your sources
docker compose up --build
open http://localhost:8080
```

## Add to Claude Code

After starting the marketplace, add it as a marketplace source in Claude Code settings:

```
http://localhost:8080/marketplace.json
```

## Configuration

| Env var | Default | Description |
|---------|---------|-------------|
| `DATA_DIR` | `/data` | Where repos and DB are stored |
| `CONFIG_DIR` | `/config` | Where `repos.yaml` is read from |
| `PORT` | `8080` | HTTP port |
| `STORAGE_BACKEND` | `sqlite` | `sqlite` or `s3` |
| `S3_ENDPOINT` | — | S3-compatible endpoint URL |
| `S3_BUCKET` | `marketplace` | S3 bucket name |
| `S3_ACCESS_KEY` | — | S3 access key |
| `S3_SECRET_KEY` | — | S3 secret key |

## Development

```bash
uv sync
uv run uvicorn src.marketplace.main:app --port 8080 --reload
uv run pytest
```
