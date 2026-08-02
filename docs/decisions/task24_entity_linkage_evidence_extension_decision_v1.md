# TASK-24 bounded entity-linkage evidence extension decision v1

## 1. Decision and measured gap

- Task: `TASK-24 Entity graph v1`.
- Atom: `T24-A4_BOUNDED_ENTITY_LINKAGE_EVIDENCE_EXTENSION_DECISION_V1`.
- Status: `VALIDATED_DECISION_ONLY` after local acceptance.
- Owner decision: `EXTEND_EVIDENCE`.
- Selected route: `BOUNDED_RAW_HISTORY_FEASIBILITY_PROBE`.
- Route owner: `LOCAL_WORK_PRIMARY`; execution route: `LOCAL_WORK_CODEX`.
- Accepted base commit: `31c01640499be6b7e86a2fe638d9217c202861cc`.
- Accepted base tree: `6677878eb2b8195018ab217c6a9a429de5726563`.

A3 projected 41 pseudonymized nodes and 40 direct account/mint/owner edges, but zero
entity candidates. Deployer, immediate-funder, authoritative-bundle and common-ownership
claims were all `NOT_TESTABLE`. The false-positive audit therefore has `0/12` required
reviewed predicted-positive claims and cannot open.

This decision does not collect external data. It freezes the cheapest probe that could
change that result without promoting a provider parser, a common funder or a vendor label
to ownership truth.

## 2. Audit arithmetic that controls the route

The A2 audit selects at most eight `CORROBORATED` positives and at most eight `INFERRED`
or `VENDOR_ONLY` positives; an undersized stratum is not filled from another stratum. If
`C` is the eligible corroborated count and `I` is the eligible inferred/vendor count, the
maximum selected predicted-positive count is:

`min(C, 8) + min(I, 8)`.

Opening the gate requires that value to be at least 12 before manual judgments. As a
consequence, any route producing only shared-funder inferences can contribute at most
eight selected positives and is structurally insufficient. At least four eligible
corroborated positives are required when the inferred/vendor stratum is full. More vendor
labels cannot repair this shortage.

`CORROBORATED` continues to require at least two independent raw edge families. Two
providers returning the same transaction, or funder and signer facts extracted from the
same transaction, are one event family for this purpose.

## 3. Current official-source findings

The following facts were read from public official documentation on 2026-08-02. No
credentialed endpoint was called.

| Route | Current documented capability | TASK-24 interpretation | Decision |
|---|---|---|---|
| Standard Solana RPC | `getSignaturesForAddress` returns signatures that reference an address, newest first; `getTransaction` resolves one known signature and may return `null`. | Canonical method semantics, but earliest-history discovery requires pagination plus per-signature reads and does not include ATA-only activity. | Retain as a bounded read-back/fallback, not the primary probe. |
| Helius `getTransactionsForAddress` | Provider-exclusive history method supports oldest-first ordering, full transactions, filters and up to 1,000 results per call. Full responses are metered at 10 credits per 100 returned transactions, rounded up, with a 10-credit minimum. | Use only as historical transport. Persist exact response bytes and derive every edge under project rules; provider descriptions or labels are not raw ownership evidence. | `ADOPT` transport semantics and `WRAP` a thin deterministic parser in the next atom. |
| Helius Enhanced Transactions v1 | The provider marks this parsed API deprecated for new integrations. | Parser coverage and human-readable labels add avoidable semantic risk. | Reject for the probe. |
| Jito bundle status APIs | Status lookup requires already-known bundle IDs, accepts at most five IDs per request, and checks recent transaction history; inflight status has a five-minute lookback. | A3 retained no bundle IDs. These APIs are status checks, not historical bundle-discovery endpoints. | Do not call in the probe. Bundle evidence remains `NOT_TESTABLE` unless an exact authoritative ID is independently retained. |
| Vendor cluster/bundle label | Attributed third-party inference rather than an exact raw event. | Remains `VENDOR_LABEL`; it cannot create `CORROBORATED`, merge wallets, exclude holders or veto a strategy. | Optional future conflict/triage evidence only. |

Official sources:

- Solana `getSignaturesForAddress`: <https://solana.com/docs/rpc/http/getsignaturesforaddress>
- Solana `getTransaction`: <https://solana.com/docs/rpc/http/gettransaction>
- Helius `getTransactionsForAddress`: <https://www.helius.dev/docs/rpc/gettransactionsforaddress>
- Helius Enhanced Transactions overview: <https://www.helius.dev/docs/enhanced-transactions/overview>
- Jito bundle API: <https://docs.jito.wtf/lowlatencytxnsend/>

Provider completeness, availability, account entitlement and live credit balance remain
unverified until a separately authorized capture preflight.

## 4. Selected bounded probe

The next candidate atom is
`T24-A5_BOUNDED_RAW_HISTORY_FEASIBILITY_CAPTURE_V1`. Its population is frozen to the one
mint and 20 owner wallets already pseudonymized by A3. It may not add wallets, mints or a
vendor-labeled sample.

The proposed external request envelope is:

- exactly 21 Helius `getTransactionsForAddress` requests: one mint plus 20 wallets;
- `transactionDetails=full`, `sortOrder=asc`, `limit=100`, `commitment=finalized`,
  `maxSupportedTransactionVersion=0`, succeeded transactions only;
- no pagination, retries or fallback provider calls inside the initial envelope;
- maximum 2,100 returned transactions;
- maximum 210 Helius credits under the documented minimum/rounding rule;
- maximum cash spend: USD 0; existing credits only;
- exact raw response retention with request parameters, observed/available/ingested times,
  byte count, SHA-256 and explicit truncation/error flags;
- zero R3/outcome/PnL/strategy reads and zero wallet/signer/transaction actions.

The 21-call envelope is a cap, not authority. It requires a separate exact user gate for
provider/API/RPC execution, credential use and provider credits. Secrets must be supplied
locally through an existing secret boundary and never written to chat, repository, logs or
URLs retained as evidence.

## 5. Frozen evidence rules for the probe

The probe may derive only these candidate-supporting families:

1. `IMMEDIATE_FUNDER_V1`: the first successful finalized explicit native SOL transfer
   into a target wallet in the returned oldest-first history. The exact transaction,
   transfer instruction, source, target and lamports are retained. This never means
   ultimate funder or ownership.
2. `COMMON_SIGNER_SEPARATE_EVENT_V1`: two or more population wallets are required signers
   of the same successful finalized transaction. A transaction used for a wallet's
   immediate-funder edge cannot also provide that wallet's independent corroboration.
3. `AUTHORITATIVE_BUNDLE_V1`: exact Jito bundle ID plus its exact transaction-signature
   membership. This family is unavailable in the initial probe because A3 retained no
   bundle ID; vendor bundle labels are not substitutes.

`RAW_MINT_CREATED_BY_WALLET` may be projected from the exact mint-creation instruction,
but one creator shared by every holder of the same mint is not a discriminating membership
family.

A shared immediate funder can produce an `INFERRED` membership claim. A claim becomes
`CORROBORATED` only if a second compatible raw family supports the same membership, uses a
different raw event, and has no unresolved conflict. Duplicate provider reads and multiple
fields from one event never count twice.

## 6. Admission, stop and recovery

The capture is usable only if all 21 request outcomes are retained, every parsed claim is
traceable to exact raw bytes, truncation and nulls remain explicit, and raw public
addresses are transformed to the existing stable pseudonyms before durable derived output.

After projection, compute `min(C, 8) + min(I, 8)`:

- if it is at least 12, freeze the candidate inventory and proceed to the blinded
  false-positive-audit atom;
- if it is below 12, do not add labels, tune rules, paginate, expand the population or call
  another provider automatically;
- choose `REDESIGN_DATA` when valid history exists but the frozen population cannot supply
  the required evidence structure;
- choose `STOP_NO_RELIABLE_ENTITY_SIGNAL` when the retained history is incomplete,
  contradictory or cannot support defensible entity inference.

Failure before materialization leaves A3 outputs authoritative and records an explicit
gap receipt. Retry requires a new immutable run ID and the same request/population contract;
any wider population, pagination, provider or credit cap is a new user-approved boundary.

## 7. Non-claims and current boundary

A4 establishes neither entity membership nor beneficial ownership. It does not establish
a deployer/funder/bundler ground truth, adjusted concentration, holder exclusion, toxicity,
alpha, causality, execution, PnL, NetReturn, owner cashflow or canonical TASK-24 `DONE`.
It makes no Catalog or registry change.

A4 authorizes only its four local files and offline validation. Provider/API/RPC/WSS
execution, credential use, credits, dependency changes, R3/outcome access, wallet actions,
spend, deployment and repository delivery are all outside this atom.
