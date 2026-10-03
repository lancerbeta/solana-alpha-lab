# FORGE_DOWNSIDE_READOUT_V1 — bounded evidence

Base: `8e72dbb492d1d430231f9e225e6000be0e1d6922`.
Design: owner-approved `FORGE_DOWNSIDE_READOUT_V1_PRD_SSD.md`, calibration
`SMIAL-FORGE-CALIB-20261003-G1G6`, calibration gold SHA
`57444d7ffb0f634ea4d2b5075cee1da498c2a94c7c1df76449a1d99b4fa98866`.
Candidate head, CI and exact owner phrase are live delivery-gate outputs,
never inferred from this document.

## Product boundary and earliest falsifier

One fixed `DOWNSIDE_DESCRIPTIVE_V1` block describes existing admitted raw
PRICE_RELATIVE_PROXY samples. Type-7 linear quantiles and fractional-mass
empirical lower-10% ES have dimensionless return units. No new scientific
target, threshold search, budget, feature, dependency or automatic verdict.

G3 first established that equal medians hide event-frequency differences.
The second cheap public probe of closed D2 initially stopped at
`CALCULATION_REVISION_NOT_REQUIRED`, then exposed `ORDINARY_OPERATION_SLOT_CLOSED`.
V5 is now an explicit coherent-V4, source/spec/input/market-bound append-only
readout revision. The closed-slot carveout does not authorize a new look.

| G3 raw return statistic | Matched | BASE_X baseline |
|---|---:|---:|
| observed / missing | 10 / 0 | 40 / 0 |
| mean | -0.15 | -0.05 |
| median | 0 | 0 |
| rate <= -0.20 | 0.30 | 0.10 |
| rate <= -0.50 | 0.30 | 0.10 |
| ES10 | -0.50 | -0.50 |
| negative mass | 1.5 | 2.0 |
| worst negative share | 1/3 | 1/4 |

Baseline includes matched. Different frequency with equal ES is a descriptive
distinction, not independent control, executable veto benefit, alpha or NetReturn.

## Five vertical proofs

1. **NUMERIC_GOLD / PIT_SNAPSHOT_REGRESSION / EMPTY_AND_MISSING.** Production
   calculation on literal G3 arrays; fractional n=15 ES=-5/6, zero/positive/n=1,
   all missing, literal threshold boundaries and nonfinite typed stop. Existing
   temporal PIT suites exercise both observation clock policies, duplicates,
   integrity conflicts, late/future rows and empty admitted cohorts. Existing
   numeric fields are compared explicitly; no expected result computed by a
   second call to the downside helper.
2. **ACTUAL_PROMPT_A_CRITIC_PACKET.** Public synthetic execution/persist → cold
   production preflight → selected freeze → validated Critic packet. Matched,
   baseline, support, median and downside are embedded. The Critic needs no
   evaluator scratch or external file to see this comparison. The normal empty
   candidate branch freezes NO_WORTHY separately. Immutable result references
   remain complete; compact details have explicit bounds, never silent loss.
3. **READOUT_REVISION_LIFECYCLE_UNCHANGED / REJECTED_CORRECTION_ZERO_WRITE.**
   Closed coherent V4 public correction appends exactly one revision. Wrong
   source hash, spec, frozen input, old numeric drift and a new operation request
   refuse before records/intents/reservations/lifecycle writes. Faults before
   append leave the committed inventory equal; reply loss after append converges
   through existing saved-result machinery without reevaluation. Old records,
   sessions, terminal, reservations and complete budget stay unchanged.
   **ORDINARY_CRASH_REPLAY** separately persists MAIN then crashes before landing:
   cold replay recovers OPEN→PAUSED_CAP through the existing `note_look_landed`,
   reports its one operation write and next_action, with zero new evaluator/look;
   the next repeat is idempotent. Closed result revision never invokes landing.
4. **REAL_D2_ISOLATED_COPY_PROOF.** `d2_isolated_acceptance.json` binds exact
   saved source/spec/input plus before/after canonical byte+size+mtime digest.
   Only datasets and committed research metadata needed to close D2 were copied,
   without hardlinks or whole-RDP clone. Public correction, cold readback and
   retry used the actual saved operation, unchanged cap, journal and terminal.
   Saved operation has no public spec; the canonical result wrapper was
   mechanically flattened and exact spec SHA verified, as documented in the
   runbook. Old matched=111, observed=105, mean=-0.06902620062974765, median=0
   remained equal. One scratch revision, zero real scientific writes. Raw market
   rows and mutable operational inventories remain outside Git.
5. **LLM_BLIND_CASE_RESULTS.** One primary native isolated batch received only
   production Prompt B and four production packets, without gold or PRD. It
   distinguished G3 frequency/severity/concentration, null, all-missing and
   single-extreme support. It also correctly rejected an inherited fixture
   ratio/H900 binding inconsistent with the saved mark/Y3600→Y7200 query.
   `blind_primary_output.json` preserves the full sanitized failed batch.
   Correcting only the candidate fixture yields the separately identified
   dependent regression in `blind_correction_manifest.json`; this is not an
   independent replication. Input hashes and frozen gold are saved before each
   launch. Model configuration is gpt-6.1-sol/xhigh/native Codex; actual backend
   identity is UNKNOWN unless the isolated execution confirms it. No external
   API, scientific assessment write or protocol-finalization claim.

**CALENDAR_MISSING_TRUNCATION_COMPATIBILITY:** six matched days, two observed
and four missing. V4's two observed keys retain their counts/means in V5;
four missing-only keys have observed=0, mean=null and missing=1. A four-row
compact prefix contains only one observed outcome while the mandatory summary
still says observed=2/missing=4 and details total=6/included=4/truncated=true.
This proves a missing prefix cannot imply full coverage or no observed outcomes.

## Field transport map

For every row below, `summary` is the persisted temporal result, read without
evaluator. Existing matched/pooled, baseline, ablation, cohort and calendar
views use their own admitted sample. Compact Prompt A uses
`forge_context_packet.grounded_readouts[].descriptive_readout`; Critic uses
`grounded_evidence.descriptive_readout`. Owner JSON uses `descriptive_readout`
and its operation projection. Mandatory matched/baseline comparison is inline;
details are bounded with explicit totals. Full result ref/hash remains available.

| Metric | Persisted field under each view | Prompt A / Critic / owner compact field |
|---|---|---|
| median | `median_target` | `matched.median_target`, `baseline.median_target`, detail rows |
| support | `downside.observed_n`, `missing_n` | same downside block |
| negative / zero counts | `downside.negative_n`, `zero_n` | same downside block |
| p05 / p10 / p25 | `downside.p05`, `p10`, `p25` | same downside block |
| fixed downside counts/rates | `downside.le_minus_20_n/rate`, `le_minus_50_n/rate` | same downside block |
| ES / support mass | `downside.es10_return`, `es10_tail_mass_n` | same downside block |
| loss mass / concentration | `downside.negative_mass`, `worst_negative_share` | same downside block |
| methods / units / empty status | `downside.profile`, `quantile_method`, `es_method`, `units`, `status` | same downside block |

## Reproduction and delivery

Run in a disposable test environment from repository root:

```powershell
$env:PYTHONPATH='src;.'
.venv\Scripts\python.exe -X utf8 -B -m unittest tests.test_forge_downside_readout_v1 tests.test_hfic_temporal_owner_path_v1
.venv\Scripts\python.exe -X utf8 -B -m unittest tests.test_hfic_temporal_discovery_v1 tests.test_hfic_temporal_result_coherence_v1 tests.test_hfic_temporal_production_runner_v1
.venv\Scripts\python.exe -X utf8 -B docs/evidence/forge_downside_readout_v1/reproduce_packets.py <new-disposable-output-directory>
```

The packet reproducer reads only synthetic test fixtures and production owners;
it never opens real data-plane inputs. Generated packet byte identities can vary
with permitted publication clocks and current Git/capability bindings; the
frozen blind inputs, not a later reproduction, own the recorded model batch.
Real D2 reproduction requires separately resolving its exact immutable source
and copying only its closed inputs/store metadata. Never pass canonical root
to the correction writer in delivery; use the runbook's source-bound command on
the isolated copy, then compare old records/session/reservation/budget and
canonical before/after inventory. This atom grants no real correction.

Performance (`performance.json`): 101 measurements, helper median 0.174 ms at
n=1159; four-cohort/28-day compact projection 8285 bytes, first four days,
explicit truncation, mandatory comparison retained. Production cap remains
65536 bytes. Corrected actual Critic packets are under 28 KB.

Eight focused owner suites initially ran 87 tests: 85 passed; two consumer
failures were `IMPLEMENTATION_HASH_MISMATCH` because current source hashes
had not yet been committed to the Git head used by implementation verification.
They require rerun after stable source/Catalog commit; integrity checks are not
weakened. Final required independent role results and exact inventory are owned
by the three delivery JSON files. Exact-head PR CI is an external current gate.

Semantic owner: `docs/contracts/forge_downside_descriptive_v1.md`; route remains
`SEM-HYPOTHESIS-FORGE`, Catalog search term `downside` resolves the contract,
operator and temporal calculator. No new route, README entrypoint or framework.

Residuals: this is descriptive observed price risk, not policy economics;
bounded native smoke does not generally calibrate an LLM; no frozen verdict is
rescued automatically. Code rollback is a separately authorized Git revert,
never deletion of appended history. Before a real V5 write rollback is simple;
after one, an old reader can honestly stop at unsupported version.

One next step after approved merge: separately authorize exact D2 readout-only
enrichment → cold readback → STOP. Independent reassessment and any subsequent
economic falsifier remain separate owner decisions.
