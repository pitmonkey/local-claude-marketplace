# Testing Guide

## Running tests

See [README.md](../README.md#development) for test commands. Pytest enables coverage by default.

## Key patterns

**Async tests** — `asyncio_mode = "auto"` in `pyproject.toml`. All test functions can be `async` without any decorator.

**API tests** — use `fastapi.testclient.TestClient` (sync), not `httpx.AsyncClient`. The TestClient handles async internals transparently.

**S3 tests** — use `moto[s3]` to mock AWS. No real credentials needed. Use `moto.mock_aws()` as in `tests/test_storage_s3.py`.

**Storage fixture** — use `SqliteRepository` with a `tmp_path`-scoped DB as the standard fixture for storage and source tests. Fixtures live in individual test modules, including `tests/test_storage_sqlite.py` and `tests/test_api_ui.py`.

**Env var mocking** — for tests that exercise `requires_auth` sources, use `monkeypatch.setenv("GIT_AUTH_TOKEN", "fake-token")` to inject the token without touching the real environment. To test the missing-token error path, use `monkeypatch.delenv("GIT_AUTH_TOKEN", raising=False)`.
