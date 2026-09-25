"""Production software lineage, continuity proof, and one-forward release."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.live_ops_hardening import LiveOpsHardeningError
from solana_alpha_lab.factory.observation_schedule_lifecycle import (
    activation_transition_research_event_proven,
)
from solana_alpha_lab.factory.production_lineage import (
    DENY_CONVERGENCE_EVIDENCE_INCOMPLETE,
    DENY_LIVE_MAIN_DIVERGENCE,
    DENY_NON_MAINLINE_TARGET,
    LEGACY_DIVERGENT_SOURCE,
    ProductionLineageError,
    classify_forward,
    classify_legacy_convergence,
    evidence_sha256,
)


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _commit(repo: Path, name: str) -> str:
    path = repo / name
    path.write_text(name + "\n", encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "-c", "user.email=test@example.com", "-c", "user.name=test", "commit", "-m", name)
    return _git(repo, "rev-parse", "HEAD")


class ProductionLineageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        _git(self.repo, "init", "-b", "main")
        self.older = _commit(self.repo, "older.txt")
        self.newer = _commit(self.repo, "newer.txt")
        _git(self.repo, "checkout", "-b", "side", self.older)
        self.side = _commit(self.repo, "side.txt")
        _git(self.repo, "checkout", "main")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_canonical_forward_allows_mainline_descendant(self) -> None:
        mode = classify_forward(
            repo=self.repo,
            main_sha=self.newer,
            live_sha=self.older,
            target_sha=self.newer,
        )
        self.assertEqual(mode, "CANONICAL_FORWARD")

    def test_side_branch_target_is_denied(self) -> None:
        with self.assertRaises(ProductionLineageError) as caught:
            classify_forward(
                repo=self.repo,
                main_sha=self.newer,
                live_sha=self.older,
                target_sha=self.side,
            )
        self.assertEqual(caught.exception.code, DENY_NON_MAINLINE_TARGET)

    def test_divergent_live_is_denied_in_forward_mode(self) -> None:
        with self.assertRaises(ProductionLineageError) as caught:
            classify_forward(
                repo=self.repo,
                main_sha=self.newer,
                live_sha=self.side,
                target_sha=self.newer,
            )
        self.assertEqual(caught.exception.code, DENY_LIVE_MAIN_DIVERGENCE)

    def test_legacy_convergence_requires_exact_source_and_closed_evidence(self) -> None:
        payload = {
            "source_sha": LEGACY_DIVERGENT_SOURCE,
            "target_binding": "CANONICAL_MAINLINE_CONTAINING_THIS_EVIDENCE",
            "dispositions": [{"path": "src/example.py", "disposition": "PORT_REQUIRED"}],
        }
        digest = evidence_sha256(payload)
        mode = classify_legacy_convergence(
            repo=self.repo,
            main_sha=self.newer,
            live_sha=LEGACY_DIVERGENT_SOURCE,
            target_sha=self.newer,
            evidence=payload,
            expected_evidence_sha256=digest,
        )
        self.assertEqual(mode, "LEGACY_CONVERGENCE")
        payload["source_sha"] = "b" * 40
        with self.assertRaises(ProductionLineageError) as caught:
            classify_legacy_convergence(
                repo=self.repo,
                main_sha=self.newer,
                live_sha=LEGACY_DIVERGENT_SOURCE,
                target_sha=self.newer,
                evidence=payload,
                expected_evidence_sha256=digest,
            )
        self.assertEqual(caught.exception.code, DENY_CONVERGENCE_EVIDENCE_INCOMPLETE)

    def test_unknown_disposition_denies_convergence(self) -> None:
        payload = {
            "source_sha": LEGACY_DIVERGENT_SOURCE,
            "target_binding": "CANONICAL_MAINLINE_CONTAINING_THIS_EVIDENCE",
            "dispositions": [{"path": "src/example.py", "disposition": "UNKNOWN"}],
        }
        with self.assertRaises(ProductionLineageError) as caught:
            classify_legacy_convergence(
                repo=self.repo,
                main_sha=self.newer,
                live_sha=LEGACY_DIVERGENT_SOURCE,
                target_sha=self.newer,
                evidence=payload,
                expected_evidence_sha256=evidence_sha256(payload),
            )
        self.assertEqual(caught.exception.code, DENY_CONVERGENCE_EVIDENCE_INCOMPLETE)

    def test_plan_only_remains_on_main_cli(self) -> None:
        text = (ROOT / "scripts/discovery_evidence_release.py").read_text(encoding="utf-8")
        bounded = (
            ROOT / "src/solana_alpha_lab/factory/bounded_cohort_materialization.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"--plan-only"', text)
        self.assertIn("BOUNDED_COHORT_WINDOW", bounded)

    def test_unproven_active_projection_fails_closed(self) -> None:
        now = datetime(2026, 9, 25, tzinfo=UTC)
        self.assertFalse(
            activation_transition_research_event_proven(None, {"state": "ACTIVE"}, now=now)
        )
        self.assertFalse(
            activation_transition_research_event_proven(
                ROOT,
                {
                    "state": "ACTIVE",
                    "schedule_sha256": "a" * 64,
                    "activation_id": "ACT-TEST",
                    "last_transition_event_id": "OBS-TRANS-not-the-proof",
                    "starts_at": "2026-09-22T11:33:19Z",
                    "stops_admitting_at": "2026-09-29T11:33:19Z",
                    "transition_sequence": 1,
                    "payload": {
                        "new_state": "ACTIVE",
                        "prior_state": "AUTHORIZED",
                        "transition_event_id": "OBS-TRANS-different",
                        "transition_sequence": 1,
                        "transition_effective_at": "2026-09-22T11:33:19Z",
                        "authority_receipt_sha256": "c" * 64,
                    },
                },
                now=now,
            )
        )


class ReleaseQuiesceTests(unittest.TestCase):
    def _module(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "factory_live_release_convergence",
            ROOT / "scripts/factory_live_release.py",
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_inactive_service_stops_timer_and_restores_prior_state(self) -> None:
        module = self._module()
        calls: list[tuple[str, ...]] = []
        state = {"factory-observation-schedule.timer": "active", "factory-observation-schedule.service": "inactive"}

        def systemctl(*args: str) -> str:
            calls.append(args)
            if args[0] == "is-active":
                return state.get(args[1], "inactive")
            if args[0] == "stop" and args[1].endswith(".timer"):
                state[args[1]] = "inactive"
            if args[0] == "start" and args[1].endswith(".timer"):
                state[args[1]] = "active"
            return "ok"

        prior = module.quiesce_scheduled_code(systemctl=systemctl, sleep=lambda _seconds: None, budget_seconds=2)
        self.assertEqual(prior["factory-observation-schedule.timer"], "active")
        self.assertIn(("stop", "factory-observation-schedule.timer"), calls)
        module.restore_timer_state(prior, systemctl)
        self.assertEqual(state["factory-observation-schedule.timer"], "active")

    def test_active_tick_aborts_before_tree_change(self) -> None:
        module = self._module()
        state = {
            "factory-observation-schedule.timer": "active",
            "factory-observation-schedule.service": "active",
        }

        def systemctl(*args: str) -> str:
            if args[0] == "is-active":
                return state.get(args[1], "inactive")
            if args[0] == "stop":
                state[args[1]] = "inactive"
            if args[0] == "start":
                state[args[1]] = "active"
            return "ok"

        with self.assertRaisesRegex(LiveOpsHardeningError, "ABORT_DEPLOY"):
            module.quiesce_scheduled_code(systemctl=systemctl, sleep=lambda _seconds: None, budget_seconds=2)
        self.assertEqual(state["factory-observation-schedule.timer"], "active")

    def test_forward_release_is_one_transition(self) -> None:
        module = self._module()
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            _git(repo, "init", "-b", "main")
            older = _commit(repo, "older.txt")
            newer = _commit(repo, "newer.txt")
            deploy = Path(tmp) / "deploy"
            deploy.mkdir()
            (deploy / "local").mkdir()
            (deploy / "local" / "keep.txt").write_text("preserve\n", encoding="utf-8")
            (deploy / ".factory_deploy_sha").write_text(older + "\n", encoding="utf-8")

            def systemctl(*args: str) -> str:
                return "inactive"

            result = module.forward_release(
                repo=repo,
                deploy_root=deploy,
                target_sha=newer,
                main_sha=newer,
                live_sha=older,
                mode="canonical-forward",
                sync_env=False,
                systemctl=systemctl,
                sleep=lambda _seconds: None,
            )
            self.assertEqual(result["forward_transitions"], 1)
            self.assertFalse(result["rollback_performed"])
            self.assertEqual((deploy / ".factory_deploy_sha").read_text(encoding="utf-8").strip(), newer)
            self.assertEqual((deploy / "local" / "keep.txt").read_text(encoding="utf-8"), "preserve\n")
            self.assertTrue((deploy / "newer.txt").is_file())


if __name__ == "__main__":
    unittest.main()
