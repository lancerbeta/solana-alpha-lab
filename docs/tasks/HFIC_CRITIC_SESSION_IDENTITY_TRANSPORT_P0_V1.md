---
task_id: HFIC_CRITIC_SESSION_IDENTITY_TRANSPORT_P0_V1
task_version: '1.0'
status: IMPLEMENTED_UNVERIFIED
as_of: '2026-08-29'
owner: GOAL_OWNER
allowed_routes:
- DIRECT_CURSOR_DELIVERY
expected_repository: lancerbeta/solana-alpha-lab
git_binding:
  expected_base: edb705c0b47c07a60ee976c489aa576008d72ac1
  expected_upstream: origin/main
  expected_upstream_oid: edb705c0b47c07a60ee976c489aa576008d72ac1
  expected_branch: cursor/hfic-critic-session-identity-transport-p0-v1
  dirty_mode: ALLOW_REPORTED
objective: Transport frozen HFIC session_id inside newly produced packet_version=1.1
  CRITIC_INPUT_PACKET before canonical SHA256 so isolated Independent Critic can
  copy every hypothesis_critic_result_v1 identity field from the packet plus
  read-only repo truth, without weakening finalize fail-closed equality.
managed_write_set:
- docs/tasks/HFIC_CRITIC_SESSION_IDENTITY_TRANSPORT_P0_V1.md
- catalog/schemas/hypothesis_critic_input_v1.schema.json
- catalog/assets/core.yaml
- src/solana_alpha_lab/factory/hfic_session.py
- .agents/skills/independent-hypothesis-critic/SKILL.md
- .cursor/commands/independent-hypothesis-critic.md
- docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md
- tests/test_hfic_session.py
- tests/test_hfic_cli.py
- tests/test_hypothesis_forge_independent_critic_v1.py
- tests/test_hfic_operational_closure_v1.py
- docs/evidence/hfic_critic_session_identity_transport_p0/a1_delivery_completion_evidence_v1.json
- docs/evidence/hfic_critic_session_identity_transport_p0/a1_delivery_independent_review_v1.json
- docs/evidence/hfic_critic_session_identity_transport_p0/a1_delivery_factory_fit_v1.json
external_caps:
  network: false
  credentials: false
  external_system: false
  signing_or_financial_action: false
  cash_spend: false
  deployment: false
stop_conditions:
- PROVIDER_API_RPC_WSS
- EXPERIMENT_EXECUTION
- WALLET_SIGNER_TX_OR_CASH
- WEAKEN_FINALIZE_IDENTITY
- CRITIC_INFERRED_SESSION_ID
- HIDDEN_FORGE_CONTEXT_TO_CRITIC
- BROAD_HFIC_REDESIGN
- MERGE_WITHOUT_EXACT_OWNER_PHRASE
context_requirements:
  catalog_asset_ids: []
  l2_roles:
    - DELIVERY_EVIDENCE
  l3_roles: []
  roadmap_path: null
  exact_role_paths:
    LIFECYCLE: []
    EXTERNAL_ROUTE_KNOWLEDGE: []
    ARCHITECTURE_DECISIONS: []
    DELIVERY_EVIDENCE:
      - docs/evidence/hfic_critic_session_identity_transport_p0/a1_delivery_completion_evidence_v1.json
      - docs/evidence/hfic_critic_session_identity_transport_p0/a1_delivery_independent_review_v1.json
      - docs/evidence/hfic_critic_session_identity_transport_p0/a1_delivery_factory_fit_v1.json
    HISTORICAL_CONTEXT: []
---

# HFIC_CRITIC_SESSION_IDENTITY_TRANSPORT_P0_V1

## Task Outcome Brief

- **Owner decision:** accept this exact message as the approved design.
  Isolated Critic must construct critic-result identity from
  `CRITIC_INPUT_PACKET` plus read-only repo truth. Do not infer
  `session_id`. Do not weaken finalize.
- **Product outcome:** selected-candidate auto-handoff can finalize
  `KILL_MECHANISM` to `SYNTHESIS_COMPLETE` when Critic copies packet
  `session_id`.
- **Named consumers:** Independent Critic, `freeze`, `finalize`,
  operator PROMPT B.
- **Cheapest falsifier:** packet-only critic fixture finalizes
  `KILL_MECHANISM`; wrong `session_id` still raises
  `CRITIC_SESSION_MISMATCH`; v1.1 schema rejects missing `session_id`;
  v1.0 fixture remains readable.
- **Evidence budget:** Git-only PRE-MERGE. Stop before merge.
- **Non-goals:** provider/API/RPC/WSS; experiment; schedule; wallet;
  observation routing; isolation weakening; self-critique; generator.

## SPEC_ROUTE=BOTH

Schema, freeze packet identity, critic operator contract, and
fail-closed finalize tests are one atom.

## DECISION_DELTA

For newly produced `packet_version=1.1`,
`critic_input_packet.session_id == frozen.session_id` and that field
is hashed before SHA256.

## UNCERTAINTY_REMOVED

Whether isolated Critic can finish identity without the outer frozen
envelope: yes, after this transport.

## CAPABILITY_OR_EVIDENCE

v1.1 packet carries `HFIC-SESS-...`; focused tests kill the live
`CRITIC_SESSION_MISMATCH` product-path bug.

## STOP

Exact-head CI, then owner merge gate. Do not merge without the exact
owner phrase bound to this PR and unchanged 40-hex head.

## NEXT

Owner merge phrase after exact-head CI.

## REPLAN_TRIGGER

Repeated identity mismatch after transport, or any request to weaken
finalize equality.
