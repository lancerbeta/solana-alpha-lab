from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.early_market_panel_importer import (  # noqa: E402
    MIN_USABLE_YIELD_ELIGIBLE,
)
from solana_alpha_lab.factory.hfic_control_integrity import (  # noqa: E402
    CONTROL_CORPUS_UNRESOLVABLE,
    CONTROL_YIELD_BELOW_MIN,
    CRITIC_PACKET_GROUNDING_MISMATCH,
    CURRENT_REPRESENTATION_CONTROL_V1,
    EXPERIMENT_SPEC_GROUNDING_MISMATCH,
    KILL_UNBOUND_EVIDENCE,
    assert_experiment_spec_grounding,
    assert_packet_grounding_consistent,
    control_case_a,
    control_packet_has_raw_sequences,
    control_probe_permitted,
    deny_unresolved_fast_lane,
    effective_control_terminal,
    resolve_control_corpus_yield,
)
from solana_alpha_lab.factory.hfic_identity import IDENTITY_FIELDS  # noqa: E402
from solana_alpha_lab.factory.hfic_memory_policy import search_identity_sha256  # noqa: E402
from solana_alpha_lab.factory.hfic_session import (  # noqa: E402
    CRITIC_PACKET_VERSION_CURRENT,
    HficSessionError,
    PROMPT_VERSION,
    freeze_draft,
    list_hfic_sessions,
    run_live_classifier,
)
from solana_alpha_lab.factory.live_cohort_discovery_release import (  # noqa: E402
    CORPUS_DATASET_ID,
)
from tests.test_hfic_cli import run_cli  # noqa: E402
from tests.test_hfic_session import _preflight_receipt  # noqa: E402

DRAFT_V12 = ROOT / "tests/fixtures/hypothesis_forge/draft_v1_2_valid.json"
FORGE_SKILL = ROOT / ".agents/skills/hypothesis-forge/SKILL.md"
CRITIC_SKILL = ROOT / ".agents/skills/independent-hypothesis-critic/SKILL.md"
OPERATOR = ROOT / "docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md"
CONTEXT_SHA = "ab" * 32


def _draft() -> dict:
    return json.loads(DRAFT_V12.read_text(encoding="utf-8"))


def _grounded_preflight() -> dict:
    receipt = dict(_preflight_receipt())
    receipt["forge_context_packet_sha256"] = CONTEXT_SHA
    receipt["forge_context_packet"] = {
        "capability_ids": ["CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001"]
    }
    return receipt


def _freeze(selected: str | None = None, runner_up: str | None = None) -> dict:
    draft = _draft()
    if selected is not None:
        draft["selected_candidate_ref"] = selected
    if runner_up is not None:
        draft["runner_up_candidate_ref"] = runner_up
    return freeze_draft(
        draft,
        preflight_receipt=_grounded_preflight(),
        repo_root=ROOT,
    )


def _corpus(yield_eligible: int) -> dict:
    return {
        "dataset_id": CORPUS_DATASET_ID,
        "dataset_manifest_id": "dataset-" + "a" * 64,
        "dataset_fingerprint": "bb" * 32,
        "evidence_role": "UNSPECIFIED",
        "yield_eligible": yield_eligible,
        "yield_missing": 0,
        "feature_usable": yield_eligible >= MIN_USABLE_YIELD_ELIGIBLE,
        "labels": {
            "yield_eligible": yield_eligible,
            "logical_dataset_id": CORPUS_DATASET_ID,
        },
    }


class GroundingTransportTests(unittest.TestCase):
    def test_t1_pit_ready_survives_packet_1_4(self) -> None:
        frozen = _freeze("HFIC-V12-C1-PIT-LIQUIDITY-RATIO", "HFIC-V12-C3-FORWARD-QUOTE")
        packet = frozen["critic_input_packet"]
        selected = packet["selected_candidate"]
        self.assertEqual(packet["packet_version"], "1.4")
        self.assertEqual(packet["generator_prompt_version"], PROMPT_VERSION)
        self.assertEqual(PROMPT_VERSION, "HFIC-V1.2")
        self.assertEqual(CRITIC_PACKET_VERSION_CURRENT, "1.4")
        binding = selected["grounding"]["feature_bindings"][0]
        self.assertEqual(binding["feature_id"], "FEAT-TOKEN-LIQUIDITY-USD-TO-MCAP-RATIO")
        self.assertEqual(binding["availability_class"], "PIT_READY")
        self.assertIn("available_to_strategy_semantics", binding)
        self.assertNotIn("required_feature_ids", IDENTITY_FIELDS)

    def test_t2_historical_reconstructible_not_upgraded(self) -> None:
        frozen = _freeze(
            "HFIC-V12-C2-HISTORICAL-RETURN",
            "HFIC-V12-C3-FORWARD-QUOTE",
        )
        binding = frozen["critic_input_packet"]["selected_candidate"]["grounding"][
            "feature_bindings"
        ][0]
        self.assertEqual(binding["availability_class"], "HISTORICAL_RECONSTRUCTIBLE")
        self.assertNotEqual(binding["availability_class"], "PIT_READY")

    def test_t3_forward_only_survives_empty_legacy_array(self) -> None:
        frozen = _freeze("HFIC-V12-C3-FORWARD-QUOTE", "HFIC-V12-C2-HISTORICAL-RETURN")
        selected = frozen["critic_input_packet"]["selected_candidate"]
        self.assertEqual(selected["missing_or_forward_only_data"], [])
        self.assertEqual(
            selected["grounding"]["feature_bindings"][0]["availability_class"],
            "FORWARD_ONLY",
        )

    def test_t4_unresolved_gap_survives_packet(self) -> None:
        frozen = _freeze(
            "HFIC-V12-C4-UNRESOLVED-CREATOR-CLUSTER",
            "HFIC-V12-C3-FORWARD-QUOTE",
        )
        selected = frozen["critic_input_packet"]["selected_candidate"]
        self.assertEqual(selected["required_feature_ids"], [])
        self.assertEqual(
            selected["unresolved_requirements"],
            ["decision-time creator-cluster attribution"],
        )
        self.assertEqual(
            selected["grounding"]["unresolved_requirements"],
            selected["unresolved_requirements"],
        )
        self.assertEqual(selected["grounding"]["terminal"], "GROUNDED_WITH_GAPS")

    def test_t5_c2_grounding_transport(self) -> None:
        frozen = _freeze("HFIC-V12-C1-PIT-LIQUIDITY-RATIO", "HFIC-V12-C3-FORWARD-QUOTE")
        runner = frozen["runner_up_critic_input_packet"]["selected_candidate"]
        self.assertEqual(
            runner["grounding"]["feature_bindings"][0]["availability_class"],
            "FORWARD_ONLY",
        )
        self.assertEqual(frozen["runner_up_critic_input_packet"]["packet_version"], "1.4")

    def test_t6_prior_memory_snapshot_identical(self) -> None:
        frozen = _freeze()
        primary = frozen["critic_input_packet"]["prior_memory"]
        runner = frozen["runner_up_critic_input_packet"]["prior_memory"]
        self.assertEqual(primary["snapshot_sha256"], runner["snapshot_sha256"])
        self.assertIs(primary, runner)

    def test_t7_packet_tamper_fails_closed(self) -> None:
        frozen = _freeze()
        selected = dict(frozen["critic_input_packet"]["selected_candidate"])
        card = _draft()["candidates"][0]
        grounding = dict(selected["grounding"])
        tampered = dict(selected)
        tampered["required_feature_ids"] = ["FEAT-MAGIC"]
        with self.assertRaises(ValueError) as raised:
            assert_packet_grounding_consistent(
                tampered,
                card,
                grounding,
                str(grounding["context_packet_sha256"]),
            )
        self.assertEqual(str(raised.exception), CRITIC_PACKET_GROUNDING_MISMATCH)
        missing = dict(selected)
        missing.pop("grounding")
        with self.assertRaises(ValueError):
            assert_packet_grounding_consistent(
                missing,
                card,
                grounding,
                str(grounding["context_packet_sha256"]),
            )

    def test_t8_historical_1_3_readable_not_upgraded(self) -> None:
        from jsonschema import Draft202012Validator

        schema = json.loads(
            (
                ROOT / "catalog/schemas/hypothesis_critic_input_v1.schema.json"
            ).read_text(encoding="utf-8")
        )
        frozen = _freeze()
        historical = dict(frozen["critic_input_packet"])
        historical["packet_version"] = "1.3"
        selected = dict(historical["selected_candidate"])
        for key in (
            "estimand",
            "state_transition",
            "required_feature_ids",
            "required_capability_ids",
            "unresolved_requirements",
            "grounding",
        ):
            selected.pop(key, None)
        historical["selected_candidate"] = selected
        Draft202012Validator(schema).validate(historical)
        self.assertEqual(frozen["critic_input_packet"]["packet_version"], "1.4")
        self.assertNotEqual(historical["packet_version"], "1.4")


class ExperimentSpecBindTests(unittest.TestCase):
    def test_t9_missing_feat_mismatch(self) -> None:
        selected = {"required_feature_ids": ["FEAT-A"], "unresolved_requirements": []}
        with self.assertRaises(ValueError) as raised:
            assert_experiment_spec_grounding({}, selected)
        self.assertEqual(str(raised.exception), EXPERIMENT_SPEC_GROUNDING_MISMATCH)

    def test_t10_extra_feat_mismatch(self) -> None:
        selected = {"required_feature_ids": ["FEAT-A"], "unresolved_requirements": []}
        with self.assertRaises(ValueError):
            assert_experiment_spec_grounding(
                {"required_feature_ids": ["FEAT-A", "FEAT-B"]},
                selected,
            )

    def test_t11_set_equivalent_order_allowed(self) -> None:
        selected = {
            "required_feature_ids": ["FEAT-A", "FEAT-B"],
            "unresolved_requirements": [],
        }
        assert_experiment_spec_grounding(
            {"required_feature_ids": ["FEAT-B", "FEAT-A"]},
            selected,
        )

    def test_t12_unresolved_only_invented_feat(self) -> None:
        selected = {
            "required_feature_ids": [],
            "unresolved_requirements": ["gap"],
        }
        with self.assertRaises(ValueError) as raised:
            assert_experiment_spec_grounding(
                {"required_feature_ids": ["FEAT-X"]},
                selected,
            )
        self.assertEqual(str(raised.exception), EXPERIMENT_SPEC_GROUNDING_MISMATCH)

    def test_t13_unresolved_fast_lane_denied(self) -> None:
        selected = {
            "required_feature_ids": [],
            "unresolved_requirements": ["gap"],
        }
        with self.assertRaises(ValueError) as raised:
            deny_unresolved_fast_lane(selected, "FAST_LANE_READY")
        self.assertEqual(str(raised.exception), KILL_UNBOUND_EVIDENCE)
        with self.assertRaises(ValueError):
            deny_unresolved_fast_lane(selected, "REPLAY_AVAILABLE")
        frozen = {
            "session_id": "HFIC-SESS-TEST",
            "selected_candidate_id": "HFIC-CAND-TEST",
            "selected_definition_sha256": "ab" * 32,
            "critic_input_packet": {
                "packet_version": "1.4",
                "selected_candidate": selected,
            },
        }
        decision = mock.Mock(
            terminal="FAST_LANE_READY",
            lane=mock.Mock(value="FAST_LANE"),
            reason_codes=[],
            next_action="PAUSE",
        )
        with mock.patch(
            "solana_alpha_lab.factory.experiment_spec.validate_experiment_document",
            return_value={"schema": "smial.experiment-spec"},
        ), mock.patch(
            "solana_alpha_lab.factory.lane_classifier.classify_lane",
            return_value=decision,
        ), mock.patch(
            "solana_alpha_lab.factory.run_passport.experiment_spec_sha256",
            return_value="cd" * 32,
        ):
            with self.assertRaises(HficSessionError) as raised:
                run_live_classifier(
                    {"experiment_spec": {"schema": "smial.experiment-spec"}},
                    frozen,
                    repo_root=ROOT,
                    data_root=ROOT,
                )
        self.assertEqual(str(raised.exception), KILL_UNBOUND_EVIDENCE)

    def test_t14_unresolved_gap_lanes_allowed(self) -> None:
        selected = {
            "required_feature_ids": [],
            "unresolved_requirements": ["gap"],
        }
        deny_unresolved_fast_lane(selected, "CHANGE_LANE_CAPABILITY_GAP")
        deny_unresolved_fast_lane(selected, "BLOCKED_DATA")


class EffectiveTerminalTests(unittest.TestCase):
    def test_t15_c2_pass_forbids_probe(self) -> None:
        terminal = effective_control_terminal(
            {
                "critic_terminal": "KILL_DUPLICATE_OR_PREVIOUSLY_CLOSED",
                "final_session_terminal": "PASS_FAST_LANE_READY",
            }
        )
        self.assertEqual(terminal, "PASS_FAST_LANE_READY")
        self.assertTrue(control_case_a(terminal))
        self.assertFalse(control_probe_permitted(terminal))

    def test_t16_c2_duplicate_permits_probe(self) -> None:
        terminal = effective_control_terminal(
            {
                "critic_terminal": "KILL_MECHANISM",
                "final_session_terminal": "KILL_DUPLICATE_OR_PREVIOUSLY_CLOSED",
            }
        )
        self.assertEqual(terminal, "KILL_DUPLICATE_OR_PREVIOUSLY_CLOSED")
        self.assertTrue(control_probe_permitted(terminal))

    def test_t17_c2_revise_pause_forbids_probe(self) -> None:
        terminal = effective_control_terminal(
            {
                "critic_terminal": "KILL_DUPLICATE_OR_PREVIOUSLY_CLOSED",
                "final_session_terminal": "RUNNER_UP_REVISION_REQUIRED",
            }
        )
        self.assertEqual(terminal, "RUNNER_UP_REVISION_REQUIRED")
        self.assertFalse(control_probe_permitted(terminal))

    def test_t18_no_worthy_fallback(self) -> None:
        terminal = effective_control_terminal(
            {"critic_terminal": "NO_WORTHY_HYPOTHESIS"}
        )
        self.assertEqual(terminal, "NO_WORTHY_HYPOTHESIS")
        self.assertTrue(control_probe_permitted(terminal))


class ControlModeTests(unittest.TestCase):
    def test_t19_default_search_identity_unchanged(self) -> None:
        epoch = "ee" * 32
        four = search_identity_sha256(epoch, "AUTO", PROMPT_VERSION)
        five = search_identity_sha256(epoch, "AUTO", PROMPT_VERSION, None, None)
        self.assertEqual(four, five)

    def test_t20_control_same_epoch_distinct_search(self) -> None:
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

    def test_t21_control_packet_has_no_raw_sequences(self) -> None:
        packet = {
            "prompt_version": PROMPT_VERSION,
            "evidence_surface_mode": CURRENT_REPRESENTATION_CONTROL_V1,
            "dataset_fingerprints": ["aa" * 32],
            "feature_families": [],
        }
        self.assertFalse(control_packet_has_raw_sequences(packet))
        self.assertTrue(
            control_packet_has_raw_sequences({**packet, "observations": []})
        )

    def test_t22_skill_operator_forbid_raw_lifecycle_in_control(self) -> None:
        forge = FORGE_SKILL.read_text(encoding="utf-8")
        critic = CRITIC_SKILL.read_text(encoding="utf-8")
        operator = OPERATOR.read_text(encoding="utf-8")
        self.assertIn("CURRENT_REPRESENTATION_CONTROL_V1", forge)
        self.assertIn("CURRENT_REPRESENTATION_CONTROL_V1", operator)
        self.assertIn("raw current lifecycle", forge)
        self.assertIn("parquet observation bodies", forge)
        self.assertIn("raw live lifecycle observation rows", operator)
        self.assertIn("--control-current-representation", forge)
        self.assertIn("WAIT_FOR_IMPORT_OR_STOP", forge)
        self.assertIn("effective_control_terminal", forge)
        self.assertIn("packet_version=1.4", critic)
        self.assertIn("authoritative over prose", critic)

    def test_t23_yield_9_control_stop_before_session(self) -> None:
        code, observed = resolve_control_corpus_yield(
            [_corpus(9)],
            corpus_dataset_id=CORPUS_DATASET_ID,
            min_usable_yield_eligible=MIN_USABLE_YIELD_ELIGIBLE,
        )
        self.assertEqual(code, CONTROL_YIELD_BELOW_MIN)
        self.assertEqual(observed, 9)
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            commissioned = run_cli(
                "preflight",
                "--owner-focus",
                "AUTO",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(json.loads(commissioned.stdout)["action"], "START_NEW_SESSION")
            from solana_alpha_lab.factory.document_runner import repository_git_snapshot
            from solana_alpha_lab.factory.hfic_preflight import run_preflight

            snap = repository_git_snapshot(ROOT)
            with mock.patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                return_value=([_corpus(9)], []),
            ):
                receipt = run_preflight(
                    ROOT,
                    data_root,
                    owner_focus="AUTO",
                    auto_commission=False,
                    git_snapshot={
                        "head_sha": snap.head_sha,
                        "composite_sha256": snap.composite_sha256,
                    },
                    evidence_surface_mode=CURRENT_REPRESENTATION_CONTROL_V1,
                )
            self.assertEqual(receipt["action"], "STOP")
            self.assertEqual(receipt["terminal"], CONTROL_YIELD_BELOW_MIN)
            self.assertEqual(
                receipt["evidence_surface_mode"],
                CURRENT_REPRESENTATION_CONTROL_V1,
            )
            self.assertIsNone(receipt.get("session_id"))
            from solana_alpha_lab.factory.research_store import ResearchStore

            store = ResearchStore(data_root, create_if_missing=False)
            self.assertEqual(list_hfic_sessions(store), [])

    def test_t24_yield_10_gate_passes(self) -> None:
        code, observed = resolve_control_corpus_yield(
            [_corpus(10)],
            corpus_dataset_id=CORPUS_DATASET_ID,
            min_usable_yield_eligible=MIN_USABLE_YIELD_ELIGIBLE,
        )
        self.assertEqual(code, "OK")
        self.assertEqual(observed, 10)
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            commissioned = run_cli(
                "preflight",
                "--owner-focus",
                "AUTO",
                "--format",
                "json",
                data_root=data_root,
            )
            general = json.loads(commissioned.stdout)
            self.assertEqual(general["action"], "START_NEW_SESSION")
            from solana_alpha_lab.factory.document_runner import repository_git_snapshot
            from solana_alpha_lab.factory.hfic_preflight import run_preflight

            snap = repository_git_snapshot(ROOT)
            with mock.patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                return_value=([_corpus(10)], []),
            ):
                receipt = run_preflight(
                    ROOT,
                    data_root,
                    owner_focus="AUTO",
                    auto_commission=False,
                    git_snapshot={
                        "head_sha": snap.head_sha,
                        "composite_sha256": snap.composite_sha256,
                    },
                    evidence_surface_mode=CURRENT_REPRESENTATION_CONTROL_V1,
                )
            self.assertEqual(receipt["action"], "START_NEW_SESSION")
            self.assertEqual(
                receipt["evidence_surface_mode"],
                CURRENT_REPRESENTATION_CONTROL_V1,
            )
            general_key = search_identity_sha256(
                receipt["evidence_epoch_sha256"], "AUTO", PROMPT_VERSION
            )
            self.assertNotEqual(receipt["search_key_sha256"], general_key)
            packet = receipt["forge_context_packet"]
            self.assertFalse(control_packet_has_raw_sequences(packet))
            self.assertEqual(
                packet["evidence_surface_mode"],
                CURRENT_REPRESENTATION_CONTROL_V1,
            )

    def test_t25_low_yield_general_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            completed = run_cli(
                "preflight",
                "--owner-focus",
                "AUTO",
                "--format",
                "json",
                data_root=data_root,
            )
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["action"], "START_NEW_SESSION")
            self.assertNotIn("evidence_surface_mode", payload)

    def test_t26_missing_corpus_control_readiness_failure(self) -> None:
        code, observed = resolve_control_corpus_yield(
            [{"dataset_id": "DATASET-OTHER", "yield_eligible": 99}],
            corpus_dataset_id=CORPUS_DATASET_ID,
            min_usable_yield_eligible=MIN_USABLE_YIELD_ELIGIBLE,
        )
        self.assertEqual(code, CONTROL_CORPUS_UNRESOLVABLE)
        self.assertIsNone(observed)
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            completed = run_cli(
                "preflight",
                "--owner-focus",
                "AUTO",
                "--control-current-representation",
                "--format",
                "json",
                data_root=data_root,
            )
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["action"], "STOP")
            self.assertEqual(payload["terminal"], CONTROL_CORPUS_UNRESOLVABLE)


class RegressionFenceTests(unittest.TestCase):
    def test_t27_generator_remains_v1_2(self) -> None:
        frozen = _freeze()
        self.assertEqual(frozen["prompt_version"], "HFIC-V1.2")
        self.assertEqual(
            frozen["critic_input_packet"]["generator_prompt_version"],
            "HFIC-V1.2",
        )
        self.assertEqual(frozen["critic_input_packet"]["packet_version"], "1.4")

    def test_t28_packet_carries_complete_prior_memory(self) -> None:
        frozen = _freeze()
        memory = frozen["critic_input_packet"]["prior_memory"]
        self.assertIn("snapshot_sha256", memory)
        self.assertIn("capsules", memory)

    def test_t29_f3_packets_exist_before_c1(self) -> None:
        frozen = _freeze()
        self.assertIn("runner_up_critic_input_packet", frozen)
        self.assertNotEqual(
            frozen["critic_input_packet_sha256"],
            frozen["runner_up_critic_input_packet_sha256"],
        )

    def test_t30_identity_fields_exclude_grounding(self) -> None:
        self.assertNotIn("required_feature_ids", IDENTITY_FIELDS)
        self.assertNotIn("grounding", IDENTITY_FIELDS)
        self.assertNotIn("unresolved_requirements", IDENTITY_FIELDS)

    def test_t31_repeated_control_does_not_shop_budget(self) -> None:
        epoch = "ee" * 32
        first = search_identity_sha256(
            epoch, "AUTO", PROMPT_VERSION, None, CURRENT_REPRESENTATION_CONTROL_V1
        )
        second = search_identity_sha256(
            epoch, "AUTO", PROMPT_VERSION, None, CURRENT_REPRESENTATION_CONTROL_V1
        )
        self.assertEqual(first, second)
        general = search_identity_sha256(epoch, "AUTO", PROMPT_VERSION)
        self.assertNotEqual(first, general)


if __name__ == "__main__":
    unittest.main()
