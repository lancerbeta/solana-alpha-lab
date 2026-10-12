# SMIAL_PR398_OPERATING_BOUNDARY_PATCH_V1

Owner explicitly authorized PATCH in PR398; merge and external operation remain separately gated.
Original review proposal/native historical source carriers:
`cd6636427e50ea3c04e9b3d2140f571a9429022e:docs/evidence/smial_trading_core_operational_closure_v1/operating-boundary-patch-review.md`.
The proposal itself was source review, not an executed probe. Actual BEFORE/AFTER facts and embedded native F-A reproducer are in `review-operating-boundary-remediation.json`; all superseded receipts retain exact Git/raw/self refs in `history.json`.

| P1 | Actual native BEFORE | Current owner invariant / regression |
|---|---|---|
| F-A caller-controlled operating scope | ordinary B denied at A=$30/cap=$30; default/False public B accepted an extra attempt, liabilities=$60; restored original EXIT admitted fresh attempt before ACK | PaperPlane derives scope from original durable state/profile/SWITCH. `test_patch_A1_A2_default_false_shared_admission_uses_managed_envelope`, `test_patch_A3_native_restore_fences_new_both_sides_preserves_replay_ack_exit` |
| F-B continuous run | missing/expired successor grant and malformed source/request stopped old healthy EXIT service | finite typed entry/source/per-obligation failures preserve same run; shared-store failures remain fatal. `test_expired_and_missing_successor_grants_keep_same_native_run_servicing_future_origin_exit`, `test_postclaim_entry_response_failure_keeps_original_pending_and_future_old_exit_in_same_run`, shared-store negative |
| cd663642 native public managed fill | genuine public accepted ENTRY had no MODELED ENTRY; originating EXIT denied `EXIT_INVENTORY_WITNESS_CONFLICT`, slot retained | pure original native intent+ENTRY fold reused by quantity owner and SQL/Python release consumers. PAPER/SHADOW native full EXIT releases cap; removed MODELED history without native intent stays UNKNOWN |
| cd663642 missing pending origin | NULL originating epoch raised TypeError before scoped recovery, healthy neighbor stayed OPEN | explicit originating identity verifier raises typed per-obligation conflict; neighbor reconciles; restoring identity reconciles original attempt without resend |

Reproduce current regressions through the existing five native trading test modules, using the locked managed Python environment and disposable marked fixtures. `scripts/prove_trading_core_operational_closure.py --suite --output <owned-receipt>` runs the required whole scope. Current execution count/source hashes/test IDs/C21 metrics and root absence are in `executed-tests.json`; thirteen address-specific scenarios are in `review-managed-native-recovery-remediation.json`.

The accepted common seam is original durable authority, independent of caller flags or mutable projections. No second truth store, synthesized trade history, new schema, unrestricted legacy partial support or blanket exception masking was added. Exact original attempt/result replay, restore fence on both sides, complete cut/ACK pause, genuine legacy and atomic refusal remain required.

Current proof includes191 whole native tests,99 direct consumers, two literal clock probes,24 fresh ordinary CLI commands and five strict read-only canaries. One final isolated required four-role review set targets the frozen candidate; P0/P1 only. A new proven P0/P1 must retain its reproducer and trigger common-seam replan, not another broad suffix campaign.

Readiness still requires exact-head CI and native owner gate. Owner phrase alone can authorize guarded merge after readiness. No working runtime/provider/credentials/deployment/signer/transactions/money authority is granted here.

Final a2cc P1: NULL original qty with retained ENTRY/forged remainder allowed an unproved fresh EXIT quote. Common witness now requires original positive inventory evidence before any new effect; original definitive nonfill and unattempted cancellation reuse their strict witnesses. Native BEFORE/NOT_READY and durable reproducer are retained in review-a2cc-quantity-guard.json and quantity-witness-reproducer.py. The current191/13 proofs cover all12 PAPER/SHADOW native/modeled damage variants, original v1.0/v1.1 nonfill, cancellation negatives and restoration/noresend. The same final review set is completed narrowly on this delta, without another broad campaign.
