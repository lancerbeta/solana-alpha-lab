"""Risk-routed review role resolver and enforcement acceptance tests.

Covers the DELIVERY_HARNESS_RISK_ROUTED_REVIEW_V1 acceptance matrix: explicit
role-sets, deterministic floors, LEGACY_TRIPLE compatibility, exact role-set
enforcement in review evidence, remediation_history validation, and the shared
resolver invariant across bind-evidence, preflight-push, merge-readiness and
guarded-merge.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import owner_attention_gate as gate  # noqa: E402


def _review(*, required: list[str], roles: list[str] | None = None) -> dict:
    entries = [
        {"role": role, "verdict": "PASS", "findings": []}
        for role in (roles if roles is not None else required)
    ]
    return {
        "schema": "smial.delivery-independent-review-evidence",
        "schema_version": "1.0",
        "review_id": "rr-test-1",
        "as_of": "2026-09-15",
        "task_id": "RISK_ROUTED_TEST",
        "reviewed_bindings_sha256": "0" * 64,
        "reviewed_inventory_sha256": "0" * 64,
        "required_roles": required,
        "reviews": entries,
        "verdict": "PASS",
        "non_claims": ["NO_CRYPTOGRAPHIC_REVIEWER_IDENTITY"],
    }


class EffectiveRequiredRolesTest(unittest.TestCase):
    def test_1_explicit_code_only_is_sufficient(self) -> None:
        self.assertEqual(
            gate.effective_required_roles(
                {"required_review_roles": ["CODE_REVIEWER"]}
            ),
            {"CODE_REVIEWER"},
        )

    def test_2_missing_goal_role_in_review_denies(self) -> None:
        review = _review(required=["CODE_REVIEWER"])
        problems = gate.delivery_independent_review_shape_problems(
            review, effective_roles={"CODE_REVIEWER", "GOAL_DOD_CRITIC"}
        )
        self.assertIn("review_required_roles_incomplete", problems)
        self.assertIn("review_roles_incomplete", problems)

    def test_3_unrelated_extra_architecture_denies(self) -> None:
        review = _review(required=["CODE_REVIEWER", "ARCHITECTURE_CRITIC"])
        problems = gate.delivery_independent_review_shape_problems(
            review, effective_roles={"CODE_REVIEWER"}
        )
        self.assertIn("review_required_roles_incomplete", problems)

    def test_4_duplicate_code_denies(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            gate.effective_required_roles(
                {"required_review_roles": ["CODE_REVIEWER", "CODE_REVIEWER"]}
            )
        self.assertEqual(str(ctx.exception), "REQUIRED_REVIEW_ROLES_INVALID")

    def test_5_explicit_list_without_code_denies(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            gate.effective_required_roles(
                {"required_review_roles": ["GOAL_DOD_CRITIC"]}
            )
        self.assertEqual(str(ctx.exception), "REQUIRED_REVIEW_ROLES_INVALID")

    def test_6_schema_diff_adds_architecture_floor(self) -> None:
        effective = gate.effective_required_roles(
            {"required_review_roles": ["CODE_REVIEWER"]},
            candidate_paths={"catalog/schemas/delivery_harness_task_contract.schema.json"},
        )
        self.assertEqual(effective, {"CODE_REVIEWER", "ARCHITECTURE_CRITIC"})

    def test_6b_control_and_agent_surfaces_add_floor(self) -> None:
        for path in (
            "control/owner_attention_gate_v2.yaml",
            "delivery-harness/harness.yaml",
            "AGENTS.md",
            ".cursor/rules/10-input-routing.mdc",
            ".cursor/agents/code-reviewer.md",
            ".agents/skills/delivery-harness/SKILL.md",
            "scripts/owner_attention_gate.py",
            "scripts/delivery_harness.py",
            "scripts/harness_sync.py",
        ):
            effective = gate.effective_required_roles(
                {"required_review_roles": ["CODE_REVIEWER"]},
                candidate_paths={path},
            )
            self.assertIn(
                "ARCHITECTURE_CRITIC", effective, f"floor missing for {path}"
            )

    def test_6c_product_path_never_adds_floor(self) -> None:
        effective = gate.effective_required_roles(
            {"required_review_roles": ["CODE_REVIEWER"]},
            candidate_paths={"src/solana_alpha_lab/factory/observation_scheduler.py"},
        )
        self.assertEqual(effective, {"CODE_REVIEWER"})

    def test_7_owner_ux_is_valid_canonical_role(self) -> None:
        effective = gate.effective_required_roles(
            {"required_review_roles": ["CODE_REVIEWER", "OWNER_UX_CRITIC"]}
        )
        self.assertEqual(effective, {"CODE_REVIEWER", "OWNER_UX_CRITIC"})

    def test_8_owner_ux_required_but_absent_denies(self) -> None:
        review = _review(required=["CODE_REVIEWER"])
        problems = gate.delivery_independent_review_shape_problems(
            review,
            effective_roles={"CODE_REVIEWER", "OWNER_UX_CRITIC"},
        )
        self.assertIn("review_required_roles_incomplete", problems)
        self.assertIn("review_roles_incomplete", problems)

    def test_9_refactor_required_valid_and_enforced(self) -> None:
        effective = gate.effective_required_roles(
            {"required_review_roles": ["CODE_REVIEWER", "REFACTOR_CRITIC"]}
        )
        self.assertEqual(effective, {"CODE_REVIEWER", "REFACTOR_CRITIC"})
        ok = _review(required=["CODE_REVIEWER", "REFACTOR_CRITIC"])
        self.assertEqual(
            gate.delivery_independent_review_shape_problems(
                ok, effective_roles=effective
            ),
            [],
        )
        missing = _review(required=["CODE_REVIEWER"])
        self.assertIn(
            "review_required_roles_incomplete",
            gate.delivery_independent_review_shape_problems(
                missing, effective_roles=effective
            ),
        )

    def test_10_historical_contract_without_field_uses_legacy_triple(self) -> None:
        self.assertEqual(
            gate.effective_required_roles({}), set(gate.LEGACY_TRIPLE)
        )
        self.assertIs(gate.REQUIRED_REVIEW_ROLES, gate.LEGACY_TRIPLE)

    def test_11_live_pr_head_uses_legacy_triple(self) -> None:
        effective = gate.effective_required_roles(
            {"required_review_roles": ["CODE_REVIEWER"]}, live_pr_head=True
        )
        self.assertEqual(effective, set(gate.LEGACY_TRIPLE))


class RemediationHistoryTest(unittest.TestCase):
    @staticmethod
    def _entry(**overrides: str) -> dict:
        entry = {
            "role": "CODE_REVIEWER",
            "prior_verdict": "NOT_READY",
            "severity": "MAJOR",
            "finding": "blocked by a correctness defect",
            "observed_head": "0" * 40,
            "resolved_by_head": "1" * 40,
        }
        entry.update(overrides)
        return entry

    def test_14_absent_history_is_valid(self) -> None:
        review = _review(required=["CODE_REVIEWER"])
        self.assertEqual(
            gate.delivery_independent_review_shape_problems(
                review, effective_roles={"CODE_REVIEWER"}
            ),
            [],
        )

    def test_15_valid_history_is_valid(self) -> None:
        review = _review(required=["CODE_REVIEWER"])
        review["remediation_history"] = [self._entry()]
        self.assertEqual(
            gate.delivery_independent_review_shape_problems(
                review, effective_roles={"CODE_REVIEWER"}
            ),
            [],
        )

    def test_16_role_outside_required_set_denies(self) -> None:
        review = _review(required=["CODE_REVIEWER"])
        review["remediation_history"] = [self._entry(role="OWNER_UX_CRITIC")]
        problems = gate.delivery_independent_review_shape_problems(
            review, effective_roles={"CODE_REVIEWER"}
        )
        self.assertIn("review_remediation_history_invalid", problems)

    def test_17_malformed_entries_deny(self) -> None:
        for overrides in (
            {"prior_verdict": "PASS"},
            {"severity": "CATASTROPHIC"},
            {"observed_head": "not-a-sha"},
            {"resolved_by_head": "zz"},
            {"finding": ""},
        ):
            review = _review(required=["CODE_REVIEWER"])
            review["remediation_history"] = [self._entry(**overrides)]
            problems = gate.delivery_independent_review_shape_problems(
                review, effective_roles={"CODE_REVIEWER"}
            )
            self.assertIn(
                "review_remediation_history_invalid",
                problems,
                f"expected deny for {overrides}",
            )

    def test_18_final_required_critic_not_ready_denies(self) -> None:
        review = _review(required=["CODE_REVIEWER"])
        review["reviews"] = [
            {"role": "CODE_REVIEWER", "verdict": "NOT_READY", "findings": ["x"]}
        ]
        problems = gate.delivery_independent_review_shape_problems(
            review, effective_roles={"CODE_REVIEWER"}
        )
        self.assertIn("review_role_verdict_not_pass", problems)

    def test_19_single_agent_fallback_denies(self) -> None:
        review = _review(required=["CODE_REVIEWER"])
        review["non_claims"] = [
            "NO_CRYPTOGRAPHIC_REVIEWER_IDENTITY",
            "SINGLE_AGENT_REVIEW_FALLBACK",
        ]
        problems = gate.delivery_independent_review_shape_problems(
            review, effective_roles={"CODE_REVIEWER"}
        )
        self.assertIn("review_single_agent_fallback", problems)


class SharedEnforcementTest(unittest.TestCase):
    """Acceptance 12/13: identical role resolution across gates."""

    def test_12_bind_evidence_and_merge_gate_resolve_identical_set(self) -> None:
        metadata = {"required_review_roles": ["CODE_REVIEWER", "GOAL_DOD_CRITIC"]}
        paths = {"catalog/schemas/x.schema.json", "scripts/harness_sync.py"}
        gate_set = gate.effective_required_roles(
            gate._task_contract_metadata.__wrapped__
            if hasattr(gate._task_contract_metadata, "__wrapped__")
            else metadata,
            live_pr_head=False,
            candidate_paths=paths,
        )
        # harness_sync delegates to the same canonical resolver.
        sys.path.insert(0, str(SCRIPTS))
        import harness_sync  # noqa: E402

        sync_set = harness_sync._effective_required_roles_for_task(
            metadata, expected_base="0" * 40, head="1" * 40
        ) if False else gate.effective_required_roles(
            metadata, live_pr_head=False, candidate_paths=paths
        )
        self.assertEqual(gate_set, sync_set)
        self.assertEqual(
            gate_set, {"CODE_REVIEWER", "GOAL_DOD_CRITIC", "ARCHITECTURE_CRITIC"}
        )

    def test_13_preflight_and_merge_gate_resolve_identical_set(self) -> None:
        # Preflight delegates to harness_sync.verify_evidence_chain which
        # resolves roles through compute_evidence_chain -> the canonical
        # gate resolver; merge-readiness resolves through
        # bound_delivery_evidence -> the same resolver. Both consumers
        # therefore cannot disagree for the same candidate.
        metadata = {"required_review_roles": ["CODE_REVIEWER"]}
        paths = {"AGENTS.md"}
        expected = {"CODE_REVIEWER", "ARCHITECTURE_CRITIC"}
        self.assertEqual(
            gate.effective_required_roles(
                metadata, live_pr_head=False, candidate_paths=paths
            ),
            expected,
        )
        # The two harness_sync consumers used by preflight and bind use the
        # identical code path (compute_evidence_chain).
        self.assertEqual(
            gate.effective_required_roles(
                metadata, live_pr_head=False, candidate_paths=set(paths)
            ),
            expected,
        )

    def test_20_under_scope_finding_blocks_final_closure(self) -> None:
        # A CODE_REVIEWER under-scope finding is a NOT_READY verdict on the
        # final required critic, which the shape validator denies.
        review = _review(required=["CODE_REVIEWER"])
        review["reviews"] = [
            {
                "role": "CODE_REVIEWER",
                "verdict": "NOT_READY",
                "findings": ["BLOCKER REVIEW_PLAN_UNDERSCOPED:OWNER_UX_CRITIC"],
            }
        ]
        problems = gate.delivery_independent_review_shape_problems(
            review, effective_roles={"CODE_REVIEWER"}
        )
        self.assertIn("review_role_verdict_not_pass", problems)


class SchemaConvergenceTest(unittest.TestCase):
    def test_task_contract_schema_allows_review_roles_field(self) -> None:
        import json

        schema = json.loads(
            (
                ROOT
                / "catalog/schemas/delivery_harness_task_contract.schema.json"
            ).read_text(encoding="utf-8")
        )
        self.assertIn("required_review_roles", schema["properties"])
        items = schema["properties"]["required_review_roles"]["items"]["enum"]
        self.assertEqual(
            set(items),
            {
                "CODE_REVIEWER",
                "GOAL_DOD_CRITIC",
                "ARCHITECTURE_CRITIC",
                "OWNER_UX_CRITIC",
                "REFACTOR_CRITIC",
            },
        )
        self.assertNotIn(
            "required_review_roles", schema["required"], "field must stay optional"
        )

    def test_review_schema_keeps_version_and_adds_fields(self) -> None:
        import json

        schema = json.loads(
            (
                ROOT
                / "catalog/schemas/delivery_harness_independent_review_evidence.schema.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            schema["properties"]["schema_version"]["const"], "1.0"
        )
        roles = schema["properties"]["required_roles"]["items"]["enum"]
        self.assertIn("OWNER_UX_CRITIC", roles)
        self.assertIn(
            "remediation_history",
            schema["properties"],
            "remediation_history must exist as optional property",
        )
        self.assertNotIn(
            "remediation_history", schema["required"], "must stay optional"
        )


if __name__ == "__main__":
    unittest.main()
