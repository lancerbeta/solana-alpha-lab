from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.experiment_spec import (  # noqa: E402
    ExperimentSpecError,
    load_experiment_spec,
    validate_experiment_document,
)
from solana_alpha_lab.factory.lane_classifier import Lane, classify_lane  # noqa: E402
from solana_alpha_lab.factory.operational_store import OperationalStore  # noqa: E402
from solana_alpha_lab.factory.research_store import ResearchStore  # noqa: E402
from solana_alpha_lab.factory.runner import (  # noqa: E402
    ExperimentRunner,
    RunContext,
    repository_status_bytes,
)
from tests.test_fast_lane_classifier import (  # noqa: E402
    AS_OF,
    CATALOG_ASSET_CONTENT_SHA256,
    DATA_BINDING_ID,
    HYPOTHESIS_DEFINITION_SHA256,
    OFFLINE_CAPABILITY,
    experiment_spec,
    submission,
)


GOLDEN_OFFLINE = (
    "configs/experiment_specs/quote_native_admissible_friction_audition_offline_v1.yaml"
)
LEGACY_SPEC = (
    "configs/experiment_specs/quote_native_admissible_friction_audition_offline_v1.yaml"
)


def offline_v1_1_spec() -> dict[str, object]:
    base = yaml.safe_load((ROOT / GOLDEN_OFFLINE).read_text(encoding="utf-8"))
    base["schema_version"] = "1.1"
    base["data_bindings"] = [
        {
            "binding_id": DATA_BINDING_ID,
            "source_kind": "CATALOG_ASSET",
            "stable_id": "SCHEMA-EXPERIMENT-SPEC-001",
            "expected_content_sha256_or_dataset_fingerprint": (
                CATALOG_ASSET_CONTENT_SHA256
            ),
        }
    ]
    base["query_recipe_ids"] = []
    base["capability_id"] = OFFLINE_CAPABILITY
    base["parameter_schema_asset_id"] = "SCHEMA-EXPERIMENT-SPEC-001"
    base["as_of"] = "2026-08-25T00:00:00Z"
    base["availability_cutoff"] = "2026-08-25T00:00:00Z"
    base["what_changed"] = ["INITIAL_FAST_LANE_FIXTURE"]
    return base


class FastLaneRunnerTests(unittest.TestCase):
    @contextmanager
    def isolated_runner(self, data_root: Path):
        ops = OperationalStore(data_root / "ops" / "operational_state.sqlite")
        try:
            yield ExperimentRunner(root=ROOT, store=ops)
        finally:
            ops.close()

    def classify_for(
        self,
        data_root: Path,
        packet: dict[str, object],
    ) -> tuple[dict[str, object], object]:
        decision = classify_lane(
            packet,
            root=ROOT,
            data_root=data_root,
            as_of=AS_OF,
        )
        return packet, decision

    def test_legacy_repository_spec_still_loads(self) -> None:
        spec = load_experiment_spec(ROOT, LEGACY_SPEC)
        self.assertEqual(spec["schema_version"], "1.0")

    def test_validate_experiment_document_accepts_v1_1(self) -> None:
        validated = validate_experiment_document(
            offline_v1_1_spec(),
            root=ROOT,
        )
        self.assertEqual(validated["schema_version"], "1.1")

    def test_validate_experiment_document_rejects_invalid(self) -> None:
        invalid = offline_v1_1_spec()
        del invalid["estimand"]  # type: ignore[index]
        with self.assertRaises(ExperimentSpecError):
            validate_experiment_document(invalid, root=ROOT)

    def test_offline_document_run_does_not_mutate_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            with self.isolated_runner(data_root) as runner:
                spec = offline_v1_1_spec()
                packet, decision = self.classify_for(
                    data_root,
                    {
                        "experiment_spec": spec,
                        "hypothesis_definition_sha256": HYPOTHESIS_DEFINITION_SHA256,
                    },
                )
                self.assertEqual(decision.terminal, "FAST_LANE_READY")
                before = repository_status_bytes(ROOT)
                result = runner.start_document(
                    spec,
                    spec_sha256=hashlib.sha256(
                        yaml.safe_dump(spec, sort_keys=True).encode("utf-8")
                    ).hexdigest(),
                    run_context=RunContext(
                        data_root=data_root,
                        hypothesis_definition_sha256=HYPOTHESIS_DEFINITION_SHA256,
                        lane_decision=decision,
                    ),
                )
                after = repository_status_bytes(ROOT)
                self.assertEqual(result["status"], "COMPLETE")
                self.assertEqual(before, after)
                self.assertEqual(result["git_mutation_count"], 0)
                self.assertEqual(result["provider_calls_actual"], 0)
                self.assertIsNotNone(result["run_id_or_null"])

    def test_capability_gap_does_not_execute(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            with self.isolated_runner(data_root) as runner:
                packet, decision = self.classify_for(
                    data_root,
                    submission(capability_id="CAP-FIXTURE-NOT-REGISTERED-001"),
                )
                self.assertIs(decision.lane, Lane.CHANGE_LANE)
                result = runner.start_document(
                    packet["experiment_spec"],  # type: ignore[arg-type]
                    spec_sha256="0" * 64,
                    run_context=RunContext(
                        data_root=data_root,
                        hypothesis_definition_sha256=HYPOTHESIS_DEFINITION_SHA256,
                        lane_decision=decision,
                    ),
                )
                self.assertEqual(result["provider_calls_actual"], 0)
                self.assertEqual(result["git_mutation_count"], 0)
                self.assertIsNone(result["run_id_or_null"])

    def test_owner_gate_missing_phrase_makes_zero_provider_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            with self.isolated_runner(data_root) as runner:
                packet, decision = self.classify_for(
                    data_root,
                    submission(capability_id="CAP-FIXTURE-PROVIDER-READ-ONLY-001"),
                )
                self.assertEqual(decision.terminal, "FAST_LANE_OWNER_GATE_REQUIRED")
                result = runner.start_document(
                    packet["experiment_spec"],  # type: ignore[arg-type]
                    spec_sha256="0" * 64,
                    run_context=RunContext(
                        data_root=data_root,
                        hypothesis_definition_sha256=HYPOTHESIS_DEFINITION_SHA256,
                        lane_decision=decision,
                    ),
                )
                self.assertEqual(result["status"], "BLOCKED_AUTHORITY")
                self.assertEqual(result["provider_calls_actual"], 0)

    def test_git_mutation_detected_without_auto_revert(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            with self.isolated_runner(data_root) as runner:
                packet, decision = self.classify_for(data_root, submission())
                with patch(
                    "solana_alpha_lab.factory.runner.repository_status_bytes",
                    side_effect=[b"", b"M"],
                ):
                    result = runner.start_document(
                        packet["experiment_spec"],  # type: ignore[arg-type]
                        spec_sha256="0" * 64,
                        run_context=RunContext(
                            data_root=data_root,
                            hypothesis_definition_sha256=HYPOTHESIS_DEFINITION_SHA256,
                            lane_decision=decision,
                        ),
                    )
                self.assertEqual(result["git_mutation_count"], 1)
                self.assertEqual(result["reason_codes"], ["GIT_MUTATION_DETECTED"])
                self.assertEqual(result["scientific_terminal"], "INVALID")

    def test_completed_run_is_persisted_outside_git(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            with self.isolated_runner(data_root) as runner:
                spec = offline_v1_1_spec()
                _, decision = self.classify_for(
                    data_root,
                    {
                        "experiment_spec": spec,
                        "hypothesis_definition_sha256": HYPOTHESIS_DEFINITION_SHA256,
                    },
                )
                result = runner.start_document(
                    spec,
                    spec_sha256="0" * 64,
                    run_context=RunContext(
                        data_root=data_root,
                        hypothesis_definition_sha256=HYPOTHESIS_DEFINITION_SHA256,
                        lane_decision=decision,
                    ),
                )
            store = ResearchStore(data_root)
            passport = store.find_completed_run(str(result["run_key_sha256"]))
            self.assertIsNotNone(passport)
            self.assertEqual(passport.run_id, result["run_id_or_null"])  # type: ignore[union-attr]

    def test_legacy_start_path_still_works(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.isolated_runner(Path(tmp)) as runner:
                result = runner.start(LEGACY_SPEC)
                self.assertIn(
                    result["status"],
                    {"COMPLETE", "FAILED", "BLOCKED_DATA"},
                )


if __name__ == "__main__":
    unittest.main()
