from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.contracts.schema_v1 import (  # noqa: E402
    PartitionManifest,
    RawResponseStatus,
)
from solana_alpha_lab.provider_smoke import (  # noqa: E402
    ProhibitedPayloadError,
    StopConditionError,
    build_attempt_raw_event,
    load_frozen_smoke_plan,
    materialize_case,
)
from solana_alpha_lab.provider_smoke_transport import (  # noqa: E402
    EXTERNAL_AUTHORITY_PHRASE,
    RAPTOR_TAIL_AUTHORITY_PHRASE,
    AttemptReceipt,
    BoundRequest,
    BoundedProviderTransport,
    DurableAttemptSink,
    DynamicBindingError,
    ExternalAuthorityRequiredError,
    ExternalExecutionGate,
    ProviderCredentials,
    RaptorTailExecutionGate,
    RaptorTailRunner,
    RecoveryEvidenceError,
    SmokeTransportRunner,
    TransportContractError,
    TransportExecutionError,
    TransportResponse,
    _NoRedirectHandler,
    _attempt_evidence,
    _read_bounded,
    bind_request,
    classify_response,
    default_run_id,
    extract_dynamic_binding,
    prepare_raptor_tail_recovery,
    safe_preflight_summary,
)
from solana_alpha_lab.storage import verify_raw_event_partition  # noqa: E402

SPEC_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "pre_git"
    / "task01"
    / "provider_smoke_spec_v1.yaml"
)


def _credentials() -> ProviderCredentials:
    h = "unit-" + ("h" * 16)
    t = "unit-" + ("t" * 16)
    return ProviderCredentials(
        helius_api_key=h,
        solana_tracker_api_key=t,
    )


def _response(
    body: bytes,
    *,
    terminal: str = "SUCCESS",
    status_code: int | None = 200,
    error_class: str | None = None,
) -> TransportResponse:
    instant = datetime(2026, 7, 24, 6, 0, tzinfo=timezone.utc)
    return TransportResponse(
        status_code=status_code,
        body=body,
        safe_headers=(("content-type", "application/json"),),
        terminal_class=terminal,
        error_class=error_class,
        request_started_at=instant,
        request_sent_at=instant,
        response_headers_at=instant if status_code is not None else None,
        response_complete_at=instant,
    )


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.value += seconds


class Task07ProviderSmokeTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = load_frozen_smoke_plan(SPEC_PATH)
        cls.credentials = _credentials()

    def _write_synthetic_r4_parent(
        self,
        raw_root: Path,
        *,
        run_id: str = "t07a4b-20260724T132144Z",
    ) -> str:
        sink = DurableAttemptSink(raw_root=raw_root, run_id=run_id)
        bindings: dict[str, object] = {}
        mint = self.plan.public_bindings["USDC_MINT"]
        signature = "1" * 64
        base = datetime(2026, 7, 24, 13, 21, tzinfo=timezone.utc)
        for index, attempt_id in enumerate(self.plan.attempt_ids[:-2]):
            case_id = attempt_id.rsplit("#", 1)[0]
            materialized = materialize_case(
                self.plan,
                case_id,
                produced_bindings=bindings,
            )
            request = bind_request(
                self.plan,
                attempt_id=attempt_id,
                materialized_request=materialized,
                credentials=self.credentials,
                wss_subscription_id=(
                    7 if attempt_id == "H12#2" else None
                ),
                produced_bindings=bindings,
            )
            if case_id == "H08":
                body = json.dumps(
                    {
                        "id": attempt_id,
                        "jsonrpc": "2.0",
                        "result": [{"signature": signature}],
                    }
                ).encode()
            elif case_id.startswith("H"):
                body = json.dumps(
                    {
                        "id": attempt_id,
                        "jsonrpc": "2.0",
                        "result": True,
                    }
                ).encode()
            elif case_id == "ST03":
                body = json.dumps({"data": [{"mint": mint}]}).encode()
            elif case_id == "ST06":
                body = (
                    b'{"pools":[{"decimals":6}],'
                    b'"token":{"decimals":6}}'
                )
            elif case_id.startswith("ST"):
                body = b'{"data":[{"ok":true}]}'
            elif case_id == "R01":
                body = b"OK"
            elif case_id.startswith("R"):
                body = b'{"amountOut":"1","routePlan":[]}'
            else:
                body = b'{"outAmount":"1","routePlan":[]}'
            instant = base + timedelta(seconds=index)
            response = replace(
                _response(
                    body,
                    status_code=(
                        101 if case_id == "H12" else 200
                    ),
                ),
                request_started_at=instant,
                request_sent_at=instant,
                response_headers_at=instant,
                response_complete_at=instant,
            )
            if attempt_id == "R01#1":
                response = replace(
                    response,
                    terminal_class="MALFORMED_PAYLOAD",
                    error_class="response_not_json",
                )
            elif attempt_id in {"R02#1", "R03#1"}:
                response = replace(
                    response,
                    terminal_class="SCHEMA_DRIFT",
                    error_class="quote_output_amount_invalid",
                )
            event, receipt, _ = _attempt_evidence(
                self.plan,
                request=request,
                materialized_request=materialized,
                response=response,
                credentials=self.credentials,
            )
            sink(event, receipt)
            case = self.plan.case_by_id[case_id]
            if case.output_binding is not None:
                binding = extract_dynamic_binding(
                    case_id,
                    event.redacted_body,
                )
                assert binding is not None
                bindings[binding[0]] = binding[1]
        return run_id

    def test_preflight_is_explicitly_zero_io_and_zero_secret(self) -> None:
        observed = safe_preflight_summary(self.plan)
        self.assertEqual(observed["case_count"], 34)
        self.assertEqual(observed["attempt_count"], 35)
        self.assertFalse(observed["network_authorized"])
        self.assertFalse(observed["credentials_read"])
        self.assertFalse(observed["output_created"])
        serialized = json.dumps(observed, sort_keys=True)
        for secret in self.credentials.explicit_secret_values:
            self.assertNotIn(secret, serialized)

    def test_credentials_and_requests_have_redacted_representations(self) -> None:
        materialized = materialize_case(self.plan, "H01")
        request = bind_request(
            self.plan,
            attempt_id="H01#1",
            materialized_request=materialized,
            credentials=self.credentials,
        )
        for secret in self.credentials.explicit_secret_values:
            self.assertNotIn(secret, repr(self.credentials))
            self.assertNotIn(secret, repr(request))
            self.assertNotIn(secret, json.dumps(request.safe_receipt()))
        self.assertIn("<redacted>", repr(request))

    def test_credential_validation_fails_closed(self) -> None:
        with self.assertRaisesRegex(
            TransportContractError,
            "helius_credential_invalid",
        ):
            ProviderCredentials(
                helius_api_key="short",
                solana_tracker_api_key="unit-" + ("t" * 16),
            )
        with self.assertRaisesRegex(
            TransportContractError,
            "solana_tracker_credential_invalid",
        ):
            ProviderCredentials(
                helius_api_key="unit-" + ("h" * 16),
                solana_tracker_api_key=" leading-space",
            )

    def test_helius_rpc_binding_is_exact_and_receipt_hides_auth(self) -> None:
        materialized = materialize_case(self.plan, "H02")
        request = bind_request(
            self.plan,
            attempt_id="H02#1",
            materialized_request=materialized,
            credentials=self.credentials,
        )
        self.assertEqual(request.transport, "HTTP")
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.safe_receipt()["host"], "mainnet.helius-rpc.com")
        self.assertEqual(request.safe_receipt()["query_keys"], [])
        payload = json.loads(request.body)
        self.assertEqual(payload["method"], "getVersion")
        self.assertEqual(payload["params"], [])
        self.assertIn("api-key=", request.url)

    def test_solana_tracker_auth_is_header_only_and_not_receipted(self) -> None:
        materialized = materialize_case(self.plan, "ST01")
        request = bind_request(
            self.plan,
            attempt_id="ST01#1",
            materialized_request=materialized,
            credentials=self.credentials,
        )
        headers = dict(request.headers)
        self.assertIn("x-api-key", headers)
        self.assertNotIn("x-api-key", request.url)
        self.assertEqual(
            request.safe_receipt()["query_keys"],
            ["limit", "query"],
        )
        self.assertNotIn(
            headers["x-api-key"],
            json.dumps(request.safe_receipt()),
        )

    def test_keyless_quote_bindings_have_exact_hosts_and_paths(self) -> None:
        for case_id, attempt_id, host, path in (
            ("J01", "J01#1", "api.jup.ag", "/swap/v2/order"),
            (
                "R01",
                "R01#1",
                "raptor-beta.solanatracker.io",
                "/health",
            ),
        ):
            with self.subTest(case_id=case_id):
                request = bind_request(
                    self.plan,
                    attempt_id=attempt_id,
                    materialized_request=materialize_case(
                        self.plan,
                        case_id,
                    ),
                    credentials=self.credentials,
                )
                receipt = request.safe_receipt()
                self.assertEqual(receipt["host"], host)
                self.assertEqual(receipt["path"], path)
                self.assertNotIn("authorization", dict(request.headers))
                self.assertNotIn("x-api-key", dict(request.headers))

    def test_materialized_identity_or_path_tampering_is_rejected(self) -> None:
        materialized = materialize_case(self.plan, "J01")
        changed = dict(materialized)
        changed["path"] = "/swap/v2/execute"
        with self.assertRaisesRegex(
            TransportContractError,
            "materialized_path_mismatch",
        ):
            bind_request(
                self.plan,
                attempt_id="J01#1",
                materialized_request=changed,
                credentials=self.credentials,
            )

        changed = dict(materialized)
        changed["provider"] = "RAPTOR_HOSTED"
        with self.assertRaisesRegex(
            TransportContractError,
            "materialized_provider_mismatch",
        ):
            bind_request(
                self.plan,
                attempt_id="J01#1",
                materialized_request=changed,
                credentials=self.credentials,
            )

    def test_wss_binding_requires_exact_two_step_state(self) -> None:
        materialized = materialize_case(self.plan, "H12")
        subscribe = bind_request(
            self.plan,
            attempt_id="H12#1",
            materialized_request=materialized,
            credentials=self.credentials,
        )
        self.assertEqual(subscribe.transport, "WSS")
        self.assertEqual(json.loads(subscribe.body)["method"], "accountSubscribe")
        with self.assertRaisesRegex(
            TransportContractError,
            "unsubscribe_subscription_id_invalid",
        ):
            bind_request(
                self.plan,
                attempt_id="H12#2",
                materialized_request=materialized,
                credentials=self.credentials,
            )
        unsubscribe = bind_request(
            self.plan,
            attempt_id="H12#2",
            materialized_request=materialized,
            credentials=self.credentials,
            wss_subscription_id=7,
        )
        payload = json.loads(unsubscribe.body)
        self.assertEqual(payload["method"], "accountUnsubscribe")
        self.assertEqual(payload["params"], [7])

    def test_external_transport_requires_exact_later_authority_phrase(self) -> None:
        with self.assertRaisesRegex(
            ExternalAuthorityRequiredError,
            "external_authority_phrase_mismatch",
        ):
            BoundedProviderTransport(
                gate=ExternalExecutionGate(authority_phrase="wrong")
            )

    def test_injected_http_exchange_runs_once_without_retry(self) -> None:
        calls: list[str] = []

        def exchange(
            request: BoundRequest,
            *,
            max_response_bytes: int,
        ) -> TransportResponse:
            calls.append(request.attempt_id)
            self.assertEqual(max_response_bytes, 2_000_000)
            return _response(b'{"ok":true}')

        transport = BoundedProviderTransport(
            gate=ExternalExecutionGate(
                authority_phrase=EXTERNAL_AUTHORITY_PHRASE
            ),
            http_exchange=exchange,
        )
        request = bind_request(
            self.plan,
            attempt_id="ST01#1",
            materialized_request=materialize_case(self.plan, "ST01"),
            credentials=self.credentials,
        )
        observed = transport.execute_http(
            request,
            max_response_bytes=2_000_000,
        )
        self.assertEqual(observed.terminal_class, "SUCCESS")
        self.assertEqual(calls, ["ST01#1"])

    def test_critical_terminal_stops_after_one_persisted_attempt(self) -> None:
        calls: list[str] = []
        persisted: list[tuple[object, AttemptReceipt]] = []

        def exchange(
            request: BoundRequest,
            *,
            max_response_bytes: int,
        ) -> TransportResponse:
            calls.append(request.attempt_id)
            return _response(
                b'{"error":"unauthorized"}',
                terminal="AUTH",
                status_code=401,
                error_class="http_401",
            )

        transport = BoundedProviderTransport(
            gate=ExternalExecutionGate(
                authority_phrase=EXTERNAL_AUTHORITY_PHRASE
            ),
            http_exchange=exchange,
        )
        runner = SmokeTransportRunner(
            plan=self.plan,
            credentials=self.credentials,
            transport=transport,
            event_sink=lambda event, receipt: persisted.append(
                (event, receipt)
            ),
            monotonic=FakeClock().monotonic,
            sleeper=lambda _: None,
        )
        with self.assertRaisesRegex(
            StopConditionError,
            "terminal_stop:AUTH",
        ):
            runner.run(run_id="t07a4b-20260724T060000Z")
        self.assertEqual(calls, ["H01#1"])
        self.assertEqual(len(persisted), 1)
        self.assertEqual(persisted[0][1].terminal_class, "AUTH")
        self.assertEqual(len(runner.receipts), 1)

    def test_total_response_cap_is_checked_before_durable_write(self) -> None:
        persisted: list[tuple[object, AttemptReceipt]] = []
        bounded_plan = replace(self.plan, max_total_response_bytes=1)
        transport = BoundedProviderTransport(
            gate=ExternalExecutionGate(
                authority_phrase=EXTERNAL_AUTHORITY_PHRASE
            ),
            http_exchange=lambda request, max_response_bytes: _response(
                b'{"jsonrpc":"2.0","id":"H01#1","result":"ok"}'
            ),
        )
        runner = SmokeTransportRunner(
            plan=bounded_plan,
            credentials=self.credentials,
            transport=transport,
            event_sink=lambda event, receipt: persisted.append(
                (event, receipt)
            ),
            monotonic=FakeClock().monotonic,
            sleeper=lambda _: None,
        )
        with self.assertRaisesRegex(
            StopConditionError,
            "total_response_bytes_exceeded",
        ):
            runner.run(run_id="t07a4b-20260724T060000Z")
        self.assertEqual(persisted, [])
        self.assertEqual(runner.guard.response_bytes_total, 0)

    def test_redirect_and_oversized_response_fail_closed_offline(self) -> None:
        handler = _NoRedirectHandler()
        with self.assertRaisesRegex(
            TransportExecutionError,
            "redirect_forbidden",
        ):
            handler.redirect_request(
                object(),
                object(),
                302,
                "redirect",
                {},
                "https://example.invalid",
            )
        with self.assertRaisesRegex(
            StopConditionError,
            "response_too_large",
        ):
            _read_bounded(io.BytesIO(b"12345"), 4)

    def test_response_representation_never_contains_body(self) -> None:
        response = _response(b'{"private":"opaque-provider-body"}')
        self.assertNotIn("opaque-provider-body", repr(response))
        self.assertIn("<redacted>", repr(response))

    def test_dynamic_binding_extractors_accept_only_frozen_outputs(self) -> None:
        signature = "1" * 64
        self.assertEqual(
            extract_dynamic_binding(
                "H08",
                json.dumps(
                    {"result": [{"signature": signature}]}
                ).encode(),
            ),
            ("RAPTOR_RECENT_SIGNATURE", signature),
        )
        mint = self.plan.public_bindings["USDC_MINT"]
        self.assertEqual(
            extract_dynamic_binding(
                "ST03",
                json.dumps({"data": [{"token": {"mint": mint}}]}).encode(),
            ),
            ("RECENT_PUMP_MINT", mint),
        )
        self.assertEqual(
            extract_dynamic_binding(
                "ST06",
                b'{"data":{"token":{"decimals":6}}}',
            ),
            ("RECENT_PUMP_DECIMALS", 6),
        )
        self.assertIsNone(
            extract_dynamic_binding("J01", b'{"outAmount":"1"}')
        )

    def test_dynamic_binding_extraction_fails_on_schema_drift(self) -> None:
        with self.assertRaisesRegex(
            DynamicBindingError,
            "st03_mint_missing",
        ):
            extract_dynamic_binding("ST03", b'{"data":[{"symbol":"X"}]}')
        with self.assertRaisesRegex(
            DynamicBindingError,
            "dynamic_response_not_json",
        ):
            extract_dynamic_binding("H08", b"not-json")
        with self.assertRaisesRegex(
            DynamicBindingError,
            "st06_pool_decimals_ambiguous",
        ):
            extract_dynamic_binding(
                "ST06",
                b'{"pools":[{"decimals":6},{"decimals":9}],'
                b'"token":"[REDACTED]"}',
            )

    def test_mocked_full_runner_preserves_35_attempt_order_and_caps(self) -> None:
        clock = FakeClock()
        observed_http: list[str] = []
        observed_wss: list[str] = []
        persisted: list[tuple[object, AttemptReceipt]] = []
        signature = "1" * 64
        mint = self.plan.public_bindings["USDC_MINT"]

        def http_exchange(
            request: BoundRequest,
            *,
            max_response_bytes: int,
        ) -> TransportResponse:
            self.assertEqual(max_response_bytes, 2_000_000)
            observed_http.append(request.attempt_id)
            if request.case_id == "H08":
                body = json.dumps(
                    {
                        "id": request.attempt_id,
                        "jsonrpc": "2.0",
                        "result": [{"signature": signature}],
                    }
                ).encode()
            elif request.case_id == "H11":
                body = json.dumps(
                    {
                        "error": {
                            "code": -32602,
                            "message": "invalid parameters",
                        },
                        "id": request.attempt_id,
                        "jsonrpc": "2.0",
                    }
                ).encode()
            elif request.case_id.startswith("H"):
                body = json.dumps(
                    {
                        "id": request.attempt_id,
                        "jsonrpc": "2.0",
                        "result": "ok",
                    }
                ).encode()
            elif request.case_id == "ST03":
                body = json.dumps({"data": [{"mint": mint}]}).encode()
            elif request.case_id == "ST06":
                body = b'{"token":{"decimals":6}}'
            elif request.case_id.startswith("ST"):
                body = b'{"data":[{"ok":true}]}'
            elif request.case_id == "J09":
                body = b'{"error":"NO_ROUTE"}'
            elif request.provider == "RAPTOR_HOSTED":
                body = (
                    b"OK"
                    if request.case_id == "R01"
                    else b'{"amountOut":"1"}'
                )
            else:
                body = b'{"outAmount":"1"}'
            return _response(body)

        runner_holder: dict[str, SmokeTransportRunner] = {}

        class FakeWssSession:
            def subscribe(
                self,
                request: BoundRequest,
                *,
                max_response_bytes: int,
                max_open_seconds: float,
                max_data_messages: int,
            ) -> tuple[TransportResponse, int | None]:
                self.assert_limits(
                    max_response_bytes,
                    max_open_seconds,
                    max_data_messages,
                )
                observed_wss.append(request.attempt_id)
                return (
                    _response(
                        b'{"data_messages":[],"subscribe_ack":{"result":7}}',
                        status_code=101,
                    ),
                    7,
                )

            @staticmethod
            def assert_limits(
                maximum: int,
                open_seconds: float,
                messages: int,
            ) -> None:
                if (maximum, open_seconds, messages) != (
                    2_000_000,
                    10.0,
                    1,
                ):
                    raise AssertionError("unexpected WSS limits")

            def unsubscribe(
                self,
                request: BoundRequest,
                *,
                max_response_bytes: int,
            ) -> TransportResponse:
                self.assert_limits(max_response_bytes, 10.0, 1)
                self_outer = runner_holder["runner"]
                if self_outer.guard.attempt_count != 13:
                    raise AssertionError(
                        "H12#2 side effect preceded its authorization"
                    )
                observed_wss.append(request.attempt_id)
                return _response(
                    b'{"jsonrpc":"2.0","id":"H12#2","result":true}',
                    status_code=101,
                )

            def close(self) -> None:
                return

        transport = BoundedProviderTransport(
            gate=ExternalExecutionGate(
                authority_phrase=EXTERNAL_AUTHORITY_PHRASE
            ),
            http_exchange=http_exchange,
            wss_session_factory=FakeWssSession,
        )
        runner = SmokeTransportRunner(
            plan=self.plan,
            credentials=self.credentials,
            transport=transport,
            event_sink=lambda event, receipt: persisted.append(
                (event, receipt)
            ),
            monotonic=clock.monotonic,
            sleeper=clock.sleep,
        )
        runner_holder["runner"] = runner
        summary = runner.run(run_id="t07a4b-20260724T060000Z")
        expected_http = [
            attempt
            for attempt in self.plan.attempt_ids
            if not attempt.startswith("H12#")
        ]
        self.assertEqual(observed_http, expected_http)
        self.assertEqual(observed_wss, ["H12#1", "H12#2"])
        self.assertEqual(
            [receipt.attempt_id for _, receipt in persisted],
            list(self.plan.attempt_ids),
        )
        self.assertEqual(summary.completed_attempts, 35)
        self.assertEqual(summary.planned_attempts, 35)
        self.assertEqual(
            summary.terminal_counts,
            {
                "INVALID_REQUEST": 1,
                "NO_ROUTE": 1,
                "SUCCESS": 33,
            },
        )
        self.assertEqual(summary.helius_credits, 15)
        self.assertEqual(summary.cash_spend_usd, 0)
        self.assertLessEqual(summary.response_bytes, 20_000_000)
        self.assertTrue(clock.sleeps)

    def test_response_classifier_fails_closed_on_semantic_drift(self) -> None:
        materialized = materialize_case(self.plan, "H01")
        request = bind_request(
            self.plan,
            attempt_id="H01#1",
            materialized_request=materialized,
            credentials=self.credentials,
        )
        malformed = classify_response(
            self.plan,
            request=request,
            materialized_request=materialized,
            response=_response(b"not-json"),
        )
        self.assertEqual(malformed.terminal_class, "MALFORMED_PAYLOAD")

        wrong_id = classify_response(
            self.plan,
            request=request,
            materialized_request=materialized,
            response=_response(
                b'{"jsonrpc":"2.0","id":"wrong","result":"ok"}'
            ),
        )
        self.assertEqual(wrong_id.terminal_class, "SCHEMA_DRIFT")
        self.assertEqual(wrong_id.error_class, "json_rpc_id_mismatch")

    def test_raptor_response_shapes_are_exact_and_provider_specific(self) -> None:
        health_materialized = materialize_case(self.plan, "R01")
        health_request = bind_request(
            self.plan,
            attempt_id="R01#1",
            materialized_request=health_materialized,
            credentials=None,
        )
        health = classify_response(
            self.plan,
            request=health_request,
            materialized_request=health_materialized,
            response=_response(b"OK"),
        )
        self.assertEqual(health.terminal_class, "SUCCESS")
        health_with_newline = classify_response(
            self.plan,
            request=health_request,
            materialized_request=health_materialized,
            response=_response(b"OK\n"),
        )
        self.assertEqual(health_with_newline.terminal_class, "SCHEMA_DRIFT")
        self.assertEqual(
            health_with_newline.error_class,
            "raptor_health_body_invalid",
        )

        raptor_materialized = materialize_case(self.plan, "R02")
        raptor_request = bind_request(
            self.plan,
            attempt_id="R02#1",
            materialized_request=raptor_materialized,
            credentials=None,
        )
        raptor_quote = classify_response(
            self.plan,
            request=raptor_request,
            materialized_request=raptor_materialized,
            response=_response(b'{"amountOut":"123"}'),
        )
        self.assertEqual(raptor_quote.terminal_class, "SUCCESS")
        raptor_jupiter_shape = classify_response(
            self.plan,
            request=raptor_request,
            materialized_request=raptor_materialized,
            response=_response(b'{"outAmount":"123"}'),
        )
        self.assertEqual(raptor_jupiter_shape.terminal_class, "SCHEMA_DRIFT")

        jupiter_materialized = materialize_case(self.plan, "J01")
        jupiter_request = bind_request(
            self.plan,
            attempt_id="J01#1",
            materialized_request=jupiter_materialized,
            credentials=None,
        )
        jupiter_raptor_shape = classify_response(
            self.plan,
            request=jupiter_request,
            materialized_request=jupiter_materialized,
            response=_response(b'{"amountOut":"123"}'),
        )
        self.assertEqual(jupiter_raptor_shape.terminal_class, "SCHEMA_DRIFT")
        jupiter_quote = classify_response(
            self.plan,
            request=jupiter_request,
            materialized_request=jupiter_materialized,
            response=_response(b'{"outAmount":"123"}'),
        )
        self.assertEqual(jupiter_quote.terminal_class, "SUCCESS")

    def test_keyless_binding_is_limited_to_public_providers(self) -> None:
        with self.assertRaisesRegex(
            TransportContractError,
            "helius_credential_required",
        ):
            bind_request(
                self.plan,
                attempt_id="H01#1",
                materialized_request=materialize_case(self.plan, "H01"),
                credentials=None,
            )
        with self.assertRaisesRegex(
            TransportContractError,
            "solana_tracker_credential_required",
        ):
            bind_request(
                self.plan,
                attempt_id="ST01#1",
                materialized_request=materialize_case(self.plan, "ST01"),
                credentials=None,
            )
        request = bind_request(
            self.plan,
            attempt_id="R02#1",
            materialized_request=materialize_case(self.plan, "R02"),
            credentials=None,
        )
        self.assertEqual(request.provider, "RAPTOR_HOSTED")
        self.assertNotIn("api-key", request.safe_receipt()["query_keys"])

    def test_attempt_receipt_bytes_are_deterministic_and_secret_free(self) -> None:
        request = bind_request(
            self.plan,
            attempt_id="ST01#1",
            materialized_request=materialize_case(self.plan, "ST01"),
            credentials=self.credentials,
        )
        instant = "2026-07-24T06:00:00+00:00"
        receipt = AttemptReceipt(
            attempt_id="ST01#1",
            case_id="ST01",
            provider="SOLANA_TRACKER_DATA",
            terminal_class="SUCCESS",
            response_status="SUCCESS",
            error_class=None,
            status_code=200,
            response_size_bytes=2,
            redacted_body_sha256="0" * 64,
            request_started_at=instant,
            request_sent_at=instant,
            response_headers_at=instant,
            response_complete_at=instant,
            safe_request=request.safe_receipt(),
            safe_response_headers=(("content-type", "application/json"),),
        )
        first = receipt.canonical_bytes()
        self.assertEqual(first, receipt.canonical_bytes())
        for secret in self.credentials.explicit_secret_values:
            self.assertNotIn(secret.encode(), first)

    def test_durable_sink_writes_immutable_partition_manifest_and_receipt(self) -> None:
        instant = datetime(2026, 7, 24, 6, 0, tzinfo=timezone.utc)
        ingested_at = instant + timedelta(seconds=1)
        materialized = materialize_case(self.plan, "H01")
        event = build_attempt_raw_event(
            self.plan,
            case_id="H01",
            materialized_request=materialized,
            response_body=b'{"jsonrpc":"2.0","id":"H01#1","result":"ok"}',
            response_status=RawResponseStatus.SUCCESS,
            error_class=None,
            observed_at=instant,
            available_to_strategy_at=instant,
            ingested_at=ingested_at,
            first_reliable_available_at=instant,
            explicit_secret_values=self.credentials.explicit_secret_values,
        )
        request = bind_request(
            self.plan,
            attempt_id="H01#1",
            materialized_request=materialized,
            credentials=self.credentials,
        )
        receipt = AttemptReceipt(
            attempt_id="H01#1",
            case_id="H01",
            provider="HELIUS_RPC",
            terminal_class="SUCCESS",
            response_status="SUCCESS",
            error_class=None,
            status_code=200,
            response_size_bytes=len(event.redacted_body),
            redacted_body_sha256=event.content_sha256,
            request_started_at=instant.isoformat(),
            request_sent_at=instant.isoformat(),
            response_headers_at=instant.isoformat(),
            response_complete_at=instant.isoformat(),
            safe_request=request.safe_receipt(),
            safe_response_headers=(),
        )
        second_observed_at = ingested_at + timedelta(seconds=1)
        second_ingested_at = second_observed_at + timedelta(seconds=1)
        second_materialized = materialize_case(self.plan, "H02")
        second_event = build_attempt_raw_event(
            self.plan,
            case_id="H02",
            materialized_request=second_materialized,
            response_body=(
                b'{"jsonrpc":"2.0","id":"H02#1","result":'
                b'{"feature-set":1,"solana-core":"2.0.0"}}'
            ),
            response_status=RawResponseStatus.SUCCESS,
            error_class=None,
            observed_at=second_observed_at,
            available_to_strategy_at=second_observed_at,
            ingested_at=second_ingested_at,
            first_reliable_available_at=second_observed_at,
            explicit_secret_values=self.credentials.explicit_secret_values,
        )
        second_request = bind_request(
            self.plan,
            attempt_id="H02#1",
            materialized_request=second_materialized,
            credentials=self.credentials,
        )
        second_receipt = replace(
            receipt,
            attempt_id="H02#1",
            case_id="H02",
            response_size_bytes=len(second_event.redacted_body),
            redacted_body_sha256=second_event.content_sha256,
            request_started_at=second_observed_at.isoformat(),
            request_sent_at=second_observed_at.isoformat(),
            response_headers_at=second_observed_at.isoformat(),
            response_complete_at=second_observed_at.isoformat(),
            safe_request=second_request.safe_receipt(),
        )
        run_id = "t07a4b-20260724T060000Z"
        with tempfile.TemporaryDirectory() as directory:
            raw_root = Path(directory).resolve()
            sink = DurableAttemptSink(raw_root=raw_root, run_id=run_id)
            sink(event, receipt)
            sink(second_event, second_receipt)
            run_root = (
                raw_root
                / "task07_provider_smoke_v1"
                / f"run={run_id}"
            )
            partition_paths = sorted(
                (run_root / "partitions").glob("*.parquet")
            )
            manifest_paths = sorted(
                (run_root / "receipts").glob("*.manifest.json")
            )
            receipt_paths = sorted(
                (run_root / "receipts").glob("*.receipt.json")
            )
            self.assertEqual(len(partition_paths), 2)
            self.assertEqual(len(manifest_paths), 2)
            self.assertEqual(len(receipt_paths), 2)
            manifests = [
                PartitionManifest.model_validate_json(path.read_bytes())
                for path in manifest_paths
            ]
            self.assertEqual(
                [manifest.first_reliable_available_at for manifest in manifests],
                [ingested_at, second_ingested_at],
            )
            for manifest in manifests:
                self.assertTrue(
                    manifest.logical_location.startswith("partitions/")
                )
                self.assertGreaterEqual(
                    manifest.first_reliable_available_at,
                    manifest.created_at,
                )
                observed = verify_raw_event_partition(
                    root=run_root,
                    manifest=manifest,
                )
                self.assertEqual(len(observed), 1)
            with self.assertRaisesRegex(
                TransportContractError,
                "run_output_already_exists",
            ):
                DurableAttemptSink(raw_root=raw_root, run_id=run_id)

    def test_recovery_verifies_exact_parent_prefix_and_reclassifies_r01_r03(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            raw_root = Path(directory).resolve()
            run_id = self._write_synthetic_r4_parent(raw_root)
            recovery = prepare_raptor_tail_recovery(
                self.plan,
                raw_root=raw_root,
                parent_run_id=run_id,
            )
            self.assertEqual(len(recovery.verified_attempts), 33)
            self.assertEqual(recovery.verified_file_count, 99)
            self.assertEqual(
                recovery.pending_attempts,
                ("R04#1", "R05#1"),
            )
            self.assertEqual(
                recovery.reclassified_attempts,
                (
                    ("R01#1", "SUCCESS"),
                    ("R02#1", "SUCCESS"),
                    ("R03#1", "SUCCESS"),
                ),
            )
            self.assertEqual(
                set(recovery.bindings),
                {
                    "RAPTOR_RECENT_SIGNATURE",
                    "RECENT_PUMP_DECIMALS",
                    "RECENT_PUMP_MINT",
                },
            )

    def test_recovery_fails_closed_on_parent_inventory_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            raw_root = Path(directory).resolve()
            run_id = self._write_synthetic_r4_parent(raw_root)
            run_root = (
                raw_root
                / "task07_provider_smoke_v1"
                / f"run={run_id}"
            )
            missing = run_root / "receipts" / "R03_1.receipt.json"
            missing.unlink()
            with self.assertRaisesRegex(
                RecoveryEvidenceError,
                "parent_receipt_inventory_mismatch",
            ):
                prepare_raptor_tail_recovery(
                    self.plan,
                    raw_root=raw_root,
                    parent_run_id=run_id,
                )

    def test_raptor_tail_runner_can_issue_only_r04_r05_without_credentials(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            raw_root = Path(directory).resolve()
            run_id = self._write_synthetic_r4_parent(raw_root)
            recovery = prepare_raptor_tail_recovery(
                self.plan,
                raw_root=raw_root,
                parent_run_id=run_id,
            )
            observed: list[str] = []
            persisted: list[tuple[object, AttemptReceipt]] = []

            def http_exchange(
                request: BoundRequest,
                *,
                max_response_bytes: int,
            ) -> TransportResponse:
                self.assertEqual(max_response_bytes, 2_000_000)
                self.assertEqual(request.provider, "RAPTOR_HOSTED")
                observed.append(request.attempt_id)
                return _response(b'{"amountOut":"123","routePlan":[]}')

            clock = FakeClock()
            transport = BoundedProviderTransport(
                gate=RaptorTailExecutionGate(
                    authority_phrase=RAPTOR_TAIL_AUTHORITY_PHRASE,
                ),
                http_exchange=http_exchange,
            )
            runner = RaptorTailRunner(
                plan=self.plan,
                recovery=recovery,
                transport=transport,
                event_sink=lambda event, receipt: persisted.append(
                    (event, receipt)
                ),
                monotonic=clock.monotonic,
                sleeper=clock.sleep,
            )
            summary = runner.run(
                child_run_id="t07a4b-20260724T140000Z"
            )
            self.assertEqual(observed, ["R04#1", "R05#1"])
            self.assertEqual(
                [receipt.attempt_id for _, receipt in persisted],
                observed,
            )
            self.assertEqual(summary.completed_attempts, 2)
            self.assertEqual(summary.terminal_counts, {"SUCCESS": 2})
            self.assertEqual(summary.cash_spend_usd, 0)
            self.assertEqual(clock.sleeps, [1.0])

            with self.assertRaisesRegex(
                ExternalAuthorityRequiredError,
                "full_run_authority_scope_mismatch",
            ):
                SmokeTransportRunner(
                    plan=self.plan,
                    credentials=self.credentials,
                    transport=transport,
                    event_sink=lambda _event, _receipt: None,
                )

    def test_default_run_id_is_utc_and_bounded(self) -> None:
        instant = datetime(
            2026,
            7,
            24,
            6,
            7,
            8,
            tzinfo=timezone.utc,
        )
        self.assertEqual(
            default_run_id(instant),
            "t07a4b-20260724T060708Z",
        )
        with self.assertRaisesRegex(
            TransportContractError,
            "run_time_not_aware",
        ):
            default_run_id(datetime(2026, 7, 24, 6, 7, 8))

    def test_launcher_default_path_does_not_prompt_write_or_execute(self) -> None:
        script_path = ROOT / "scripts" / "run_task07_provider_smoke.py"
        spec = importlib.util.spec_from_file_location(
            "task07_smoke_launcher_for_test",
            script_path,
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        def unexpected_prompt(_: str) -> str:
            self.fail("offline preflight must not prompt")

        output = io.StringIO()
        with redirect_stdout(output):
            code = module.main(
                [],
                input_fn=unexpected_prompt,
                secret_input_fn=unexpected_prompt,
            )
        self.assertEqual(code, 0)
        self.assertIn("TASK07_TRANSPORT_PREFLIGHT: PASS", output.getvalue())
        self.assertIn(
            "LIVE_EXECUTION: BLOCKED_REQUIRES_SEPARATE_ATOM",
            output.getvalue(),
        )

    def test_launcher_raptor_tail_preflight_is_offline_and_read_only(
        self,
    ) -> None:
        script_path = ROOT / "scripts" / "run_task07_provider_smoke.py"
        spec = importlib.util.spec_from_file_location(
            "task07_raptor_tail_preflight_for_test",
            script_path,
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        def unexpected_prompt(_: str) -> str:
            self.fail("offline recovery preflight must not prompt")

        with tempfile.TemporaryDirectory() as directory:
            raw_root = Path(directory).resolve()
            run_id = self._write_synthetic_r4_parent(raw_root)
            module.RAW_ROOT = raw_root
            before = sorted(
                path.relative_to(raw_root).as_posix()
                for path in raw_root.rglob("*")
            )
            output = io.StringIO()
            with redirect_stdout(output):
                code = module.main(
                    ["--prepare-raptor-tail", run_id],
                    input_fn=unexpected_prompt,
                    secret_input_fn=unexpected_prompt,
                )
            after = sorted(
                path.relative_to(raw_root).as_posix()
                for path in raw_root.rglob("*")
            )
        self.assertEqual(code, 0)
        self.assertEqual(before, after)
        self.assertIn(
            "TASK07_RAPTOR_TAIL_PREFLIGHT: PASS",
            output.getvalue(),
        )
        self.assertIn('"verified_attempts":33', output.getvalue())
        self.assertIn('"verified_files":99', output.getvalue())

    def test_launcher_raptor_tail_wrong_phrase_creates_no_child_run(
        self,
    ) -> None:
        script_path = ROOT / "scripts" / "run_task07_provider_smoke.py"
        spec = importlib.util.spec_from_file_location(
            "task07_raptor_tail_wrong_phrase_for_test",
            script_path,
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        def secret_prompt(_: str) -> str:
            self.fail("Raptor tail must never prompt for provider keys")

        with tempfile.TemporaryDirectory() as directory:
            raw_root = Path(directory).resolve()
            run_id = self._write_synthetic_r4_parent(raw_root)
            module.RAW_ROOT = raw_root
            before = sorted(
                path.relative_to(raw_root).as_posix()
                for path in raw_root.rglob("*")
            )
            output = io.StringIO()
            with redirect_stdout(output):
                code = module.main(
                    ["--execute-raptor-tail", run_id],
                    input_fn=lambda _: "wrong",
                    secret_input_fn=secret_prompt,
                )
            after = sorted(
                path.relative_to(raw_root).as_posix()
                for path in raw_root.rglob("*")
            )
        self.assertEqual(code, 2)
        self.assertEqual(before, after)
        self.assertIn(
            "TASK07_RAPTOR_TAIL: BLOCKED_AUTHORITY_PHRASE",
            output.getvalue(),
        )

    def test_launcher_wrong_phrase_stops_before_secret_prompt(self) -> None:
        script_path = ROOT / "scripts" / "run_task07_provider_smoke.py"
        spec = importlib.util.spec_from_file_location(
            "task07_smoke_launcher_wrong_phrase",
            script_path,
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        def secret_prompt(_: str) -> str:
            self.fail("secret prompt must not run after authority mismatch")

        output = io.StringIO()
        with redirect_stdout(output):
            code = module.main(
                ["--execute"],
                input_fn=lambda _: "wrong",
                secret_input_fn=secret_prompt,
            )
        self.assertEqual(code, 2)
        self.assertIn(
            "TASK07_LIVE_SMOKE: BLOCKED_AUTHORITY_PHRASE",
            output.getvalue(),
        )

    def test_prohibited_payload_is_reduced_to_sanitized_failure_evidence(
        self,
    ) -> None:
        materialized = materialize_case(self.plan, "J01")
        request = bind_request(
            self.plan,
            attempt_id="J01#1",
            materialized_request=materialized,
            credentials=self.credentials,
        )
        response = _response(b'{"transaction":"forbidden"}')
        event, receipt, safe_body = _attempt_evidence(
            self.plan,
            request=request,
            materialized_request=materialized,
            response=response,
            credentials=self.credentials,
        )
        self.assertEqual(receipt.terminal_class, "PROHIBITED_PAYLOAD")
        self.assertEqual(receipt.response_status, "INVALID_RESPONSE")
        self.assertNotIn(b"forbidden", safe_body)
        self.assertEqual(event.redacted_body, safe_body)


if __name__ == "__main__":
    unittest.main()
