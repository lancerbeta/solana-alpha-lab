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
    CONVERGENCE_EVIDENCE_PATH,
    DENY_CONVERGENCE_EVIDENCE_INCOMPLETE,
    DENY_LIVE_MAIN_DIVERGENCE,
    DENY_NON_MAINLINE_TARGET,
    LEGACY_DIVERGENT_SOURCE,
    ProductionLineageError,
    classify_forward,
    classify_legacy_convergence,
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

    def _commit_evidence(self, payload: dict) -> str:
        path = self.repo / CONVERGENCE_EVIDENCE_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        _git(self.repo, "add", CONVERGENCE_EVIDENCE_PATH)
        _git(
            self.repo,
            "-c",
            "user.email=test@example.com",
            "-c",
            "user.name=test",
            "commit",
            "-m",
            "evidence",
        )
        return _git(self.repo, "rev-parse", "HEAD")

    def _closed_evidence(self) -> dict:
        raw = json.loads((ROOT / CONVERGENCE_EVIDENCE_PATH).read_text(encoding="utf-8"))
        return raw

    def test_legacy_convergence_requires_exact_current_main(self) -> None:
        payload = self._closed_evidence()
        head = self._commit_evidence(payload)
        mode = classify_legacy_convergence(
            repo=self.repo,
            main_sha=head,
            live_sha=LEGACY_DIVERGENT_SOURCE,
            target_sha=head,
        )
        self.assertEqual(mode, "LEGACY_CONVERGENCE")

    def test_legacy_convergence_denies_older_mainline_without_repair(self) -> None:
        with self.assertRaises(ProductionLineageError) as caught:
            classify_legacy_convergence(
                repo=self.repo,
                main_sha=self.newer,
                live_sha=LEGACY_DIVERGENT_SOURCE,
                target_sha=self.newer,
            )
        self.assertEqual(caught.exception.code, DENY_CONVERGENCE_EVIDENCE_INCOMPLETE)

    def test_legacy_evidence_outside_target_tree_is_denied(self) -> None:
        payload = self._closed_evidence()
        payload["source_sha"] = "b" * 40
        head = self._commit_evidence(payload)
        with self.assertRaises(ProductionLineageError) as caught:
            classify_legacy_convergence(
                repo=self.repo,
                main_sha=head,
                live_sha=LEGACY_DIVERGENT_SOURCE,
                target_sha=head,
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

    def test_inactive_is_normal_not_a_command_failure(self) -> None:
        module = self._module()
        self.assertEqual(module.interpret_is_active(3, "inactive\n", ""), "inactive")
        self.assertEqual(module.interpret_is_active(3, "failed\n", ""), "failed")
        self.assertEqual(module.interpret_is_active(4, "", "Unit foo.service could not be found.\n"), "not-found")
        self.assertEqual(module.interpret_is_active(0, "active\n", ""), "active")
        with self.assertRaisesRegex(LiveOpsHardeningError, "SYSTEMCTL_STATE_ERROR"):
            module.interpret_is_active(1, "", "Failed to connect to bus")

    def test_inactive_oneshot_quiesce_does_not_fail(self) -> None:
        module = self._module()
        calls: list[tuple[str, ...]] = []
        state = {
            "factory-observation-schedule.timer": "active",
            "factory-observation-schedule.service": "inactive",
        }

        def probe(unit: str) -> str:
            return state.get(unit, "inactive")

        def control(action: str, unit: str) -> str:
            calls.append((action, unit))
            if action == "stop":
                state[unit] = "inactive"
            if action == "start":
                state[unit] = "active"
            return "ok"

        prior = module.quiesce_for_release(
            probe=probe,
            control=control,
            sleep=lambda _seconds: None,
            timers=("factory-observation-schedule.timer",),
            services=("factory-v1-workbench.service",),
            budget_seconds=2,
        )
        self.assertEqual(prior["phase"], "QUIESCED")
        self.assertIn(("stop", "factory-observation-schedule.timer"), calls)
        self.assertNotIn(("start", "factory-v1-workbench.service"), calls)

    def test_quiesce_exception_restores_stopped_triggers(self) -> None:
        module = self._module()
        state = {"factory-observation-schedule.timer": "active"}
        probes = {"n": 0}

        def probe(unit: str) -> str:
            probes["n"] += 1
            if probes["n"] >= 2 and unit.endswith(".service"):
                raise RuntimeError("probe blew up")
            return state.get(unit, "inactive")

        def control(action: str, unit: str) -> str:
            if action == "stop":
                state[unit] = "inactive"
            if action == "start":
                state[unit] = "active"
            return "ok"

        with self.assertRaises(RuntimeError):
            module.quiesce_for_release(
                probe=probe,
                control=control,
                sleep=lambda _seconds: None,
                timers=("factory-observation-schedule.timer",),
                services=(),
                budget_seconds=1,
            )
        self.assertEqual(state["factory-observation-schedule.timer"], "active")

    def test_active_long_running_stops_before_tree_and_restores_after(self) -> None:
        module = self._module()
        order: list[str] = []
        state = {
            "tick.timer": "inactive",
            "tick.service": "inactive",
            "factory-v1-workbench.service": "active",
            "factory-remote-health.service": "inactive",
        }

        def probe(unit: str) -> str:
            return state.get(unit, "inactive")

        def control(action: str, unit: str) -> str:
            order.append(f"{action}:{unit}")
            if action == "stop":
                state[unit] = "inactive"
            if action == "start":
                state[unit] = "active"
            return "ok"

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            _git(repo, "init", "-b", "main")
            older = _commit(repo, "older.txt")
            newer = _commit(repo, "newer.txt")
            deploy = Path(tmp) / "deploy"
            deploy.mkdir()
            (deploy / "local").mkdir()
            real_install = module._install_exact_tree

            def install(**kwargs):
                order.append("mutate")
                self.assertEqual(state["factory-v1-workbench.service"], "inactive")
                return real_install(**kwargs)

            module._install_exact_tree = install
            result = module.forward_release(
                repo=repo,
                deploy_root=deploy,
                target_sha=newer,
                main_sha=newer,
                live_sha=older,
                sync_env=False,
                probe=probe,
                control=control,
                sleep=lambda _seconds: None,
                timers=("tick.timer",),
            )
            self.assertEqual(result["forward_transitions"], 1)
            self.assertLess(order.index("stop:factory-v1-workbench.service"), order.index("mutate"))
            self.assertLess(order.index("mutate"), order.index("start:factory-v1-workbench.service"))
            self.assertNotIn("start:factory-remote-health.service", order)
            self.assertEqual(state["factory-remote-health.service"], "inactive")

    def test_no_start_before_verified_rollback(self) -> None:
        module = self._module()
        starts: list[str] = []
        verified = {"n": 0}

        def probe(unit: str) -> str:
            return "active" if unit == "tick.timer" else "inactive"

        def control(action: str, unit: str) -> str:
            if action == "start":
                self.assertGreaterEqual(verified["n"], 2)
                starts.append(f"{verified['n']}:{unit}")
            return "ok"

        real_verify = module.verify_installed_tree

        def verify(**kwargs):
            verified["n"] += 1
            if verified["n"] == 1:
                raise LiveOpsHardeningError("INSTALL_TREE_MISMATCH")
            return real_verify(**kwargs)

        module.verify_installed_tree = verify
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            _git(repo, "init", "-b", "main")
            older = _commit(repo, "older.txt")
            newer = _commit(repo, "newer.txt")
            deploy = Path(tmp) / "deploy"
            deploy.mkdir()
            (deploy / "local").mkdir()
            with self.assertRaisesRegex(LiveOpsHardeningError, "INSTALL_TREE_MISMATCH"):
                module.forward_release(
                    repo=repo,
                    deploy_root=deploy,
                    target_sha=newer,
                    main_sha=newer,
                    live_sha=older,
                    sync_env=False,
                    probe=probe,
                    control=control,
                    sleep=lambda _seconds: None,
                    timers=("tick.timer",),
                )
            self.assertEqual((deploy / ".factory_deploy_sha").read_text(encoding="utf-8").strip(), older)
            self.assertEqual(starts, ["2:tick.timer"])

    def test_unresolved_recovery_leaves_units_quiesced(self) -> None:
        module = self._module()
        starts: list[str] = []

        def probe(_unit: str) -> str:
            return "active" if _unit == "tick.timer" else "inactive"

        def control(action: str, unit: str) -> str:
            if action == "start":
                starts.append(unit)
            return "ok"

        def boom(**_kwargs):
            raise LiveOpsHardeningError("INSTALL_TREE_MISMATCH")

        module._install_exact_tree = boom
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            _git(repo, "init", "-b", "main")
            older = _commit(repo, "older.txt")
            newer = _commit(repo, "newer.txt")
            deploy = Path(tmp) / "deploy"
            deploy.mkdir()
            with self.assertRaisesRegex(LiveOpsHardeningError, "UNRESOLVED_RECOVERY"):
                module.forward_release(
                    repo=repo,
                    deploy_root=deploy,
                    target_sha=newer,
                    main_sha=newer,
                    live_sha=older,
                    sync_env=False,
                    probe=probe,
                    control=control,
                    sleep=lambda _seconds: None,
                    timers=("tick.timer",),
                )
        self.assertEqual(starts, [])

    def test_timer_inventory_includes_external_heartbeat(self) -> None:
        module = self._module()
        timers = module.load_scheduled_code_timers()
        self.assertIn("factory-external-heartbeat.timer", timers)
        configured = {
            path.name
            for path in (ROOT / "configs" / "factory_remote_ops").glob("*.timer")
        }
        self.assertEqual(set(timers), configured)

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

            def probe(_unit: str) -> str:
                return "inactive"

            def control(*_args: str) -> str:
                return "ok"

            result = module.forward_release(
                repo=repo,
                deploy_root=deploy,
                target_sha=newer,
                main_sha=newer,
                live_sha=older,
                mode="canonical-forward",
                sync_env=False,
                probe=probe,
                control=control,
                sleep=lambda _seconds: None,
                timers=("tick.timer",),
            )
            self.assertEqual(result["forward_transitions"], 1)
            self.assertFalse(result["rollback_performed"])
            self.assertEqual((deploy / ".factory_deploy_sha").read_text(encoding="utf-8").strip(), newer)
            self.assertEqual((deploy / "local" / "keep.txt").read_text(encoding="utf-8"), "preserve\n")
            self.assertTrue((deploy / "newer.txt").is_file())


if __name__ == "__main__":
    unittest.main()
