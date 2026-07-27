from __future__ import annotations

import base64
import json
import struct
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.pumpswap_touch_decoder import (  # noqa: E402
    PROGRAM_DATA_PREFIX,
    PUMPSWAP_PROGRAM_ID,
    FieldSpec,
    LayoutSchema,
    load_pinned_pumpswap_plan,
)
from solana_alpha_lab.pumpswap_touch_probe import (  # noqa: E402
    ELAPSED_SECONDS_CAP,
    EXTERNAL_AUTHORITY_PHRASE,
    GET_TRANSACTION_CAP,
    LOGS_SUBSCRIBE_REQUEST_ID,
    MAX_ADMITTED_RECEIVED_BYTES,
    MODELED_HELIUS_CREDITS_MAX,
    NOTIFICATION_CAP,
    RECEIVED_AND_STORED_BYTES_CAP,
    STREAM_BYTES_CAP,
    WSS_CAPTURE_SECONDS,
    DurableTouchProbeSink,
    ExternalAuthorityRequiredError,
    ExternalExecutionGate,
    HttpCapture,
    TouchProbeRunner,
    WssCapture,
    bind_get_transaction,
    bind_logs_subscribe,
    parse_logs_notification,
    parse_subscription_ack,
    safe_preflight_summary,
    validate_get_transaction_response,
)

FIXTURE = (
    ROOT / "tests" / "fixtures" / "task09" / "pumpswap_idl_subset_v1.json"
)
SCRIPT = ROOT / "scripts" / "run_task09_pumpswap_touch_probe.py"
MODULE = SRC / "solana_alpha_lab" / "pumpswap_touch_probe.py"


def _sample_value(field: FieldSpec, seed: int) -> object:
    if field.type_spec == "bool":
        return seed % 2 == 0
    if field.type_spec == "i64":
        return 1_720_000_000 + seed
    if field.type_spec == "i128":
        return 500 + seed
    if field.type_spec == "pubkey":
        return bytes([(seed % 250) + 1]) * 32
    if field.type_spec == "string":
        return "buy"
    if field.type_spec == "u8":
        return seed + 1
    if field.type_spec == "u16":
        return 100 + seed
    if field.type_spec == "u64":
        return 1_000 + seed
    raise AssertionError(field.type_spec)


def _encode_type(type_spec: str, value: object) -> bytes:
    if type_spec == "bool":
        return bytes([int(value)])
    if type_spec == "i64":
        return struct.pack("<q", int(value))
    if type_spec == "i128":
        return int(value).to_bytes(16, "little", signed=True)
    if type_spec == "pubkey":
        assert isinstance(value, bytes)
        return value
    if type_spec == "string":
        encoded = str(value).encode()
        return struct.pack("<I", len(encoded)) + encoded
    if type_spec == "u8":
        return struct.pack("<B", int(value))
    if type_spec == "u16":
        return struct.pack("<H", int(value))
    if type_spec == "u64":
        return struct.pack("<Q", int(value))
    raise AssertionError(type_spec)


def _payload(schema: LayoutSchema) -> bytes:
    return schema.discriminator + b"".join(
        _encode_type(field.type_spec, _sample_value(field, index))
        for index, field in enumerate(schema.fields)
    )


def _notification(
    *,
    subscription_id: int,
    logs: list[str],
    succeeded: bool = True,
    slot: int = 123,
    signature: str = "1" * 64,
) -> bytes:
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "method": "logsNotification",
            "params": {
                "result": {
                    "context": {"slot": slot},
                    "value": {
                        "err": None if succeeded else {"InstructionError": [0, 1]},
                        "logs": logs,
                        "signature": signature,
                    },
                },
                "subscription": subscription_id,
            },
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


class Task09PumpSwapTouchProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = load_pinned_pumpswap_plan(FIXTURE)
        cls.now = datetime(2026, 7, 27, 12, 0, tzinfo=UTC)
        cls.ack = json.dumps(
            {
                "id": LOGS_SUBSCRIBE_REQUEST_ID,
                "jsonrpc": "2.0",
                "result": 77,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        event_line = PROGRAM_DATA_PREFIX + base64.b64encode(
            _payload(cls.plan.events[0])
        ).decode()
        cls.touch = _notification(
            subscription_id=77,
            logs=[
                f"Program {PUMPSWAP_PROGRAM_ID} invoke [1]",
                event_line,
                f"Program {PUMPSWAP_PROGRAM_ID} success",
            ],
        )

    def test_preflight_freezes_caps_and_is_offline(self) -> None:
        summary = safe_preflight_summary(self.plan)
        self.assertEqual(summary["elapsed_seconds_cap"], ELAPSED_SECONDS_CAP)
        self.assertEqual(summary["wss_capture_seconds"], WSS_CAPTURE_SECONDS)
        self.assertEqual(summary["notification_cap"], NOTIFICATION_CAP)
        self.assertEqual(summary["stream_bytes_cap"], STREAM_BYTES_CAP)
        self.assertEqual(summary["get_transaction_cap"], GET_TRANSACTION_CAP)
        self.assertEqual(
            summary["modeled_helius_credits_max"],
            MODELED_HELIUS_CREDITS_MAX,
        )
        self.assertEqual(
            summary["received_and_stored_bytes_cap"],
            RECEIVED_AND_STORED_BYTES_CAP,
        )
        self.assertLess(MAX_ADMITTED_RECEIVED_BYTES, STREAM_BYTES_CAP)
        self.assertFalse(summary["network_authorized"])
        self.assertFalse(summary["durable_output_created"])
        self.assertFalse(summary["credentials_required"])

    def test_exact_gate_and_allowlisted_requests(self) -> None:
        with self.assertRaises(ExternalAuthorityRequiredError):
            ExternalExecutionGate("").require()
        ExternalExecutionGate(EXTERNAL_AUTHORITY_PHRASE).require()
        request = bind_logs_subscribe()
        body = json.loads(request.body)
        self.assertEqual(
            body["params"][0]["mentions"],
            [PUMPSWAP_PROGRAM_ID],
        )
        self.assertEqual(body["params"][1], {"commitment": "confirmed"})
        self.assertNotIn("api-key", repr(request))
        followup = bind_get_transaction("1" * 64, 1)
        self.assertEqual(json.loads(followup.body)["method"], "getTransaction")
        self.assertNotIn("send", followup.body.decode().casefold())

    def test_ack_and_attributed_touch_decode_fail_closed(self) -> None:
        self.assertEqual(parse_subscription_ack(self.ack), 77)
        parsed = parse_logs_notification(
            self.touch,
            expected_subscription_id=77,
            plan=self.plan,
        )
        self.assertTrue(parsed.transaction_succeeded)
        self.assertEqual(len(parsed.decoded_events), 1)
        self.assertEqual(parsed.decoded_events[0].event_name, "BuyEvent")

        failed = _notification(
            subscription_id=77,
            succeeded=False,
            logs=[
                f"Program {PUMPSWAP_PROGRAM_ID} invoke [1]",
                PROGRAM_DATA_PREFIX
                + base64.b64encode(_payload(self.plan.events[0])).decode(),
                f"Program {PUMPSWAP_PROGRAM_ID} failed: synthetic",
            ],
        )
        self.assertFalse(
            parse_logs_notification(
                failed,
                expected_subscription_id=77,
                plan=self.plan,
            ).decoded_events
        )

    def test_get_transaction_result_preserves_gap_and_provider_failure(self) -> None:
        present = json.dumps(
            {
                "id": "x",
                "jsonrpc": "2.0",
                "result": {
                    "blockTime": 1_720_000_000,
                    "meta": {
                        "err": None,
                        "loadedAddresses": {
                            "readonly": [],
                            "writable": [],
                        },
                        "logMessages": [],
                        "postTokenBalances": [],
                        "preTokenBalances": [],
                    },
                    "slot": 1,
                    "transaction": {
                        "message": {
                            "accountKeys": [PUMPSWAP_PROGRAM_ID],
                            "instructions": [],
                        },
                        "signatures": ["1" * 64],
                    },
                    "version": 0,
                },
            }
        ).encode()
        missing = json.dumps(
            {"id": "x", "jsonrpc": "2.0", "result": None}
        ).encode()
        error = json.dumps(
            {
                "error": {"code": -32000, "message": "synthetic"},
                "id": "x",
                "jsonrpc": "2.0",
            }
        ).encode()
        self.assertEqual(
            validate_get_transaction_response(
                present,
                request_id="x",
            )["terminal"],
            "FIELD_COVERAGE_CANDIDATE",
        )
        self.assertEqual(
            validate_get_transaction_response(
                missing,
                request_id="x",
            )["terminal"],
            "FIELD_COVERAGE_GAP_OBSERVED",
        )
        self.assertEqual(
            validate_get_transaction_response(
                error,
                request_id="x",
            )["terminal"],
            "TYPED_PROVIDER_FAILURE",
        )

    def test_fake_transport_runner_writes_bounded_raw_evidence(self) -> None:
        def wss_exchange(request, **limits):
            self.assertEqual(limits["max_open_seconds"], WSS_CAPTURE_SECONDS)
            self.assertEqual(limits["max_notifications"], NOTIFICATION_CAP)
            self.assertEqual(
                limits["max_stream_bytes"],
                MAX_ADMITTED_RECEIVED_BYTES,
            )
            return WssCapture(
                acknowledgement=self.ack,
                notifications=(self.touch,),
                acknowledgement_observed_at=self.now,
                notification_observed_at=(self.now + timedelta(seconds=1),),
                terminal_class="BOUND_REACHED",
                error_class=None,
                stop_reason="ELAPSED_CAP",
            )

        def http_exchange(request, **limits):
            self.assertLessEqual(
                limits["max_response_bytes"],
                128_000,
            )
            body = json.dumps(
                {
                    "id": request.request_id,
                    "jsonrpc": "2.0",
                    "result": {
                        "blockTime": 1_720_000_000,
                        "meta": {
                            "err": None,
                            "loadedAddresses": {
                                "readonly": [],
                                "writable": [],
                            },
                            "logMessages": [],
                            "postTokenBalances": [],
                            "preTokenBalances": [],
                        },
                        "slot": 123,
                        "transaction": {
                            "message": {
                                "accountKeys": [PUMPSWAP_PROGRAM_ID],
                                "instructions": [],
                            },
                            "signatures": ["1" * 64],
                        },
                        "version": 0,
                    },
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            return HttpCapture(
                status_code=200,
                body=body,
                terminal_class="SUCCESS",
                error_class=None,
                received_bytes=len(body),
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            sink = DurableTouchProbeSink(raw_root=root, run_id="synthetic")
            runner = TouchProbeRunner(
                plan=self.plan,
                gate=ExternalExecutionGate(EXTERNAL_AUTHORITY_PHRASE),
                sink=sink,
                wss_exchange=wss_exchange,
                http_exchange=http_exchange,
                now=lambda: self.now + timedelta(seconds=2),
                clock=lambda: 0.0,
            )
            result = runner.run()
            self.assertEqual(result.status, "FIELD_COVERAGE_CANDIDATE")
            self.assertEqual(result.decoded_events, 1)
            self.assertEqual(result.rpc_followups, 1)
            self.assertLessEqual(
                result.received_bytes + result.stored_bytes,
                RECEIVED_AND_STORED_BYTES_CAP,
            )
            self.assertTrue(sink.safe_receipt()["complete"])
            self.assertTrue(
                (
                    root
                    / "task09_pumpswap_touch_probe_v1"
                    / "run=synthetic"
                    / "partitions"
                    / "probe.parquet"
                ).is_file()
            )

    def test_no_event_window_is_explicit_not_zero_or_no_route(self) -> None:
        empty = _notification(
            subscription_id=77,
            logs=[
                f"Program {PUMPSWAP_PROGRAM_ID} invoke [1]",
                f"Program {PUMPSWAP_PROGRAM_ID} success",
            ],
        )

        def wss_exchange(request, **limits):
            return WssCapture(
                acknowledgement=self.ack,
                notifications=(empty,),
                acknowledgement_observed_at=self.now,
                notification_observed_at=(self.now,),
                terminal_class="BOUND_REACHED",
                error_class=None,
                stop_reason="ELAPSED_CAP",
            )

        def forbidden_http(request, **limits):
            raise AssertionError("unexpected_followup")

        with tempfile.TemporaryDirectory() as directory:
            sink = DurableTouchProbeSink(
                raw_root=Path(directory).resolve(),
                run_id="no-event",
            )
            result = TouchProbeRunner(
                plan=self.plan,
                gate=ExternalExecutionGate(EXTERNAL_AUTHORITY_PHRASE),
                sink=sink,
                wss_exchange=wss_exchange,
                http_exchange=forbidden_http,
                now=lambda: self.now,
                clock=lambda: 0.0,
            ).run()
        self.assertEqual(result.status, "NOT_TESTABLE_IN_WINDOW")
        self.assertNotIn("NO_ROUTE", json.dumps(result.safe_receipt()))

    def test_launcher_defaults_offline_and_has_no_secret_surface(self) -> None:
        script = SCRIPT.read_text(encoding="utf-8")
        module = MODULE.read_text(encoding="utf-8")
        self.assertIn("BLOCKED_UNLESS_EXPLICIT_EXECUTE", script)
        for marker in (
            "getpass",
            "os.environ",
            "getenv(",
            "api_key",
            "Keypair",
            "sendTransaction",
            "simulateTransaction",
        ):
            self.assertNotIn(marker, script)
            self.assertNotIn(marker, module)


if __name__ == "__main__":
    unittest.main()
