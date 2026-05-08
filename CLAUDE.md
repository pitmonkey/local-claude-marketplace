# CLAUDE.md

## Project

local-claude-marketplace — <one-line description of what this project does>

## Commands

```bash
uv run python main.py              # normal run
DRY_RUN=true uv run python main.py # skip side effects, print output
uv run pytest                      # run tests
```

## Architecture

| File | Role |
|------|------|
| `main.py` | Entry point |
| `config.py` | Loads `.env` — exposes config vars |

## Code changes

All Python code changes must be handed off to the `python-pro` subagent. Do not write Python inline.
