# ARCH-INTENT-004 Context Capsule Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Register a durable, discoverable architecture intent for a future Factory Context Capsule without implementing the Capsule or adding a new truth system.

**Architecture:** One Markdown intent is the human-readable boundary. One existing Catalog architecture record provides stable-ID discovery and relationships; the repository generator derives Project Map and edge views. A focused unittest binds the document, Catalog record, generated views, activation trigger, and no-authority boundary.

**Tech Stack:** Markdown, YAML, Python 3.13 `unittest`, PyYAML, SHA-256, existing Catalog validator and navigation generator.

## Global Constraints

- Base: merged `main` commit `9a1e325f49e8c5d14851c163ce97d14d2c698904`.
- Atom: `ARCH-INTENT-004_FACTORY_CONTEXT_CAPSULE_AND_WORKBENCH_BOUNDARY_V1`.
- The result is `ACCEPTED_DIRECTION_NOT_IMPLEMENTED`, never implementation evidence.
- Git remains byte truth; Catalog remains discovery/relationship truth; lifecycle registries remain lifecycle truth.
- No vector database, graph database, embeddings, RAG service, UI, provider/API/RPC/WSS call, dependency, wallet, signer, transaction, cash, strategy, PnL, NetReturn or Project Source mutation.
- The Context Capsule remains unimplemented until a separate Entry Gate observes one declared activation trigger.
- Generated Catalog views are produced only by `scripts/generate_navigation.py --write`; never edit them manually.
- One focused test, existing Catalog validation and one tracked-only delivery gate are sufficient validation. No ordinary full gate is added for unchanged candidate bytes.

---

### Task 1: Bind the architecture intent to Catalog discovery and its activation boundary

**Files:**
- Create: `tests/test_arch_intent_004_context_capsule_boundary.py`
- Create: `docs/architecture/intents/ARCH-INTENT-004-factory-context-capsule-and-workbench-boundary.md`
- Modify: `catalog/assets/architecture.yaml`
- Modify: `catalog/catalog_manifest.yaml`
- Modify: `catalog/assets/lifecycle.yaml`
- Generate: `catalog/generated/asset_edges.json`
- Generate: `docs/PROJECT_MAP.md`

**Interfaces:**
- Consumes: `ARCH-INTENT-002`, `ARCH-INTENT-T21-PRODUCT-VISION-001`, `ADR-001`, `catalog/assets/architecture.yaml`, and the existing Catalog navigation generator.
- Produces: Catalog asset `ARCH-INTENT-004`, a content-bound intent document, deterministic generated discovery edges, and one focused semantic test.

- [ ] **Step 1: Write the failing semantic test**

Create `tests/test_arch_intent_004_context_capsule_boundary.py` with this exact structure:

```python
from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
INTENT_PATH = ROOT / "docs/architecture/intents/ARCH-INTENT-004-factory-context-capsule-and-workbench-boundary.md"
ARCHITECTURE_CATALOG_PATH = ROOT / "catalog/assets/architecture.yaml"
MANIFEST_PATH = ROOT / "catalog/catalog_manifest.yaml"
PROJECT_MAP_PATH = ROOT / "docs/PROJECT_MAP.md"
EDGE_PATH = ROOT / "catalog/generated/asset_edges.json"
INTENT_ID = "ARCH-INTENT-004"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frontmatter(path: Path) -> dict:
    parts = path.read_text(encoding="utf-8").split("---", 2)
    if len(parts) != 3:
        raise AssertionError("frontmatter_missing")
    return yaml.safe_load(parts[1])


class ArchIntent004ContextCapsuleBoundaryTests(unittest.TestCase):
    def test_intent_is_content_bound_catalog_discoverable_and_not_implemented(self) -> None:
        self.assertTrue(INTENT_PATH.is_file(), INTENT_PATH)
        document = frontmatter(INTENT_PATH)
        self.assertEqual(document["intent_id"], INTENT_ID)
        self.assertEqual(document["intent_version"], "1.0")
        self.assertEqual(document["status"], "ACCEPTED_DIRECTION_NOT_IMPLEMENTED")
        self.assertEqual(document["projection_kind"], "DERIVED_READ_ONLY_PROJECTION")
        self.assertEqual(document["truth_owners"], {
            "bytes": "GIT",
            "discovery_and_relations": "CATALOG",
            "lifecycle": "REGISTRIES",
        })
        self.assertFalse(document["authority"]["provider_read"])
        self.assertFalse(document["authority"]["wallet_signer_transaction"])
        self.assertFalse(document["authority"]["cash_spend"])
        self.assertFalse(document["authority"]["project_source_mutation"])
        self.assertEqual(document["implementation"], "DEFERRED_UNTIL_TRIGGER")
        self.assertEqual(len(document["activation_triggers_any"]), 3)

        catalog = yaml.safe_load(ARCHITECTURE_CATALOG_PATH.read_text(encoding="utf-8"))
        record = next(item for item in catalog["records"] if item["asset_id"] == INTENT_ID)
        self.assertEqual(record["status"], "ACCEPTED_DIRECTION_NOT_IMPLEMENTED")
        self.assertEqual(record["integrity"]["sha256"], sha256(INTENT_PATH))
        self.assertEqual(
            {item["target_asset_id"] for item in record["relations"]},
            {"ARCH-INTENT-002", "ARCH-INTENT-T21-PRODUCT-VISION-001"},
        )
        self.assertEqual(record["consumers"], ["FACTORY-001", "REG-RESEARCH-001", "TASK-28"])

        manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
        self.assertEqual(manifest["catalog_version"], "0.36.4")
        self.assertEqual(manifest["current_checkpoint"]["assets"], 554)
        self.assertIn(INTENT_ID, PROJECT_MAP_PATH.read_text(encoding="utf-8"))
        self.assertIn(INTENT_ID, EDGE_PATH.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Verify the red state**

Run:

```text
uv run --locked --managed-python python -B -m unittest tests.test_arch_intent_004_context_capsule_boundary
```

Expected: one failure at `INTENT_PATH.is_file()` because no `ARCH-INTENT-004`
document exists yet. Do not add a skip.

- [ ] **Step 3: Create the immutable direction, then bind it to Catalog**

Create `docs/architecture/intents/ARCH-INTENT-004-factory-context-capsule-and-workbench-boundary.md` with YAML frontmatter:

```yaml
intent_id: ARCH-INTENT-004
intent_version: '1.0'
status: ACCEPTED_DIRECTION_NOT_IMPLEMENTED
as_of: '2026-08-08'
truth_owner: USER_GOAL_OWNER
projection_kind: DERIVED_READ_ONLY_PROJECTION
truth_owners:
  bytes: GIT
  discovery_and_relations: CATALOG
  lifecycle: REGISTRIES
implementation: DEFERRED_UNTIL_TRIGGER
activation_triggers_any:
  - TASK28_FIRST_NONEMPTY_HYPOTHESIS_OR_SECOND_REAL_HYPOTHESIS
  - TWO_REPEATED_MANUAL_CONTEXT_RECONSTRUCTIONS
  - ENTRY_GATE_CONTEXT_RESOLUTION_MATERIAL_DELAY
authority:
  provider_read: false
  wallet_signer_transaction: false
  cash_spend: false
  project_source_mutation: false
contains_secrets: false
```

The body must state all of these exact semantics:

- it answers what evidence, constraints, prior attempts and next safe action
  already exist before a hypothesis is started or extended;
- it returns stable asset IDs, paths, hashes, named consumers, lifecycle state,
  evidence-linked missingness and `UNKNOWN`/`CATALOG_GAP` rather than inference;
- it is deterministic and read-only, never a second truth owner;
- `ADR-001` keeps graph databases deferred; vector databases, embeddings, RAG,
  remote services and UI are explicitly excluded;
- the cheapest falsifier is an existing bounded Catalog/lifecycle query; and
- a separate Entry Gate is required before any implementation.

Append one `ARCH-INTENT-004` record to `catalog/assets/architecture.yaml` with:

```yaml
asset_id: ARCH-INTENT-004
record_version: '1.0'
asset_type: architecture_intent
purpose: Accepted boundary for a future deterministic Factory Context Capsule and Research Workbench navigation surface.
status: ACCEPTED_DIRECTION_NOT_IMPLEMENTED
origin: PROJECT_SOURCE
as_of: '2026-08-08'
truth_owner: USER_GOAL_OWNER
location:
  kind: git_path
  logical_uri: repo://docs/architecture/intents/ARCH-INTENT-004-factory-context-capsule-and-workbench-boundary.md
  repository_path: docs/architecture/intents/ARCH-INTENT-004-factory-context-capsule-and-workbench-boundary.md
integrity:
  kind: sha256
  sha256: lowercase 64-character SHA-256 emitted by `Get-FileHash -Algorithm SHA256 docs/architecture/intents/ARCH-INTENT-004-factory-context-capsule-and-workbench-boundary.md`
access:
  mode: read_only
  method: file
  recipe_id: QUERY-CATALOG-RESOLVE-ASSET-001
  network_required: false
  secrets_required: false
relations:
  - relation_type: derived_from
    target_asset_id: ARCH-INTENT-002
  - relation_type: derived_from
    target_asset_id: ARCH-INTENT-T21-PRODUCT-VISION-001
consumers:
  - FACTORY-001
  - REG-RESEARCH-001
  - TASK-28
evidence:
  - evidence_id: EVIDENCE-ARCH-INTENT-004
    kind: user_attestation
    reference: USER_DESIGN_AND_SPEC_APPROVAL_2026-08-08
    result: PASS
classification:
  contains_secrets: false
  contains_raw_data: false
  sensitivity: INTERNAL_NON_SECRET
provenance:
  created_at: '2026-08-08'
  first_reliable_available_at: '2026-08-08'
  imported_by_task: TASK-27
  import_mode: REGISTERED_CURRENT_INTENT
  past_availability_claim: NO_PAST_AVAILABILITY_CLAIM
  retention: TRACKED_REFERENCE
  canonicality: CURRENT_INTENT
  availability_note: Current user-approved direction; it registers a future projection boundary and does not claim Capsule implementation.
```

Calculate the document hash from the working tree. Do not copy a historical
hash. Update the `catalog/assets/architecture.yaml` header `as_of` to
`'2026-08-08'`.

In `catalog/catalog_manifest.yaml`, set `catalog_version: 0.36.4`,
`as_of: '2026-08-08'`, and `current_checkpoint.assets: 554`. Do not add
`ARCH-INTENT-004` to `mandatory_asset_ids`: the focused regression test is the
durable anti-omission guard while the intent remains direction-only.

- [ ] **Step 4: Generate Catalog navigation and prove the green state**

Run exactly:

```text
uv run --locked --managed-python python -B scripts/generate_navigation.py --write
uv run --locked --managed-python python -B scripts/validate_catalog.py
uv run --locked --managed-python python -B -m unittest tests.test_arch_intent_004_context_capsule_boundary tests.test_catalog tests.test_generate_navigation
uv run --locked --managed-python python -B scripts/generate_navigation.py --check
```

Expected: generated edge and Project Map files are changed only by the
generator; Catalog validation reports 554 assets; all focused tests pass; the
final generator check reports `GENERATOR_CHECK: PASS`.

The generated views are content-bound Catalog assets. After the generator
changes either view, refresh only the corresponding `GENERATED-PROJECT-MAP-001`
and `GENERATED-EDGE-PROJECTION-001` SHA-256 records in
`catalog/assets/lifecycle.yaml`, then rerun the strict Catalog validator. This
is required to preserve the existing self-integrity contract; it does not
implement the Context Capsule or add authority.

- [ ] **Step 5: Commit the checked architecture registration**

```text
git add docs/architecture/intents/ARCH-INTENT-004-factory-context-capsule-and-workbench-boundary.md catalog/assets/architecture.yaml catalog/catalog_manifest.yaml catalog/generated/asset_edges.json docs/PROJECT_MAP.md tests/test_arch_intent_004_context_capsule_boundary.py
git diff --cached --check
git commit -m "docs: register ARCH-INTENT-004 context boundary"
```

Expected: one ordinary commit with exactly seven files and pre-commit PASS.

### Task 2: Deliver the intent without widening authority

**Files:**
- Verify only; no new tracked files.

**Interfaces:**
- Consumes: the committed intent registration from Task 1.
- Produces: one tracked-only delivery receipt, pushed task branch, one Draft PR and CI read-back.

- [ ] **Step 1: Verify the exact candidate inventory**

Run:

```text
git status --short --branch
git diff --name-status origin/main...HEAD
git diff --check origin/main...HEAD
```

Expected: the design and plan support documents plus exactly seven Task 1 files;
the working tree is clean; no provider, raw, source-release or generated file
outside the generator pair changed.

**Delivery-gate repair, if observed:** a historical Factory Fit test may preserve
its original receipt while still incorrectly require that the live Catalog asset
count never grows. Replace only that absolute live-count assertion with a
monotonic comparison against the receipt's recorded `after_assets`; retain the
historical receipt unchanged. If that test is itself content-bound by the
Catalog, refresh only its current Catalog SHA-256 record and record version.
This preserves the test's non-authority semantics while allowing later
direction-only registrations.

- [ ] **Step 2: Run the one full delivery gate**

Run:

```text
uv run --locked --managed-python python -B scripts/validate_ci.py --tracked-only-delivery
```

Expected: PASS within 15 minutes, no decision-critical skips, an ignored local
delivery receipt, and no tracked changes.

- [ ] **Step 3: Push and create a Draft PR**

Push without force to `architecture/context-capsule-boundary`. Create one Draft
PR targeting `main` with title:

```text
ARCH-INTENT-004: register Context Capsule boundary
```

The PR body must say: this is a direction-only Catalog registration; Capsule
implementation is deferred to its three explicit triggers; no graph/vector/RAG
system, UI, dependency, provider call, wallet, signer, transaction, cash,
strategy, PnL, NetReturn, Source mutation or authority change occurred.

- [ ] **Step 4: Read back CI and stop before merge**

Read back PR number, exact base/head SHA, six-file Task 1 inventory and CI on
that exact head. Stop before Ready or merge. The owner remains the only merge
gate.

## Plan self-review

- Spec coverage: Task 1 binds every boundary, trigger, truth owner and
  discoverability requirement; Task 2 supplies reproducible delivery only.
- Scope: one direction record and Catalog discovery registration; actual
  Capsule implementation is excluded.
- Consistency: document frontmatter, Catalog record, hash, two `derived_from`
  edges, consumer list, Catalog version/count and generated views are all
  asserted by the same focused test.
- Validation economy: one red/green focused cycle, existing Catalog/generator
  validation and one tracked-only delivery gate; no duplicate full suite.
