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
