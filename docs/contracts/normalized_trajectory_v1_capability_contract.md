---
schema: smial.normalized-trajectory-v1-capability
schema_version: '1.0'
capability_id: NORMALIZED_TRAJECTORY_V1
implementation_status: IMPLEMENTED_DORMANT_NOT_EXECUTED
scientific_preregistration: docs/contracts/normalized_trajectory_representation_probe_v1.md
execution_status: NOT_EXECUTED
ordinary_hypothesis_forge: UNCHANGED
current_representation_control: TRAJECTORY_BLIND
current_cohort_scientific_content_accessed: false
provider_calls: 0
deployment: NONE
max_packet_bytes: 16384
max_distinct_motif_tuples: 8
registered_probe_runs_per_control_epoch: 1
---

# NORMALIZED_TRAJECTORY_V1 capability

This is the implementation contract for the dormant MOVE A slice. The frozen
scientific meaning remains in
`docs/contracts/normalized_trajectory_representation_probe_v1.md`; this file
does not amend that preregistration and is not permission to run the probe.

## Boundary

The pure projection accepts only typed, schedule-bound observations and a
validated lifecycle schedule. It uses the member-anchor plus `Y1800` cutoff,
keeps missing or late slots as `M`, normalizes within each member's admissible
prefix history, and emits only an anonymous cohort motif histogram. The frozen
channels are `PRICE`, `LIQUIDITY`, activity volume, and `TRADERS`.
Every projection carries a deterministic `schedule_sha256` binding; the
challenger accepts only the closed representation payload produced by this
projection, never an arbitrary raw mapping.

Taker volume is used only when observed. If taker volume is unavailable and
both buy and sell volume are observed, two fallback channels are emitted. Buy
and sell are never summed or relabeled as taker volume. No interpolation,
imputation, future denominator, mint identity, raw value, quote, holder,
market-cap, or execution field is emitted.

The deterministic histogram retains at most eight motif tuples, with
count-descending and canonical tie ordering. `U`, `D`, and `F` are strict
up/down/exact equality transitions; `M` means either adjacent slot is not
legitimately available. No outcome-tuned threshold is introduced.

The projection accepts only typed numeric values (or explicit null/missing
values) and the frozen ObservationSchedule shape. An observed non-positive
value remains observed but is not admissible for a log ratio, so it produces
`M`; it does not silently activate a different volume channel. A deterministic
M-heavy representative is retained when the eight-tuple bound is reached.

## CONTROL and Challenger

`hfic_representation_probe.py` is a bounded adapter, not a second Forge. It
requires the effective CONTROL terminal and exact hash-bound CONTROL packet,
with `evidence_surface_mode=CURRENT_REPRESENTATION_CONTROL_V1`. The adapter
clones that packet byte-for-byte into a separate challenger envelope and adds
the compact representation under the exact frozen packet key
`normalized_trajectory_v1`. The existing HFIC packet schema and
lifecycle fixture therefore remain readable and unchanged.

The `existing_hfic_lifecycle_fixture_input` bridge carries the representation
as explicit outer context while handing the unchanged nested packet to the
existing fixture. The bridge revalidates the closed envelope, nested packet,
schedule binding, payload hash, search identity, and one-run probe identity
before transport. The representation payload hash is part of both the search
identity and the one-run probe identity, so two payloads cannot share a
CONTROL/epoch identity. Recorded CONTROL packet and memory-baseline hashes are
mandatory; missing or mismatched anchors fail closed.

The envelope binds the same evidence epoch, prompt (`HFIC-V1.2`), prior-memory
baseline, packet hash, and one-run representation identity. It does not rebuild
context from a later ResearchStore state and does not add ordinary Forge search
budget. Any epoch, packet, memory, grounding, or byte-budget drift fails closed.

`representation-status` is read-only. It can return
`CONTROL_REQUIRED`, `NORMALIZED_TRAJECTORY_V1_ELIGIBLE`,
`MARKET_FALSIFIER_FIRST`, `OBSERVABILITY_BLOCKED`, `RUNNER_UP_PAUSE`,
`REPRESENTATION_PROBE_ALREADY_EXISTS`, or
`REPRESENTATION_PROBE_COMPLETE`. It first verifies a current CONTROL receipt
and all session, epoch, packet, memory, mode, and terminal anchors; caller-
declared prior states require a complete baseline-bound probe receipt. None of
these statuses executes a probe or claims alpha.

## Rollback and non-claims

Rollback removes or repairs only this capability and its navigation records.
It does not require collector, ObservationSchedule, seal, verify, import,
cohort release, ordinary Forge, CONTROL, provider, deployment, timer, VPS,
trading, or Workbench changes. A post-CONTROL defect invalidates the comparison
and requires repair plus a new evidence epoch and new CONTROL; it is never
silently repaired against the old baseline.

Git proves implementation and tests only. It does not prove cohort readiness,
CONTROL execution, challenger execution, scientific PASS, alpha, deployment,
or product completion.
