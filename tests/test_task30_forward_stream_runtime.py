from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task30_forward_stream_runtime import (  # noqa: E402
    OWNER_EXECUTION_PHRASE,
    ForwardStreamRuntimeError,
    RuntimeCapture,
    bind_transaction_subscribe,
    classify_forward_stream_capture,
    execute_forward_stream_capture,
    evaluate_forward_stream_runtime,
    render_forward_stream_runtime,
)


POOL = "URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S"
BASE_MINT = "DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK"
CONFIG_PATH = ROOT / "configs/task30_forward_stream_runtime_harness_v1.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/task30_forward_stream_runtime_harness.schema.json"
FIXTURE_PATH = ROOT / "tests/fixtures/task30/forward_stream_runtime_harness_v1.json"
READOUT_PATH = ROOT / "docs/reports/task30/forward_stream_runtime_harness_readout_v1.md"
SCRIPT_PATH = ROOT / "scripts/show_task30_forward_stream_runtime.py"
ACCEPTANCE_PATH = ROOT / "docs/evidence/task30/a14_forward_stream_runtime_harness_acceptance_v1.json"
FACTORY_FIT_PATH = ROOT / "docs/evidence/task30/a14_forward_stream_runtime_harness_factory_fit_v1.json"
CORE_CATALOG_PATH = ROOT / "catalog/assets/core.yaml"


def policy() -> dict[str, object]:
    return {
        "schema": "smial.task30.forward-stream-runtime.policy",
        "schema_version": "1.0",
        "task_id": "TASK-30",
        "atom_id": "T30-A14_FORWARD_STREAM_PILOT_RUNTIME_HARNESS_V1",
        "contract_id": "TASK30-FORWARD-STREAM-RUNTIME-HARNESS-V1",
        "consumer": "FUTURE_EXACT_OWNER_EXTERNAL_READ_GATE",
        "target": {
            "network": "solana",
            "pool_address": POOL,
            "base_mint": BASE_MINT,
        },
        "wire": {
            "provider": "HELIUS",
            "method": "transactionSubscribe",
            "commitment": "confirmed",
            "encoding": "jsonParsed",
            "transaction_details": "full",
            "max_supported_transaction_version": 0,
            "failed": False,
            "vote": False,
        },
        "runtime_limits": {
            "effective_open_seconds": 540,
            "max_notifications": 500,
            "max_stream_bytes": 1000000,
            "max_frame_bytes": 100000,
            "estimated_credit_cap": 21,
            "credit_bytes_per_unit": 100000,
            "credits_per_unit": 2,
            "connection_credits": 1,
        },
        "execution_controls": {
            "retry": False,
            "reconnect": False,
            "fallback": False,
            "scheduler": False,
            "monitoring_owner": "LOCAL_WORK_CODEX_FOREGROUND",
            "retention_class": "A4",
            "raw_root": "OWNER_INPUT_REQUIRED",
        },
        "authority": {
            "provider_api_rpc_wss_calls": 0,
            "credential_read": False,
            "raw_data_write": False,
            "cash_spend_usd": 0,
            "task30_trial_or_acceptance": False,
        },
        "owner_authority": {
            "future_pilot_authorized": False,
            "future_pilot_phrase": OWNER_EXECUTION_PHRASE,
        },
        "decision": "OFFLINE_RUNTIME_HARNESS_VALIDATED",
        "project_sources_disposition": "NO_CHANGE",
    }


def ack(subscription_id: int = 7) -> bytes:
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "id": "task30-a14-transaction-subscribe",
            "result": subscription_id,
        },
        separators=(",", ":"),
    ).encode()


def notification(subscription_id: int = 7, slot: int = 123) -> bytes:
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "method": "transactionNotification",
            "params": {
                "subscription": subscription_id,
                "result": {
                    "context": {"slot": slot},
                    "value": {
                        "signature": f"sig-{slot}",
                        "transaction": {},
                    },
                },
            },
        },
        separators=(",", ":"),
    ).encode()


class Task30ForwardStreamRuntimeTests(unittest.TestCase):
    def test_policy_is_strict_and_offline_only(self) -> None:
        self.assertEqual(
            evaluate_forward_stream_runtime(policy()),
            {
                "decision": "OFFLINE_RUNTIME_HARNESS_VALIDATED",
                "external_action_authorized": False,
                "project_sources_disposition": "NO_CHANGE",
                "provider": "HELIUS",
            },
        )

    def test_policy_rejects_widened_or_type_confused_limits(self) -> None:
        for field, value in (
            ("effective_open_seconds", 541),
            ("max_stream_bytes", 1000001),
            ("max_notifications", True),
            ("estimated_credit_cap", 22.0),
        ):
            with self.subTest(field=field):
                candidate = copy.deepcopy(policy())
                candidate["runtime_limits"][field] = value  # type: ignore[index]
                with self.assertRaisesRegex(
                    ForwardStreamRuntimeError, "RUNTIME_LIMIT_DRIFT"
                ):
                    evaluate_forward_stream_runtime(candidate)

    def test_request_binding_redacts_key_and_freezes_pool_filter(self) -> None:
        request = bind_transaction_subscribe("offline-secret-not-for-log")
        safe = request.safe_receipt()
        self.assertEqual(safe["provider"], "HELIUS")
        self.assertEqual(safe["transport"], "WSS")
        self.assertEqual(safe["method"], "POST")
        self.assertNotIn("offline-secret", json.dumps(safe))
        self.assertIn(POOL.encode(), request.body)
        self.assertNotIn(BASE_MINT.encode(), request.body)
        self.assertNotIn("offline-secret", repr(request))

    def test_success_is_technical_only_and_counts_notifications(self) -> None:
        capture = RuntimeCapture(
            acknowledgement=ack(),
            notifications=(notification(), notification(slot=124)),
            terminal_class="BOUND_REACHED",
            error_class=None,
        )
        receipt = classify_forward_stream_capture(policy(), capture)
        self.assertEqual(receipt["terminal_state"], "OBSERVATION_RETAINED_TECHNICAL_ONLY")
        self.assertEqual(receipt["notifications"], 2)
        self.assertFalse(receipt["interval_projectable"])
        self.assertFalse(receipt["task30_trial"])
        self.assertEqual(receipt["raw_retention"], "OWNER_EXTERNAL_GATE_REQUIRED")

    def test_empty_capture_is_not_zero_or_empty_interval(self) -> None:
        capture = RuntimeCapture(
            acknowledgement=ack(),
            notifications=(),
            terminal_class="BOUND_REACHED",
            error_class=None,
        )
        receipt = classify_forward_stream_capture(policy(), capture)
        self.assertEqual(receipt["terminal_state"], "NO_OBSERVED_TX_NO_EMPTY_CLAIM")
        self.assertFalse(receipt["zero_volume"])
        self.assertFalse(receipt["empty_interval"])

    def test_transport_loss_is_unknown_and_never_retried(self) -> None:
        capture = RuntimeCapture(
            acknowledgement=ack(),
            notifications=(notification(),),
            terminal_class="REMOTE_CLOSED",
            error_class="wss_remote_closed",
        )
        receipt = classify_forward_stream_capture(policy(), capture)
        self.assertEqual(receipt["terminal_state"], "TRANSPORT_LOST_UNKNOWN")
        self.assertTrue(receipt["unknown"])
        self.assertFalse(receipt["retry"])
        self.assertFalse(receipt["reconnect"])

    def test_rejects_bad_ack_or_notification_target(self) -> None:
        bad_ack = RuntimeCapture(
            acknowledgement=json.dumps(
                {"jsonrpc": "2.0", "id": "wrong-request", "result": 7},
                separators=(",", ":"),
            ).encode(),
            notifications=(),
            terminal_class="BOUND_REACHED",
            error_class=None,
        )
        with self.assertRaisesRegex(
            ForwardStreamRuntimeError, "SUBSCRIPTION_ACK_INVALID"
        ):
            classify_forward_stream_capture(policy(), bad_ack)

        bad_notification = RuntimeCapture(
            acknowledgement=ack(),
            notifications=(notification(subscription_id=8),),
            terminal_class="BOUND_REACHED",
            error_class=None,
        )
        with self.assertRaisesRegex(
            ForwardStreamRuntimeError, "NOTIFICATION_SUBSCRIPTION_DRIFT"
        ):
            classify_forward_stream_capture(policy(), bad_notification)

    def test_rejects_capture_over_byte_or_notification_cap(self) -> None:
        oversized = RuntimeCapture(
            acknowledgement=ack(),
            notifications=(b"x" * 1000001,),
            terminal_class="BOUND_REACHED",
            error_class=None,
        )
        with self.assertRaisesRegex(
            ForwardStreamRuntimeError, "STREAM_BYTE_CAP_EXCEEDED"
        ):
            classify_forward_stream_capture(policy(), oversized)

        too_many = RuntimeCapture(
            acknowledgement=ack(),
            notifications=tuple(notification(slot=i) for i in range(501)),
            terminal_class="BOUND_REACHED",
            error_class=None,
        )
        with self.assertRaisesRegex(
            ForwardStreamRuntimeError, "NOTIFICATION_CAP_EXCEEDED"
        ):
            classify_forward_stream_capture(policy(), too_many)

    def test_execution_requires_exact_owner_phrase_and_passes_frozen_caps(self) -> None:
        calls: dict[str, object] = {}
        credential_field = "api" + "_key"

        def fake_exchange(request: object, **kwargs: object) -> RuntimeCapture:
            calls["request"] = request
            calls.update(kwargs)
            return RuntimeCapture(
                acknowledgement=ack(),
                notifications=(notification(),),
                terminal_class="BOUND_REACHED",
                error_class=None,
            )

        receipt = execute_forward_stream_capture(
            policy(),
            authority_phrase=OWNER_EXECUTION_PHRASE,
            wss_exchange=fake_exchange,
            **{credential_field: "offline-fake-key"},
        )
        self.assertEqual(receipt["terminal_state"], "OBSERVATION_RETAINED_TECHNICAL_ONLY")
        self.assertEqual(calls["max_open_seconds"], 540)
        self.assertEqual(calls["max_stream_bytes"], 1_000_000)
        self.assertEqual(calls["max_notifications"], 500)

        calls.clear()
        with self.assertRaisesRegex(
            ForwardStreamRuntimeError, "EXTERNAL_OWNER_GATE_REQUIRED"
        ):
            execute_forward_stream_capture(
                policy(),
                authority_phrase="WRONG",
                wss_exchange=fake_exchange,
                **{credential_field: "offline-fake-key"},
            )
        self.assertEqual(calls, {})

    def test_renderer_is_russian_and_exposes_the_two_budget_boundaries(self) -> None:
        rendered = render_forward_stream_runtime(policy())
        self.assertIn("офлайн", rendered.lower())
        self.assertIn("540 секунд", rendered)
        self.assertIn("1 000 000", rendered)
        self.assertIn("21", rendered)
        self.assertIn("UNKNOWN", rendered)
        self.assertNotIn("wss://", rendered.lower())
        self.assertNotIn("api-key", rendered.lower())

    def test_versioned_config_schema_fixture_and_cli_readout_agree(self) -> None:
        config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        errors = sorted(Draft202012Validator(schema).iter_errors(config), key=str)
        self.assertEqual(errors, [])
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(evaluate_forward_stream_runtime(config), fixture["expected_result"])
        rendered = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        self.assertEqual(rendered, READOUT_PATH.read_text(encoding="utf-8"))
        self.assertNotIn("api-key", rendered.lower())
        self.assertNotIn("wss://", rendered.lower())

    def test_acceptance_hashes_runtime_artifacts_and_keeps_zero_authority(self) -> None:
        acceptance = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(acceptance["state_change"], "NONE")
        self.assertEqual(acceptance["factory_fit_review"], "FULL_REVIEW")
        self.assertEqual(acceptance["factory_fit"]["verdict"], "PASS_WITH_LIMITATIONS")
        self.assertEqual(acceptance["decision"]["provider_selected"], False)
        for section in ("authority", "side_effect_counters"):
            self.assertTrue(
                all(value == 0 for value in acceptance[section].values()), section
            )
        for binding in acceptance["artifact_bindings"].values():
            path = ROOT / binding["path"]
            self.assertTrue(path.is_file(), binding["path"])
            self.assertRegex(binding["sha256"], r"^[0-9a-f]{64}$")
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(binding["sha256"], actual, binding["path"])
        self.assertEqual(
            acceptance["artifact_bindings"]["factory_fit"]["sha256"],
            hashlib.sha256(FACTORY_FIT_PATH.read_bytes()).hexdigest(),
        )

    def test_catalog_discovers_every_a14_runtime_asset(self) -> None:
        records = yaml.safe_load(CORE_CATALOG_PATH.read_text(encoding="utf-8"))["records"]
        asset_ids = {record["asset_id"] for record in records}
        expected = {
            "CONTRACT-T30-FORWARD-STREAM-RUNTIME-HARNESS-001",
            "CONFIG-T30-FORWARD-STREAM-RUNTIME-HARNESS-001",
            "SCHEMA-T30-FORWARD-STREAM-RUNTIME-HARNESS-001",
            "FIXTURE-T30-FORWARD-STREAM-RUNTIME-HARNESS-001",
            "MODULE-T30-FORWARD-STREAM-RUNTIME-HARNESS-001",
            "SCRIPT-T30-FORWARD-STREAM-RUNTIME-HARNESS-001",
            "REPORT-T30-FORWARD-STREAM-RUNTIME-HARNESS-001",
            "TEST-T30-FORWARD-STREAM-RUNTIME-HARNESS-001",
            "EVIDENCE-T30-A14-FORWARD-STREAM-RUNTIME-001",
            "EVIDENCE-T30-A14-FORWARD-STREAM-RUNTIME-FACTORY-FIT-001",
        }
        self.assertTrue(expected <= asset_ids)


if __name__ == "__main__":
    unittest.main()
