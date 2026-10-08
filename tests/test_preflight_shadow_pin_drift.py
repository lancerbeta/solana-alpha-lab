from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
SHA_A = hashlib.sha256(b"committed-bytes").hexdigest()
SHA_B = hashlib.sha256(b"other-bytes").hexdigest()


def load_harness() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "delivery_harness_shadow_pin", ROOT / "scripts/delivery_harness.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ShadowPinDiscriminatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_harness()

    def _scan(
        self,
        files: dict[str, dict],
        *,
        changed: set[str],
        blobs: dict[str, str],
        frozen: frozenset[str] | None = None,
    ) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence_root = root / "docs" / "evidence"
            for rel, payload in files.items():
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(payload), encoding="utf-8")
            return self.module._preflight_shadow_pin_problems(
                root,
                head="0" * 40,
                changed=changed,
                evidence_root=evidence_root,
                blob_sha_lookup=lambda relative: blobs.get(relative),
                frozen_evidence=frozen if frozen is not None else frozenset(),
            )

    def test_separate_drift_denies(self) -> None:
        reasons = self._scan(
            {
                "docs/evidence/hist/acceptance.json": {
                    "artifact_bindings": {
                        "agents": {"path": "AGENTS.md", "sha256": SHA_A}
                    }
                }
            },
            changed={"AGENTS.md"},
            blobs={"AGENTS.md": SHA_B},
        )
        self.assertEqual(
            reasons,
            ["SHADOW_PIN_DRIFT:docs/evidence/hist/acceptance.json->AGENTS.md"],
        )

    def test_co_moved_evidence_does_not_deny(self) -> None:
        reasons = self._scan(
            {
                "docs/evidence/hist/acceptance.json": {
                    "artifact_bindings": {
                        "agents": {"path": "AGENTS.md", "sha256": SHA_A}
                    }
                }
            },
            changed={"AGENTS.md", "docs/evidence/hist/acceptance.json"},
            blobs={"AGENTS.md": SHA_B},
        )
        self.assertEqual(reasons, [])

    def test_frozen_semantics_evidence_is_exempt(self) -> None:
        reasons = self._scan(
            {
                "docs/evidence/task21/durable_resume_router_binding_acceptance_v1.json": {
                    "protected_inputs": [{"path": "AGENTS.md", "sha256": SHA_A}]
                }
            },
            changed={"AGENTS.md"},
            blobs={"AGENTS.md": SHA_B},
            frozen=frozenset({"docs/evidence/task21/durable_resume_router_binding_acceptance_v1.json"}),
        )
        self.assertEqual(reasons, [])

    def test_matching_current_bytes_pass(self) -> None:
        reasons = self._scan(
            {
                "docs/evidence/hist/acceptance.json": {
                    "artifact_bindings": {
                        "agents": {"path": "AGENTS.md", "sha256": SHA_A}
                    }
                }
            },
            changed={"AGENTS.md"},
            blobs={"AGENTS.md": SHA_A},
        )
        self.assertEqual(reasons, [])

    def test_missing_target_blob_denies(self) -> None:
        reasons = self._scan(
            {
                "docs/evidence/hist/acceptance.json": {
                    "artifact_bindings": {
                        "gone": {"path": "deleted.py", "sha256": SHA_A}
                    }
                }
            },
            changed={"deleted.py"},
            blobs={},
        )
        self.assertEqual(
            reasons,
            ["SHADOW_PIN_TARGET_MISSING:docs/evidence/hist/acceptance.json->deleted.py"],
        )

    def test_unrelated_pin_outside_diff_is_ignored(self) -> None:
        reasons = self._scan(
            {
                "docs/evidence/hist/acceptance.json": {
                    "artifact_bindings": {
                        "other": {"path": "README.md", "sha256": SHA_A}
                    }
                }
            },
            changed={"AGENTS.md"},
            blobs={"AGENTS.md": SHA_B},
        )
        self.assertEqual(reasons, [])

    def _pin(self, target: str) -> dict:
        return {
            "docs/evidence/hist/acceptance.json": {
                "protected_inputs": [{"path": target, "sha256": SHA_A}]
            }
        }

    def test_catalog_registry_pin_is_snapshot_only(self) -> None:
        target = "catalog/assets/core.yaml"
        self.assertEqual(
            self._scan(self._pin(target), changed={target}, blobs={target: SHA_B}),
            [],
        )

    def test_nav_output_and_manifest_pins_are_snapshot_only(self) -> None:
        harness_sync = self.module._load_harness_sync_module()
        for target in (harness_sync.NAV_OUTPUTS[0], harness_sync.MANIFEST_RELATIVE):
            self.assertEqual(
                self._scan(self._pin(target), changed={target}, blobs={target: SHA_B}),
                [],
                target,
            )

    def test_product_path_pin_still_denies(self) -> None:
        target = "src/solana_alpha_lab/task21_owner_pulse.py"
        self.assertEqual(
            self._scan(self._pin(target), changed={target}, blobs={target: SHA_B}),
            [f"SHADOW_PIN_DRIFT:docs/evidence/hist/acceptance.json->{target}"],
        )

    def test_exempt_set_is_exactly_the_harness_sync_constants(self) -> None:
        harness_sync = self.module._load_harness_sync_module()
        self.assertEqual(
            self.module.harness_owned_aggregate_paths(),
            frozenset(
                {
                    harness_sync.MANIFEST_RELATIVE,
                    *harness_sync.ASSET_REGISTRIES,
                    *harness_sync.NAV_OUTPUTS,
                }
            ),
        )
        for target in self.module.harness_owned_aggregate_paths():
            self.assertEqual(
                self._scan(self._pin(target), changed={target}, blobs={target: SHA_B}),
                [],
                target,
            )

    def test_registry_contains_only_known_frozen_files(self) -> None:
        self.assertEqual(
            self.module.FROZEN_SEMANTICS_EVIDENCE_FILES,
            frozenset(
                {
                    "docs/evidence/task21/durable_resume_router_binding_acceptance_v1.json",
                    "docs/evidence/task21/task21_artifact_index_v1.json",
                    "docs/evidence/forge_composite_feature_recipes_v1/a1_native_isolation_v1.json",
                }
            ),
        )
        for relative in self.module.FROZEN_SEMANTICS_EVIDENCE_FILES:
            self.assertTrue((ROOT / relative).is_file(), relative)

    def test_composite_isolation_pins_are_frozen_accepted_base_bytes(self) -> None:
        relative = "docs/evidence/forge_composite_feature_recipes_v1/a1_native_isolation_v1.json"
        raw = (ROOT / relative).read_bytes()
        self.assertEqual(raw, self.module.git_bytes(ROOT, "show", f"04ec8e0286a3dce5999d0687784717ee90fc5dca:{relative}"))
        receipt = json.loads(raw)
        # The accepted receipt pins its final owner view, not the earlier
        # execution producer. Do not retroactively attest producer bytes.
        frozen = "04ec8e0286a3dce5999d0687784717ee90fc5dca"
        self.assertEqual(receipt["presearch_agent"]["input_execution_commit"],
                         "66abc2bb41db2e7f4cb2704980f74f4aafd0da7b")
        tracked = [row for row in receipt["presearch_agent"]["actual_attestation"]["actual_read_set"]
                   if not row["path"].startswith("local/")]
        self.assertEqual({row["path"] for row in tracked}, {
            ".agents/skills/hypothesis-forge/SKILL.md",
            "docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md",
        })
        for row in tracked:
            self.assertEqual(row["sha256"], hashlib.sha256(
                self.module.git_bytes(ROOT, "show", f"{frozen}:{row['path']}" )).hexdigest())
        with patch.object(self.module, "git_bytes", return_value=json.dumps(receipt).encode("utf-8")):
            reasons = self._scan({relative: receipt}, changed={row["path"] for row in tracked},
                                 blobs={row["path"]: SHA_B for row in tracked},
                                 frozen=self.module.FROZEN_SEMANTICS_EVIDENCE_FILES)
        self.assertEqual(reasons, [])
        altered = json.loads(raw)
        altered["presearch_agent"]["actual_attestation"]["actual_read_set"][1]["sha256"] = SHA_B
        with patch.object(self.module, "git_bytes", return_value=json.dumps(receipt).encode("utf-8")):
            reasons = self._scan({relative: altered}, changed={relative}, blobs={},
                                 frozen=self.module.FROZEN_SEMANTICS_EVIDENCE_FILES)
        self.assertEqual(reasons, [f"FROZEN_PIN_EVIDENCE_DRIFT:{relative}"])

    def test_commit_bound_receipt_absence_denies_with_and_without_evidence_root(self) -> None:
        relative = "docs/evidence/forge_composite_feature_recipes_v1/a1_native_isolation_v1.json"
        for files in ({}, {"docs/evidence/other/receipt.json": {}}):
            with self.subTest(evidence_root_exists=bool(files)):
                with patch.object(self.module, "git_bytes", return_value=b"accepted receipt"):
                    reasons = self._scan(files, changed={relative}, blobs={}, frozen=frozenset({relative}))
                self.assertEqual(reasons, [f"FROZEN_PIN_EVIDENCE_UNAVAILABLE:{relative}"])

    def test_commit_bound_receipt_guard_does_not_depend_on_json_discovery(self) -> None:
        relative = "docs/evidence/forge_composite_feature_recipes_v1/a1_native_isolation_v1.json"
        with patch.object(Path, "rglob", return_value=iter(())):
            with patch.object(self.module, "git_bytes", return_value=b"accepted receipt"):
                reasons = self._scan({relative: {"tampered": True}}, changed={relative}, blobs={},
                                     frozen=frozenset({relative}))
        self.assertEqual(reasons, [f"FROZEN_PIN_EVIDENCE_DRIFT:{relative}"])

    def test_commit_bound_receipt_unavailable_git_blob_denies(self) -> None:
        relative = "docs/evidence/forge_composite_feature_recipes_v1/a1_native_isolation_v1.json"
        with patch.object(self.module, "git_bytes", side_effect=ValueError("unavailable")):
            reasons = self._scan({relative: {}}, changed={relative}, blobs={}, frozen=frozenset({relative}))
        self.assertEqual(reasons, [f"FROZEN_PIN_EVIDENCE_UNAVAILABLE:{relative}"])


class WorktreeCommittedDivergenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_harness()

    def test_crlf_worktree_versus_lf_blob_denies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            relative = "docs/evidence/control/example.json"
            path = root / relative
            path.parent.mkdir(parents=True)
            path.write_bytes(b'{"k": "v"}\r\n')
            reasons = self.module._preflight_worktree_committed_divergence(
                root,
                head="0" * 40,
                changed=[relative],
                blob_reader=lambda _rel: b'{"k": "v"}\n',
            )
        self.assertEqual(reasons, [f"WORKTREE_COMMITTED_DIVERGENCE:{relative}"])

    def test_matching_bytes_pass(self) -> None:
        payload = b'{"k": "v"}\n'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            relative = "AGENTS.md"
            (root / relative).write_bytes(payload)
            reasons = self.module._preflight_worktree_committed_divergence(
                root,
                head="0" * 40,
                changed=[relative],
                blob_reader=lambda _rel: payload,
            )
        self.assertEqual(reasons, [])

    def test_deleted_candidate_path_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reasons = self.module._preflight_worktree_committed_divergence(
                root,
                head="0" * 40,
                changed=["gone.py"],
                blob_reader=lambda _rel: b"x",
            )
        self.assertEqual(reasons, [])


class WalkPinsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_harness()

    def test_nested_and_rejects_unsafe_paths(self) -> None:
        payload = {
            "outer": {
                "path": "AGENTS.md",
                "sha256": SHA_A,
                "nested": [{"path": "../etc/passwd", "sha256": SHA_B}],
            },
            "skip": {"path": "/abs", "sha256": SHA_A},
        }
        pins = self.module.walk_path_sha256_pins(payload)
        self.assertEqual(pins, [("AGENTS.md", SHA_A)])


class CommittedBindingHashTests(unittest.TestCase):
    def test_gate_bindings_follow_git_show_not_worktree_bytes(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "owner_attention_gate_shadow", ROOT / "scripts/owner_attention_gate.py"
        )
        assert spec is not None and spec.loader is not None
        gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gate)
        from tests.test_delivery_harness_merge_guard import (
            BASE,
            HEAD,
            write_delivery_evidence_fixture,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipt = write_delivery_evidence_fixture(gate, root)
            committed = (root / "impl.txt").read_bytes()
            diverged = (
                committed.replace(b"\n", b"\r\n")
                if b"\r\n" not in committed
                else committed.replace(b"\r\n", b"\n")
            )
            self.assertNotEqual(committed, diverged)
            (root / "impl.txt").write_bytes(diverged)

            def runner(args: list[str], cwd: Path) -> bytes:
                if args[:2] == ["git", "show"] and args[2].endswith(":impl.txt"):
                    return committed
                raise ValueError("LIVE_READBACK_FAILED")

            result = gate.bound_delivery_evidence(
                root,
                receipt,
                expected_base=BASE,
                head=HEAD,
                inventory_builder=lambda *args, **kwargs: "1" * 64,
                runner=runner,
            )
        self.assertTrue(result["factory_fit_pass"])


if __name__ == "__main__":
    unittest.main()
