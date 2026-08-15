# TASK-30 A24 raw-to-PIT admissibility owner-panel contract v1

## Decision

Decide whether the exact retained A22+A23 PumpSwap batch for the frozen pool and
UTC day can support a reproducible, explicitly limited 15-minute diagnostic
panel for `RC001-H07-H01-LIQUIDITY-RETENTION`, or name the exact missing data
capability. Success is one terminal owner decision, not a decoder or 96 rows
alone.

## Frozen inputs

Page 0 is the immutable A22 raw response
`local/task30_a22_helius_get_transactions_for_address/run=20260814T184209Z-7572a5c2/raw_response.json`
with SHA-256 `7244a4c049c7ebe5f77d6136513d402c9af568dd0ccabb3a842160ab61a72bcc`
and 9,012,030 bytes. The A23 terminal page
`local/task30_a23_helius_bounded_pagination/run=20260814T220124Z-e494b5aa/page=001/raw_response.json`
must hash to `6770f134e61d334451780ded411fe5dd79e0577f2c532a5d3a8a694b8c58ae81`,
contain zero rows and a null cursor. Both files are read-only. No provider,
credential or network access is authorized.

The named consumer, pool, mints, program, 900-second grid and 96 expected slots
are frozen in the A24 policy. RC001 definition SHA-256
`14a7387148d05773dedcb5ad6a8110a0dcab7e49da4dec77328903a5b7577df7` must not
change.

## Architecture boundary

WRAP the existing PumpSwap Touch decoder and TASK-09 log attribution. Do not
build another provider abstraction or a second event decoder. Modify
`pumpswap_touch_probe.py` only to extract a behavior-preserving attribution
seam that ignores non-PumpSwap `Program data` without parsing it as PumpSwap.
Live `logsNotification` truncation still drops decoded events; A24 keeps events
decoded before truncation and treats truncation as an explicit coverage
condition.

Versioned account keys are static `accountKeys` plus `loadedAddresses.writable`
then `loadedAddresses.readonly`. Instruction data uses Solana JSON base58.
Market-changing PumpSwap instructions are exactly `buy`, `buy_exact_quote_in`
and `sell`, identified by `sha256("global:<name>")[:8]`. Anchor self-CPI event
logs are not market-changing. `close_user_volume_accumulator` and event
`CloseUserVolumeAccumulatorEvent` (`sha256("event:CloseUserVolumeAccumulatorEvent")[:8]`
= `929fbdac925838f4`) are non-market only through that pinned official
IDL/Anchor binding. Any other PumpSwap discriminator is
`STOP_INTEGRITY_CONFLICT`. A market-changing instruction without a matching
attributed Buy/Sell event is `STOP_INTEGRITY_CONFLICT`. Heuristic recovery is
forbidden.

## 96-slot panel

Slots are the closed UTC day split into 96 intervals of 900 seconds. A slot
with no decoded target trade is not automatically zero, flat or complete.

- `OBSERVED_TARGET_TRADES`: at least one target-pool Buy/Sell event.
- `PROVEN_NO_TARGET_TRADE`: complete coverage and zero target-pool trades.
  Volume may be zero only in this state or in proven persistence with zero
  trades.
- `STATE_PERSISTENCE_PROVEN`: complete coverage, zero target trades, and no
  market-changing PumpSwap instruction since the last proven AMM reserve
  snapshot. Carry-forward is proven unchanged AMM state, never imputation.
  OHLC remains null.
- `UNKNOWN_COVERAGE`: truncation or any other condition that prevents proving
  completeness. Volume and OHLC stay null.

Other-pool Buy/Sell events are exclusion evidence only. Migration is not
inferred from `index=0` or observation alone. Raw and virtual quote reserves
stay separate.

## PIT and availability

Required timestamps: `event_at`, `observed_at`, `first_reliable_available_at`,
`available_to_strategy_at`, `ingested_at`, `measured_as_of`. Do not backdate
historical retrieval to `blockTime`. Chain `blockTime` may be retained as
non-availability evidence. Derived availability is the maximum availability of
all required inputs. Retrospective market-history usability is separate from
prospective PIT-route usability. If first reliable availability cannot be
proved earlier than the retained A22/A23 capture, keep that later timestamp and
limit the decision.

## Terminal decisions

- `LIMITED_DIAGNOSTIC_PANEL_READY`: the 96-slot panel is reproducible with
  explicit limitations and may support one later frozen limited diagnostic, not
  a trial or alpha.
- `TARGETED_PROVIDER_CAPABILITY_GAP_PROVEN`: a named field, completeness,
  availability or universe requirement is missing from retained bytes.
- `REDESIGN_DATA`: the estimand cannot be represented without forbidden
  imputation or a changed public meaning.
- `STOP_INTEGRITY_CONFLICT`: identity, attribution or instruction/event
  mismatch; preserve evidence and stop.

`TASK-30` remains `BLOCKED_DATA`. This atom does not establish route
persistence, fillability, settlement, PnL, NetReturn, continuous price, alpha
or strategy promotion.
