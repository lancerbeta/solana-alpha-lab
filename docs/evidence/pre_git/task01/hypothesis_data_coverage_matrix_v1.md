---
artifact_id: SMIAL_TASK_01_HYPOTHESIS_DATA_COVERAGE_MATRIX
artifact_version: "1.0"
task_id: TASK-01
task_execution_status: DONE
owner: user+assistant
started_at: 2026-07-18
artifact_status: VALIDATED_COVERAGE_CONTRACT
as_of: 2026-07-18
entry_verdict: START_AS_WRITTEN
scope_completed: "provider-neutral domain inventory + preliminary official-docs candidate mapping"
provider_mapping_status: PRELIMINARY_OFFICIAL_DOCS_MAPPING_COMPLETE
provider_shortlist_status: PRELIMINARY_NO_ACCOUNTS_REQUIRED
source_contract_status: SOURCES_V1_DRAFT_CREATED_AND_STATICALLY_VALIDATED
data_option_tiers_status: DATA_OPTION_TIERS_V1_DRAFT_CREATED_AND_STATICALLY_VALIDATED
provider_cost_snapshot_status: PROVIDER_COST_SNAPSHOT_V1_DRAFT_CREATED_AND_STATICALLY_VALIDATED
reuse_candidate_registry_status: REUSE_CANDIDATE_REGISTRY_DATA_SUBSET_DRAFT_CREATED_AND_STATICALLY_VALIDATED
provider_decision_status: PROVIDER_DECISION_V1_DRAFT_CREATED
provider_account_checklist_status: PROVIDER_ACCOUNT_CHECKLIST_V1_DRAFT_CREATED
provider_smoke_spec_status: PROVIDER_SMOKE_SPEC_V1_DRAFT_CREATED_AND_STATICALLY_VALIDATED
api_rpc_provider_requests_executed: false
accounts_created: false
contains_secrets: false
procurement_constraint: "Prefer a goal-feasible crypto-payable service over a slightly cheaper or more convenient fiat-only alternative"
procurement_constraint_status: ACTIVE_USER_REQUIREMENT
crypto_asset_flexibility: "ANY_ASSET_ACCEPTED_BY_THE_SERVICE; no specific coin or stablecoin required"
iteration_footer_required: true
iteration_footer_fields: "ОТ ВАС СЕЙЧАС; ЧТО СДЕЛАЛ АССИСТЕНТ; СЛЕДУЮЩИЙ АТОМ; BLOCKER"
next_action: "User activates the coordinated canonical handoff; TASK-02 remains READY until a new Task Entry Gate. TASK-03 later imports validated TASK-01 artifacts and hashes into Git."
canonical_sources_sync: "PENDING_COORDINATED_TASK_HANDOFF; current Project Sources were not modified in this one-atom step"
---

# TASK-01 — Hypothesis/Data Coverage Matrix v1

## 0. Статус этого черновика

Это валидированный design contract после финального DoD/gap audit TASK-01: provider-neutral потребности, preliminary runtime mapping, machine-readable source contracts, data-option/cadence policy, cost/reuse reconciliation и frozen future smoke design. Все внешние факты получены только из официальной документации или официальных репозиториев, без endpoint calls.

Документ пока не утверждает:

- какой provider будет primary или fallback;
- что какой-либо endpoint фактически работает;
- что у пользователя есть provider account или entitlement;
- что pricing/dashboard claim подтверждён;
- что historical catalog создаёт наше `observed_at` или `available_to_strategy_at`;
- что выполнен хотя бы один API/RPC/provider request.

## 1. Правила классификации

### 1.1. Coverage state

| Значение | Смысл |
|---|---|
| `AVAILABLE_NOW` | Поле может быть получено стратегией в live/paper контуре после фактической validation |
| `RECONSTRUCTIBLE_LATER` | Историческую chain/market сущность можно восстановить, но не наше прежнее наблюдение |
| `FORWARD_ONLY` | Честно появляется только после начала нашего логирования |
| `PARTIAL_OR_VENDOR_DEPENDENT` | Coverage/revisions/universe зависят от provider и ещё не подтверждены |
| `MISSING` | Affordable/valid source пока не найден |
| `DERIVED_PIT` | Вычисляется только из PIT-safe upstream rows |

`AVAILABLE_NOW` в этом draft не присваивается: TASK-07 ещё не выполнил controlled smoke.

### 1.2. Data option tier

| Tier | Правило |
|---|---|
| `T0_CORE` | Невосстановимое либо обязательное для universe, execution, lineage, replay или экономического контроля |
| `T1_BUDGETED_REUSE` | Полезно нескольким families, но cadence/retention ограничиваются credits, storage и QA |
| `T2_HYPOTHESIS_SPECIFIC` | Дорогое или узкое enrichment; требуется отдельный hypothesis/data memo |

### 1.3. Timestamp minimum

Каждая внешняя observation должна поддерживать, где применимо:

```text
event_time
observed_at
available_to_strategy_at
ingested_at
```

On-chain event time не доказывает, что стратегия уже знала событие. Поле получает реальный `first_reliable_available_at` только после TASK-07/пилота; до этого значение `UNSET_UNTIL_VALIDATED`.

### 1.4. Procurement/payment constraint

Пользователь предпочитает provider/infra/service, который можно оплатить **хотя бы одним поддерживаемым сервисом криптоактивом**, даже если goal-feasible аналог немного дороже или менее удобен, чем fiat-only вариант. Требования к конкретной монете или stablecoin нет: пользователь может подстроиться под документированно принимаемый сервисом актив.

Decision order:

1. Сначала обязательны technical fit, data/execution truth, security, terms, reliability и достижение DoD.
2. Среди прошедших обязательный gate преимущество получает documented crypto-payable вариант.
3. Допустим умеренный price/convenience premium, но его точная величина не выдумывается: перед покупкой показываются full TCO, ограничения и более дешёвая альтернатива.
4. Fiat-only provider допустим только если ни один crypto-payable кандидат не достигает обязательного contract либо несёт materially худший security/terms/TCO; требуется explicit exception memo и решение пользователя.
5. Бесплатный plan можно использовать без penalty, даже если будущий paid checkout fiat-only; upgrade path всё равно маркируется заранее.

Для каждого платного кандидата позже фиксируются:

```text
payment_mode = crypto_direct | crypto_documented_processor | fiat_only | unknown
accepted_assets_or_rail
recurring_or_manual_renewal
KYC/region/terms constraints
refund/cancellation path
payment evidence state + as_of
```

Оплату всегда выполняет пользователь. Wallet address, transaction details, seed/private key, cookies и screenshots checkout/billing в project artifacts не сохраняются.

## 2. Provider-neutral required-domain inventory

`Next-family` ниже означает только plausible future consumer и **не регистрирует новую проверенную гипотезу или trial**.

| Domain ID | Domain / обязательные field groups | Почему нужен | Named consumers | Initial coverage | Irrecoverability | Initial tier | Предварительный collection mode |
|---|---|---|---|---|---|---|---|
| `D01` | Universe discovery: mint/token ID, launchpad, creation signature/slot, creator, lifecycle state, eligibility reason, first/last seen | Не допустить winner-only и migrated-only universe | H01–H18; TASK-08/20/21 | Chain facts `RECONSTRUCTIBLE_LATER`; наше discovery/omissions `FORWARD_ONLY` | High | `T0_CORE` | Event discovery + low-rate reconciliation |
| `D02` | Token/program identity: mint/quote mint, decimals, token program, authorities, metadata version, program IDs | Правильные units/decoder и защита от protocol drift | H01/H04/H05/H06/H17; TASK-05/08/09 | Mostly `RECONSTRUCTIBLE_LATER`; provider decode time `FORWARD_ONLY` | Medium | `T0_CORE` | Event + change-triggered |
| `D03` | Pump bonding-curve state: complete flag, real/virtual base and quote reserves, `quote_mint`, instruction/program version, fee-state reference | Определить lifecycle и не hardcode устаревшую SOL-only математику | H01/H03/H11/H17; TASK-05/08/09/26 | Chain state partly `RECONSTRUCTIBLE_LATER`; exact observed state `FORWARD_ONLY` | High | `T0_CORE` | Lifecycle sentinel + completion trigger |
| `D04` | Migration/canonical pool: migration eligibility, fee observed, migration signature/slot, destination venue/pool, initial pool state, failed/non-migrated terminal state | Не смешивать launch, migration и signal-eligible universe | H01/H11/H17; TASK-08/09/20 | Successful chain events `RECONSTRUCTIBLE_LATER`; missed/failed observation semantics `PARTIAL_OR_VENDOR_DEPENDENT` | High | `T0_CORE` | Event-triggered + reconciliation |
| `D05` | Pool truth: pool ID/type/version, token accounts, reserves, effective/virtual quote reserves, LP/liquidity changes, fee schedule/version, price/depth inputs | Liquidity USD не равна sellable capacity; требуется versioned pool truth | H01/H02/H03/H07/H08/H10/H16; TASK-05/09/10/26 | Raw state often `RECONSTRUCTIBLE_LATER`; high-frequency path `FORWARD_ONLY` | High | `T0_CORE` for raw state; `T1_BUDGETED_REUSE` for dense depth | Base sentinel + state-triggered |
| `D06` | Trades/swaps: signature/index, slot/block time, pool, side, atomic in/out, mints, trader, success/error, fee fields, source/schema version | Flow, sell-pressure, breadth и outcome без candle-only иллюзии | H01/H02/H03/H09/H10/H14/H18; TASK-08/09/20/21 | On-chain trades `RECONSTRUCTIBLE_LATER`; indexed classification/revisions `PARTIAL_OR_VENDOR_DEPENDENT` | Medium | `T0_CORE` | Event stream/poll + dedupe |
| `D07` | PIT market references: VWAP, peak/drawdown, impulse velocity, lifecycle clocks, adjusted flow aggregates, bar-close availability | Сигнал должен вычисляться только из уже доступных events | H01/H02/H03/H10/H11/H18 | `DERIVED_PIT` | High if upstream observation lost | `T0_CORE` | Derived from versioned upstream only |
| `D08` | Executable quote panel: request time, response time, input/output mint and atomic amount, buy/sell, notionals, route legs/count, context slot, quoted output, price impact attribution, fee fields, validity/expiry | Главный тест execution illusion и capacity | H01/H02/H03/H07/H08/H13/H16/H17; TASK-07/10/25/26/29 | `FORWARD_ONLY` | Critical | `T0_CORE` | Bounded base sentinel + triggered panel |
| `D09` | Quote/route failures: no-route, HTTP/provider error class, timeout, stale context, invalid mint/amount, simulation/build refusal, retry/requote link | Missing/no-route нельзя превращать в zero или удалять | H07/H08/H13/H16/H17; TASK-06/07/10/25 | `FORWARD_ONLY` | Critical | `T0_CORE` | Every attempted quote, including failures |
| `D10` | Execution/landing evidence: signal→quote→build→simulate→send timestamps, blockhash age, send path, signature, terminal state, actual deltas, base/priority/relay fees, retry chain | Отличить Fillable от Realized и оценить strategy-specific landing | H08/H13/H16/H17; TASK-25/26/29/35+ | Paper quote subset `FORWARD_ONLY`; sends запрещены до later gates | Critical | `T0_CORE` | Schema now; collection only at authorized later stages |
| `D11` | Holder snapshots: raw balances/supply, top-N, excluded program/pool accounts, creator share, snapshot slot/time, source revision | Concentration и supply-control veto без hindsight | H05/H06/H09/H14/H15; TASK-11/20 | Current state reconstructibility limited; historical snapshots `PARTIAL_OR_VENDOR_DEPENDENT` | High | `T1_BUDGETED_REUSE` | Sparse base + lifecycle/signal triggers |
| `D12` | Entity/deployer/funder/bundle inputs: deployer launch history known then, funder graph, common ownership evidence, synchronized activity, label source/version/confidence | Toxicity avoidance и sybil-adjusted breadth | H04/H05/H06/H09/H14/H15; TASK-11/20 | Raw transfers often `RECONSTRUCTIBLE_LATER`; entity inference revisions `PARTIAL_OR_VENDOR_DEPENDENT` | Medium–High | `T1_BUDGETED_REUSE` | Triggered enrichment with budget cap |
| `D13` | Liquidity/creator actions: LP add/remove, creator/related-wallet sells, fee collection, inactivity/route death events | Distinguish organic continuation from controlled exit/liquidity withdrawal | H02/H04/H06/H07/H10/H16; next toxicity/liquidity families | Chain events `RECONSTRUCTIBLE_LATER`; attribution `PARTIAL_OR_VENDOR_DEPENDENT` | Medium | `T1_BUDGETED_REUSE` | Event + suspicious-state trigger |
| `D14` | Network state: slot/block time, commitment, recent prioritization fees, congestion proxies, RPC/provider latency, blockhash validity context | Execution feasibility and causal separation from strategy failure | H08/H16/H17; TASK-10/25/26 | Chain history partly `RECONSTRUCTIBLE_LATER`; local latency `FORWARD_ONLY` | Medium–High | `T1_BUDGETED_REUSE` | Low-rate sentinel + quote/send context |
| `D15` | Observation lineage: provider/product, request class, auth-plan label without secrets, request hash, raw payload hash, schema/program version, revision link, four timestamps, confidence, disagreement ID | Replay, provider drift, leakage control и auditability | All hypotheses; TASK-05/06/07/16/17 | `FORWARD_ONLY` | Critical | `T0_CORE` | Every observation/error, append-only |
| `D16` | Provider/service quality: response class, latency, 429/quota signal, documented credits/CU, observed credit delta later, outage/divergence, retry policy | Не перепутать provider outage с market no-route и контролировать spend | H08/H16; TASK-07/10/12/15 | Docs `PARTIAL_OR_VENDOR_DEPENDENT`; measurements `FORWARD_ONLY` | High | `T0_CORE` control telemetry | Every controlled request; no calls in TASK-01 |
| `D17` | Cohort/regime context: SOL returns/volatility, launch/migration breadth, cohort breadth, liquidity/session buckets, regime availability timestamp | Outer gate и alternative-world checks | H12/H18; next regime/portfolio families | Market history mostly `RECONSTRUCTIBLE_LATER`; selected feature availability `DERIVED_PIT` | Low–Medium | `T1_BUDGETED_REUSE` | Coarse low-frequency snapshots |
| `D18` | Vendor/social/smart-money enrichment: proprietary risk score, social momentum, vendor PnL labels, sentiment, influencer/attention data | Только узкие deferred hypotheses; высокий leakage/revision risk | H15; possible future social family | `PARTIAL_OR_VENDOR_DEPENDENT` or `MISSING` | Medium | `T2_HYPOTHESIS_SPECIFIC` | Excluded until approved memo |
| `D19` | Economic/procurement control: provider/VPS/storage/software cash cost, credits/CU consumed, payment mode (`crypto_*`/`fiat_only`/`unknown`), accepted payment rail, renewal/cancellation, bytes/events, QA/operator time shadow cost, upgrade condition | Business mission = owner cashflow; crypto-payable goal-feasible service preferred over slightly cheaper/more convenient fiat-only alternative | TASK-01/12/15/16/47; all future RC budgets | Pricing/payment docs `PARTIAL_OR_VENDOR_DEPENDENT`; cash/usage receipts `FORWARD_ONLY` | High | `T0_CORE` control | Per decision/task + monthly rollup |
| `D20` | Outcomes/labels: executable entry time, path-aware exits, buy/sell quote availability, realized/hypothetical deltas, no-exit/route-death terminal state, NetReturn components and non-overlap flags | Фальсифицируемая цель вместо candle high | H01–H18; TASK-20/21/25/26/29 | `DERIVED_PIT`; forward quote/execution inputs required | Critical | `T0_CORE` | Versioned derivation after upstream validation |

## 3. Preliminary family coverage map

| Family / experiment | Minimum domain set | Critical forward-only dependency | Cheapest falsification path |
|---|---|---|---|
| `H13` baseline + composite toxicity veto | D01–D09, D11–D16, D20 | Sell quotes, no-route/errors, observed entity snapshots | Compare simple baseline vs veto; kill if execution-aware CVaR/NetEV does not improve |
| `H07 + H01` liquidity-retention continuation | D01, D04–D09, D13–D16, D20 | Multi-notional sell quote persistence | Test route/depth survival before complex prediction |
| `H02` controlled pullback/reclaim | D01, D05–D10, D13–D16, D20 | Quote state at reclaim and exit decisions | Same-drawdown cohort comparison after quote-aware costs |
| `H08` execution/capacity gate | D05, D08–D10, D14–D16, D19–D20 | Buy/sell quote panel and failure surface | Notional sweep; close strategy version if edge vanishes at intended size |
| `H16` route-deterioration veto | D05, D08–D10, D14–D16, D20 | Repeated sell quote/no-route trajectory | Check whether deterioration predicts no-exit beyond provider outage |
| Next toxicity-avoidance family | D01/D02/D06/D11–D16/D20 | PIT entity/holder observation history | Test tail-loss reduction; do not call avoidance entry alpha |
| Next lifecycle-survival family | D01–D06/D11–D17/D20 | Complete dead/non-migrated universe observation | Cheap hazard/baseline before trading simulation |
| Next pure execution/capacity family | D05/D08–D10/D14–D16/D19/D20 | Strategy-specific quote/landing logs | Break-even/capacity frontier before signal search |

## 4. First-step findings

1. `D08`, `D09`, `D15`, `D16` и часть `D19` — наиболее невосстановимые assets: historical chain catalog их не заменит.
2. Honest universe требует сохранять failed/non-migrated/inactive cases через `D01/D04`, иначе любой later backtest будет survivor-biased.
3. Текущая архитектура не должна начинаться с holder/social enrichment: `D18` исключён, а `D11/D12` остаются budgeted/triggered.
4. Quote panel нужен не только при сигнале: ограниченный sentinel создаёт option value для будущих families, но cadence/caps будут определены после provider cost mapping.
5. Provider schema не может стать canonical schema: этот inventory является верхним contract layer, а mappings будут добавляться ниже.
6. Payment compatibility — отдельная procurement dimension: она не может компенсировать провал technical/security DoD, но влияет на выбор между прошедшими кандидатами.

## 5. Validation этого атома

- [x] RC-001 top experiments и mandatory execution gate имеют named domain consumers.
- [x] Plausible next families обозначены без регистрации новых hypotheses/trials.
- [x] Dead/non-migrated/no-route/error states включены.
- [x] `event_time` отделён от фактической доступности стратегии.
- [x] T2 enrichment исключён без memo.
- [x] Business cost/credits/operator burden включены с TASK-01.
- [x] Пользовательское предпочтение crypto-payable services включено с explicit exception rule и без выполнения платежей.
- [x] Provider/product/endpoints не выбраны до evidence mapping.
- [x] API/RPC/provider requests не выполнялись.
- [x] Secrets и credentials отсутствуют.

## 6. Truth layers и запрет на «одного всезнающего provider»

| Layer | Что считается правдой | Что не разрешено |
|---|---|---|
| `PROTOCOL_TRUTH` | Raw Solana account/transaction state, официальный IDL/program documentation, slot/commitment | Подменять protocol state vendor risk score, human-readable parser или candle |
| `TRANSPORT_OR_INDEX` | RPC/WSS transport, indexed discovery, parsed transactions, holder/deployer convenience | Объявлять vendor decode без raw lineage единственным source of truth |
| `EXECUTABLE_QUOTE_REALITY` | Двусторонний quote для точного mint/amount/time с route, fees, context и error/no-route | Использовать candle close, spot price API или reserve formula как доказательство fillability |
| `LOCAL_OBSERVATION_TRUTH` | Наш append-only envelope, request/response time, raw hash, failure, plan/credits и revision link | Реконструировать задним числом наше прежнее знание из исторического каталога |
| `DERIVED_PIT` | Расчёт только из строк, доступных стратегии на decision timestamp | Backfill feature без честного `first_reliable_available_at` |

Следствие: один provider может занимать несколько ролей, но не получает неограниченного доверия. `Primary` ниже означает предпочтительный компонент конкретного domain contract, а не универсальную истину.

## 7. Official evidence registry

`as_of = 2026-07-18`. Доступность URL проверена read-only web retrieval. Pricing/payment остаются mutable и повторно проверяются перед account/purchase decision.

| ID | Кандидат и допустимая роль | Official evidence | Подтверждено документацией | Evidence state / ограничения |
|---|---|---|---|---|
| `P01` | Solana RPC/program state — protocol truth и стандартный interface | https://solana.com/docs/rpc | HTTP/WSS read/subscription methods, commitments; public mainnet RPC shared и не предназначен для production | `official_docs`; конкретный paid transport всё равно нужен после smoke |
| `P02` | Pump/PumpSwap public docs + IDL — decoder/program-version truth | https://github.com/pump-fun/pump-public-docs | Official IDL/docs; `quote_mint`, v2 instructions и effective/virtual quote reserve semantics существуют | `official_repo`; pin commit/checksum later; docs не заменяют raw observations |
| `P03` | Helius — preliminary raw RPC/WSS transport и optional parsed convenience | https://www.helius.dev/docs/billing/plans ; https://www.helius.dev/docs/api-reference/enhanced-transactions/overview ; https://www.helius.dev/docs/billing/pay-with-crypto | Free: 1M credits/month, 10 RPC RPS, standard Solana WSS; Enhanced parser covers swaps/transfers; paid crypto via USDC on Solana | `official_docs + TASK07_validation_required`; parser is vendor decode; no gRPC purchase initially |
| `P04` | Jupiter Developer Platform — preliminary executable quote source | https://developers.jup.ag/docs/swap ; https://developers.jup.ag/docs/portal/plans | Current Swap v2 uses `/swap/v2/order`+`/execute` or `/swap/v2/build`+`/tx/v1/submit`; keyless 0.5 RPS, Free 1 RPS; paid plans accept USDC on Solana | `official_docs + TASK07_validation_required`; actual coverage/no-route/fee fields are not yet validated |
| `P05` | Solana Tracker — indexed discovery/enrichment and possible cross-check | https://docs.solanatracker.io/pricing | Data API advertises 70+ endpoints, token/trade/OHLCV/risk/PnL; Free 10k requests/month at 3 RPS; hosted Datastream is Premium+; self-hosted Raptor listed free | `official_docs`; universe/PIT/revision/field quality require TASK-07; payment rail `official_dashboard_needed` |
| `P06` | Birdeye — secondary market/holder/trade cross-check | https://docs.birdeye.so/docs/pricing ; https://docs.birdeye.so/docs/data-accessibility-by-packages ; https://docs.birdeye.so/docs/payment | Tiered CU model and endpoints; crypto payments in USDC/USDT documented for 3/6/12-month subscriptions via contact | `official_docs`; no long subscription or purchase before measured need; dashboard entitlement check later |
| `P07` | Dune Solana catalog — historical discovery/backfill/reference | https://docs.dune.com/data-catalog/solana/overview | Raw and decoded transactions, blocks, instructions and account activity are indexed | `official_docs`; not live executable truth and cannot fabricate our historical `observed_at` |
| `P08` | Local append-only pipeline — observation, lineage, cost and derived PIT truth | This contract + future TASK-05/06 artifacts | Required fields/timestamps/failures are under project control | `design_only`; implementation/validation are downstream |

### 7.1. Procurement compatibility

| Candidate | Current cost posture | Payment state | TASK-01 decision |
|---|---|---|---|
| Helius | Start on Free; paid only after measured bottleneck | `crypto_direct`: USDC on Solana; manual renewal link available, auto-wallet authorization optional | `PASS_PAYMENT_GATE`; auto-pay remains off by default |
| Jupiter | Start keyless or Free as specified by future smoke; no paid need now | `crypto_documented_processor`: USDC on Solana via Moonpay/Stripe flow | `PASS_PAYMENT_GATE` |
| Solana Tracker | Free Data API candidate; no Premium/Datastream purchase | Docs show EUR pricing but do not state payment rail | `official_dashboard_needed`; does not block free shortlist |
| Birdeye | Secondary only; free/shortest sufficient until measured gap | USDC/USDT documented only for longer subscriptions | `PASS_WITH_TERM_CONSTRAINT`; no prepayment |
| Raw Solana/Pump docs | Public documentation/interface | No purchase | `NOT_APPLICABLE` |
| Dune catalog | Reference candidate only in this atom | Payment not needed for reference decision | `DEFER_PURCHASE_REVIEW` |

Crypto preference therefore does not currently create a technical compromise: preliminary primary Helius and Jupiter upgrade paths both pass it. No service, account or plan is being purchased.

## 8. Domain → source candidate mapping

Evidence suffixes:

- `OD` — official docs/repository inspected;
- `S07` — claims must be tested by controlled requests in TASK-07;
- `DB` — official authenticated dashboard/user attestation required;
- `GAP` — no equivalent fallback yet;
- `INT` — generated and validated internally.

| Domain | Preliminary primary contract | Fallback / cross-check | Evidence state and unresolved risk |
|---|---|---|---|
| `D01` Universe discovery | `P03` standard WSS/RPC transport + `P01/P02` program/event semantics | `P05` indexed reconciliation; `P07` historical missed-case audit | `OD+S07`; live completeness, reconnect loss and non-migrated terminal coverage unmeasured |
| `D02` Token/program identity | `P01` raw accounts + official Token/Pump program semantics `P02` | `P03` DAS/parsed convenience; `P05/P06` metadata comparison | `OD+S07`; metadata revisions and Token-2022 edge cases need fixtures |
| `D03` Bonding-curve state | `P01` account state decoded by pinned `P02` IDL/version | `P03` transport; `P05/P07` historical cross-check | `OD+S07`; decoder must not hardcode SOL-only or ignore effective quote reserves |
| `D04` Migration/canonical pool | `P01/P02` raw instructions/events and destination account state | `P03` transport; `P05` graduating/graduated index; `P07` backfill | `OD+S07`; failed/non-migrated definitions and provider lag unresolved |
| `D05` Pool truth | Raw pool accounts/transactions via `P01`, official venue/Pump semantics `P02` | `P03` transport; `P05/P06/P07` disagreement checks | `OD+S07`; DEX-version coverage registry still required; indexed liquidity is not truth |
| `D06` Trades/swaps | Raw successful/failed transactions `P01` + pinned program decoders | `P03` Enhanced parser convenience; `P05/P06` indexed comparison; `P07` history | `OD+S07`; parser classification/revision and inner-instruction coverage must be measured |
| `D07` PIT market references | `P08` deterministic derivation from D01–D06 available rows | Recompute from immutable raw payloads/schema version | `INT`; no external provider may write final feature values directly |
| `D08` Executable quote panel | `P04 /swap/v2/order` for exact buy/sell amount/time; Router path retained as controlled alternative | Protocol reserve reconstruction and `P05` Raptor are only diagnostic candidates, not equivalent fillability proof | `OD+S07+GAP`; independent executable quote fallback is not established |
| `D09` Quote/route failures | `P08` stores every `P04` response/error/timeout/no-route attempt | Local retry-classification replay; no substitute for unobserved failure | `OD+S07+GAP`; response taxonomy and rate-limit separation need TASK-07 |
| `D10` Execution/landing evidence | Future `P04` order/build + execute/submit evidence joined to `P01/P03` status and actual deltas | Direct standard RPC send/status path only after later authorization | `OD+S07`; schema only now; no signing/simulation/send in TASK-01 |
| `D11` Holder snapshots | `P01` token accounts/supply at explicit slot + local exclusions | `P03` DAS and `P05/P06` holder snapshots; `P07` history | `OD+S07`; vendor top-holder rules and historical snapshot availability may differ |
| `D12` Entity/deployer/funder inputs | Raw transfers/accounts `P01` + versioned local inference `P08` | `P05` deployer/bundler fields, `P03` parsed data, `P07` historical graph | `OD+S07`; vendor labels/PnL are evidence with confidence, never ground truth |
| `D13` LP/creator/liquidity actions | Raw instructions/balance deltas `P01/P02` + local attribution | `P03` Enhanced parser; `P05/P06/P07` cross-check | `OD+S07`; entity attribution and venue decoder coverage unresolved |
| `D14` Network state | `P01` slot/blockhash/commitment/recent prioritization fee methods | `P03` RPC and Priority Fee convenience; provider-local latency in `P08` | `OD+S07`; network-wide metrics cannot become strategy landing probability |
| `D15` Observation lineage | `P08` raw envelope, hashes, four timestamps, provider/schema/program versions | Append-only backup/replay downstream | `INT`; fully forward-only and mandatory before collector |
| `D16` Provider quality | `P08` local request telemetry + each provider's official pricing/status/dashboard | Cross-provider same-case comparison designed for TASK-07 | `OD+DB+S07`; marketing SLA is not observed reliability |
| `D17` Cohort/regime context | `P08` PIT derivation from coarse raw market/network/universe inputs | `P05/P06` OHLCV reference; `P04` price only as heuristic input | `OD+S07+INT`; vendor candles cannot set decision-time availability by themselves |
| `D18` Vendor/social/smart-money | No initial source: excluded T2 | `P05/P06` risk/PnL/security candidates only after approved hypothesis/data memo | `DEFERRED`; avoids buying leakage-prone enrichment without consumer |
| `D19` Cost/procurement | `P08` cost ledger + official plan/payment evidence `P03–P06` | Authenticated dashboard/user attestation before purchase | `OD+DB+INT`; receipts/wallet/keys never enter artifacts |
| `D20` Outcomes/labels | `P08` versioned path-aware derivation using D01–D10 and executable buy/sell evidence | Raw-chain realized deltas for later authorized executions; never candle high alone | `INT+S07`; route-death/no-exit remains a terminal outcome, not missing row |

## 9. Preliminary shortlist and reuse gate

Это **не** account checklist и не финальный purchase decision.

| Candidate | Gate | Предварительное решение | Почему |
|---|---|---|---|
| Solana RPC interface + Pump official IDLs/docs | `ADOPT_AS_REFERENCE` | Adopt and pin versions/checksums later | Это минимальный protocol truth слой; создание собственного protocol specification с нуля повысило бы drift risk |
| Helius Free RPC/standard WSS | `WRAP` | Primary transport candidate for TASK-07 smoke | Покрывает raw interface/WSS на free tier, crypto upgrade path; требует reconnect/credit/schema validation |
| Jupiter Swap v2 | `WRAP` | Primary executable quote candidate for TASK-07 smoke | Текущий официальный route/quote interface; crypto upgrade path; не заменяет собственный error/latency envelope |
| Solana Tracker Free Data API | `WRAP` | Indexed convenience candidate, not truth | Высокий information gain для discovery/entity/holder comparison при ограниченном free budget; payment и PIT semantics unresolved |
| Birdeye | `WRAP_LATER_IF_GAP` | Secondary cross-check, no account/purchase now | Дублирует часть indexed coverage; long-duration crypto terms делают раннюю покупку нерациональной |
| Dune Solana catalog | `ADOPT_AS_REFERENCE` | Historical discovery/backfill/cross-check only | Экономит собственное сканирование history, но не создаёт live/PIT/executable evidence |
| Solana Tracker Raptor hosted beta | `WRAP` | Один bounded unsigned quote comparator в TASK-07 после due diligence | Официально заявлен public beta, сейчас free/no stated rate limits; это дешёвый способ отделить Jupiter-specific gap от market route death, но не SLA и не fill proof |
| Solana Tracker Raptor self-hosted | `DEFER` | Review in TASK-04/07 only if hosted comparison leaves a measured gap | Self-hosted binary adds license/supply-chain/ops burden; zero licensing fee не означает zero TCO |
| Helius/Solana Tracker gRPC, dedicated nodes | `DEFER` | Do not buy/build initially | Premature throughput/complexity before free-tier measurements and hypothesis kill tests |

### 9.1. Материальный gap

`D08/D09`: Jupiter имеет сильный preliminary contract, но независимый **эквивалентный** executable-quote fallback пока не доказан. Reserve math, candle, Birdeye price и indexed swap history не являются заменой. Это не блокирует TASK-01 на текущем шаге: gap должен стать explicit smoke/architecture risk с одним из исходов после TASK-07:

1. Jupiter coverage/reliability достаточны для bounded research panel;
2. Raptor/другой router проходит отдельный due-diligence и controlled comparison;
3. scope ограничивается venues/notionals, где quote contract валиден;
4. `REDESIGN_DATA`, если affordable executable truth недостижима.

## 10. Validation второго атома

- [x] Все `D01…D20` имеют preliminary primary contract и fallback либо явный `GAP`.
- [x] Protocol truth отделена от indexed convenience и executable quote reality.
- [x] Helius, Jupiter, Solana Tracker, Birdeye, raw Solana/Pump и Dune проверены по официальным источникам.
- [x] Mutable pricing/payment claims имеют `as_of` и evidence state.
- [x] Пользовательское правило asset-agnostic crypto payment применено без скрытого требования конкретной монеты.
- [x] Не найденный payment rail Solana Tracker оставлен `official_dashboard_needed`, а не выдуман.
- [x] Jupiter independent quote fallback не замаскирован historical/price proxy.
- [x] `ADOPT → WRAP → FORK → BUILD` gate применён; собственная реализация не начата.
- [x] API/RPC/provider requests, endpoint probing, accounts, purchases и external writes не выполнялись.
- [x] Автоматическое списание/подключение wallet не предлагалось и не выполнялось.

## 11. Machine-readable source contract

Создан `sources_v1.yaml` на базе этой карты:

```text
source role + truth layer
→ product/endpoint class (design only)
→ auth/account state
→ mutable evidence URL/as_of/state
→ timestamps/revisions/raw retention
→ primary/fallback and failure semantics
→ payment state and upgrade gate
```

Static validation: YAML parse, unique source/product IDs, D01–D20 completeness, source-reference integrity, evidence-state enum, HTTPS evidence URLs, executable-quote gap preservation, crypto-payment policy, task boundary и secret-pattern scan — `PASS`.

## 12. Data-option and cadence contract

Создан `data_option_tiers_v1.yaml`: T0/T1/T2, 12 collection profiles, base/triggered quote panels, provisional provider credit caps, retention classes, QA budgets и automatic stop rules. Все числовые thresholds маркированы как engineering caps, а не рыночная истина, и должны быть подтверждены/исправлены по TASK-07/пилоту.

## 13. Cost and reuse reconciliation

Созданы:

- `provider_cost_snapshot_v1.csv` — 26 plan/product records без FX-конверсии и ложных TCO; `UNKNOWN` не превращён в zero; `purchase_now=false` для каждой строки.
- `reuse_candidate_registry.yaml` — data-source/decoder/router subset для gate `ADOPT → WRAP → FORK → BUILD`; полный software gate остаётся в TASK-04.

Материальные решения:

1. Raptor hosted beta retained как optional TASK-07 unsigned quote comparator, но не runtime dependency и не эквивалент fillability.
2. Vixen, Old Faithful, Hummingbot и self-hosted Raptor не входят в initial spine: их license/maturity/ops/security cost превышает текущий information gain.
3. Dune и official Solana/Pump semantics переиспользуются как references, но не подменяют forward-only observation truth.
4. Birdeye-specific `x402` подтверждён прямой официальной reference page: USDC on Solana, no API key/subscription, per-request route-specific terms. Цена конкретного route неизвестна без payment challenge; wallet/signing/payment остаются запрещены до measured gap, explicit approval и signer-security gate. Canonical roadmap не требует patch по факту доступности.

Static validation: CSV parse/schema/unique IDs/26 rows/all `purchase_now=false`/unknown-not-zero; YAML parse/unique candidate IDs/gate/official provenance/license state/security/TCO/exit path; cross-file handoff and secret scan — `PASS`.

## 14. Provider decision, account boundary and frozen smoke design

Созданы:

- `provider_decision_v1.md` — бесплатный conditional shortlist и upgrade/stop gates;
- `provider_account_checklist_v1.md` — beginner-safe just-in-time account workflow; сейчас accounts не нужны;
- `provider_smoke_spec_v1.yaml` — 34 exact future cases / 35 planned attempts, hard cap 50, cash cap `$0`, concurrency 1.

Smoke охватывает Helius RPC/WSS, Solana Tracker indexed discovery/holders, Jupiter quote-only `/order` и optional matched Raptor `/quote`. Запрещены build/simulate/sign/send/execute/submit, `taker/payer/receiver`, x402/payment, retries by default и любое превышение frozen caps.

## 15. Следующий атом

TASK-01 завершён только как validated design task. Пользователь устанавливает coordinated canonical handoff; TASK-02 не начинается автоматически. На TASK-03 все validated TASK-01 artifacts, hashes и validation evidence импортируются в private Git registry без переписывания истории.
