# Quote-Native Evidence Channel Qualification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to execute this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run exactly one Free-key Jupiter quote-native campaign that either qualifies the existing evidence channel or durably pauses/closes it without creating a new provider, paid tier, hypothesis trial, or execution capability.

**Architecture:** Preserve the completed keyless campaign and its v8 registry semantics. Add an append-only v9 registry with three credentialed Jupiter bindings and a narrowly scoped runner that reuses the existing cohort-selection, schedule, and scoring semantics while owning only credential injection, safe response telemetry, global pacing, and typed terminal outcomes.

**Tech Stack:** Python 3.11+, stdlib `urllib`/`ssl`/`socket`/`hashlib`, PyYAML, JSON Schema, `unittest`, `uv`, Delivery Harness.

## Global Constraints

- Use only `JUPITER_API_KEY` from the current process environment; never load `.env`, print a key, write it to a URL, receipt, raw manifest, Git, or test fixture.
- One credential-free DNS/TCP/TLS preflight must complete before the one allowed credential read and before every provider request.
- Only `https://api.jup.ag/tokens/v2/recent`, `https://api.jup.ag/tokens/v2/toptraded/1h`, and `https://api.jup.ag/swap/v2/order` are permitted.
- Preserve six RECENT plus six TRADED cells, liquidity floor, notional, t0/H900/H3600 semantics, success floors (`>=10` complete X/Y and `>=6` time-separated), and the TRADED control kill.
- Provider-call cap is 60; one global clock enforces at least 3 seconds between all discovery and quote calls; retries and fallbacks are zero.
- `429`, insufficient complete Free-key sample, or the TRADED control kill terminally pauses/closes the current quote-native alpha route. `401`/`403` is a single owner-action result, not an automatic retry.
- No taker, `/build`, `/execute`, wallet, signer, transaction, paid tier, second provider, background scheduler, alpha claim, or mechanism audition.
- Preserve v8 routes byte-for-byte. Registry records bind capability only and never grant an external call.
- Retain only `x-api-gateway-request-id` and `retry-after` response headers when present; all other response headers are excluded from receipts.
- Do not commit unless the owner explicitly asks for a commit.

---

### Task 1: Reconcile the keyless campaign and bind the v9 route contract

**Files:**
- Modify: `docs/tasks/QUOTE_NATIVE_EVIDENCE_CHANNEL_QUALIFICATION_V1.md`
- Modify: `docs/tasks/QUOTE_NATIVE_LIVE_VARIATION_CAMPAIGN_V1.md`
- Create: `docs/evidence/quote_native_live_variation_campaign/a2_replan_closure_v1.json`
- Create: `configs/provider_route_capability_registry_v9.yaml`
- Create: `catalog/schemas/provider_route_capability_registry_v9.schema.json`
- Create: `src/solana_alpha_lab/provider_route_capability_registry_v9.py`
- Create: `tests/test_provider_route_capability_registry_v9.py`

**Interfaces:**
- Consumes: immutable `configs/provider_route_capability_registry_v8.yaml`, its SHA-256, and the prior campaign runtime/acceptance SHA-256 values.
- Produces: `validate_provider_route_capability_registry_v9(registry, *, predecessor, predecessor_sha256, v7_registry, v7_sha256, v6_registry, v6_sha256) -> tuple[Mapping[str, Any], ...]`.
- Produces three v9-only route IDs:
  - `JUPITER-SOLANA-TOKENS-V2-RECENT-FREE-API-KEY-001`
  - `JUPITER-SOLANA-TOKENS-V2-TOPTRADED-FREE-API-KEY-001`
  - `JUPITER-SOLANA-SWAP-V2-ORDER-FREE-API-KEY-001`

- [ ] **Step 1: Write failing registry and closure tests**

```python
def test_v9_preserves_every_v8_route_and_adds_only_three_credentialed_bindings() -> None:
    routes = validate_provider_route_capability_registry_v9(
        _v9(),
        predecessor=_v8(),
        predecessor_sha256=V8_SHA256,
        v7_registry=_v7(),
        v7_sha256=V7_SHA256,
        v6_registry=_v6(),
        v6_sha256=V6_SHA256,
    )
    assert len(routes) == 12
    assert [semantic_sha256(route) for route in routes[:9]] == [
        semantic_sha256(route) for route in _v8()["routes"]
    ]
    assert {route["route_id"] for route in routes[9:]} == FREE_KEY_ROUTE_IDS
    assert {route["access_class"] for route in routes[9:]} == {"LOCAL_ENV_CREDENTIAL"}
    assert all(route["execution_policy"]["authority_granted"] is False for route in routes[9:])

def test_replan_closure_binds_prior_sample_invalid_evidence_without_rewriting_it() -> None:
    closure = json.loads(CLOSURE_PATH.read_text(encoding="utf-8"))
    assert closure["prior_terminal"] == "SAMPLE_INVALID_INSUFFICIENT_COMPLETE_XY"
    assert closure["replan"] == "QUOTE_NATIVE_EVIDENCE_CHANNEL_QUALIFICATION_V1"
    assert closure["prior_runtime_sha256"] == PRIOR_RUNTIME_SHA256
    assert closure["prior_acceptance_sha256"] == PRIOR_ACCEPTANCE_SHA256
```

- [ ] **Step 2: Run the registry test to verify it is RED**

Run:

```powershell
uv run --locked --managed-python python -B -m unittest tests.test_provider_route_capability_registry_v9 -v
```

Expected: `ModuleNotFoundError` for `provider_route_capability_registry_v9` or a missing-file failure.

- [ ] **Step 3: Implement the append-only v9 validator and declarative registry**

```python
def validate_provider_route_capability_registry_v9(
    registry: Mapping[str, Any],
    *,
    predecessor: Mapping[str, Any],
    predecessor_sha256: str,
    v7_registry: Mapping[str, Any],
    v7_sha256: str,
    v6_registry: Mapping[str, Any],
    v6_sha256: str,
) -> tuple[Mapping[str, Any], ...]:
    _require(predecessor_sha256 == V8_SHA256, "V8_BYTES_DRIFT")
    v8_routes = validate_provider_route_capability_registry_v8(
        predecessor,
        predecessor=v7_registry,
        predecessor_sha256=v7_sha256,
        v6_registry=v6_registry,
        v6_sha256=v6_sha256,
    )
    routes = _routes(registry, expected_count=12)
    for previous, current in zip(v8_routes, routes[:9], strict=True):
        _require(_semantic_sha256(previous) == _semantic_sha256(current), "PRESERVED_ROUTE_DRIFT")
    for route, route_id, endpoint, operation in zip(
        routes[9:], FREE_KEY_ROUTE_IDS, FREE_KEY_ENDPOINTS, FREE_KEY_OPERATIONS, strict=True
    ):
        _require(route["route_id"] == route_id, "FREE_KEY_ROUTE_ID_DRIFT")
        _require(route["access_class"] == "LOCAL_ENV_CREDENTIAL", "FREE_KEY_ACCESS_DRIFT")
        _require(route["endpoint_family"] == endpoint, "FREE_KEY_ENDPOINT_DRIFT")
        _require(route["operation"] == operation, "FREE_KEY_OPERATION_DRIFT")
        _require(route["execution_policy"]["retry"] is False, "FREE_KEY_RETRY_DRIFT")
        _require(route["execution_policy"]["fallback"] is False, "FREE_KEY_FALLBACK_DRIFT")
        _require(route["execution_policy"]["authority_granted"] is False, "FREE_KEY_AUTHORITY_DRIFT")
    return tuple(routes)
```

The closure receipt must identify the former task/version and immutable evidence hashes, record the owner-approved `REPLAN`, name no key or raw response, and explicitly state that it is not alpha, MOVE 2, or a rewrite of A1.

- [ ] **Step 4: Mark the new contract in progress only as implementation begins**

```yaml
task_id: QUOTE_NATIVE_EVIDENCE_CHANNEL_QUALIFICATION_V1
task_version: '1.0'
status: IN_PROGRESS
```

Change only the status field after the v9 binding files exist and before any
credential read or provider request. Keep the exact owner phrase, base SHA, caps,
and stop conditions unchanged.

- [ ] **Step 5: Run the registry and task-contract checks to verify GREEN**

Run:

```powershell
uv run --locked --managed-python python -B -m unittest tests.test_provider_route_capability_registry_v9 -v
uv run --locked --managed-python python -B scripts/delivery_harness.py check
```

Expected: both commands pass; v8 semantics remain unchanged and the new v9 route records have no authority grant.

### Task 2: Build credential-safe, telemetry-bounded campaign transport with tests first

**Files:**
- Create: `configs/quote_native_evidence_channel_qualification_v1.yaml`
- Create: `src/solana_alpha_lab/quote_native_evidence_channel_qualification.py`
- Create: `tests/test_quote_native_evidence_channel_qualification.py`

**Interfaces:**
- Consumes: the three v9 route IDs; `credential_free_preflight`; `select_cohort`, `build_schedule`, and `score_campaign`.
- Produces:
  - `load_process_credential(environ: Mapping[str, str]) -> str`
  - `perform_credentialed_get(url: str, *, api_key: str, limits: Mapping[str, Any], opener: object | None = None) -> dict[str, object]`
  - `run_campaign(policy: Mapping[str, Any], *, credential_loader: Callable[[], str], preflight_fn: Callable[..., Mapping[str, Any]], opener: object | None, clock: Callable[[], datetime], sleeper: Callable[[float], None]) -> dict[str, object]`
  - `run_capture(*, authority_phrase: str) -> dict[str, object]`

- [ ] **Step 1: Write failing transport tests**

```python
def test_credential_is_read_once_after_preflight_and_only_sent_in_header() -> None:
    state = {"preflight": False, "reads": 0}
    receipt = run_wave(
        _policy(), wave="discovery", prior_receipt=None,
        preflight_fn=lambda *_args, **_kwargs: state.update(preflight=True) or {"credential_reads": 0},
        credential_loader=lambda: _read_key(state),
        opener=_ScriptedOpener([(RECENT, b"[]", 200), (TRADED, b"[]", 200)]),
    )
    assert state == {"preflight": True, "reads": 1}
    assert receipt["credential_reads"] == 1
    assert "test-key" not in json.dumps(receipt)
    assert _ScriptedOpener.last_request_url_has_no_api_key()
    assert _ScriptedOpener.last_request_header("x-api-key") == "test-key"

def test_only_allowlisted_response_headers_enter_the_receipt() -> None:
    response = _Response(
        b"{}",
        429,
        {"x-api-gateway-request-id": "request-1", "retry-after": "3", "set-cookie": "never-record"},
    )
    result = perform_credentialed_get(ORDER, api_key="test-key", limits=_limits(), opener=_OneResponse(response))
    assert result["safe_response_headers"] == {
        "retry-after": "3",
        "x-api-gateway-request-id": "request-1",
    }

def test_429_stops_the_campaign_without_retry_or_later_cells() -> None:
    receipt = _run_t0_with_statuses([200, 200, 429, 200])
    assert receipt["terminal_outcome"] == "PAUSE_CLOSE_QUOTE_NATIVE_CURRENT_ALPHA_ROUTE"
    assert receipt["retries"] == 0
    assert receipt["fallbacks"] == 0
    assert receipt["provider_requests"] == 3
    assert all(row["terminal"] == "NOT_REACHED" for row in _unreached_t0_rows(receipt))
```

- [ ] **Step 2: Run the focused test module to verify it is RED**

Run:

```powershell
uv run --locked --managed-python python -B -m unittest tests.test_quote_native_evidence_channel_qualification -v
```

Expected: import failure for the new module or assertion failures for absent credential/telemetry behavior.

- [ ] **Step 3: Implement the minimal credential-safe transport**

```python
SAFE_RESPONSE_HEADERS = frozenset({"x-api-gateway-request-id", "retry-after"})

def load_process_credential(environ: Mapping[str, str]) -> str:
    value = environ.get("JUPITER_API_KEY", "").strip()
    _require(bool(value), "JUPITER_API_KEY_MISSING_OR_EMPTY")
    return value

def _safe_response_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {
        key.casefold(): value
        for key, value in headers.items()
        if key.casefold() in SAFE_RESPONSE_HEADERS
    }

def perform_credentialed_get(url: str, *, api_key: str, limits: Mapping[str, Any], opener: object | None = None) -> dict[str, object]:
    _require("api-key" not in url.casefold(), "API_KEY_IN_URL")
    request = urllib.request.Request(
        url, method="GET",
        headers={"Accept": "application/json", "User-Agent": USER_AGENT, "x-api-key": api_key},
    )
    selected = opener or urllib.request.build_opener(_NoRedirectHandler())
    try:
        with selected.open(request, timeout=float(limits["timeout_seconds"])) as response:
            status, headers = int(response.getcode()), response.headers
            body = response.read(int(limits["max_response_bytes"]) + 1)
    except urllib.error.HTTPError as exc:
        status, headers = int(exc.code), exc.headers or {}
        body = exc.read(int(limits["max_response_bytes"]) + 1)
    _require(len(body) <= int(limits["max_response_bytes"]), "RESPONSE_BYTES_EXCEEDED")
    return {
        "http_status": status,
        "content_type": str(headers.get("Content-Type", "")),
        "response_bytes": len(body),
        "response_sha256": hashlib.sha256(body).hexdigest(),
        "safe_response_headers": _safe_response_headers(headers),
        "body": body,
    }
```

Use the existing credential-free DNS/TCP/TLS preflight before `load_process_credential`. Create a local attempt-start marker before that read. Do not import or call the old `.env` loader. Add a monotonic global pacer that applies before every one of the three allowed endpoints and preserves a `>=3.0` second interval in the receipt.

- [ ] **Step 4: Run focused transport tests to verify GREEN**

Run:

```powershell
uv run --locked --managed-python python -B -m unittest tests.test_quote_native_evidence_channel_qualification -v
```

Expected: all tests pass, including secret exclusion, pacing, no retry/fallback, 401/403 owner-action classification, and 429 terminal stop.

### Task 3: Compose the fresh 6+6 campaign without changing measurement semantics

**Files:**
- Modify: `configs/quote_native_evidence_channel_qualification_v1.yaml`
- Modify: `src/solana_alpha_lab/quote_native_evidence_channel_qualification.py`
- Modify: `tests/test_quote_native_evidence_channel_qualification.py`
- Create: `scripts/run_quote_native_evidence_channel_qualification.py`

**Interfaces:**
- Consumes: `perform_credentialed_get`, the v9 binding config, and existing pure selection/schedule/scoring helpers.
- Produces a create-only local raw directory plus a typed Git receipt containing `QUOTE_NATIVE_EVIDENCE_FIT_PASS`, `PAUSE_CLOSE_QUOTE_NATIVE_CURRENT_ALPHA_ROUTE`, or an owner-action terminal.

- [ ] **Step 1: Write failing campaign-semantic tests**

```python
def test_policy_keeps_prior_cohort_and_success_control_thresholds() -> None:
    policy = _policy()
    assert (policy["recent_cell_count"], policy["traded_cell_count"]) == (6, 6)
    assert policy["success"] == {"min_complete_xy": 10, "min_time_separated": 6}
    assert policy["control_kill"] == {"min_complete_cells": 6, "min_time_separated_share": "0.5"}
    assert policy["execution_controls"]["provider_requests_max"] == 60
    assert policy["execution_controls"]["retries"] == 0
    assert policy["execution_controls"]["fallback"] is False

def test_success_requires_both_strata_and_six_time_separated_cells() -> None:
    verdict = classify_terminal(score_campaign(_ten_complete_rows(both_strata=True, separated=6)))
    assert verdict == "QUOTE_NATIVE_EVIDENCE_FIT_PASS"
    assert classify_terminal(score_campaign(_ten_complete_rows(both_strata=False, separated=10))) == (
        "PAUSE_CLOSE_QUOTE_NATIVE_CURRENT_ALPHA_ROUTE"
    )
```

- [ ] **Step 2: Run semantic tests to verify they are RED**

Run:

```powershell
uv run --locked --managed-python python -B -m unittest tests.test_quote_native_evidence_channel_qualification.QualificationPolicyTests -v
```

Expected: missing configuration/runner behavior causes failure.

- [ ] **Step 3: Implement the three-wave foreground runner**

```python
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authority-phrase", required=True)
    args = parser.parse_args()
    receipt = run_capture(authority_phrase=args.authority_phrase)
    print(json.dumps({
        "terminal_outcome": receipt["terminal_outcome"],
        "provider_requests": receipt["provider_requests"],
        "campaign_verdict": receipt["campaign"]["campaign_verdict"],
    }, sort_keys=True))
    return 0
```

One foreground process performs discovery, freezes exactly six eligible RECENT and six eligible TRADED cells, executes t0 SOL→mint then exact-outAmount reverse quotes, waits to the frozen H900/H3600 offsets, and consumes only due cells inside their slack. H14400 is an explicit gap. The process reads the credential once after preflight, retains it only in process memory, and immediately stops after the first terminal failure; it is not a scheduler, daemon, or resumable wave process.

- [ ] **Step 4: Run direct consumer tests to verify GREEN**

Run:

```powershell
uv run --locked --managed-python python -B -m unittest tests.test_quote_native_evidence_channel_qualification tests.test_quote_native_live_variation_campaign -v
```

Expected: the new campaign behavior is green and the original keyless campaign tests remain green.

### Task 4: Execute one authorized campaign, record the decision, and deliver

**Files:**
- Create: `docs/evidence/quote_native_evidence_channel_qualification/a1_quote_native_evidence_channel_qualification_runtime_receipt_v1.json`
- Create: `docs/evidence/quote_native_evidence_channel_qualification/a1_quote_native_evidence_channel_qualification_acceptance_v1.json`
- Create: `docs/reports/quote_native_evidence_channel_qualification/a1_owner_readout_v1.md`
- Create: `docs/evidence/quote_native_evidence_channel_qualification/a1_delivery_completion_evidence_v1.json`
- Create: `docs/evidence/quote_native_evidence_channel_qualification/a1_delivery_independent_review_v1.json`
- Create: `docs/evidence/quote_native_evidence_channel_qualification/a1_delivery_factory_fit_v1.json`
- Modify: `catalog/assets/core.yaml`
- Modify: `catalog/assets/lifecycle.yaml`
- Modify: `catalog/catalog_manifest.yaml`
- Modify: `catalog/generated/asset_edges.json`
- Modify: `docs/PROJECT_MAP.md`
- Modify: `registries/decisions_negative_results.yaml`

**Interfaces:**
- Consumes: the exact owner phrase in `QUOTE_NATIVE_EVIDENCE_CHANNEL_QUALIFICATION_V1`, the local process environment, and all green offline tests.
- Produces: one decision-bearing receipt, a Russian owner readout, and either a durable evidence-fit pass or a durable current-route pause/close.

- [ ] **Step 1: Run pre-live validation**

Run:

```powershell
uv run --locked --managed-python python -B -m unittest tests.test_provider_route_capability_registry_v9 tests.test_quote_native_evidence_channel_qualification tests.test_quote_native_live_variation_campaign -v
uv run --locked --managed-python python -B scripts/secret_scan.py --self-test --scan-repository
uv run --locked --managed-python python -B scripts/validate_catalog.py
uv run --locked --managed-python python -B scripts/generate_navigation.py --check
```

Expected: every command passes without any provider call.

- [ ] **Step 2: Run the single foreground campaign**

Run the approved runner’s `discovery`, `t0`, and due `H900`/`H3600` waves in one foreground chain. Stop immediately on a typed terminal outcome. Do not alter `JUPITER_API_KEY`, inspect it, echo it, or retry a failed request.

```powershell
uv run --locked --managed-python python -B scripts/run_quote_native_evidence_channel_qualification.py --authority-phrase 'OK QUOTE_NATIVE_EVIDENCE_CHANNEL_QUALIFICATION_V1: one fresh Jupiter Free-key quote-native evidence campaign using a local process-environment key only; Tokens V2 /recent and /toptraded/1h plus quote-only /swap/v2/order; x-api-key header only; no .env read, no key in URL/log/receipt/Git, no taker, /build, /execute, wallet, signer, transaction, paid plan, second provider, retry or fallback; cash cap $0; call cap 60; global provider pace >=3s; preserve the existing 6 RECENT + 6 TRADED cohort and success/control-kill thresholds; any 429 or insufficient Free-key sample closes or pauses the current quote-native alpha route.'
```

- [ ] **Step 3: Build acceptance and owner evidence from observed bytes only**

```python
acceptance = {
    "terminal": runtime["terminal_outcome"],
    "provider_requests": runtime["provider_requests"],
    "credential_reads": runtime["credential_reads"],
    "retries": runtime["retries"],
    "fallbacks": runtime["fallbacks"],
    "cash_spend_usd_cents": 0,
    "route_ids": FREE_KEY_ROUTE_IDS,
    "non_claims": ["NO_ALPHA", "NO_NETRETURN", "NO_EXECUTE", "NO_PAID_PLAN"],
}
```

For a terminal pause/close, append one bounded decision record to
`registries/decisions_negative_results.yaml`; for a pass, record that only a
separate fresh mechanism task may follow. Never label either result as alpha,
execution, NetReturn, or canonical project DONE.

- [ ] **Step 4: Run review and delivery checks**

Run independent code, goal/DoD, and architecture review for the exact diff and
contract. Then run focused validation, Catalog validation, generated-navigation
check, write-set check, and secret scan. Use the project’s exact PR CI as the
full-gate owner; do not run the local full gate before PR. Stop at the
repository’s exact merge authorization rather than claiming merge or task DONE.
