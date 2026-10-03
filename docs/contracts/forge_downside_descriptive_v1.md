# FORGE_DOWNSIDE_READOUT_V1

`DOWNSIDE_DESCRIPTIVE_V1` describes the observed raw
`PRICE_RELATIVE_PROXY = price_exit / price_reference - 1` in each existing
temporal view. It is dimensionless: `-0.20` means minus 20 percent. It is not
NetReturn, a portfolio risk estimate, a future loss probability, OOS evidence
or a trading verdict. The same admitted, deduplicated, PIT-clean sample that
feeds the existing mean feeds this block; no new target, predicate or look is
introduced.

For each view, `observed_n` counts finite observed targets and `missing_n`
counts target-missing members of that view's eligible pre-outcome population.
Missing observations never enter rates or numeric values as zero. The fixed
fields are `negative_n` (`r < 0`), `zero_n` (`r == 0`), `p05`, `p10`, `p25`,
`le_minus_20_n`, `le_minus_20_rate`, `le_minus_50_n`, `le_minus_50_rate`,
`es10_return`, `es10_tail_mass_n`, `negative_mass`, and
`worst_negative_share`.

Quantiles use Hyndman–Fan type 7 linear interpolation on a sorted copy:
`h=(n-1)q`, `j=floor(h)`, and
`Q=(1-(h-j))*x[j]+(h-j)*x[min(j+1,n-1)]`. For expected shortfall of the
lowest tenth, let `k=n//10`, `f=(n%10)/10`, and `a=n/10`;
`ES10=(sum(x[:k])+f*x[k])/a`, omitting the fractional term when `f=0`.
Its sign is the return sign, and its support mass is `a`. The rates are the
literal counts of `r <= -0.20` and `r <= -0.50`, divided by observed `n`.
`negative_mass=sum(max(-r,0))`; `worst_negative_share` is the largest single
negative contribution divided by that mass.

At `n=0`, counts are zero and distribution values, rates, ES and
concentration are null with `NO_OBSERVED_TARGET`; missing support remains
visible. With no negative mass, event rates and mass are zero but
`worst_negative_share` is null. Nonfinite admitted targets are an integrity
stop. Small `n` is reported, never converted to a verdict. Pooled quantiles,
ES and concentration are calculated from pooled observations, not group
averages. Cohort overlap and existing dedup semantics remain unchanged.

New results use `HFIC_TEMPORAL_DISCOVERY_CALC_V5`, preserving every prior
numerical field, spec/input/market identity and scientific accounting for the
same question. V1–V4 replay without evaluator or rewrite and explicitly say
that downside metrics are unavailable. A coherent closed V4 source can be
supplemented only by public `discovery-execute` with its exact source ref and
hash, same saved spec, immutable binding and clocks, and equal old numerical
projection. The append-only V5 `CALCULATION_REVISION` records
`DOWNSIDE_READOUT_ADDED`; source bytes, slot, operation, session, reservation,
terminal and frozen assessment remain untouched. Exact retry reads the saved
revision without evaluation or writes. Historical verdicts stay bound to
their original refs; a newer readout asks for review rather than silently
changing a verdict. Fixed downside exposure is recorded as descriptive
evidence, not a new threshold trial.

V5 calendar rows use the same matched population and existing calendar key.
Existing observed counts and means are unchanged; missing-only keys add rows
with observed zero, null mean and explicit missing support. Compact packets
keep matched/baseline support and mark detail totals, included prefix and
truncation. A detail prefix is not complete calendar coverage.

Ordinary replay completes an interrupted landing through the existing
state-aware `note_look_landed` owner: an OPEN limited operation whose MAIN cap
is spent becomes PAUSED_CAP. Already terminal states are immutable. Readout
revision and its replay have no landing transition and never invoke that owner.
