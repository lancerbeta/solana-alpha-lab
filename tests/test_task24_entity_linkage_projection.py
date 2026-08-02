from __future__ import annotations

import hashlib
import json
import re
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.storage.parquet_store import _events_from_table  # noqa: E402
from solana_alpha_lab.task24_entity_linkage_capture import (  # noqa: E402
    load_frozen_population,
)
from solana_alpha_lab.task24_entity_linkage_projection import (  # noqa: E402
    A3_ADJUSTED_SHA256,
    PREFLIGHT_SHA256,
    SYSTEM_PROGRAM_ID,
    Task24LinkageProjectionError,
    _canonical_json_bytes,
    build_task24_linkage_projection,
    parse_transaction_observation,
)


RUN_ID = "t24a5-20260802T081138Z"
CAPTURE_RECEIPT_SHA256 = (
    "512d0cc6687229d0e68d887ea85afeb96f636f23aa48f48358a676d4bfce593a"
)
OUTPUT_DIR = ROOT / "docs/evidence/task24/a5_projection_v1"
RAW_RUN_DIR = (
    ROOT / "data/raw/task24_entity_linkage_history_v1" / f"run={RUN_ID}"
)
EXPECTED_OUTPUTS = {
    "entity_nodes_v1.jsonl": (
        "acf5fc59baf1c6b7c90df78274cee6716bb9607a9965a322523292be4a17fa32",
        61586,
        78,
    ),
    "entity_edges_v1.jsonl": (
        "020411c32a06f19f98ba60ac3940e34d5ef0925c52096070cc7294ee6cbab095",
        85900,
        65,
    ),
    "entity_candidates_v1.json": (
        "8fc6f5fca446191b56ad30cf4e68f4c5df3f9708f94f4d7f18a55517a74f872f",
        3552,
        2,
    ),
    "entity_adjusted_concentration_v1.json": (
        A3_ADJUSTED_SHA256,
        323,
        1,
    ),
    "projection_manifest_v1.json": (
        "64d58868c96da4d560f0a12f63010343a19c1d6df6674c3a5857c1b7738e1825",
        5960,
        1,
    ),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def base58_encode(value: bytes) -> str:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    leading_zeroes = len(value) - len(value.lstrip(b"\0"))
    number = int.from_bytes(value, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = alphabet[remainder] + encoded
    return "1" * leading_zeroes + encoded


def transaction_with_system_transfers(lamports: list[int]) -> dict[str, object]:
    keys = ["SourceWallet111", "TargetWallet111", SYSTEM_PROGRAM_ID]
    instructions = []
    for amount in lamports:
        data = (2).to_bytes(4, "little") + amount.to_bytes(8, "little")
        instructions.append(
            {
                "programIdIndex": 2,
                "accounts": [0, 1],
                "data": base58_encode(data),
            }
        )
    return {
        "blockTime": 1_700_000_000,
        "meta": {"err": None, "innerInstructions": [], "loadedAddresses": {}},
        "slot": 123,
        "transactionIndex": 4,
        "transaction": {
            "message": {
                "accountKeys": keys,
                "header": {"numRequiredSignatures": 1},
                "instructions": instructions,
            },
            "signatures": ["Signature111"],
        },
    }


class Task24EntityLinkageProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            (OUTPUT_DIR / "projection_manifest_v1.json").read_bytes()
        )
        cls.nodes = jsonl(OUTPUT_DIR / "entity_nodes_v1.jsonl")
        cls.edges = jsonl(OUTPUT_DIR / "entity_edges_v1.jsonl")
        cls.candidates = json.loads(
            (OUTPUT_DIR / "entity_candidates_v1.json").read_bytes()
        )

    def test_preflight_and_capture_identity_are_exact(self) -> None:
        preflight = ROOT / "docs/evidence/task24/a5_raw_history_capture_preflight_v1.json"
        self.assertEqual(sha256(preflight), PREFLIGHT_SHA256)
        self.assertEqual(self.manifest["capture"]["run_id"], RUN_ID)
        self.assertEqual(
            self.manifest["capture"]["receipt_sha256"], CAPTURE_RECEIPT_SHA256
        )
        self.assertEqual(
            self.manifest["population"]["fingerprint_sha256"],
            "c513e589184c0d774a23ed00c94daf87a19518e9a3f02374349697d5ad8ef1f0",
        )

    def test_all_outputs_have_exact_hash_size_and_rows(self) -> None:
        for name, (expected_hash, expected_bytes, expected_rows) in EXPECTED_OUTPUTS.items():
            with self.subTest(name=name):
                path = OUTPUT_DIR / name
                self.assertEqual(sha256(path), expected_hash)
                self.assertEqual(path.stat().st_size, expected_bytes)
                if name.endswith(".jsonl"):
                    rows = len(jsonl(path))
                elif name == "entity_candidates_v1.json":
                    rows = len(json.loads(path.read_bytes())["records"])
                else:
                    rows = 1
                self.assertEqual(rows, expected_rows)

    def test_measured_counts_force_redesign_data(self) -> None:
        self.assertEqual(
            self.manifest["counts"],
            {
                "corroborated_positive_claims": 0,
                "derived_shared_immediate_funder": 2,
                "duplicate_transaction_payload_conflicts": 0,
                "edges": 65,
                "entity_candidates": 2,
                "immediate_funder_absent": 2,
                "immediate_funder_ambiguous": 0,
                "inferred_or_vendor_positive_claims": 4,
                "membership_claims": 4,
                "nodes": 78,
                "raw_common_transaction_signer": 0,
                "raw_immediate_funder": 18,
                "raw_mint_created_by_wallet": 1,
                "selected_predicted_positive_capacity": 4,
            },
        )
        self.assertEqual(
            self.manifest["owner_decision"], "RECAPTURE_EXACT_WIRE_OR_STOP"
        )
        self.assertEqual(
            self.manifest["provisional_structure_decision"],
            "REDESIGN_DATA_NON_ADMISSIBLE",
        )
        self.assertEqual(
            self.manifest["false_positive_audit"]["status"],
            "NOT_TESTABLE_CAPTURE_RETENTION_CONTRACT_FAILED",
        )
        self.assertEqual(
            self.manifest["false_positive_audit"]["provisional_capacity"], 4
        )
        self.assertEqual(self.manifest["false_positive_audit"]["minimum_required"], 12)

    def test_capture_was_bounded_and_did_not_open_forbidden_authority(self) -> None:
        self.assertEqual(self.manifest["capture"]["provider_calls"], 21)
        self.assertEqual(self.manifest["capture"]["provider_credits_modeled"], 210)
        self.assertEqual(self.manifest["capture"]["cash_spend_usd_cents"], 0)
        self.assertEqual(self.manifest["capture"]["retries"], 0)
        self.assertEqual(self.manifest["capture"]["transactions_returned"], 1939)
        self.assertEqual(self.manifest["capture"]["truncated_subjects"], 21)
        self.assertEqual(self.manifest["authority"]["r3_or_outcome_reads"], 0)
        self.assertEqual(
            self.manifest["authority"]["wallet_signer_transaction_actions"], 0
        )
        self.assertEqual(self.manifest["authority"]["credential_values_exposed"], 0)

    def test_edges_preserve_evidence_class_and_reversible_membership(self) -> None:
        counts: dict[str, int] = {}
        by_id = {node["node_id"]: node for node in self.nodes}
        for edge in self.edges:
            counts[str(edge["edge_type"])] = counts.get(str(edge["edge_type"]), 0) + 1
            self.assertIn(edge["source_node_id"], by_id)
            self.assertIn(edge["target_node_id"], by_id)
            self.assertEqual(
                by_id[edge["source_node_id"]]["node_type"], edge["source_node_type"]
            )
            self.assertEqual(
                by_id[edge["target_node_id"]]["node_type"], edge["target_node_type"]
            )
        self.assertEqual(counts["RAW_IMMEDIATE_FUNDER"], 18)
        self.assertEqual(counts["RAW_MINT_CREATED_BY_WALLET"], 1)
        self.assertEqual(counts["DERIVED_SHARED_IMMEDIATE_FUNDER"], 2)
        self.assertEqual(counts["PROJECT_ENTITY_MEMBERSHIP_CANDIDATE"], 4)
        membership = [
            edge
            for edge in self.edges
            if edge["edge_type"] == "PROJECT_ENTITY_MEMBERSHIP_CANDIDATE"
        ]
        self.assertTrue(all(edge["evidence_class"] == "PROJECT_INFERENCE" for edge in membership))
        self.assertTrue(all(edge["confidence_class"] == "INFERRED" for edge in membership))
        self.assertTrue(
            all("NO_DESTRUCTIVE_MERGE" in edge["quality_flags"] for edge in membership)
        )

    def test_candidate_records_do_not_claim_ownership(self) -> None:
        self.assertEqual(
            self.candidates["status"], "INSUFFICIENT_PREDICTED_POSITIVE_CAPACITY"
        )
        self.assertEqual(
            self.candidates["capacity_formula"],
            "MIN(CORROBORATED_COUNT,8)+MIN(INFERRED_OR_VENDOR_COUNT,8)",
        )
        self.assertEqual([row["member_count"] for row in self.candidates["records"]], [2, 2])
        for candidate in self.candidates["records"]:
            self.assertTrue(candidate["reversible"])
            self.assertFalse(candidate["ownership_claimed"])
            self.assertTrue(
                all(member["confidence_class"] == "INFERRED" for member in candidate["members"])
            )

    def test_content_hashes_and_point_in_time_ordering_hold(self) -> None:
        for row in [*self.nodes, *self.edges]:
            content_hash = row["content_sha256"]
            payload = dict(row)
            del payload["content_sha256"]
            self.assertEqual(
                hashlib.sha256(_canonical_json_bytes(payload)).hexdigest(), content_hash
            )
            reliable = datetime.fromisoformat(str(row["first_reliable_available_at"]))
            available = datetime.fromisoformat(str(row["available_to_strategy_at"]))
            ingested = datetime.fromisoformat(str(row["ingested_at"]))
            self.assertGreaterEqual(available, reliable)
            self.assertGreaterEqual(ingested, reliable)

    def test_adjusted_concentration_is_byte_identical_to_a3(self) -> None:
        a3 = ROOT / "docs/evidence/task24/a3_projection_v1/entity_adjusted_concentration_v1.json"
        a5 = OUTPUT_DIR / "entity_adjusted_concentration_v1.json"
        self.assertEqual(sha256(a3), A3_ADJUSTED_SHA256)
        self.assertEqual(a3.read_bytes(), a5.read_bytes())
        adjusted = json.loads(a5.read_bytes())
        self.assertIsNone(adjusted["adjusted_top_accounts_supply_share"])
        self.assertFalse(adjusted["exclusion_inventory_complete"])

    def test_tracked_projection_uses_only_pseudonyms(self) -> None:
        digest = re.compile(r"^[0-9a-f]{64}$")
        for node in self.nodes:
            self.assertRegex(str(node["business_key"]).rsplit(":", 1)[1], digest)
        persisted = b"".join((OUTPUT_DIR / name).read_bytes() for name in EXPECTED_OUTPUTS)
        population = load_frozen_population(ROOT)
        for subject in population.subjects:
            self.assertNotIn(subject.raw_public_key.encode("utf-8"), persisted)
        self.assertEqual(self.manifest["privacy"]["raw_public_addresses_persisted"], 0)
        self.assertEqual(
            self.manifest["privacy"]["raw_transaction_signatures_persisted"], 0
        )

    def test_local_raw_addresses_and_signatures_are_absent_from_tracked_projection(self) -> None:
        receipt = RAW_RUN_DIR / "receipts/capture.receipt.json"
        if not receipt.is_file():
            self.skipTest("ignored local A5 raw capture is not available")
        persisted = b"".join((OUTPUT_DIR / name).read_bytes() for name in EXPECTED_OUTPUTS)
        raw_values: set[str] = set()
        for partition in sorted((RAW_RUN_DIR / "partitions").glob("*.parquet")):
            event = _events_from_table(pq.read_table(partition))[0]
            document = json.loads(event.redacted_body)
            for transaction in document["result"]["data"]:
                raw_values.update(transaction["transaction"]["signatures"])
                raw_values.update(transaction["transaction"]["message"]["accountKeys"])
                loaded = transaction["meta"].get("loadedAddresses") or {}
                raw_values.update(loaded.get("writable") or [])
                raw_values.update(loaded.get("readonly") or [])
        self.assertGreater(len(raw_values), 100)
        for value in raw_values:
            self.assertNotIn(value.encode("utf-8"), persisted)

    def test_compiled_system_transfer_parser_accepts_positive_and_ignores_zero(self) -> None:
        row = transaction_with_system_transfers([0, 12345])
        observation = parse_transaction_observation(
            row,
            batch_raw_event_id="raw-unit",
            observed_at=datetime(2026, 8, 2, tzinfo=UTC),
            ingested_at=datetime(2026, 8, 2, tzinfo=UTC),
        )
        self.assertEqual(len(observation.native_transfers), 1)
        self.assertEqual(observation.native_transfers[0].lamports, 12345)
        self.assertEqual(observation.signers, ("SourceWallet111",))
        self.assertEqual(observation.transaction_index, 4)

    def test_provider_parsed_instruction_is_rejected(self) -> None:
        row = transaction_with_system_transfers([1])
        row["transaction"]["message"]["instructions"] = [
            {"parsed": {"type": "transfer"}, "programIdIndex": 2, "accounts": [0, 1], "data": "1"}
        ]
        with self.assertRaisesRegex(
            Task24LinkageProjectionError, "provider_parsed_instruction_forbidden"
        ):
            parse_transaction_observation(
                row,
                batch_raw_event_id="raw-unit",
                observed_at=datetime(2026, 8, 2, tzinfo=UTC),
                ingested_at=datetime(2026, 8, 2, tzinfo=UTC),
            )

    def test_legacy_capture_is_rejected_without_exact_wire_retention(self) -> None:
        receipt = RAW_RUN_DIR / "receipts/capture.receipt.json"
        if not receipt.is_file():
            self.skipTest("ignored local A5 raw capture is not available")
        local_root = ROOT / "local"
        local_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="task24-a5-", dir=local_root) as temp:
            output = Path(temp) / "projection"
            with self.assertRaisesRegex(
                Task24LinkageProjectionError, "exact_wire_response_not_retained"
            ):
                build_task24_linkage_projection(
                    repo_root=ROOT,
                    raw_root=ROOT / "data/raw",
                    run_id=RUN_ID,
                    receipt_sha256=CAPTURE_RECEIPT_SHA256,
                    output_dir=output,
                    capture_logical_root="task24_entity_linkage_history_v1",
                    exact_wire_logical_root="task24_entity_linkage_history_wire_v1",
                )

    def test_next_atom_is_only_recommended_not_authorized(self) -> None:
        self.assertEqual(
            self.manifest["next_boundary"]["recommended_atom"],
            "T24-A5R1_EXACT_WIRE_RETENTION_RECAPTURE_V1",
        )
        self.assertFalse(self.manifest["next_boundary"]["authorized"])
        self.assertIn("TASK24_DONE", self.manifest["non_claims"])


if __name__ == "__main__":
    unittest.main()
