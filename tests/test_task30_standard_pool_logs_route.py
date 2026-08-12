from __future__ import annotations

import copy
import base64
import hashlib
import json
import struct
import sys
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator
from solders.pubkey import Pubkey

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from solana_alpha_lab.task30_standard_pool_logs_route import (
    StandardPoolLogsCapture,
    StandardPoolLogsRouteError,
    bind_pool_logs_subscribe,
    classify_standard_pool_logs_capture,
    evaluate_standard_pool_logs_route,
    render_standard_pool_logs_route,
)
from solana_alpha_lab.pumpswap_touch_decoder import (
    PROGRAM_DATA_PREFIX,
    PUMPSWAP_PROGRAM_ID,
    FieldSpec,
    LayoutSchema,
    load_pinned_pumpswap_plan,
)

POOL = "URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S"
CONFIG = ROOT / "configs" / "task30_standard_pool_logs_route_v1.yaml"
SCHEMA = ROOT / "catalog" / "schemas" / "task30_standard_pool_logs_route.schema.json"
FIXTURE = ROOT / "tests" / "fixtures" / "task30" / "standard_pool_logs_route_v1.json"
PUMPSWAP_FIXTURE = ROOT / "tests" / "fixtures" / "task09" / "pumpswap_idl_subset_v1.json"
READOUT = ROOT / "docs" / "reports" / "task30" / "standard_pool_logs_route_readout_v1.md"
TASK = ROOT / "docs" / "tasks" / "TASK-30-standard-pool-logs-route.md"
CONTRACT = ROOT / "docs" / "contracts" / "task30_standard_pool_logs_route_contract_v1.md"
MODULE = ROOT / "src" / "solana_alpha_lab" / "task30_standard_pool_logs_route.py"
SCRIPT = ROOT / "scripts" / "show_task30_standard_pool_logs_route.py"
ACCEPTANCE = ROOT / "docs" / "evidence" / "task30" / "a15_standard_pool_logs_route_acceptance_v1.json"
FACTORY_FIT = ROOT / "docs" / "evidence" / "task30" / "a15_standard_pool_logs_route_factory_fit_v1.json"
CATALOG = ROOT / "catalog" / "assets" / "core.yaml"

ARTIFACTS = {
    "contract": CONTRACT,
    "configuration": CONFIG,
    "schema": SCHEMA,
    "module": MODULE,
    "fixture": FIXTURE,
    "test": Path(__file__),
    "script": SCRIPT,
    "report": READOUT,
}
CATALOG_IDS = {
    "CONTRACT-T30-STANDARD-POOL-LOGS-ROUTE-001": CONTRACT,
    "CONFIG-T30-STANDARD-POOL-LOGS-ROUTE-001": CONFIG,
    "SCHEMA-T30-STANDARD-POOL-LOGS-ROUTE-001": SCHEMA,
    "MODULE-T30-STANDARD-POOL-LOGS-ROUTE-001": MODULE,
    "FIXTURE-T30-STANDARD-POOL-LOGS-ROUTE-001": FIXTURE,
    "TEST-T30-STANDARD-POOL-LOGS-ROUTE-001": Path(__file__),
    "SCRIPT-T30-STANDARD-POOL-LOGS-ROUTE-001": SCRIPT,
    "REPORT-T30-STANDARD-POOL-LOGS-ROUTE-001": READOUT,
    "EVIDENCE-T30-A15-STANDARD-POOL-LOGS-ROUTE-001": ACCEPTANCE,
    "EVIDENCE-T30-A15-STANDARD-POOL-LOGS-ROUTE-FACTORY-FIT-001": FACTORY_FIT,
}


def _sample_value(field: FieldSpec, seed: int, *, pool: bytes) -> object:
    if field.name == "pool":
        return pool
    if field.type_spec == "bool":
        return False
    if field.type_spec == "i64":
        return 1_720_000_000 + seed
    if field.type_spec == "i128":
        return 500 + seed
    if field.type_spec == "pubkey":
        return bytes([(seed % 250) + 1]) * 32
    if field.type_spec == "string":
        return "buy" if seed % 2 == 0 else "sell"
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


def _payload(schema: LayoutSchema, *, pool: bytes) -> bytes:
    return schema.discriminator + b"".join(
        _encode_type(
            field.type_spec,
            _sample_value(field, index, pool=pool),
        )
        for index, field in enumerate(schema.fields)
    )


def _notification(
    *,
    subscription_id: int,
    logs: list[str],
    succeeded: bool = True,
    signature: str = "1" * 64,
) -> bytes:
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "method": "logsNotification",
            "params": {
                "result": {
                    "context": {"slot": 123},
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


def policy() -> dict[str, object]:
    loaded = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Task30StandardPoolLogsRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = load_pinned_pumpswap_plan(PUMPSWAP_FIXTURE)
        cls.subscription_id = 77
        cls.ack = json.dumps(
            {"id": "task30-a15-pool-logs-subscribe", "jsonrpc": "2.0", "result": 77},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()

    def trade_notification(
        self,
        event_index: int,
        *,
        pool: bytes | None = None,
        succeeded: bool = True,
        signature: str = "1" * 64,
    ) -> bytes:
        event_line = PROGRAM_DATA_PREFIX + base64.b64encode(
            _payload(
                self.plan.events[event_index],
                pool=pool or bytes(Pubkey.from_string(POOL)),
            )
        ).decode()
        return _notification(
            subscription_id=self.subscription_id,
            succeeded=succeeded,
            signature=signature,
            logs=[
                f"Program {PUMPSWAP_PROGRAM_ID} invoke [1]",
                event_line,
                f"Program {PUMPSWAP_PROGRAM_ID} success",
            ],
        )

    def classify(
        self,
        notifications: tuple[bytes, ...],
        *,
        terminal_class: str = "BOUND_REACHED",
        error_class: str | None = None,
    ) -> dict[str, object]:
        return classify_standard_pool_logs_capture(
            policy(),
            StandardPoolLogsCapture(
                acknowledgement=self.ack,
                notifications=notifications,
                terminal_class=terminal_class,
                error_class=error_class,
            ),
            self.plan,
        )

    def test_policy_is_closed_and_exact(self) -> None:
        document = policy()
        Draft202012Validator(
            json.loads(SCHEMA.read_text(encoding="utf-8"))
        ).validate(document)
        self.assertEqual(document["target"]["pool_address"], POOL)
        self.assertEqual(document["wire"]["method"], "logsSubscribe")
        self.assertEqual(document["wire"]["mentions"], [POOL])
        self.assertEqual(document["wire"]["commitment"], "confirmed")
        self.assertEqual(document["execution_controls"]["rpc_followups"], 0)

    def test_request_is_pool_targeted_and_secret_safe(self) -> None:
        request = bind_pool_logs_subscribe("offline-synthetic-key")
        body = json.loads(request.body)
        self.assertEqual(body["method"], "logsSubscribe")
        self.assertEqual(
            body["params"],
            [{"mentions": [POOL]}, {"commitment": "confirmed"}],
        )
        self.assertNotIn("offline-synthetic-key", repr(request))
        self.assertNotIn(
            "offline-synthetic-key", json.dumps(request.safe_receipt())
        )

    def test_policy_rejects_widening_and_type_confusion(self) -> None:
        for pointer, value in (
            (("wire", "mentions"), [POOL, "DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK"]),
            (("runtime_limits", "effective_open_seconds"), 601),
            (("runtime_limits", "max_notifications"), True),
            (("execution_controls", "rpc_followups"), 1),
            (("execution_controls", "retry"), True),
        ):
            candidate = copy.deepcopy(policy())
            candidate[pointer[0]][pointer[1]] = value
            with self.subTest(pointer=pointer):
                with self.assertRaises(StandardPoolLogsRouteError):
                    evaluate_standard_pool_logs_route(candidate)

    def test_classifier_preserves_exact_truth_states_and_nonclaims(self) -> None:
        happy_buy = self.classify((self.trade_notification(0),))
        happy_sell = self.classify(
            (self.trade_notification(1, signature="2" * 64),)
        )
        no_notifications = self.classify(())
        remote_closed = self.classify(
            (), terminal_class="REMOTE_CLOSED", error_class="remote_closed"
        )
        failed_tx = self.classify((self.trade_notification(0, succeeded=False),))
        truncated = self.classify(
            (
                _notification(
                    subscription_id=self.subscription_id,
                    logs=[
                        f"Program {PUMPSWAP_PROGRAM_ID} invoke [1]",
                        "Log truncated",
                    ],
                ),
            )
        )
        self.assertEqual(happy_buy["terminal_state"], "OBSERVED_POOL_TRADE")
        self.assertEqual(happy_sell["terminal_state"], "OBSERVED_POOL_TRADE")
        self.assertEqual(no_notifications["terminal_state"], "NO_OBSERVATION_UNKNOWN")
        self.assertEqual(remote_closed["terminal_state"], "TRANSPORT_LOST_UNKNOWN")
        self.assertEqual(failed_tx["terminal_state"], "OBSERVED_NON_TRADE_OR_UNSUPPORTED")
        self.assertEqual(truncated["terminal_state"], "TRUNCATED_OR_SCHEMA_DRIFT_UNKNOWN")
        for result in (
            happy_buy,
            happy_sell,
            no_notifications,
            remote_closed,
            failed_tx,
            truncated,
        ):
            for key in (
                "zero_volume",
                "empty_interval",
                "interval_complete",
                "pit_admissible",
                "task30_trial",
                "numeric_netreturn",
            ):
                self.assertIs(result[key], False)

    def test_typed_subscription_rejection_is_terminal_without_retry(self) -> None:
        acknowledgement = json.dumps(
            {
                "error": {"code": -32602, "message": "synthetic rejection"},
                "id": "task30-a15-pool-logs-subscribe",
                "jsonrpc": "2.0",
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        result = classify_standard_pool_logs_capture(
            policy(),
            StandardPoolLogsCapture(
                acknowledgement=acknowledgement,
                notifications=(),
                terminal_class="BOUND_REACHED",
            ),
            self.plan,
        )
        self.assertEqual(result["terminal_state"], "SUBSCRIPTION_REJECTED")
        self.assertIs(result["retry"], False)
        self.assertIs(result["reconnect"], False)

    def test_classifier_fails_closed_on_identity_or_schema_drift(self) -> None:
        wrong_request = json.dumps(
            {"id": "wrong", "jsonrpc": "2.0", "result": 77},
            separators=(",", ":"),
        ).encode()
        wrong_subscription = _notification(
            subscription_id=78,
            logs=[f"Program {PUMPSWAP_PROGRAM_ID} invoke [1]"],
        )
        duplicate = self.trade_notification(0)
        wrong_pool = self.trade_notification(0, pool=bytes([7]) * 32)
        unknown = json.loads(self.trade_notification(0))
        unknown["unexpected"] = True
        unknown_frame = json.dumps(unknown, separators=(",", ":")).encode()
        cases = (
            StandardPoolLogsCapture(wrong_request, (), "BOUND_REACHED"),
            StandardPoolLogsCapture(self.ack, (wrong_subscription,), "BOUND_REACHED"),
            StandardPoolLogsCapture(self.ack, (duplicate, duplicate), "BOUND_REACHED"),
            StandardPoolLogsCapture(self.ack, (wrong_pool,), "BOUND_REACHED"),
            StandardPoolLogsCapture(self.ack, (unknown_frame,), "BOUND_REACHED"),
        )
        for capture in cases:
            with self.subTest(capture=repr(capture)):
                with self.assertRaises(StandardPoolLogsRouteError):
                    classify_standard_pool_logs_capture(
                        policy(), capture, self.plan
                    )

    def test_owner_readout_is_exact_and_nontechnical(self) -> None:
        rendered = render_standard_pool_logs_route(policy())
        self.assertIn("Стандартный бесплатный WSS-маршрут подготовлен офлайн", rendered)
        self.assertIn("реальный запуск пока не разрешён", rendered)
        self.assertIn("отсутствие уведомлений не означает нулевой объём", rendered)
        self.assertNotIn("api-key", rendered.casefold())
        self.assertEqual(READOUT.read_text(encoding="utf-8"), rendered)

    def test_acceptance_is_hash_bound_and_catalogued_without_promotion(self) -> None:
        receipt = json.loads(ACCEPTANCE.read_text(encoding="utf-8"))
        self.assertEqual(
            receipt["decision"],
            "OFFLINE_STANDARD_POOL_LOGS_ROUTE_READY_FOR_OWNER_GATE",
        )
        self.assertEqual(receipt["validation_status"], "PASS_WITH_LIMITATIONS")
        self.assertEqual(receipt["state_change"], "NONE")
        self.assertEqual(receipt["project_sources_disposition"]["kind"], "NO_CHANGE")
        self.assertEqual(set(receipt["artifact_bindings"]), set(ARTIFACTS))
        for artifact_id, path in ARTIFACTS.items():
            binding = receipt["artifact_bindings"][artifact_id]
            self.assertEqual(binding["path"], path.relative_to(ROOT).as_posix())
            self.assertEqual(binding["sha256"], sha256(path))
        self.assertTrue(all(value in (0, False) for value in receipt["authority"].values()))
        self.assertTrue(all(value is False for value in receipt["non_claims"].values()))

        factory_fit = json.loads(FACTORY_FIT.read_text(encoding="utf-8"))
        self.assertEqual(factory_fit["review_scope"], "FULL_REVIEW")
        self.assertEqual(factory_fit["verdict"], "PASS_WITH_LIMITATIONS")
        self.assertEqual(factory_fit["state_change"], "NONE")

        catalog = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
        records = {record["asset_id"]: record for record in catalog["records"]}
        for asset_id, path in CATALOG_IDS.items():
            self.assertEqual(
                records[asset_id]["location"]["repository_path"],
                path.relative_to(ROOT).as_posix(),
            )


if __name__ == "__main__":
    unittest.main()
