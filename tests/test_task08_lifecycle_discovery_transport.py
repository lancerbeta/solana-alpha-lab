from __future__ import annotations

import base64
import contextlib
import importlib.util
import io
import json
import struct
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.lifecycle_discovery import (  # noqa: E402
    load_frozen_discovery_plan,
)
from solana_alpha_lab.lifecycle_discovery_transport import (  # noqa: E402
    DATASET_ID,
    DEFAULT_HTTP_TIMEOUT_SECONDS,
    EXTERNAL_AUTHORITY_PHRASE,
    LOGS_SUBSCRIBE_REQUEST_ID,
    MAX_ADMITTED_RECEIVED_BYTES,
    MAX_EVIDENCE_RECORDS,
    NETWORK_DISABLED_IN_ATOM4,
    RAW_LOGICAL_ROOT,
    TRACKER_MAX_RESPONSE_BYTES,
    TRACKER_OVERVIEW_LIMIT,
    TRACKER_PATHS,
    TRANSPORT_CONTRACT_VERSION,
    WSS_CAPTURE_SECONDS,
    BoundProbeRequest,
    DurableProbeSink,
    ExternalAuthorityRequiredError,
    ExternalExecutionGate,
    HttpCapture,
    InMemoryEvidenceSink,
    NotificationSchemaError,
    ProbeAccessAttestation,
    ProbeCredentials,
    ProbeEvidence,
    ProbeStopError,
    ProbeTransportContractError,
    ProbeTransportRunner,
    ProgramLogAttributionError,
    WssCapture,
    admission_budget_proof,
    assert_atom4_offline_boundary,
    bind_get_transaction,
    bind_logs_subscribe,
    bind_tracker_snapshot,
    parse_logs_notification,
    parse_subscription_ack,
    safe_preflight_summary,
    stdlib_http_exchange,
    websockets_wss_exchange,
)
from solana_alpha_lab.pump_event_decoder import (  # noqa: E402
    PROGRAM_DATA_PREFIX,
    PUMP_PROGRAM_ID,
    FieldSpec,
    PumpEventPlan,
    load_pinned_pump_event_plan,
)
from solana_alpha_lab.contracts.schema_v1 import (  # noqa: E402
    PartitionManifest,
    RawResponseStatus,
)
from solana_alpha_lab.storage import (  # noqa: E402
    verify_raw_event_partition,
)

DISCOVERY_FIXTURE = (
    ROOT
    / "tests"
    / "fixtures"
    / "task08"
    / "lifecycle_discovery_contract_v1.json"
)
EVENT_FIXTURE = (
    ROOT
    / "tests"
    / "fixtures"
    / "task08"
    / "pump_event_idl_subset_v1.json"
)
MODULE_PATH = SRC / "solana_alpha_lab" / "lifecycle_discovery_transport.py"
LAUNCHER_PATH = ROOT / "scripts" / "run_task08_lifecycle_discovery_probe.py"
CONTRACT_PATH = (
    ROOT
    / "docs"
    / "contracts"
    / "lifecycle_discovery_probe_transport_contract_v1.md"
)
SIGNATURE = "2" * 88
SECOND_SIGNATURE = "3" * 88
OTHER_PROGRAM_ID = "11111111111111111111111111111111"


def _credentials() -> ProbeCredentials:
    h = "unit-" + ("h" * 20)
    t = "unit-" + ("t" * 20)
    return ProbeCredentials(
        helius_api_key=h,
        solana_tracker_api_key=t,
    )


def _access() -> ProbeAccessAttestation:
    return ProbeAccessAttestation(
        dashboard_readback_completed=True,
        helius_credits_remaining=41,
        solana_tracker_requests_remaining=8,
    )


def _sample_value(field: FieldSpec, seed: int) -> object:
    if field.type_spec == "bool":
        return True
    if field.type_spec == "i64":
        return 1_721_888_000 + seed
    if field.type_spec == "pubkey":
        return bytes([(seed + 1) % 251]) * 32
    if field.type_spec == "string":
        return f"synthetic-{field.name}-{seed}"
    if field.type_spec == "u16":
        return seed
    if field.type_spec == "u64":
        return 10_000 + seed
    if field.type_spec == ("vec_defined", "Shareholder"):
        return [
            {
                "address": bytes([(seed + 2) % 251]) * 32,
                "share_bps": 125,
            }
        ]
    raise AssertionError(f"unsupported_test_type:{field.type_spec!r}")


def _encode_type(
    plan: PumpEventPlan,
    type_spec: object,
    value: object,
) -> bytes:
    if type_spec == "bool":
        return bytes([int(bool(value))])
    if type_spec == "i64":
        return struct.pack("<q", int(value))
    if type_spec == "pubkey":
        if not isinstance(value, bytes) or len(value) != 32:
            raise AssertionError("test_pubkey_must_be_32_bytes")
        return value
    if type_spec == "string":
        encoded = str(value).encode("utf-8")
        return struct.pack("<I", len(encoded)) + encoded
    if type_spec == "u16":
        return struct.pack("<H", int(value))
    if type_spec == "u64":
        return struct.pack("<Q", int(value))
    if type_spec == ("vec_defined", "Shareholder"):
        if not isinstance(value, list):
            raise AssertionError("test_vector_must_be_list")
        encoded = bytearray(struct.pack("<I", len(value)))
        for item in value:
            if not isinstance(item, dict):
                raise AssertionError("test_defined_value_must_be_mapping")
            for field in plan.defined_types["Shareholder"]:
                encoded.extend(
                    _encode_type(plan, field.type_spec, item[field.name])
                )
        return bytes(encoded)
    raise AssertionError(f"unsupported_test_type:{type_spec!r}")


def _event_line(plan: PumpEventPlan, event_name: str = "CreateEvent") -> str:
    schema = next(event for event in plan.events if event.name == event_name)
    values = {
        field.name: _sample_value(field, index)
        for index, field in enumerate(schema.fields)
    }
    payload = schema.discriminator + b"".join(
        _encode_type(plan, field.type_spec, values[field.name])
        for field in schema.fields
    )
    return PROGRAM_DATA_PREFIX + base64.b64encode(payload).decode("ascii")


def _unknown_event_line() -> str:
    return PROGRAM_DATA_PREFIX + base64.b64encode(
        b"UNKNOWN!" + b"ignored"
    ).decode("ascii")


def _ack(subscription_id: int = 17) -> bytes:
    return json.dumps(
        {
            "id": LOGS_SUBSCRIBE_REQUEST_ID,
            "jsonrpc": "2.0",
            "result": subscription_id,
        },
        separators=(",", ":"),
    ).encode("utf-8")


def _notification(
    event_plan: PumpEventPlan,
    *,
    signature: str = SIGNATURE,
    subscription_id: int = 17,
    err: object = None,
    logs: list[str] | None = None,
) -> bytes:
    if logs is None:
        logs = [
            f"Program {PUMP_PROGRAM_ID} invoke [1]",
            _event_line(event_plan),
            f"Program {PUMP_PROGRAM_ID} success",
        ]
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "method": "logsNotification",
            "params": {
                "result": {
                    "context": {"slot": 310_000_000},
                    "value": {
                        "err": err,
                        "logs": logs,
                        "signature": signature,
                    },
                },
                "subscription": subscription_id,
            },
        },
        separators=(",", ":"),
    ).encode("utf-8")


class _Clock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class _MockWss:
    def __init__(
        self,
        *,
        clock: _Clock,
        notifications: tuple[bytes, ...],
        advance_seconds: float = 1.0,
        acknowledgement: bytes | None = None,
        terminal_class: str = "BOUND_REACHED",
        error_class: str | None = None,
        stop_reason: str = "ADAPTER_BOUND",
    ) -> None:
        self.clock = clock
        self.notifications = notifications
        self.advance_seconds = advance_seconds
        self.acknowledgement = acknowledgement or _ack()
        self.terminal_class = terminal_class
        self.error_class = error_class
        self.stop_reason = stop_reason
        frame_time = datetime(2026, 7, 25, 12, tzinfo=UTC)
        self.acknowledgement_observed_at = frame_time
        self.notification_observed_at = tuple(
            frame_time + timedelta(seconds=index + 1)
            for index in range(len(notifications))
        )
        self.requests: list[BoundProbeRequest] = []
        self.limits: list[tuple[int, int, int]] = []

    def __call__(
        self,
        request: BoundProbeRequest,
        *,
        max_open_seconds: int,
        max_stream_bytes: int,
        max_notifications: int,
    ) -> WssCapture:
        self.requests.append(request)
        self.limits.append(
            (max_open_seconds, max_stream_bytes, max_notifications)
        )
        self.clock.advance(self.advance_seconds)
        return WssCapture(
            acknowledgement=self.acknowledgement,
            notifications=self.notifications,
            acknowledgement_observed_at=(
                self.acknowledgement_observed_at
            ),
            notification_observed_at=self.notification_observed_at,
            terminal_class=self.terminal_class,
            error_class=self.error_class,
            stop_reason=self.stop_reason,
        )


class _MockHttp:
    def __init__(self, *, clock: _Clock) -> None:
        self.clock = clock
        self.requests: list[BoundProbeRequest] = []
        self.status_code = 200
        self.redirect = False
        self.override_body: bytes | None = None
        self.tracker_body = (
            b'{"graduated":[],"graduating":[],"latest":[]}'
        )

    def __call__(
        self,
        request: BoundProbeRequest,
        *,
        max_response_bytes: int,
    ) -> HttpCapture:
        self.requests.append(request)
        self.clock.advance(0.01)
        if self.override_body is not None:
            body = self.override_body
        elif request.provider == "SOLANA_TRACKER":
            body = self.tracker_body
        else:
            body = json.dumps(
                {
                    "id": request.request_id,
                    "jsonrpc": "2.0",
                    "result": {"slot": 310_000_000},
                },
                separators=(",", ":"),
            ).encode("utf-8")
        if len(body) > max_response_bytes:
            return HttpCapture(
                status_code=None,
                body=b"",
                response_url=request.url,
                terminal_class="RESPONSE_TOO_LARGE",
                error_class="http_response_too_large",
                received_bytes=max_response_bytes + 1,
            )
        response_url = (
            "https://unexpected.invalid/redirect"
            if self.redirect
            else request.url
        )
        return HttpCapture(
            status_code=self.status_code,
            body=body,
            response_url=response_url,
        )


class Task08LifecycleDiscoveryTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = load_frozen_discovery_plan(DISCOVERY_FIXTURE)
        cls.event_plan = load_pinned_pump_event_plan(EVENT_FIXTURE)

    def _runner(
        self,
        *,
        notifications: tuple[bytes, ...],
        sink: object | None = None,
        advance_seconds: float = 1.0,
        terminal_class: str = "BOUND_REACHED",
        error_class: str | None = None,
        stop_reason: str = "ADAPTER_BOUND",
    ) -> tuple[
        ProbeTransportRunner,
        _Clock,
        _MockWss,
        _MockHttp,
        InMemoryEvidenceSink,
        list[float],
    ]:
        clock = _Clock()
        wss = _MockWss(
            clock=clock,
            notifications=notifications,
            advance_seconds=advance_seconds,
            terminal_class=terminal_class,
            error_class=error_class,
            stop_reason=stop_reason,
        )
        http = _MockHttp(clock=clock)
        memory_sink = InMemoryEvidenceSink()
        selected_sink = sink or memory_sink
        pacing: list[float] = []

        def pace(seconds: float) -> None:
            pacing.append(seconds)
            clock.advance(seconds)

        runner = ProbeTransportRunner(
            plan=self.plan,
            event_plan=self.event_plan,
            credentials=_credentials(),
            access=_access(),
            gate=ExternalExecutionGate(EXTERNAL_AUTHORITY_PHRASE),
            wss_exchange=wss,
            http_exchange=http,
            evidence_sink=selected_sink,  # type: ignore[arg-type]
            clock=clock,
            pace=pace,
            now=lambda: datetime(2026, 7, 25, tzinfo=UTC),
        )
        return runner, clock, wss, http, memory_sink, pacing

    def test_preflight_is_exact_and_offline(self) -> None:
        summary = safe_preflight_summary(self.plan, self.event_plan)
        self.assertTrue(NETWORK_DISABLED_IN_ATOM4)
        self.assertEqual(TRANSPORT_CONTRACT_VERSION, "1.1")
        self.assertEqual(summary["atom"], "T08-A5U")
        self.assertEqual(
            summary["admission_received_bytes_cap"],
            MAX_ADMITTED_RECEIVED_BYTES,
        )
        self.assertEqual(
            summary["admission_budget_proof"],
            admission_budget_proof(),
        )
        self.assertGreater(
            summary["admission_budget_proof"][
                "remaining_safety_bytes"
            ],
            0,
        )
        self.assertFalse(summary["network_authorized"])
        self.assertFalse(summary["credential_prompted"])
        self.assertFalse(summary["durable_output_created"])
        self.assertTrue(summary["concrete_adapters_ready"])
        self.assertEqual(
            summary["durable_output_logical_root"],
            RAW_LOGICAL_ROOT,
        )
        self.assertEqual(summary["provider_requests_planned"], 0)
        self.assertEqual(summary["wss_capture_seconds"], WSS_CAPTURE_SECONDS)
        self.assertEqual(summary["tracker_paths"], list(TRACKER_PATHS))
        self.assertEqual(
            summary["tracker_category_limit"],
            TRACKER_OVERVIEW_LIMIT,
        )
        self.assertEqual(
            summary["tracker_max_response_bytes"],
            TRACKER_MAX_RESPONSE_BYTES,
        )
        self.assertEqual(summary["tracker_planned_requests"], 2)

    def test_credentials_requests_and_receipts_are_redacted(self) -> None:
        credentials = _credentials()
        requests = [
            bind_logs_subscribe(credentials),
            bind_get_transaction(
                credentials,
                signature=SIGNATURE,
                ordinal=1,
            ),
            bind_tracker_snapshot(
                credentials,
                phase="OPEN",
            ),
        ]
        for request in requests:
            text = repr(request) + json.dumps(request.safe_receipt())
            self.assertNotIn(credentials.helius_api_key, text)
            self.assertNotIn(credentials.solana_tracker_api_key, text)
            self.assertNotIn("https://", text)
            self.assertNotIn("wss://", text)
        self.assertNotIn(credentials.helius_api_key, repr(credentials))
        self.assertNotIn(credentials.solana_tracker_api_key, repr(credentials))

    def test_exact_request_bodies_hosts_methods_and_paths(self) -> None:
        credentials = _credentials()
        wss = bind_logs_subscribe(credentials)
        wss_body = json.loads(wss.body)
        self.assertEqual(wss.provider, "HELIUS")
        self.assertEqual(wss.transport, "WSS")
        self.assertEqual(wss.method, "POST")
        self.assertEqual(wss.safe_receipt()["host"], "mainnet.helius-rpc.com")
        self.assertEqual(wss_body["method"], "logsSubscribe")
        self.assertEqual(
            wss_body["params"],
            [
                {"mentions": [PUMP_PROGRAM_ID]},
                {"commitment": "confirmed"},
            ],
        )

        followup = bind_get_transaction(
            credentials,
            signature=SIGNATURE,
            ordinal=20,
        )
        followup_body = json.loads(followup.body)
        self.assertEqual(followup.transport, "HTTP")
        self.assertEqual(followup_body["method"], "getTransaction")
        self.assertEqual(followup_body["params"][0], SIGNATURE)
        self.assertEqual(
            followup_body["params"][1],
            {
                "commitment": "confirmed",
                "encoding": "json",
                "maxSupportedTransactionVersion": 0,
            },
        )

        request = bind_tracker_snapshot(
            credentials,
            phase="CLOSE",
        )
        self.assertEqual(request.method, "GET")
        self.assertEqual(
            request.safe_receipt()["path"],
            TRACKER_PATHS[0],
        )
        self.assertEqual(
            request.safe_receipt()["query_keys"],
            ["limit"],
        )
        self.assertTrue(
            request.url.endswith(f"?limit={TRACKER_OVERVIEW_LIMIT}")
        )

    def test_endpoint_method_path_and_ordinal_drift_fail_closed(self) -> None:
        credentials = _credentials()
        with self.assertRaisesRegex(
            ProbeTransportContractError,
            "tracker_phase_invalid",
        ):
            bind_tracker_snapshot(
                credentials,
                phase="MIDDLE",
            )
        tracker = bind_tracker_snapshot(
            credentials,
            phase="OPEN",
        )
        with self.assertRaisesRegex(
            ProbeTransportContractError,
            "tracker_endpoint_drift",
        ):
            BoundProbeRequest(
                request_id=tracker.request_id,
                provider=tracker.provider,
                transport=tracker.transport,
                method=tracker.method,
                url=tracker.url.replace(
                    f"limit={TRACKER_OVERVIEW_LIMIT}",
                    f"limit={TRACKER_OVERVIEW_LIMIT + 1}",
                ),
                headers=tracker.headers,
                body=tracker.body,
                safe_query_keys=tracker.safe_query_keys,
            )
        with self.assertRaisesRegex(
            ProbeTransportContractError,
            "followup_ordinal_invalid",
        ):
            bind_get_transaction(
                credentials,
                signature=SIGNATURE,
                ordinal=21,
            )
        valid = bind_logs_subscribe(credentials)
        with self.assertRaisesRegex(
            ProbeTransportContractError,
            "helius_endpoint_drift",
        ):
            BoundProbeRequest(
                request_id=valid.request_id,
                provider=valid.provider,
                transport=valid.transport,
                method=valid.method,
                url=(
                    "wss://example.invalid/?"
                    + "api-key"
                    + "="
                    + "not-a-real-value"
                ),
                headers=valid.headers,
                body=valid.body,
                safe_query_keys=(),
            )

    def test_access_attestation_and_external_gate_fail_closed(self) -> None:
        with self.assertRaisesRegex(
            ExternalAuthorityRequiredError,
            "external_authority_phrase_mismatch",
        ):
            ExternalExecutionGate("wrong").require()
        ExternalExecutionGate(EXTERNAL_AUTHORITY_PHRASE).require()

        cases = (
            ProbeAccessAttestation(False, 41, 8),
            ProbeAccessAttestation(True, 40, 8),
            ProbeAccessAttestation(True, 41, 7),
            ProbeAccessAttestation(True, 41, 8, 1),
        )
        for access in cases:
            with self.subTest(access=access):
                with self.assertRaises(ProbeTransportContractError):
                    access.require(self.plan)
        _access().require(self.plan)

    def test_wss_capture_requires_utc_ordered_receive_times(self) -> None:
        observed_at = datetime(2026, 7, 25, 12, tzinfo=UTC)
        capture = WssCapture(
            acknowledgement=_ack(),
            notifications=(b"{}",),
            acknowledgement_observed_at=observed_at,
            notification_observed_at=(
                observed_at + timedelta(seconds=1),
            ),
        )
        self.assertEqual(
            capture.notification_observed_at[0],
            observed_at + timedelta(seconds=1),
        )

        cases = (
            {
                "acknowledgement": _ack(),
                "notifications": (),
            },
            {
                "acknowledgement": _ack(),
                "notifications": (b"{}",),
                "acknowledgement_observed_at": observed_at,
                "notification_observed_at": (),
            },
            {
                "acknowledgement": _ack(),
                "notifications": (b"{}",),
                "acknowledgement_observed_at": observed_at,
                "notification_observed_at": (
                    datetime(2026, 7, 25, 12),
                ),
            },
            {
                "acknowledgement": _ack(),
                "notifications": (b"{}",),
                "acknowledgement_observed_at": (
                    observed_at + timedelta(seconds=2)
                ),
                "notification_observed_at": (
                    observed_at + timedelta(seconds=1),
                ),
            },
        )
        for values in cases:
            with self.subTest(values=values):
                with self.assertRaises(ProbeTransportContractError):
                    WssCapture(**values)

    def test_subscription_ack_is_strict_and_duplicate_safe(self) -> None:
        self.assertEqual(parse_subscription_ack(_ack()), 17)
        with self.assertRaisesRegex(
            NotificationSchemaError,
            "wss_ack_identity_drift",
        ):
            parse_subscription_ack(
                b'{"id":"wrong","jsonrpc":"2.0","result":17}'
            )
        with self.assertRaisesRegex(
            NotificationSchemaError,
            "json_duplicate_key",
        ):
            parse_subscription_ack(
                b'{"id":"task08-logs-subscribe","id":17,'
                b'"jsonrpc":"2.0","result":17}'
            )

    def test_successful_pump_event_is_attributed_and_decoded(self) -> None:
        parsed = parse_logs_notification(
            _notification(self.event_plan),
            expected_subscription_id=17,
            event_plan=self.event_plan,
        )
        self.assertTrue(parsed.transaction_succeeded)
        self.assertTrue(parsed.is_followup_candidate)
        self.assertEqual(parsed.signature, SIGNATURE)
        self.assertEqual(
            [event.event_name for event in parsed.decoded_events],
            ["CreateEvent"],
        )
        self.assertEqual(parsed.unsupported_pump_program_data, 0)

    def test_only_create_event_is_a_probe_followup_candidate(self) -> None:
        parsed = parse_logs_notification(
            _notification(
                self.event_plan,
                logs=[
                    f"Program {PUMP_PROGRAM_ID} invoke [1]",
                    _event_line(self.event_plan, "TradeEvent"),
                    f"Program {PUMP_PROGRAM_ID} success",
                ],
            ),
            expected_subscription_id=17,
            event_plan=self.event_plan,
        )
        self.assertEqual(
            [event.event_name for event in parsed.decoded_events],
            ["TradeEvent"],
        )
        self.assertFalse(parsed.is_followup_candidate)

    def test_terminal_log_truncation_is_typed_and_never_promoted(self) -> None:
        parsed = parse_logs_notification(
            _notification(
                self.event_plan,
                logs=[
                    f"Program {PUMP_PROGRAM_ID} invoke [1]",
                    _event_line(self.event_plan),
                    "Log truncated",
                ],
            ),
            expected_subscription_id=17,
            event_plan=self.event_plan,
        )
        self.assertTrue(parsed.transaction_succeeded)
        self.assertTrue(parsed.logs_truncated)
        self.assertFalse(parsed.is_followup_candidate)
        self.assertEqual(parsed.decoded_events, ())
        self.assertEqual(parsed.unsupported_pump_program_data, 0)

    def test_log_truncation_marker_must_be_unique_and_terminal(self) -> None:
        cases = (
            [
                f"Program {PUMP_PROGRAM_ID} invoke [1]",
                "Log truncated",
                f"Program {PUMP_PROGRAM_ID} success",
            ],
            [
                f"Program {PUMP_PROGRAM_ID} invoke [1]",
                "Log truncated",
                "Log truncated",
            ],
        )
        for logs in cases:
            with self.subTest(logs=logs):
                with self.assertRaisesRegex(
                    ProgramLogAttributionError,
                    "program_log_truncation_marker_invalid",
                ):
                    parse_logs_notification(
                        _notification(self.event_plan, logs=logs),
                        expected_subscription_id=17,
                        event_plan=self.event_plan,
                    )

    def test_failed_transaction_is_retained_but_never_promoted(self) -> None:
        parsed = parse_logs_notification(
            _notification(
                self.event_plan,
                err={"InstructionError": [0, "Custom"]},
            ),
            expected_subscription_id=17,
            event_plan=self.event_plan,
        )
        self.assertFalse(parsed.transaction_succeeded)
        self.assertFalse(parsed.is_followup_candidate)
        self.assertEqual(parsed.decoded_events, ())

    def test_cross_program_data_cannot_be_promoted_to_pump(self) -> None:
        parsed = parse_logs_notification(
            _notification(
                self.event_plan,
                logs=[
                    f"Program {PUMP_PROGRAM_ID} invoke [1]",
                    f"Program {OTHER_PROGRAM_ID} invoke [2]",
                    _event_line(self.event_plan),
                    f"Program {OTHER_PROGRAM_ID} success",
                    f"Program {PUMP_PROGRAM_ID} success",
                ],
            ),
            expected_subscription_id=17,
            event_plan=self.event_plan,
        )
        self.assertEqual(parsed.decoded_events, ())
        self.assertFalse(parsed.is_followup_candidate)

    def test_invocation_stack_mismatch_and_orphan_data_stop(self) -> None:
        cases = (
            [
                _event_line(self.event_plan),
            ],
            [
                f"Program {PUMP_PROGRAM_ID} invoke [2]",
                f"Program {PUMP_PROGRAM_ID} success",
            ],
            [
                f"Program {PUMP_PROGRAM_ID} invoke [1]",
                f"Program {OTHER_PROGRAM_ID} success",
            ],
            [
                f"Program {PUMP_PROGRAM_ID} invoke [1]",
            ],
        )
        for logs in cases:
            with self.subTest(logs=logs):
                with self.assertRaises(ProgramLogAttributionError):
                    parse_logs_notification(
                        _notification(self.event_plan, logs=logs),
                        expected_subscription_id=17,
                        event_plan=self.event_plan,
                    )

    def test_unsupported_pump_program_data_is_counted_without_promotion(self) -> None:
        parsed = parse_logs_notification(
            _notification(
                self.event_plan,
                logs=[
                    f"Program {PUMP_PROGRAM_ID} invoke [1]",
                    _unknown_event_line(),
                    f"Program {PUMP_PROGRAM_ID} success",
                ],
            ),
            expected_subscription_id=17,
            event_plan=self.event_plan,
        )
        self.assertEqual(parsed.decoded_events, ())
        self.assertEqual(parsed.unsupported_pump_program_data, 1)

    def test_notification_schema_and_subscription_drift_stop(self) -> None:
        with self.assertRaisesRegex(
            NotificationSchemaError,
            "logs_subscription_id_mismatch",
        ):
            parse_logs_notification(
                _notification(self.event_plan, subscription_id=18),
                expected_subscription_id=17,
                event_plan=self.event_plan,
            )
        document = json.loads(_notification(self.event_plan))
        document["params"]["result"]["value"]["extra"] = 1
        with self.assertRaisesRegex(
            NotificationSchemaError,
            "logs_notification_value_keys_drift",
        ):
            parse_logs_notification(
                json.dumps(document).encode("utf-8"),
                expected_subscription_id=17,
                event_plan=self.event_plan,
            )

    def test_mocked_runner_is_sequential_bounded_and_deduplicates_followups(
        self,
    ) -> None:
        notifications = (
            _notification(self.event_plan),
            _notification(self.event_plan),
            _notification(
                self.event_plan,
                signature=SECOND_SIGNATURE,
                err={"InstructionError": [0, "Custom"]},
            ),
        )
        runner, _, wss, http, sink, pacing = self._runner(
            notifications=notifications
        )
        summary = runner.run()
        self.assertEqual(summary.status, "COMPLETE_REQUIRES_ACCEPTANCE")
        self.assertEqual(summary.notifications, 3)
        self.assertEqual(summary.successful_notifications, 2)
        self.assertEqual(summary.failed_notifications, 1)
        self.assertEqual(summary.truncated_notifications, 0)
        self.assertEqual(summary.decoded_events, 2)
        self.assertEqual(summary.create_events, 2)
        self.assertEqual(summary.unique_followup_candidates, 1)
        self.assertEqual(summary.rpc_followups, 1)
        self.assertEqual(summary.solana_tracker_requests, 2)
        self.assertEqual(summary.solana_tracker_failures, 0)
        self.assertEqual(summary.retries, 0)
        self.assertEqual(summary.concurrency, 1)
        self.assertEqual(summary.cash_spend_usd_cents, 0)
        self.assertEqual(summary.wss_stop_reason, "ADAPTER_BOUND")
        self.assertEqual(len(wss.requests), 1)
        self.assertEqual(
            wss.limits,
            [
                (
                    WSS_CAPTURE_SECONDS,
                    (
                        MAX_ADMITTED_RECEIVED_BYTES
                        - len(http.tracker_body)
                        - TRACKER_MAX_RESPONSE_BYTES
                        - 1
                    ),
                    500,
                )
            ],
        )
        self.assertEqual(
            [request.provider for request in http.requests],
            [
                "SOLANA_TRACKER",
                "SOLANA_TRACKER",
                "HELIUS",
            ],
        )
        self.assertEqual(
            [request.method for request in http.requests],
            ["GET", "GET", "POST"],
        )
        self.assertEqual(pacing, [])
        self.assertEqual(summary.evidence_records, len(sink.records))
        self.assertEqual(summary.evidence_records, 7)
        self.assertLessEqual(summary.helius_credits, 41)
        self.assertLessEqual(summary.received_and_stored_bytes, 5_000_000)

    def test_runner_preserves_wss_receive_times_after_buffering(self) -> None:
        notifications = (
            _notification(
                self.event_plan,
                logs=[
                    f"Program {PUMP_PROGRAM_ID} invoke [1]",
                    _event_line(self.event_plan, "TradeEvent"),
                    f"Program {PUMP_PROGRAM_ID} success",
                ],
            ),
            _notification(
                self.event_plan,
                signature=SECOND_SIGNATURE,
                logs=[
                    f"Program {PUMP_PROGRAM_ID} invoke [1]",
                    _event_line(self.event_plan, "TradeEvent"),
                    f"Program {PUMP_PROGRAM_ID} success",
                ],
            ),
        )
        runner, _, wss, _, sink, _ = self._runner(
            notifications=notifications
        )
        summary = runner.run()
        self.assertEqual(summary.status, "NOT_TESTABLE_IN_WINDOW")
        captured_records = [
            record
            for record in sink.records
            if record.kind
            in {"WSS_SUBSCRIPTION_ACK", "WSS_LOGS_NOTIFICATION"}
        ]
        self.assertEqual(
            [record.observed_at for record in captured_records],
            [
                wss.acknowledgement_observed_at,
                *wss.notification_observed_at,
            ],
        )
        self.assertEqual(
            len({record.observed_at for record in captured_records}),
            3,
        )

    def test_no_create_event_is_not_testable_without_retry_or_extension(
        self,
    ) -> None:
        runner, _, _, _, _, _ = self._runner(notifications=())
        summary = runner.run()
        self.assertEqual(summary.status, "NOT_TESTABLE_IN_WINDOW")
        self.assertEqual(summary.create_events, 0)
        self.assertEqual(summary.rpc_followups, 0)
        self.assertEqual(summary.retries, 0)

    def test_runner_retains_truncation_and_continues_without_followup(
        self,
    ) -> None:
        truncated = _notification(
            self.event_plan,
            logs=[
                f"Program {PUMP_PROGRAM_ID} invoke [1]",
                _event_line(self.event_plan),
                "Log truncated",
            ],
        )
        valid_trade = _notification(
            self.event_plan,
            signature=SECOND_SIGNATURE,
            logs=[
                f"Program {PUMP_PROGRAM_ID} invoke [1]",
                _event_line(self.event_plan, "TradeEvent"),
                f"Program {PUMP_PROGRAM_ID} success",
            ],
        )
        runner, _, wss, http, sink, _ = self._runner(
            notifications=(truncated, valid_trade)
        )
        summary = runner.run()
        self.assertEqual(summary.status, "NOT_TESTABLE_IN_WINDOW")
        self.assertEqual(summary.notifications, 2)
        self.assertEqual(summary.successful_notifications, 1)
        self.assertEqual(summary.failed_notifications, 0)
        self.assertEqual(summary.truncated_notifications, 1)
        self.assertEqual(summary.decoded_events, 1)
        self.assertEqual(summary.create_events, 0)
        self.assertEqual(summary.rpc_followups, 0)
        self.assertEqual(len(http.requests), 2)
        truncated_records = [
            record
            for record in sink.records
            if record.error_class == "program_logs_truncated"
        ]
        self.assertEqual(len(truncated_records), 1)
        self.assertEqual(
            truncated_records[0].response_status,
            RawResponseStatus.INVALID_RESPONSE,
        )
        self.assertEqual(
            truncated_records[0].metadata["decoded_event_names"],
            [],
        )
        self.assertTrue(truncated_records[0].metadata["logs_truncated"])
        self.assertEqual(
            truncated_records[0].observed_at,
            wss.notification_observed_at[0],
        )

    def test_invalid_notification_retains_wss_receive_time(self) -> None:
        broken = _notification(
            self.event_plan,
            logs=[f"Program {PUMP_PROGRAM_ID} invoke [1]"],
        )
        runner, _, wss, _, sink, _ = self._runner(
            notifications=(broken,)
        )
        with self.assertRaisesRegex(
            ProgramLogAttributionError,
            "program_invocation_unclosed",
        ):
            runner.run()
        invalid_records = [
            record
            for record in sink.records
            if record.error_class == "program_invocation_unclosed"
        ]
        self.assertEqual(len(invalid_records), 1)
        self.assertEqual(
            invalid_records[0].observed_at,
            wss.notification_observed_at[0],
        )

    def test_notification_and_stream_caps_stop_before_processing(self) -> None:
        notification = _notification(self.event_plan)
        runner, _, _, _, sink, _ = self._runner(
            notifications=(notification,) * 501
        )
        with self.assertRaisesRegex(
            ProbeStopError,
            "probe_notifications_exceeded",
        ):
            runner.run()
        self.assertEqual(len(sink.records), 1)

        huge = b" " * 1_000_001
        clock = _Clock()
        wss = _MockWss(
            clock=clock,
            notifications=(),
            acknowledgement=huge,
        )
        http = _MockHttp(clock=clock)
        sink = InMemoryEvidenceSink()
        runner = ProbeTransportRunner(
            plan=self.plan,
            event_plan=self.event_plan,
            credentials=_credentials(),
            access=_access(),
            gate=ExternalExecutionGate(EXTERNAL_AUTHORITY_PHRASE),
            wss_exchange=wss,
            http_exchange=http,
            evidence_sink=sink,
            clock=clock,
            pace=clock.advance,
        )
        with self.assertRaisesRegex(
            ProbeStopError,
            "probe_stream_bytes_exceeded",
        ):
            runner.run()

    def test_more_than_twenty_unique_candidates_stops_without_followups(
        self,
    ) -> None:
        notifications = tuple(
            _notification(
                self.event_plan,
                signature=character * 88,
            )
            for character in "23456789ABCDEFGHJKLMN"
        )
        self.assertEqual(len(notifications), 21)
        runner, _, _, http, _, _ = self._runner(
            notifications=notifications
        )
        with self.assertRaisesRegex(
            ProbeStopError,
            "rpc_followup_candidate_cap_exceeded",
        ):
            runner.run()
        self.assertEqual(len(http.requests), 1)

    def test_redirect_non_200_and_elapsed_cap_stop(self) -> None:
        runner, _, wss, http, sink, _ = self._runner(notifications=())
        http.redirect = True
        summary = runner.run()
        self.assertEqual(summary.solana_tracker_failures, 2)
        self.assertEqual(len(wss.requests), 1)
        self.assertEqual(len(sink.records), 3)

        runner, _, _, http, sink, _ = self._runner(notifications=())
        http.status_code = 429
        summary = runner.run()
        self.assertEqual(summary.solana_tracker_failures, 2)
        self.assertEqual(len(sink.records), 3)

        runner, _, _, http, _, _ = self._runner(
            notifications=(_notification(self.event_plan),)
        )
        http.redirect = True
        with self.assertRaisesRegex(
            ProbeStopError,
            "http_redirect_or_target_drift",
        ):
            runner.run()

        runner, _, _, http, sink, _ = self._runner(
            notifications=(_notification(self.event_plan),)
        )
        http.status_code = 429
        with self.assertRaisesRegex(
            ProbeStopError,
            "http_status_not_success:429",
        ):
            runner.run()
        self.assertEqual(len(sink.records), 5)

        runner, _, _, _, _, _ = self._runner(
            notifications=(),
            advance_seconds=601,
        )
        with self.assertRaisesRegex(
            ProbeStopError,
            "probe_elapsed_seconds_exceeded",
        ):
            runner.run()

    def test_get_transaction_schema_drift_stops_after_raw_retention(self) -> None:
        runner, _, _, http, sink, _ = self._runner(
            notifications=(_notification(self.event_plan),)
        )
        http.override_body = b'{"jsonrpc":"2.0","id":"wrong","result":{}}'
        with self.assertRaises(ProbeStopError):
            runner.run()
        self.assertGreaterEqual(len(sink.records), 1)

    def test_evidence_sink_accounting_and_metadata_fail_closed(self) -> None:
        evidence = ProbeEvidence(
            provider="HELIUS",
            kind="TEST",
            body=b"raw-sensitive-payload",
            observed_at=datetime(2026, 7, 25, tzinfo=UTC),
            metadata={"status": "SAFE"},
        )
        self.assertNotIn("raw-sensitive-payload", repr(evidence))
        with self.assertRaises(ProbeTransportContractError):
            ProbeEvidence(
                provider="HELIUS",
                kind="TEST",
                body=b"body",
                observed_at=datetime(2026, 7, 25, tzinfo=UTC),
                metadata={"url": "https://example.invalid"},
            )
        with self.assertRaises(ProbeTransportContractError):
            ProbeEvidence(
                provider="HELIUS",
                kind="TEST",
                body=b"body",
                observed_at=datetime(2026, 7, 25, tzinfo=UTC),
                metadata={"location": r"C:\Users\operator\raw"},
            )

        class InvalidSink:
            def __call__(self, _: ProbeEvidence) -> int:
                return -1

            def finalize(self, *, max_stored_bytes: int) -> int:
                return 0

        runner, _, _, _, _, _ = self._runner(
            notifications=(),
            sink=InvalidSink(),
        )
        with self.assertRaisesRegex(
            ProbeStopError,
            "evidence_sink_byte_count_invalid",
        ):
            runner.run()

    def test_atom4_offline_boundary_blocks_every_side_effect_class(self) -> None:
        assert_atom4_offline_boundary()
        for name in (
            "network_requested",
            "credential_use_requested",
            "local_data_write_requested",
            "dependency_change_requested",
        ):
            with self.subTest(name=name):
                with self.assertRaises(ExternalAuthorityRequiredError):
                    assert_atom4_offline_boundary(**{name: True})

    def test_concrete_http_adapter_is_no_redirect_bounded_and_no_retry(
        self,
    ) -> None:
        request = bind_tracker_snapshot(
            _credentials(),
            phase="OPEN",
        )

        class Response:
            status = 200

            def __enter__(self) -> Response:
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def read(self, maximum: int) -> bytes:
                return b"[]"[:maximum]

            def geturl(self) -> str:
                return request.url

        opener = mock.Mock()
        opener.open.return_value = Response()
        with mock.patch(
            "urllib.request.build_opener",
            return_value=opener,
        ) as build:
            capture = stdlib_http_exchange(
                request,
                max_response_bytes=100,
            )
        self.assertEqual(capture.body, b"[]")
        self.assertEqual(capture.terminal_class, "SUCCESS")
        self.assertEqual(opener.open.call_count, 1)
        self.assertEqual(
            opener.open.call_args.kwargs["timeout"],
            DEFAULT_HTTP_TIMEOUT_SECONDS,
        )
        self.assertEqual(build.call_count, 1)

        class OversizeResponse(Response):
            def read(self, maximum: int) -> bytes:
                return b"x" * maximum

        opener.open.return_value = OversizeResponse()
        with mock.patch("urllib.request.build_opener", return_value=opener):
            capture = stdlib_http_exchange(
                request,
                max_response_bytes=3,
            )
        self.assertEqual(capture.terminal_class, "RESPONSE_TOO_LARGE")
        self.assertEqual(capture.body, b"")
        self.assertEqual(capture.received_bytes, 4)

    def test_concrete_wss_adapter_closes_and_enforces_runtime_options(
        self,
    ) -> None:
        request = bind_logs_subscribe(_credentials())

        class Socket:
            def __init__(self) -> None:
                self.frames = [_ack(), b"{}"]
                self.closed = False
                self.sent: list[str] = []

            def send(self, value: str) -> None:
                self.sent.append(value)

            def recv(self, *, timeout: float) -> bytes:
                if self.frames:
                    return self.frames.pop(0)
                raise TimeoutError

            def close(self) -> None:
                self.closed = True

        socket = Socket()
        with mock.patch(
            "websockets.sync.client.connect",
            return_value=socket,
        ) as connect:
            capture = websockets_wss_exchange(
                request,
                max_open_seconds=WSS_CAPTURE_SECONDS,
                max_stream_bytes=1_000_000,
                max_notifications=500,
            )
        self.assertEqual(capture.terminal_class, "BOUND_REACHED")
        self.assertEqual(capture.stop_reason, "ELAPSED_CAP")
        self.assertIsNotNone(capture.acknowledgement_observed_at)
        self.assertEqual(len(capture.notification_observed_at), 1)
        assert capture.acknowledgement_observed_at is not None
        self.assertLessEqual(
            capture.acknowledgement_observed_at,
            capture.notification_observed_at[0],
        )
        self.assertEqual(
            capture.notification_observed_at[0].utcoffset(),
            timedelta(0),
        )
        self.assertTrue(socket.closed)
        self.assertEqual(len(socket.sent), 1)
        options = connect.call_args.kwargs
        self.assertIsNone(options["proxy"])
        self.assertIsNone(options["compression"])
        self.assertEqual(options["max_queue"], 1)
        self.assertEqual(options["max_size"], 100_000)

        oversize_socket = Socket()
        oversize_socket.frames = [b"x" * 100_001]
        with mock.patch(
            "websockets.sync.client.connect",
            return_value=oversize_socket,
        ):
            oversize = websockets_wss_exchange(
                request,
                max_open_seconds=WSS_CAPTURE_SECONDS,
                max_stream_bytes=1_000_000,
                max_notifications=500,
            )
        self.assertEqual(oversize.terminal_class, "RESPONSE_TOO_LARGE")
        self.assertEqual(oversize.stop_reason, "FRAME_LIMIT")
        self.assertEqual(oversize.acknowledgement, b"")
        self.assertIsNone(oversize.acknowledgement_observed_at)

    def test_durable_sink_writes_one_verified_partition_and_safe_receipts(
        self,
    ) -> None:
        credentials = _credentials()
        with tempfile.TemporaryDirectory() as directory:
            raw_root = Path(directory).resolve()
            sink = DurableProbeSink(
                raw_root=raw_root,
                run_id="t08a5-20260725T120000Z",
                credentials=credentials,
            )
            runner, _, wss, _, _, _ = self._runner(
                notifications=(_notification(self.event_plan),),
                sink=sink,
            )
            result = runner.run()
            self.assertEqual(
                result.status,
                "COMPLETE_REQUIRES_ACCEPTANCE",
            )
            run_directory = (
                raw_root
                / RAW_LOGICAL_ROOT
                / "run=t08a5-20260725T120000Z"
            )
            files = sorted(
                path.relative_to(run_directory).as_posix()
                for path in run_directory.rglob("*")
                if path.is_file()
            )
            self.assertEqual(
                files,
                [
                    "partitions/probe.parquet",
                    "receipts/probe.manifest.json",
                    "receipts/probe.receipt.json",
                ],
            )
            manifest = PartitionManifest.model_validate_json(
                (
                    run_directory / "receipts" / "probe.manifest.json"
                ).read_bytes()
            )
            events = verify_raw_event_partition(
                root=run_directory,
                manifest=manifest,
            )
            self.assertEqual(len(events), result.evidence_records)
            acknowledgement_events = []
            notification_events = []
            for event in events:
                try:
                    document = json.loads(event.redacted_body)
                except json.JSONDecodeError:
                    continue
                if (
                    isinstance(document, dict)
                    and document.get("id") == LOGS_SUBSCRIBE_REQUEST_ID
                    and "result" in document
                ):
                    acknowledgement_events.append(event)
                if (
                    isinstance(document, dict)
                    and document.get("method") == "logsNotification"
                ):
                    notification_events.append(event)
            self.assertEqual(len(acknowledgement_events), 1)
            self.assertEqual(len(notification_events), 1)
            self.assertEqual(
                acknowledgement_events[0].observed_at,
                wss.acknowledgement_observed_at,
            )
            self.assertEqual(
                notification_events[0].observed_at,
                wss.notification_observed_at[0],
            )
            receipt = json.loads(
                (
                    run_directory / "receipts" / "probe.receipt.json"
                ).read_bytes()
            )
            self.assertEqual(receipt["dataset_id"], DATASET_ID)
            self.assertEqual(
                receipt["event_count_received"],
                len(events),
            )
            self.assertEqual(
                receipt["event_count_stored"],
                len(events),
            )
            self.assertTrue(receipt["complete"])
            all_bytes = b"".join(
                path.read_bytes()
                for path in run_directory.rglob("*")
                if path.is_file()
            )
            self.assertNotIn(
                credentials.helius_api_key.encode(),
                all_bytes,
            )
            self.assertNotIn(
                credentials.solana_tracker_api_key.encode(),
                all_bytes,
            )
            stored_bytes = sum(
                path.stat().st_size
                for path in run_directory.rglob("*")
                if path.is_file()
            )
            self.assertEqual(
                stored_bytes,
                sink.safe_receipt()["stored_bytes"],
            )
            self.assertLessEqual(
                result.received_and_stored_bytes,
                5_000_000,
            )
            self.assertNotIn(str(raw_root), json.dumps(sink.safe_receipt()))

    def test_durable_sink_retains_explicit_prefix_when_full_set_exceeds_cap(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            sink = DurableProbeSink(
                raw_root=Path(directory).resolve(),
                run_id="t08a5-20260725T120002Z",
                credentials=_credentials(),
            )
            for index in range(10):
                sink(
                    ProbeEvidence(
                        provider="HELIUS",
                        kind="SYNTHETIC_STORAGE_PRESSURE",
                        body=bytes([65 + index]) * 100_000,
                        observed_at=datetime(
                            2026,
                            7,
                            25,
                            12,
                            0,
                            index,
                            tzinfo=UTC,
                        ),
                        metadata={
                            "ordinal": index,
                            "request": {
                                "method": "POST",
                                "path": "/",
                            },
                        },
                    )
                )
            stored_bytes = sink.finalize(max_stored_bytes=300_000)
            self.assertFalse(sink.complete)
            self.assertTrue(sink.safe_receipt()["finalized"])
            self.assertGreater(stored_bytes, 0)
            self.assertLessEqual(stored_bytes, 300_000)
            manifest = PartitionManifest.model_validate_json(
                (
                    sink.run_directory
                    / "receipts"
                    / "probe.manifest.json"
                ).read_bytes()
            )
            events = verify_raw_event_partition(
                root=sink.run_directory,
                manifest=manifest,
            )
            self.assertGreater(len(events), 0)
            self.assertLess(len(events), 10)
            receipt = json.loads(
                (
                    sink.run_directory
                    / "receipts"
                    / "probe.receipt.json"
                ).read_bytes()
            )
            self.assertFalse(receipt["complete"])
            self.assertEqual(receipt["event_count_received"], 10)
            self.assertEqual(
                receipt["event_count_stored"],
                len(events),
            )
            self.assertEqual(
                receipt["omitted_event_count"],
                10 - len(events),
            )
            self.assertIn(
                receipt["finalize_error_class"],
                {
                    "partition_byte_budget_exceeded",
                    "dataset_byte_budget_exceeded",
                },
            )

    def test_admission_proof_fits_max_rows_with_expanding_redaction(
        self,
    ) -> None:
        proof = admission_budget_proof()
        self.assertEqual(
            proof["worst_case_combined_bytes"],
            4_812_416,
        )
        self.assertEqual(proof["remaining_safety_bytes"], 187_584)
        base, remainder = divmod(
            MAX_ADMITTED_RECEIVED_BYTES,
            MAX_EVIDENCE_RECORDS,
        )
        with tempfile.TemporaryDirectory() as directory:
            sink = DurableProbeSink(
                raw_root=Path(directory).resolve(),
                run_id="t08a5-20260725T120003Z",
                credentials=_credentials(),
            )
            received = 0
            started = datetime(2026, 7, 25, 12, tzinfo=UTC)
            pattern = b"token:a "
            for index in range(MAX_EVIDENCE_RECORDS):
                body_size = base + int(index < remainder)
                body = (pattern * ((body_size // len(pattern)) + 1))[
                    :body_size
                ]
                received += len(body)
                sink(
                    ProbeEvidence(
                        provider="HELIUS",
                        kind="ADMISSION_BOUND_PROOF",
                        body=body,
                        observed_at=started + timedelta(microseconds=index),
                        metadata={
                            "ordinal": index,
                            "request": {
                                "method": "POST",
                                "path": "/",
                            },
                        },
                    )
                )
            self.assertEqual(received, MAX_ADMITTED_RECEIVED_BYTES)
            stored = sink.finalize(
                max_stored_bytes=5_000_000 - received
            )
            self.assertTrue(sink.complete)
            self.assertEqual(
                sink.safe_receipt()["stored_event_count"],
                MAX_EVIDENCE_RECORDS,
            )
            self.assertLessEqual(received + stored, 5_000_000)

    def test_oversize_tracker_is_retained_without_blocking_wss(
        self,
    ) -> None:
        runner, _, wss, http, sink, _ = self._runner(notifications=())
        http.override_body = b"x" * (TRACKER_MAX_RESPONSE_BYTES + 1)
        summary = runner.run()
        self.assertEqual(summary.status, "NOT_TESTABLE_IN_WINDOW")
        self.assertEqual(summary.solana_tracker_requests, 2)
        self.assertEqual(summary.solana_tracker_failures, 2)
        self.assertEqual(len(wss.requests), 1)
        self.assertEqual(len(http.requests), 2)
        self.assertEqual(len(sink.records), 3)
        self.assertEqual(sink.records[0].body, b"")
        self.assertEqual(
            sink.records[0].response_status,
            RawResponseStatus.INVALID_RESPONSE,
        )
        self.assertEqual(
            sink.records[2].response_status,
            RawResponseStatus.INVALID_RESPONSE,
        )
        self.assertLessEqual(
            summary.received_bytes,
            MAX_ADMITTED_RECEIVED_BYTES,
        )

    def test_tracker_limit_drift_is_retained_without_blocking_wss(
        self,
    ) -> None:
        runner, _, wss, http, sink, _ = self._runner(notifications=())
        http.tracker_body = json.dumps(
            {
                "graduated": [],
                "graduating": [],
                "latest": [{}] * (TRACKER_OVERVIEW_LIMIT + 1),
            },
            separators=(",", ":"),
        ).encode("utf-8")
        summary = runner.run()
        self.assertEqual(summary.status, "NOT_TESTABLE_IN_WINDOW")
        self.assertEqual(summary.solana_tracker_failures, 2)
        self.assertEqual(len(wss.requests), 1)
        self.assertEqual(len(sink.records), 3)
        self.assertEqual(
            sink.records[0].error_class,
            "tracker_latest_limit_exceeded",
        )
        self.assertEqual(
            sink.records[2].error_class,
            "tracker_latest_limit_exceeded",
        )

    def test_typed_partial_wss_failure_is_finalized_before_stop(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            sink = DurableProbeSink(
                raw_root=Path(directory).resolve(),
                run_id="t08a5-20260725T120001Z",
                credentials=_credentials(),
            )
            runner, _, _, _, _, _ = self._runner(
                notifications=(),
                sink=sink,
                terminal_class="REMOTE_CLOSED",
                error_class="wss_remote_closed",
                stop_reason="REMOTE_CLOSED",
            )
            with self.assertRaisesRegex(
                ProbeStopError,
                "wss_remote_closed",
            ):
                runner.run()
            self.assertTrue(sink.safe_receipt()["finalized"])
            manifest = PartitionManifest.model_validate_json(
                (
                    sink.run_directory
                    / "receipts"
                    / "probe.manifest.json"
                ).read_bytes()
            )
            events = verify_raw_event_partition(
                root=sink.run_directory,
                manifest=manifest,
            )
            failures = [
                event
                for event in events
                if event.error_class == "wss_remote_closed"
            ]
            self.assertEqual(len(failures), 1)
            self.assertEqual(
                failures[0].response_status,
                RawResponseStatus.PROVIDER_ERROR,
            )

    def test_launcher_default_offline_and_execute_uses_injected_runtime(
        self,
    ) -> None:
        spec = importlib.util.spec_from_file_location(
            "task08_probe_launcher",
            LAUNCHER_PATH,
        )
        self.assertIsNotNone(spec)
        assert spec is not None and spec.loader is not None
        launcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(launcher)

        prompts: list[str] = []

        def prompt(value: str) -> str:
            prompts.append(value)
            return "wrong"

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = launcher.main([], input_fn=prompt)
        self.assertEqual(code, 0)
        self.assertEqual(prompts, [])
        self.assertIn("TASK08_PROBE_PREFLIGHT: PASS", output.getvalue())
        self.assertIn(
            "EXTERNAL_EXECUTION: BLOCKED_UNLESS_EXPLICIT_EXECUTE",
            output.getvalue(),
        )

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = launcher.main(["--execute"], input_fn=prompt)
        self.assertEqual(code, 2)
        self.assertEqual(len(prompts), 1)
        self.assertIn("BLOCKED_PREFLIGHT", output.getvalue())
        self.assertIn(
            "external_authority_phrase_mismatch",
            output.getvalue(),
        )

        output = io.StringIO()
        values = iter([EXTERNAL_AUTHORITY_PHRASE, "41", "8"])
        secrets: list[str] = []

        def secret_prompt(prompt_text: str) -> str:
            secrets.append(prompt_text)
            return (
                "unit-" + ("h" * 20)
                if len(secrets) == 1
                else "unit-" + ("t" * 20)
            )

        clock = _Clock()
        wss = _MockWss(clock=clock, notifications=())
        http = _MockHttp(clock=clock)
        with tempfile.TemporaryDirectory() as directory:
            with contextlib.redirect_stdout(output):
                code = launcher.main(
                    ["--execute"],
                    input_fn=lambda _: next(values),
                    secret_input_fn=secret_prompt,
                    wss_exchange=wss,
                    http_exchange=http,
                    clock=clock,
                    pace=clock.advance,
                    now=lambda: datetime(2026, 7, 25, 12, tzinfo=UTC),
                    raw_root=Path(directory),
                )
        self.assertEqual(code, 0)
        self.assertEqual(len(secrets), 2)
        self.assertIn(
            "CAPTURE_COMPLETE_REQUIRES_WORK_ACCEPTANCE",
            output.getvalue(),
        )
        self.assertNotIn("unit-", output.getvalue())

    def test_launcher_prints_sanitized_usage_on_controlled_stop(
        self,
    ) -> None:
        spec = importlib.util.spec_from_file_location(
            "task08_probe_launcher_stopped",
            LAUNCHER_PATH,
        )
        self.assertIsNotNone(spec)
        assert spec is not None and spec.loader is not None
        launcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(launcher)

        broken = _notification(
            self.event_plan,
            logs=[f"Program {PUMP_PROGRAM_ID} invoke [1]"],
        )
        clock = _Clock()
        wss = _MockWss(clock=clock, notifications=(broken,))
        http = _MockHttp(clock=clock)
        values = iter([EXTERNAL_AUTHORITY_PHRASE, "41", "8"])
        secret_values = iter(
            ["unit-" + ("h" * 20), "unit-" + ("t" * 20)]
        )
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            with contextlib.redirect_stdout(output):
                code = launcher.main(
                    ["--execute"],
                    input_fn=lambda _: next(values),
                    secret_input_fn=lambda _: next(secret_values),
                    wss_exchange=wss,
                    http_exchange=http,
                    clock=clock,
                    pace=clock.advance,
                    now=lambda: datetime(2026, 7, 25, 12, tzinfo=UTC),
                    raw_root=Path(directory),
                )
        text = output.getvalue()
        self.assertEqual(code, 3)
        self.assertIn("SAFE_USAGE_RECEIPT:", text)
        self.assertIn("DURABLE_SINK_RECEIPT:", text)
        documents = [
            json.loads(line)
            for line in text.splitlines()
            if line.startswith("{")
        ]
        usage = next(
            item
            for item in documents
            if item.get("receipt_type") == "CONTROLLED_STOP_USAGE"
        )
        self.assertEqual(
            usage["stop_error_class"],
            "program_invocation_unclosed",
        )
        self.assertEqual(usage["wss_captured_notifications"], 1)
        self.assertEqual(
            usage["wss_captured_bytes"],
            len(_ack()) + len(broken),
        )
        self.assertEqual(
            usage["network_received_bytes"],
            len(http.tracker_body) + len(_ack()) + len(broken),
        )
        self.assertEqual(usage["helius_credits"], 3)
        self.assertEqual(usage["retries"], 0)
        self.assertEqual(usage["cash_spend_usd_cents"], 0)
        self.assertNotIn("unit-", text)

    def test_atom5_files_bind_only_locked_transports_and_task06_sink(self) -> None:
        module_text = MODULE_PATH.read_text(encoding="utf-8")
        launcher_text = LAUNCHER_PATH.read_text(encoding="utf-8")
        contract_text = CONTRACT_PATH.read_text(encoding="utf-8")
        self.assertIn("import urllib.request", module_text)
        self.assertIn("from websockets", module_text)
        self.assertNotIn("import requests", module_text)
        self.assertNotIn("import httpx", module_text)
        self.assertIn('ROOT / "data" / "raw"', launcher_text)
        self.assertIn("getpass.getpass", launcher_text)
        self.assertIn("T08-A5", contract_text)
        self.assertIn("TASK-06-compatible", contract_text)
        self.assertIn("two planned", contract_text)


if __name__ == "__main__":
    unittest.main()
