---
intent_id: ARCH-INTENT-003
intent_version: '1.0'
status: ACCEPTED_DIRECTION_NOT_IMPLEMENTED
as_of: '2026-08-01'
truth_owner: PRODUCT_VISION
terminal_gate_result: CANONICALIZED_WITH_PATCH
contains_secrets: false
---

# Product and owner operating topology

TASK-21 accepts the Alpha Factory as three coupled planes, not one trading bot
and not one generic data platform.

1. The Research Workbench turns an idea or source into a versioned hypothesis,
   reproducible experiment, evidence and promotion proposal. Tools may change;
   provenance, trials, negative results and decisions stay append-only.
2. The shared evidence and truth plane owns PIT datasets, lifecycle history,
   strategy and execution lineage, position reconciliation and NetReturn. A
   notebook, chat or attractive chart cannot silently change a running
   strategy.
3. The production control plane and Owner Cockpit run remotely when unattended
   operation becomes justified. They expose health, watchlists, signals,
   positions, exits, risk, economics, incidents, recovery and exact owner
   actions as projections over accepted truth.

High-impact commands are a separate authority surface from read access. A
future pause, kill, capital change, strategy activation, signer or transaction
requires identity, policy, audit and its own gate; a dashboard button grants
nothing by itself.

The first production-lite runtime must be portable across ordinary supported
Linux hosts, keep secrets outside the repository, back up into an independent
failure domain and prove a clean rehost with RTO no worse than 12 hours and RPO
no worse than 24 hours. Monitoring loss or unknown reconciliation blocks new
risk. This intent selects no provider and authorizes no purchase or deploy.

Cross-hypothesis portfolio review remains a read-only WATCH until related
evidence spans more than one hypothesis family, the owner asks for a second
manual synthesis, or lifecycle triage creates measurable delay. Its first
output is a recommendation with evidence, never an automatic lifecycle or
trading mutation.

Terminal reconciliation for gate
SMIAL-PRODUCT-VISION-RECONCILIATION-2026-07-31 is
CANONICALIZED_WITH_PATCH. The corresponding roadmap additions are recorded in
docs/roadmap_patches/task21_product_vision_followups_v1.md and require Project
Source activation at the TASK-21 finish boundary before they become active UI
Sources.
