from __future__ import annotations

import json
import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.lane_classifier import Lane, LaneDecision, classify_lane


AS_OF = datetime(2026, 8, 25, tzinfo=UTC)
OFFLINE_CAPABILITY = "CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001"
LIVE_CAPABILITY = "CAP-FIXTURE-PROVIDER-READ-ONLY-001"
GIT_WRITING_CAPABILITY = "CAP-FIXTURE-GIT-RECEIPT-WRITER-001"
DATA_BINDING_ID = "BINDING-CANONICAL-RECEIPT-001"


def experiment_spec(*, capability_id: str = OFFLINE_CAPABILITY) -> dict[str, object]:
    return {
        "schema": "smial.experiment-spec",
        "schema_version": "1.1",
        "experiment_id": "EXP-HYPOTHESIS-FAST-LANE-001",
        "hypothesis_version": "HYP-VERSION-FAST-LANE-V1",
        "question": "Does the accepted offline receipt support this falsifier?",
        "estimand": "Typed terminal agreement",
        "population": "Accepted canonical receipt fixture",
        "data_requirements": [
            {
                "requirement_id": "CANONICAL_RECEIPT",
                "kind": "CATALOG_ASSET",
                "path": "catalog/catalog_manifest.yaml",
                "sha256": "0" * 64,
            }
        ],
        "capabilities": [capability_id],
        "falsifier": "The typed terminal does not agree",
        "method": "classify_audition_terminal",
        "parameters": {},
        "evidence_budget": {
            "provider_api_rpc_wss_calls": 1 if capability_id == LIVE_CAPABILITY else 0
        },
        "holdout_policy": "No holdout is opened by classification",
        "terminal_outcomes": ["SUPPORTED", "FALSIFIED", "INCONCLUSIVE"],
        "data_bindings": [
            {
                "binding_id": DATA_BINDING_ID,
                "source_kind": "CATALOG_ASSET",
                "stable_id": "SCHEMA-EXPERIMENT-SPEC-001",
                "expected_content_sha256_or_dataset_fingerprint": "a" * 64,
            }
        ],
        "query_recipe_ids": [],
        "capability_id": capability_id,
        "parameter_schema_asset_id": "SCHEMA-EXPERIMENT-SPEC-001",
        "as_of": "2026-08-25T00:00:00Z",
        "availability_cutoff": "2026-08-25T00:00:00Z",
        "what_changed": ["INITIAL_FAST_LANE_FIXTURE"],
    }


def submission(
    *,
    capability_id: str = OFFLINE_CAPABILITY,
    available: bool = True,
    promotion_requested: bool = False,
    completed_runs: dict[str, str] | None = None,
) -> dict[str, object]:
    return {
        "experiment_spec": experiment_spec(capability_id=capability_id),
        "available_data_binding_ids": [DATA_BINDING_ID] if available else [],
        "completed_runs": dict(completed_runs or {}),
        "promotion_requested": promotion_requested,
    }


class FastLaneContractTests(unittest.TestCase):
    def classify(self, packet: dict[str, object]) -> LaneDecision:
        with tempfile.TemporaryDirectory() as tmp:
            return classify_lane(
                packet,
                root=ROOT,
                data_root=Path(tmp),
                as_of=AS_OF,
            )

    def test_v1_1_schema_preserves_v1_fields_and_validates_fast_lane_fixture(self) -> None:
        schema = json.loads(
            (ROOT / "catalog/schemas/experiment_spec_v1_1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        jsonschema.validate(experiment_spec(), schema)
        self.assertEqual(schema["properties"]["schema_version"]["const"], "1.1")
        for required in (
            "data_requirements",
            "capabilities",
            "data_bindings",
            "query_recipe_ids",
            "capability_id",
            "parameter_schema_asset_id",
            "as_of",
            "availability_cutoff",
            "what_changed",
        ):
            self.assertIn(required, schema["required"])

    def test_capability_registry_descriptors_validate_and_freeze_required_fixtures(
        self,
    ) -> None:
        descriptor_schema = json.loads(
            (
                ROOT / "catalog/schemas/experiment_capability_descriptor.schema.json"
            ).read_text(encoding="utf-8")
        )
        registry = yaml.safe_load(
            (ROOT / "configs/experiment_capability_registry_v1.yaml").read_text(
                encoding="utf-8"
            )
        )
        descriptors = {
            item["capability_id"]: item for item in registry["capabilities"]
        }
        for descriptor in descriptors.values():
            jsonschema.validate(descriptor, descriptor_schema)
        self.assertEqual(descriptors[OFFLINE_CAPABILITY]["status"], "ACCEPTED")
        self.assertEqual(
            descriptors[OFFLINE_CAPABILITY]["effect_class"], "OFFLINE_READ_ONLY"
        )
        self.assertEqual(
            descriptors[OFFLINE_CAPABILITY]["output_zone"], "DATA_ROOT_ONLY"
        )
        self.assertEqual(
            descriptors[GIT_WRITING_CAPABILITY]["output_zone"], "GIT_REPOSITORY"
        )
        self.assertEqual(
            descriptors[LIVE_CAPABILITY]["effect_class"],
            "PROVIDER_READ_ONLY_BOUNDED",
        )

    def test_fast_lane_config_is_logical_and_freezes_two_rung(self) -> None:
        config = yaml.safe_load(
            (ROOT / "configs/hypothesis_fast_lane_v1.yaml").read_text(
                encoding="utf-8"
            )
        )
        rendered = json.dumps(config, sort_keys=True)
        self.assertEqual(
            config["two_rung_live_h900_v1"]["status"],
            "FROZEN_PENDING_FAST_LANE",
        )
        self.assertEqual(config["foundation_authority"]["provider_calls"], 0)
        self.assertEqual(
            config["writer_lease_policy"], "CREATE_EXCLUSIVE_SINGLE_WRITER_V1"
        )
        self.assertNotIn("C:\\", rendered)
        self.assertNotIn("/Users/", rendered)
        self.assertNotIn("/home/", rendered)
        self.assertNotIn("SMIAL_DATA_ROOT:", rendered)

    def test_lane_decision_is_frozen(self) -> None:
        decision = self.classify(submission())
        with self.assertRaises(FrozenInstanceError):
            decision.terminal = "MUTATED"  # type: ignore[misc]

    def test_existing_offline_capability_is_fast_lane(self) -> None:
        decision = self.classify(submission())
        self.assertIs(decision.lane, Lane.FAST_LANE)
        self.assertEqual(decision.terminal, "FAST_LANE_READY")
        self.assertEqual(decision.reason_codes, ())
        self.assertIsNotNone(decision.run_key_sha256)
        self.assertIsNone(decision.prior_run_id)

    def test_owner_gated_live_capability_requires_authority_without_calling_provider(
        self,
    ) -> None:
        decision = self.classify(submission(capability_id=LIVE_CAPABILITY))
        self.assertIs(decision.lane, Lane.FAST_LANE)
        self.assertEqual(decision.terminal, "FAST_LANE_OWNER_GATE_REQUIRED")
        self.assertEqual(decision.reason_codes, ("OWNER_AUTHORITY_REQUIRED",))

    def test_missing_capability_requires_change_lane(self) -> None:
        decision = self.classify(
            submission(capability_id="CAP-FIXTURE-NOT-REGISTERED-001")
        )
        self.assertIs(decision.lane, Lane.CHANGE_LANE)
        self.assertEqual(decision.terminal, "CHANGE_LANE_CAPABILITY_GAP")
        self.assertEqual(decision.reason_codes, ("CAPABILITY_NOT_REGISTERED",))

    def test_repo_writing_capability_requires_change_lane(self) -> None:
        decision = self.classify(submission(capability_id=GIT_WRITING_CAPABILITY))
        self.assertIs(decision.lane, Lane.CHANGE_LANE)
        self.assertEqual(decision.terminal, "CHANGE_LANE_CAPABILITY_GAP")
        self.assertEqual(decision.reason_codes, ("OUTPUT_SINK_NOT_DATA_PLANE",))

    def test_invalid_spec_is_denied_before_other_lanes(self) -> None:
        packet = submission(
            capability_id="CAP-FIXTURE-NOT-REGISTERED-001",
            promotion_requested=True,
        )
        del packet["experiment_spec"]["estimand"]  # type: ignore[index]
        decision = self.classify(packet)
        self.assertIs(decision.lane, Lane.DENY)
        self.assertEqual(decision.terminal, "DENY_INVALID_SPEC")

    def test_missing_immutable_binding_is_blocked_data(self) -> None:
        decision = self.classify(submission(available=False))
        self.assertIs(decision.lane, Lane.FAST_LANE)
        self.assertEqual(decision.terminal, "BLOCKED_DATA")
        self.assertEqual(decision.reason_codes, ("DATA_BINDING_UNAVAILABLE",))

    def test_exact_duplicate_returns_replay_available(self) -> None:
        first = self.classify(submission())
        assert first.run_key_sha256 is not None
        duplicate = submission(
            completed_runs={first.run_key_sha256: "RUN-0123456789ABCDEF01234567"}
        )
        decision = self.classify(duplicate)
        self.assertIs(decision.lane, Lane.FAST_LANE)
        self.assertEqual(decision.terminal, "REPLAY_AVAILABLE")
        self.assertEqual(decision.prior_run_id, "RUN-0123456789ABCDEF01234567")

    def test_promotion_request_cannot_enter_fast_lane(self) -> None:
        decision = self.classify(submission(promotion_requested=True))
        self.assertIs(decision.lane, Lane.PROMOTION_LANE)
        self.assertEqual(decision.terminal, "PROMOTION_LANE_REQUIRED")
        self.assertEqual(decision.reason_codes, ("PROMOTION_REQUESTED",))


if __name__ == "__main__":
    unittest.main()
