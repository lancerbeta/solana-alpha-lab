from __future__ import annotations

import base64
import copy
import json
import struct
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.pump_event_decoder import (  # noqa: E402
    PROGRAM_DATA_PREFIX,
    PUMP_PROGRAM_ID,
    FieldSpec,
    PumpEventPlan,
    load_pinned_pump_event_plan,
)
from solana_alpha_lab.task36_h11_lifecycle_clock_screen import (  # noqa: E402
    running_peak_at_decision,
)
from solana_alpha_lab.task37_h11_migration_clock_capture import (  # noqa: E402
    ATOM_ID,
    FAMILY,
    MIGRATION_EVENT,
    TERMINAL_OUTCOMES,
    TRIAL_ID,
    CaptureError,
    CaptureIntegrityError,
    OutcomeGuard,
    clock_fingerprint,
    decide_terminal,
    execute_capture,
    load_policy,
    migration_timestamp_from_events,
    scan_pool_history,
)

CONFIG_PATH = ROOT / "configs/task37_rc002_h11_migration_clock_capture_v1.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/task37_rc002_h11_migration_clock_capture.schema.json"
FIXTURE_PATH = ROOT / "tests/fixtures/task37/h11_migration_clock_capture_v1.json"
RC001_PATH = ROOT / "configs/task28_rc001_registry_freeze_v1.yaml"
HOLDOUT_PATH = ROOT / "registries/holdout_consumption.yaml"
IDL_PATH = ROOT / "tests/fixtures/task08/pump_event_idl_subset_v1.json"
PUMPSWAP = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"


def _encode_type(plan: PumpEventPlan, type_spec: object, value: object) -> bytes:
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
        return struct.pack("<I", 0)
    raise AssertionError(f"unsupported_test_type:{type_spec!r}")


def _default_value(field: FieldSpec, seed: int) -> object:
    if field.type_spec == "bool":
        return False
    if field.type_spec == "i64":
        return 1_721_888_000 + seed
    if field.type_spec == "pubkey":
        return bytes([(seed + 1) % 251]) * 32
    if field.type_spec == "string":
        return f"synthetic-{field.name}"
    if field.type_spec == "u16":
        return seed
    if field.type_spec == "u64":
        return 10_000 + seed
    if field.type_spec == ("vec_defined", "Shareholder"):
        return []
    raise AssertionError(f"unsupported_test_type:{field.type_spec!r}")


def _event_line(
    plan: PumpEventPlan,
    event_name: str,
    overrides: dict[str, object] | None = None,
) -> str:
    schema = next(event for event in plan.events if event.name == event_name)
    values = {
        field.name: _default_value(field, index)
        for index, field in enumerate(schema.fields)
    }
    if overrides:
        values.update(overrides)
    payload = schema.discriminator + b"".join(
        _encode_type(plan, field.type_spec, values[field.name])
        for field in schema.fields
    )
    return PROGRAM_DATA_PREFIX + base64.b64encode(payload).decode("ascii")


def _pump_logs(plan: PumpEventPlan, event_name: str, **overrides: object) -> list[str]:
    return [
        f"Program {PUMP_PROGRAM_ID} invoke [1]",
        _event_line(plan, event_name, overrides),
        f"Program {PUMP_PROGRAM_ID} success",
    ]


def _tx_row(
    *,
    logs: list[str],
    keys: list[str],
    sig: str,
    index: int = 0,
) -> dict[str, object]:
    return {
        "slot": 438709109 + index,
        "transactionIndex": index,
        "blockTime": 1786494563 + index,
        "transaction": {
            "signatures": [sig],
            "message": {"accountKeys": keys},
        },
        "meta": {"err": None, "logMessages": logs},
    }


class Task37ClockCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = load_policy(CONFIG_PATH)
        cls.plan = load_pinned_pump_event_plan(IDL_PATH)
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_policy_matches_closed_schema_and_frozen_clocks(self) -> None:
        jsonschema.Draft202012Validator(self.schema).validate(
            yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        )
        self.assertEqual(self.policy["atom_id"], ATOM_ID)
        self.assertEqual(self.policy["capture_protocol"]["family"], FAMILY)
        clocks = self.policy["clock_definitions"]
        self.assertTrue(clocks["freeze_before_event_inspection"])
        self.assertEqual(
            clocks["migration_at"]["source_event"],
            "CompletePumpAmmMigrationEvent",
        )
        self.assertEqual(
            clocks["migration_at"]["forbidden_sources"],
            [
                "later_price",
                "first_pumpswap_trade",
                "block_time_heuristic",
                "first_reliable_availability",
            ],
        )
        self.assertEqual(clocks["running_peak_at"]["future_events"], "IGNORE")
        self.assertEqual(list(self.policy["terminal_outcomes"]), list(TERMINAL_OUTCOMES))

    def test_trial_must_register_pending_before_outcome(self) -> None:
        guard = OutcomeGuard()
        with self.assertRaises(CaptureError):
            guard.allow()
        guard.register({"status": "PENDING", "record_id": TRIAL_ID})
        guard.allow()

    def test_running_peak_ignores_future_prices(self) -> None:
        decision = 1_000
        peak_at, state = running_peak_at_decision(
            [
                {"event_at": 900, "price": 2.0},
                {"event_at": 950, "price": 3.0},
                {"event_at": 1_100, "price": 99.0},
            ],
            decision,
        )
        self.assertEqual(peak_at, 950)
        self.assertEqual(state, "OBSERVED")

    def test_migration_timestamp_comes_from_chain_event_not_later_price(self) -> None:
        logs = _pump_logs(
            self.plan,
            MIGRATION_EVENT,
            timestamp=1_721_000_000,
        )
        row = _tx_row(
            logs=logs,
            keys=[PUMP_PROGRAM_ID, PUMPSWAP],
            sig="1" * 88,
        )
        scan = scan_pool_history(
            [row],
            plan=self.plan,
            pool_address=str(self.policy["adopted_route"]["pool_address"]),
        )
        self.assertEqual(scan["migration_events"], 1)
        migration_at = scan["reconstructed"][0]["migration_at"]
        self.assertEqual(migration_at, 1_721_000_000)
        decoded_ts = migration_timestamp_from_events(
            [
                type(
                    "E",
                    (),
                    {"event_name": MIGRATION_EVENT, "event_timestamp": 1_721_000_000},
                )()
            ],
            later_price=99.0,
        )
        self.assertEqual(decoded_ts, 1_721_000_000)
        self.assertNotEqual(decoded_ts, 99.0)

    def test_pool_history_without_pump_events_is_typed_wrong_address(self) -> None:
        row = _tx_row(
            logs=["Program " + PUMPSWAP + " invoke [1]", "Program " + PUMPSWAP + " success"],
            keys=[PUMPSWAP, "So11111111111111111111111111111111111111112"],
            sig="2" * 88,
        )
        scan = scan_pool_history(
            [row],
            plan=self.plan,
            pool_address=str(self.policy["adopted_route"]["pool_address"]),
        )
        self.assertEqual(scan["create_events"], 0)
        self.assertEqual(scan["migration_events"], 0)
        self.assertIn("CREATE_EVENT_NOT_IN_ADDRESSED_HISTORY", scan["missingness"])
        self.assertIn("MIGRATION_EVENT_NOT_IN_ADDRESSED_HISTORY", scan["missingness"])
        self.assertEqual(
            decide_terminal(
                scan,
                minima=self.policy["capture_protocol"]["minimum_independent_units"],
            ),
            "HISTORICAL_ROUTE_WRONG_ADDRESS_OR_EVENT",
        )

    def test_one_reconstructed_pool_is_insufficient_scale(self) -> None:
        logs = _pump_logs(self.plan, MIGRATION_EVENT, timestamp=1_721_000_000)
        create = _pump_logs(self.plan, "CreateEvent", timestamp=1_720_999_000)
        rows = [
            _tx_row(logs=create, keys=[PUMP_PROGRAM_ID], sig="3" * 88, index=0),
            _tx_row(logs=logs, keys=[PUMP_PROGRAM_ID], sig="4" * 88, index=1),
        ]
        scan = scan_pool_history(
            rows,
            plan=self.plan,
            pool_address=str(self.policy["adopted_route"]["pool_address"]),
        )
        self.assertGreaterEqual(scan["migration_events"], 1)
        self.assertEqual(
            decide_terminal(
                scan,
                minima=self.policy["capture_protocol"]["minimum_independent_units"],
            ),
            "INSUFFICIENT_SCALE_WITHOUT_PAID_CAPTURE",
        )

    def test_predeclared_minima_with_clocks_are_cohort_ready(self) -> None:
        rows = []
        for index in range(8):
            day = 1_721_000_000 if index < 4 else 1_721_086_400
            creator = bytes([10 if index < 4 else 20]) * 32
            pool = bytes([index + 1]) * 32
            mint = bytes([30 + index]) * 32
            create = _pump_logs(
                self.plan,
                "CreateEvent",
                timestamp=day - 60,
                creator=creator,
                user=creator,
                mint=mint,
            )
            migrate = _pump_logs(
                self.plan,
                MIGRATION_EVENT,
                timestamp=day,
                pool=pool,
                mint=mint,
            )
            rows.append(
                _tx_row(
                    logs=create,
                    keys=[PUMP_PROGRAM_ID],
                    sig=chr(97 + index) * 88,
                    index=index * 2,
                )
            )
            rows.append(
                _tx_row(
                    logs=migrate,
                    keys=[PUMP_PROGRAM_ID],
                    sig=chr(65 + index) * 88,
                    index=index * 2 + 1,
                )
            )
        result = execute_capture(
            repo_root=ROOT,
            policy=self.policy,
            pages=rows,
        )
        self.assertFalse(result["live_universe"])
        self.assertEqual(
            result["terminal_decision"],
            "CLOCKS_RECONSTRUCTED_COHORT_READY",
        )
        self.assertGreaterEqual(result["cohort"]["n"], 8)
        self.assertGreaterEqual(len(result["cohort"]["days"]), 2)
        self.assertGreaterEqual(len(result["cohort"]["deployers"]), 2)

    def test_live_compact_fixture_matches_wrong_address_gap(self) -> None:
        compact = {
            "transaction_count": self.fixture["transaction_count"],
            "pump_program_in_account_keys": self.fixture["pump_program_in_account_keys"],
            "create_events": self.fixture["create_events"],
            "complete_events": self.fixture["complete_events"],
            "migration_events": self.fixture["migration_events"],
            "reconstructed": [],
            "missingness": [
                "CREATE_EVENT_NOT_IN_ADDRESSED_HISTORY",
                "MIGRATION_EVENT_NOT_IN_ADDRESSED_HISTORY",
                "PUMP_PROGRAM_NOT_IN_ACCOUNT_KEYS",
            ],
            "attribution_errors": {},
        }
        result = execute_capture(
            repo_root=ROOT,
            policy=self.policy,
            compact_scan=compact,
        )
        self.assertEqual(
            result["terminal_decision"],
            self.fixture["expected_live_terminal"],
        )
        self.assertEqual(result["trial"]["record_id"], TRIAL_ID)
        self.assertEqual(result["trial"]["outcome"], "INCONCLUSIVE")
        self.assertEqual(result["cohort"]["n"], 0)
        self.assertIn("CREATE_EVENT_NOT_IN_ADDRESSED_HISTORY", result["scan"]["missingness"])

    def test_rc001_hash_drift_fails_closed(self) -> None:
        policy = copy.deepcopy(dict(self.policy))
        policy["rc001_freeze"]["required_definition_sha256"][
            "RC001-H13-COMPOSITE-VETO"
        ] = "0" * 64
        with self.assertRaises(CaptureIntegrityError):
            execute_capture(
                repo_root=ROOT,
                policy=policy,
                compact_scan={"create_events": 0, "migration_events": 0, "reconstructed": []},
            )

    def test_holdout_and_rc001_bytes_are_unmutated(self) -> None:
        result = execute_capture(
            repo_root=ROOT,
            policy=self.policy,
            compact_scan={
                "create_events": 0,
                "migration_events": 0,
                "reconstructed": [],
                "missingness": ["CREATE_EVENT_NOT_IN_ADDRESSED_HISTORY"],
            },
        )
        freeze = yaml.safe_load(RC001_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            freeze["hypothesis_groups"][0]["definition_sha256"],
            result["rc001_freeze"]["definition_sha256"]["RC001-H13-COMPOSITE-VETO"],
        )
        holdout = yaml.safe_load(HOLDOUT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(holdout["records"], [])
        self.assertFalse(result["rc001_mutated"])
        self.assertFalse(result["holdout_consumed"])

    def test_clock_fingerprint_is_stable(self) -> None:
        first = clock_fingerprint(self.policy)
        second = clock_fingerprint(load_policy(CONFIG_PATH))
        self.assertEqual(first, second)

    def test_live_a22_scan_matches_committed_gap_when_a4_present(self) -> None:
        a22 = ROOT / self.policy["adopted_route"]["a22_raw"]["path"]
        if not a22.is_file():
            # DELIVERY_PREFLIGHT_NONCRITICAL_SKIP: tracked proof is
            # docs/evidence/task30/a22_helius_get_transactions_for_address_runtime_receipt_v1.json
            # plus tests/fixtures/task37/h11_migration_clock_capture_v1.json.
            self.skipTest("A4 local A22 bytes absent")
        result = execute_capture(repo_root=ROOT, policy=self.policy)
        self.assertTrue(result["live_universe"])
        self.assertEqual(
            result["terminal_decision"],
            self.fixture["expected_live_terminal"],
        )
        self.assertEqual(result["scan"]["create_events"], 0)
        self.assertEqual(result["scan"]["migration_events"], 0)
        self.assertEqual(result["scan"]["pump_program_in_account_keys"], 0)
        self.assertEqual(result["scan"]["transaction_count"], 520)


if __name__ == "__main__":
    unittest.main()
