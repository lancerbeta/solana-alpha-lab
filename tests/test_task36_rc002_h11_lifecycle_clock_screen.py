from __future__ import annotations

import copy
import json
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

from solana_alpha_lab.task36_h11_lifecycle_clock_screen import (  # noqa: E402
    ATOM_ID,
    FAMILY,
    H11Error,
    H11IntegrityError,
    OutcomeGuard,
    TERMINAL_OUTCOMES,
    TRIAL_ID,
    chronological_group_split,
    decision_time_features,
    execute_screen,
    freeze_cohort,
    load_policy,
    protocol_fingerprint,
    running_peak_at_decision,
)

CONFIG_PATH = ROOT / "configs/task36_rc002_h11_lifecycle_clock_screen_v1.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/task36_rc002_h11_lifecycle_clock_screen.schema.json"
FIXTURE_PATH = ROOT / "tests/fixtures/task36/h11_lifecycle_clock_screen_v1.json"
RC001_PATH = ROOT / "configs/task28_rc001_registry_freeze_v1.yaml"
HOLDOUT_PATH = ROOT / "registries/holdout_consumption.yaml"


def _epoch(stamp: str) -> int:
    return int(datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp())


def _row(
    *,
    index: int,
    migration_offset: int,
    decision_offset: int,
    hour: int,
    outcome: str,
    extra_future_peak: bool = False,
) -> dict[str, object]:
    day = "2026-08-01" if index % 2 == 0 else "2026-08-02"
    migration = _epoch(f"{day}T{hour:02d}:00:00Z") + migration_offset
    decision = migration + decision_offset
    events = [
        {"event_at": migration + 10, "price": 1.0},
        {"event_at": migration + 20, "price": 2.0},
        {"event_at": decision, "price": 1.5},
    ]
    if extra_future_peak:
        events.append({"event_at": decision + 60, "price": 99.0})
    return {
        "row_id": f"R{index:02d}",
        "pool_id": f"P{index % 8:02d}",
        "deployer_id": f"D{index % 4:02d}",
        "day_id": day,
        "migration_at": migration,
        "decision_time": decision,
        "events": events,
        "outcome": outcome,
    }


def positive_cohort() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index in range(24):
        early = index < 12
        rows.append(
            _row(
                index=index,
                migration_offset=0,
                decision_offset=60 if early else 4000,
                hour=4 if index % 3 == 0 else (12 if index % 3 == 1 else 20),
                outcome="CONTINUATION" if early else "FAST_DEATH",
            )
        )
    return rows


def negative_cohort() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index in range(24):
        eu = index % 2 == 0
        rows.append(
            _row(
                index=index,
                migration_offset=0,
                decision_offset=60 if index % 3 == 0 else 4000,
                hour=12 if eu else 4,
                outcome="CONTINUATION" if eu else "FAST_DEATH",
            )
        )
    return rows


def small_cohort() -> list[dict[str, object]]:
    return [
        _row(
            index=index,
            migration_offset=0,
            decision_offset=60,
            hour=12,
            outcome="CONTINUATION",
        )
        for index in range(3)
    ]


class Task36H11LifecycleClockScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = load_policy(CONFIG_PATH)
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_policy_matches_closed_schema(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(
            yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        )
        self.assertEqual(self.policy["atom_id"], ATOM_ID)
        self.assertEqual(tuple(self.policy["terminal_outcomes"]), TERMINAL_OUTCOMES)
        self.assertEqual(self.policy["screen_protocol"]["family"], FAMILY)

    def test_protocol_fingerprint_is_stable_before_outcomes(self) -> None:
        first = protocol_fingerprint(self.policy)
        second = protocol_fingerprint(load_policy(CONFIG_PATH))
        self.assertEqual(first, second)
        self.assertEqual(len(first), 64)

    def test_live_universe_is_historical_route_inadequate(self) -> None:
        result = execute_screen(repo_root=ROOT, policy=self.policy)
        self.assertEqual(
            result["terminal_decision"],
            self.fixture["expected_live_terminal"],
        )
        self.assertTrue(result["live_universe"])
        self.assertEqual(result["cohort"]["n"], 0)
        self.assertFalse(result["inventory"]["migration_clock_reconstructable"])
        self.assertEqual(result["trial"]["record_id"], TRIAL_ID)
        self.assertEqual(result["trial"]["outcome"], "INCONCLUSIVE")
        self.assertFalse(result["live_PIT_claim"])
        self.assertFalse(result["execution_claim"])
        self.assertFalse(result["rc001_mutated"])
        self.assertFalse(result["holdout_consumed"])

    def test_trial_is_pending_before_outcome_inspection(self) -> None:
        pending = execute_screen(
            repo_root=ROOT,
            policy=self.policy,
            cohort_rows=positive_cohort(),
            inspect_outcomes=False,
        )
        self.assertEqual(pending["trial"]["outcome"], "PENDING")
        self.assertIsNone(pending["terminal_decision"])
        guard = OutcomeGuard(positive_cohort())
        with self.assertRaises(H11Error):
            guard.inspect()
        guard.register_trial()
        inspected = guard.inspect()
        self.assertEqual(len(inspected), 24)

    def test_decision_time_features_ignore_future_peak(self) -> None:
        row = _row(
            index=0,
            migration_offset=0,
            decision_offset=120,
            hour=12,
            outcome="CONTINUATION",
            extra_future_peak=True,
        )
        protocol = self.policy["screen_protocol"]
        features = decision_time_features(row, protocol)
        self.assertEqual(features["peak_state"], "OBSERVED")
        self.assertEqual(features["time_since_decision_time_running_peak"], 100)
        decision = int(row["decision_time"])
        peak_at, _state = running_peak_at_decision(list(row["events"]), decision)
        self.assertEqual(peak_at, int(row["migration_at"]) + 20)

    def test_missing_migration_stays_typed_and_not_zero(self) -> None:
        row = _row(
            index=0,
            migration_offset=0,
            decision_offset=60,
            hour=12,
            outcome="FAST_DEATH",
        )
        row["migration_at"] = None
        features = decision_time_features(row, self.policy["screen_protocol"])
        self.assertIsNone(features["time_since_migration"])
        self.assertEqual(features["time_since_migration_bin"], "MISSING_UNKNOWN")
        self.assertIn("MIGRATION_AT_MISSING", features["missingness"])
        row["time_since_migration"] = 0
        with self.assertRaises(H11Error):
            decision_time_features(row, self.policy["screen_protocol"])

    def test_cohort_freeze_is_outcome_independent(self) -> None:
        base = positive_cohort()
        flipped = copy.deepcopy(base)
        for row in flipped:
            row["outcome"] = (
                "FAST_DEATH" if row["outcome"] == "CONTINUATION" else "CONTINUATION"
            )
        first = freeze_cohort(base, self.policy["screen_protocol"])
        second = freeze_cohort(flipped, self.policy["screen_protocol"])
        self.assertEqual(first["fingerprint"], second["fingerprint"])
        self.assertEqual(first["row_ids"], second["row_ids"])

    def test_split_is_chronological_and_group_aware(self) -> None:
        early, late = chronological_group_split(positive_cohort())
        early_groups = {str(row["deployer_id"]) for row in early}
        late_groups = {str(row["deployer_id"]) for row in late}
        self.assertFalse(early_groups & late_groups)

    def test_positive_synthetic_earns_prospective_confirmation(self) -> None:
        result = execute_screen(
            repo_root=ROOT,
            policy=self.policy,
            cohort_rows=positive_cohort(),
        )
        self.assertFalse(result["live_universe"])
        self.assertEqual(
            result["terminal_decision"],
            "H11_SCREEN_POSITIVE_EARNS_PROSPECTIVE_CONFIRMATION",
        )
        self.assertEqual(result["trial"]["outcome"], "PASS")

    def test_negative_synthetic_deprioritizes(self) -> None:
        result = execute_screen(
            repo_root=ROOT,
            policy=self.policy,
            cohort_rows=negative_cohort(),
        )
        self.assertEqual(
            result["terminal_decision"],
            "H11_SCREEN_NEGATIVE_DEPRIORITIZE_OR_CLOSE",
        )
        self.assertEqual(result["trial"]["outcome"], "FAIL")

    def test_small_n_is_inconclusive_data_scale(self) -> None:
        result = execute_screen(
            repo_root=ROOT,
            policy=self.policy,
            cohort_rows=small_cohort(),
        )
        self.assertEqual(
            result["terminal_decision"],
            "H11_SCREEN_INCONCLUSIVE_DATA_SCALE",
        )
        self.assertEqual(result["trial"]["outcome"], "INCONCLUSIVE")

    def test_rc001_hash_drift_fails_closed(self) -> None:
        policy = copy.deepcopy(dict(self.policy))
        policy["rc001_freeze"]["required_definition_sha256"][
            "RC001-H13-COMPOSITE-VETO"
        ] = "0" * 64
        with self.assertRaises(H11IntegrityError):
            execute_screen(repo_root=ROOT, policy=policy)

    def test_holdout_and_rc001_bytes_are_unmutated(self) -> None:
        result = execute_screen(repo_root=ROOT, policy=self.policy)
        freeze = yaml.safe_load(RC001_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            freeze["hypothesis_groups"][0]["definition_sha256"],
            result["rc001_freeze"]["definition_sha256"]["RC001-H13-COMPOSITE-VETO"],
        )
        holdout = yaml.safe_load(HOLDOUT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(holdout["records"], [])
        self.assertEqual(result["holdout"]["records"], 0)

    def test_module_and_runner_have_no_network_imports(self) -> None:
        module = (
            ROOT / "src/solana_alpha_lab/task36_h11_lifecycle_clock_screen.py"
        ).read_text(encoding="utf-8")
        runner = (
            ROOT / "scripts/run_task36_rc002_h11_lifecycle_clock_screen.py"
        ).read_text(encoding="utf-8")
        for blob in (module, runner):
            self.assertNotIn("import urllib", blob)
            self.assertNotIn("import requests", blob)
            self.assertNotIn("import http.client", blob)
            self.assertNotIn("import socket", blob)
