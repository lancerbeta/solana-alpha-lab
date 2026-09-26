"""FAST_LANE_READY requires the frozen definition hash. A bare spec is unbound."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.hfic_session import (  # noqa: E402
    HficSessionError,
    run_live_classifier,
)
from tests.test_fast_lane_classifier import experiment_spec  # noqa: E402
from tests.test_hfic_packet14_availability_fast_lane_guard_v1 import (  # noqa: E402
    HISTORICAL_FEAT,
    _freeze,
    _selected,
)

PIT_LABEL = "HFIC-V12-C1-PIT-LIQUIDITY-RATIO"
RUNNER_LABEL = "HFIC-V12-C3-FORWARD-QUOTE"
FOREIGN_VERSION = "HYP-FOREIGN-NOT-THE-CANDIDATE"


def _pit_frozen() -> dict:
    return _freeze(PIT_LABEL, RUNNER_LABEL)


def _foreign_spec(frozen: dict, feature_ids: list[str]) -> dict:
    spec = experiment_spec()
    spec["hypothesis_version"] = FOREIGN_VERSION
    spec["required_feature_ids"] = list(feature_ids)
    return spec


class FastLaneDefinitionHashBindTests(unittest.TestCase):
    def test_a_bare_spec_is_hypothesis_definition_unbound(self) -> None:
        frozen = _pit_frozen()
        selected = _selected(frozen)
        spec = _foreign_spec(frozen, list(selected["required_feature_ids"]))
        with self.assertRaises(HficSessionError) as raised:
            run_live_classifier(
                {"experiment_spec": spec},
                frozen,
                repo_root=ROOT,
                data_root=ROOT,
            )
        self.assertEqual(str(raised.exception), "HYPOTHESIS_DEFINITION_UNBOUND")

    def test_b_matching_hash_keeps_pit_ready_and_records_spec_version(self) -> None:
        frozen = _pit_frozen()
        selected = _selected(frozen)
        spec = _foreign_spec(frozen, list(selected["required_feature_ids"]))
        receipt = run_live_classifier(
            {
                "experiment_spec": spec,
                "hypothesis_definition_sha256": frozen["selected_definition_sha256"],
            },
            frozen,
            repo_root=ROOT,
            data_root=ROOT,
        )
        self.assertEqual(receipt["lane_classifier_terminal"], "FAST_LANE_READY")
        self.assertEqual(receipt["hypothesis_version"], FOREIGN_VERSION)
        self.assertNotEqual(receipt["hypothesis_version"], frozen["selected_candidate_id"])

    def test_c_feature_id_mismatch_stays_grounding_mismatch(self) -> None:
        frozen = _pit_frozen()
        spec = _foreign_spec(frozen, [HISTORICAL_FEAT])
        with self.assertRaises(HficSessionError) as raised:
            run_live_classifier(
                {
                    "experiment_spec": spec,
                    "hypothesis_definition_sha256": frozen["selected_definition_sha256"],
                },
                frozen,
                repo_root=ROOT,
                data_root=ROOT,
            )
        self.assertEqual(str(raised.exception), "EXPERIMENT_SPEC_GROUNDING_MISMATCH")


if __name__ == "__main__":
    unittest.main()
