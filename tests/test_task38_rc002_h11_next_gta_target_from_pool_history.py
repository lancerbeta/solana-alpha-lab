from __future__ import annotations

import base64
import copy
import json
import struct
import sys
import unittest
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
from solana_alpha_lab.task37_h11_migration_clock_capture import (  # noqa: E402
    CaptureError,
    CaptureIntegrityError,
    OutcomeGuard,
)
from solana_alpha_lab.task38_h11_next_gta_target_from_pool_history import (  # noqa: E402
    ATOM_ID,
    FAMILY,
    TERMINAL_OUTCOMES,
    TRIAL_ID,
    WSOL_MINT,
    decide_terminal,
    execute_target,
    load_policy,
    resolver_fingerprint,
    scan_pool_history,
)

CONFIG_PATH = ROOT / "configs/task38_rc002_h11_next_gta_target_from_pool_history_v1.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/task38_rc002_h11_next_gta_target_from_pool_history.schema.json"
FIXTURE_PATH = ROOT / "tests/fixtures/task38/h11_next_gta_target_from_pool_history_v1.json"
RC001_PATH = ROOT / "configs/task28_rc001_registry_freeze_v1.yaml"
HOLDOUT_PATH = ROOT / "registries/holdout_consumption.yaml"
IDL_PATH = ROOT / "tests/fixtures/task08/pump_event_idl_subset_v1.json"
UNIQUE_MINT = "DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK"
OTHER_MINT = "GCa9TZMK9Q3VUSkhZgX76YAQBjqQd1dPxkBnZojFpump"
USER = "11111111111111111111111111111111"


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


def _balance(mint: str, owner: str) -> dict[str, str]:
    return {"mint": mint, "owner": owner}


def _tx_row(
    *,
    logs: list[str] | None = None,
    keys: list[str],
    sig: str,
    index: int = 0,
    balances: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    return {
        "slot": 438709109 + index,
        "transactionIndex": index,
        "blockTime": 1786494563 + index,
        "transaction": {
            "signatures": [sig],
            "message": {"accountKeys": keys},
        },
        "meta": {
            "err": None,
            "logMessages": logs or [],
            "preTokenBalances": list(balances or []),
            "postTokenBalances": list(balances or []),
        },
    }


class Task38NextGtaTargetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = load_policy(CONFIG_PATH)
        cls.plan = load_pinned_pump_event_plan(IDL_PATH)
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.pool = str(cls.policy["adopted_route"]["pool_address"])

    def test_policy_matches_closed_schema_and_frozen_resolver(self) -> None:
        jsonschema.Draft202012Validator(self.schema).validate(
            yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        )
        self.assertEqual(self.policy["atom_id"], ATOM_ID)
        resolver = self.policy["target_resolver"]
        self.assertTrue(resolver["freeze_before_candidate_inspection"])
        self.assertEqual(resolver["token_balance_owner_scope"], "SCANNED_POOL_ONLY")
        self.assertEqual(resolver["wrapped_sol_mint"], WSOL_MINT)
        self.assertEqual(resolver["pump_program_id"], PUMP_PROGRAM_ID)
        self.assertTrue(resolver["unbounded_gta_forbidden"])
        self.assertTrue(resolver["naming_does_not_authorize_network"])
        self.assertEqual(list(self.policy["terminal_outcomes"]), list(TERMINAL_OUTCOMES))
        self.assertFalse(self.policy["external_authority"]["network"])

    def test_trial_must_register_pending_before_outcome(self) -> None:
        guard = OutcomeGuard()
        with self.assertRaises(CaptureError):
            guard.allow()
        guard.register({"status": "PENDING", "record_id": TRIAL_ID})
        guard.allow()

    def test_unique_pool_owned_mint_is_named_despite_incidental_mints(self) -> None:
        row = _tx_row(
            keys=[self.pool, USER],
            sig="1" * 88,
            balances=[
                _balance(UNIQUE_MINT, self.pool),
                _balance(WSOL_MINT, self.pool),
                _balance(OTHER_MINT, USER),
            ],
        )
        scan = scan_pool_history(
            [row],
            plan=self.plan,
            pool_address=self.pool,
        )
        self.assertEqual(scan["pool_owned_mints"], [UNIQUE_MINT])
        self.assertIn(OTHER_MINT, scan["incidental_mints"])
        self.assertNotIn(WSOL_MINT, scan["pool_owned_mints"])
        decision = decide_terminal(scan)
        self.assertEqual(decision["terminal_decision"], "NEXT_BOUNDED_GTA_TARGET_NAMED")
        self.assertEqual(decision["named_target_kind"], "TOKEN_MINT")
        self.assertEqual(decision["named_target_address"], UNIQUE_MINT)
        self.assertFalse(decision["network_authorized"])

    def test_cannot_resolve_when_no_mint(self) -> None:
        row = _tx_row(keys=[self.pool], sig="2" * 88, balances=[])
        scan = scan_pool_history([row], plan=self.plan, pool_address=self.pool)
        self.assertEqual(scan["pool_owned_mints"], [])
        self.assertEqual(
            decide_terminal(scan)["terminal_decision"],
            "CANNOT_RESOLVE_BOUNDED_TARGET_FROM_POOL_HISTORY",
        )

    def test_cannot_resolve_when_only_program_or_only_pool(self) -> None:
        program_row = _tx_row(
            keys=[PUMP_PROGRAM_ID],
            sig="3" * 88,
            balances=[_balance(PUMP_PROGRAM_ID, PUMP_PROGRAM_ID)],
        )
        pool_row = _tx_row(
            keys=[self.pool],
            sig="4" * 88,
            balances=[_balance(self.pool, self.pool), _balance(WSOL_MINT, self.pool)],
        )
        for row in (program_row, pool_row):
            scan = scan_pool_history([row], plan=self.plan, pool_address=self.pool)
            self.assertEqual(
                decide_terminal(scan)["terminal_decision"],
                "CANNOT_RESOLVE_BOUNDED_TARGET_FROM_POOL_HISTORY",
            )
            self.assertIsNone(decide_terminal(scan)["named_target_address"])

    def test_multiple_pool_owned_mints_are_ambiguous_cannot_resolve(self) -> None:
        row = _tx_row(
            keys=[self.pool],
            sig="5" * 88,
            balances=[
                _balance(UNIQUE_MINT, self.pool),
                _balance(OTHER_MINT, self.pool),
            ],
        )
        scan = scan_pool_history([row], plan=self.plan, pool_address=self.pool)
        decision = decide_terminal(scan)
        self.assertTrue(decision["ambiguous"])
        self.assertEqual(
            decision["terminal_decision"],
            "CANNOT_RESOLVE_BOUNDED_TARGET_FROM_POOL_HISTORY",
        )

    def test_unique_create_event_mint_is_named(self) -> None:
        mint = bytes([7]) * 32
        logs = _pump_logs(self.plan, "CreateEvent", mint=mint)
        row = _tx_row(logs=logs, keys=[PUMP_PROGRAM_ID], sig="6" * 88)
        result = execute_target(repo_root=ROOT, policy=self.policy, pages=[row])
        self.assertEqual(result["terminal_decision"], "NEXT_BOUNDED_GTA_TARGET_NAMED")
        self.assertEqual(result["named_target"]["kind"], "TOKEN_MINT")
        self.assertTrue(result["named_target"]["address"])
        self.assertNotEqual(result["named_target"]["address"], PUMP_PROGRAM_ID)
        self.assertFalse(result["network_authorized"])
        self.assertEqual(result["side_effects"]["provider_requests"], 0)

    def test_unique_bonding_curve_is_named_when_no_mint(self) -> None:
        curve = bytes([9]) * 32
        logs = _pump_logs(
            self.plan,
            "CreateEvent",
            mint=bytes([0]) * 32,
            bonding_curve=curve,
        )
        row = _tx_row(logs=logs, keys=[PUMP_PROGRAM_ID], sig="7" * 88)
        scan = scan_pool_history([row], plan=self.plan, pool_address=self.pool)
        # all-zero mint base58 is a string of 1s; still a mint, so prefer mint.
        self.assertEqual(len(scan["create_mints"]), 1)
        mintless = dict(scan)
        mintless["create_mints"] = []
        mintless["pool_owned_mints"] = []
        decision = decide_terminal(mintless)
        self.assertEqual(decision["terminal_decision"], "NEXT_BOUNDED_GTA_TARGET_NAMED")
        self.assertEqual(decision["named_target_kind"], "BONDING_CURVE")
        self.assertEqual(len(scan["bonding_curves"]), 1)

    def test_pump_program_is_never_named_as_next_gta_target(self) -> None:
        compact = {
            "pool_owned_mints": [PUMP_PROGRAM_ID],
            "create_mints": [],
            "bonding_curves": [],
        }
        result = execute_target(
            repo_root=ROOT,
            policy=self.policy,
            compact_scan=compact,
        )
        self.assertEqual(
            result["terminal_decision"],
            "CANNOT_RESOLVE_BOUNDED_TARGET_FROM_POOL_HISTORY",
        )
        self.assertIsNone(result["named_target"]["address"])

    def test_live_compact_fixture_names_unique_pool_mint_without_network(self) -> None:
        compact = {
            "transaction_count": self.fixture["transaction_count"],
            "pump_program_in_account_keys": self.fixture["pump_program_in_account_keys"],
            "create_events": self.fixture["create_events"],
            "pool_owned_mints": self.fixture["pool_owned_mints"],
            "create_mints": self.fixture["create_mints"],
            "bonding_curves": self.fixture["bonding_curves"],
            "incidental_mints": ["x" * 44],
            "missingness": ["PUMP_PROGRAM_NOT_IN_ACCOUNT_KEYS"],
            "attribution_errors": {},
        }
        result = execute_target(
            repo_root=ROOT,
            policy=self.policy,
            compact_scan=compact,
        )
        self.assertEqual(result["terminal_decision"], self.fixture["expected_live_terminal"])
        self.assertEqual(result["named_target"]["kind"], self.fixture["expected_target_kind"])
        self.assertEqual(
            result["named_target"]["address"],
            self.fixture["expected_target_address"],
        )
        self.assertEqual(result["trial"]["record_id"], TRIAL_ID)
        self.assertEqual(result["trial"]["outcome"], "PASS")
        self.assertFalse(result["network_authorized"])
        self.assertEqual(result["side_effects"]["provider_requests"], 0)

    def test_rc001_hash_drift_fails_closed(self) -> None:
        policy = copy.deepcopy(dict(self.policy))
        policy["rc001_freeze"]["required_definition_sha256"][
            "RC001-H13-COMPOSITE-VETO"
        ] = "0" * 64
        with self.assertRaises(CaptureIntegrityError):
            execute_target(
                repo_root=ROOT,
                policy=policy,
                compact_scan={"pool_owned_mints": [], "create_mints": [], "bonding_curves": []},
            )

    def test_holdout_and_rc001_bytes_are_unmutated(self) -> None:
        result = execute_target(
            repo_root=ROOT,
            policy=self.policy,
            compact_scan={
                "pool_owned_mints": [],
                "create_mints": [],
                "bonding_curves": [],
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
        self.assertEqual(result["trial"]["outcome"], "INCONCLUSIVE")

    def test_resolver_fingerprint_is_stable(self) -> None:
        first = resolver_fingerprint(self.policy)
        second = resolver_fingerprint(load_policy(CONFIG_PATH))
        self.assertEqual(first, second)
        self.assertEqual(FAMILY, "H11_LIFECYCLE_CLOCK")

    def test_live_a22_scan_matches_committed_target_when_a4_present(self) -> None:
        a22 = ROOT / self.policy["adopted_route"]["a22_raw"]["path"]
        if not a22.is_file():
            # DELIVERY_PREFLIGHT_NONCRITICAL_SKIP: docs/evidence/task38/a1_h11_next_gta_target_runtime_receipt_v1.json
            self.skipTest("A4 local A22 bytes absent")
        result = execute_target(repo_root=ROOT, policy=self.policy)
        self.assertTrue(result["live_universe"])
        self.assertEqual(result["terminal_decision"], self.fixture["expected_live_terminal"])
        self.assertEqual(result["named_target"]["kind"], self.fixture["expected_target_kind"])
        self.assertEqual(
            result["named_target"]["address"],
            self.fixture["expected_target_address"],
        )
        self.assertEqual(result["scan"]["create_events"], 0)
        self.assertEqual(result["scan"]["pump_program_in_account_keys"], 0)
        self.assertEqual(result["scan"]["transaction_count"], 520)
        self.assertGreater(result["scan"]["incidental_mint_count"], 1)
        self.assertFalse(result["network_authorized"])
        self.assertEqual(result["side_effects"]["provider_requests"], 0)
        self.assertNotEqual(result["named_target"]["address"], PUMP_PROGRAM_ID)
        self.assertNotEqual(result["named_target"]["address"], self.pool)


if __name__ == "__main__":
    unittest.main()
