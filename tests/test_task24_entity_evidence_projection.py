from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.storage.parquet_store import _events_from_table  # noqa: E402
from solana_alpha_lab.task24_entity_evidence_projection import (  # noqa: E402
    ALLOWED_EDGE_TYPES,
    PRE_READ_MANIFEST_SHA256,
    Task24ProjectionError,
    _canonical_json_bytes,
    build_task24_projection,
)


MANIFEST_PATH = (
    ROOT / "docs/evidence/task24/a3_entity_evidence_pre_read_manifest_v1.json"
)
OUTPUT_DIR = ROOT / "docs/evidence/task24/a3_projection_v1"

EXPECTED_OUTPUTS = {
    "entity_nodes_v1.jsonl": (
        "fdb169bd3f639c42b350de5eae41fc280061f5682fb3ea2605fcad2408ff3af7",
        32620,
        41,
    ),
    "entity_edges_v1.jsonl": (
        "fa19151a85d43783c37f6d0d99101baeaf2c755e4fe9536792872451af3d39c4",
        48100,
        40,
    ),
    "entity_candidates_v1.json": (
        "ca5942bab810ab72949455f46947c068cb42664b173101633a641b4547755c81",
        262,
        0,
    ),
    "entity_adjusted_concentration_v1.json": (
        "644b148f17fe437118196dabdb4185886117086aab1fe1b77f7965621a06f4ad",
        323,
        1,
    ),
    "projection_manifest_v1.json": (
        "85803b180144c4c2581f9f9d6d81d4048408e12f1e25bde17478b51eb7674e80",
        2042,
        1,
    ),
}

EXPECTED_INPUTS = {
    "PILOT_PLAN": (
        "tests/fixtures/task11/entity_input_pilot_plan_v1.json",
        "ff0524ab2a77b517f8796ff54a753842306b83de9be6e8d4c391776afba0cf1d",
        2533,
    ),
    "RUNTIME_RECEIPT": (
        "data/raw/task11_entity_input_probe_v1/run=t11a3-20260728T102537Z/receipts/probe.receipt.json",
        "0cad0cb9fac95475691ab9f71fac01a29ae63b87a8910647e0a0afcc23d233f1",
        4225,
    ),
    "TOKEN_SUPPLY_RAW_EVENT": (
        "data/raw/task11_entity_input_probe_v1/run=t11a3-20260728T102537Z/partitions/01-getTokenSupply.parquet",
        "819fbfe6f76a11fa9c9c834cfb9fb78952fcfdc1ac354031c75f88922a872a29",
        8852,
    ),
    "LARGEST_TOKEN_ACCOUNTS_RAW_EVENT": (
        "data/raw/task11_entity_input_probe_v1/run=t11a3-20260728T102537Z/partitions/02-getTokenLargestAccounts.parquet",
        "847f9a7f406adf65d58e75095c1acc410807b5f68933bd99106757f2dd09aaa9",
        24019,
    ),
    "TOKEN_ACCOUNT_OWNER_RAW_EVENT": (
        "data/raw/task11_entity_input_probe_v1/run=t11a3-20260728T102537Z/partitions/03-getMultipleAccounts.parquet",
        "5a01c427070c2ff50d8d208fc02f4cbd6c1b567aa89ef1d1e0499271e66e919b",
        18570,
    ),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


class Task24EntityEvidenceProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest_bytes = MANIFEST_PATH.read_bytes()
        cls.manifest = json.loads(cls.manifest_bytes)
        cls.nodes = jsonl(OUTPUT_DIR / "entity_nodes_v1.jsonl")
        cls.edges = jsonl(OUTPUT_DIR / "entity_edges_v1.jsonl")
        cls.candidates = json.loads(
            (OUTPUT_DIR / "entity_candidates_v1.json").read_bytes()
        )
        cls.adjusted = json.loads(
            (OUTPUT_DIR / "entity_adjusted_concentration_v1.json").read_bytes()
        )
        cls.projection = json.loads(
            (OUTPUT_DIR / "projection_manifest_v1.json").read_bytes()
        )

    def test_pre_read_manifest_is_exact_and_authorizes_only_partial_raw_projection(self) -> None:
        self.assertEqual(sha256(MANIFEST_PATH), PRE_READ_MANIFEST_SHA256)
        self.assertEqual(self.manifest["status"], "PASS_ADMISSIBLE_LOCAL_INPUTS")
        self.assertEqual(
            set(self.manifest["scope"]["allowed_projection"]),
            ALLOWED_EDGE_TYPES,
        )
        self.assertEqual(
            self.manifest["projection_gate"]["projection_authorized"],
            "PARTIAL_RAW_RELATIONS_ONLY",
        )
        self.assertFalse(
            self.manifest["no_r3_no_outcome_assertion"]["r3_paths_allowed"]
        )

    def test_all_manifest_inputs_match_exact_local_bytes(self) -> None:
        actual = {
            item["role"]: (
                item["exact_local_path"],
                item["sha256"],
                item["bytes"],
            )
            for item in self.manifest["inputs"]
        }
        self.assertEqual(actual, EXPECTED_INPUTS)
        for role, (relative, expected_hash, expected_bytes) in EXPECTED_INPUTS.items():
            path = ROOT / relative
            self.assertTrue(path.is_file(), role)
            self.assertFalse(path.is_symlink(), role)
            self.assertEqual(path.stat().st_size, expected_bytes, role)
            self.assertEqual(sha256(path), expected_hash, role)

    def test_all_generated_outputs_have_exact_hash_size_and_row_count(self) -> None:
        for name, (expected_hash, expected_bytes, expected_rows) in EXPECTED_OUTPUTS.items():
            path = OUTPUT_DIR / name
            self.assertEqual(sha256(path), expected_hash, name)
            self.assertEqual(path.stat().st_size, expected_bytes, name)
            if name.endswith(".jsonl"):
                rows = len(jsonl(path))
            elif name == "entity_candidates_v1.json":
                rows = len(json.loads(path.read_bytes())["records"])
            else:
                rows = 1
            self.assertEqual(rows, expected_rows, name)

    def test_node_population_is_one_mint_twenty_accounts_twenty_wallets(self) -> None:
        counts = {}
        for node in self.nodes:
            counts[node["node_type"]] = counts.get(node["node_type"], 0) + 1
        self.assertEqual(
            counts,
            {"TOKEN_MINT": 1, "TOKEN_ACCOUNT": 20, "WALLET": 20},
        )
        self.assertEqual(len({node["node_id"] for node in self.nodes}), 41)
        digest_pattern = re.compile(r"^[0-9a-f]{64}$")
        for node in self.nodes:
            digest = str(node["business_key"]).rsplit(":", 1)[1]
            self.assertRegex(digest, digest_pattern)
            self.assertEqual(node["evidence_class"], "RAW_ONCHAIN")

    def test_edges_are_exactly_twenty_mint_and_twenty_owner_relations(self) -> None:
        counts = {}
        for edge in self.edges:
            counts[edge["edge_type"]] = counts.get(edge["edge_type"], 0) + 1
        self.assertEqual(
            counts,
            {
                "RAW_TOKEN_ACCOUNT_FOR_MINT": 20,
                "RAW_TOKEN_ACCOUNT_OWNER": 20,
            },
        )
        self.assertEqual(len({edge["edge_id"] for edge in self.edges}), 40)
        for edge in self.edges:
            self.assertEqual(edge["evidence_class"], "RAW_ONCHAIN")
            self.assertEqual(edge["confidence_class"], "DIRECT")
            self.assertEqual(edge["supporting_edge_ids"], [])
            self.assertEqual(len(edge["supporting_raw_event_ids"]), 1)

    def test_every_edge_endpoint_exists_and_types_agree(self) -> None:
        by_id = {node["node_id"]: node for node in self.nodes}
        for edge in self.edges:
            source = by_id[edge["source_node_id"]]
            target = by_id[edge["target_node_id"]]
            self.assertEqual(source["node_type"], edge["source_node_type"])
            self.assertEqual(target["node_type"], edge["target_node_type"])
            self.assertEqual(source["node_type"], "TOKEN_ACCOUNT")
            if edge["edge_type"] == "RAW_TOKEN_ACCOUNT_FOR_MINT":
                self.assertEqual(target["node_type"], "TOKEN_MINT")
            else:
                self.assertEqual(target["node_type"], "WALLET")

    def test_point_in_time_ordering_and_content_hashes_hold(self) -> None:
        for row in [*self.nodes, *self.edges]:
            available = datetime.fromisoformat(str(row["available_to_strategy_at"]))
            reliable = datetime.fromisoformat(str(row["first_reliable_available_at"]))
            ingested = datetime.fromisoformat(str(row["ingested_at"]))
            self.assertGreaterEqual(available, reliable)
            self.assertGreaterEqual(ingested, reliable)
            content_hash = row["content_sha256"]
            payload = dict(row)
            del payload["content_sha256"]
            self.assertEqual(
                hashlib.sha256(_canonical_json_bytes(payload)).hexdigest(),
                content_hash,
            )

    def test_raw_public_addresses_are_not_persisted_in_projection_outputs(self) -> None:
        supply_path = ROOT / EXPECTED_INPUTS["TOKEN_SUPPLY_RAW_EVENT"][0]
        largest_path = ROOT / EXPECTED_INPUTS["LARGEST_TOKEN_ACCOUNTS_RAW_EVENT"][0]
        owner_path = ROOT / EXPECTED_INPUTS["TOKEN_ACCOUNT_OWNER_RAW_EVENT"][0]
        supply_event = _events_from_table(pq.ParquetFile(supply_path).read())[0]
        largest_event = _events_from_table(pq.ParquetFile(largest_path).read())[0]
        owner_event = _events_from_table(pq.ParquetFile(owner_path).read())[0]
        supply_document = json.loads(supply_event.redacted_body)
        largest_document = json.loads(largest_event.redacted_body)
        owner_document = json.loads(owner_event.redacted_body)
        self.assertIn("amount", supply_document["result"]["value"])
        raw_keys = [self.manifest["scope"]["selected_mint"]]
        raw_keys.extend(
            row["address"] for row in largest_document["result"]["value"]
        )
        raw_keys.extend(
            row["data"]["parsed"]["info"]["owner"]
            for row in owner_document["result"]["value"]
        )
        persisted = b"".join(
            (OUTPUT_DIR / name).read_bytes() for name in EXPECTED_OUTPUTS
        )
        for raw_key in raw_keys:
            self.assertNotIn(str(raw_key).encode("utf-8"), persisted)

    def test_entity_candidates_fail_closed_without_linkage_evidence(self) -> None:
        self.assertEqual(
            self.candidates["status"],
            "NOT_TESTABLE_NO_ADMISSIBLE_LINKAGE_EVIDENCE",
        )
        self.assertEqual(self.candidates["records"], [])
        self.assertEqual(self.candidates["vendor_or_project_inferences_created"], 0)
        self.assertIn("IMMEDIATE_FUNDER", self.candidates["missing_evidence"])
        self.assertIn("AUTHORITATIVE_BUNDLE_ID", self.candidates["missing_evidence"])

    def test_adjusted_concentration_stays_null_and_raw_is_preserved(self) -> None:
        self.assertEqual(
            self.adjusted["status"],
            "NOT_AVAILABLE_EXCLUSION_INVENTORY_INCOMPLETE",
        )
        self.assertIsNone(self.adjusted["adjusted_top_accounts_supply_share"])
        self.assertFalse(self.adjusted["exclusion_inventory_complete"])
        self.assertTrue(self.adjusted["raw_metric_preserved"])
        self.assertEqual(self.adjusted["holder_exclusions_changed"], 0)
        self.assertEqual(self.adjusted["unresolved_exclusion_account_count"], 20)

    def test_projection_manifest_returns_extend_evidence_without_overclaim(self) -> None:
        self.assertEqual(
            self.projection["status"], "PASS_PARTIAL_RAW_RELATION_PROJECTION"
        )
        self.assertEqual(self.projection["owner_decision"], "EXTEND_EVIDENCE")
        self.assertEqual(self.projection["raw_public_addresses_persisted"], 0)
        self.assertEqual(self.projection["counts"]["entity_candidates"], 0)
        self.assertIn("COMMON_OWNERSHIP", self.projection["not_testable"])
        self.assertIn("TASK24_DONE", self.projection["non_claims"])
        for value in self.projection["authority"].values():
            self.assertEqual(value, 0)

    def test_rebuild_is_deterministic_for_core_outputs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="task24-a3-", dir=ROOT / "local") as tmp:
            output = Path(tmp) / "projection"
            result = build_task24_projection(
                repo_root=ROOT,
                manifest_path=MANIFEST_PATH,
                output_dir=output,
            )
            self.assertEqual(result["counts"], self.projection["counts"])
            for name in (
                "entity_nodes_v1.jsonl",
                "entity_edges_v1.jsonl",
                "entity_candidates_v1.json",
                "entity_adjusted_concentration_v1.json",
            ):
                self.assertEqual(sha256(output / name), EXPECTED_OUTPUTS[name][0])

    def test_unbound_manifest_mutation_is_rejected_before_projection(self) -> None:
        with tempfile.TemporaryDirectory(prefix="task24-a3-", dir=ROOT / "local") as tmp:
            changed_path = Path(tmp) / "manifest.json"
            changed = copy.deepcopy(self.manifest)
            changed["scope"]["dataset_version"] = "MUTATED"
            changed_path.write_bytes(_canonical_json_bytes(changed))
            with self.assertRaisesRegex(Task24ProjectionError, "manifest_hash_drift"):
                build_task24_projection(
                    repo_root=ROOT,
                    manifest_path=changed_path,
                    output_dir=Path(tmp) / "output",
                )

    def test_bound_adversarial_authority_and_privacy_mutations_fail_closed(self) -> None:
        mutations = [
            ("no_r3_no_outcome_assertion", "r3_paths_allowed", True, "forbidden_boundary_enabled"),
            ("authority", "provider_api_rpc_wss_calls", 1, "external_authority_enabled"),
            (
                "privacy_and_output_policy",
                "raw_owner_addresses_may_be_persisted_in_git",
                True,
                "owner_address_persistence_enabled",
            ),
        ]
        with tempfile.TemporaryDirectory(prefix="task24-a3-", dir=ROOT / "local") as tmp:
            for index, (section, key, value, error) in enumerate(mutations):
                with self.subTest(section=section, key=key):
                    changed = copy.deepcopy(self.manifest)
                    changed[section][key] = value
                    changed_path = Path(tmp) / f"manifest-{index}.json"
                    changed_path.write_bytes(_canonical_json_bytes(changed))
                    changed_hash = sha256(changed_path)
                    with patch(
                        "solana_alpha_lab.task24_entity_evidence_projection.PRE_READ_MANIFEST_SHA256",
                        changed_hash,
                    ):
                        with self.assertRaisesRegex(Task24ProjectionError, error):
                            build_task24_projection(
                                repo_root=ROOT,
                                manifest_path=changed_path,
                                output_dir=Path(tmp) / f"output-{index}",
                            )


if __name__ == "__main__":
    unittest.main()
