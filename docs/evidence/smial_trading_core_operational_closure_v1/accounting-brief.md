# Accounting implementation brief

Task: SMIAL_TRADING_CORE_OPERATIONAL_CLOSURE_V1, base ba87f8e339d5cc3aa55322801ae56e3f92369446.
Read AGENTS.md and exact task contract. Requirements are source-contract.md
sections 2 (D2/D3), 7.4, 8, 11.4 and C08/C11/C20. Owner accepted D1-D4.

Ownership exclusively: factory/paper_plane.py, factory/trading_runtime_policy.py,
factory/risk_economics.py, tests/test_trading_operational_obligations_v1.py and
docs/contracts/risk_and_economics_v1.md, docs/contracts/trading_runtime_policy_v1.md
(src paths prefixed src/solana_alpha_lab). Do not change runner/coordinator/adapters.
You are not alone; accommodate other changes, never revert others. No subagents,
no commits/push/PR, no dependencies/provider/network/credentials/live/runtime data.

Implement at existing owners: versioned optional ordinary operating envelope
stored in same PaperPlane DB (events are fine), explicit positive money/count
limits, shared per-mode outstanding obligations across all identities/epochs.
Default legacy APIs keep original OPEN_RISK_STATES/max_open_positions semantics.
Additional ordinary check applies before reservation, same immediate transaction.
Unknown inventory reserves at least admitted cost basis; pending reservation,
possible entry, open, EXIT_REQUIRED/EXITING/UNRESOLVED included. Definitive nonfill
and proven complete exit free capacity, costs UNKNOWN separate. No auto shrink.
Expose small normalize/configure/read/enforce/obligation-summary API to coordinator;
report signatures early. Ordinary absence of limits is CONFIGURATION_REQUIRED.

Minimal additive partial EXIT result v1.1: explicit quantity sold (not notional),
unit denomination, known remaining inventory, each definitive partial finalizes
attempt, next exit attempt works remainder, no overlap following UNKNOWN.
Keep v1.0 full exit behavior/old stored hashes. Reject overfill/NaN/negative.
Accounting realized legs plus remainder, aggregate entry fee allocation exact,
literal oracle: 10M entry units @$0.000003, entry $30 fee .06; exit 4M @.0000033
proceeds 13.20 fee .03, remainder 6M; exit 6M @.000003 proceeds18 fee .04;
gross1.20/trade1.07/additional .01/model net1.06. No double effects on exact replay.
Existing cumulative costs/monotonic clocks preserved. Fees already net in a quote
must have explicit supported semantics; coordinate with parent on field if needed.

Get native reproducer/trace before repair and focused regressions after. Use
existing tests directly; no full local gate. uv env UV_CACHE_DIR standard writable
cache, UV_OFFLINE=true, UV_PYTHON_DOWNLOADS=never; escalation allowed if sandbox
cannot read interpreter. Write full implementation/test report to accounting-report.md
in same evidence directory, return concise status/changed files/tests/concerns.
