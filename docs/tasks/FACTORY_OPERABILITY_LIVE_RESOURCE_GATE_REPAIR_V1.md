---
task_id: FACTORY_OPERABILITY_LIVE_RESOURCE_GATE_REPAIR_V1
task_version: "1.1"
status: READY
as_of: "2026-10-03"
owner: GOAL_OWNER
allowed_routes:
  - DIRECT_CODEX_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: 94b284534b6ad55a95002d51b9d04b4a5ced6bde
  expected_upstream: origin/main
  expected_upstream_oid: 94b284534b6ad55a95002d51b9d04b4a5ced6bde
  expected_branch: codex/factory-operability-live-resource-gate-repair-v1
  dirty_mode: ALLOW_REPORTED
objective: >-
  Repair the measured resource bottleneck in Factory operability watch and pulse
  with a small bounded implementation, prove unchanged monitoring truth and
  growing-history cost under a Linux cgroup, and deliver a checked PR for a
  separate post-merge live commissioning.
managed_write_set:
  - docs/tasks/FACTORY_OPERABILITY_LIVE_RESOURCE_GATE_REPAIR_V1.md
  - src/solana_alpha_lab/factory/observation_schedule_store.py
  - src/solana_alpha_lab/factory/research_store.py
  - src/solana_alpha_lab/factory/observation_schedule_lifecycle.py
  - src/solana_alpha_lab/factory/collector_read_model.py
  - src/solana_alpha_lab/factory/collector_operational_packet.py
  - src/solana_alpha_lab/factory/operability_watch.py
  - src/solana_alpha_lab/factory/collector_owner_pulse.py
  - scripts/factory_operability_watch.py
  - scripts/collector_owner_pulse.py
  - scripts/factory_prepare_operability_index.py
  - scripts/factory_cgroup_peak.py
  - configs/factory_remote_ops/factory-operability-watch.service
  - configs/factory_remote_ops/factory-collector-owner-pulse.service
  - tests/test_factory_operability_live_resource_gate_repair_v1.py
  - tests/operability_bounded_call_profile.py
  - .github/workflows/factory-operability-resource-proof.yml
  - .github/workflows/ci.yml
  - scripts/validate_ci.py
  - tests/test_ci.py
  - docs/operator/FACTORY_UNATTENDED_OPERABILITY.md
  - docs/evidence/factory_operability_live_resource_gate_repair/a1_linux_profile_v1.json
  - docs/evidence/factory_operability_live_resource_gate_repair/a1_delivery_completion_evidence_v1.json
  - docs/evidence/factory_operability_live_resource_gate_repair/a1_delivery_independent_review_v1.json
  - docs/evidence/factory_operability_live_resource_gate_repair/a1_delivery_factory_fit_v1.json
  - docs/reports/factory_operability_live_resource_gate_repair/a1_owner_readout_v1.md
  - catalog/assets/core.yaml
  - catalog/assets/lifecycle.yaml
  - catalog/catalog_manifest.yaml
  - catalog/generated/asset_edges.json
  - docs/FACTORY_SEMANTIC_MAP.md
  - docs/OPERATOR_NAVIGATION.md
  - docs/PROJECT_MAP.md
  - docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json
required_review_roles:
  - CODE_REVIEWER
  - GOAL_DOD_CRITIC
  - ARCHITECTURE_CRITIC
  - OWNER_UX_CRITIC
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
  - LINUX_CGROUP_PROFILE_UNAVAILABLE_OR_THRESHOLD_FAILED
  - MEASURED_BOTTLENECK_OUTSIDE_BOUNDED_WRITE_SET
  - MONITORING_SEMANTICS_OR_UNKNOWN_CANNOT_BE_PRESERVED
  - LIVE_VPS_CAMPAIGN_TIMER_OR_TELEGRAM_MUTATION_REQUIRED
  - EXACT_OWNER_MERGE_PHRASE_AFTER_CI_AND_MERGE_READINESS
context_requirements:
  catalog_asset_ids: []
  l2_roles:
    - ARCHITECTURE_DECISIONS
    - DELIVERY_EVIDENCE
  l3_roles: []
  roadmap_path: null
  exact_role_asset_ids:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE: []
    HISTORICAL_CONTEXT: []
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS:
      - docs/tasks/FACTORY_OPERABILITY_BOUNDED_CALL_DIAGNOSTICS_V1.md
    DELIVERY_EVIDENCE:
      - docs/evidence/factory_operability_live_resource_gate_repair/a1_delivery_completion_evidence_v1.json
      - docs/evidence/factory_operability_live_resource_gate_repair/a1_delivery_independent_review_v1.json
      - docs/evidence/factory_operability_live_resource_gate_repair/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# FACTORY_OPERABILITY_LIVE_RESOURCE_GATE_REPAIR_V1

## SPEC_ROUTE

`BOTH` — compact PRD and design in this contract. Entry gate uses the existing
Delivery Harness, Git/gh, uv, SQLite and Linux cgroup facilities. No new service,
dependency, connector, plugin or automation.

## Outcome and vertical proof

Owner decision: whether one Git repair is safe to merge and later commission.
Consumers: 15-minute watch, daily owner pulse and the sole operator. First,
profile each watch stage on Linux with the production 768 MiB/180 s guard,
recording only elapsed time, cgroup peak, row counts and stage names. Identify
the dominant stage before editing runtime code. A missing profile is UNKNOWN,
never evidence that the earlier 768 MiB peak was harmless.

Patch only the measured growth source. The likely candidate is the unindexed
`call_ledger` timestamp UDF scan; this is a hypothesis until stage measurements.
No full historical call/payload walk on each cycle, silent bounded tail, cursor that skips
late updates, broad table migration on the live store, or limit increase.
Existing incident/recovery, invalid/equal/future timestamps and UNKNOWN behavior
must remain exact. Prefer an indexed bounded projection if its migration can be
shown safe on a copy; otherwise replan the smallest equivalent fix.

Measured entry evidence (one read-only VPS diagnostic unit, 2026-10-03):
`call_diagnostics` 16.170 s/48,008 rows examined/1,162 returned; three
immutable activation checks ~17 s each; successor continuity 32.643 s;
whole watch 106.816 s and process peak 193,110,016 bytes while cgroup peak
reached 805,306,368 bytes. Repair both repeated immutable reads within one
packet and the unindexed call timestamp scan. Treat cgroup file cache as part
of the gate; process RSS alone is insufficient.

Prove a vertical loop: frozen-base behavior fails a focused growing-history bounded-read
test; repaired watch and pulse pass through their real CLIs on a representative
synthetic store and Linux cgroup with peak <512 MiB and wall <120 s each;
double old history with the recent observations fixed and show cost does not
grow materially with irrelevant history. Compare incident/recovery and UNKNOWN
outputs with frozen cases. Save a payload-free machine receipt with fixture
size, cgroup limit, peak, wall, actual index candidates/UDF evaluations and commands. Failure/absence is
`NOT_READY`, not a claim based on Windows RSS or a unit file alone.
The Linux proof runs in the candidate PR workflow before merge-readiness;
The same standard-library kernel peak reader runs after ordinary report
oneshots, before systemd disposes their cgroup; readback is bound to the
specific InvocationID. This closes the measured Ubuntu completed-unit
MemoryPeak=[not set] gap without a new daemon, dependency or limit increase.
the required Repository validation aggregator depends on its reusable job.
Affected-path selection fails closed and defaults to running when no base is
available; an absent, failed, skipped or cancelled resource job denies validate.
draft CI overlap is permitted without claiming that an unexecuted gate passed.
Immutable manifest headers are enumerated once per packet; only relevant
partitions are verified, once, and no cross-cycle cache owns scientific truth.
State-transition proofs omit the member predecessor search they do not consume;
scientific member reconstruction retains its existing default search. The growth
fixture includes old member partitions for foreign schedule/activation identities.
This residual metadata cost is explicit and tested on doubled manifest history.
An existing populated store receives the built-in SQLite expression index only
through explicit backed-up commissioning, with a 5-second lock wait, limited
SQLite cache and a 120-second progress deadline. Missing/wrong index yields
UNKNOWN; no recovery full scan. Old writer rollback must still INSERT/UPDATE.
The indexed resource proof covers producer UTC timestamps and comma/empty
fraction compatibility forms. Other Python-valid ISO forms and malformed times
remain conservative header candidates; exact Python filtering precedes payload
projection. This anomaly cost is not claimed constant for arbitrary corrupt
or externally rewritten timestamp history.

## Boundaries and delivery

Git change only through exact-head CI, independent code/goal/architecture/owner
reviews, Catalog propagation and Delivery Harness merge-readiness. No live
VPS, campaign, provider, Telegram or timer mutation; post-merge commissioning
is a separate exact atom. Do not enable the three intentionally disabled timers.
Report residual UNKNOWNs and a simple rollback plan. Stop at the machine
rendered exact owner merge phrase, then guarded merge only after that phrase.

`DECISION_DELTA`: replace the failed live resource gate with measured evidence.
`UNCERTAINTY_REMOVED`: stage cost, history scaling, cgroup peak and monitoring
semantic parity. `CAPABILITY_OR_EVIDENCE`: one PR plus reproducible receipt.
`STOP`: missing Linux cgroup proof, threshold miss, or semantic regression.
`NEXT`: separate exact post-merge commissioning of target code and report timers.
`REPLAN_TRIGGER`: second unbounded hotspot, unsafe migration or exceeded proof
budget; shrink the patch instead of building a new monitoring platform.
