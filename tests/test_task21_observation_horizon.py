from __future__ import annotations

import copy
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task21_observation_horizon import (
    EXPECTED_OFFSETS,
    NEXT_ATOM,
    ObservationHorizonError,
    build_correction_plan,
    canonical_json_bytes,
    materialize_capture_schedule,
    sha256_file,
    validate_policy,
)


POLICY_PATH = ROOT / "configs" / "task21_observation_horizon_policy_v1.yaml"
ACCEPTANCE_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task21"
    / "observation_horizon_policy_acceptance_v1.json"
)
CONSUMER_RECONCILIATION_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task21"
    / "observation_horizon_consumer_reconciliation_acceptance_v1.json"
)
EFFECTIVE_AT = datetime(
    2026,
    7,
    30,
    22,
    30,
    2,
    46_000,
    tzinfo=timezone.utc,
)


class TestTask21ObservationHorizon(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))

    def test_policy_validates_against_exact_preserved_source(self) -> None:
        validate_policy(self.policy, repository_root=ROOT)

    def test_p7d_is_retained_but_not_an_exclusive_wait(self) -> None:
        plan = build_correction_plan(
            self.policy,
            repository_root=ROOT,
            as_of=EFFECTIVE_AT,
        )
        self.assertEqual(
            plan["verdict"],
            "P7D_EXCLUSIVE_WAIT_SUPERSEDED_FORWARD_ONLY",
        )
        self.assertTrue(plan["original_gate"]["retained_as_horizon"])
        self.assertEqual(
            plan["capture_clock"]["wait_before_first_capture"],
            "NONE",
        )

    def test_outcome_blind_truth_is_preserved(self) -> None:
        truth = build_correction_plan(
            self.policy,
            repository_root=ROOT,
            as_of=EFFECTIVE_AT,
        )["protected_truth"]
        self.assertEqual(truth["nominations"], 3)
        self.assertEqual(truth["admissions"], 0)
        self.assertEqual(truth["panels"], 0)
        self.assertFalse(truth["backdating"])
        self.assertFalse(truth["historical_rewrite"])
        self.assertFalse(truth["outcomes_observed_before_correction"])

    def test_horizons_are_multi_scale_and_deterministic(self) -> None:
        schedule = materialize_capture_schedule(
            self.policy,
            repository_root=ROOT,
            first_authorized_capture_at=EFFECTIVE_AT,
        )
        self.assertEqual(
            tuple(window["offset_seconds"] for window in schedule),
            EXPECTED_OFFSETS,
        )
        self.assertEqual(schedule[0]["scheduled_at"], "2026-07-30T22:30:02.046Z")
        self.assertEqual(schedule[-1]["scheduled_at"], "2026-08-06T22:30:02.046Z")

    def test_capture_cannot_be_backdated_before_correction(self) -> None:
        with self.assertRaisesRegex(
            ObservationHorizonError,
            "capture_before_correction",
        ):
            materialize_capture_schedule(
                self.policy,
                repository_root=ROOT,
                first_authorized_capture_at=datetime(
                    2026,
                    7,
                    30,
                    22,
                    30,
                    2,
                    45_000,
                    tzinfo=timezone.utc,
                ),
            )

    def test_missing_window_is_not_silently_rescheduled(self) -> None:
        clock = self.policy["capture_clock"]
        self.assertEqual(
            clock["missed_window_policy"],
            "RETAIN_EXPLICIT_GAP_NO_BACKFILL",
        )
        self.assertFalse(clock["reschedule_after_miss"])

    def test_next_boundary_grants_no_external_authority(self) -> None:
        boundary = build_correction_plan(
            self.policy,
            repository_root=ROOT,
            as_of=EFFECTIVE_AT,
        )["next_boundary"]
        self.assertEqual(boundary["atom_id"], NEXT_ATOM)
        self.assertFalse(boundary["external_authority_granted"])

    def test_any_authority_leak_fails_closed(self) -> None:
        changed = copy.deepcopy(self.policy)
        changed["next_boundary"]["provider_api_rpc_wss_calls_authorized"] = True
        with self.assertRaisesRegex(
            ObservationHorizonError,
            "authority_leak",
        ):
            validate_policy(changed, repository_root=ROOT)

    def test_plan_is_deterministic(self) -> None:
        first = build_correction_plan(
            self.policy,
            repository_root=ROOT,
            as_of=EFFECTIVE_AT,
        )
        second = build_correction_plan(
            self.policy,
            repository_root=ROOT,
            as_of=EFFECTIVE_AT,
        )
        self.assertEqual(canonical_json_bytes(first), canonical_json_bytes(second))

    def test_historical_acceptance_and_current_consumer_reconciliation_bind(
        self,
    ) -> None:
        receipt = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(
            receipt["verdict"],
            "P7D_EXCLUSIVE_WAIT_SUPERSEDED_FORWARD_ONLY",
        )
        historical_core = receipt["artifacts"][:3]
        self.assertEqual(
            [artifact["path"] for artifact in historical_core],
            [
                "configs/task21_observation_horizon_policy_v1.yaml",
                "docs/contracts/task21_observation_horizon_policy_contract_v1.md",
                "src/solana_alpha_lab/task21_observation_horizon.py",
            ],
        )
        for artifact in historical_core:
            self.assertEqual(
                sha256_file(ROOT / artifact["path"]),
                artifact["sha256"],
                artifact["path"],
            )
        reconciliation = json.loads(
            CONSUMER_RECONCILIATION_PATH.read_text(encoding="utf-8")
        )
        self.assertEqual(
            sha256_file(CONSUMER_RECONCILIATION_PATH),
            "083781cdffee14fa6edd3f60d350a1073f991b0888f8bdbb77fae7d994cc5a22",
        )
        self.assertEqual(reconciliation["status"], "PASS")
        self.assertEqual(
            reconciliation["verdict"],
            "HISTORICAL_HORIZON_RECEIPT_PRESERVED_CURRENT_CONSUMERS_REBOUND",
        )
        for protected_input in reconciliation["protected_inputs"]:
            self.assertEqual(
                sha256_file(ROOT / protected_input["path"]),
                protected_input["sha256"],
                protected_input["path"],
            )
        current = json.loads(
            (
                ROOT
                / "docs"
                / "evidence"
                / "task21"
                / "owner_pulse_post_h6_sentinel_rebase_acceptance_v2.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            current["verdict"],
            "OWNER_PULSE_H24_MINIMUM_AGE_H72_H168_TRIGGER_ONLY",
        )
        for key, value in receipt["actual_actions"].items():
            if key == "scheduler_or_background_process":
                self.assertFalse(value)
            else:
                self.assertEqual(value, 0, key)
        self.assertFalse(receipt["catalog"]["version_or_count_advanced"])


if __name__ == "__main__":
    unittest.main()
