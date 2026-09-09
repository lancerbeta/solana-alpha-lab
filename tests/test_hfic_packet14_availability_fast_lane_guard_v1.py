from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.hfic_control_integrity import (  # noqa: E402
    CURRENT_REPRESENTATION_CONTROL_V1,
    KILL_UNBOUND_EVIDENCE,
    PIT_READY_AVAILABILITY_CLASS,
    control_packet_has_raw_sequences,
    deny_non_pit_fast_lane,
    deny_unresolved_fast_lane,
)
from solana_alpha_lab.factory.hfic_identity import IDENTITY_FIELDS  # noqa: E402
from solana_alpha_lab.factory.hfic_memory_policy import search_identity_sha256  # noqa: E402
from solana_alpha_lab.factory.hfic_session import (  # noqa: E402
    CRITIC_PACKET_VERSION_CURRENT,
    HficSessionError,
    PROMPT_VERSION,
    _classifier_to_hfic_terminal,
    freeze_draft,
    run_live_classifier,
)
from tests.test_fast_lane_classifier import experiment_spec  # noqa: E402
from tests.test_hfic_session import _preflight_receipt  # noqa: E402

DRAFT_V12 = ROOT / "tests/fixtures/hypothesis_forge/draft_v1_2_valid.json"
CONTEXT_SHA = "ab" * 32
PIT_FEAT = "FEAT-TOKEN-LIQUIDITY-USD-TO-MCAP-RATIO"
FORWARD_FEAT = "FEAT-QUOTE-AVAILABILITY"
HISTORICAL_FEAT = "FEAT-RETURN-15M"
MISSING_FEAT = "FEAT-AGE-SINCE-CREATION"
MISSING_CAP_FEAT = "FEAT-CREATOR-CLUSTER-SHARE"


def _draft() -> dict:
    return json.loads(DRAFT_V12.read_text(encoding="utf-8"))


def _grounded_preflight() -> dict:
    receipt = dict(_preflight_receipt())
    receipt["forge_context_packet_sha256"] = CONTEXT_SHA
    receipt["forge_context_packet"] = {
        "capability_ids": ["CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001"]
    }
    return receipt


def _freeze_draft(draft: dict) -> dict:
    return freeze_draft(
        draft,
        preflight_receipt=_grounded_preflight(),
        repo_root=ROOT,
    )


def _freeze(
    selected: str,
    runner_up: str,
    *,
    required_feature_ids: list[str] | None = None,
) -> dict:
    draft = _draft()
    if required_feature_ids is not None:
        for card in draft["candidates"]:
            if card["label"] == selected:
                card["required_feature_ids"] = list(required_feature_ids)
                card["unresolved_requirements"] = []
    draft["selected_candidate_ref"] = selected
    draft["runner_up_candidate_ref"] = runner_up
    return _freeze_draft(draft)


def _spec_for(feat_ids: list[str]) -> dict:
    spec = experiment_spec()
    spec["required_feature_ids"] = list(feat_ids)
    return spec


def _classify(frozen: dict, spec: dict) -> dict:
    return run_live_classifier(
        {"experiment_spec": spec},
        frozen,
        repo_root=ROOT,
        data_root=ROOT,
    )


def _selected(frozen: dict) -> dict:
    return frozen["critic_input_packet"]["selected_candidate"]


def _mutate_selected(frozen: dict, mutator) -> dict:
    cloned = copy.deepcopy(frozen)
    mutator(cloned["critic_input_packet"]["selected_candidate"])
    return cloned


def _lane_decision(terminal: str) -> mock.Mock:
    return mock.Mock(
        terminal=terminal,
        lane=mock.Mock(value="FAST_LANE"),
        reason_codes=[],
        next_action="PAUSE",
    )


def _mocked_classify(frozen: dict, spec: dict, terminal: str) -> dict:
    with mock.patch(
        "solana_alpha_lab.factory.lane_classifier.classify_lane",
        return_value=_lane_decision(terminal),
    ):
        return _classify(frozen, spec)


class AvailabilityFastLaneGuardTests(unittest.TestCase):
    def test_t1_pit_ready_survives_to_pass_fast_lane(self) -> None:
        frozen = _freeze(
            "HFIC-V12-C1-PIT-LIQUIDITY-RATIO",
            "HFIC-V12-C3-FORWARD-QUOTE",
        )
        selected = _selected(frozen)
        self.assertEqual(
            frozen["critic_input_packet"]["packet_version"],
            CRITIC_PACKET_VERSION_CURRENT,
        )
        self.assertEqual(
            selected["grounding"]["feature_bindings"][0]["availability_class"],
            PIT_READY_AVAILABILITY_CLASS,
        )
        receipt = _classify(frozen, _spec_for(selected["required_feature_ids"]))
        self.assertEqual(receipt["lane_classifier_terminal"], "FAST_LANE_READY")
        self.assertEqual(
            _classifier_to_hfic_terminal(receipt),
            "PASS_FAST_LANE_READY",
        )

    def test_t2_forward_only_denied(self) -> None:
        frozen = _freeze(
            "HFIC-V12-C3-FORWARD-QUOTE",
            "HFIC-V12-C2-HISTORICAL-RETURN",
        )
        selected = _selected(frozen)
        self.assertEqual(
            selected["grounding"]["feature_bindings"][0]["availability_class"],
            "FORWARD_ONLY",
        )
        with self.assertRaises(HficSessionError) as raised:
            _classify(frozen, _spec_for(selected["required_feature_ids"]))
        self.assertEqual(str(raised.exception), KILL_UNBOUND_EVIDENCE)

    def test_t3_historical_reconstructible_denied(self) -> None:
        frozen = _freeze(
            "HFIC-V12-C2-HISTORICAL-RETURN",
            "HFIC-V12-C3-FORWARD-QUOTE",
        )
        selected = _selected(frozen)
        self.assertEqual(
            selected["grounding"]["feature_bindings"][0]["availability_class"],
            "HISTORICAL_RECONSTRUCTIBLE",
        )
        with self.assertRaises(HficSessionError) as raised:
            _classify(frozen, _spec_for(selected["required_feature_ids"]))
        self.assertEqual(str(raised.exception), KILL_UNBOUND_EVIDENCE)

    def test_t4_missing_denied(self) -> None:
        frozen = _freeze(
            "HFIC-V12-C1-PIT-LIQUIDITY-RATIO",
            "HFIC-V12-C3-FORWARD-QUOTE",
            required_feature_ids=[MISSING_FEAT],
        )
        selected = _selected(frozen)
        self.assertEqual(selected["required_feature_ids"], [MISSING_FEAT])
        self.assertEqual(
            selected["grounding"]["feature_bindings"][0]["availability_class"],
            "MISSING",
        )
        with self.assertRaises(HficSessionError) as raised:
            _classify(frozen, _spec_for(selected["required_feature_ids"]))
        self.assertEqual(str(raised.exception), KILL_UNBOUND_EVIDENCE)

    def test_t5_missing_capability_denied(self) -> None:
        frozen = _freeze(
            "HFIC-V12-C1-PIT-LIQUIDITY-RATIO",
            "HFIC-V12-C3-FORWARD-QUOTE",
            required_feature_ids=[MISSING_CAP_FEAT],
        )
        selected = _selected(frozen)
        self.assertEqual(
            selected["grounding"]["feature_bindings"][0]["availability_class"],
            "MISSING_CAPABILITY",
        )
        with self.assertRaises(HficSessionError) as raised:
            _classify(frozen, _spec_for(selected["required_feature_ids"]))
        self.assertEqual(str(raised.exception), KILL_UNBOUND_EVIDENCE)

    def test_t6_partial_denied(self) -> None:
        frozen = _freeze(
            "HFIC-V12-C1-PIT-LIQUIDITY-RATIO",
            "HFIC-V12-C3-FORWARD-QUOTE",
        )
        mutated = _mutate_selected(
            frozen,
            lambda selected: selected["grounding"]["feature_bindings"][0].__setitem__(
                "availability_class",
                "PARTIAL",
            ),
        )
        with self.assertRaises(HficSessionError) as raised:
            _classify(mutated, _spec_for(_selected(mutated)["required_feature_ids"]))
        self.assertEqual(str(raised.exception), KILL_UNBOUND_EVIDENCE)

    def test_t7_unknown_class_fail_closed(self) -> None:
        frozen = _freeze(
            "HFIC-V12-C1-PIT-LIQUIDITY-RATIO",
            "HFIC-V12-C3-FORWARD-QUOTE",
        )
        mutated = _mutate_selected(
            frozen,
            lambda selected: selected["grounding"]["feature_bindings"][0].__setitem__(
                "availability_class",
                "FUTURE_STRATEGY_USABLE",
            ),
        )
        with self.assertRaises(HficSessionError) as raised:
            _classify(mutated, _spec_for(_selected(mutated)["required_feature_ids"]))
        self.assertEqual(str(raised.exception), KILL_UNBOUND_EVIDENCE)

    def test_t8_replay_available_non_pit_denied(self) -> None:
        cases = (
            ("HFIC-V12-C3-FORWARD-QUOTE", "HFIC-V12-C2-HISTORICAL-RETURN"),
            ("HFIC-V12-C2-HISTORICAL-RETURN", "HFIC-V12-C3-FORWARD-QUOTE"),
        )
        for selected_ref, runner in cases:
            frozen = _freeze(selected_ref, runner)
            selected = _selected(frozen)
            with self.assertRaises(HficSessionError) as raised:
                _mocked_classify(
                    frozen,
                    _spec_for(selected["required_feature_ids"]),
                    "REPLAY_AVAILABLE",
                )
            self.assertEqual(str(raised.exception), KILL_UNBOUND_EVIDENCE)
            mapped = _classifier_to_hfic_terminal(
                {"lane_classifier_terminal": "REPLAY_AVAILABLE"}
            )
            self.assertEqual(mapped, "PASS_FAST_LANE_READY")

    def test_t9_mixed_pit_and_forward_denied(self) -> None:
        frozen = _freeze(
            "HFIC-V12-C1-PIT-LIQUIDITY-RATIO",
            "HFIC-V12-C3-FORWARD-QUOTE",
            required_feature_ids=[PIT_FEAT, FORWARD_FEAT],
        )
        selected = _selected(frozen)
        classes = {
            item["feature_id"]: item["availability_class"]
            for item in selected["grounding"]["feature_bindings"]
        }
        self.assertEqual(classes[PIT_FEAT], PIT_READY_AVAILABILITY_CLASS)
        self.assertEqual(classes[FORWARD_FEAT], "FORWARD_ONLY")
        with self.assertRaises(HficSessionError) as raised:
            _classify(frozen, _spec_for(selected["required_feature_ids"]))
        self.assertEqual(str(raised.exception), KILL_UNBOUND_EVIDENCE)

    def test_t10_missing_binding_denied(self) -> None:
        frozen = _freeze(
            "HFIC-V12-C1-PIT-LIQUIDITY-RATIO",
            "HFIC-V12-C3-FORWARD-QUOTE",
        )
        mutated = _mutate_selected(
            frozen,
            lambda selected: selected["grounding"].__setitem__(
                "feature_bindings",
                [],
            ),
        )
        with self.assertRaises(HficSessionError) as raised:
            _classify(mutated, _spec_for(_selected(mutated)["required_feature_ids"]))
        self.assertEqual(str(raised.exception), KILL_UNBOUND_EVIDENCE)

    def test_t11_duplicate_binding_denied(self) -> None:
        frozen = _freeze(
            "HFIC-V12-C1-PIT-LIQUIDITY-RATIO",
            "HFIC-V12-C3-FORWARD-QUOTE",
        )

        def duplicate(selected: dict) -> None:
            bindings = selected["grounding"]["feature_bindings"]
            bindings.append(copy.deepcopy(bindings[0]))

        mutated = _mutate_selected(frozen, duplicate)
        with self.assertRaises(HficSessionError) as raised:
            _classify(mutated, _spec_for(_selected(mutated)["required_feature_ids"]))
        self.assertEqual(str(raised.exception), KILL_UNBOUND_EVIDENCE)

    def test_t12_extra_unrelated_binding_cannot_weaken(self) -> None:
        frozen = _freeze(
            "HFIC-V12-C1-PIT-LIQUIDITY-RATIO",
            "HFIC-V12-C3-FORWARD-QUOTE",
        )
        extra = {
            "feature_id": FORWARD_FEAT,
            "availability_class": "FORWARD_ONLY",
            "available_to_strategy_semantics": "HISTORICAL_CAPTURE_NOT_STRATEGY_AVAILABLE",
        }
        mutated = _mutate_selected(
            frozen,
            lambda selected: selected["grounding"]["feature_bindings"].append(extra),
        )
        receipt = _classify(mutated, _spec_for(_selected(mutated)["required_feature_ids"]))
        self.assertEqual(receipt["lane_classifier_terminal"], "FAST_LANE_READY")
        salvaged = _freeze(
            "HFIC-V12-C3-FORWARD-QUOTE",
            "HFIC-V12-C2-HISTORICAL-RETURN",
        )
        extra_pit = {
            "feature_id": PIT_FEAT,
            "availability_class": PIT_READY_AVAILABILITY_CLASS,
            "available_to_strategy_semantics": "BOUNDED_PIT_READY_EXPLICIT_SCOPE",
        }
        mutated_forward = _mutate_selected(
            salvaged,
            lambda selected: selected["grounding"]["feature_bindings"].append(extra_pit),
        )
        with self.assertRaises(HficSessionError) as raised:
            _classify(
                mutated_forward,
                _spec_for(_selected(mutated_forward)["required_feature_ids"]),
            )
        self.assertEqual(str(raised.exception), KILL_UNBOUND_EVIDENCE)

    def test_t13_non_fast_lanes_unchanged(self) -> None:
        frozen = _freeze(
            "HFIC-V12-C3-FORWARD-QUOTE",
            "HFIC-V12-C2-HISTORICAL-RETURN",
        )
        selected = _selected(frozen)
        spec = _spec_for(selected["required_feature_ids"])
        mapping = {
            "CHANGE_LANE_CAPABILITY_GAP": "PASS_CHANGE_LANE_REQUIRED",
            "BLOCKED_DATA": "PASS_DATA_OPTION_REQUIRED",
            "FAST_LANE_OWNER_GATE_REQUIRED": "OWNER_DECISION_REQUIRED",
        }
        for classifier_terminal, hfic_terminal in mapping.items():
            deny_non_pit_fast_lane(selected, classifier_terminal)
            receipt = _mocked_classify(frozen, spec, classifier_terminal)
            self.assertEqual(receipt["lane_classifier_terminal"], classifier_terminal)
            self.assertEqual(_classifier_to_hfic_terminal(receipt), hfic_terminal)

    def test_t14_unresolved_only_guard_unchanged(self) -> None:
        frozen = _freeze(
            "HFIC-V12-C4-UNRESOLVED-CREATOR-CLUSTER",
            "HFIC-V12-C3-FORWARD-QUOTE",
        )
        selected = _selected(frozen)
        self.assertEqual(selected["required_feature_ids"], [])
        self.assertEqual(selected["grounding"]["terminal"], "GROUNDED_WITH_GAPS")
        deny_non_pit_fast_lane(selected, "FAST_LANE_READY")
        deny_non_pit_fast_lane(selected, "REPLAY_AVAILABLE")
        with self.assertRaises(ValueError) as raised:
            deny_unresolved_fast_lane(selected, "FAST_LANE_READY")
        self.assertEqual(str(raised.exception), KILL_UNBOUND_EVIDENCE)
        spec = experiment_spec()
        with mock.patch(
            "solana_alpha_lab.factory.experiment_spec.validate_experiment_document",
            return_value=spec,
        ), mock.patch(
            "solana_alpha_lab.factory.lane_classifier.classify_lane",
            return_value=_lane_decision("FAST_LANE_READY"),
        ), mock.patch(
            "solana_alpha_lab.factory.run_passport.experiment_spec_sha256",
            return_value="cd" * 32,
        ):
            with self.assertRaises(HficSessionError) as live:
                run_live_classifier(
                    {"experiment_spec": spec},
                    frozen,
                    repo_root=ROOT,
                    data_root=ROOT,
                )
        self.assertEqual(str(live.exception), KILL_UNBOUND_EVIDENCE)

    def test_t15_historical_packet_1_3_skips_new_guard(self) -> None:
        frozen = _freeze(
            "HFIC-V12-C3-FORWARD-QUOTE",
            "HFIC-V12-C2-HISTORICAL-RETURN",
        )
        historical = copy.deepcopy(frozen)
        historical["critic_input_packet"]["packet_version"] = "1.3"
        receipt = _classify(
            historical,
            _spec_for(_selected(historical)["required_feature_ids"]),
        )
        self.assertEqual(receipt["lane_classifier_terminal"], "FAST_LANE_READY")
        self.assertEqual(frozen["critic_input_packet"]["packet_version"], "1.4")

    def test_t16_f1_f2_f3_control_memory_search_unchanged(self) -> None:
        frozen = _freeze(
            "HFIC-V12-C1-PIT-LIQUIDITY-RATIO",
            "HFIC-V12-C3-FORWARD-QUOTE",
        )
        packet = frozen["critic_input_packet"]
        self.assertEqual(PROMPT_VERSION, "HFIC-V1.2")
        self.assertEqual(packet["generator_prompt_version"], "HFIC-V1.2")
        self.assertEqual(packet["packet_version"], "1.4")
        self.assertIn("runner_up_critic_input_packet", frozen)
        self.assertNotEqual(
            frozen["critic_input_packet_sha256"],
            frozen["runner_up_critic_input_packet_sha256"],
        )
        self.assertNotIn("required_feature_ids", IDENTITY_FIELDS)
        self.assertNotIn("grounding", IDENTITY_FIELDS)
        epoch = "ee" * 32
        general = search_identity_sha256(epoch, "AUTO", PROMPT_VERSION)
        control = search_identity_sha256(
            epoch,
            "AUTO",
            PROMPT_VERSION,
            None,
            CURRENT_REPRESENTATION_CONTROL_V1,
        )
        self.assertNotEqual(general, control)
        self.assertFalse(
            control_packet_has_raw_sequences(
                {
                    "prompt_version": PROMPT_VERSION,
                    "evidence_surface_mode": CURRENT_REPRESENTATION_CONTROL_V1,
                }
            )
        )
        self.assertTrue(
            control_packet_has_raw_sequences({"observations": []})
        )


if __name__ == "__main__":
    unittest.main()
