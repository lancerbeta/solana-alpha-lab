from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

import yaml

from scripts import query_hypothesis_research_memory as memory

ROOT = Path(__file__).resolve().parents[1]
DOSSIER_JSON_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task17"
    / "first_bounded_hypothesis_cycle_v1.json"
)
DOSSIER_MARKDOWN_PATH = DOSSIER_JSON_PATH.with_suffix(".md")
TASK16_ACCEPTANCE_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task16"
    / "hypothesis_research_memory_acceptance_v1.json"
)
HYPOTHESIS_VERSION_ID = (
    "HYP-VERSION-EXECUTION-CAPACITY-CURVATURE-V1"
)
EVIDENCE_ID = "EVIDENCE-T17-FIRST-BOUNDED-HYPOTHESIS-CYCLE-001"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_front_matter(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    opening, front_matter, body = text.split("---", 2)
    if opening:
        raise AssertionError("front_matter_not_first")
    return yaml.safe_load(front_matter), body


class Task17FirstBoundedHypothesisCycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document, cls.document_sha256 = memory.load_memory(
            DOSSIER_JSON_PATH
        )
        cls.front_matter, cls.markdown_body = load_front_matter(
            DOSSIER_MARKDOWN_PATH
        )

    def test_real_dossier_validates_as_one_frozen_cycle(self) -> None:
        memory.validate_memory(self.document)
        self.assertEqual(self.document["truth_owner"], "TASK-17")
        self.assertTrue(self.document["append_only"])
        self.assertTrue(self.document["current_state_is_projection"])
        self.assertEqual(len(self.document["hypothesis_families"]), 1)
        self.assertEqual(len(self.document["hypothesis_origins"]), 1)
        self.assertEqual(len(self.document["research_cycles"]), 1)
        self.assertEqual(len(self.document["hypothesis_versions"]), 1)
        self.assertEqual(len(self.document["research_artifacts"]), 4)
        self.assertEqual(self.document["trials"], [])
        self.assertEqual(self.document["derivation_edges"], [])
        self.assertEqual(self.document["activation_epochs"], [])

        version = self.document["hypothesis_versions"][0]
        self.assertEqual(version["hypothesis_version_id"], HYPOTHESIS_VERSION_ID)
        self.assertEqual(version["definition_state"], "FROZEN")
        self.assertEqual(
            memory.canonical_definition_sha256(version),
            version["definition_sha256"],
        )
        self.assertEqual(
            version["data_requirement_asset_id"],
            "DATA-REQUIREMENT-T17-EXECUTION-CAPACITY-001",
        )

    def test_origin_is_real_retained_evidence_not_task16_fixture(self) -> None:
        origin = self.document["hypothesis_origins"][0]
        self.assertEqual(origin["origin_kind"], "DATA_ANALYSIS")
        self.assertEqual(
            set(origin["source_reference_asset_ids"]),
            {
                "PRE-GIT-TASK01-A019",
                "EVIDENCE-T10-JUPITER-QUOTE-SUMMARY-002",
            },
        )
        serialized = json.dumps(self.document, sort_keys=True)
        self.assertNotIn("HYP-VERSION-LIQUIDITY-REVERSAL", serialized)
        self.assertNotIn("FIXTURE-T16-HYPOTHESIS-RESEARCH-MEMORY-001", serialized)

    def test_every_research_artifact_hash_matches_repository_bytes(self) -> None:
        for artifact in self.document["research_artifacts"]:
            with self.subTest(artifact=artifact["research_artifact_id"]):
                logical_uri = artifact["logical_uri"]
                self.assertTrue(logical_uri.startswith("repo://"))
                path = ROOT / logical_uri.removeprefix("repo://")
                self.assertTrue(path.is_file())
                self.assertEqual(sha256(path), artifact["content_sha256"])

    def test_production_prior_work_query_returns_paused_candidate(self) -> None:
        result = memory.query_prior_work(
            self.document,
            {
                "query_id": "PRIOR-WORK-QUERY-T17-CAPACITY-001",
                "as_of": self.document["as_of"],
                "max_results": 10,
                "predicates": {
                    "mechanism_terms": ["price impact", "capacity"],
                },
            },
            memory_content_sha256=self.document_sha256,
        )
        self.assertEqual(result["result_count"], 1)
        row = result["results"][0]
        self.assertEqual(row["hypothesis_version_id"], HYPOTHESIS_VERSION_ID)
        self.assertIn("MECHANISM_TERM", row["matched_by"])
        self.assertEqual(row["current_state_as_of"], "PAUSED")
        self.assertTrue(row["repeat_or_extension_requires_what_changed"])
        self.assertFalse(result["automatic_reject_or_promotion"])

    def test_data_need_is_exact_bounded_and_not_authorized(self) -> None:
        self.assertEqual(
            self.front_matter["data_verdict"],
            "LIVE_NON_RECONSTRUCTABLE_NEED",
        )
        live = self.front_matter["live_capture"]
        self.assertEqual(live["authority"], "NOT_AUTHORIZED")
        self.assertEqual(
            live["scope"],
            "VERSIONED_HYPOTHESIS_WATCHLIST_MEMBERS_ONLY",
        )
        calculated_cap = (
            live["max_members"]
            * live["triggered_windows_per_member"]
            * len(live["notionals_usd"])
            * live["quote_legs_per_notional"]
        )
        self.assertEqual(calculated_cap, 192)
        self.assertEqual(live["max_provider_calls"], calculated_cap)
        self.assertEqual(live["concurrency"], 1)
        self.assertEqual(live["retries"], 0)
        self.assertEqual(live["cash_cap_usd"], 0)
        self.assertEqual(self.front_matter["provider_calls_in_atom"], 0)
        self.assertEqual(self.front_matter["cash_spend_usd"], 0)
        self.assertEqual(
            self.front_matter["wallet_signer_transaction_actions"],
            0,
        )

        decisions = self.document["decision_events"]
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0]["decision_kind"], "PAUSE")
        self.assertIn(
            "LIVE_NON_RECONSTRUCTABLE_NEED",
            decisions[0]["rationale"],
        )
        self.assertIn("192", decisions[0]["next_condition"])

    def test_search_budget_and_non_claims_are_frozen(self) -> None:
        budget = self.front_matter["search_budget"]
        self.assertEqual(
            budget,
            {
                "hypothesis_versions": 1,
                "primary_estimands": 1,
                "planned_trial_variants": 1,
                "holdout_looks": 0,
            },
        )
        for required_text in (
            "no provider/API/RPC/WSS call occurred in A2",
            "no historical hydration or live collection occurred",
            "no strategy, execution, position, fill, PnL or alpha result exists",
            "no wallet, signer, transaction or real-money action occurred",
        ):
            with self.subTest(required_text=required_text):
                self.assertIn(required_text, self.markdown_body)

    def test_task16_legacy_registry_sources_remain_exact_and_empty(self) -> None:
        acceptance = json.loads(
            TASK16_ACCEPTANCE_PATH.read_text(encoding="utf-8")
        )
        sources = {
            source["path"]: source
            for source in acceptance["migration"]["sources"]
        }
        for relative_path in (
            "registries/research_cycles.yaml",
            "registries/hypotheses.yaml",
        ):
            with self.subTest(path=relative_path):
                source = sources[relative_path]
                path = ROOT / relative_path
                self.assertEqual(sha256(path), source["sha256"])
                self.assertEqual(
                    yaml.safe_load(path.read_text(encoding="utf-8"))[
                        "records"
                    ],
                    [],
                )

        self.assertEqual(self.front_matter["evidence_id"], EVIDENCE_ID)
        self.assertIn(
            "create a second editable copy",
            self.markdown_body,
        )


if __name__ == "__main__":
    unittest.main()
