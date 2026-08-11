from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = (
    ROOT
    / "docs"
    / "contracts"
    / "bounded_sustained_collection_contract_v1.md"
)
FIXTURE_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task15"
    / "bounded_sustained_collection_contract_v1.json"
)
ARCHITECTURE_PATH = (
    ROOT
    / "docs"
    / "architecture"
    / "intents"
    / "ARCH-INTENT-002-hypothesis-factory-operating-model.md"
)
RECEIPT_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task15"
    / "hypothesis_driven_acquisition_acceptance_receipt_v1.json"
)
EXPECTED_CONTRACT_SHA256 = (
    "65f0ca725e8e3a28976d3f7286c8f8cea49180588704b12d75ddc7d12be7310e"
)
EXPECTED_FIXTURE_SHA256 = (
    "a1258f56c7521922876c1edd73ca77125e31294b623b8b793d6d5cfe2542235b"
)
EXPECTED_ARCHITECTURE_SNAPSHOT_SHA256 = (
    "ea094d88abf635fbe4df3b1ff9b3f0e80cb87dfa836f67505173766e69708639"
)
EXPECTED_RECEIPT_SHA256 = (
    "b96ba7e55529f79726cafb09e3ab6162a94e6a49eb667971418454b122110683"
)
TASK15_ASSET_IDS = {
    "ARCH-INTENT-002",
    "CONTRACT-T15-BOUNDED-SUSTAINED-COLLECTION-001",
    "FIXTURE-T15-HYPOTHESIS-DRIVEN-ACQUISITION-001",
    "TEST-T15-HYPOTHESIS-DRIVEN-ACQUISITION-001",
    "TEST-T15-HYPOTHESIS-DRIVEN-ACQUISITION-ACCEPTANCE-001",
    "EVIDENCE-T15-HYPOTHESIS-DRIVEN-ACQUISITION-ACCEPTANCE-001",
}


class Task15HypothesisDrivenAcquisitionAcceptanceTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract_bytes = CONTRACT_PATH.read_bytes()
        cls.fixture_bytes = FIXTURE_PATH.read_bytes()
        cls.fixture = json.loads(cls.fixture_bytes)
        cls.architecture_bytes = ARCHITECTURE_PATH.read_bytes()
        cls.architecture = cls.architecture_bytes.decode("utf-8")
        cls.receipt_bytes = RECEIPT_PATH.read_bytes()
        cls.receipt = json.loads(cls.receipt_bytes)

    def test_acceptance_binds_exact_contract_fixture_and_historical_intent(
        self,
    ) -> None:
        self.assertEqual(
            hashlib.sha256(self.contract_bytes).hexdigest(),
            EXPECTED_CONTRACT_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(self.fixture_bytes).hexdigest(),
            EXPECTED_FIXTURE_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(self.receipt_bytes).hexdigest(),
            EXPECTED_RECEIPT_SHA256,
        )
        self.assertEqual(self.receipt["verdict"], "PASS")
        self.assertEqual(
            self.receipt["accepted_contract"]["sha256"],
            EXPECTED_CONTRACT_SHA256,
        )
        self.assertEqual(
            self.receipt["frozen_fixture"]["sha256"],
            EXPECTED_FIXTURE_SHA256,
        )
        self.assertEqual(
            self.receipt["architecture_anchor"]["sha256"],
            EXPECTED_ARCHITECTURE_SNAPSHOT_SHA256,
        )

    def test_current_decision_remains_not_due_and_defer(self) -> None:
        self.assertEqual(
            self.fixture["current_disposition"]["acquisition_path"],
            "MEASUREMENT_NOT_DUE",
        )
        self.assertEqual(
            self.receipt["acceptance"]["acquisition_path"],
            "MEASUREMENT_NOT_DUE",
        )
        self.assertEqual(
            self.receipt["acceptance"]["provider_purchase"],
            "DEFER",
        )
        self.assertFalse(
            self.receipt["acceptance"][
                "global_detailed_watchlist_authorized"
            ]
        )
        self.assertTrue(
            self.receipt["acceptance"][
                "triggered_live_capture_requires_historical_falsifier"
            ]
        )

    def test_architecture_intent_preserves_factory_lifecycle(self) -> None:
        required = (
            "hypothesis_family",
            "hypothesis_version",
            "hypothesis_origin",
            "hypothesis_derivation_edge",
            "research_artifact",
            "hypothesis_data_requirement",
            "watchlist_membership",
            "activation_epoch",
            "position",
            "tool_capability",
            "regime_observation",
            "multiple-testing",
            "owner-facing pulse",
        )
        for term in required:
            with self.subTest(term=term):
                self.assertIn(term, self.architecture)
        self.assertIn(
            "triggered live capture only for non-reconstructable evidence",
            self.architecture,
        )
        self.assertIn(
            "Canonical Project Sources and\nroadmap versions change only",
            self.architecture,
        )
        self.assertIn("## Factory leverage invariant", self.architecture)
        self.assertIn("comparable new hypotheses", self.architecture)
        self.assertIn(
            "not an automatic block or a\nsecond control plane",
            self.architecture,
        )

    def test_hypothesis_research_memory_is_reproducible_and_append_only(
        self,
    ) -> None:
        memory = self.receipt["hypothesis_research_memory"]
        self.assertEqual(
            memory["status"],
            "ARCHITECTURE_REQUIREMENT_ACCEPTED_NOT_IMPLEMENTED",
        )
        self.assertTrue(memory["applies_to_all_origin_kinds"])
        self.assertEqual(
            set(memory["origin_kinds"]),
            {
                "OWNER_OBSERVATION",
                "DATA_ANALYSIS",
                "AI_HYPOTHESIS_MINING",
                "EXTERNAL_RESEARCH",
                "TOOL_OR_FRAMEWORK_OUTPUT",
                "DERIVED_FROM_EXISTING_HYPOTHESIS",
                "OTHER_DECLARED",
            },
        )
        self.assertTrue(memory["append_only"])
        self.assertTrue(
            memory["corrections_use_version_or_supersedes_event"]
        )
        self.assertTrue(
            memory["prior_work_query_before_new_research_cycle"]
        )
        self.assertFalse(
            memory["semantic_similarity_auto_rejects_candidate"]
        )
        self.assertFalse(memory["sensitive_raw_conversation_required"])
        for statement in (
            "Every `hypothesis_version` has an append-only provenance chain",
            "Origin prestige never substitutes for evidence.",
            "History is append-only.",
            "queries this memory for",
            "what changed and why repeating or extending the work",
            "negative history into input for derivative insights",
        ):
            with self.subTest(statement=statement):
                self.assertIn(statement, self.architecture)

    def test_owner_pulse_covers_hypotheses_positions_finance_and_health(
        self,
    ) -> None:
        required = (
            "hypotheses are exploring",
            "tokens are currently evaluated or watched",
            "positions are open",
            "gross and net financial result",
            "datasets/providers/tools are stale",
            "owner decisions need attention",
        )
        for statement in required:
            with self.subTest(statement=statement):
                self.assertIn(statement, self.architecture)
        self.assertIn(
            "does not become a second truth owner",
            self.architecture,
        )

    def test_execution_bridge_connects_hypothesis_to_reconciled_cashflow(
        self,
    ) -> None:
        bridge = self.receipt["execution_and_position_bridge"]
        self.assertEqual(
            bridge["status"],
            "ARCHITECTURE_REQUIREMENT_ACCEPTED_NOT_IMPLEMENTED",
        )
        self.assertEqual(
            bridge["required_chain"][0],
            "HYPOTHESIS_VERSION",
        )
        self.assertEqual(
            bridge["required_chain"][-1],
            "STRATEGY_DEGRADATION_AND_HYPOTHESIS_FEEDBACK",
        )
        self.assertTrue(
            bridge[
                "replaceable_plumbing_requires_adopt_wrap_fork_build"
            ]
        )
        self.assertFalse(
            bridge[
                "third_party_component_owns_hypothesis_risk_position_"
                "or_cashflow_truth"
            ]
        )
        self.assertTrue(
            bridge["shared_replay_paper_shadow_live_interfaces_required"]
        )
        self.assertTrue(
            bridge["monitoring_is_precondition_for_live_authority"]
        )
        self.assertTrue(
            bridge[
                "overlapping_hypotheses_retain_logical_position_attribution"
            ]
        )
        self.assertTrue(bridge["account_level_risk_aggregation_required"])
        self.assertTrue(
            bridge[
                "unknown_transaction_state_requires_reconciliation_"
                "before_retry"
            ]
        )
        self.assertFalse(
            bridge[
                "monitoring_loss_with_open_inventory_allows_new_entries"
            ]
        )
        for statement in (
            "A trigger is not an order",
            "logical attribution stays separate",
            "A third-party bot or router never becomes the owner",
            "Monitoring is a precondition for live authority",
            "reconcile first",
            "pauses new entries and escalates recovery",
        ):
            with self.subTest(statement=statement):
                self.assertIn(statement, self.architecture)

    def test_research_tool_routing_is_problem_and_contract_driven(
        self,
    ) -> None:
        for field in (
            "question",
            "estimand",
            "population and controls",
            "required output",
            "error cost",
            "validation owner",
        ):
            with self.subTest(field=field):
                self.assertIn(field, self.architecture)
        self.assertIn(
            "A new tool is added only when a named research question",
            self.architecture,
        )
        self.assertIn(
            "Tool adoption never bypasses statistical validation.",
            self.architecture,
        )

    def test_roadmap_reconciliation_is_required_but_not_claimed_done(
        self,
    ) -> None:
        roadmap = self.receipt["roadmap_reconciliation"]
        self.assertEqual(
            roadmap["status"],
            "REQUIRED_AFTER_REPOSITORY_ACCEPTANCE_NOT_PERFORMED_IN_A3",
        )
        self.assertIn(
            "OWNER_PULSE_DASHBOARD_AND_PROBLEM_MONITORING",
            roadmap["required_meaning"],
        )
        self.assertIn(
            "RESEARCH_TOOL_CAPABILITY_REGISTRY_AND_ROUTER",
            roadmap["required_meaning"],
        )
        self.assertIn(
            "APPEND_ONLY_HYPOTHESIS_PROVENANCE_AND_DERIVATION_LEDGER",
            roadmap["required_meaning"],
        )
        self.assertIn(
            "RESEARCH_MEMORY_QUERY_BEFORE_NEW_TRIAL",
            roadmap["required_meaning"],
        )
        self.assertIn(
            "VERSIONED_TRIGGER_TO_CASHFLOW_EXECUTION_BRIDGE",
            roadmap["required_meaning"],
        )
        self.assertIn(
            "POSITION_ATTRIBUTION_ACCOUNT_RISK_AND_RECONCILIATION_TRUTH",
            roadmap["required_meaning"],
        )
        self.assertIn(
            "LIVE_REQUIRES_MONITORING_KILL_SWITCH_INCIDENT_AND_RECOVERY",
            roadmap["required_meaning"],
        )
        self.assertIn(
            "LIVE_CAPTURE_ONLY_FOR_PROVEN_NON_RECONSTRUCTABLE_NEEDS",
            roadmap["required_meaning"],
        )
        self.assertIn(
            "MANDATORY_FACTORY_FIT_REVIEW_FOR_EVERY_FUTURE_TASK",
            roadmap["required_meaning"],
        )
        self.assertIn(
            "FACTORY_FIT_RECONCILED_INTO_OS_ROADMAP_AND_FINISH_SKILL",
            roadmap["required_meaning"],
        )

    def test_factory_fit_gate_is_adversarial_and_non_bureaucratic(
        self,
    ) -> None:
        review = self.receipt["factory_fit_review"]
        self.assertEqual(
            review["timing"],
            "AFTER_TECHNICAL_DOD_BEFORE_COMPLETION_BUNDLE",
        )
        self.assertEqual(
            review["applicability"],
            "MANDATORY_FOR_EVERY_FUTURE_CANONICAL_TASK",
        )
        self.assertEqual(
            set(review["allowed_review_depths"]),
            {"FAST_PATH", "FULL_REVIEW"},
        )
        self.assertEqual(review["review_depth"], "FULL_REVIEW")
        self.assertEqual(
            review["verdict"],
            "FACTORY_FIT_PASS_WITH_FOLLOWUP",
        )
        self.assertEqual(
            {item["dimension"] for item in review["dimensions"]},
            {
                "MISSION_AND_NAMED_CONSUMER",
                "FLEXIBILITY_AND_CHANGE_AMPLIFICATION",
                "COMPATIBILITY_HISTORY_AND_PIT",
                "EFFICIENCY_AND_EVIDENCE_ECONOMY",
                "RESEARCH_AND_STATISTICAL_TRUTH",
                "OWNER_OPERABILITY",
                "EXECUTION_POSITION_MONITORING_BRIDGE",
                "SAFETY_AND_AUTHORITY",
                "ADVERSARIAL_SCALE_AND_DRIFT",
            },
        )
        self.assertTrue(
            all(
                item["result"] == "PASS"
                for item in review["dimensions"]
            )
        )
        amplification = review["observed_change_amplification"]
        self.assertEqual(
            amplification["signal"],
            "LIVE_CATALOG_CHECKPOINT_VALUES_DUPLICATED_ACROSS_DIRECT_CONSUMERS",
        )
        self.assertEqual(
            amplification["measured_direct_consumer_files_updated"],
            11,
        )
        self.assertFalse(amplification["historical_receipts_changed"])
        self.assertEqual(review["required_patches"], [])
        self.assertEqual(
            review["bounded_followup_candidate"],
            "CENTRALIZE_LIVE_CATALOG_CHECKPOINT_ASSERTIONS_WHILE_"
            "PRESERVING_HISTORICAL_RECEIPTS",
        )
        followup = review["durable_followup"]
        self.assertEqual(followup["status"], "RECORDED_NON_BLOCKING")
        self.assertEqual(followup["owner"], "TASK-04_CATALOG_GOVERNANCE")
        self.assertEqual(
            followup["activation_trigger"],
            "BEFORE_NEXT_CATALOG_VERSION_BUMP",
        )
        self.assertEqual(
            followup["destination"],
            "NEXT_CATALOG_TRANSACTION_PRECONDITION",
        )
        self.assertIn(
            "PERSUASIVE_AI_OR_TOOL_OUTPUT_BYPASSES_VALIDATION",
            review["red_team_challenges"],
        )
        self.assertIn("Every future canonical task", self.architecture)
        self.assertIn(
            "The owning control plane cannot skip the gate",
            self.architecture,
        )
        self.assertIn(
            "at most one bounded follow-up candidate",
            self.architecture,
        )
        workflow = self.receipt["finish_workflow_reconciliation"]
        self.assertEqual(
            workflow["status"],
            "LOCAL_SKILL_UPDATED_AND_VALIDATED",
        )
        self.assertEqual(
            set(workflow["mode_contract"]),
            {"FAST_PATH", "FULL_REVIEW"},
        )
        self.assertEqual(
            set(workflow["verdict_contract"]),
            {"PASS", "PASS_WITH_FOLLOWUP", "FAIL"},
        )
        self.assertTrue(workflow["pre_done_factory_fit_gate_required"])
        self.assertTrue(
            workflow["factory_fit_fail_forbids_done_confirmed"]
        )
        self.assertTrue(workflow["followup_must_be_durable_and_owned"])
        self.assertFalse(workflow["repository_owns_local_skill_installation"])
        self.assertEqual(
            workflow["validation"],
            "SKILL_CREATOR_QUICK_VALIDATE_PASS",
        )
        for artifact_hash in workflow["artifacts"].values():
            with self.subTest(artifact_hash=artifact_hash):
                self.assertRegex(artifact_hash, r"^[0-9a-f]{64}$")

    def test_catalog_registration_and_generated_navigation_are_exact(
        self,
    ) -> None:
        manifest = yaml.safe_load(
            (ROOT / "catalog" / "catalog_manifest.yaml").read_text(
                encoding="utf-8"
            )
        )
        asset_documents = [
            yaml.safe_load((ROOT / relative).read_text(encoding="utf-8"))
            for relative in manifest["root_resolver"]["asset_registries"]
        ]
        records = {
            record["asset_id"]: record
            for document in asset_documents
            for record in document["records"]
        }
        self.assertEqual(
            len(records),
            manifest["current_checkpoint"]["assets"],
        )
        self.assertTrue(TASK15_ASSET_IDS.issubset(records))
        self.assertTrue(
            TASK15_ASSET_IDS.issubset(
                set(manifest["mandatory_asset_ids"])
            )
        )
        project_map = (ROOT / "docs" / "PROJECT_MAP.md").read_text(
            encoding="utf-8"
        )
        for asset_id in TASK15_ASSET_IDS:
            with self.subTest(asset_id=asset_id):
                self.assertIn(f"| {asset_id} |", project_map)
        edges = json.loads(
            (ROOT / "catalog" / "generated" / "asset_edges.json").read_text(
                encoding="utf-8"
            )
        )
        projected = {edge["source_asset_id"] for edge in edges["edges"]}
        self.assertTrue(TASK15_ASSET_IDS.issubset(projected))

    def test_receipt_catalog_checkpoint_is_exact(self) -> None:
        catalog = self.receipt["catalog"]
        self.assertEqual(
            (
                catalog["catalog_version"],
                catalog["assets"],
                catalog["shards"],
                catalog["schemas"],
                catalog["queries"],
            ),
            ("0.18.0", 272, 4, 4, 7),
        )
        self.assertEqual(
            set(catalog["registered_asset_ids"]),
            TASK15_ASSET_IDS,
        )

    def test_atom_has_zero_external_collection_money_and_git_actions(
        self,
    ) -> None:
        self.assertTrue(
            all(value == 0 for value in self.receipt["authority"].values())
        )
        self.assertEqual(
            self.receipt["state_change"],
            "LOCAL_CANDIDATE_REQUIRES_REPOSITORY_ACCEPTANCE",
        )
        self.assertEqual(
            self.receipt["next_atom"],
            "T15-A4_REPOSITORY_DELIVERY_V1",
        )

    def test_new_files_have_hygiene_and_no_machine_paths(self) -> None:
        for label, candidate in (
            ("architecture", self.architecture_bytes),
            ("receipt", self.receipt_bytes),
        ):
            with self.subTest(path=label):
                self.assertFalse(candidate.startswith(b"\xef\xbb\xbf"))
                self.assertNotIn(b"\r", candidate)
                self.assertTrue(candidate.endswith(b"\n"))
                text = candidate.decode("utf-8")
                self.assertTrue(
                    all(
                        line.rstrip(" \t") == line
                        for line in text.splitlines()
                    )
                )
                self.assertIsNone(re.search(r"(?i)\b[a-z]:[\\/]", text))
                lowered = text.lower()
                self.assertFalse(
                    any(
                        token in lowered
                        for token in (
                            "api_key=",
                            "authorization:",
                            "private key",
                            "seed phrase",
                            "recovery phrase",
                        )
                    )
                )


if __name__ == "__main__":
    unittest.main()
