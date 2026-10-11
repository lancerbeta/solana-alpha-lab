# Accounting / outstanding-obligation implementation

Task: `SMIAL_TRADING_CORE_OPERATIONAL_CLOSURE_V1`.
Scope: D2/D3, source-contract §§7.4/8/11.4 and C08/C11/C20 at the existing
PaperPlane, runtime-policy and economics owners. All amounts below are explicit
synthetic fixture inputs, never working runtime limits or financial claims.

## Native before trace

Before the repair, the existing native test
`OrdinarySourceTests.test_cumulative_cost_floor_clock_and_partial_exit_refusal`
passed its predecessor oracle: `PARTIAL` EXIT was refused with
`PARTIAL_EXIT_MODEL_UNSUPPORTED`, preserving the old position/result events.
The initial sandbox invocation failed before the product path because its
managed interpreter/test temporary directory was inaccessible. Repeating the
same offline test with permitted escalation ran one test successfully.

The remaining legacy risk behavior is independently reproduced in the new
shared-predecessor test: after a close request `open_risk_count` is zero while
one physical obligation still exists. This demonstrates why the additional
ordinary basis is required without rewriting `OPEN_RISK_STATES`.

## Implemented behavior

- Optional ordinary envelope is persisted as append-only, revision/hash-linked
  events and idempotent operator-command records in the same PaperPlane DB.
  Both count and cost-basis limits are explicitly positive; ordinary absence
  is `CONFIGURATION_REQUIRED`. Malformed envelope/revision chains fail closed.
- Shared per-mode obligation summary includes all identities/epochs,
  reservations, possible entry, inventory, partial remainder, closing and
  unreconciled states. Definitive non-fill and proved complete exit release
  capacity. `CLOSED` alone, unknown attempt, corrupt remainder or missing
  required inventory does not. Unknown additional costs stay economic unknown;
  they do not invent physical inventory after a proved flat outcome.
- Ordinary admission is an additive check inside the existing immediate
  transaction, before reservation. Before ENTRY attempt it rechecks the same
  safety envelope and other obligations, excluding its own frozen reservation.
  Headroom does not resize the accepted amount. Legacy entry-risk semantics
  and v1.0 result payload/hash inputs remain unchanged.
- Modeled result v1.1 has explicit token quantity/units and fee semantics.
  ENTRY can preserve raw quoted quantity; EXIT proves sold and remaining
  quantity rather than misusing entry notional as proceeds. Each definitive
  partial finalizes one attempt, retains originating `EXIT_REQUIRED`, and lets
  the next attempt use only the known remainder. UNKNOWN prevents overlap.
- Original entry quantity/cost/fee remain immutable. Residual quantity,
  residual cost basis and residual entry fee are additive position columns;
  realized quantity legs are append-only events. Cumulative fee allocation
  consumes exactly the original entry fee, including the final residual.
  Open marks use residual components; partial realised rows are separate
  from fully reconciled totals. Unknown EXIT preserves already realised legs.
- `SEPARATE_MODELED_FEE` uses the frozen fee-bps model.
  `INCLUDED_IN_UNIT_PRICE` adds no second modeled leg fee to an already net
  quote. Additional `chargeable_cost_usd` is still cumulative and excludes
  both kinds of price-leg fees. Existing cost floor, clock monotonicity and
  exact-result replay behavior remain in their original owner.
- Indexed readback selects envelope events and current obligation candidates,
  then only those positions' events, grouped once. A native partial index skips
  proved complete trades and explicitly zeroed non-fill/cancelled inventory.
  Old unproved legacy rows retain conservative readback. Default
  `execution_events()` keeps its original zero-argument API; the additional
  `filtered_execution_events` helper handles indexed reads.

## Coordinator API

```python
normalize_operating_envelope(raw, *, mode) -> dict
configure_operating_envelope(store, *, mode, candidate_raw,
    expected_current_sha256, idempotency_key, as_of) -> dict
read_operating_envelope(store, mode) -> dict
obligation_summary(store, *, mode, exclude_position_id=None) -> dict
enforce_operating_envelope(store, *, mode, admitted_notional_usd,
    exclude_position_id=None) -> dict
accept_signal_decision_outcome(..., ordinary_operating=False) -> dict
begin_modeled_attempt(..., ordinary_operating=False) -> dict
```

Envelope body: `schema='smial.ordinary-operating-envelope'`,
`schema_version='1.0'`, `basis='OUTSTANDING_OBLIGATIONS_V1'`, mode,
`max_outstanding_positions`, `max_outstanding_cost_basis_usd`.
Normalize supplies the fixed schema identifiers; it never supplies limits.
The configuration helper consumes authority from its enclosing explicit
profile command and grants none by itself. CAS uses `envelope_sha256` from
readback; genesis is 64 zeroes.

Positive result v1.1 requires `schema_version='1.1'`,
`quantity_unit='TOKEN_UNITS'`, `fee_semantics`, `unit_price_usd` and the existing
attempt/result/outcome/time identity. ENTRY requires `quantity_filled` and
`filled_notional_usd`. EXIT requires `quantity_sold` and
`remaining_quantity`; it rejects entry notional/quantity fields. Partial
remaining is positive; full remaining is zero. Legacy v1.0 full EXIT and
historical partial-ENTRY meaning are preserved.
Positive ENTRY also rejects quantity/effective-price/notional conflicts at
cent precision; net quote price is paid notional divided by raw output quantity.

## Independent accounting oracle

Entry: 10M units at `$0.000003`, notional `$30`, entry fee `$0.06`.
First EXIT: 4M units at `$0.0000033`, proceeds `$13.20`, exit fee `$0.03`;
remaining 6M units, cost basis `$18`, remaining entry fee `$0.04`.
Second EXIT: 6M units at `$0.000003`, proceeds `$18`, exit fee `$0.04`.
Expected aggregate: gross `$1.20`, trade net `$1.07`, additional cost `$0.01`,
model net `$1.06`. All values matched independently asserted literals.
A three-leg fractional allocation oracle also conserved the original `$0.06`
entry fee and the exact sums of realized gross/trade net.

## Validation

Environment for every command: `UV_CACHE_DIR` points to the existing writable
uv cache, `UV_OFFLINE=true`, `UV_PYTHON_DOWNLOADS=never`,
`PYTHONIOENCODING=utf-8`. Tests use owned disposable fixture DBs and no provider.
The extended legacy tests need `PYTHONPATH=src;tests` because two old tests use
bare imports of another test module. No local full gate was run.

```text
uv run --locked --managed-python python -B -m unittest
  tests.test_trading_operational_obligations_v1
  tests.test_trading_runtime_admission_concurrency_v1
  tests.test_trading_runtime_policy_backup_restore_v1
  tests.test_paper_shadow_execution_integrity_vertical_v1 -q
PASS: 54 tests (13 new obligations tests), 10.315s

uv run --locked --managed-python python -B -m unittest
  tests.test_risk_and_economics_v1 tests.test_trading_runtime_policy_v1
  tests.test_paper_shadow_accounting_and_control_v1 -q
PASS: 37 tests, 12.164s

uv run --locked --managed-python python -B -m unittest
  tests.test_trading_operational_obligations_v1
  tests.test_trading_runtime_admission_concurrency_v1
  tests.test_trading_runtime_policy_backup_restore_v1
  tests.test_paper_shadow_execution_integrity_vertical_v1
  tests.test_risk_and_economics_v1 tests.test_trading_runtime_policy_v1
  tests.test_paper_shadow_accounting_and_control_v1
  tests.test_trading_continuity_v1.OrdinarySourceTests.test_cumulative_cost_floor_clock_and_partial_exit_refusal -q
PASS: 94 direct-consumer tests (15 obligations tests), 24.615s

uv run --locked --managed-python python -B -m unittest
  tests.test_trading_operational_obligations_v1 -q
PASS: 15 tests, 1.181s, after the final NULL-safe candidate predicate and
      missing-remainder + corrupt non-fill-final regression.
```

New focused tests cover missing/invalid configuration, unchanged legacy API,
mode separation, concurrent reservation serialization, predecessor capacity,
no auto-shrink, literal partial oracle, exact replay, raw quote quantity,
included fees, NaN/negative/overfill/unit rejection, crash rollback, cold
read-only readback, unknown outcomes and non-fill, damaged remainder/final
events, attempt recheck, multi-leg allocation conservation and the ENTRY
quantity/price/notional guard. The performance oracle adds 4,000 completed
positions, 2,000 explicitly zeroed non-fill positions and 12,000 historical
events while asserting SQLite VM work remains below `2 * baseline + 100`.

An earlier 94-test combined run reported two old bare-test-import errors and
two continuity tests whose old file-dependency expectations conflict with the
parallel frozen-context runner repair. The import errors were resolved by the
correct test path and the complete direct accounting consumers passed above.
The two runner expectations were reported to the parent owner for integration;
they are outside this subtask's file ownership.
One intermediate direct-consumer run exposed a zero-argument event-reorder
monkeypatch compatibility issue. Separating the filtered helper from the
original method fixed the product seam without changing that test.

## Scope and remaining integration

Changed owned files: `paper_plane.py`, `trading_runtime_policy.py`,
`risk_economics.py`, `test_trading_operational_obligations_v1.py`, and the two
runtime-policy/economics contracts. No runner/coordinator/adapter file was
changed, no commit/remote/provider/credentials/live/runtime access occurred,
and no dependencies/services were added.
Every store fixture closes its readers/writers before temporary-directory
cleanup. The temporary directory from the initial failed sandbox invocation
was separately read back as `ABSENT`; no test resource was retained.

Parent integration must select ordinary admission and register the new test
module in execution-domain inventory; it owns successor/driver/adapter/CLI,
whole-source process proof, final cleanup and delivery/review gates. This
report establishes the accounting subtask's engineering evidence, not whole
software commissioning readiness, scientific acceptance or financial authority.
