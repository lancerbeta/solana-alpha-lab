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

## Capture host (producer)

The schedule kind `smial.opportunity-episode-schedule` runs inside the ordinary
`scripts/observation_schedule.py tick --once` lane after register / authorize /
activate. Template: `configs/opportunity_episodes_jupiter_core_v1.yaml`; its
protection source is a deliberate placeholder, so admissions stay
`UNRESOLVED_SCOPE` until commissioning registers real assignment documents under
`<data_root>/protection/assignments/`.

* Stop intake: let `stops_admitting_at` pass or pause the activation; admitted
  obligations continue while DRAINING and complete when every slot is terminal.
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

The focus becomes `OPPORTUNITY_EPISODES:<FOCUS>`; use that stored focus for
`forge-run`. Questions use `smial.hfic-temporal-query` 1.1 with
`population=OPPORTUNITY_EPISODES`, E-points, at most 8 points, the universe
policy owner for holders/liquidity minima and `lte` predicates for ceilings.
CONTROL mode is not supported for this collection. Saved readback loads no
values; registered replay recomputes from the frozen recipe and release files.

## Not here

No provider smoke, deploy, live activation, real science, retention/eviction or
volume features. Category 5m routes are a `PROVIDER_ROUTE_REGISTRY_GAP` until
commissioning records evidence.
