# Configuration

## Supported repo layouts

Sources select recursive remote scanning or an owned-repository layout via `ownership` and `format`. An optional `subpath` limits scanning to a source subdirectory.

**`remote` — third-party repos (e.g. community collections)**

Set `ownership: remote`. The indexer deep-walks the entire repo tree looking for `.md` files. Each file is treated as a plugin. If a sibling `skill.yaml` exists, its structured metadata (name, version, description, tags, author, type) is used; otherwise files must pass validation, including frontmatter with a name and a Markdown body longer than 50 characters. Common documentation filenames are skipped. Duplicate names across subdirectories are disambiguated with a parent-directory prefix. Use this for repos you don't control, like `awesome-claude-code-subagents`.

A sibling `skill.yaml` can supply an explicit version. Otherwise version is auto-managed: each reindex computes a SHA; if it changed since the last index, the version counter increments (`1.0.0` → `1.0.1` → ...).

**`mine` + `format: flat` — your own flat repo**

Set `ownership: mine`, `format: flat` (or omit `format` — auto-detected when no subdirs contain `skill.yaml` or `SKILL.md`). The indexer scans only root-level `.md` files. Name, description, and type are read from YAML frontmatter at the top of each file. The simplest layout for a personal or team skills repo: one `.md` file per skill.

Version is auto-managed the same way as `remote`: file SHA tracked across reindexes, counter increments on change. Commit a change to the `.md` file, reindex, and the version bumps automatically.

**`mine` + `format: proper` — structured plugin repo**

Set `ownership: mine`, `format: proper` (or omit `format` — auto-detected when subdirs contain `skill.yaml` or `SKILL.md`). Each plugin is a subdirectory containing:

```
my-skill/
  skill.yaml   ← structured metadata (name, version, description, tags, author, type)
  SKILL.md     ← skill content (or <name>.md, or any single .md file)
```

Version is explicit: set the `version` field in `skill.yaml` and the indexer uses it as-is. If `version` is omitted, the same auto-increment behaviour as `flat` applies. This layout gives full control — bump the version in `skill.yaml` as part of your commit, and the marketplace reflects it on the next reindex.

**`mine` + manifest — native plugin metadata**

A root `.claude-plugin/plugin.json` selects a single plugin record from manifest metadata, unless `format: flat` is explicit. The manifest version is used when supplied; otherwise versions increment on manifest SHA changes. Companion scripts and binaries remain unsupported by the generated feed.

**Note:** If you already manage your own skills repo and add it directly to Claude Code as a marketplace source, you don't need `ownership: mine` — that layout is mainly useful when you want a single centralized marketplace serving multiple users.

## Source configuration

Sources are defined in `config/repos.yaml`:

```yaml
repos:
  - url: https://github.com/VoltAgent/awesome-claude-code-subagents
    name: awesome-claude-code-subagents
    description: Community Claude Code skills and agents
    ownership: remote # remote = deep-walk all .md files
    format: auto # auto-detect repo layout

  - url: https://github.com/yourorg/internal-skills
    name: internal-skills
    description: Company-internal skills
    ownership: mine
    format: flat # flat = .md files at repo root
```

Edit `config/repos.yaml` directly — `config/repos.yaml.example` has annotated options for reference. For private repos, set `requires_auth: true` on the source and supply `GIT_AUTH_TOKEN` at runtime — the token is injected ephemerally at clone/pull time and never written to disk or config.

### Environment variables

See [deployment-contract.yaml](deployment-contract.yaml) for environment keys, required flags, and defaults. `DB_PATH` defaults to `db/marketplace.db` under `DATA_DIR`. S3 credentials may come from the boto3 credential chain.

`PORT` is read into settings, but the supplied commands explicitly bind Uvicorn to port 8080. Change the Uvicorn command and port mapping to use another port. Set `LOG_LEVEL` in the process environment before startup; logging is configured before `.env` is loaded.

## Client compatibility

Self-contained skills with safe names and YAML name/description fields are eligible
for Codex by default. Claude subagents and native manifests remain Claude-only.
Compatibility is structural; Claude-specific instructions may need adaptation.
Companion files are not included. Existing source configuration requires no migration.
