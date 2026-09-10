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

from solana_alpha_lab.factory.hfic_control_integrity import (  # noqa: E402
    CURRENT_REPRESENTATION_CONTROL_V1,
)
from solana_alpha_lab.factory.hfic_preflight import MAX_PACKET_BYTES  # noqa: E402
from solana_alpha_lab.factory.hfic_representation_probe import (  # noqa: E402
    ControlBaseline,
    INVALID_CONTROL_PACKET_HASH,
    INVALID_CONTROL_NOT_RUN,
    INVALID_PROBE_IDENTITY,
    INVALID_MEMORY_BASELINE_DRIFT,
    INVALID_PACKET_BUDGET,
    INVALID_TRIGGER_NOT_MET,
    STATUS_CONTROL_REQUIRED,
    STATUS_ELIGIBLE,
    STATUS_OBSERVABILITY_BLOCKED,
    RepresentationProbeError,
    build_challenger_packet,
    control_baseline_from_receipt,
    control_memory_baseline_sha256,
    existing_hfic_lifecycle_fixture_input,
    existing_hfic_packet,
    representation_status,
)
from solana_alpha_lab.factory.normalized_trajectory_v1 import (  # noqa: E402
    PACKET_KEY,
    project_normalized_trajectory,
)
from solana_alpha_lab.factory.run_passport import canonical_sha256  # noqa: E402
from solana_alpha_lab.factory.document_runner import repository_git_snapshot  # noqa: E402
from solana_alpha_lab.factory.hfic_identity import candidate_identity  # noqa: E402
from solana_alpha_lab.factory.hfic_session import freeze_draft  # noqa: E402


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
    }
    receipt["memory_baseline_sha256"] = control_memory_baseline_sha256(receipt)
    return receipt


class HficRepresentationProbeTests(unittest.TestCase):
    def test_exact_control_clone_and_existing_hfic_fixture(self) -> None:
        receipt = _control_receipt()
        baseline = control_baseline_from_receipt(receipt)
        representation = project_normalized_trajectory([])
        challenger = build_challenger_packet(baseline, representation)

        self.assertEqual(challenger["evidence_epoch_sha256"], "aa" * 32)
        self.assertEqual(challenger["control_packet_sha256"], baseline.packet_sha256)
        self.assertEqual(challenger["memory_baseline_sha256"], baseline.memory_baseline_sha256)
        self.assertEqual(challenger["critic_input_packet"], baseline.packet)
        lifecycle_input = existing_hfic_lifecycle_fixture_input(challenger)
        self.assertEqual(lifecycle_input["representation"], challenger[PACKET_KEY])
        self.assertEqual(challenger[PACKET_KEY], challenger["normalized_trajectory_v1"])
        self.assertEqual(existing_hfic_packet(challenger), baseline.packet)
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
        Draft202012Validator(schema).validate(existing_hfic_packet(challenger))
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
        with self.assertRaises(RepresentationProbeError) as raised:
            control_baseline_from_receipt(missing_memory_hash)
        self.assertEqual(str(raised.exception), INVALID_MEMORY_BASELINE_DRIFT)

        receipt = _control_receipt()
        baseline = control_baseline_from_receipt(receipt)
        with self.assertRaises(RepresentationProbeError) as raised:
            build_challenger_packet(
                baseline,
                project_normalized_trajectory([]),
                registered_probe_identity_sha256="dd" * 32,
            )
        self.assertEqual(str(raised.exception), INVALID_PROBE_IDENTITY)

        challenger = build_challenger_packet(baseline, project_normalized_trajectory([]))
        with self.assertRaises(RepresentationProbeError) as raised:
            build_challenger_packet(
                baseline,
                project_normalized_trajectory([]),
                registered_probe_identity_sha256=challenger["probe_identity_sha256"],
            )
        self.assertEqual(str(raised.exception), "REPRESENTATION_PROBE_ALREADY_EXISTS")

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

    def test_fixture_bridge_rechecks_outer_identity(self) -> None:
        receipt = _control_receipt()
        baseline = control_baseline_from_receipt(receipt)
        challenger = build_challenger_packet(baseline, project_normalized_trajectory([]))
        drifted = dict(challenger)
        drifted["control_session_id"] = "different-session"
        with self.assertRaises(RepresentationProbeError) as raised:
            existing_hfic_lifecycle_fixture_input(drifted)
        self.assertEqual(str(raised.exception), INVALID_PROBE_IDENTITY)

    def test_runner_up_or_case_a_cannot_create_challenger(self) -> None:
        receipt = _control_receipt()
        receipt["final_session_terminal"] = "RUNNER_UP_REVISION_REQUIRED"
        baseline = control_baseline_from_receipt(receipt)
        with self.assertRaises(RepresentationProbeError) as raised:
            build_challenger_packet(baseline, project_normalized_trajectory([]))
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
        oversized_receipt["memory_baseline_sha256"] = control_memory_baseline_sha256(
            oversized_receipt
        )
        with self.assertRaises(RepresentationProbeError) as raised:
            build_challenger_packet(oversized_receipt, project_normalized_trajectory([]))
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
            "cohort_ready": True,
            "readiness": "READY_VALID",
            "yield_eligible": 10,
        }
        self.assertEqual(representation_status({})["status"], STATUS_CONTROL_REQUIRED)
        self.assertEqual(representation_status(eligible)["status"], STATUS_ELIGIBLE)
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
