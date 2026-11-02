# Dual client implementation plan

- [x] Verify generated Git marketplace registration with isolated Codex CLI configuration.
- [x] Derive client compatibility; expose REST fields and client filtering.
- [x] Generate Codex manifests/catalog alongside shared skill packages and Claude snapshot.
- [x] Serialize mutations and preserve committed snapshot on failed generation.
- [x] Update branding, UI compatibility, and installation documentation.
- [x] Run final tests, lint, typing, and review; document external validation limitations.

Constraints: retain Claude identity and routes, preserve pre-existing .env.example changes,
no database migration, no companion files or automatic instruction conversion, no commits.

Verification: 186 tests pass (85% coverage); Ruff and mypy pass. Frozen Docker build succeeds. Codex CLI 0.166.0 registers the HTTP Git marketplace and installs portable@local-ai-marketplace using isolated CODEX_HOME. No paid model invocation or live Claude installation was performed.
