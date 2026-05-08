# local-claude-marketplace

<Short description of what this project does.>

## Setup

```bash
cp .env.example .env   # fill in required values
uv sync
```

## Usage

```bash
uv run python main.py
DRY_RUN=true uv run python main.py  # skip side effects
```

## Development

```bash
uv run pytest          # tests
uv run ruff check .    # lint
uv run mypy .          # types
```
