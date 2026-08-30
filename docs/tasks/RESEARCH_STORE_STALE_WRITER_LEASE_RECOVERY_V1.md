---
task_id: RESEARCH_STORE_STALE_WRITER_LEASE_RECOVERY_V1
task_version: '1.0'
status: IMPLEMENTATION_UNVERIFIED
as_of: '2026-08-31'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 11c9e81c20fe0e55a33c27a62ad83f88c03fa819
  expected_upstream: origin/main
  expected_upstream_oid: 11c9e81c20fe0e55a33c27a62ad83f88c03fa819
  expected_branch: cursor/research-store-stale-writer-lease-recovery-v1
  dirty_mode: ALLOW_REPORTED
objective: Recover expired same-host dead-PID ResearchStore writer leases fail-closed without multi-writer or distributed locks; preserve WRITER_BUSY for live/ambiguous leases.
managed_write_set:
- docs/tasks/RESEARCH_STORE_STALE_WRITER_LEASE_RECOVERY_V1.md
- src/solana_alpha_lab/factory/research_store.py
- tests/test_research_store.py
- catalog/assets/core.yaml
- docs/evidence/research_store_stale_writer_lease_recovery/a1_delivery_completion_evidence_v1.json
- docs/evidence/research_store_stale_writer_lease_recovery/a1_delivery_independent_review_v1.json
- docs/evidence/research_store_stale_writer_lease_recovery/a1_delivery_factory_fit_v1.json
- docs/reports/research_store_stale_writer_lease_recovery/a1_owner_readout_v1.md
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- STALE_LEASE_RECOVERY_ATOMICITY_NOT_PROVEN
- MULTI_WRITER_OR_DISTRIBUTED_LOCK
- PACKAGE_ADOPTION_REQUIRED
- REMOTE_HOST_AUTO_RECOVERY
- PROVIDER_OR_CREDENTIAL_USE
- SECRET_IN_RECEIPTS
- BASE_DRIFT_REQUIRES_REPLAN
context_requirements:
  catalog_asset_ids: []
  l2_roles:
  - ARCHITECTURE_DECISIONS
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
    - docs/decisions/ADR-006-hypothesis-fast-lane-research-data-plane.md
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
---

# RESEARCH_STORE_STALE_WRITER_LEASE_RECOVERY_V1

`SPEC_ROUTE=BOTH` from owner PRD/SSD Desktop backlog. This Git contract is the execution authority. Base rebound from authoring `b5ae41ee7d0507035c8604d4ac8f6856767199d3` to exact `main` `11c9e81c20fe0e55a33c27a62ad83f88c03fa819` after PR #221.

## DECISION_DELTA
Expired same-host dead-PID writer leases reclaim; live/ambiguous fail closed.

## UNCERTAINTY_REMOVED
Whether a crashed writer can permanently wedge ResearchStore behind WRITER_BUSY.

## CAPABILITY_OR_EVIDENCE
Deterministic stale-lease recovery with race-safe takeover proof (T1–T12).

## STOP
RESEARCH_STORE_STALE_WRITER_LEASE_RECOVERY_PASS_READY_FOR_MERGE_GATE

## NEXT
Return to product/research (/hypothesis-forge); no reliability-refactor chain.

# PRD + SSD — RESEARCH_STORE_STALE_WRITER_LEASE_RECOVERY_V1

**Status:** READY_FOR_DIRECT_DELIVERY
**Route:** `DIRECT_CURSOR_DELIVERY` (equally valid for Codex)
**Delivery mode:** `VERTICAL_CAPABILITY_LOOP`
**Model effort:** `SOL_XHIGH`
**Expected base at authoring:** `b5ae41ee7d0507035c8604d4ac8f6856767199d3` (`main`)
**Product area:** Factory / Research Data Plane / `ResearchStore`
**Change class:** bounded reliability/correctness repair

---

## 0. Owner intent

Close one concrete liveness defect in the existing one-writer `ResearchStore` without redesigning the RDP:

> a process that dies after creating `locks/research-writer.lock` must not be able to leave the research write path permanently stuck in `WRITER_BUSY`.

Preserve the existing safety model: **never recover a lock when ownership/liveness is ambiguous**.

This atom is successful when a clearly dead, expired **local** writer lease can be reclaimed deterministically and audibly, while live/non-expired/remote/ambiguous leases remain fail-closed.

This is not a generic distributed lock service and not a multi-writer redesign.

---

# PRD

## 1. Problem / current truth

Current `ResearchStore.writer_lease()`:

1. resolves `locks/research-writer.lock`;
2. creates it with exclusive `xb`;
3. writes `expiry`, `host`, `opened_at`, `pid`, `token` and fsyncs;
4. on an existing destination returns `WRITER_BUSY`;
5. removes the lock only in the normal `finally` path after validating the token.

Therefore:

```text
writer acquires lease
→ process / host-local Python runtime dies before finally
→ file remains
→ every later writer sees existing path
→ WRITER_BUSY forever until manual mutation
```

The lock already carries enough metadata to distinguish many safe-recovery cases, but the acquire path currently does not consume it for recovery.

## 2. Why now

`ResearchStore` is now a reusable substrate for Fast Lane / Hypothesis Forge / append-only research memory. A stale lock is no longer merely an interactive nuisance; it can become an unattended-factory liveness outage.

The fix is small enough to be JIT: one bounded recovery path plus deterministic tests, with no provider, scientific estimand, RDP schema or product behavior change.

## 3. Named consumer

Primary consumers are all existing paths that enter `ResearchStore.writer_lease()`.

Do **not** special-case Hypothesis Forge or Fast Lane. Fix the canonical store boundary once.

## 4. Decision delta

Before:

`existing lock => WRITER_BUSY`, even when canonical metadata proves that the same-host writer is expired and dead.

After:

```text
no lock
→ acquire normally

existing lease, non-expired
→ WRITER_BUSY

existing lease, expired + same host + owner PID proven alive
→ WRITER_BUSY

existing lease, expired + same host + owner PID proven dead
→ bounded stale-lease recovery → retry acquire

remote host / malformed lease / PID state unknown / race ambiguity
→ fail closed; NO recovery
```

## 5. Non-goals

Explicitly forbidden in this atom:

- multi-writer support;
- distributed consensus / Redis / etcd / database locking;
- changing `_LEASE_DURATION` merely to hide the defect;
- automatic recovery of a lock from a different host;
- assuming `expiry < now` alone proves the owner is dead;
- dependency/package adoption solely for PID checking;
- provider/API/RPC/WSS calls;
- credentials;
- scientific evidence changes;
- ResearchEvent schema changes;
- Parquet / manifest publication redesign;
- DuckDB changes;
- destructive cleanup of arbitrary files;
- force/history operations.

## 6. Product requirements

### PR-1 — Preserve one-writer safety

At most one process may successfully own the research writer lease.

Recovery must not create a split-brain writer window.

### PR-2 — Expiry is necessary but not sufficient

A lease is recovery-eligible only when:

- lease document is valid and complete;
- `expiry < now`;
- recorded `host` equals the current host under the existing canonical host representation;
- recorded PID is positively classified `DEAD` by a local, non-destructive probe;
- the exact stale lease being recovered is still the one observed at takeover time.

### PR-3 — PID probing must be non-destructive

Implement a standard-library local PID probe with tri-state semantics:

`ALIVE | DEAD | UNKNOWN`.

It must **never send a terminating signal**.

Important Windows constraint: do not blindly use a POSIX `os.kill(pid, 0)` pattern if it is not demonstrably non-destructive on Windows. Use an appropriate non-destructive Windows process-query mechanism or fail `UNKNOWN`.

The implementation must remain valid on the repository's supported Windows development path and Linux/VPS path.

### PR-4 — Ambiguity fails closed

The following must not auto-recover:

- remote/different host;
- invalid/malformed JSON;
- missing/invalid token, PID, host or timestamps;
- non-expired lease;
- PID `ALIVE`;
- PID `UNKNOWN`;
- lease changed between inspection and recovery attempt;
- unsafe/symlinked paths.

Use typed failures rather than deleting the file.

### PR-5 — Recovery is auditable

Before a stale lock disappears, preserve a bounded recovery artifact outside scientific truth.

The artifact must record only safe metadata, at minimum:

- recovery schema/version;
- old lease token or its safe identifier;
- old opened/expiry timestamps;
- old host/PID;
- classification `EXPIRED_LOCAL_OWNER_DEAD`;
- recovered_at;
- recovery artifact integrity hash if consistent with existing local artifact conventions.

No secrets, physical path strings in durable/public Git evidence, or arbitrary environment values.

Prefer a create-only artifact in a bounded local `locks/recovery/`-style namespace. Do not invent a ResearchEvent for a lock repair unless an existing canonical RDP convention requires it.

### PR-6 — Recovery is race-safe

Two processes encountering the same stale lease must not both convert it into writer ownership.

The implementation must prove a smallest atomic takeover/serialization mechanism using local filesystem primitives already available in the project/runtime.

Do not use `os.replace()` in a way that can silently move/overwrite a newly-created successor lock after a TOCTOU race.

If safe bounded takeover cannot be proven with the current local filesystem contract, STOP `STALE_LEASE_RECOVERY_ATOMICITY_NOT_PROVEN` rather than shipping a heuristic.

### PR-7 — Normal path stays cheap

When there is no lock, behavior and performance should remain materially unchanged.

Do not scan directories or reconstruct RDP state on every acquire.

## 7. Operator behavior

No new owner workflow.

Normal success remains invisible to the operator.

A genuinely ambiguous lock may still return a typed fail-closed condition requiring inspection; that is preferable to unsafe auto-recovery.

## 8. Acceptance outcomes

Terminal PASS:

`RESEARCH_STORE_STALE_WRITER_LEASE_RECOVERY_PASS_READY_FOR_MERGE_GATE`

Allowed evidence terminal:

`STALE_LEASE_RECOVERY_ATOMICITY_NOT_PROVEN` — no PR; return exact blocker.

---

# SSD

## 9. Entry / harness

Start from:

1. `AGENTS.md`
2. `delivery-harness/harness.yaml`
3. `delivery-harness/project-profile.yaml`
4. this exact task contract
5. `docs/agent/DELIVERY_HARNESS_PROTOCOL.md`
6. relevant Factory/RDP context only

Run deterministic harness CHECK/CONTEXT.

If canonical `main` is no longer the expected base, do **not** blindly apply this document to stale code. Inspect the delta limited to `ResearchStore.writer_lease()` and its direct tests:

- if semantics are unchanged, bind the atom to the new exact base and continue;
- if writer-lease semantics materially changed, STOP `BASE_DRIFT_REQUIRES_REPLAN`.

No owner pause for routine branch/test/review/PR/CI steps.

## 10. Required forensic before code

Inspect, at minimum:

- `src/solana_alpha_lab/factory/research_store.py`
- direct ResearchStore tests
- existing filesystem safety / create-only helpers
- existing local recovery-artifact conventions, if any

Prove current behavior with a **focused deterministic test** before broad implementation:

- create a valid expired same-host lease for a definitely dead/nonexistent PID;
- show current store returns `WRITER_BUSY`.

Do not kill a real process to produce the fixture.

If current main already contains equivalent safe stale recovery, STOP `ALREADY_SATISFIED` with proof; do not create redundant code.

## 11. Design shape

Prefer the smallest decomposition, e.g. conceptual helpers:

```text
_parse_writer_lease(...)
_probe_local_pid(...) -> ALIVE | DEAD | UNKNOWN
_classify_existing_writer_lease(...)
_recover_stale_writer_lease(...)
```

Names may differ; semantics may not.

Keep recovery logic close to `ResearchStore` rather than creating a new service layer.

### 11.1 Lease validation

A recoverable lease must parse canonical timestamps and bounded scalar fields.

Do not accept arbitrary additive garbage if existing contract is exact enough to reject it safely. If compatibility with historical lease bytes requires additive tolerance, document/test the precise rule.

### 11.2 Clock

Use an injectable clock or existing testable time boundary where practical. Avoid sleep-based expiry tests.

### 11.3 PID state

Required tri-state behavior:

```text
known active local PID        -> ALIVE
known absent local PID        -> DEAD
permission/platform ambiguity -> UNKNOWN
```

PID probe exceptions must not become `DEAD` by default.

### 11.4 Atomic takeover

The implementation may choose the smallest correct local mechanism after inspecting project/runtime constraints.

Required invariant:

> recovery may only consume the exact stale lease bytes/identity that were validated, and a concurrent successor lock must never be mistaken for that stale lease.

Use deterministic race-shaped tests. Do not rely on timing luck.

## 12. Typed outcomes

Preserve existing `WRITER_BUSY` compatibility where reasonable for a live lease.

Add only the smallest typed errors required for diagnosability, e.g. concepts equivalent to:

- `WRITER_LEASE_INVALID`
- `WRITER_LEASE_REMOTE_OR_AMBIGUOUS`
- `WRITER_LEASE_RECOVERY_FAILED`
- `WRITER_LEASE_RECOVERY_RACE`

Do not explode the public error taxonomy if existing callers only need fail-closed `WRITER_BUSY`; internal reason may be preserved in recovery/test evidence.

## 13. Required tests

Use deterministic tests; no provider/network.

### T1 — ordinary acquire/release unchanged

No lock → acquire → lock exists with valid ownership → release → lock absent.

### T2 — non-expired lease is not recovered

Valid same-host lease, expiry in future → `WRITER_BUSY`; bytes unchanged.

### T3 — expired but owner alive is not recovered

Expired same-host lease + PID probe `ALIVE` → `WRITER_BUSY`; bytes unchanged.

This proves expiry alone does not steal a long-running writer.

### T4 — expired remote-host lease is not recovered

PID must not be used as authority across hosts.

### T5 — malformed/partial lease fails closed

Invalid JSON / missing token / invalid timestamp / invalid PID → no deletion, no writer acquisition.

### T6 — PID UNKNOWN fails closed

Probe ambiguity/permission/platform case → no recovery.

### T7 — killed-writer shape recovers

Valid expired same-host lease + PID `DEAD`:

- old lease preserved as bounded recovery artifact;
- stale lock safely removed/taken over;
- caller acquires a fresh lease with a new token;
- normal release succeeds.

### T8 — recovery artifact is create-only / deterministic enough

A collision or replay cannot overwrite prior recovery evidence.

### T9 — concurrent recovery race

Two contenders inspect the same stale lease:

- exactly one can recover/acquire;
- the other returns busy/race fail-closed;
- no successor lock is moved/deleted by the loser;
- no duplicate ownership.

### T10 — lease changed after inspection

If token/identity changes between inspection and takeover, recovery aborts and preserves the successor.

### T11 — symlink/path safety regression

Recovery path cannot escape data root or operate through a symlinked lock/recovery target.

### T12 — existing append-only write flow still passes

At least one direct ResearchStore transaction test proves manifest-last immutable publication unchanged.

## 14. Vertical Capability Repair Loop

Use exactly one capability loop:

```text
forensic + red test
→ minimal recovery implementation
→ focused T1–T12
→ crash/race-shaped smoke on temp data root
→ bounded mechanical repair(s)
→ repeat focused smoke until PASS
→ risk-routed review
→ Factory Fit / Product Horizon proportional check
→ harness_sync only if derived state actually changed
→ ONE PR
→ exact-head CI
→ exact merge gate
→ post-merge read-back
```

In-scope same-loop repairs:

- Windows/POSIX PID-probe glue;
- serializer/validation errors;
- deterministic clock injection;
- recovery artifact identity;
- race fencing;
- direct regression tests;
- Catalog/generated propagation required by changed primary bytes.

Do **not** split these into separate PRs.

## 15. Stop / replan boundaries

STOP only on a real boundary:

- safe atomic takeover cannot be proven;
- project now requires multi-host/distributed writer semantics;
- package adoption becomes necessary;
- recovery requires destructive mutation beyond the one stale lock/recovery artifact;
- material RDP schema/scientific truth change;
- >3 distinct architectural root causes;
- process budget breach.

Routine test/glue/platform differences stay inside the repair loop.

## 16. Review requirements

Mandatory:

- code review;
- architecture/recovery critic (triggered: concurrency + durability boundary);
- Goal/DoD critic because PASS requires a real killed-writer recovery proof.

Architecture critic must explicitly attack:

1. split-brain possibility;
2. PID reuse / PID probe ambiguity;
3. long-running-but-expired writer theft;
4. TOCTOU where a successor lock appears during recovery;
5. Windows non-destructive PID probing.

No owner-UX critic unless owner-facing CLI/error flow changes.

## 17. Delivery evidence / final return

Return compactly:

```yaml
capability: RESEARCH_STORE_STALE_WRITER_LEASE_RECOVERY_V1
base: <40hex>

forensic:
  stale_lock_reproduced: true
  previous_terminal: WRITER_BUSY

recovery_contract:
  expired_required: true
  same_host_required: true
  pid_dead_required: true
  pid_unknown_recovers: false
  remote_host_recovers: false
  race_safe: true

smoke:
  killed_writer_shape: PASS
  concurrent_recovery: PASS
  successor_preserved: PASS

safety:
  provider_calls: 0
  credential_reads: 0
  scientific_records_rewritten: 0
  destructive_nonlock_mutations: 0

reviews:
  code: PASS
  architecture_recovery: PASS
  goal_dod: PASS

delivery:
  branch: <branch>
  head: <40hex>
  pr: <number>
  exact_head_ci: PASS

stop_reason: RESEARCH_STORE_STALE_WRITER_LEASE_RECOVERY_PASS_READY_FOR_MERGE_GATE
```

Then STOP for the exact owner PR/head merge phrase. After guarded merge, verify `main` + post-merge CI.

## 18. Success effect

After this atom, a clearly dead local writer cannot permanently wedge the Research Data Plane, while uncertainty still fails closed.

**NEXT:** return immediately to product/research work (`/hypothesis-forge` / evidence acquisition). Do not start another reliability refactor merely because this one merged.
