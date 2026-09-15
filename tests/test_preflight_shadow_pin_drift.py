from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
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
            frozen=self.module.FROZEN_SEMANTICS_EVIDENCE_FILES,
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

    def test_registry_contains_only_known_frozen_files(self) -> None:
        self.assertEqual(
            self.module.FROZEN_SEMANTICS_EVIDENCE_FILES,
            frozenset(
                {
                    "docs/evidence/task21/durable_resume_router_binding_acceptance_v1.json",
                    "docs/evidence/task21/task21_artifact_index_v1.json",
                }
            ),
        )
        for relative in self.module.FROZEN_SEMANTICS_EVIDENCE_FILES:
            self.assertTrue((ROOT / relative).is_file(), relative)


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
