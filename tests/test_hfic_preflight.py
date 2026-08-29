from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.data_root import (  # noqa: E402
    DataRootError,
    resolve_active_data_root,
)
from solana_alpha_lab.factory.hfic_preflight import (  # noqa: E402
    HficPreflightError,
    enumerate_rdp_datasets,
    prove_fast_lane_commissioned,
)


class DataRootResolverTests(unittest.TestCase):
    def test_single_commissioned_candidate_is_selected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            default_root = repo / "local/factory_v1/data_plane"
            env_root = Path(tmp) / "env_root"
            default_root.mkdir(parents=True)
            env_root.mkdir(parents=True)
            resolved = resolve_active_data_root(
                repo,
                env={"SMIAL_DATA_ROOT": str(env_root)},
                is_commissioned=lambda path: path == env_root,
            )
            self.assertEqual(resolved.root, env_root.resolve())
            self.assertEqual(resolved.selection_reason, "SINGLE_COMMISSIONED")
            self.assertNotIn(str(env_root), json.dumps(resolved.redacted_receipt()))

    def test_none_commissioned_prefers_valid_env_then_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            default_root = repo / "local/factory_v1/data_plane"
            env_root = Path(tmp) / "env_root"
            default_root.mkdir(parents=True)
            env_root.mkdir(parents=True)
            resolved = resolve_active_data_root(
                repo,
                env={"SMIAL_DATA_ROOT": str(env_root)},
                is_commissioned=lambda _path: False,
            )
            self.assertEqual(resolved.root, env_root.resolve())
            self.assertEqual(resolved.selection_reason, "ENV_UNCOMMISSIONED")

    def test_divergent_commissioned_roots_are_split_brain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            default_root = repo / "local/factory_v1/data_plane"
            env_root = Path(tmp) / "env_root"
            default_root.mkdir(parents=True)
            env_root.mkdir(parents=True)
            with self.assertRaises(DataRootError) as raised:
                resolve_active_data_root(
                    repo,
                    env={"SMIAL_DATA_ROOT": str(env_root)},
                    is_commissioned=lambda _path: True,
                    inventory_digest=lambda path: f"digest-{path.name}",
                )
            self.assertEqual(str(raised.exception), "DATA_ROOT_SPLIT_BRAIN")

    def test_identical_commissioned_roots_do_not_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            default_root = repo / "local/factory_v1/data_plane"
            env_root = Path(tmp) / "env_root"
            default_root.mkdir(parents=True)
            env_root.mkdir(parents=True)
            resolved = resolve_active_data_root(
                repo,
                env={"SMIAL_DATA_ROOT": str(env_root)},
                is_commissioned=lambda _path: True,
                inventory_digest=lambda _path: "same-digest",
            )
            self.assertEqual(resolved.root, env_root.resolve())
            self.assertEqual(resolved.selection_reason, "IDENTICAL_COMMISSIONED")
            self.assertTrue(resolved.duplicate_receipt)

    def test_symlink_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            real = Path(tmp) / "real"
            real.mkdir()
            link = Path(tmp) / "link"
            try:
                os.symlink(real, link, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlink unavailable")
            with self.assertRaises(DataRootError) as raised:
                resolve_active_data_root(
                    repo,
                    explicit_data_root=link,
                    is_commissioned=lambda _path: False,
                )
            self.assertEqual(str(raised.exception), "DATA_ROOT_INVALID")


class CommissioningProofTests(unittest.TestCase):
    def test_empty_directory_is_not_commissioned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(HficPreflightError) as raised:
                prove_fast_lane_commissioned(Path(tmp))
            self.assertEqual(str(raised.exception), "FAST_LANE_NOT_COMMISSIONED")

    def test_unrelated_store_records_do_not_prove_commissioning(self) -> None:
        from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent, ResearchStore

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            git_head = "0" * 40
            now = __import__("datetime").datetime(1970, 1, 1, tzinfo=__import__("datetime").UTC)
            payload = {
                "hypothesis_version_id": "HYP-UNRELATED-001",
                "statement": "noise",
            }
            encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            store.append(
                [
                    ResearchEvent(
                        record_id="HYP-UNRELATED-001",
                        record_kind=RecordKind.HYPOTHESIS_VERSION,
                        entity_id="HYP-UNRELATED-001",
                        hypothesis_version_id="HYP-UNRELATED-001",
                        run_id=None,
                        transaction_id="RESEARCH-TXN-NOISE-001",
                        effective_at=now,
                        first_reliable_available_at=now,
                        supersedes_record_id=None,
                        payload_json=encoded,
                        payload_sha256=__import__("hashlib").sha256(encoded.encode()).hexdigest(),
                        schema_version="1.0",
                        producer_capability_id="CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
                        producer_git_sha=git_head,
                        created_at=now,
                    )
                ],
                transaction_id="RESEARCH-TXN-NOISE-001",
            )
            with self.assertRaises(HficPreflightError) as raised:
                prove_fast_lane_commissioned(Path(tmp))
            self.assertEqual(str(raised.exception), "FAST_LANE_NOT_COMMISSIONED")

    def test_passport_git_mutation_is_rejected(self) -> None:
        from solana_alpha_lab.factory.commissioning_proof import (
            CommissioningProofError,
            verify_commissioning_passport,
        )

        with self.assertRaises(CommissioningProofError) as raised:
            verify_commissioning_passport({"git_mutation_count": 1, "provider_calls_actual": 0})
        self.assertEqual(str(raised.exception), "COMMISSION_GIT_MUTATION")

    def test_missing_git_mutation_count_is_rejected(self) -> None:
        from solana_alpha_lab.factory.commissioning_proof import (
            CommissioningProofError,
            verify_commissioning_passport,
        )

        passport = {
            "provider_calls_actual": 0,
            "run_id": "RUN-FAST-LANE-COMMISSIONING-FIXTURE-001",
        }
        with self.assertRaises(CommissioningProofError) as raised:
            verify_commissioning_passport(passport)
        self.assertEqual(str(raised.exception), "COMMISSION_GIT_MUTATION_COUNT_MISSING")

    def test_owner_json_never_contains_physical_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            default_root = repo / "local/factory_v1/data_plane"
            default_root.mkdir(parents=True)
            resolved = resolve_active_data_root(
                repo,
                env={},
                is_commissioned=lambda _path: False,
            )
            rendered = json.dumps(resolved.redacted_receipt(), sort_keys=True)
            self.assertNotIn(str(default_root), rendered)
            self.assertNotIn(":\\", rendered)
            self.assertNotIn("SMIAL_DATA_ROOT", rendered)


class ObservationScheduleInventoryRepairTests(unittest.TestCase):
    def test_sidecars_are_ignored_and_canonical_corrupt_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifests = Path(tmp) / "datasets" / "manifests"
            manifests.mkdir(parents=True)
            (manifests / "DATASET-MANIFEST-EARLY-ICP-FIRST-HIT-MIX-FALSIFIER-001.decision.json").write_text(
                "{not-json",
                encoding="utf-8",
            )
            (manifests / "DATASET-MANIFEST-EARLY-ICP-FIRST-HIT-MIX-FALSIFIER-001.labels.json").write_text(
                "{not-json",
                encoding="utf-8",
            )
            canonical = manifests / ("dataset-" + ("a" * 64) + ".json")
            canonical.write_text("{not-json", encoding="utf-8")
            stable = manifests / "DATASET-MANIFEST-EARLY-ICP-FIRST-HIT-MIX-FALSIFIER-001.json"
            stable.write_text("{not-json", encoding="utf-8")
            entries, warnings = enumerate_rdp_datasets(Path(tmp))
            self.assertEqual(entries, [])
            codes = [item["code"] for item in warnings]
            self.assertIn("DATASET_MANIFEST_CORRUPT", codes)
            self.assertEqual(codes.count("DATASET_MANIFEST_CORRUPT"), 1)
            self.assertEqual(
                [item["dataset_manifest_id"] for item in warnings if item["code"] == "DATASET_MANIFEST_CORRUPT"],
                [canonical.stem],
            )
