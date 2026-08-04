# TASK-26A execution-evidence completion contract v1

## 1. Purpose and status

- Task: `TASK-26A`
- Atom: `T26A-A1_EXECUTION_EVIDENCE_CONTRACT_AND_INVENTORY_V1`
- Status after this freeze: `VALIDATED_CONTRACT_AND_TRACKED_INVENTORY_ONLY`
- Accepted base commit: `62513091ae97419c753ae3630beb79c2b317c769`
- Accepted base tree: `f176a90d5ff462c8a994b155228e27bc743743b9`

This contract freezes the evidence-completion vocabulary required before any
modeled numeric NetReturn comparison. It consumes tracked repository bytes only.
It does not open raw R2, read R3 paths or values, call providers, simulate,
build or send transactions, touch wallets or signers, spend money, or compute
numeric NetReturn.

## 2. Evidence classes

The frozen model distinguishes these classes; none may silently promote into
another:

| evidence_class | Question | Never proves by itself |
|---|---|---|
| `QUOTE` | What route and price was quoted? | Attempt, landing, fill, settlement |
| `BUILD` | Was a transaction constructed? | Send, landing, fill |
| `SIMULATION` | What did a simulation return? | Actual landing or cashflow |
| `SEND_ATTEMPT` | What intended send/retry chain existed? | Chain landing or fill |
| `PROCESSED_TERMINAL` | What processed-terminal observation exists? | Confirmed landing, fill, or flat inventory |
| `LANDING` | What terminal landing state is evidenced? | Fill, flat inventory, settlement |
| `FILL` | What reconciled token deltas exist? | Settled cashflow or NetReturn |
| `FEE_CHARGEABILITY` | Which fee components are evidenced and chargeable? | That missing fees are zero |
| `INVENTORY` | What position remains under control or recovery? | Flat from an exit quote |
| `SETTLEMENT` | What cash settled under declared accounting? | Modeled or observed NetReturn alone |
| `MODELED_NETRETURN` | Is a modeled-complete scenario eligible? | Observed profit or owner cashflow |
| `OBSERVED_NETRETURN` | Is observed NetReturn reconciled? | Strategy promotion |
| `UNKNOWN` | Explicit typed unknown | Zero, false, landed, flat, or settled |

## 3. Required components for NetReturn eligibility

Before modeled numeric NetReturn may be considered, every required component
must pass with a stable `evidence_class`, source binding, availability status,
missingness reason, and named consumer:

1. `FEE_CHARGEABILITY` — independent evidence for network, relay/tip, ATA/rent,
   and any separately charged transfer components; quote-embedded AMM impact
   must not be double-counted.
2. `SEND_ATTEMPT` — stable attempt and retry-chain identity.
3. `LANDING` — terminal landing distinct from processed-only samples.
4. `INVENTORY` — reconciled inventory; open, partial, residual or unresolved
   inventory cannot be reported flat.
5. `SETTLEMENT` — settled trading cashflow under an explicit accounting basis.

Observed NetReturn additionally requires complete attributed project cash cost
and reconciled flat actual inventory. Absence or `UNKNOWN` never becomes zero,
false, landed, flat, or settled.

## 4. Tracked-only inventory rules

- Inputs must be exact repository paths with SHA-256 bindings.
- Raw R2 files opened, R3 paths or values read, provider calls, simulations,
  wallet actions and transactions must remain zero.
- Processed-only or confirmed-only evidence cannot estimate dropped or rejected
  probability.
- Quote availability cannot establish fill, settlement, strategy-specific
  landing probability, or owner cashflow.

## 5. Deterministic result enum

Exactly one result:

- `FIT_FOR_MODELED_NETRETURN_COMPARISON_WITH_LIMITATIONS`
- `EXTEND_EXECUTION_EVIDENCE`
- `REDESIGN_EVIDENCE`
- `PAUSE`

No promotion or baseline authority is attached to any result.

## 6. Adversarial rejects

Mutations must reject at least:

1. quote-to-fill promotion;
2. missing-fee zeroing;
3. processed-only landing inference;
4. double-counted route costs;
5. unresolved inventory flattening;
6. R3 access;
7. untracked or raw input;
8. numeric NetReturn without complete reconciliation.
