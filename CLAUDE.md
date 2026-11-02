# CLAUDE.md

## Project

For the project overview and development commands, read `README.md`.

## Architecture

For the component map, read `docs/architecture.md`.

## Scanner layouts

For source layouts and versioning, read `docs/configuration.md`.

## Testing

For test patterns, fixtures, and mocking setup, read `docs/testing.md`.

## Known constraints

- **SQLite is single-writer** — do not run multiple replicas with `STORAGE_BACKEND=sqlite`; use `s3` backend for horizontal scaling
- **Env var reads are contract-bound** — every `os.getenv` / `os.environ` read in `src/` must have an entry in `docs/deployment-contract.yaml`; `tests/test_deployment_contract.py` AST-derives the list from code and fails CI on drift in either direction

## Deployment

For Docker, Kubernetes, and S3 backend setup, read `docs/deployment.md`.

## Code changes

All Python code changes must be handed off to the `python-pro` subagent. Do not write Python inline.
