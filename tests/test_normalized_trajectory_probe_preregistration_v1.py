from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SRC = ROOT / "src"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.collector_schedulability_oracle import (  # noqa: E402
    ALLOWED_X_POINTS,
    DEFAULT_LIFECYCLE_Y_SECONDS,
    PREFERRED_X_SECONDS,
)
from solana_alpha_lab.factory.early_market_panel_importer import (  # noqa: E402
    MIN_USABLE_YIELD_ELIGIBLE,
)
from solana_alpha_lab.factory.hfic_preflight import MAX_PACKET_BYTES  # noqa: E402
from solana_alpha_lab.factory.hfic_session import PROMPT_VERSION  # noqa: E402
from solana_alpha_lab.factory.live_cohort_discovery_release import (  # noqa: E402
    CORPUS_DATASET_ID,
    LIVE_EVIDENCE_ROLE,
)
from solana_alpha_lab.factory.tokens_v2_typed_projection import (  # noqa: E402
    FIELD_TO_FAMILY,
    TOKENS_V2_FIELD_KINDS,
)
from solana_alpha_lab.factory_semantic_operability import (  # noqa: E402
    load_semantic_catalog_views,
    load_semantic_projection,
    resolve_semantic_route,
    search_semantic_routes,
)
from validate_catalog import load_and_validate  # noqa: E402

CONTRACT_PATH = ROOT / "docs/contracts/normalized_trajectory_representation_probe_v1.md"
TOKENS_V2_PATH = ROOT / "src/solana_alpha_lab/factory/tokens_v2_typed_projection.py"


def _load_frozen_contract() -> dict:
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    match = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n", text, re.DOTALL)
    if match is None:
        raise AssertionError("FROZEN_CONTRACT_FRONT_MATTER_MISSING")
    payload = yaml.safe_load(match.group(1))
    if not isinstance(payload, dict):
        raise AssertionError("FROZEN_CONTRACT_NOT_MAPPING")
    return payload


class NormalizedTrajectoryProbePreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = _load_frozen_contract()
        cls.snapshot = load_and_validate(allow_generated_drift=True)
        cls.projection = load_semantic_projection(ROOT)
        cls.assets, cls.bindings, _queries = load_semantic_catalog_views(ROOT)

    def test_frozen_identity_and_scientific_fences(self) -> None:
        frozen = self.contract
        self.assertEqual(
            frozen["preregistration_id"],
            "NORMALIZED_TRAJECTORY_PROBE_PREREGISTRATION_V1",
        )
        self.assertEqual(frozen["probe_id"], "NORMALIZED_TRAJECTORY_V1")
        self.assertEqual(frozen["probe_kind"], "REPRESENTATION_CHALLENGER")
        self.assertEqual(frozen["probe_state"], "PREREGISTERED_NOT_EXECUTED")
        self.assertIs(frozen["auto_execute_after_cohort_import"], False)
        self.assertEqual(frozen["implementation_status"], "CONTRACT_ONLY")
        self.assertIs(frozen["projection_code_implemented"], False)
        self.assertIs(frozen["current_live_cohort_scientific_content_accessed"], False)
        self.assertIs(frozen["confirmatory_reuse_forbidden"], True)
        self.assertEqual(frozen["evidence_role"], "EXPLORATORY_REUSE")
        self.assertEqual(frozen["evidence_role"], LIVE_EVIDENCE_ROLE)
        self.assertEqual(frozen["corpus_dataset_id"], CORPUS_DATASET_ID)
        self.assertEqual(frozen["cohort_normalization"], "OFF")
        self.assertIs(frozen["scores_pnl"], False)
        self.assertEqual(frozen["new_novelty_scorer"], "forbidden")
        self.assertEqual(frozen["ninth_family_workaround"], "forbidden")

    def test_binds_current_hfic_and_yield_constants(self) -> None:
        self.assertEqual(self.contract["hfic_prompt_family"], PROMPT_VERSION)
        self.assertEqual(self.contract["max_packet_bytes"], MAX_PACKET_BYTES)
        self.assertEqual(
            self.contract["min_usable_yield_eligible"],
            MIN_USABLE_YIELD_ELIGIBLE,
        )
        self.assertEqual(MIN_USABLE_YIELD_ELIGIBLE, 10)

    def test_field_ids_exist_and_taker_is_not_invented(self) -> None:
        fields = self.contract["fields"]
        expected = {
            "PRICE": "FIELD-USD-PRICE-001",
            "LIQUIDITY": "FIELD-LIQUIDITY-USD-001",
            "VOLUME_PRIMARY": "FIELD-STATS5M-TAKER-VOLUME-001",
            "VOLUME_FALLBACK_BUY": "FIELD-STATS5M-BUY-VOLUME-001",
            "VOLUME_FALLBACK_SELL": "FIELD-STATS5M-SELL-VOLUME-001",
            "TRADERS": "FIELD-STATS5M-NUM-TRADERS-001",
        }
        for logical_id, field_id in expected.items():
            self.assertEqual(fields[logical_id]["field_id"], field_id)
            self.assertIn(field_id, TOKENS_V2_FIELD_KINDS)
            self.assertIn(field_id, FIELD_TO_FAMILY)
        self.assertIs(fields["VOLUME_PRIMARY"]["never_infer_from_buy_sell"], True)
        self.assertEqual(
            fields["VOLUME_PRIMARY"]["excluded_reason_if_invented"],
            "TAKER_VOLUME_NOT_INFERRED_FROM_BUY_SELL",
        )
        source = TOKENS_V2_PATH.read_text(encoding="utf-8")
        self.assertIn("TAKER_VOLUME_NOT_INFERRED_FROM_BUY_SELL", source)
        channel = self.contract["volume_channel_rule"]
        self.assertIs(channel["never_sum_buy_plus_sell_into_one_series"], True)
        self.assertEqual(
            channel["else_if_buy_and_sell_observed"],
            "ACTIVITY_VOLUME_OBSERVED_BUY_PLUS_SELL",
        )
        for forbidden in self.contract["forbidden_probe1_fields"]:
            if str(forbidden).startswith("FIELD-"):
                self.assertIn(forbidden, TOKENS_V2_FIELD_KINDS)

    def test_motif_keeps_exact_zero_flat_without_snooping(self) -> None:
        motif = self.contract["motif"]
        self.assertEqual(motif["alphabet"], ["U", "F", "D", "M"])
        self.assertEqual(motif["flat_threshold"], "EXACT_ZERO_CHANGE_ONLY")
        self.assertEqual(motif["epsilon_flat_band"], "forbidden")
        self.assertEqual(motif["outcome_tuned_threshold"], "forbidden")
        self.assertEqual(self.contract["time"]["interpolation"], "forbidden")
        self.assertEqual(
            self.contract["time"]["substitute_event_time_if_clock_missing"],
            "forbidden",
        )
        self.assertEqual(self.contract["pit"]["imputation"], "forbidden")

    def test_pass_kill_invalid_are_distinct(self) -> None:
        self.assertEqual(
            self.contract["pass_code"],
            "NORMALIZED_TRAJECTORY_REPRESENTATION_PROBE_PASS",
        )
        self.assertEqual(
            self.contract["kill_code"],
            "NORMALIZED_TRAJECTORY_REPRESENTATION_PROBE_KILL",
        )
        invalid = set(self.contract["invalid_codes"])
        self.assertIn("INVALID_GROUNDING_BOUNDARY", invalid)
        self.assertIn("INVALID_PACKET_BUDGET", invalid)
        self.assertIn("INVALID_INSUFFICIENT_PREFIX", invalid)
        self.assertEqual(
            self.contract["control_terminals_permit_probe"],
            ["NO_WORTHY_HYPOTHESIS", "KILL_DUPLICATE_OR_PREVIOUSLY_CLOSED"],
        )
        self.assertEqual(
            self.contract["time"]["decision_t_point_id"],
            "Y1800",
        )
        self.assertEqual(self.contract["time"]["decision_t_due_offset_seconds"], 1800)
        self.assertEqual(
            self.contract["time"]["schedule_shape"],
            "one_x_point_plus_declared_y_points",
        )
        self.assertIs(
            self.contract["time"]["x_selection_menu_is_not_collected_prefix"],
            True,
        )
        self.assertEqual(
            self.contract["time"]["preferred_x_due_offset_seconds"],
            PREFERRED_X_SECONDS,
        )
        self.assertEqual(
            set(self.contract["time"]["x_selection_menu_seconds"]),
            set(ALLOWED_X_POINTS),
        )
        self.assertEqual(
            tuple(self.contract["time"]["declared_y_due_offset_seconds"]),
            DEFAULT_LIFECYCLE_Y_SECONDS,
        )
        self.assertEqual(self.contract["time"]["min_motif_steps"], 2)
        self.assertEqual(self.contract["time"]["min_prefix_slots"], 3)
        self.assertEqual(
            self.contract["time"]["drop_slot_when_clock_missing"],
            "forbidden",
        )
        self.assertEqual(
            self.contract["challenger"]["packet_surgery"],
            "REPLACE_WITHIN_EXISTING_TRUNCATION",
        )
        self.assertEqual(
            self.contract["control_terminal_else"],
            "INVALID_TRIGGER_NOT_MET",
        )
        self.assertEqual(
            self.contract["case_e"]["code"],
            "INVALID_GROUNDING_BOUNDARY",
        )
        self.assertIs(self.contract["control_run_required_first"], True)
        self.assertIs(self.contract["one_registered_trial"], True)
        self.assertEqual(self.contract["after_pass_does_not_mean"], "alpha_exists")
        self.assertEqual(len(self.contract["pass_requires_all"]), 5)
        self.assertGreaterEqual(len(self.contract["kill_if_any"]), 5)

    def test_no_projection_implementation_landed(self) -> None:
        src = ROOT / "src"
        matches = [
            str(path.relative_to(ROOT).as_posix())
            for path in src.rglob("*")
            if path.is_file()
            and (
                "normalized_trajectory" in path.name
                or "trajectory_projection" in path.name
                or "motif_encoder" in path.name
            )
        ]
        self.assertEqual(matches, [])
        self.assertFalse(
            (
                ROOT / "src/solana_alpha_lab/factory/normalized_trajectory_v1.py"
            ).exists()
        )

    def test_discoverable_from_hypothesis_forge_route(self) -> None:
        hits = search_semantic_routes(
            self.projection,
            "normalized trajectory",
            assets=self.assets,
            bindings=self.bindings,
            limit=5,
        )
        assert isinstance(hits, list)
        self.assertTrue(hits)
        self.assertEqual(hits[0]["semantic_route_id"], "SEM-HYPOTHESIS-FORGE")
        self.assertIs(hits[0]["authority_granted"], False)
        resolved = resolve_semantic_route(
            self.projection,
            "SEM-HYPOTHESIS-FORGE",
            assets=self.assets,
            bindings=self.bindings,
        )
        root_ids = [item["asset_id"] for item in resolved["root_assets"]]
        self.assertNotIn(
            "CONTRACT-NORMALIZED-TRAJECTORY-REPRESENTATION-PROBE-001",
            root_ids,
        )
        self.assertEqual(resolved["forge_visibility"], "EXCLUDE")
        record = self.snapshot.assets[
            "CONTRACT-NORMALIZED-TRAJECTORY-REPRESENTATION-PROBE-001"
        ]
        self.assertEqual(
            record["location"]["repository_path"],
            "docs/contracts/normalized_trajectory_representation_probe_v1.md",
        )
        self.assertEqual(
            record["status"],
            "ACCEPTED_DIRECTION_NOT_IMPLEMENTED",
        )


if __name__ == "__main__":
    unittest.main()
