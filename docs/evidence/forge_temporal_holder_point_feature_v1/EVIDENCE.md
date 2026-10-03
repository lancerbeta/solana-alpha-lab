# Holder point feature evidence

Scope: `FORGE_TEMPORAL_HOLDER_POINT_FEATURE_V1` on base
`94b284534b6ad55a95002d51b9d04b4a5ced6bde`; one PR, no merge authority.

## Production vertical proof

`tests/test_forge_temporal_holder_point_feature_v1.py` supplies synthetic typed
transport rows to the existing production publisher/seal/import/schedule owners.
The published binding, files, clocks and hashes then feed the public CLI. There
is no reconstructed holdout, experiment binding or result injection.

The exact synthetic question is holder point Y900 >=3 and PRICE_RELATIVE_PROXY
Y900→Y14400. Four disposable cohorts supply 16 members, 8 matched, 4 holder
unknown, 8 observed matched targets and 4 zero matched returns. These are
fixture numbers, never market evidence. V5 retains baseline, downside, calendar,
cohort and cost stress semantics. `synthetic_*.json` are outputs of the real
owners, exported only after the proof passes.

Preview observes holder values/status before the target and returns only X300 /
Y900 observation rows. The test inspects the actual Arrow-loader result and
requires its filters; no Y14400 values reach the evaluator. No scientific look
exists after preview. Public discovery lands one synthetic MAIN, loses its
reply, and cold replay recovers the saved result without the value loader.
Replay inventory stays unchanged. Independent new-process preflight builds
Prompt A from that result; production freeze creates the selected candidate and
Critic packet. Their identity and owner projection match the saved recipe.
Field, point, threshold, primary target horizon and target-axis tampering fail.
Registered fixed-time capability replays the same saved recipe/spec/input and
the same complete result; no provider call and no NetReturn label.

Reproduction (disposable stores only):

```text
uv run --locked --managed-python python -B -m unittest tests.test_forge_temporal_holder_point_feature_v1 -v
```

Optional `FORGE_HOLDER_PROOF_DIR` exports the production proof outputs.
The old PRICE and LIQUIDITY canonical specs, SHA and complete frozen results
were captured before product mutation. They remain byte-exact in the regression.

## Real read-only compatibility

`real_compatibility.json` proves canonical publication/admission, schedule,
validator and existing cell selection using holder Y900 only. The lineage was
confirmed to contain exactly corpus versions 1–4 before observation selection.
No target field/point was selected. C5 was not opened or assigned.
ResearchStore inventory before/after is
`15ea38b43bfb7d4e65c558aecad7147600d27f4f1d9edbbd213660a17080e250`,
with 380 committed records both times. No real operation, session, reservation,
look or disposition was created. The real operation gate was not invoked,
because this implementation grants no real-operation authority.

1157 eligible census members have an OBSERVED, admitted holder Y900 cell.
11 are absent, 91 arrive after deadline and 303 have uninterpretable snapshot
lineage. This is a feature-readiness diagnostic, not the future MAIN denominator:
decision-price eligibility and target support have not been evaluated. Excluded
cells remain UNKNOWN. No fallback or new clock interpretation is introduced.

## Anti-follow-up seam review

"What predictable failure will the very first real holder MAIN hit that my
synthetic/vertical proof did not exercise?"

The initial gaps were preview feature/target separation and feature/predicate
binding to the selected card. Isolated review then found lossy numeric labels,
feature-only preview validation after the loader, and inherited liquidity/MEU
text in the holder fixture. All are closed in this atom: canonical float labels
are lossless; one pure preview validator runs before the loader and is reused
by the evaluator; the entire synthetic scientific card is holder-specific.
Regression distinguishes >=3 from >=3.0000001, refuses the wrong card, requires
zero loader calls for invalid previews and rejects MEU/liquidity fixture text.
Validator, typed loader,
mixed-point clocks, missingness/lineage, spec identity, ordinary cap/intent,
interrupted reply/cold replay, V5, Prompt A, Critic, owner and registered consumer
are exercised through existing owners. No holder-specific raw loader exists.
Production consumers must use the machine-generated holder card labels.

Residual: the separately authorized real MAIN can still have limited support,
integrity/missingness exclusions or activity/price-staleness confounding. The
implementation preserves those stops; it does not declare an entry edge.
No C5, provider, VPS, import or real-science repair is needed for the capability
proof. The prior D2 exposure, fixed >=3 predicate and future decision taxonomy
are retained in the exact task and consumer contract.

Rollback: separately authorized ordinary Git revert before any real holder look;
after one exists, preserve its reader and saved history through forward repair.
