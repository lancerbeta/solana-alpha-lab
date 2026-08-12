from __future__ import annotations

import copy
import base64
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


if __name__ == "__main__":
    unittest.main()
