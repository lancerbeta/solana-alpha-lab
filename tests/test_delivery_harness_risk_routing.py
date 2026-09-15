"""Risk-routed review role resolver and enforcement acceptance tests.

Covers the DELIVERY_HARNESS_RISK_ROUTED_REVIEW_V1 acceptance matrix: explicit
role-sets, deterministic floors, LEGACY_TRIPLE compatibility, exact role-set
enforcement in review evidence, remediation_history validation, and the shared
resolver invariant across bind-evidence, preflight-push, merge-readiness and
guarded-merge.
"""

from __future__ import annotations

import sys
import tempfile
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

    def test_6d_floor_prefix_matching_is_exact_for_files(self) -> None:
        # CODE_REVIEWER MINOR 6: file entries match exactly; sibling files
        # using the name as a prefix (AGENTS.md.bak) must not trigger the
        # floor, while subpaths under directory entries and exact script
        # paths must.
        for path, expected_arch in [
            ("AGENTS.md.bak", False),
            ("AGENTS.md", True),
            ("scripts/owner_attention_gate.py.orig", False),
            ("scripts/owner_attention_gate.py", True),
            ("control/anything.yaml", True),
            ("controlx/anything.yaml", False),
        ]:
            with self.subTest(path=path):
                effective = gate.effective_required_roles(
                    {"required_review_roles": ["CODE_REVIEWER"]},
                    candidate_paths={path},
                )
                self.assertEqual(
                    "ARCHITECTURE_CRITIC" in effective, expected_arch
                )

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

    def test_fail_closed_bound_contract_unreadable(self) -> None:
        # MINOR 4 remediation: a receipt that names a contract which cannot
        # be read must raise (DENY) instead of silently degrading to the
        # legacy triple. Absence of a binding stays LEGACY_TRIPLE.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt = {
                "task": {"task_id": "TEST", "path": "docs/tasks/missing.md"}
            }
            with self.assertRaisesRegex(ValueError, "TASK_CONTRACT_UNREADABLE"):
                gate._task_contract_metadata(root, receipt)
            with self.assertRaisesRegex(
                ValueError, "CANDIDATE_PATHS_UNREADABLE"
            ):
                gate._candidate_paths_for_roles(
                    root, {"task": {"task_id": "TEST", "path": "docs/tasks/missing.md", "sha256": "0" * 64}}
                )
        # No binding at all -> deliberate legacy triple, not an error.
        self.assertEqual(
            gate.effective_required_roles(
                gate._task_contract_metadata(Path("."), {"task": {"task_id": "X"}})
            ),
            set(gate.LEGACY_TRIPLE),
        )


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
    """Acceptance 12/13: identical role resolution across gates.

    Real two-path comparison: the merge-gate path (gate resolver over the
    receipt-bound contract metadata and candidate diff) versus the
    bind/preflight path (harness_sync._effective_required_roles_for_task over
    the same contract and the same base..head diff), executed on this live
    worktree.
    """

    TASK_RELATIVE = "docs/tasks/DELIVERY_HARNESS_RISK_ROUTED_REVIEW_V1.md"
    TASK_ID = "DELIVERY_HARNESS_RISK_ROUTED_REVIEW_V1"

    @classmethod
    def setUpClass(cls) -> None:
        import subprocess

        cls.head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT,
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        cls.metadata = gate.load_delivery_harness_runtime(ROOT).parse_task_contract(
            ROOT, cls.TASK_RELATIVE, cls.TASK_ID
        )
        cls.expected_base = cls.metadata["git_binding"]["expected_base"]

    def test_12_bind_evidence_and_merge_gate_resolve_identical_set(self) -> None:
        import subprocess

        sys.path.insert(0, str(SCRIPTS))
        import harness_sync  # noqa: E402

        # Merge-gate path: canonical resolver over contract metadata plus the
        # candidate diff computed exactly like bound_delivery_evidence does.
        diff_output = subprocess.run(
            ["git", "diff", "--name-only", "--no-renames", "-z",
             f"{self.expected_base}...{self.head}"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout
        candidate_paths = {
            item.replace("\\", "/") for item in diff_output.split("\0") if item
        }
        gate_set = gate.effective_required_roles(
            self.metadata, live_pr_head=False, candidate_paths=candidate_paths
        )
        # Bind/preflight path: the harness_sync wrapper over the same
        # contract and diff, used by compute_evidence_chain.
        original_root = harness_sync.ROOT
        harness_sync.ROOT = ROOT
        try:
            sync_set = harness_sync._effective_required_roles_for_task(
                self.metadata, expected_base=self.expected_base, head=self.head
            )
        finally:
            harness_sync.ROOT = original_root
        self.assertEqual(gate_set, sync_set)
        # The frozen contract lists the triple; the atom diff touches
        # schema/control surfaces so the architecture floor must hold on both
        # paths identically.
        self.assertEqual(
            gate_set,
            {"CODE_REVIEWER", "GOAL_DOD_CRITIC", "ARCHITECTURE_CRITIC"},
        )

    def test_13_preflight_and_merge_gate_resolve_identical_set(self) -> None:
        # Preflight reaches the resolver through verify_evidence_chain ->
        # compute_evidence_chain -> _effective_required_roles_for_task; the
        # merge gate reaches it through bound_delivery_evidence. Exercise the
        # shared entry (compute path) for the exact receipt-bound head and
        # compare with the gate-side resolver over the same inputs.
        import subprocess

        sys.path.insert(0, str(SCRIPTS))
        import harness_sync  # noqa: E402

        # The full compute path requires the contract's evidence paths to be
        # committed (they are the excluded inventory entries). Mid-flow local
        # runs before the evidence commit skip; CI runs on the exact PR head
        # where they are committed and exercise the full path.
        committed = subprocess.run(
            ["git", "diff", "--name-only", "--no-renames",
             f"{self.expected_base}...{self.head}"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout.splitlines()
        evidence_paths = set(
            self.metadata["context_requirements"]["exact_role_paths"]["DELIVERY_EVIDENCE"]
        ) if isinstance(
            self.metadata.get("context_requirements", {}).get("exact_role_paths"),
            dict,
        ) else set()
        if not evidence_paths or not evidence_paths.issubset(set(committed)):
            self.skipTest(
                "evidence paths not yet committed (mid-flow before BIND EVIDENCE)"
            )

        original_root = harness_sync.ROOT
        harness_sync.ROOT = ROOT
        try:
            chain = harness_sync.compute_evidence_chain(
                task_id=self.TASK_ID, contract=self.TASK_RELATIVE
            )
        finally:
            harness_sync.ROOT = original_root
        preflight_roles = set(chain["effective_required_roles"])

        diff_output = subprocess.run(
            ["git", "diff", "--name-only", "--no-renames", "-z",
             f"{self.expected_base}...{chain['head']}"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout
        candidate_paths = {
            item.replace("\\", "/") for item in diff_output.split("\0") if item
        }
        merge_roles = gate.effective_required_roles(
            self.metadata, live_pr_head=False, candidate_paths=candidate_paths
        )
        self.assertEqual(preflight_roles, merge_roles)

    def test_20_under_scope_finding_blocks_final_closure(self) -> None:
        # A CODE_REVIEWER under-scope finding is a NOT_READY verdict on the
        # final required critic, which the shape validator denies. The
        # finding text itself (REVIEW_PLAN_UNDERSCOPED:<ROLE>) carries the
        # missing role; closure requires strengthening the plan (replan +
        # new context receipt) and re-review, which acceptance 3 enforces:
        # a review claiming the missing role as required while the frozen
        # plan lacks it is an exact-set MISMATCH and stays denied until the
        # contract itself is strengthened.
        review = _review(required=["CODE_REVIEWER", "OWNER_UX_CRITIC"])
        review["reviews"] = [
            {
                "role": "CODE_REVIEWER",
                "verdict": "NOT_READY",
                "findings": ["BLOCKER REVIEW_PLAN_UNDERSCOPED:OWNER_UX_CRITIC"],
            }
        ]
        # Under the frozen (unstRENGTHENED) plan the role-set is still
        # [CODE_REVIEWER] only -> exact-set mismatch denies closure.
        frozen_plan_problems = gate.delivery_independent_review_shape_problems(
            review, effective_roles={"CODE_REVIEWER"}
        )
        self.assertIn("review_required_roles_incomplete", frozen_plan_problems)
        self.assertIn("review_role_verdict_not_pass", frozen_plan_problems)
        # After a legitimate strengthening replan, the strengthened plan
        # resolves both roles; until a final PASS exists for every role
        # (including the added OWNER_UX_CRITIC) closure stays denied — the
        # under-scope finding's demanded role cannot be skipped.
        strengthened_problems = gate.delivery_independent_review_shape_problems(
            review, effective_roles={"CODE_REVIEWER", "OWNER_UX_CRITIC"}
        )
        self.assertNotIn("review_required_roles_incomplete", strengthened_problems)
        self.assertIn("review_roles_incomplete", strengthened_problems)
        # And once the strengthened plan is fully re-reviewed with final PASS
        # entries for both roles, closure passes.
        healed = _review(
            required=["CODE_REVIEWER", "OWNER_UX_CRITIC"],
            roles=["CODE_REVIEWER", "OWNER_UX_CRITIC"],
        )
        healed_problems = gate.delivery_independent_review_shape_problems(
            healed, effective_roles={"CODE_REVIEWER", "OWNER_UX_CRITIC"}
        )
        self.assertEqual(healed_problems, [])


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
