# OPPORTUNITY_EPISODES operator runbook V1

Contract: `docs/contracts/opportunity_episodes_jupiter_v1.md`.
Live lane: **DISABLED**. Nothing below activates collection; that is a separate
OPERATE commissioning decision (route registry evidence for the category 5m
routes, real protection assignment inventory, host envelope, canary budget).

## What it is

An episode is one committed admission of a Jupiter-nominated mint into the
collection. Its anchor `T0` is the admission commit instant (`NOMINATION_T0`),
not birth or pool creation. Each episode has a frozen 139-point schedule
(`E0` witness, 5-minute grid to 6 h, hourly to 72 h). Every committed
admission stays in the denominator; gaps stay explicit and never become zero.

## Capture host (producer) — OPERATE commissioning gate only, not an owner step in this slice

The schedule kind `smial.opportunity-episode-schedule` runs inside the ordinary
`scripts/observation_schedule.py tick --once` lane after register / authorize /
activate. Template: `configs/opportunity_episodes_jupiter_core_v1.yaml`; its
protection source is a deliberate placeholder, so admissions stay
`UNRESOLVED_SCOPE` until commissioning registers real assignment documents under
`<data_root>/protection/assignments/`.

* Stop intake early (safe drain), without waiting for `stops_admitting_at`:

```text
uv run --locked --managed-python python -B scripts/observation_schedule.py stop-intake --schedule-sha256 <sha> --activation-id <id> --runtime-config <runtime-config> --data-root <rdp>
```

  It closes new admissions at that instant through the same ACTIVE → DRAINING
  transition the natural boundary uses. Already committed episodes keep
  collecting and publishing, and the activation completes once every obligation
  is terminal. Rerun the same command after a crash: it is idempotent and
  repairs a missing evidence event. A paused activation must be resumed first.
  `pause` is not a stop-intake: it also stops the committed obligations. The
  schedule sha and activation id come from `observation_schedule.py status`;
  if a tick holds the writer lease the command answers `WRITER_BUSY`: retry.
* Recovery: the next tick republishes the outbox, recovers completed calls from
  the call ledger and turns intent-without-result into
  `ATTEMPT_OUTCOME_UNKNOWN`; it never re-requests a past slot.
* Freeze one mature cohort (UTC admission day, all slots terminal, outbox
  published):

```text
uv run --locked --managed-python python -B scripts/discovery_evidence_release.py capture-freeze-export --collection OPPORTUNITY_EPISODES --observation-rdp <rdp> --ops-store <ops.sqlite>
```

## Workstation (consume)

```text
uv run --locked --managed-python python -B scripts/discovery_evidence_release.py unpack-next-live-cohort --collection OPPORTUNITY_EPISODES --max-cohorts 1 --data-root <explicit-data-root>
```

Default path: SSH capture on the remote host, transfer of only missing verified
files, local seal (release 1.2) → verify → import into
`datasets/opportunity_episodes_corpus/`. With a capture packet already on disk:
add `--capture-packet <packet.json> --source-rdp <rdp> --mirror-rdp <mirror>`.
A repeated import of identical bytes returns `PASS_ALREADY_PRESENT_EXACT`. The
command never starts Forge; it prints the generated population card.

## Ordinary Forge

```text
uv run --locked --managed-python python -B scripts/hypothesis_forge.py --data-root <data-root> preflight --collection OPPORTUNITY_EPISODES --owner-focus <FOCUS>
```

The focus becomes `OPPORTUNITY_EPISODES:<FOCUS>` (`--owner-focus
OPPORTUNITY_EPISODES:<FOCUS>` without `--collection` is equivalent; the default
focus is `AUTO`). Then:

```text
uv run --locked --managed-python python -B scripts/hypothesis_forge.py --data-root <data-root> forge-run --collection OPPORTUNITY_EPISODES --owner-focus <FOCUS>
```

A query whose `population` differs from the focus collection stops before any
value with `FOCUS_POPULATION_MISMATCH`. Questions use `smial.hfic-temporal-query` 1.1 with
`population=OPPORTUNITY_EPISODES`, E-points, at most 8 points, the universe
policy owner for holders/liquidity minima and `lte` predicates for ceilings.
CONTROL mode is not supported for this collection. Saved readback loads no
values; registered replay recomputes from the frozen recipe and release files.

## If a command fails

| Code | Meaning | Next |
| --- | --- | --- |
| `EPISODE_BATCH_NOTHING_MATURE` (PASS) | no mature unimported cohort yet | wait for the next UTC day |
| `MIRROR_INCOMPLETE` | transfer interrupted | rerun the same command |
| `MARKET_EVIDENCE_BASIS_INCOMPLETE` at preflight | an import was interrupted after labels, before lineage | rerun the same unpack command (not preflight); it reuses the recorded import instant |
| `RELEASE_HASH_MISMATCH`, `MIRROR_CONFLICT`, `CLOSURE_COHORT_MISMATCH` | bytes differ from the sealed or captured identity | stop; do not import |
| `COLLECTION_PACKET_MISMATCH` | packet from another collection | use an OPPORTUNITY_EPISODES capture packet |
| `CAPTURE_PACKET_REQUIRES_SOURCE_AND_MIRROR_RDP` | packet given without its transport roots | add `--source-rdp` and `--mirror-rdp` |
| `FROZEN_PROTECTION_*` (missing, unreadable, hash/identity/set mismatch) at export, seal or verify | the protection assignment frozen at admission is absent, damaged or differs from its pin | stop; restore the exact registered assignment file (never regenerate it) and rerun |
| `ACTIVATION_NOT_ACTIVE` at stop-intake | the activation is paused (run `observation_schedule.py resume` with the same ids, then repeat stop-intake) or aborted (nothing to stop) | see meaning |
| `STOP_INTAKE_ALREADY_DRAINING` / `STOP_INTAKE_COMPLETE_REPLAY` | intake is already closed | no action |
| `STOP_INTAKE_EPISODE_SCHEDULE_ONLY` | the ids point at a non-episode schedule | check `--schedule-sha256` |
| `STOP_INTAKE_CLOCK_BEFORE_LAST_ADMISSION` / `STOP_INTAKE_ROLLOVER_PENDING` | the clock is earlier than an existing admission, or a rollover cutover is pending | fix the clock / wait for the cutover, then repeat |
| `FOCUS_POPULATION_MISMATCH` | question population differs from the focus collection | use `population=OPPORTUNITY_EPISODES` with an episode focus |

## Not here

No provider smoke, deploy, live activation, real science, retention/eviction or
volume features. Category 5m routes are a `PROVIDER_ROUTE_REGISTRY_GAP` until
commissioning records evidence.
