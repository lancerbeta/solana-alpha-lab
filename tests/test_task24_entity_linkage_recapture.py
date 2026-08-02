from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.storage.parquet_store import _events_from_table  # noqa: E402
from solana_alpha_lab.task24_entity_linkage_projection import (  # noqa: E402
    build_task24_linkage_projection,
)


RUN_ID = "t24a5-20260802T084813Z"
RECEIPT_SHA256 = (
    "c52f7892e3227adba0afa2a6afc6bcf872f258313be2e14745a6420a32c5c829"
)
PREFLIGHT_PATH = (
    ROOT / "docs/evidence/task24/a5r1_exact_wire_recapture_preflight_v1.json"
)
PREFLIGHT_SHA256 = (
    "f1b4964768b7db1474ea6c0199bebbad37c264adf9a37c4b6697b151afe27250"
)
CANONICAL_RUN = (
    ROOT / "data/raw/task24_entity_linkage_history_v1_1" / f"run={RUN_ID}"
)
WIRE_RUN = (
    ROOT / "data/raw/task24_entity_linkage_history_wire_v1_1" / f"run={RUN_ID}"
)
OUTPUT_DIR = ROOT / "docs/evidence/task24/a5r1_projection_v1"
LEGACY_MANIFEST = ROOT / "docs/evidence/task24/a5_projection_v1/projection_manifest_v1.json"
LEGACY_MANIFEST_SHA256 = (
    "64d58868c96da4d560f0a12f63010343a19c1d6df6674c3a5857c1b7738e1825"
)
EXPECTED_OUTPUTS = {
    "entity_nodes_v1.jsonl": (
        "8bc35e1ae3678b1b282ff42a6450a759627c48e75f4d8cbb3bb79a7809f6410a",
        61586,
        78,
    ),
    "entity_edges_v1.jsonl": (
        "24ce894f08f689002a131f7d7bbfe80ec9021d46536d6cb0ffc89847bf16ea9b",
        85900,
        65,
    ),
    "entity_candidates_v1.json": (
        "e21c37b074ae623a359ed1d4228f95333706ce7b4f26f607bbd2789ba6b1b1de",
        3552,
        2,
    ),
    "entity_adjusted_concentration_v1.json": (
        "644b148f17fe437118196dabdb4185886117086aab1fe1b77f7965621a06f4ad",
        323,
        1,
    ),
    "projection_manifest_v1.json": (
        "a6489a33d7bad02ffeb0fd70f3912e46c1175bcb0b21691005414a6448e57b6e",
        4857,
        1,
    ),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


class Task24EntityLinkageRecaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            (OUTPUT_DIR / "projection_manifest_v1.json").read_bytes()
        )

    def test_preflight_and_legacy_quarantine_are_immutable(self) -> None:
        self.assertEqual(sha256(PREFLIGHT_PATH), PREFLIGHT_SHA256)
        self.assertEqual(sha256(LEGACY_MANIFEST), LEGACY_MANIFEST_SHA256)
        legacy = json.loads(LEGACY_MANIFEST.read_bytes())
        self.assertEqual(
            legacy["status"], "QUARANTINED_CAPTURE_RETENTION_CONTRACT_FAILED"
        )

    def test_all_recapture_outputs_have_exact_hash_size_and_rows(self) -> None:
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

    def test_projection_is_admissible_but_capacity_remains_four_of_twelve(self) -> None:
        self.assertEqual(
            self.manifest["manifest_id"],
            "T24-A5R1-EXACT-WIRE-RECAPTURE-PROJECTION-001",
        )
        self.assertEqual(
            self.manifest["atom"], "T24-A5R1_EXACT_WIRE_RETENTION_RECAPTURE_V1"
        )
        self.assertEqual(
            self.manifest["status"],
            "PASS_BOUNDED_HISTORY_PROJECTION_INSUFFICIENT_CAPACITY",
        )
        self.assertEqual(self.manifest["owner_decision"], "REDESIGN_DATA")
        self.assertEqual(
            self.manifest["false_positive_audit"],
            {
                "capacity": 4,
                "manual_labels_opened": 0,
                "minimum_required": 12,
                "status": "NOT_TESTABLE_INSUFFICIENT_PREDICTED_POSITIVES",
            },
        )

    def test_manifest_records_exact_dual_retention_receipts(self) -> None:
        capture = self.manifest["capture"]
        self.assertEqual(capture["run_id"], RUN_ID)
        self.assertEqual(capture["receipt_sha256"], RECEIPT_SHA256)
        self.assertEqual(capture["capture_contract_version"], "1.1")
        self.assertEqual(capture["exact_wire_files_verified"], 21)
        self.assertEqual(capture["exact_wire_bytes_verified"], 21_386_958)
        self.assertEqual(capture["wire_canonical_semantic_equalities_verified"], 21)
        self.assertEqual(capture["provider_calls"], 21)
        self.assertEqual(capture["provider_credits_modeled"], 210)
        self.assertEqual(capture["cash_spend_usd_cents"], 0)
        self.assertEqual(capture["retries"], 0)

    def test_local_receipt_binds_all_exact_wire_and_canonical_files(self) -> None:
        receipt_path = CANONICAL_RUN / "receipts/capture.receipt.json"
        if not receipt_path.is_file():
            self.skipTest("ignored local A5R1 raw capture is not available")
        self.assertEqual(sha256(receipt_path), RECEIPT_SHA256)
        receipt = json.loads(receipt_path.read_bytes())
        self.assertEqual(receipt["capture_contract_version"], "1.1")
        self.assertEqual(receipt["dataset_version"], "1.1")
        self.assertEqual(receipt["provider_calls"], 21)
        self.assertEqual(receipt["provider_credits_modeled"], 210)
        self.assertEqual(receipt["stored_exact_wire_bytes"], receipt["received_bytes"])
        self.assertEqual(len(receipt["attempts"]), 21)
        page_by_rpc = {page["rpc_id"]: page for page in receipt["pages"]}
        for attempt in receipt["attempts"]:
            rpc_id = attempt["rpc_id"]
            wire = ROOT / "data/raw" / attempt["exact_wire_logical_location"]
            canonical = ROOT / "data/raw" / attempt["logical_location"]
            self.assertTrue(wire.is_file())
            self.assertTrue(canonical.is_file())
            self.assertFalse(wire.is_symlink())
            self.assertFalse(canonical.is_symlink())
            self.assertEqual(sha256(wire), attempt["exact_wire_response_sha256"])
            self.assertEqual(wire.stat().st_size, attempt["exact_wire_response_bytes"])
            self.assertEqual(
                attempt["exact_wire_response_sha256"],
                page_by_rpc[rpc_id]["response_sha256"],
            )
            self.assertEqual(sha256(canonical), attempt["partition_file_sha256"])
            event = _events_from_table(pq.read_table(canonical))[0]
            self.assertEqual(event.content_sha256, attempt["response_sha256"])
            self.assertEqual(
                hashlib.sha256(event.redacted_body).hexdigest(), event.content_sha256
            )
            self.assertEqual(json.loads(wire.read_bytes()), json.loads(event.redacted_body))

    def test_local_raw_addresses_and_signatures_are_absent_from_tracked_outputs(self) -> None:
        receipt_path = CANONICAL_RUN / "receipts/capture.receipt.json"
        if not receipt_path.is_file():
            self.skipTest("ignored local A5R1 raw capture is not available")
        persisted = b"".join((OUTPUT_DIR / name).read_bytes() for name in EXPECTED_OUTPUTS)
        raw_values: set[str] = set()
        for wire in sorted(WIRE_RUN.glob("*.response.json")):
            document = json.loads(wire.read_bytes())
            for transaction in document["result"]["data"]:
                raw_values.update(transaction["transaction"]["signatures"])
                raw_values.update(transaction["transaction"]["message"]["accountKeys"])
                loaded = transaction["meta"].get("loadedAddresses") or {}
                raw_values.update(loaded.get("writable") or [])
                raw_values.update(loaded.get("readonly") or [])
        self.assertGreater(len(raw_values), 100)
        for value in raw_values:
            self.assertNotIn(value.encode("utf-8"), persisted)

    def test_recapture_projection_rebuild_is_deterministic_for_core_outputs(self) -> None:
        receipt_path = CANONICAL_RUN / "receipts/capture.receipt.json"
        if not receipt_path.is_file():
            self.skipTest("ignored local A5R1 raw capture is not available")
        local_root = ROOT / "local"
        local_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="task24-a5r1-", dir=local_root) as temp:
            output = Path(temp) / "projection"
            result = build_task24_linkage_projection(
                repo_root=ROOT,
                raw_root=ROOT / "data/raw",
                run_id=RUN_ID,
                receipt_sha256=RECEIPT_SHA256,
                output_dir=output,
            )
            self.assertEqual(result["owner_decision"], "REDESIGN_DATA")
            for name in (
                "entity_nodes_v1.jsonl",
                "entity_edges_v1.jsonl",
                "entity_candidates_v1.json",
                "entity_adjusted_concentration_v1.json",
            ):
                self.assertEqual(sha256(output / name), EXPECTED_OUTPUTS[name][0])

    def test_next_atom_is_recommended_but_not_authorized(self) -> None:
        self.assertEqual(
            self.manifest["next_boundary"]["recommended_atom"],
            "T24-A6_BOUNDED_DATA_REDESIGN_OR_STOP_DECISION_V1",
        )
        self.assertFalse(self.manifest["next_boundary"]["authorized"])
        self.assertIn("TASK24_DONE", self.manifest["non_claims"])
        self.assertEqual(self.manifest["authority"]["r3_or_outcome_reads"], 0)
        self.assertEqual(
            self.manifest["authority"]["wallet_signer_transaction_actions"], 0
        )


if __name__ == "__main__":
    unittest.main()
