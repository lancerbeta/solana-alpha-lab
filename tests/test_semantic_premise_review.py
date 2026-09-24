from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from solana_alpha_lab.semantic_premise_review import (  # noqa: E402
    SemanticPremiseReviewError,
    build_semantic_premise_packet,
    classify_review_profile,
    evaluate_fixture_premise,
    load_profile,
    map_semantic_verdict_to_architecture,
    packet_is_stale,
    require_packet_fingerprint_in_findings,
    validate_launch_inputs,
)

sys.path.insert(0, str(ROOT / "scripts"))
from owner_attention_gate import REQUIRED_REVIEW_ROLES  # noqa: E402

FIXTURES = ROOT / "tests/fixtures/semantic_premise"


def _minimal_packet(**overrides):
    kwargs = {
        "repo_root": ROOT,
        "task_id": "T",
        "task_contract_bytes": b"task-v1",
        "base": "a" * 40,
        "head": "b" * 40,
        "diff_bytes": b"diff-v1",
        "semantic_claims": [
            {"claim_id": "C1", "claim": "bounded", "scope": "exact"}
        ],
        "non_claims": ["family remains UNKNOWN"],
        "evidence": [
            {
                "asset_id": None,
                "logical_ref": "x",
                "sha256_or_fingerprint": "1" * 64,
            }
        ],
        "risk_dimensions": ["HYPOTHESIS_OR_FAMILY_CLOSURE"],
        "profile": load_profile(ROOT),
    }
    kwargs.update(overrides)
    return build_semantic_premise_packet(**kwargs)


class SemanticPremiseReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile = load_profile(ROOT)

    def test_ordinary_paths_use_standard_profile(self) -> None:
        result = classify_review_profile(
            changed_paths=["scripts/generate_navigation.py", "docs/OPERATOR_NAVIGATION.md"],
            task_text="# routine refactor\n",
            repo_root=ROOT,
        )
        self.assertEqual(result["profile"], "STANDARD")
        self.assertIs(result["authority_granted"], False)

    def test_semantic_path_prefix_activates_profile(self) -> None:
        result = classify_review_profile(
            changed_paths=["./configs/hypothesis_forge_independent_critic_v1.yaml"],
            task_text="# no marker\n",
            repo_root=ROOT,
        )
        self.assertEqual(result["profile"], "SEMANTIC_PREMISE")
        self.assertIn("HYPOTHESIS_OR_FAMILY_CLOSURE", result["risk_dimensions"])

    def test_task_marker_activates_without_nlp(self) -> None:
        result = classify_review_profile(
            changed_paths=["README.md"],
            task_text="SEMANTIC_PREMISE_HIGH_RISK: true\n",
            repo_root=ROOT,
        )
        self.assertEqual(result["profile"], "SEMANTIC_PREMISE")
        self.assertEqual(result["reason"], "TASK_BODY_MARKER")

    def test_no_fourth_review_role(self) -> None:
        self.assertEqual(
            REQUIRED_REVIEW_ROLES,
            {"CODE_REVIEWER", "GOAL_DOD_CRITIC", "ARCHITECTURE_CRITIC"},
        )
        self.assertNotIn("SEMANTIC_PREMISE_CRITIC", REQUIRED_REVIEW_ROLES)
        self.assertIs(self.profile["new_permanent_review_role"], False)

    def test_packet_excludes_implementation_transcript(self) -> None:
        with self.assertRaises(SemanticPremiseReviewError):
            _minimal_packet(
                evidence=[
                    {
                        "asset_id": None,
                        "logical_ref": "x",
                        "sha256_or_fingerprint": "1" * 64,
                        "implementation_transcript": "secret chat",
                    }
                ]
            )

    def test_stale_candidate_invalidates_packet(self) -> None:
        packet = _minimal_packet()
        self.assertFalse(
            packet_is_stale(
                packet,
                task_contract_bytes=b"task-v1",
                base="a" * 40,
                head="b" * 40,
                diff_bytes=b"diff-v1",
                semantic_claims=[
                    {"claim_id": "C1", "claim": "bounded", "scope": "exact"}
                ],
                non_claims=["family remains UNKNOWN"],
                evidence=[
                    {
                        "asset_id": None,
                        "logical_ref": "x",
                        "sha256_or_fingerprint": "1" * 64,
                    }
                ],
                risk_dimensions=["HYPOTHESIS_OR_FAMILY_CLOSURE"],
            )
        )
        self.assertTrue(
            packet_is_stale(
                packet,
                task_contract_bytes=b"task-v2",
                base="a" * 40,
                head="b" * 40,
                diff_bytes=b"diff-v1",
                semantic_claims=[
                    {"claim_id": "C1", "claim": "bounded", "scope": "exact"}
                ],
                non_claims=["family remains UNKNOWN"],
                evidence=[
                    {
                        "asset_id": None,
                        "logical_ref": "x",
                        "sha256_or_fingerprint": "1" * 64,
                    }
                ],
                risk_dimensions=["HYPOTHESIS_OR_FAMILY_CLOSURE"],
            )
        )

    def test_model_diversity_defaults_unproven(self) -> None:
        packet = _minimal_packet()
        independence = packet["independence"]
        self.assertEqual(independence["model_diversity"], "UNPROVEN")
        self.assertIsNone(independence["model_diversity_identity"])
        self.assertEqual(independence["claim_scope"], "PACKET_INFORMATION_PATH")
        self.assertEqual(independence["launch_isolation"], "PROCESS_OBLIGATION")
        self.assertIs(independence["implementation_transcript_seen"], False)

    def test_model_diversity_proven_requires_identity(self) -> None:
        with self.assertRaises(SemanticPremiseReviewError) as ctx:
            _minimal_packet(model_diversity="PROVEN")
        self.assertIn("MODEL_DIVERSITY_PROVEN_REQUIRES_IDENTITY", str(ctx.exception))
        packet = _minimal_packet(
            model_diversity="PROVEN",
            model_diversity_identity="other-family-model-id",
        )
        self.assertEqual(packet["independence"]["model_diversity"], "PROVEN")
        self.assertEqual(
            packet["independence"]["model_diversity_identity"],
            "other-family-model-id",
        )

    def test_inconclusive_maps_to_not_ready(self) -> None:
        mapped = map_semantic_verdict_to_architecture("INCONCLUSIVE", self.profile)
        self.assertEqual(mapped, "NOT_READY")

    def test_validate_launch_requires_packet_for_semantic(self) -> None:
        classification = {"profile": "SEMANTIC_PREMISE", "risk_dimensions": ["X"]}
        with self.assertRaises(SemanticPremiseReviewError) as ctx:
            validate_launch_inputs(
                classification=classification,
                packet=None,
                repo_root=ROOT,
            )
        self.assertIn("SEMANTIC_PACKET_REQUIRED", str(ctx.exception))

        packet = _minimal_packet()
        ok = validate_launch_inputs(
            classification=classification,
            packet=packet,
            repo_root=ROOT,
            task_contract_bytes=b"task-v1",
            base="a" * 40,
            head="b" * 40,
            diff_bytes=b"diff-v1",
            semantic_claims=[
                {"claim_id": "C1", "claim": "bounded", "scope": "exact"}
            ],
            non_claims=["family remains UNKNOWN"],
            evidence=[
                {
                    "asset_id": None,
                    "logical_ref": "x",
                    "sha256_or_fingerprint": "1" * 64,
                }
            ],
            risk_dimensions=["HYPOTHESIS_OR_FAMILY_CLOSURE"],
        )
        self.assertTrue(ok["ok"])
        self.assertEqual(ok["packet_fingerprint_sha256"], packet["packet_fingerprint_sha256"])

        with self.assertRaises(SemanticPremiseReviewError) as stale_ctx:
            validate_launch_inputs(
                classification=classification,
                packet=packet,
                repo_root=ROOT,
                task_contract_bytes=b"task-v2",
                base="a" * 40,
                head="b" * 40,
                diff_bytes=b"diff-v1",
                semantic_claims=[
                    {"claim_id": "C1", "claim": "bounded", "scope": "exact"}
                ],
                non_claims=["family remains UNKNOWN"],
                evidence=[
                    {
                        "asset_id": None,
                        "logical_ref": "x",
                        "sha256_or_fingerprint": "1" * 64,
                    }
                ],
                risk_dimensions=["HYPOTHESIS_OR_FAMILY_CLOSURE"],
            )
        self.assertIn("SEMANTIC_PACKET_STALE", str(stale_ctx.exception))

    def test_standard_launch_omits_packet(self) -> None:
        result = validate_launch_inputs(
            classification={"profile": "STANDARD"},
            packet=None,
            repo_root=ROOT,
        )
        self.assertTrue(result["ok"])
        self.assertFalse(result["packet_required"])

    def test_findings_must_bind_packet_fingerprint(self) -> None:
        packet = _minimal_packet()
        require_packet_fingerprint_in_findings(
            f"ok\npacket_fingerprint_sha256={packet['packet_fingerprint_sha256']}\n",
            packet,
        )
        with self.assertRaises(SemanticPremiseReviewError):
            require_packet_fingerprint_in_findings("PASS without binding", packet)

    def test_smoke_fixtures(self) -> None:
        for name, expected in [
            ("false_global_closure.json", "NOT_READY"),
            ("bounded_closure_pass.json", "PASS"),
            ("unknown_as_negative.json", "NOT_READY"),
        ]:
            fixture = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
            packet = build_semantic_premise_packet(
                repo_root=ROOT,
                task_id=fixture["task_id"],
                task_contract_bytes=fixture["task_contract_text"].encode("utf-8"),
                base=fixture["base"],
                head=fixture["head"],
                diff_bytes=fixture["diff_text"].encode("utf-8"),
                semantic_claims=fixture["semantic_claims"],
                non_claims=fixture.get("non_claims") or [],
                evidence=fixture.get("evidence") or [],
                risk_dimensions=fixture.get("risk_dimensions") or [],
                model_diversity=fixture.get("model_diversity") or "UNPROVEN",
                model_diversity_identity=fixture.get("model_diversity_identity"),
                profile=self.profile,
            )
            self.assertEqual(packet["review"]["profile"], "SEMANTIC_PREMISE")
            result = evaluate_fixture_premise(
                claims=fixture["semantic_claims"],
                non_claims=fixture.get("non_claims") or [],
            )
            mapped = map_semantic_verdict_to_architecture(
                result["semantic_verdict"], self.profile
            )
            self.assertEqual(mapped, expected)
            self.assertEqual(result["architecture_verdict"], expected)

    def test_semantic_routes_grant_no_authority(self) -> None:
        from solana_alpha_lab.factory_semantic_operability import (
            load_semantic_projection,
        )

        projection = load_semantic_projection(ROOT)
        self.assertIs(projection["authority_granted"], False)

    def test_architecture_critic_documents_semantic_profile(self) -> None:
        text = (ROOT / ".cursor/agents/architecture-critic.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("SEMANTIC_PREMISE", text)
        self.assertIn("PACKET_INFORMATION_PATH", text)
        self.assertIn("PROCESS_OBLIGATION", text)
        self.assertIn("packet_fingerprint_sha256=", text)
        self.assertIn("implementation transcript", text.casefold())
        self.assertNotIn("SEMANTIC_PREMISE_CRITIC", text)

    def test_delivery_review_requires_validate_launch(self) -> None:
        text = (ROOT / ".cursor/commands/delivery-review.md").read_text(encoding="utf-8")
        self.assertIn("validate-launch", text)
        self.assertIn("PACKET_INFORMATION_PATH", text)


if __name__ == "__main__":
    unittest.main()
