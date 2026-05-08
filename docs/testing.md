# Testing Guide

## Running tests

```bash
uv run pytest                # full run with coverage
uv run pytest -q --no-header # quiet
```

## Key patterns

**Async tests** — `asyncio_mode = "auto"` in `pyproject.toml`. All test functions can be `async` without any decorator.

**API tests** — use `fastapi.testclient.TestClient` (sync), not `httpx.AsyncClient`. The TestClient handles async internals transparently.

**S3 tests** — use `moto[s3]` to mock AWS. No real credentials needed. Decorate with `@mock_s3` or use the `moto` context manager.

**Storage fixture** — use `SqliteRepository` with a `tmp_path`-scoped DB as the standard fixture for storage and source tests. See `tests/conftest.py` for existing fixtures.
