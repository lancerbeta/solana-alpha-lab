---
protocol_id: DELIVERY_CONTEXT_PROTOCOL_V1
status: ACTIVE_IMPLEMENTATION_CANDIDATE
as_of: '2026-08-14'
context_map_id: DELIVERY_CONTEXT_MAP_V1
---

# Delivery Context Protocol

Context is a deterministic read-only projection, not a memory database.

- L0: lean front door and project profile.
- L1: exact task contract, Git identity, exact Catalog anchors and explicit
  roadmap gap when no exact Git roadmap binding exists.
- L2: named registries, provider routes, architecture and candidate evidence.
- L3: historical evidence only for a concrete dispute.

Every selected reference carries role, lane, truth owner, repository-relative
path, stable ID where available and SHA-256. Files above the inline cap are
reference-only. Missing optional truth is explicit; missing required truth
fails. Receipts contain no file bodies, absolute machine paths, secrets or
exception text and are capped by the project profile.

Cursor and Codex generate equivalent selection for identical committed bytes,
apart from the route field and resulting receipt hash. Cloud bundle paths are
never selected as working context. Exact history stays queryable on demand.
