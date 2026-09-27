"""Temporal proxy through classify_lane and DocumentRunner. No caller row hooks."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.document_runner import (  # noqa: E402
    DocumentRunner,
    RunContext,
    repository_git_snapshot,
)
from solana_alpha_lab.factory.lane_classifier import classify_lane  # noqa: E402
from solana_alpha_lab.factory.operational_store import OperationalStore  # noqa: E402
from solana_alpha_lab.factory.research_store import ResearchStore  # noqa: E402
from solana_alpha_lab.factory.hfic_temporal_discovery import (  # noqa: E402
    canonical_temporal_spec,
)
from tests.test_fast_lane_classifier import (  # noqa: E402
    AS_OF,
    HYPOTHESIS_DEFINITION_SHA256,
)
from tests.test_fast_lane_runner import offline_v1_1_spec, publish_commissioning_dataset  # noqa: E402
from tests.test_hfic_temporal_discovery_v1 import (  # noqa: E402
    _binding,
    _census,
    _path,
    _spec,
)

ROOT = Path(__file__).resolve().parents[1]


class TemporalProductionRunnerTests(unittest.TestCase):
    def test_classify_and_document_runner_complete_offline(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            data_root = Path(raw)
            publish_commissioning_dataset(data_root)
            census = [_census("runner-mint")]
            observations = _path(
                "runner-mint",
                [1.0, 1.5, 2.0, 1.6],
                (10000.0, 9000.0),
                1.92,
            )
            folder = data_root / "datasets" / "temporal_fixed_time_proxy"
            folder.mkdir(parents=True)
            census_path = folder / "census.parquet"
            observations_path = folder / "observations.parquet"
            pq.write_table(pa.Table.from_pylist(census), census_path)
            pq.write_table(pa.Table.from_pylist(observations), observations_path)
            binding = _binding()
            binding[0]["census_sha256"] = hashlib.sha256(census_path.read_bytes()).hexdigest()
            binding[0]["observations_sha256"] = hashlib.sha256(observations_path.read_bytes()).hexdigest()
            binding[0]["census_rel"] = "datasets/temporal_fixed_time_proxy/census.parquet"
            binding[0]["observations_rel"] = "datasets/temporal_fixed_time_proxy/observations.parquet"
            (folder / "binding.json").write_text(
                json.dumps({"cohorts": binding}),
                encoding="utf-8",
            )
            recipe_spec = canonical_temporal_spec(_spec(cost_profile=None))
            spec = offline_v1_1_spec()
            spec["capability_id"] = "CAP-HFIC-TEMPORAL-FIXED-TIME-PROXY-001"
            spec["capabilities"] = ["CAP-HFIC-TEMPORAL-FIXED-TIME-PROXY-001"]
            spec["parameters"] = {
                "temporal_recipe": {
                    "scientific_identity": recipe_spec["spec_sha256"],
                    "spec": recipe_spec,
                }
            }
            decision = classify_lane(
                {
                    "experiment_spec": spec,
                    "hypothesis_definition_sha256": HYPOTHESIS_DEFINITION_SHA256,
                },
                root=ROOT,
                data_root=data_root,
                as_of=AS_OF,
            )
            self.assertEqual(decision.terminal, "FAST_LANE_READY", decision.reason_codes)
            ops = OperationalStore(data_root / "ops" / "operational_state.sqlite")
            try:
                runner = DocumentRunner(root=ROOT, store=ops)
                before = repository_git_snapshot(ROOT)
                result = runner.start_document(
                    spec,
                    spec_sha256="ab" * 32,
                    run_context=RunContext(
                        data_root=data_root,
                        hypothesis_definition_sha256=HYPOTHESIS_DEFINITION_SHA256,
                        lane_decision=decision,
                    ),
                )
                after = repository_git_snapshot(ROOT)
            finally:
                ops.close()
            self.assertEqual(result["status"], "COMPLETE", result)
            self.assertEqual(result["provider_calls_actual"], 0)
            self.assertEqual(result["git_mutation_count"], 0)
            self.assertTrue(before.unchanged(after))
            self.assertIsNotNone(result["run_id_or_null"])
            stored = list(ResearchStore(data_root).iter_committed_records())
            self.assertTrue(stored)


if __name__ == "__main__":
    unittest.main()
