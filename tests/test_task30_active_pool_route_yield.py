from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.lifecycle_discovery_transport import (  # noqa: E402
    HttpCapture,
    WssCapture,
)
from solana_alpha_lab.task30_active_pool_route_yield import (  # noqa: E402
    OWNER_RUNTIME_PHRASE,
    ActivePoolRouteYieldError,
    bind_pool_activity_request,
    bind_pool_logs_subscribe,
    classify_route_window,
    evaluate_active_pool_route_yield_policy,
    select_active_pool,
)
from solana_alpha_lab.task30_active_pool_route_yield_runtime import (  # noqa: E402
    ActivePoolRouteYieldRuntimeError,
    execute_active_pool_route_yield,
)
from solana_alpha_lab.provider_route_capability_registry_v2 import (  # noqa: E402
    ProviderRouteRegistryError,
    resolve_provider_route_v2,
    validate_provider_route_capability_registry_v2,
)


CONFIG_PATH = ROOT / "configs/task30_active_pool_route_yield_v1.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/task30_active_pool_route_yield.schema.json"
FIXTURE_PATH = ROOT / "tests/fixtures/task30/active_pool_route_yield_v1.json"
CONTRACT_PATH = ROOT / "docs/contracts/task30_active_pool_route_yield_contract_v1.md"
MODULE_PATH = ROOT / "src/solana_alpha_lab/task30_active_pool_route_yield.py"
RUNTIME_PATH = ROOT / "src/solana_alpha_lab/task30_active_pool_route_yield_runtime.py"
SCRIPT_PATH = ROOT / "scripts/run_task30_active_pool_route_yield.py"
TEST_PATH = ROOT / "tests/test_task30_active_pool_route_yield.py"
ACCEPTANCE_PATH = ROOT / "docs/evidence/task30/a17_active_pool_route_yield_acceptance_v1.json"
CATALOG_PATH = ROOT / "catalog/assets/core.yaml"
MANIFEST_PATH = ROOT / "catalog/catalog_manifest.yaml"
REGISTRY_PATH = ROOT / "configs/provider_route_capability_registry_v2.yaml"

POPCAT = "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr"
WSOL = "So11111111111111111111111111111111111111112"
POOL_A = "AHTTzwf3GmVMJdxWM8v2MSxyjZj8rQR6hyAC3g9477Yj"
POOL_B = "6" * 44
ACK_AT = datetime(2026, 8, 13, 9, 0, 1, tzinfo=UTC)
END_AT = ACK_AT + timedelta(seconds=180)


def config() -> dict[str, object]:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def pair(
    pool: str,
    *,
    buys: int = 2,
    sells: int = 1,
    liquidity: float = 1000.0,
    dex: str = "orca",
    base: str = POPCAT,
    quote: str = WSOL,
) -> dict[str, object]:
    return {
        "chainId": "solana",
        "dexId": dex,
        "pairAddress": pool,
        "baseToken": {"address": base, "name": "Popcat", "symbol": "POPCAT"},
        "quoteToken": {"address": quote, "name": "Wrapped SOL", "symbol": "SOL"},
        "txns": {"m5": {"buys": buys, "sells": sells}},
        "liquidity": {"usd": liquidity},
    }


def discovery_body(*rows: dict[str, object]) -> bytes:
    return json.dumps(list(rows), separators=(",", ":")).encode()


def ack(subscription_id: int = 7) -> bytes:
    return json.dumps(
        {"jsonrpc": "2.0", "id": "task30-a17-pool-logs-subscribe", "result": subscription_id},
        separators=(",", ":"),
    ).encode()


def notification(pool: str = POOL_A, subscription_id: int = 7) -> bytes:
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "method": "logsNotification",
            "params": {
                "subscription": subscription_id,
                "result": {
                    "context": {"slot": 100},
                    "value": {
                        "signature": "1" * 64,
                        "err": None,
                        "logs": [f"Program {pool} invoke [1]", f"Program {pool} success"],
                    },
                },
            },
        },
        separators=(",", ":"),
    ).encode()


def wss(
    *,
    notices: tuple[bytes, ...] = (),
    terminal: str = "BOUND_REACHED",
    error: str | None = None,
) -> WssCapture:
    return WssCapture(
        acknowledgement=ack(),
        notifications=notices,
        acknowledgement_observed_at=ACK_AT,
        notification_observed_at=tuple(ACK_AT + timedelta(seconds=i + 1) for i in range(len(notices))),
        terminal_class=terminal,
        error_class=error,
        stop_reason="FIRST_NOTIFICATION" if notices else "ELAPSED_CAP",
    )


def signature_response(*times: int) -> HttpCapture:
    records = [
        {
            "signature": str(index + 1) * 64,
            "slot": 1000 - index,
            "err": None,
            "memo": None,
            "blockTime": value,
            "confirmationStatus": "confirmed",
        }
        for index, value in enumerate(times)
    ]
    body = json.dumps(
        {"jsonrpc": "2.0", "id": "task30-a17-pool-activity", "result": records},
        separators=(",", ":"),
    ).encode()
    return HttpCapture(status_code=200, body=body, response_url="https://mainnet.helius-rpc.com/?api-key=<redacted>")


class Task30ActivePoolRouteYieldTests(unittest.TestCase):
    def test_closed_policy_schema_fixture_and_registry_binding(self) -> None:
        policy = config()
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(policy)), [])
        expected = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["expected_result"]
        registry = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
        self.assertEqual(evaluate_active_pool_route_yield_policy(policy, registry), expected)

        for pointer, value, code in (
            (("runtime_limits", "max_wss_seconds"), 180.0, "RUNTIME_LIMIT_DRIFT"),
            (("runtime_limits", "max_rpc_requests"), True, "RUNTIME_LIMIT_DRIFT"),
            (("authority", "provider_api_rpc_wss_calls"), 1, "ZERO_AUTHORITY_REQUIRED"),
            (("replan", "terminal_atom"), 1, "REPLAN_POLICY_DRIFT"),
        ):
            with self.subTest(pointer=pointer):
                candidate = copy.deepcopy(policy)
                candidate[pointer[0]][pointer[1]] = value  # type: ignore[index]
                with self.assertRaisesRegex(ActivePoolRouteYieldError, code):
                    evaluate_active_pool_route_yield_policy(candidate, registry)

    def test_registry_v2_is_append_only_and_resolves_all_three_routes(self) -> None:
        registry = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
        routes = validate_provider_route_capability_registry_v2(registry)
        self.assertEqual(
            [route["route_id"] for route in routes],
            [
                "DEXSCREENER-SOLANA-TOKEN-PAIRS-KEYLESS-001",
                "HELIUS-SOLANA-GET-SIGNATURES-001",
                "HELIUS-SOLANA-LOGS-SUBSCRIBE-001",
            ],
        )
        self.assertEqual(
            resolve_provider_route_v2(registry, "HELIUS-SOLANA-LOGS-SUBSCRIBE-001")["operation"],
            "LOGS_SUBSCRIBE_MENTIONS",
        )
        drifted = copy.deepcopy(registry)
        drifted["routes"][0]["runtime"]["observed_result"] = "DRIFTED"
        with self.assertRaisesRegex(ProviderRouteRegistryError, "LEGACY_ROUTE_SEMANTICS_DRIFT"):
            validate_provider_route_capability_registry_v2(drifted)

    def test_active_pool_selection_is_closed_and_deterministic(self) -> None:
        document = json.loads(
            discovery_body(
                pair(POOL_B, buys=3, sells=2, liquidity=100.0),
                pair(POOL_A, buys=3, sells=2, liquidity=200.0),
                pair("7" * 44, buys=100, dex="raydium"),
            )
        )
        selected = select_active_pool(document)
        self.assertEqual(selected["pool_address"], POOL_A)
        self.assertEqual(selected["m5_transactions"], 5)
        self.assertEqual(selected["liquidity_usd"], 200.0)
        self.assertIsNone(select_active_pool([pair(POOL_A, buys=0, sells=0)]))
        self.assertIsNone(select_active_pool([pair(POOL_A, quote="bad-mint")]))

    def test_request_binding_is_target_bound_and_secret_safe(self) -> None:
        logs = bind_pool_logs_subscribe(POOL_A, "offline-helius-secret")
        activity = bind_pool_activity_request(POOL_A, "offline-helius-secret")
        for request in (logs, activity):
            safe = request.safe_receipt()
            self.assertEqual(safe["provider"], "HELIUS")
            self.assertIn(POOL_A.encode(), request.body)
            self.assertNotIn("offline-helius-secret", repr(request))
            self.assertNotIn("offline-helius-secret", json.dumps(safe))
        self.assertIn(b"logsSubscribe", logs.body)
        self.assertIn(b"getSignaturesForAddress", activity.body)

    def test_terminal_classification_distinguishes_yield_activity_and_no_activity(self) -> None:
        selected = select_active_pool([pair(POOL_A)])
        assert selected is not None
        result = classify_route_window(config(), yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")), selected, wss_capture=wss(notices=(notification(),)), rpc_capture=None)
        self.assertEqual(result["terminal_state"], "ROUTE_YIELD_OBSERVED_TECHNICAL_ONLY")
        self.assertEqual(result["rpc_requests"], 0)

        result = classify_route_window(
            config(),
            yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")),
            selected,
            wss_capture=wss(),
            rpc_capture=signature_response(int(END_AT.timestamp()), int(ACK_AT.timestamp()) + 10, int(ACK_AT.timestamp())),
            terminal_observed_at=END_AT,
        )
        self.assertEqual(result["terminal_state"], "ACTIVE_BUT_NO_WSS_YIELD")
        self.assertEqual(result["interior_signature_count"], 1)

        result = classify_route_window(
            config(),
            yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")),
            selected,
            wss_capture=wss(),
            rpc_capture=signature_response(int(END_AT.timestamp()), int(ACK_AT.timestamp())),
            terminal_observed_at=END_AT,
        )
        self.assertEqual(result["terminal_state"], "NO_ACTIVITY_DURING_WINDOW")
        self.assertTrue(result["window_bracketed"])

    def test_unknown_is_fail_closed_for_transport_schema_target_or_coverage(self) -> None:
        selected = select_active_pool([pair(POOL_A)])
        assert selected is not None
        failed = WssCapture(
            acknowledgement=b"",
            notifications=(),
            terminal_class="DNS_OR_TLS",
            error_class="wss_connection_failed",
            stop_reason="CONNECTION_FAILURE",
        )
        for wss_capture, rpc_capture in (
            (failed, None),
            (wss(), None),
            (wss(), signature_response(int(ACK_AT.timestamp()) + 20)),
        ):
            with self.subTest(wss=wss_capture.terminal_class, rpc=rpc_capture is not None):
                result = classify_route_window(
                    config(), yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")), selected, wss_capture=wss_capture,
                    rpc_capture=rpc_capture,
                    terminal_observed_at=END_AT if rpc_capture is not None else None,
                )
                self.assertEqual(result["terminal_state"], "TRANSPORT_OR_COVERAGE_UNKNOWN")
                self.assertTrue(result["unknown"])
                self.assertFalse(result["zero_volume"])
                self.assertFalse(result["task30_trial"])

    def test_runtime_stops_before_helius_when_no_active_target(self) -> None:
        calls: list[str] = []
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            receipt = execute_active_pool_route_yield(
                config(),
                yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")),
                authority_phrase=OWNER_RUNTIME_PHRASE,
                repository_root=root,
                raw_root=root / "local/task30_active_pool_route_yield",
                discovery_exchange=lambda request, max_response_bytes: HttpCapture(
                    status_code=200,
                    body=discovery_body(pair(POOL_A, buys=0, sells=0)),
                    response_url="https://api.dexscreener.com/token-pairs/v1/solana/<mint>",
                ),
                route_preflight=lambda: calls.append("preflight") or {"dns_resolved": True, "tcp_443": True},
                credential_loader=lambda name: calls.append("credential") or "offline-secret",
                wss_exchange=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("WSS forbidden")),
                rpc_exchange=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("RPC forbidden")),
                clock=lambda: datetime(2026, 8, 13, 10, tzinfo=UTC),
                nonce_factory=lambda: "01234567",
            )
        self.assertEqual(receipt["terminal_state"], "NO_ACTIVE_TARGET_STOP")
        self.assertEqual(receipt["helius_calls"], 0)
        self.assertEqual(calls, [])

    def test_discovery_transport_failure_is_unknown_not_no_active_target(self) -> None:
        calls: list[str] = []
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            receipt = execute_active_pool_route_yield(
                config(),
                yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")),
                authority_phrase=OWNER_RUNTIME_PHRASE,
                repository_root=root,
                raw_root=root / "local/task30_active_pool_route_yield",
                discovery_exchange=lambda request, max_response_bytes: HttpCapture(
                    status_code=None,
                    body=b"",
                    response_url="https://api.dexscreener.com/token-pairs/v1/solana/<mint>",
                    terminal_class="DNS_OR_TLS",
                    error_class="discovery_connection_failed",
                ),
                route_preflight=lambda: calls.append("preflight") or {"dns_resolved": True, "tcp_443": True},
                credential_loader=lambda name: calls.append("credential") or "offline-secret",
                wss_exchange=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("WSS forbidden")),
                rpc_exchange=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("RPC forbidden")),
                clock=lambda: datetime(2026, 8, 13, 10, tzinfo=UTC),
                nonce_factory=lambda: "76543210",
            )
        self.assertEqual(receipt["terminal_state"], "TRANSPORT_OR_COVERAGE_UNKNOWN")
        self.assertTrue(receipt["unknown"])
        self.assertEqual(receipt["helius_calls"], 0)
        self.assertEqual(calls, [])

    def test_malformed_discovery_is_unknown_but_empty_valid_list_is_no_target(self) -> None:
        for label, body, expected in (
            ("malformed-row", b"[{}]", "TRANSPORT_OR_COVERAGE_UNKNOWN"),
            ("duplicate-key", b'[{"chainId":"solana","chainId":"solana"}]', "TRANSPORT_OR_COVERAGE_UNKNOWN"),
            ("empty-list", b"[]", "NO_ACTIVE_TARGET_STOP"),
        ):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                receipt = execute_active_pool_route_yield(
                    config(),
                    yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")),
                    authority_phrase=OWNER_RUNTIME_PHRASE,
                    repository_root=root,
                    raw_root=root / "local/task30_active_pool_route_yield",
                    discovery_exchange=lambda request, max_response_bytes, body=body: HttpCapture(
                        status_code=200,
                        body=body,
                        response_url="https://api.dexscreener.com/token-pairs/v1/solana/<mint>",
                    ),
                    route_preflight=lambda: (_ for _ in ()).throw(AssertionError("preflight forbidden")),
                    credential_loader=lambda name: (_ for _ in ()).throw(AssertionError("credential forbidden")),
                    wss_exchange=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("WSS forbidden")),
                    rpc_exchange=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("RPC forbidden")),
                    clock=lambda: datetime(2026, 8, 13, 10, tzinfo=UTC),
                    nonce_factory=lambda: {"malformed-row": "44444444", "duplicate-key": "55555555", "empty-list": "66666666"}[label],
                )
                self.assertEqual(receipt["terminal_state"], expected)
                self.assertEqual(receipt["helius_calls"], 0)
                self.assertTrue((root / receipt["logical_run_root"] / "terminal_receipt.json").is_file())

    def test_runtime_sequences_wss_and_conditional_rpc_without_retry(self) -> None:
        events: list[str] = []

        def discovery(request: object, *, max_response_bytes: int) -> HttpCapture:
            events.append("discovery")
            return HttpCapture(
                status_code=200,
                body=discovery_body(pair(POOL_A)),
                response_url="https://api.dexscreener.com/token-pairs/v1/solana/<mint>",
            )

        def stream(request: object, **kwargs: object) -> WssCapture:
            events.append("wss")
            self.assertEqual(kwargs["max_open_seconds"], 180)
            self.assertEqual(kwargs["max_notifications"], 1)
            return wss()

        def rpc(request: object, *, max_response_bytes: int) -> HttpCapture:
            events.append("rpc")
            return signature_response(int(END_AT.timestamp()), int(ACK_AT.timestamp()) + 30, int(ACK_AT.timestamp()))

        times = iter(
            (
                ACK_AT - timedelta(seconds=2),
                ACK_AT - timedelta(seconds=1),
                END_AT,
                END_AT + timedelta(seconds=1),
                END_AT + timedelta(seconds=2),
            )
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            raw_root = root / "local/task30_active_pool_route_yield"
            receipt = execute_active_pool_route_yield(
                config(),
                yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")),
                authority_phrase=OWNER_RUNTIME_PHRASE,
                repository_root=root,
                raw_root=raw_root,
                discovery_exchange=discovery,
                route_preflight=lambda: {"dns_resolved": True, "tcp_443": True},
                credential_loader=lambda name: events.append("credential") or "offline-helius-secret",
                wss_exchange=stream,
                rpc_exchange=rpc,
                clock=lambda: next(times),
                nonce_factory=lambda: "89abcdef",
            )
            run_root = root / receipt["logical_run_root"]
            self.assertTrue((run_root / "raw_manifest.json").is_file())
            self.assertTrue((run_root / "terminal_receipt.json").is_file())
            retained = b"".join(path.read_bytes() for path in run_root.iterdir())
            self.assertNotIn(b"offline-helius-secret", retained)
        self.assertEqual(events, ["discovery", "credential", "wss", "rpc"])
        self.assertEqual(receipt["terminal_state"], "ACTIVE_BUT_NO_WSS_YIELD")
        self.assertEqual(receipt["provider_calls"], 3)
        self.assertFalse(receipt["price"])
        self.assertFalse(receipt["volume"])
        self.assertTrue(receipt["replan"]["terminal_atom"])

    def test_runtime_does_not_rpc_after_first_notification(self) -> None:
        rpc_calls = 0

        def rpc(*args: object, **kwargs: object) -> HttpCapture:
            nonlocal rpc_calls
            rpc_calls += 1
            raise AssertionError("RPC forbidden after WSS yield")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            receipt = execute_active_pool_route_yield(
                config(),
                yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")),
                authority_phrase=OWNER_RUNTIME_PHRASE,
                repository_root=root,
                raw_root=root / "local/task30_active_pool_route_yield",
                discovery_exchange=lambda request, max_response_bytes: HttpCapture(
                    status_code=200,
                    body=discovery_body(pair(POOL_A)),
                    response_url="https://api.dexscreener.com/token-pairs/v1/solana/<mint>",
                ),
                route_preflight=lambda: {"dns_resolved": True, "tcp_443": True},
                credential_loader=lambda name: "offline-helius-secret",
                wss_exchange=lambda request, **kwargs: wss(notices=(notification(),)),
                rpc_exchange=rpc,
                clock=lambda: datetime(2026, 8, 13, 10, tzinfo=UTC),
                nonce_factory=lambda: "fedcba98",
            )
        self.assertEqual(receipt["terminal_state"], "ROUTE_YIELD_OBSERVED_TECHNICAL_ONLY")
        self.assertEqual(receipt["rpc_requests"], 0)
        self.assertEqual(rpc_calls, 0)

    def test_runtime_does_not_rpc_after_invalid_acknowledgement(self) -> None:
        rpc_calls = 0

        def rpc(*args: object, **kwargs: object) -> HttpCapture:
            nonlocal rpc_calls
            rpc_calls += 1
            raise AssertionError("RPC forbidden after invalid acknowledgement")

        invalid = WssCapture(
            acknowledgement=json.dumps({"jsonrpc": "2.0", "id": "wrong", "result": 7}).encode(),
            notifications=(),
            acknowledgement_observed_at=ACK_AT,
            notification_observed_at=(),
            terminal_class="BOUND_REACHED",
            error_class=None,
            stop_reason="ELAPSED_CAP",
        )
        times = iter((ACK_AT - timedelta(seconds=2), ACK_AT - timedelta(seconds=1), END_AT, END_AT + timedelta(seconds=1)))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            receipt = execute_active_pool_route_yield(
                config(), yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")),
                authority_phrase=OWNER_RUNTIME_PHRASE,
                repository_root=root,
                raw_root=root / "local/task30_active_pool_route_yield",
                discovery_exchange=lambda request, max_response_bytes: HttpCapture(status_code=200, body=discovery_body(pair(POOL_A)), response_url="https://api.dexscreener.com/token-pairs/v1/solana/<mint>"),
                route_preflight=lambda: {"dns_resolved": True, "tcp_443": True},
                credential_loader=lambda name: "offline-helius-secret",
                wss_exchange=lambda request, **kwargs: invalid,
                rpc_exchange=rpc,
                clock=lambda: next(times),
                nonce_factory=lambda: "a1b2c3d4",
            )
        self.assertEqual(receipt["terminal_state"], "TRANSPORT_OR_COVERAGE_UNKNOWN")
        self.assertEqual(receipt["rpc_requests"], 0)
        self.assertEqual(rpc_calls, 0)

    def test_runtime_rejects_wrong_authority_without_calls_or_writes(self) -> None:
        calls = 0

        def discovery(*args: object, **kwargs: object) -> HttpCapture:
            nonlocal calls
            calls += 1
            raise AssertionError

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            raw_root = root / "local/task30_active_pool_route_yield"
            with self.assertRaisesRegex(ActivePoolRouteYieldRuntimeError, "OWNER_AUTHORITY_MISMATCH"):
                execute_active_pool_route_yield(
                    config(),
                    yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")),
                    authority_phrase="WRONG",
                    repository_root=root,
                    raw_root=raw_root,
                    discovery_exchange=discovery,
                    route_preflight=lambda: {"dns_resolved": True, "tcp_443": True},
                    credential_loader=lambda name: "offline-helius-secret",
                    wss_exchange=lambda *args, **kwargs: wss(),
                    rpc_exchange=lambda *args, **kwargs: signature_response(),
                    clock=lambda: datetime.now(UTC),
                    nonce_factory=lambda: "01234567",
                )
            self.assertFalse(raw_root.exists())
        self.assertEqual(calls, 0)

    def test_missing_credential_retains_terminal_unknown_without_helius_call(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            receipt = execute_active_pool_route_yield(
                config(), yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")),
                authority_phrase=OWNER_RUNTIME_PHRASE,
                repository_root=root,
                raw_root=root / "local/task30_active_pool_route_yield",
                discovery_exchange=lambda request, max_response_bytes: HttpCapture(status_code=200, body=discovery_body(pair(POOL_A)), response_url="https://api.dexscreener.com/token-pairs/v1/solana/<mint>"),
                route_preflight=lambda: {"dns_resolved": True, "tcp_443": True},
                credential_loader=lambda name: (_ for _ in ()).throw(KeyError(name)),
                wss_exchange=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("WSS forbidden")),
                rpc_exchange=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("RPC forbidden")),
                clock=lambda: datetime(2026, 8, 13, 10, tzinfo=UTC),
                nonce_factory=lambda: "0a1b2c3d",
            )
            run_root = root / receipt["logical_run_root"]
            self.assertTrue((run_root / "terminal_receipt.json").is_file())
        self.assertEqual(receipt["terminal_state"], "TRANSPORT_OR_COVERAGE_UNKNOWN")
        self.assertEqual(receipt["error_stage"], "CREDENTIAL_UNAVAILABLE_OR_INVALID")
        self.assertEqual(receipt["helius_calls"], 0)

    def test_thrown_adapters_retain_safe_terminal_receipts(self) -> None:
        cases = ("discovery", "wss", "rpc")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                clock_values = iter(
                    [
                        ACK_AT - timedelta(seconds=2),
                        ACK_AT - timedelta(seconds=1),
                        END_AT,
                        END_AT + timedelta(seconds=1),
                        END_AT + timedelta(seconds=2),
                    ]
                )

                def boom(*args: object, **kwargs: object) -> object:
                    raise RuntimeError("secret-bearing adapter detail must not persist")

                receipt = execute_active_pool_route_yield(
                    config(),
                    yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")),
                    authority_phrase=OWNER_RUNTIME_PHRASE,
                    repository_root=root,
                    raw_root=root / "local/task30_active_pool_route_yield",
                    discovery_exchange=boom if case == "discovery" else lambda request, max_response_bytes: HttpCapture(status_code=200, body=discovery_body(pair(POOL_A)), response_url="https://api.dexscreener.com/token-pairs/v1/solana/<mint>"),
                    route_preflight=lambda: {"dns_resolved": True, "tcp_443": True},
                    credential_loader=lambda name: "offline-helius-secret",
                    wss_exchange=boom if case == "wss" else lambda *args, **kwargs: wss(),
                    rpc_exchange=boom if case == "rpc" else lambda *args, **kwargs: signature_response(int(END_AT.timestamp()), int(ACK_AT.timestamp())),
                    clock=lambda: next(clock_values),
                    nonce_factory=lambda: {"discovery": "11111111", "wss": "22222222", "rpc": "33333333"}[case],
                )
                run_root = root / receipt["logical_run_root"]
                terminal = (run_root / "terminal_receipt.json").read_text(encoding="utf-8")
                self.assertEqual(receipt["terminal_state"], "TRANSPORT_OR_COVERAGE_UNKNOWN")
                self.assertTrue((run_root / "terminal_receipt.json").is_file())
                self.assertNotIn("secret-bearing", terminal)
                self.assertFalse(receipt["price"])
                self.assertFalse(receipt["volume"])
                self.assertTrue(receipt["replan"]["required"])

    def test_acceptance_hashes_assets_and_catalog_is_discoverable(self) -> None:
        acceptance = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(acceptance["state_change"], "NONE")
        self.assertEqual(acceptance["factory_fit_review"]["scope"], "FULL_REVIEW")
        self.assertEqual(acceptance["project_sources_disposition"]["kind"], "NO_CHANGE")
        self.assertTrue(acceptance["replan"]["terminal_atom"])
        for binding in acceptance["artifact_bindings"].values():
            path = ROOT / binding["path"]
            self.assertTrue(path.is_file(), binding["path"])
            self.assertEqual(binding["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())

        catalog = yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8"))
        ids = {record["asset_id"] for record in catalog["records"]}
        self.assertTrue(
            {
                "CONTRACT-T30-ACTIVE-POOL-ROUTE-YIELD-001",
                "CONFIG-T30-ACTIVE-POOL-ROUTE-YIELD-001",
                "SCHEMA-T30-ACTIVE-POOL-ROUTE-YIELD-001",
                "FIXTURE-T30-ACTIVE-POOL-ROUTE-YIELD-001",
                "MODULE-T30-ACTIVE-POOL-ROUTE-YIELD-001",
                "MODULE-T30-ACTIVE-POOL-ROUTE-YIELD-RUNTIME-001",
                "SCRIPT-T30-ACTIVE-POOL-ROUTE-YIELD-001",
                "TEST-T30-ACTIVE-POOL-ROUTE-YIELD-001",
                "EVIDENCE-T30-A17-ACTIVE-POOL-ROUTE-YIELD-001",
                "CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-002",
                "SCHEMA-PROVIDER-ROUTE-CAPABILITY-REGISTRY-002",
                "MODULE-PROVIDER-ROUTE-CAPABILITY-REGISTRY-002",
            }.issubset(ids)
        )
        manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
        self.assertIn(
            "catalog/schemas/task30_active_pool_route_yield.schema.json",
            manifest["root_resolver"]["schemas"],
        )
        self.assertIn(
            "catalog/schemas/provider_route_capability_registry_v2.schema.json",
            manifest["root_resolver"]["schemas"],
        )


if __name__ == "__main__":
    unittest.main()
