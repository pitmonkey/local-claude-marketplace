# Shared Claude and Codex catalog

Approved design: retain one searchable catalog and publish separate client manifests.
Publish structurally valid self-contained Markdown skills to both clients by default.
Claude subagents and native Claude manifest records remain Claude-only. Do not rewrite
instructions or copy companion scripts/assets. Expose compatibility and portability notices.
Rename product/distribution/image to local-ai-marketplace, preserving Claude marketplace
identity, existing endpoints, data paths, module name, and actual GitHub repository links.
Serialize source mutations and generate a validated committed snapshot before advancing
its Git reference. Derive compatibility without storage migrations. All Python implementation
is delegated to python-pro. Alternatives rejected: duplicated catalogs and full bundle passthrough.
