from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.data_root import (  # noqa: E402
    DEFAULT_DATA_PLANE_RELATIVE,
    resolve_data_root,
    resolve_existing_data_root,
)
from solana_alpha_lab.factory.forge_input_receipt import (  # noqa: E402
    CURRENT_CORPUS_EXCLUDED_FROM_PACKET,
    CURRENT_CORPUS_MISSING,
    OWNER_CLASS_INPUT_NOT_READY,
    OWNER_CLASS_OBSERVABILITY_BLOCKED,
    OWNER_CLASS_READY,
    SCHEMA,
    build_forge_input_receipt,
    format_forge_input_owner_block,
)
from solana_alpha_lab.factory.live_cohort_discovery_release import (  # noqa: E402
    CORPUS_DATASET_ID,
)


def _git(cwd: Path, *args: str) -> None:
    subprocess.check_call(["git", *args], cwd=cwd, stdout=subprocess.DEVNULL)


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True)
    _git(path, "init", "-b", "main")
    _git(path, "config", "user.email", "a3@test")
    _git(path, "config", "user.name", "a3")
    (path / "README.md").write_text("a3\n", encoding="utf-8")
    _git(path, "add", "README.md")
    _git(path, "commit", "-m", "init")


def _write_lineage(data_root: Path, *, mid: str = "MID-CURRENT") -> None:
    lineage_dir = data_root / "datasets" / "live_lifecycle_corpus"
    lineage_dir.mkdir(parents=True)
    payload = {
        "corpus_dataset_id": CORPUS_DATASET_ID,
        "current_corpus_version": 2,
        "current_dataset_manifest_id": mid,
        "cohorts": [
            {"cohort_id": "REL-C1", "release_id": "rel-c1", "source_sha256": "aa" * 32},
            {"cohort_id": "REL-C2", "release_id": "rel-c2", "source_sha256": "bb" * 32},
        ],
    }
    (lineage_dir / "lineage.json").write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )


def _live_dataset(mid: str = "MID-CURRENT") -> dict[str, object]:
    return {
        "dataset_manifest_id": mid,
        "dataset_id": CORPUS_DATASET_ID,
        "dataset_version": "2.0",
        "labels": {
            "logical_dataset_id": CORPUS_DATASET_ID,
            "corpus_version": 2,
            "yield_eligible": 40,
        },
        "yield_eligible": 40,
    }


def _enumerate_live(_data_root: Path):
    return [_live_dataset()], []


class ForgeInputReceiptTests(unittest.TestCase):
    def test_g_a3_3_missing_corpus_is_input_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.run_preflight",
                side_effect=AssertionError("builder must not call run_preflight"),
            ):
                receipt = build_forge_input_receipt(data_root, repo_root=ROOT)
        self.assertEqual(receipt["schema"], SCHEMA)
        self.assertEqual(receipt["owner_class"], OWNER_CLASS_INPUT_NOT_READY)
        self.assertFalse(receipt["forge_runnable"])
        self.assertIn(CURRENT_CORPUS_MISSING, receipt["blocking_reason_codes"])
        self.assertIsNone(receipt.get("session_id"))
        self.assertEqual(receipt["writes"]["research_store"], 0)
        self.assertEqual(receipt["experiment_data_scope"]["status"], "NOT_STARTED")
        block = format_forge_input_owner_block(receipt)
        self.assertIn("FORGE INPUT", block)
        self.assertNotIn("NO_WORTHY", block)
        self.assertIn("WAIT_FOR_IMPORT_OR_STOP", block)
        self.assertIn("NOT_EVALUATED", block)
        rendered = json.dumps(receipt)
        self.assertNotIn("C:\\", rendered)

    def test_g_a3_5_good_current_c2_is_runnable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                receipt = build_forge_input_receipt(data_root, repo_root=ROOT)
        self.assertEqual(receipt["owner_class"], OWNER_CLASS_READY)
        self.assertTrue(receipt["forge_runnable"])
        self.assertEqual(
            receipt["active_evidence_set"]["visible_cohort_ids"],
            ["REL-C1", "REL-C2"],
        )
        self.assertEqual(receipt["active_evidence_set"]["corpus_version"], 2)
        self.assertTrue(receipt["packet"]["live_corpus_in_packet"])
        self.assertTrue(receipt["packet"]["live_corpus_protected"])
        block = format_forge_input_owner_block(receipt)
        self.assertIn("REL-C1", block)
        self.assertIn("REL-C2", block)

    def test_g_a3_1_linked_worktree_sees_same_c1_c2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            principal = Path(tmp) / "principal"
            linked = Path(tmp) / "linked"
            _init_repo(principal)
            _git(principal, "worktree", "add", str(linked), "-b", "linked-a3")
            try:
                plane = principal / DEFAULT_DATA_PLANE_RELATIVE
                plane.mkdir(parents=True)
                _write_lineage(plane)
                from_linked = resolve_data_root(linked, env={})
                self.assertEqual(from_linked, plane.resolve())
                with patch(
                    "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                    side_effect=_enumerate_live,
                ):
                    receipt = build_forge_input_receipt(from_linked, repo_root=ROOT)
            finally:
                _git(principal, "worktree", "remove", "--force", str(linked))
        self.assertEqual(
            receipt["active_evidence_set"]["visible_cohort_ids"],
            ["REL-C1", "REL-C2"],
        )
        self.assertTrue(receipt["forge_runnable"])

    def test_g_a3_4_live_corpus_drop_is_observability_blocked(self) -> None:
        def _drop(enumerated, **_kwargs):
            del enumerated
            return [], {
                "truncated": True,
                "max_datasets": 8,
                "selection_policy": "forced_drop",
                "live_corpus_protected": False,
                "live_corpus_in_packet": False,
            }

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ), patch(
                "solana_alpha_lab.factory.hfic_preflight.select_forge_packet_datasets",
                side_effect=_drop,
            ):
                receipt = build_forge_input_receipt(data_root, repo_root=ROOT)
        self.assertEqual(receipt["owner_class"], OWNER_CLASS_OBSERVABILITY_BLOCKED)
        self.assertFalse(receipt["forge_runnable"])
        self.assertIn(CURRENT_CORPUS_EXCLUDED_FROM_PACKET, receipt["blocking_reason_codes"])
        self.assertTrue(receipt["visibility"]["material_truncation"])

    def test_g_a3_2_historical_stale_manifest_stays_caveat(self) -> None:
        from solana_alpha_lab.factory.hfic_selection_robustness_gate import (
            FORGE_ELIGIBLE_WITH_SELECTION_CAVEAT,
        )

        historical = [
            {
                "scope": "HISTORICAL_CALIBRATION",
                "calibration_id": "HFIC_SELECTION_ROBUSTNESS_GATE_V1",
                "cohort_scope": "C1",
                "eligibility_scope": "FULL_LIFECYCLE_COMPLETENESS",
                "receipt_sha256": "ab" * 32,
                "router_decision": FORGE_ELIGIBLE_WITH_SELECTION_CAVEAT,
                "integrity": "PASS",
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root, mid="MID-C2")
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=lambda _root: ([_live_dataset("MID-C2")], []),
            ), patch(
                "solana_alpha_lab.factory.forge_input_receipt._historical_calibration",
                return_value=(historical, None),
            ):
                receipt = build_forge_input_receipt(data_root, repo_root=ROOT)
        self.assertTrue(receipt["forge_runnable"])
        self.assertEqual(receipt["historical_calibration"][0]["integrity"], "PASS")
        self.assertEqual(
            receipt["historical_calibration"][0]["eligibility_scope"],
            "FULL_LIFECYCLE_COMPLETENESS",
        )
        self.assertEqual(receipt["active_evidence_set"]["current_dataset_manifest_id"], "MID-C2")

    def test_forge_input_cli_missing_plane_is_input_not_ready(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "hypothesis_forge_a3", ROOT / "scripts" / "hypothesis_forge.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        from io import StringIO
        from contextlib import redirect_stdout

        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "no-plane"
            captured = StringIO()
            with redirect_stdout(captured):
                code = module.cmd_forge_input(ROOT, explicit_data_root=missing)
        self.assertEqual(code, 2)
        payload = json.loads(captured.getvalue())
        self.assertEqual(payload["owner_class"], OWNER_CLASS_INPUT_NOT_READY)
        self.assertFalse(payload["forge_runnable"])
        self.assertEqual(payload["next"], "WAIT_FOR_IMPORT_OR_STOP")


class RealPlaneNoWriteTests(unittest.TestCase):
    def test_canonical_plane_no_write_when_present(self) -> None:
        resolved = resolve_existing_data_root(ROOT)
        if resolved.status != "PRESENT" or resolved.root is None:
            self.skipTest("canonical data plane not present in this checkout")
        root = resolved.root

        def fingerprint() -> str:
            parts: list[str] = []
            targets = [
                root / "datasets" / "live_lifecycle_corpus" / "lineage.json",
                root / "research",
            ]
            files: list[Path] = []
            for target in targets:
                if target.is_file():
                    files.append(target)
                elif target.is_dir():
                    files.extend(
                        path
                        for path in target.rglob("*")
                        if path.is_file() and not path.is_symlink()
                    )
            for path in sorted(files):
                rel = path.relative_to(root).as_posix()
                stat = path.stat()
                parts.append(f"{rel}:{stat.st_size}:{stat.st_mtime_ns}")
            return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()

        before = fingerprint()
        receipt = build_forge_input_receipt(root, repo_root=ROOT)
        after = fingerprint()
        self.assertEqual(before, after)
        self.assertEqual(receipt["writes"]["research_store"], 0)
        self.assertEqual(receipt["writes"]["session"], 0)
        ids = receipt["active_evidence_set"]["visible_cohort_ids"]
        self.assertGreaterEqual(len(ids), 2)
        self.assertEqual(receipt["active_evidence_set"]["corpus_version"], 2)


if __name__ == "__main__":
    unittest.main()
