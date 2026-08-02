# TASK-24 bounded data redesign or stop decision v1

## 1. Decision

- Task: `TASK-24 Entity graph v1`.
- Atom: `T24-A6_BOUNDED_DATA_REDESIGN_OR_STOP_DECISION_V1`.
- Status: `VALIDATED_STOP_DECISION_ONLY` after local acceptance.
- Owner decision: `STOP_NO_RELIABLE_ENTITY_SIGNAL` for TASK-24 v1.
- Route owner: `LOCAL_WORK_PRIMARY`; execution route: `LOCAL_WORK_CODEX`.
- Accepted base commit: `31c01640499be6b7e86a2fe638d9217c202861cc`.

The A5R1 exact-wire recapture repaired the retention defect and made the bounded
history projection admissible. It did not make the entity signal reliable enough
for the frozen false-positive audit or any downstream concentration, eligibility
or strategy decision. TASK-24 therefore stops evidence expansion at the current
partial graph. This is a stop for the v1 route, not a claim that entity evidence
can never be useful.

## 2. Measured result

The frozen population contains one mint and 20 wallets. A5R1 retained 21 exact
wire responses, used 21 provider calls and 210 modeled provider credits, returned
1,939 transactions (1,936 unique), and marked all 21 subjects truncated. The
projection produced:

- 18 direct immediate-funder edges;
- two shared-immediate-funder candidates;
- four `INFERRED` membership claims;
- zero `CORROBORATED` membership claims;
- zero common-transaction-signer edges;
- no authoritative bundle family;
- selected predicted-positive capacity `4/12`.

The four claims are reversible project inferences. They do not establish common,
economic or beneficial ownership.

## 3. Structural deficit

The frozen audit capacity is:

`min(C, 8) + min(I, 8)`

where `C` is the number of eligible corroborated positive claims and `I` is the
number of eligible inferred or vendor-only positive claims. A5R1 measured
`C=0, I=4`. Opening the audit requires at least 12 selected positives.

The smallest numerical repair requires eight additional eligible claims and must
reach at least four corroborated claims. One minimal shape is `C=4, I=8`; another
is `C=8, I=4`. Adding inferred claims alone can never exceed the inferred-stratum
cap of eight and therefore cannot open the gate.

## 4. Why the available redesigns are rejected now

| Candidate change | What it could add | Why it does not close the frozen gate |
|---|---|---|
| Paginate the same address history | Later transactions for the same 21 subjects | More transactions are not a second independent evidence family. Yield of shared-signing events is unknown, and using later interactions risks selection without a frozen causal window. |
| Increase the per-address limit | More of the same provider history | Same structural problem; it changes the call/credit boundary without evidence that four corroborated and four additional inferred claims will appear. |
| Expand beyond the 20-wallet population | More possible shared-funder clusters | Can add inferred claims, but population expansion alone cannot create the required corroborated stratum and changes the frozen population. |
| Read the same transactions from another provider | Duplicate transport | Duplicate providers for the same raw event are not independent evidence. |
| Add vendor cluster or bundle labels | Attributed third-party inferences | They remain `VENDOR_LABEL`, cannot become `CORROBORATED`, and cannot merge, exclude or veto. |
| Query Jito status without retained bundle IDs | No historical discovery truth | The current evidence has no authoritative bundle IDs; status APIs are not historical bundle discovery. |
| Relax confidence or audit thresholds | Apparent capacity | This is target-driven rule tuning after value read and is forbidden research debt. |

No candidate is both bounded within the current data contract and capable of
closing the two-stratum deficit with defensible evidence. A wider multi-mint
sample, a new event family, pagination, higher provider caps or a different
labeling design would materially change the population, evidence contract, cost
or selection boundary. That is a new versioned research objective, not an A6
repair.

## 5. Consequences

The following artifacts remain valid as partial evidence:

- the frozen graph/evidence/false-positive contract;
- deterministic pseudonymized nodes and raw edges;
- two reversible shared-funder candidates and their four inferred memberships;
- exact A5R1 wire/canonical retention receipts and deterministic projection.

They are not admissible to:

- change raw or adjusted holder concentration;
- exclude a holder or change eligibility;
- merge wallets into ownership truth;
- veto or enable a strategy;
- open the blinded false-positive audit;
- support alpha, execution, PnL, NetReturn or owner-cashflow claims.

Manual labels remain unopened. Missing corroboration remains `NOT_TESTABLE`, not
zero and not false.

## 6. Reactivation contract

A future entity-evidence objective may be proposed only after all of these are
named before new value reads:

1. a downstream hypothesis or owner decision for which entity evidence can
   materially change an action;
2. a frozen prospective population and sampling rule, normally spanning more
   than one mint rather than expanding this sample after seeing its values;
3. an available second independent raw-event family capable of producing
   corroborated claims, such as retained authoritative bundle membership or a
   separately defined disjoint interaction event;
4. an audit-capacity forecast showing a credible path to at least 12 selected
   positives with at least four corroborated claims;
5. a blinded/manual judgment plan, provider/cost cap, PIT/retention contract and
   separate authority for any external calls.

Reactivation must create a new versioned task or contract. It must not rewrite
the A2–A6 receipts or retrospectively relabel the current four claims.

## 7. Boundary and next atom

A6 made zero provider/API/RPC/WSS calls, consumed zero credits, read no R3 or
outcome data, changed no Catalog/registry, and performed no wallet, signer,
transaction, deployment or repository-delivery action.
It does not establish canonical TASK-24 `DONE`.

TASK-24 remains `IN_PROGRESS` until partial assets, limitations and lifecycle
status are registered and the required full Factory Fit review is accepted. The
recommended next atom is
`T24-A7_REGISTER_PARTIAL_ASSETS_UPDATE_CATALOG_AND_FULL_FACTORY_FIT_REVIEW_V1`.
It is not authorized by this decision.
