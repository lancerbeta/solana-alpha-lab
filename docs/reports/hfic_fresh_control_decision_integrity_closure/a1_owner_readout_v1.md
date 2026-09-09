# Owner readout — HFIC_FRESH_CONTROL_DECISION_INTEGRITY_CLOSURE_V1

## Terminal

The first fresh preregistered CONTROL can run without the three confirmed P1
decision-integrity defects: freeze-owned grounding is visible to C1/C2,
downstream branching uses the true final session outcome, and CONTROL mode
fences Prompt A plus the frozen min usable yield before consuming the search.
This is not alpha, not representation proof, not scientific PASS, and not FCF.

## What landed

1. Fresh HFIC-V1.2 freeze emits critic `packet_version=1.4` with freeze-owned
   `required_feature_ids`, `required_capability_ids`, `unresolved_requirements`,
   and `grounding`. Historical 1.3 stays readable and is never upgraded.
   Generator remains `HFIC-V1.2`. Critic result stays `schema_version=1.1`.
2. HFIC classification (packet 1.4 only) requires ExperimentSpec FEAT set
   equality. Unresolved-only candidates cannot finalize `PASS_FAST_LANE_READY`
   via `FAST_LANE_READY` / `REPLAY_AVAILABLE`; they map to
   `KILL_UNBOUND_EVIDENCE`. Honest CHANGE_LANE / DATA_OPTION remain.
3. Prereg `effective_control_terminal` prefers `final_session_terminal`, else
   `critic_terminal`. F3 receipt split is unchanged. C1 kill + C2 PASS does not
   trigger the representation probe.
4. `preflight --control-current-representation` sets
   `evidence_surface_mode=CURRENT_REPRESENTATION_CONTROL_V1`. Same evidence
   epoch, distinct search identity. Skill/operator fence forbids raw current
   lifecycle bodies for Prompt A. Yield `< 10` or missing corpus STOPS before
   session/freeze/Critic. General Forge is unchanged.

## Explicit non-claims

- Not scientific DONE. Not alpha. Not representation sufficiency.
- No autonomous generator. No C3+. No generic ExperimentSpec required-field.
- No live CONTROL. No active-RDP write. No live cohort scientific content.
- Historical packet 1.3 is not rewritten.

## NEXT

Exact-head CI, then merge-readiness, then one owner merge phrase. The owner
does not click GitHub Merge. After merge, the first fresh CONTROL is an
operational slash under `CURRENT_REPRESENTATION_CONTROL_V1`, not this PR.
