from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.experiment_spec import validate_experiment_document
from solana_alpha_lab.factory.observation_schedule import (
    ObservationScheduleError,
    load_observation_schedule,
    schedule_sha256,
    validate_observation_schedule,
)


class ObservationScheduleSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = json.loads(
            (ROOT / "catalog/schemas/observation_schedule_v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.fixture = yaml.safe_load(
            (ROOT / "tests/fixtures/observation_schedule/common_panel.yaml").read_text(
                encoding="utf-8"
            )
        )

    def test_valid_fixture_compiles(self) -> None:
        loaded = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/common_panel.yaml"
        )
        self.assertEqual(loaded["schedule_sha256"], schedule_sha256(self.fixture))
        jsonschema.validate(self.fixture, self.schema)

    def test_unknown_field_rejected(self) -> None:
        payload = copy.deepcopy(self.fixture)
        payload["url"] = "https://evil.example/x"
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(payload, self.schema)

    def test_duplicate_y_rejected(self) -> None:
        payload = copy.deepcopy(self.fixture)
        payload["y_points"].append(copy.deepcopy(payload["y_points"][0]))
        with self.assertRaises(ObservationScheduleError):
            validate_observation_schedule(payload, root=ROOT)

    def test_unordered_y_rejected(self) -> None:
        payload = copy.deepcopy(self.fixture)
        payload["y_points"] = list(reversed(payload["y_points"]))
        with self.assertRaises(ObservationScheduleError):
            validate_observation_schedule(payload, root=ROOT)

    def test_more_than_eight_y_rejected(self) -> None:
        payload = copy.deepcopy(self.fixture)
        last = payload["y_points"][-1]
        for index in range(9, 14):
            item = copy.deepcopy(last)
            item["point_id"] = f"Y{index}"
            item["due_offset_seconds"] = int(last["due_offset_seconds"]) + index
            payload["y_points"].append(item)
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(payload, self.schema)

    def test_offset_beyond_30_days_rejected(self) -> None:
        payload = copy.deepcopy(self.fixture)
        payload["y_points"][-1]["due_offset_seconds"] = 2592001
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(payload, self.schema)

    def test_relative_y_rejected(self) -> None:
        payload = copy.deepcopy(self.fixture)
        payload["y_points"][0]["relative_to"] = "X300"
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(payload, self.schema)

    def test_arbitrary_url_rejected(self) -> None:
        payload = copy.deepcopy(self.fixture)
        payload["population"]["source_predicates"][0]["value_text"] = "https://evil.example"
        with self.assertRaises(ObservationScheduleError) as raised:
            validate_observation_schedule(payload, root=ROOT)
        self.assertEqual(str(raised.exception), "DENY_UNSAFE_RUNTIME_CODE")

    def test_unknown_is_zero_forbidden(self) -> None:
        payload = copy.deepcopy(self.fixture)
        payload["missingness"]["unknown_is_zero"] = True
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(payload, self.schema)

    def test_retry_budget_forbidden(self) -> None:
        payload = copy.deepcopy(self.fixture)
        payload["budgets"]["retry"] = True
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(payload, self.schema)

    def test_legacy_v1_1_still_validates(self) -> None:
        document = {
            "schema": "smial.experiment-spec",
            "schema_version": "1.1",
            "experiment_id": "EXP-HYPOTHESIS-FAST-LANE-001",
            "hypothesis_version": "HYP-VERSION-FAST-LANE-V1",
            "question": "Does the accepted offline receipt support this falsifier?",
            "estimand": "Typed terminal agreement",
            "population": "Accepted canonical receipt fixture",
            "data_requirements": [
                {
                    "requirement_id": "REQ-CANONICAL-RECEIPT",
                    "kind": "CATALOG_ASSET",
                    "path": "catalog/schemas/experiment_spec.schema.json",
                    "sha256": "a" * 64,
                }
            ],
            "capabilities": ["CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001"],
            "falsifier": "Replay diverges from the accepted receipt.",
            "method": "receipt-replay",
            "parameters": {},
            "evidence_budget": {"provider_api_rpc_wss_calls": 0},
            "holdout_policy": "No holdout is consumed.",
            "terminal_outcomes": ["RETAINED"],
            "data_bindings": [
                {
                    "binding_id": "BINDING-CANONICAL-RECEIPT-001",
                    "source_kind": "CATALOG_ASSET",
                    "stable_id": "SCHEMA-EXPERIMENT-SPEC-001",
                    "expected_content_sha256_or_dataset_fingerprint": "a" * 64,
                }
            ],
            "query_recipe_ids": [],
            "capability_id": "CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
            "parameter_schema_asset_id": "SCHEMA-EXPERIMENT-SPEC-001",
            "as_of": "2026-08-25T00:00:00Z",
            "availability_cutoff": "2026-08-25T00:00:00Z",
            "what_changed": ["FAST_LANE_FOUNDATION"],
        }
        validate_experiment_document(document, root=ROOT)


if __name__ == "__main__":
    unittest.main()
