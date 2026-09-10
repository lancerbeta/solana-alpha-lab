from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.document_runner import (
    repository_git_snapshot,
)
from solana_alpha_lab.factory.hfic_control_integrity import (
    CURRENT_REPRESENTATION_CONTROL_V1,
)
from solana_alpha_lab.factory.hfic_identity import candidate_identity
from solana_alpha_lab.factory.hfic_preflight import MAX_PACKET_BYTES
from solana_alpha_lab.factory.hfic_representation_probe import (
    INVALID_CONTROL_NOT_RUN,
    INVALID_CONTROL_PACKET_HASH,
    INVALID_COVERAGE_BROKEN,
    INVALID_INSUFFICIENT_YIELD,
    INVALID_PACKET_BUDGET,
    INVALID_PROBE_IDENTITY,
    INVALID_REPRESENTATION_SCHEMA,
    INVALID_TRIGGER_NOT_MET,
    STATUS_CONTROL_REQUIRED,
    STATUS_ELIGIBLE,
    STATUS_OBSERVABILITY_BLOCKED,
    ControlBaseline,
    RepresentationProbeError,
    build_challenger_packet,
    control_baseline_from_receipt,
    control_memory_baseline_sha256,
    existing_hfic_lifecycle_fixture_input,
    existing_hfic_packet,
    representation_probe_identity_sha256,
    representation_search_key_sha256,
    representation_status,
)
from solana_alpha_lab.factory.hfic_session import freeze_draft
from solana_alpha_lab.factory.normalized_trajectory_v1 import (
    DEFAULT_SCHEDULE,
    PACKET_KEY,
    project_normalized_trajectory,
)
from solana_alpha_lab.factory.run_passport import (
    canonical_json_bytes,
    canonical_sha256,
)

DRAFT_PATH = ROOT / "tests/fixtures/hypothesis_forge/draft_v1_2_valid.json"


def _frozen_control() -> dict[str, object]:
    draft = json.loads(DRAFT_PATH.read_text(encoding="utf-8"))
    draft["selected_candidate_ref"] = "HFIC-V12-C4-UNRESOLVED-CREATOR-CLUSTER"
    git = repository_git_snapshot(ROOT)
    preflight = {
        "receipt_id": "HFIC-PREFLIGHT-FIXTURE-001",
        "evidence_epoch_sha256": "aa" * 32,
        "focus_key_sha256": "bb" * 32,
        "search_key_sha256": "cc" * 32,
        "owner_focus": "AUTO",
        "live_git_head": git.head_sha.lower(),
        "git_composite_sha256": git.composite_sha256,
        "session_started_at": "2026-08-27T12:00:00Z",
        "forge_context_packet_sha256": "ab" * 32,
        "forge_context_packet": {
            "capability_ids": ["CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001"]
        },
    }
    return freeze_draft(draft, preflight_receipt=preflight, repo_root=ROOT)


def _critic_result_from_packet_only(
    packet: dict[str, object],
    terminal: str = "KILL_MECHANISM",
) -> dict[str, object]:
    selected = packet["selected_candidate"]
    assert isinstance(selected, dict)
    identity = candidate_identity(
        {
            "claim": selected["claim"],
            "mechanism": selected["mechanism"],
            "actor_counterparty": selected["actor_counterparty"],
            "population": selected["population"],
            "decision_timestamp": selected["decision_timestamp"],
            "primary_x_family": selected["primary_x"],
            "primary_y": selected["primary_y"],
            "horizon_notional": selected["horizon_notional"],
            "negative_control": selected["negative_control"],
            "cheapest_falsifier": selected["cheapest_falsifier"],
        }
    )
    return {
        "schema": "smial.hypothesis-critic-result",
        "schema_version": "1.1",
        "session_id": packet["session_id"],
        "critic_input_packet_sha256": canonical_sha256(packet),
        "selected_candidate_id": selected["candidate_id"],
        "selected_definition_sha256": identity.full_sha256,
        "critic_prompt_version": "HFIC-V1.1",
        "isolated_context_attestation": "NEW_CONTEXT_REQUIRED",
        "critic_terminal": terminal,
        "next": "STOP",
        "authority": {
            "git_mutation": 0,
            "experiment_execution": 0,
            "provider_api_rpc_wss_calls": 0,
        },
        "non_claims": ["NO_ALPHA", "PACKET_ONLY_CRITIC"],
    }


def _control_receipt() -> dict[str, object]:
    frozen = _frozen_control()
    packet = frozen["critic_input_packet"]
    assert isinstance(packet, dict)
    session_receipt: dict[str, object] = {
        "session_id": frozen["session_id"],
        "session_state": "SYNTHESIS_COMPLETE",
        "evidence_epoch_sha256": "aa" * 32,
        "focus_key_sha256": "bb" * 32,
        "search_key_sha256": "cc" * 32,
        "prompt_version": "HFIC-V1.2",
        "receipt_schema_version": "1.3",
        "live_git_head": packet["live_git_head"],
        "store_inventory_digest": "dd" * 32,
        "candidate_ids": list(frozen["candidate_ids"]),
        "selected_candidate_id": frozen["selected_candidate_id"],
        "runner_up_candidate_id": frozen["runner_up_candidate_id"],
        "critic_input_packet_sha256": frozen["critic_input_packet_sha256"],
        "critic_result_sha256": "ee" * 32,
        "critic_terminal": "KILL_UNBOUND_EVIDENCE",
        "lane_classifier_terminal": None,
        "decision_event_ids": [],
        "next": "STOP",
        "authority": {
            "git_mutation": 0,
            "experiment_execution": 0,
            "provider_api_rpc_wss_calls": 0,
        },
        "no_git_fence_receipt": {},
        "created_at": "2026-08-27T12:00:00Z",
        "diagnostics": {
            "candidate_count": 4,
            "known_feature_reference_count": 0,
            "known_capability_reference_count": 0,
            "candidate_with_unresolved_requirement_count": 0,
            "unresolved_requirement_count": 0,
            "unique_structural_signature_count": 4,
            "structural_repetition_count": 0,
            "structural_repetition_ratio": 0.0,
            "critic_terminal": "KILL_UNBOUND_EVIDENCE",
            "selected_candidate_present": True,
            "no_worthy_hypothesis": False,
        },
        "primary_selected_candidate_id": frozen["selected_candidate_id"],
        "primary_critic_terminal": "KILL_UNBOUND_EVIDENCE",
        "primary_critic_result_sha256": "ee" * 32,
        "primary_critic_input_packet_sha256": frozen["critic_input_packet_sha256"],
        "runner_up_failover_used": False,
        "runner_up_critic_input_packet_sha256": frozen[
            "runner_up_critic_input_packet_sha256"
        ],
        "runner_up_critic_terminal": None,
        "runner_up_critic_result_sha256": None,
        "final_survivor_candidate_id": None,
        "final_session_terminal": "NO_WORTHY_HYPOTHESIS",
        "effective_control_terminal": "NO_WORTHY_HYPOTHESIS",
        "critic_screen_count": 1,
        "critic_launched": True,
        "forge_context_packet_sha256": frozen["forge_context_packet_sha256"],
        "evidence_surface_mode": CURRENT_REPRESENTATION_CONTROL_V1,
    }
    receipt: dict[str, object] = {
        "session_id": frozen["session_id"],
        "critic_input_packet": packet,
        "critic_input_packet_sha256": frozen["critic_input_packet_sha256"],
        "evidence_epoch_sha256": "aa" * 32,
        "focus_key_sha256": "bb" * 32,
        "search_key_sha256": "cc" * 32,
        "prompt_version": "HFIC-V1.2",
        "evidence_surface_mode": CURRENT_REPRESENTATION_CONTROL_V1,
        "final_session_terminal": "NO_WORTHY_HYPOTHESIS",
        "critic_terminal": "KILL_UNBOUND_EVIDENCE",
        "session_receipt": session_receipt,
    }
    receipt["memory_baseline_sha256"] = control_memory_baseline_sha256(receipt)
    return receipt


def _cohort_readiness_receipt(
    *,
    yield_eligible: object = 10,
    coverage: str = "DISCOVERY_COVERAGE_CONFIRMED",
) -> dict[str, object]:
    binding = DEFAULT_SCHEDULE.corpus_binding
    assert binding is not None
    binding_values = binding.as_dict()
    manifest: dict[str, object] = {
        "schema": "smial.live-cohort-discovery-release",
        "schema_version": "1.0",
        "release_id": binding_values["release_id"],
        "cohort_id": binding_values["cohort_id"],
        "sealed_at": "2026-09-01T00:00:00Z",
        "schedule_sha256": binding_values["schedule_sha256"],
        "activation_id": binding_values["activation_id"],
        "producer_git_sha": binding_values["producer_git_sha"],
        "source_sha256": binding_values["source_sha256"],
        "starts_at": "2026-01-01T00:00:00Z",
        "stops_admitting_at": "2026-01-22T00:00:00Z",
        "admission_field": "discovery_first_reliable_available_at",
        "evidence_role": "EXPLORATORY_REUSE",
        "confirmatory_reuse_forbidden": True,
        "census_sha256": binding_values["census_sha256"],
        "observations_sha256": binding_values["observations_sha256"],
        "census_row_count": 10,
        "observation_row_count": 30,
        "feature_families": [],
        "yield_eligible": yield_eligible,
        "yield_missing": 0,
        "readiness_state": "READY_VALID",
        "discovery_coverage_class": coverage,
        "projection_id": "TOKENS_V2_TYPED_PROJECTION_V1",
        "projection_version": "1.0",
    }
    base: dict[str, object] = {
        "schema": "smial.normalized-trajectory-v1-readiness-receipt",
        "schema_version": "1.0",
        "source_kind": "VERIFIED_LIVE_COHORT_RELEASE_READBACK_V1",
        "readback_verified": True,
        "readback_verifier": "solana_alpha_lab.factory.live_cohort_discovery_release.verify_live_cohort",
        "release_manifest": manifest,
        "release_id": manifest["release_id"],
        "manifest_sha256": canonical_sha256(manifest),
        "schedule_sha256": manifest["schedule_sha256"],
        "readiness_state": manifest["readiness_state"],
        "discovery_coverage_class": manifest["discovery_coverage_class"],
        "first_fresh_cohort_sealed_verified_imported": True,
        "confirmatory_reuse_forbidden": True,
        "yield_eligible": yield_eligible,
    }
    return {
        **base,
        "receipt_sha256": canonical_sha256(base),
    }


def _registration_receipt(challenger: dict[str, object]) -> dict[str, object]:
    base: dict[str, object] = {
        "schema": "smial.normalized-trajectory-v1-registration-receipt",
        "schema_version": "1.0",
        "source_kind": "REPRESENTATION_PROBE_REGISTRY_READBACK_V1",
        "readback_verified": True,
        "readback_verifier": (
            "solana_alpha_lab.factory.hfic_representation_probe.registration_readback"
        ),
        "registration_state": "REGISTERED",
        "registration_slot_sha256": canonical_sha256(
            {
                "identity_kind": "REGISTERED_REPRESENTATION_PROBE_SLOT",
                "control_session_id": challenger["control_session_id"],
                "evidence_epoch_sha256": challenger["evidence_epoch_sha256"],
                "representation_id": "NORMALIZED_TRAJECTORY_V1",
            }
        ),
        "registered_probe_identity_sha256": challenger["probe_identity_sha256"],
        "control_session_id": challenger["control_session_id"],
        "evidence_epoch_sha256": challenger["evidence_epoch_sha256"],
        "control_packet_sha256": challenger["control_packet_sha256"],
        "memory_baseline_sha256": challenger["memory_baseline_sha256"],
        "representation_payload_sha256": challenger["representation_payload_sha256"],
        "representation_search_key_sha256": challenger[
            "representation_search_key_sha256"
        ],
        "probe_identity_sha256": challenger["probe_identity_sha256"],
    }
    return {**base, "receipt_sha256": canonical_sha256(base)}


class HficRepresentationProbeTests(unittest.TestCase):
    def test_exact_control_clone_and_existing_hfic_fixture(self) -> None:
        receipt = _control_receipt()
        baseline = control_baseline_from_receipt(receipt)
        representation = project_normalized_trajectory([])
        readiness = _cohort_readiness_receipt()
        challenger = build_challenger_packet(
            baseline,
            representation,
            cohort_readiness_receipt=readiness,
        )

        self.assertEqual(challenger["evidence_epoch_sha256"], "aa" * 32)
        self.assertEqual(challenger["control_packet_sha256"], baseline.packet_sha256)
        self.assertEqual(challenger["memory_baseline_sha256"], baseline.memory_baseline_sha256)
        self.assertEqual(challenger["critic_input_packet"], baseline.packet)
        lifecycle_input = existing_hfic_lifecycle_fixture_input(
            challenger,
            control_receipt=receipt,
            cohort_readiness_receipt=readiness,
        )
        self.assertEqual(lifecycle_input["representation"], challenger[PACKET_KEY])
        self.assertEqual(challenger[PACKET_KEY], challenger["normalized_trajectory_v1"])
        self.assertEqual(
            existing_hfic_packet(
                challenger,
                cohort_readiness_receipt=readiness,
            ),
            baseline.packet,
        )
        self.assertNotEqual(
            challenger["representation_search_key_sha256"],
            receipt["search_key_sha256"],
        )
        self.assertTrue(challenger["ordinary_search_budget_unchanged"])
        self.assertEqual(challenger["max_packet_bytes"], MAX_PACKET_BYTES)
        self.assertLessEqual(
            len(json.dumps(challenger, sort_keys=True, separators=(",", ":")).encode()),
            MAX_PACKET_BYTES,
        )

        schema = json.loads(
            (ROOT / "catalog/schemas/hypothesis_critic_input_v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        Draft202012Validator(schema).validate(
            existing_hfic_packet(
                challenger,
                cohort_readiness_receipt=readiness,
            )
        )
        critic = _critic_result_from_packet_only(
            lifecycle_input["critic_input_packet"], "KILL_MECHANISM"
        )
        self.assertEqual(critic["session_id"], challenger["control_session_id"])
        self.assertEqual(
            critic["critic_input_packet_sha256"], challenger["control_packet_sha256"]
        )

    def test_control_and_probe_identity_fail_closed(self) -> None:
        missing_packet_hash = _control_receipt()
        del missing_packet_hash["critic_input_packet_sha256"]
        with self.assertRaises(RepresentationProbeError) as raised:
            control_baseline_from_receipt(missing_packet_hash)
        self.assertEqual(str(raised.exception), INVALID_CONTROL_PACKET_HASH)

        missing_memory_hash = _control_receipt()
        del missing_memory_hash["memory_baseline_sha256"]
        derived_baseline = control_baseline_from_receipt(missing_memory_hash)
        self.assertEqual(
            derived_baseline.memory_baseline_sha256,
            control_memory_baseline_sha256(missing_memory_hash),
        )

        receipt = _control_receipt()
        baseline = control_baseline_from_receipt(receipt)
        with self.assertRaises(RepresentationProbeError) as raised:
            build_challenger_packet(
                baseline,
                project_normalized_trajectory([]),
                cohort_readiness_receipt=_cohort_readiness_receipt(),
                registered_probe_identity_sha256="dd" * 32,
            )
        self.assertEqual(str(raised.exception), INVALID_PROBE_IDENTITY)

        challenger = build_challenger_packet(
            baseline,
            project_normalized_trajectory([]),
            cohort_readiness_receipt=_cohort_readiness_receipt(),
        )
        with self.assertRaises(RepresentationProbeError) as raised:
            build_challenger_packet(
                baseline,
                project_normalized_trajectory([]),
                cohort_readiness_receipt=_cohort_readiness_receipt(),
                registered_probe_identity_sha256=challenger["probe_identity_sha256"],
            )
        self.assertEqual(str(raised.exception), "REPRESENTATION_PROBE_ALREADY_EXISTS")

    def test_builder_rejects_unusable_readiness(self) -> None:
        receipt = _control_receipt()
        baseline = control_baseline_from_receipt(receipt)
        for readiness, expected in (
            (
                _cohort_readiness_receipt(yield_eligible=9),
                INVALID_INSUFFICIENT_YIELD,
            ),
            (
                _cohort_readiness_receipt(coverage="GAP_CONFIRMED"),
                INVALID_COVERAGE_BROKEN,
            ),
        ):
            with self.subTest(expected=expected):
                with self.assertRaises(RepresentationProbeError) as raised:
                    build_challenger_packet(
                        baseline,
                        project_normalized_trajectory([]),
                        cohort_readiness_receipt=readiness,
                    )
                self.assertEqual(str(raised.exception), expected)

    def test_control_memory_anchors_must_match_packet(self) -> None:
        receipt = _control_receipt()
        receipt["memory_policy_head_sha256"] = "aa" * 32
        packet = receipt["critic_input_packet"]
        assert isinstance(packet, dict)
        packet["memory_policy_head_sha256"] = "bb" * 32
        packet_hash = canonical_sha256(packet)
        receipt["critic_input_packet_sha256"] = packet_hash
        session_receipt = receipt["session_receipt"]
        assert isinstance(session_receipt, dict)
        session_receipt["critic_input_packet_sha256"] = packet_hash
        with self.assertRaises(RepresentationProbeError) as raised:
            control_baseline_from_receipt(receipt)
        self.assertEqual(str(raised.exception), "INVALID_MEMORY_BASELINE_DRIFT")

    def test_public_control_baseline_constructor_cannot_grant_verification(self) -> None:
        with self.assertRaises(RepresentationProbeError) as raised:
            ControlBaseline(
                session_id="session",
                terminal="NO_WORTHY_HYPOTHESIS",
                evidence_epoch_sha256="aa" * 32,
                prompt_version="HFIC-V1.2",
                packet={},
                packet_sha256="bb" * 32,
                memory_baseline_sha256="cc" * 32,
                receipt_verified=True,
            )
        self.assertEqual(str(raised.exception), INVALID_CONTROL_NOT_RUN)

    def test_raw_mapping_cannot_enter_challenger_representation(self) -> None:
        receipt = _control_receipt()
        baseline = control_baseline_from_receipt(receipt)
        raw_mapping = {
            "packet_schema": "smial.normalized-trajectory-v1",
            "representation_id": "NORMALIZED_TRAJECTORY_V1",
            "raw_values": [1.0],
        }
        raw_mapping["payload_sha256"] = canonical_sha256(raw_mapping)
        with self.assertRaises(RepresentationProbeError) as raised:
            build_challenger_packet(baseline, raw_mapping)
        self.assertIn(
            str(raised.exception),
            {"REPRESENTATION_INVALID", "INVALID_REPRESENTATION_SCHEMA"},
        )

    def test_schedule_hash_drift_cannot_enter_challenger(self) -> None:
        receipt = _control_receipt()
        baseline = control_baseline_from_receipt(receipt)
        readiness = _cohort_readiness_receipt()
        challenger = build_challenger_packet(
            baseline,
            project_normalized_trajectory([]),
            cohort_readiness_receipt=readiness,
        )
        drifted = json.loads(json.dumps(challenger))
        representation = drifted[PACKET_KEY]
        representation["schedule"]["schedule_sha256"] = "00" * 32
        representation["payload_sha256"] = canonical_sha256(
            {key: value for key, value in representation.items() if key != "payload_sha256"}
        )
        drifted["representation_payload_sha256"] = representation["payload_sha256"]
        with self.assertRaises(RepresentationProbeError) as raised:
            existing_hfic_packet(
                drifted,
                cohort_readiness_receipt=readiness,
            )
        self.assertEqual(str(raised.exception), INVALID_REPRESENTATION_SCHEMA)

    def test_invalid_x900_cannot_enter_serialized_challenger(self) -> None:
        receipt = _control_receipt()
        baseline = control_baseline_from_receipt(receipt)
        readiness = _cohort_readiness_receipt()
        challenger = build_challenger_packet(
            baseline,
            project_normalized_trajectory([]),
            cohort_readiness_receipt=readiness,
        )
        drifted = json.loads(json.dumps(challenger))
        representation = drifted[PACKET_KEY]
        representation["schedule"]["x_due_offset_seconds"] = 900
        representation["schedule"]["prefix_due_offset_seconds"] = [900, 900, 1800]
        representation["payload_sha256"] = canonical_sha256(
            {key: value for key, value in representation.items() if key != "payload_sha256"}
        )
        with self.assertRaises(RepresentationProbeError) as raised:
            existing_hfic_packet(
                drifted,
                cohort_readiness_receipt=readiness,
            )
        self.assertEqual(str(raised.exception), INVALID_REPRESENTATION_SCHEMA)

    def test_representation_is_bound_to_verified_release_bytes(self) -> None:
        receipt = _control_receipt()
        baseline = control_baseline_from_receipt(receipt)
        representation = project_normalized_trajectory([])
        with self.assertRaises(RepresentationProbeError) as raised:
            build_challenger_packet(baseline, representation)
        self.assertEqual(str(raised.exception), "INVALID_COHORT_READINESS_RECEIPT")

        readiness = _cohort_readiness_receipt()
        challenger = build_challenger_packet(
            baseline,
            representation,
            cohort_readiness_receipt=readiness,
        )
        drifted = json.loads(json.dumps(challenger))
        drifted[PACKET_KEY]["corpus_binding"]["source_sha256"] = "ff" * 32
        drifted[PACKET_KEY]["payload_sha256"] = canonical_sha256(
            {
                key: value
                for key, value in drifted[PACKET_KEY].items()
                if key != "payload_sha256"
            }
        )
        drifted["representation_payload_sha256"] = drifted[PACKET_KEY][
            "payload_sha256"
        ]
        drifted["representation_search_key_sha256"] = representation_search_key_sha256(
            evidence_epoch_sha256=drifted["evidence_epoch_sha256"],
            owner_focus=drifted["owner_focus"],
            prompt_version=drifted["prompt_version"],
            memory_baseline_sha256=drifted["memory_baseline_sha256"],
            representation_id=drifted["representation_id"],
            representation_payload_sha256=drifted["representation_payload_sha256"],
            control_packet_sha256=drifted["control_packet_sha256"],
        )
        drifted["probe_identity_sha256"] = representation_probe_identity_sha256(
            control_session_id=drifted["control_session_id"],
            evidence_epoch_sha256=drifted["evidence_epoch_sha256"],
            representation_id=drifted["representation_id"],
            representation_search_key=drifted["representation_search_key_sha256"],
            representation_payload_sha256=drifted["representation_payload_sha256"],
        )
        for _ in range(3):
            drifted["packet_bytes"] = len(canonical_json_bytes(drifted))
        with self.assertRaises(RepresentationProbeError) as raised:
            existing_hfic_lifecycle_fixture_input(
                drifted,
                control_receipt=receipt,
                cohort_readiness_receipt=readiness,
            )
        self.assertEqual(str(raised.exception), "INVALID_COHORT_READINESS_RECEIPT")

    def test_fixture_bridge_rechecks_outer_identity(self) -> None:
        receipt = _control_receipt()
        baseline = control_baseline_from_receipt(receipt)
        challenger = build_challenger_packet(
            baseline,
            project_normalized_trajectory([]),
            cohort_readiness_receipt=_cohort_readiness_receipt(),
        )
        drifted = dict(challenger)
        drifted["control_session_id"] = "different-session"
        with self.assertRaises(RepresentationProbeError) as raised:
            existing_hfic_lifecycle_fixture_input(
                drifted,
                control_receipt=receipt,
                cohort_readiness_receipt=_cohort_readiness_receipt(),
            )
        self.assertEqual(str(raised.exception), INVALID_PROBE_IDENTITY)

    def test_fixture_bridge_rejects_rehashed_outer_baseline_drift(self) -> None:
        receipt = _control_receipt()
        baseline = control_baseline_from_receipt(receipt)
        challenger = build_challenger_packet(
            baseline,
            project_normalized_trajectory([]),
            cohort_readiness_receipt=_cohort_readiness_receipt(),
        )
        drifted = json.loads(json.dumps(challenger))
        drifted["control_session_id"] = "different-session"
        drifted["evidence_epoch_sha256"] = "ff" * 32
        drifted["representation_search_key_sha256"] = representation_search_key_sha256(
            evidence_epoch_sha256=drifted["evidence_epoch_sha256"],
            owner_focus=drifted["owner_focus"],
            prompt_version=drifted["prompt_version"],
            memory_baseline_sha256=drifted["memory_baseline_sha256"],
            representation_id=drifted["representation_id"],
            representation_payload_sha256=drifted["representation_payload_sha256"],
            control_packet_sha256=drifted["control_packet_sha256"],
        )
        drifted["probe_identity_sha256"] = representation_probe_identity_sha256(
            control_session_id=drifted["control_session_id"],
            evidence_epoch_sha256=drifted["evidence_epoch_sha256"],
            representation_id=drifted["representation_id"],
            representation_search_key=drifted["representation_search_key_sha256"],
            representation_payload_sha256=drifted["representation_payload_sha256"],
        )
        drifted["packet_bytes"] = 0
        for _ in range(3):
            drifted["packet_bytes"] = len(canonical_json_bytes(drifted))

        with self.assertRaises(RepresentationProbeError) as raised:
            existing_hfic_lifecycle_fixture_input(
                drifted,
                control_receipt=receipt,
                cohort_readiness_receipt=_cohort_readiness_receipt(),
            )
        self.assertEqual(str(raised.exception), INVALID_PROBE_IDENTITY)

    def test_runner_up_or_case_a_cannot_create_challenger(self) -> None:
        receipt = _control_receipt()
        receipt["final_session_terminal"] = "RUNNER_UP_REVISION_REQUIRED"
        assert isinstance(receipt["session_receipt"], dict)
        receipt["session_receipt"]["final_session_terminal"] = (
            "RUNNER_UP_REVISION_REQUIRED"
        )
        receipt["session_receipt"]["effective_control_terminal"] = (
            "RUNNER_UP_REVISION_REQUIRED"
        )
        baseline = control_baseline_from_receipt(receipt)
        with self.assertRaises(RepresentationProbeError) as raised:
            build_challenger_packet(
                baseline,
                project_normalized_trajectory([]),
                cohort_readiness_receipt=_cohort_readiness_receipt(),
            )
        self.assertEqual(str(raised.exception), INVALID_TRIGGER_NOT_MET)

    def test_packet_budget_fails_without_dropping_control_context(self) -> None:
        receipt = _control_receipt()
        baseline = control_baseline_from_receipt(receipt)
        huge = dict(baseline.packet)
        huge["known_unknowns"] = ["x" * (MAX_PACKET_BYTES * 2)]
        huge_hash = canonical_sha256(huge)
        oversized_receipt = dict(_control_receipt())
        oversized_receipt["critic_input_packet"] = huge
        oversized_receipt["critic_input_packet_sha256"] = huge_hash
        assert isinstance(oversized_receipt["session_receipt"], dict)
        oversized_receipt["session_receipt"]["critic_input_packet_sha256"] = huge_hash
        oversized_receipt["memory_baseline_sha256"] = control_memory_baseline_sha256(
            oversized_receipt
        )
        with self.assertRaises(RepresentationProbeError) as raised:
            build_challenger_packet(
                oversized_receipt,
                project_normalized_trajectory([]),
                cohort_readiness_receipt=_cohort_readiness_receipt(),
            )
        self.assertEqual(str(raised.exception), INVALID_PACKET_BUDGET)


class RepresentationStatusTests(unittest.TestCase):
    def test_read_only_status_routes(self) -> None:
        receipt = _control_receipt()
        baseline = control_baseline_from_receipt(receipt)
        eligible = {
            "control_present": True,
            "control_receipt": receipt,
            "control_terminal": "NO_WORTHY_HYPOTHESIS",
            "control_mode": CURRENT_REPRESENTATION_CONTROL_V1,
            "evidence_epoch_matches": True,
            "control_session_id": baseline.session_id,
            "evidence_epoch_sha256": baseline.evidence_epoch_sha256,
            "control_packet_sha256": baseline.packet_sha256,
            "memory_baseline_sha256": baseline.memory_baseline_sha256,
            "representation_schedule_sha256": DEFAULT_SCHEDULE.schedule_sha256,
            "cohort_ready": True,
            "cohort_readiness_receipt": _cohort_readiness_receipt(),
        }
        self.assertEqual(representation_status({})["status"], STATUS_CONTROL_REQUIRED)
        self.assertEqual(representation_status(eligible)["status"], STATUS_ELIGIBLE)

        challenger = build_challenger_packet(
            baseline,
            project_normalized_trajectory([]),
            cohort_readiness_receipt=_cohort_readiness_receipt(),
        )
        registered = json.loads(json.dumps(challenger))
        registered["probe_state"] = "REGISTERED"
        for _ in range(3):
            registered["packet_bytes"] = len(canonical_json_bytes(registered))
        registered["receipt_verified"] = True
        registered["registration_receipt"] = _registration_receipt(registered)
        self.assertEqual(
            representation_status(
                {
                    **eligible,
                    "representation_probe_state": "REGISTERED",
                    "representation_probe_receipt": registered,
                }
            )["status"],
            "REPRESENTATION_PROBE_ALREADY_EXISTS",
        )
        self.assertEqual(
            representation_status(
                {key: value for key, value in eligible.items() if key != "control_receipt"}
            )["status"],
            STATUS_CONTROL_REQUIRED,
        )
        self.assertEqual(
            representation_status({key: value for key, value in eligible.items() if key != "evidence_epoch_matches"})[
                "status"
            ],
            STATUS_OBSERVABILITY_BLOCKED,
        )
        self.assertEqual(
            representation_status({**eligible, "control_mode": "ORDINARY"})["status"],
            STATUS_OBSERVABILITY_BLOCKED,
        )
        self.assertEqual(
            representation_status(
                {
                    **eligible,
                    "control_terminal": "PASS_FAST_LANE_READY",
                }
            )["status"],
            STATUS_OBSERVABILITY_BLOCKED,
        )
        self.assertEqual(
            representation_status(
                {
                    **eligible,
                    "control_terminal": "KILL_DATA_INFEASIBLE",
                }
            )["status"],
            STATUS_OBSERVABILITY_BLOCKED,
        )
        self.assertEqual(
            representation_status(
                {
                    **eligible,
                    "control_terminal": "RUNNER_UP_REVISION_REQUIRED",
                }
            )["status"],
            STATUS_OBSERVABILITY_BLOCKED,
        )
        self.assertEqual(
            representation_status(
                {
                    **eligible,
                    "representation_probe_exists": True,
                    "existing_probe_identity_sha256": "dd" * 32,
                }
            )[
                "status"
            ],
            STATUS_OBSERVABILITY_BLOCKED,
        )
        self.assertEqual(
            representation_status(
                {
                    **eligible,
                    "representation_probe_state": "COMPLETE",
                    "existing_probe_identity_sha256": "ee" * 32,
                }
            )[
                "status"
            ],
            STATUS_OBSERVABILITY_BLOCKED,
        )
        self.assertEqual(
            representation_status({**eligible, "representation_probe_exists": True})[
                "status"
            ],
            STATUS_OBSERVABILITY_BLOCKED,
        )
        result = representation_status(eligible)
        self.assertTrue(result["read_only"])
        self.assertFalse(result["probe_executed"])
        self.assertFalse(result["alpha_claim"])

        invalid_readiness = dict(eligible["cohort_readiness_receipt"])
        invalid_readiness["yield_eligible"] = "10"
        self.assertEqual(
            representation_status(
                {**eligible, "cohort_readiness_receipt": invalid_readiness}
            )["status"],
            STATUS_OBSERVABILITY_BLOCKED,
        )
        self.assertEqual(
            representation_status(
                {key: value for key, value in eligible.items() if key != "cohort_readiness_receipt"}
            )["status"],
            STATUS_OBSERVABILITY_BLOCKED,
        )

        tampered_readiness = json.loads(
            json.dumps(eligible["cohort_readiness_receipt"])
        )
        tampered_readiness["release_manifest"]["schedule_sha256"] = "22" * 32
        tampered_readiness["schedule_sha256"] = "22" * 32
        tampered_readiness["receipt_sha256"] = canonical_sha256(
            {
                key: value
                for key, value in tampered_readiness.items()
                if key != "receipt_sha256"
            }
        )
        self.assertEqual(
            representation_status(
                {**eligible, "cohort_readiness_receipt": tampered_readiness}
            )["status"],
            STATUS_OBSERVABILITY_BLOCKED,
        )

        challenger = build_challenger_packet(
            baseline,
            project_normalized_trajectory([]),
            cohort_readiness_receipt=_cohort_readiness_receipt(),
        )
        incomplete_execution_receipt = {
            **challenger,
            "receipt_verified": True,
        }
        self.assertEqual(
            representation_status(
                {
                    **eligible,
                    "representation_probe_state": "COMPLETE",
                    "representation_probe_receipt": incomplete_execution_receipt,
                }
            )["status"],
            STATUS_OBSERVABILITY_BLOCKED,
        )

        for missing_key in (
            "control_session_id",
            "evidence_epoch_sha256",
            "control_packet_sha256",
            "memory_baseline_sha256",
        ):
            missing_anchor = dict(eligible)
            del missing_anchor[missing_key]
            self.assertEqual(
                representation_status(missing_anchor)["status"],
                STATUS_OBSERVABILITY_BLOCKED,
                missing_key,
            )


if __name__ == "__main__":
    unittest.main()
