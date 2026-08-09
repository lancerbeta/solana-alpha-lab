from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task30_birdeye_route_hold_forward_capture_decision import (  # noqa: E402
    BirdeyeRouteHoldForwardCaptureError,
    evaluate_birdeye_route_hold_forward_capture,
)


CONFIG_PATH = ROOT / "configs/task30_birdeye_route_hold_forward_capture_decision_v1.yaml"
SCHEMA_PATH = (
    ROOT / "catalog/schemas/task30_birdeye_route_hold_forward_capture_decision.schema.json"
)
FIXTURE_PATH = (
    ROOT / "tests/fixtures/task30/birdeye_route_hold_forward_capture_decision_v1.json"
)


def replace_pointer(record: dict[str, object], pointer: str, replacement: object) -> None:
    target: dict[str, object] = record
    parts = pointer.split(".")
    for part in parts[:-1]:
        target = target[part]  # type: ignore[assignment,index]
    target[parts[-1]] = replacement


class Task30BirdeyeRouteHoldForwardCaptureDecisionTests(unittest.TestCase):
    def test_evaluates_only_one_offline_hold_and_forward_capture_decision(self) -> None:
        """Catches a different result replacing the bounded offline decision."""
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

        self.assertFalse(list(Draft202012Validator(schema).iter_errors(policy)))
        self.assertEqual(
            evaluate_birdeye_route_hold_forward_capture(policy),
            fixture["expected_result"],
        )

    def test_rejects_route_pool_cadence_and_authority_widening(self) -> None:
        """Catches auto-retry, broad collection and live-capture promotion."""
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        cases = (
            ("birdeye_route.state", "RETRY_NOW", "BIRDEYE_AUTORETRY_FORBIDDEN"),
            (
                "forward_capture_candidate.pool_address",
                "another-pool",
                "POOL_EXPANSION_FORBIDDEN",
            ),
            ("forward_capture_candidate.slot_seconds", 60, "CADENCE_DRIFT"),
            (
                "forward_capture_candidate.max_observation_slots",
                97,
                "SLOT_CAP_DRIFT",
            ),
            (
                "forward_capture_candidate.provider_selection",
                "BIRDEYE",
                "PROVIDER_PROMOTION_FORBIDDEN",
            ),
            (
                "authority.provider_api_rpc_wss_calls",
                1,
                "EXTERNAL_AUTHORITY_FORBIDDEN",
            ),
            (
                "authority.scheduler_or_background_process",
                True,
                "SCHEDULER_ACTIVATION_FORBIDDEN",
            ),
            (
                "non_claims.explicit_no_trade_claim",
                True,
                "PROMOTION_CLAIM_FORBIDDEN",
            ),
            ("decision", "START_CAPTURE_NOW", "DECISION_PROMOTION_FORBIDDEN"),
        )
        for pointer, replacement, expected_error in cases:
            with self.subTest(pointer=pointer):
                candidate = copy.deepcopy(policy)
                replace_pointer(candidate, pointer, replacement)
                with self.assertRaisesRegex(
                    BirdeyeRouteHoldForwardCaptureError, expected_error
                ):
                    evaluate_birdeye_route_hold_forward_capture(candidate)

    def test_rejects_credential_like_keys_anywhere_in_the_policy(self) -> None:
        """Catches a credential-like field hidden in a nominally offline policy."""
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        policy["birdeye_route"]["api_key"] = "synthetic-only"
        with self.assertRaisesRegex(
            BirdeyeRouteHoldForwardCaptureError, "CREDENTIAL_DISCLOSURE_FORBIDDEN"
        ):
            evaluate_birdeye_route_hold_forward_capture(policy)
