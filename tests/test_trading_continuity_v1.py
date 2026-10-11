"""Independent continuity regressions; engine probes are not whole-chain proof."""
from __future__ import annotations

from contextlib import contextmanager
from contextlib import redirect_stdout
from io import StringIO
import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
import shutil
import sqlite3
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch

import yaml

from tests.test_paper_shadow_execution_integrity_vertical_v1 import (
    StoreCase, ROOT, accept, open_filled, signal, fail_once_on_event,
)
from solana_alpha_lab.factory.paper_plane import PaperPlaneError, accept_signal_decision
from solana_alpha_lab.factory.paper_shadow_commands import apply_operator_command
from solana_alpha_lab.factory.paper_shadow_operations import build_operations_projection
from solana_alpha_lab.factory.trading_operations import _bot_context
from solana_alpha_lab.factory import hfic_research_scope as scope
from solana_alpha_lab.factory.promotion_handoff import materialize_strategy_candidate, verify_strategy_version, PromotionHandoffError
from solana_alpha_lab.factory.strategy_runtime import canonical_spec_sha256
from solana_alpha_lab.factory.research_store import ResearchStore
from solana_alpha_lab.factory.application import FactoryApplication
from solana_alpha_lab.factory.research_workbench import LifecycleEntityLocatorV1
from solana_alpha_lab.factory.trading_runner import TradingContinuityRunner, OFFLINE_MARKER
from solana_alpha_lab.factory.paper_plane import PaperPlaneStore
from solana_alpha_lab.factory.trading_runtime_policy import apply_policy, show_policy
from tests.test_opportunity_episodes_harness_v1 import EpisodeScenario, nominate, token_object, synth_mint
from tests.test_opportunity_episodes_contract_v1 import episode_spec, HOLD
from tests.test_science_to_strategy_handoff_v1 import _schema_root, _event, _scientific_payload


class ConfirmedBaselineDefects(StoreCase):
    def test_mixed_mode_projection_has_no_combined_money_headline(self):
        store = self.store()
        paper_pid = open_filled(store, self.strategy, "SIGDEC-MIXED-PAPER", price="1")
        store.apply_paper_exit_fill(position_id=paper_pid, exit_unit_price_usd="1.1", mode="PAPER")
        epoch = "ACTIVATION-EPOCH-MIXED-SHADOW-001"
        shadow_signal = {**signal("SIGDEC-MIXED-SHADOW"), "activation_epoch_id": epoch}
        admitted = accept_signal_decision(ROOT, store, strategy=self.strategy, signal_decision=shadow_signal,
            known_activation_epochs={epoch: {"mode": "SHADOW"}}, mode="SHADOW", as_of=shadow_signal["decision_at"])
        store.apply_paper_entry_fill(position_id=admitted["position_id"], entry_unit_price_usd="1", entry_gross_notional_usd="100", fee_bps=10, mode="SHADOW")
        store.apply_paper_exit_fill(position_id=admitted["position_id"], exit_unit_price_usd="0.9", mode="SHADOW")
        view = build_operations_projection(store)
        self.assertIsNone(view["reconciled_net_pnl_usd"])
        self.assertIsNone(view["current_loss_streak_count"])
        self.assertIsNone(view["max_drawdown_usd"])
        self.assertEqual(len(view["economics_scopes"]), 2)

    def test_reserved_admission_is_in_operator_entry_count(self):
        store = self.store()
        result = accept(store, self.strategy, "SIGDEC-CONTINUITY-COUNT", skip_fill=True)
        bot = store.get_bot(result["bot_instance_id"])
        view = _bot_context(bot, build_operations_projection(store), relation="EXACT")
        self.assertEqual(store.open_risk_count(bot["bot_instance_id"]), 1)
        self.assertEqual(view["open_risk_count"], 1)

    def test_pause_after_admission_before_fill_dominates(self):
        store = self.store()
        operator = self.store()
        original = store.immediate_write
        fired = False

        @contextmanager
        def interleaving():
            nonlocal fired
            outer = not store._conn.in_transaction
            with original():
                yield
            rows = store.positions()
            if outer and not fired and rows and rows[0]["state"] == "WATCHED":
                fired = True
                apply_operator_command(operator, {
                    "command_type": "PAUSE_NEW_ENTRIES", "idempotency_key": "continuity-pause",
                    "bot_instance_id": rows[0]["bot_instance_id"],
                })

        with patch.object(store, "immediate_write", interleaving):
            try:
                accept(store, self.strategy, "SIGDEC-CONTINUITY-PAUSE")
            except PaperPlaneError as error:
                self.assertEqual(str(error), "ENTRIES_PAUSED")
        self.assertTrue(fired, "Controlled post-admission interleaving must execute")
        self.assertEqual(store.positions()[0]["state"], "CANCELLED")

    def test_duplicate_entry_result_has_one_accounting_effect(self):
        store = self.store()
        position_id = open_filled(store, self.strategy, "SIGDEC-CONTINUITY-DUP", price="0.000003")
        before = store.execution_events()
        store.apply_paper_entry_fill(position_id=position_id, entry_unit_price_usd="0.000003",
                                     entry_gross_notional_usd="100", fee_bps=10, mode="PAPER")
        self.assertEqual(store.execution_events(), before)

    def test_conflicting_entry_result_cannot_rewrite_inventory(self):
        store = self.store()
        position_id = open_filled(store, self.strategy, "SIGDEC-CONTINUITY-CONFLICT", price="0.000003")
        before = store.get_position(position_id)
        with self.assertRaisesRegex(PaperPlaneError, "ENTRY_FILL_CONTENT_CONFLICT"):
            store.apply_paper_entry_fill(position_id=position_id, entry_unit_price_usd="0.000004",
                                         entry_gross_notional_usd="100", fee_bps=10, mode="PAPER")
        self.assertEqual(store.get_position(position_id), before)


class OrdinarySourceTests(unittest.TestCase):
    """Synthetic vendor bytes; real membership, handoff, admission and result owners."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = _schema_root(Path(self.tmp.name) / "repo")
        for rel in ("catalog/schemas/experiment_spec.schema.json", "catalog/schemas/owner_lifecycle_projection_v1.schema.json",
                    "catalog/schemas/signal_decision_v1.schema.json", "catalog/schemas/exit_decision_v1.schema.json",
                    "configs/owner_lifecycle_projection_v1.yaml"):
            target = self.root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / rel, target)
        self.data = self.root / "local/offline-synth"
        self.data.mkdir(parents=True)
        (self.data / "offline_runtime.json").write_text(json.dumps(OFFLINE_MARKER), encoding="utf-8")
        self.start = datetime(2026, 10, 5, 12, 1, 6, tzinfo=UTC)
        self.source = EpisodeScenario(self.data / "source", start=self.start, stops=self.start + timedelta(minutes=1))
        self.mint = synth_mint("Continuity")
        self.membership = "TRUE"
        self.holders_start, self.holders_end = 60, 66
        self.late = False
        self.future_price = 0.0000033
        self.decision_price = 0.000003

    def tearDown(self):
        self.tmp.cleanup()

    def prepare(self, *, list_only=False, defer_publication=False):
        obj = token_object(self.mint, price=0.000003, liquidity=10000, holders=60)
        mapping = {"toptraded": [obj], "toptrending": [obj] if self.membership == "TRUE" else []}
        nominate(self.source.market, self.start, mapping)
        self.source.market.series[self.mint] = lambda now: token_object(self.mint,
            price=self.future_price if now.hour >= 16 else self.decision_price, liquidity=10000,
            holders=self.holders_end if now >= datetime(2026, 10, 5, 12, 35, tzinfo=UTC) else self.holders_start)
        if self.late:
            self.source.market.latency = lambda kind, now: 301 if kind == "search" and now.hour == 12 and now.minute == 35 else 1
        self.source.tick(self.start)
        self.admission = self.source.admissions()[0]
        fault = "EPISODE_BEFORE_PUBLISH" if defer_publication else None
        self.source.tick(datetime(2026, 10, 5, 12, 10, tzinfo=UTC), fault=fault)
        self.source.tick(datetime(2026, 10, 5, 12, 35, tzinfo=UTC), fault=fault)
        evidence = scope.MembershipEvidence()
        for definition in scope.jupiter_definitions(self.source.schedule).values():
            evidence.add_definition(definition)
        snapshot_shas = []
        list_a = "toptrending_5m"
        if self.membership == "UNKNOWN":
            # A genuinely late registered list is unknown at T0, not an absent mint.
            local = {"schema": "smial.local-membership-snapshot", "schema_version": "1.0",
                "definition": {"list_id": "LOCAL:SYNTH-A", "definition_version": "1", "provider_or_owner": "SYNTHETIC_FIXTURE",
                               "kind": "DECLARED_LIST", "semantics": {"purpose": "engineering"}},
                "member_identity_kind": "MINT", "members": [self.mint],
                "effective_from": "2026-10-05T12:00:00Z", "effective_until": "2026-10-06T12:00:00Z",
                "available_at": "2026-10-05T12:02:00Z", "basis": "EXPLICIT_SYNTHETIC_INPUT", "completeness": {"kind": "COMPLETE_FOR_INTERVAL"}}
            path = self.data / "local-list.json"
            path.write_text(json.dumps(local), encoding="utf-8")
            registered = scope.register_local_snapshot(self.data / "source", path, registered_at=datetime(2026, 10, 5, 12, 2, tzinfo=UTC))
            snapshot_shas = [registered["snapshot_sha256"]]
            scope.add_local_snapshots(evidence, self.data / "source", snapshot_shas=snapshot_shas)
            list_a = "LOCAL:SYNTH-A"
        query = episode_spec(schema_version="1.2", hypothesis_kind="LIST_CONTRAST" if list_only else "MIXED_LIST_NUMERIC",
            research_scope={}, list_condition={"clauses": [{"all_of": [list_a]}]},
            features=[] if list_only else [{"name": "d_holders", "op": "delta", "field_id": HOLD, "start": "E300", "end": "E1800"}],
            all=[] if list_only else [{"feature": "d_holders", "op": "gt", "value": 0}])
        query = scope.canonicalize_query_scope(query, evidence)
        spec = yaml.safe_load((ROOT / "configs/experiment_specs/ordinary_price_path_buy_pressure_v1.yaml").read_text(encoding="utf-8"))
        self.experiment_id = "EXP-CONTINUITY-SYNTH-001"
        self.hypothesis = "HYP-CONTINUITY-SYNTH-V1"
        spec.update(experiment_id=self.experiment_id, hypothesis_version=self.hypothesis, population="OPPORTUNITY_EPISODES",
                    question="Engineering continuity of a synthetic episode, without alpha claims",
                    estimand="Synthetic offline decision and execution continuity only",
                    parameters={"episode_query": query, "membership_snapshot_shas": snapshot_shas})
        self.spec_rel = "configs/experiment_specs/continuity_synth.yaml"
        spec_path = self.root / self.spec_rel
        spec_path.parent.mkdir(parents=True, exist_ok=True)
        spec_path.write_text(yaml.safe_dump(spec, allow_unicode=True, sort_keys=False), encoding="utf-8")
        raw_sha = hashlib.sha256(spec_path.read_bytes()).hexdigest()
        # The real scientific owner requires a Git producer identity. A fixture
        # must own that identity rather than discover the host checkout's HEAD.
        subprocess.run(["git", "init", "--quiet"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "-c", "core.autocrlf=false", "add", "--", self.spec_rel],
                       cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "-c", "user.name=Synthetic offline fixture",
                        "-c", "user.email=offline-fixture@invalid.example", "-c", "commit.gpgSign=false",
                        "commit", "--quiet", "-m", "Freeze synthetic experiment spec"],
                       cwd=self.root, check=True, capture_output=True)
        run = _event(record_id="RUN-CONTINUITY-SYNTH-001", record_kind="RUN_COMPLETED", entity_id="RUN-CONTINUITY-SYNTH-001",
            run_id="RUN-CONTINUITY-SYNTH-001", hypothesis_version_id=self.hypothesis, transaction_id="RESEARCH-TXN-CONTINUITY-SYNTH-001",
            payload={"experiment_id": self.experiment_id, "run_id": "RUN-CONTINUITY-SYNTH-001", "availability_cutoff": "2026-09-01T00:00:00Z",
                     "first_reliable_available_at": "2026-09-01T00:00:00Z", "observed_n": 24, "robustness": "HOLD_SPLIT", "outcome": "INCONCLUSIVE"})
        ref = {"record_id": run.record_id, "payload_sha256": run.payload_sha256}
        unsigned = {"schema": "smial.execution-evidence-binding", "schema_version": "1.0", "binding_id": "EEB-" + "AB" * 12,
            "experiment_id": self.experiment_id, "experiment_spec_sha256": raw_sha, "population_ref": "OPPORTUNITY_EPISODES",
            "regimes": [{"tested_notional_usd": 30.0, "evidence_class": "DECISION_TIME_QUOTE_PAIR_V1", "population_n": 24,
                         "two_way_n": 18, "entry_only_n": 4, "no_entry_n": 1, "unknown_n": 1,
                         "strategy_fee_bps_assumption": 20, "cost_evidence_refs": [ref]}], "direct_evidence_refs": [ref]}
        binding = {**unsigned, "binding_sha256": scope.sha256_of(unsigned)}
        evidence_event = _event(record_id="EVIDENCE-CONTINUITY-SYNTH-001", record_kind="EVIDENCE_BINDING",
            entity_id="EVIDENCE-CONTINUITY-SYNTH-001", hypothesis_version_id=self.hypothesis,
            transaction_id="RESEARCH-TXN-CONTINUITY-SYNTH-001", payload=_scientific_payload(
                experiment_id=self.experiment_id, execution_evidence_binding=binding))
        research = ResearchStore(self.data / "research-data")
        research.append([run, evidence_event], transaction_id="RESEARCH-TXN-CONTINUITY-SYNTH-001")
        app = FactoryApplication(root=self.root, spec_relative=self.spec_rel, research_data_root=self.data / "research-data")
        locator = LifecycleEntityLocatorV1(self.experiment_id, "GIT", "EXPERIMENT_SPEC")
        detail = app.research_detail(locator)
        class SyntheticClock(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime(2026, 10, 1, tzinfo=UTC)
        with patch("datetime.datetime", SyntheticClock):
            promoted = app.record_research_decision({"entity_id": self.experiment_id, "truth_plane": "GIT", "native_kind": "EXPERIMENT_SPEC",
                "decision_kind": "PROMOTE", "expected_evidence_snapshot_sha256": detail["dossier"]["evidence_snapshot_sha256"],
                "promote_scientific_only": "1", "rationale": "Isolated synthetic engineering fixture; no scientific acceptance."})
        records = tuple(research.iter_committed_records())
        record = next(record for record in records if record.record_id == promoted["decision_result"]["decision_event_id"])
        payload = json.loads(record.payload_json)
        self.manifest = payload["promotion_handoff_manifest"]
        self.binding = payload["execution_evidence_binding"]
        inputs = {"max_age_seconds": 30, "notional_usd": 30.0, "fee_bps": 20, "max_open_positions": 2, "shadow": True}
        materialized = materialize_strategy_candidate(root=self.root, manifest=self.manifest,
            decision_event_id=record.record_id, created_at=self.manifest["decision_effective_at"],
            execution_inputs=inputs, execution_evidence_binding=self.binding)
        self.assertEqual(materialized["disposition"], "RENDERED")
        self.assertFalse(materialized["activation_created"])
        self.strategy_rel = "configs/strategies/continuity_synth.yaml"
        (self.root / self.strategy_rel).write_text(yaml.safe_dump(materialized["candidate"], sort_keys=False), encoding="utf-8")
        self.runner = TradingContinuityRunner(self.root, data_root=self.data, strategy_relative=self.strategy_rel)
        self.assertFalse(self.runner.store_path.exists(), "Definition load is not activation")
        self.epoch = "ACTIVATION-EPOCH-CONTINUITY-PAPER-001"
        # Only the physical owner clock is synthetic; the PROMOTE guard runs unchanged.
        self.runner.activate(epoch_id=self.epoch, mode="PAPER", at=self.manifest["decision_effective_at"])

    def decision(self):
        return self.runner.episode(source_relative="source/observation_schedule_state.sqlite", episode_id=self.admission["episode_id"],
                                   epoch_id=self.epoch, mode="PAPER", as_of="2026-10-05T12:40:00Z")

    def cli(self, command, **fields):
        argv = [sys.executable, "-B", str(ROOT / "scripts/trading_continuity.py"), command,
                "--repository-root", str(self.root), "--data-root", str(self.data), "--strategy", self.strategy_rel]
        for key, value in fields.items():
            argv += ["--" + key.replace("_", "-"), str(value)]
        completed = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stdout.decode("utf-8", errors="replace"))
        return json.loads(completed.stdout)

    def test_O1_ordinary_source_to_single_admission(self):
        self.prepare()
        packet = self.decision()
        self.assertEqual(packet["decision"]["action"], "ENTER", packet["provenance"])
        self.assertEqual(packet["provenance"]["numeric"]["values"]["d_holders"], 6)
        self.assertEqual(len(self.runner.readback()["positions"]), 1)
        self.assertEqual(packet, self.decision() | {"admission": packet["admission"]})

    def test_scientific_producer_requires_own_git_identity(self):
        # Match CI's absence of an ambient parent repository without mocking Git.
        with patch.dict(os.environ, {"GIT_CEILING_DIRECTORIES": str(self.root.parent)}):
            self.prepare()
            own_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.root, text=True).strip()
        research = ResearchStore(self.data / "research-data")
        decision = next(record for record in research.iter_committed_records()
                        if record.record_id == self.manifest["decision_event_id"])
        self.assertEqual(decision.producer_git_sha, own_head)
        committed_spec = subprocess.check_output(["git", "show", "HEAD:" + self.spec_rel], cwd=self.root)
        self.assertEqual(committed_spec, (self.root / self.spec_rel).read_bytes())

    def fixture_policy(self, enabled, *, key="ADMISSION-POLICY"):
        store = PaperPlaneStore(self.runner.store_path)
        try:
            current = show_policy(store, "PAPER")["policy_sha256"]
            return apply_policy(ROOT, store, mode="PAPER",
                candidate_raw={"new_entries_enabled": enabled, "max_total_open_positions": 2},
                expected_current_sha256=current or "0" * 64, idempotency_key=key,
                owner_authorization_phrase="AUTHORIZE PAPER SHADOW TRADING RUNTIME POLICY APPLY",
                reason="SYNTHETIC_ADMISSION_OUTCOME")
        finally:
            store.close()

    def test_ordinary_denied_admission_is_durable_and_idempotent(self):
        self.prepare()
        applied = self.fixture_policy(False)
        packet = None
        try:
            packet = self.decision()
        except PaperPlaneError as error:
            self.assertEqual(str(error), "BLOCK_NEW_ENTRIES_DISABLED")
        reader = PaperPlaneStore(self.runner.store_path, readonly=True)
        try:
            before = reader.execution_events()
            sources = [e for e in before if e["event_type"] == "SOURCE_DECISION_PRODUCED"]
            risks = [e for e in before if e["event_type"] == "PRE_TRADE_RISK_SNAPSHOT"]
            self.assertEqual(len(sources), 1, "ordinary refusal must preserve exact source packet")
            self.assertEqual(sources[0]["payload"]["decision"]["action"], "ENTER")
            self.assertEqual(len(risks), 1)
            self.assertEqual(risks[0]["payload"]["decision"], "BLOCK_NEW_ENTRIES_DISABLED")
            self.assertEqual(risks[0]["payload"]["runtime_policy_sha256"], applied["readback"]["policy_sha256"])
            self.assertEqual(reader.positions(), [])
        finally:
            reader.close()
        self.assertIsNotNone(packet)
        self.assertEqual(packet["admission"]["outcome"], "DENIED")
        self.assertEqual(packet["admission"]["reason_code"], "BLOCK_NEW_ENTRIES_DISABLED")
        self.assertEqual(packet["decision"]["action"], "ENTER")
        replay = self.decision()
        self.assertTrue(replay["admission"]["idempotent"])
        cli_replay = self.cli("episode", source="source/observation_schedule_state.sqlite",
            episode_id=self.admission["episode_id"], epoch=self.epoch, mode="PAPER", as_of="2026-10-05T12:40:00Z")
        self.assertEqual(cli_replay["admission"], replay["admission"])
        store = PaperPlaneStore(self.runner.store_path)
        try:
            with self.assertRaisesRegex(PaperPlaneError, "BLOCK_NEW_ENTRIES_DISABLED"):
                accept_signal_decision(self.root, store, strategy=self.runner.strategy,
                    signal_decision=packet["decision"], known_activation_epochs={self.epoch},
                    mode="PAPER", as_of="2026-10-05T12:40:00Z", skip_fill=True)
        finally:
            store.close()
        reader = PaperPlaneStore(self.runner.store_path, readonly=True)
        try:
            self.assertEqual(reader.execution_events(), before)
            self.assertEqual(reader.positions(), [])
        finally:
            reader.close()

    def test_ordinary_stale_replay_cancellation_survives_new_connection(self):
        self.prepare()
        first = self.decision()
        try:
            self.runner.episode(source_relative="source/observation_schedule_state.sqlite",
                episode_id=self.admission["episode_id"], epoch_id=self.epoch,
                mode="PAPER", as_of="2026-10-05T12:40:31Z")
        except PaperPlaneError as error:
            self.assertEqual(str(error), "SIGNAL_DECISION_STALE")
        reader = PaperPlaneStore(self.runner.store_path, readonly=True)
        try:
            position = reader.get_position(first["admission"]["position_id"])
            self.assertEqual(position["state"], "CANCELLED", "cancel must survive the runner transaction")
            self.assertEqual(position["cancel_reason_code"], "SIGNAL_EXPIRED")
            self.assertEqual(reader.open_risk_count(first["admission"]["bot_instance_id"]), 0)
            events = reader.execution_events()
            self.assertEqual(len([e for e in events if e["event_type"] == "ENTRY_INTENT_CANCELLED"]), 1)
            self.assertEqual(len([e for e in events if e["event_type"] == "SOURCE_DECISION_PRODUCED"]), 1)
        finally:
            reader.close()
        replay = self.runner.episode(source_relative="source/observation_schedule_state.sqlite",
            episode_id=self.admission["episode_id"], epoch_id=self.epoch,
            mode="PAPER", as_of="2026-10-05T12:40:31Z")
        self.assertEqual(replay["admission"]["state"], "CANCELLED")
        reader = PaperPlaneStore(self.runner.store_path, readonly=True)
        try:
            self.assertEqual(reader.execution_events(), events)
        finally:
            reader.close()

    def assert_cancelled_episode_replay(self, cause):
        self.prepare()
        first = self.decision()
        if cause == "PAUSED":
            self.runner.command({"command_type": "PAUSE_NEW_ENTRIES", "idempotency_key": "REPLAY-PAUSE",
                "bot_instance_id": first["admission"]["bot_instance_id"]})
            expected = "ENTRIES_PAUSED"
        else:
            applied = self.fixture_policy(False)
            expected = "NEW_ENTRIES_DISABLED"
        refused = self.decision()
        self.assertEqual(refused["admission"]["outcome"], "DENIED")
        reader = PaperPlaneStore(self.runner.store_path, readonly=True)
        try:
            position = reader.get_position(first["admission"]["position_id"])
            self.assertEqual((position["state"], position["cancel_reason_code"]), ("CANCELLED", expected))
            self.assertEqual(reader.open_risk_count(first["admission"]["bot_instance_id"]), 0)
            events = reader.execution_events()
            self.assertEqual(len([e for e in events if e["event_type"] == "SOURCE_DECISION_PRODUCED"]), 1)
            self.assertEqual(len([e for e in events if e["event_type"] == "ENTRY_INTENT_CANCELLED"]), 1)
            denials = [e for e in events if e["event_type"] == "SIGNAL_ADMISSION_DENIED"]
            self.assertEqual(len(denials), 1)
            if cause == "DISABLED":
                self.assertEqual(denials[0]["payload"]["runtime_policy_sha256"], applied["readback"]["policy_sha256"])
            self.assertFalse(any(e["event_type"] in {"MODELED_ATTEMPT_STARTED", "MODELED_RESULT_ACCEPTED"} for e in events))
        finally:
            reader.close()
        self.assertEqual(self.decision()["admission"]["state"], "CANCELLED")
        reader = PaperPlaneStore(self.runner.store_path, readonly=True)
        try:
            self.assertEqual(reader.execution_events(), events)
        finally:
            reader.close()

    def test_ordinary_paused_replay_cancellation_is_durable(self):
        self.assert_cancelled_episode_replay("PAUSED")

    def test_ordinary_disabled_policy_replay_cancellation_is_durable(self):
        self.assert_cancelled_episode_replay("DISABLED")

    def test_denial_re_evaluates_after_policy_revision_without_erasing_history(self):
        self.prepare()
        self.fixture_policy(False)
        denied = self.decision()
        self.assertEqual(denied["admission"]["outcome"], "DENIED")
        applied = self.fixture_policy(True, key="ADMISSION-ENABLE")
        admitted = self.decision()
        self.assertEqual(admitted["decision"], denied["decision"])
        self.assertEqual(admitted["provenance"], denied["provenance"])
        self.assertEqual(admitted["admission"]["state"], "WATCHED")
        self.decision()
        reader = PaperPlaneStore(self.runner.store_path, readonly=True)
        try:
            events = reader.execution_events()
            self.assertEqual(len([e for e in events if e["event_type"] == "SOURCE_DECISION_PRODUCED"]), 1)
            self.assertEqual(len([e for e in events if e["event_type"] == "SIGNAL_ADMISSION_DENIED"]), 1)
            risks = [e for e in events if e["event_type"] == "PRE_TRADE_RISK_SNAPSHOT"]
            self.assertEqual({e["payload"]["decision"] for e in risks}, {"BLOCK_NEW_ENTRIES_DISABLED", "ALLOW"})
            self.assertEqual(len(risks), 2)
            positions = reader.positions()
            self.assertEqual(len(positions), 1)
            self.assertEqual(positions[0]["runtime_policy_sha256"], applied["readback"]["policy_sha256"])
            self.assertEqual((positions[0]["admitted_entry_notional_usd_dec"], positions[0]["admitted_fee_bps"]), ("30.0", 20))
        finally:
            reader.close()

    def test_ordinary_admission_real_errors_rollback_source_reservation_and_risk(self):
        self.prepare()
        reader = PaperPlaneStore(self.runner.store_path, readonly=True)
        before = reader.execution_events()
        reader.close()
        original = PaperPlaneStore.append_execution_event
        for error in (RuntimeError("INJECTED_ADMISSION_CRASH"), PaperPlaneError("ADMISSION_BINDING_MISSING")):
            def failing(store, **kwargs):
                result = original(store, **kwargs)
                if kwargs["event_type"] == "SIGNAL_DECISION_ACCEPTED":
                    raise error
                return result
            with patch.object(PaperPlaneStore, "append_execution_event", failing):
                with self.assertRaises(type(error)):
                    self.decision()
            reader = PaperPlaneStore(self.runner.store_path, readonly=True)
            try:
                self.assertEqual(reader.execution_events(), before)
                self.assertEqual(reader.positions(), [])
            finally:
                reader.close()
        store = PaperPlaneStore(self.runner.store_path)
        store._conn.execute("CREATE TRIGGER admission_fault BEFORE INSERT ON positions BEGIN SELECT RAISE(ABORT, 'SYNTHETIC_STORAGE_FAULT'); END")
        store.close()
        with self.assertRaises(sqlite3.IntegrityError):
            self.decision()
        reader = PaperPlaneStore(self.runner.store_path, readonly=True)
        try:
            self.assertEqual(reader.execution_events(), before)
            self.assertEqual(reader.positions(), [])
        finally:
            reader.close()
        store = PaperPlaneStore(self.runner.store_path)
        store._conn.execute("DROP TRIGGER admission_fault")
        store.close()
        packet = self.decision()
        reader = PaperPlaneStore(self.runner.store_path, readonly=True)
        try:
            position = reader.positions()[0]
            self.assertEqual(position["signal_decision_id"], packet["decision"]["signal_decision_id"])
            self.assertEqual(position["signal_decision_sha256"], canonical_spec_sha256(packet["decision"]))
            self.assertIsNotNone(position["admitted_fee_bps"])
            self.assertEqual(len([e for e in reader.execution_events() if e["event_type"] == "SOURCE_DECISION_PRODUCED"]), 1)
            self.assertEqual(len([e for e in reader.execution_events() if e["event_type"] == "PRE_TRADE_RISK_SNAPSHOT"]), 1)
        finally:
            reader.close()
        store = PaperPlaneStore(self.runner.store_path)
        store._conn.execute("UPDATE execution_events SET payload_json='{}' WHERE event_id=?", ("SRC-" + packet["decision"]["signal_decision_id"],))
        before = store.execution_events()
        positions = store.positions()
        store.close()
        with self.assertRaisesRegex(PaperPlaneError, "SOURCE_DECISION_CONTENT_CONFLICT"):
            self.decision()
        reader = PaperPlaneStore(self.runner.store_path, readonly=True)
        try:
            self.assertEqual(reader.execution_events(), before)
            self.assertEqual(reader.positions(), positions)
        finally:
            reader.close()

    def test_episode_replay_cannot_cancel_attempting_or_unknown(self):
        self.prepare()
        first = self.decision()
        attempted = self.runner.attempt(position_id=first["admission"]["position_id"], side="ENTRY",
            attempt_key="DENIAL-UNKNOWN", as_of="2026-10-05T12:40:00Z")
        self.fixture_policy(False)
        for expected in ("ATTEMPTING", "UNKNOWN"):
            if expected == "UNKNOWN":
                self.runner.result(self._result(attempted["attempt_id"], "UNKNOWN_REQUIRES_RECONCILIATION", chargeable_cost_usd=None))
            before = self.runner.readback()
            replay = self.runner.episode(source_relative="source/observation_schedule_state.sqlite",
                episode_id=self.admission["episode_id"], epoch_id=self.epoch,
                mode="PAPER", as_of="2026-10-05T12:40:31Z")
            self.assertTrue(replay["admission"]["reconciliation_required"])
            after = self.runner.readback()
            self.assertEqual(after["positions"][0]["state"], expected)
            self.assertEqual(after["positions"], before["positions"])
            self.assertEqual(after["modeled_attempts"], before["modeled_attempts"])
            self.assertEqual(after["modeled_results"], before["modeled_results"])
            self.assertEqual(after["admission_refusals"], [])

    def test_O5_membership_unknown_refuses_before_loader(self):
        self.membership = "UNKNOWN"
        self.prepare()
        packet = self.decision()
        self.assertEqual(packet["decision"]["action"], "UNKNOWN")
        self.assertEqual(packet["provenance"]["read_set"], [])
        self.assertEqual(self.runner.readback()["positions"], [])

    def test_O3_flat_is_not_positive(self):
        self.holders_end = 60
        self.prepare()
        packet = self.decision()
        self.assertEqual(packet["decision"]["action"], "NO_ENTER")
        self.assertEqual(packet["provenance"]["numeric"]["values"]["d_holders"], 0)

    def test_O4_missing_holder_is_not_zero(self):
        self.holders_start = None
        self.prepare()
        packet = self.decision()
        self.assertEqual(packet["decision"]["action"], "UNKNOWN")
        self.assertIsNone(packet["provenance"]["numeric"]["values"]["d_holders"])

    def test_O6_late_input_does_not_heal(self):
        self.late = True
        self.prepare()
        packet = self.decision()
        self.assertEqual(packet["decision"]["action"], "UNKNOWN")
        self.assertEqual(self.decision()["decision"], packet["decision"])
        self.assertEqual(self.runner.readback()["positions"], [])

    def test_list_only_uses_same_source_owner(self):
        self.holders_start = None
        self.prepare(list_only=True)
        packet = self.decision()
        self.assertEqual(packet["decision"]["action"], "ENTER")
        self.assertEqual([(row["point_id"], row["field_id"]) for row in packet["provenance"]["read_set"]],
                         [("E1800", "FIELD-USD-PRICE-001")])
        pid = packet["admission"]["position_id"]
        attempt = self.runner.attempt(position_id=pid, side="ENTRY", attempt_key="LIST-ENTRY", as_of="2026-10-05T12:40:00Z")
        self.runner.result(self._result(attempt["attempt_id"], "LANDED_SUCCESS", unit_price_usd="0.000003", filled_notional_usd="30", chargeable_cost_usd="0"))
        self.source.tick(datetime(2026, 10, 5, 16, 5, tzinfo=UTC))
        self.runner.exit(position_id=pid, source_relative="source/observation_schedule_state.sqlite", as_of="2026-10-05T16:10:00Z")
        exit_attempt = self.runner.attempt(position_id=pid, side="EXIT", attempt_key="LIST-EXIT", as_of="2026-10-05T16:10:00Z")
        self.runner.result({"attempt_id": exit_attempt["attempt_id"], "result_id": "LIST-EXIT", "outcome": "LANDED_SUCCESS", "observed_at": "2026-10-05T16:10:01Z", "unit_price_usd": "0.0000033", "chargeable_cost_usd": "0"})
        self.assertEqual(self.runner.readback()["positions"][0]["realized_net_pnl_usd_dec"], "2.87")

    def test_missing_decision_price_refuses_list_only(self):
        self.decision_price = None
        self.prepare(list_only=True)
        packet = self.decision()
        self.assertEqual(packet["decision"]["action"], "UNKNOWN")
        self.assertTrue(packet["decision"]["reason_code"].startswith("EPISODE_DECISION_PRICE_"))
        self.assertEqual(packet["provenance"]["numeric"]["values"], {})
        self.assertEqual(self.runner.readback()["positions"], [])

    def test_missing_decision_price_refuses_positive_holder_delta(self):
        self.decision_price = None
        self.prepare()
        packet = self.decision()
        self.assertEqual(packet["decision"]["action"], "UNKNOWN")
        self.assertTrue(packet["decision"]["reason_code"].startswith("EPISODE_DECISION_PRICE_"))
        self.assertEqual([(row["point_id"], row["field_id"]) for row in packet["provenance"]["read_set"]],
                         [("E1800", "FIELD-USD-PRICE-001")])
        self.assertEqual(self.runner.readback()["positions"], [])

    def test_late_decision_price_refuses_list_only_without_future_healing(self):
        self.late = True
        self.prepare(list_only=True)
        packet = self.decision()
        self.assertEqual(packet["decision"]["action"], "UNKNOWN")
        self.assertTrue(packet["decision"]["reason_code"].startswith("EPISODE_DECISION_PRICE_"))
        self.source.tick(datetime(2026, 10, 5, 16, 5, tzinfo=UTC))
        self.assertEqual(self.decision()["decision"], packet["decision"])
        self.assertEqual(self.runner.readback()["positions"], [])

    def test_O7_O8_restart_and_future_do_not_change_decision(self):
        self.prepare()
        before = self.decision()
        self.future_price = 123.456
        self.source.tick(datetime(2026, 10, 5, 16, 5, tzinfo=UTC))
        self.runner = TradingContinuityRunner(self.root, data_root=self.data, strategy_relative=self.strategy_rel)
        after = self.decision()
        self.assertEqual(after["decision"], before["decision"])
        self.assertEqual(after["provenance"], before["provenance"])
        self.assertEqual({row["point_id"] for row in after["provenance"]["read_set"]}, {"E300", "E1800"})
        self.assertEqual(len(self.runner.readback()["positions"]), 1)

    def _attempt(self):
        packet = self.decision()
        pid = packet["admission"]["position_id"]
        attempted = self.runner.attempt(position_id=pid, side="ENTRY", attempt_key="ENTRY-1", as_of="2026-10-05T12:40:00Z")
        self.assertTrue(attempted["send_permitted"])
        return pid, attempted["attempt_id"]

    def _result(self, attempt_id, outcome, *, result_id="ENTRY-RESULT-1", **fields):
        return {"attempt_id": attempt_id, "result_id": result_id, "outcome": outcome,
                "observed_at": "2026-10-05T12:40:01Z", **fields}

    def test_ordinary_full_chain_decimal_oracle(self):
        self.prepare()
        packet = self.cli("episode", episode_id=self.admission["episode_id"], epoch=self.epoch, as_of="2026-10-05T12:40:00Z")
        pid = packet["admission"]["position_id"]
        attempt = self.cli("attempt", position_id=pid, side="ENTRY", attempt_key="ENTRY-1", as_of="2026-10-05T12:40:00Z")["attempt_id"]
        entry = self._result(attempt, "LANDED_SUCCESS", unit_price_usd="0.000003", filled_notional_usd="30", chargeable_cost_usd="0")
        (self.data / "result.json").write_text(json.dumps(entry), encoding="utf-8")
        opened = self.cli("result", input="result.json")["position"]
        self.assertEqual(opened["qty_dec"], "10000000.00000000")
        self.assertEqual(opened["entry_fee_usd_dec"], "0.06")
        self.source.tick(datetime(2026, 10, 5, 16, 5, tzinfo=UTC))
        exit_packet = self.cli("exit", position_id=pid, as_of="2026-10-05T16:10:00Z")
        self.assertEqual(exit_packet["decision"]["action"], "EXIT")
        exit_attempt = self.cli("attempt", position_id=pid, side="EXIT", attempt_key="EXIT-1", as_of="2026-10-05T16:10:00Z")
        exit_result = {"attempt_id": exit_attempt["attempt_id"], "result_id": "EXIT-RESULT-1", "outcome": "LANDED_SUCCESS",
                       "observed_at": "2026-10-05T16:10:01Z", "unit_price_usd": "0.0000033", "chargeable_cost_usd": "0"}
        (self.data / "result.json").write_text(json.dumps(exit_result), encoding="utf-8")
        reconciled = self.cli("result", input="result.json")["position"]
        self.assertEqual(reconciled["state"], "RECONCILED")
        self.assertEqual(reconciled["exit_fee_usd_dec"], "0.07")
        self.assertEqual(reconciled["realized_gross_pnl_usd_dec"], "3.00")
        self.assertEqual(reconciled["realized_net_pnl_usd_dec"], "2.87")
        before = self.cli("readback")
        self.assertTrue(self.runner.result(exit_result)["idempotent"])
        self.assertEqual({key: value for key, value in self.runner.readback().items() if key != "as_of"},
                         {key: value for key, value in before.items() if key != "as_of"})
        self.assertEqual(len(before["modeled_attempts"]), 2)
        self.assertEqual(len(before["modeled_results"]), 2)
        self.assertEqual(before["modeled_net_after_additional_costs_usd"], "2.87")

    def test_unknown_then_delayed_result_is_one_effect_after_restart(self):
        self.prepare()
        pid, attempt = self._attempt()
        unknown = self._result(attempt, "UNKNOWN_REQUIRES_RECONCILIATION")
        self.assertEqual(self.runner.result(unknown)["position"]["state"], "UNKNOWN")
        self.runner = TradingContinuityRunner(self.root, data_root=self.data, strategy_relative=self.strategy_rel)
        retry = self.runner.attempt(position_id=pid, side="ENTRY", attempt_key="ENTRY-1", as_of="2026-10-05T12:40:02Z")
        self.assertFalse(retry["send_permitted"])
        final = self._result(attempt, "LANDED_SUCCESS", result_id="DELAYED-RESULT", unit_price_usd="0.000003", filled_notional_usd="30", chargeable_cost_usd="0")
        self.assertEqual(self.runner.result(final)["position"]["state"], "OPEN")
        self.assertTrue(self.runner.result(final)["idempotent"])
        with self.assertRaisesRegex(PaperPlaneError, "MODELED_RESULT_CONTENT_CONFLICT"):
            self.runner.result({**final, "unit_price_usd": "0.000004"})
        self.assertEqual(len(self.runner.readback()["modeled_attempts"]), 1)

    def test_definitive_failed_result_preserves_cost_and_no_inventory(self):
        self.prepare()
        _pid, attempt = self._attempt()
        failed = self._result(attempt, "LANDED_FAILED", chargeable_cost_usd="0.01")
        accepted = self.runner.result(failed)
        self.assertEqual(accepted["position"]["state"], "CANCELLED")
        self.assertIsNone(accepted["position"]["qty_dec"])
        self.assertIsNone(accepted["position"]["realized_net_pnl_usd_dec"])
        self.assertEqual(self.runner.readback()["modeled_results"][0]["payload"]["result"]["chargeable_cost_usd"], "0.01")
        self.assertEqual(self.runner.readback()["modeled_net_after_additional_costs_usd"], "-0.01")
        self.assertIsNone(self.runner.readback()["reconciled_net_pnl_usd"])

    def test_nonfill_classes_unknown_cost_and_invalid_amounts(self):
        self.prepare()
        for index, outcome in enumerate(("NO_ROUTE", "REJECTED_BEFORE_SEND", "DROPPED_OR_EXPIRED_NOT_PROCESSED")):
            epoch = f"ACTIVATION-EPOCH-NONFILL-{index}"
            self.runner.activate(epoch_id=epoch, mode="PAPER", at=self.manifest["decision_effective_at"])
            packet = self.runner.episode(source_relative="source/observation_schedule_state.sqlite",
                episode_id=self.admission["episode_id"], epoch_id=epoch, mode="PAPER", as_of="2026-10-05T12:40:00Z")
            pid = packet["admission"]["position_id"]
            attempt = self.runner.attempt(position_id=pid, side="ENTRY", attempt_key="ONE", as_of="2026-10-05T12:40:00Z")
            result = self._result(attempt["attempt_id"], outcome, result_id=f"NEGATIVE-{index}")
            position = self.runner.result(result)["position"]
            self.assertEqual(position["state"], "CANCELLED")
            self.assertIsNone(position["qty_dec"])
            self.assertTrue(self.runner.result(result)["idempotent"])
        view = self.runner.readback()
        self.assertIsNone(view["modeled_net_after_additional_costs_usd"])
        self.assertEqual(len(view["modeled_attempts"]), 3)
        pid, attempt = self._attempt()
        for value in ("NaN", "Infinity", "0", "-1"):
            with self.assertRaises(PaperPlaneError):
                self.runner.result(self._result(attempt, "LANDED_SUCCESS", unit_price_usd=value, filled_notional_usd="30"))
        self.assertEqual(next(p for p in self.runner.readback()["positions"] if p["position_id"] == pid)["state"], "ATTEMPTING")

    def test_shadow_ordinary_boundary_is_separate_from_paper_and_quote_only(self):
        self.prepare()
        paper = self.decision()
        epoch = "ACTIVATION-EPOCH-CONTINUITY-SHADOW-001"
        self.runner.activate(epoch_id=epoch, mode="SHADOW", at=self.manifest["decision_effective_at"])
        packet = self.runner.episode(source_relative="source/observation_schedule_state.sqlite",
            episode_id=self.admission["episode_id"], epoch_id=epoch, mode="SHADOW", as_of="2026-10-05T12:40:00Z")
        self.assertNotEqual(packet["decision"]["signal_decision_id"], paper["decision"]["signal_decision_id"])
        attempt = self.runner.attempt(position_id=packet["admission"]["position_id"], side="ENTRY", attempt_key="SHADOW-1", as_of="2026-10-05T12:40:00Z")
        self.runner.result(self._result(attempt["attempt_id"], "LANDED_SUCCESS", unit_price_usd="0.000003", filled_notional_usd="30", chargeable_cost_usd="0"))
        pid = packet["admission"]["position_id"]
        self.source.tick(datetime(2026, 10, 5, 16, 5, tzinfo=UTC))
        self.runner.exit(position_id=pid, source_relative="source/observation_schedule_state.sqlite", as_of="2026-10-05T16:10:00Z")
        exit_attempt = self.runner.attempt(position_id=pid, side="EXIT", attempt_key="SHADOW-EXIT", as_of="2026-10-05T16:10:00Z")
        self.runner.result({"attempt_id": exit_attempt["attempt_id"], "result_id": "SHADOW-EXIT", "outcome": "LANDED_SUCCESS", "observed_at": "2026-10-05T16:10:01Z", "unit_price_usd": "0.0000033", "chargeable_cost_usd": "0"})
        view = self.runner.readback()
        self.assertEqual(len(view["positions"]), 2)
        self.assertEqual(view["modeled_attempts"][0]["payload"]["evidence_class"], "SHADOW_QUOTE_MODEL")
        self.assertEqual(view["aggregation_status"], "MIXED_SCOPE")
        self.assertIsNone(view["modeled_net_after_additional_costs_usd"])
        self.assertEqual(next(p for p in view["positions"] if p["position_id"] == pid)["realized_net_pnl_usd_dec"], "2.87")

    def test_native_corrupt_and_missing_store_readback_is_typed_no_bootstrap(self):
        self.prepare()
        path = self.runner.store_path
        original = path.read_bytes()
        for broken in (None, b"native corrupt sqlite bytes"):
            if path.exists():
                path.unlink()
            if broken is not None:
                path.write_bytes(broken)
            completed = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/trading_continuity.py"), "readback",
                "--repository-root", str(self.root), "--data-root", str(self.data), "--strategy", self.strategy_rel],
                cwd=ROOT, capture_output=True, timeout=30)
            self.assertEqual(completed.returncode, 2)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "BLOCKED")
            self.assertEqual(payload["reason_code"], "SOURCE_NOT_PRESENT" if broken is None else "OFFLINE_DATABASE_CORRUPT")
            self.assertIn("next_safe_action", payload)
            self.assertEqual(path.exists(), broken is not None)
            if broken is not None:
                self.assertEqual(path.read_bytes(), broken)
        path.write_bytes(original)

    def test_frozen_spec_tamper_and_activation_conflict_cannot_rebind_position(self):
        self.prepare()
        before = self.decision()
        with self.assertRaisesRegex(PaperPlaneError, "ACTIVATION_BINDING_CONFLICT"):
            self.runner.activate(epoch_id=self.epoch, mode="SHADOW", at=self.manifest["decision_effective_at"])
        path = self.root / self.spec_rel
        path.write_bytes(path.read_bytes() + b"\n# bytes changed after PROMOTE\n")
        with self.assertRaises(ValueError):
            TradingContinuityRunner(self.root, data_root=self.data, strategy_relative=self.strategy_rel)
        self.assertEqual(self.runner.readback()["positions"][0]["position_id"], before["admission"]["position_id"])

    def test_store_hardlink_canary_refused_before_writable_effect(self):
        self.prepare()
        canary = self.root / "outside-root-canary.sqlite"
        os.link(self.runner.store_path, canary)
        before = hashlib.sha256(canary.read_bytes()).hexdigest()
        try:
            with self.assertRaisesRegex(PaperPlaneError, "OFFLINE_STORE_ALIAS_FORBIDDEN"):
                self.runner.activate(epoch_id="ACTIVATION-EPOCH-CANARY", mode="PAPER", at=self.manifest["decision_effective_at"])
            self.assertEqual(hashlib.sha256(canary.read_bytes()).hexdigest(), before)
        finally:
            canary.unlink()

    def test_source_publication_preserves_first_visibility_and_replay(self):
        self.prepare(defer_publication=True)
        before = self.decision()
        self.assertGreater(self.source.unpublished(), 0)
        self.source.tick(datetime(2026, 10, 5, 12, 41, tzinfo=UTC))
        self.assertEqual(self.source.unpublished(), 0)
        after = TradingContinuityRunner(self.root, data_root=self.data, strategy_relative=self.strategy_rel).episode(
            source_relative="source/observation_schedule_state.sqlite", episode_id=self.admission["episode_id"],
            epoch_id=self.epoch, mode="PAPER", as_of="2026-10-05T12:40:00Z")
        self.assertEqual(after["provenance"], before["provenance"])
        self.assertTrue(all(r["ingested_visible_at_floor"] is not None for r in after["provenance"]["read_set"]))

    def test_unknown_close_delayed_positive_preserves_close_and_negative_clears(self):
        self.prepare()
        pid, attempt = self._attempt()
        self.runner.result(self._result(attempt, "UNKNOWN_REQUIRES_RECONCILIATION"))
        self.runner.command({"command_type": "REQUEST_CLOSE_POSITION", "idempotency_key": "CLOSE-UNKNOWN", "position_id": pid})
        with self.assertRaisesRegex(PaperPlaneError, "EXIT_ATTEMPT_REQUIRES_ENTRY_RECONCILIATION"):
            self.runner.attempt(position_id=pid, side="EXIT", attempt_key="NO-PREMATURE-EXIT", as_of="2026-10-05T12:40:03Z")
        positive = self._result(attempt, "LANDED_SUCCESS", result_id="LATE-KNOWN", unit_price_usd="0.000003", filled_notional_usd="30", chargeable_cost_usd="0")
        position = self.runner.result(positive)["position"]
        self.assertEqual(position["state"], "EXIT_REQUIRED")
        self.assertEqual(position["qty_dec"], "10000000.00000000")
        with self.assertRaisesRegex(PaperPlaneError, "MODELED_ATTEMPT_CAUSAL_CLOCK_INVALID"):
            self.runner.attempt(position_id=pid, side="EXIT", attempt_key="BEFORE-ENTRY", as_of="2026-10-05T12:39:00Z")
        self.assertTrue(self.runner.attempt(position_id=pid, side="EXIT", attempt_key="AFTER-ENTRY", as_of="2026-10-05T12:40:02Z")["send_permitted"])
        epoch = "ACTIVATION-EPOCH-LATE-NEGATIVE"
        self.runner.activate(epoch_id=epoch, mode="PAPER", at=self.manifest["decision_effective_at"])
        packet = self.runner.episode(source_relative="source/observation_schedule_state.sqlite", episode_id=self.admission["episode_id"], epoch_id=epoch, mode="PAPER", as_of="2026-10-05T12:40:00Z")
        pid2 = packet["admission"]["position_id"]
        attempt2 = self.runner.attempt(position_id=pid2, side="ENTRY", attempt_key="ONE", as_of="2026-10-05T12:40:00Z")["attempt_id"]
        self.runner.result(self._result(attempt2, "UNKNOWN_REQUIRES_RECONCILIATION", result_id="UNKNOWN-2"))
        self.runner.command({"command_type": "REQUEST_CLOSE_POSITION", "idempotency_key": "CLOSE-UNKNOWN-2", "position_id": pid2})
        negative = self._result(attempt2, "DROPPED_OR_EXPIRED_NOT_PROCESSED", result_id="FINAL-NEGATIVE", chargeable_cost_usd="0")
        self.assertEqual(self.runner.result(negative)["position"]["state"], "CANCELLED")
        self.assertEqual(len(self.runner.readback()["modeled_attempts"]), 3)

    def test_origin_packet_corruption_and_missing_research_refuse_without_effect(self):
        self.prepare()
        packet = self.decision()
        store = PaperPlaneStore(self.runner.store_path)
        try:
            sid = "SRC-" + packet["decision"]["signal_decision_id"]
            stored = store.get_execution_event(sid)["payload"]
            stored["provenance"]["decision_cutoff"] = "2026-10-05T12:41:00Z"
            store._conn.execute("UPDATE execution_events SET payload_json=? WHERE event_id=?", (json.dumps(stored), sid))
            store._conn.commit()
        finally:
            store.close()
        with self.assertRaisesRegex(PaperPlaneError, "SOURCE_DECISION_PROVENANCE_CONFLICT"):
            self.runner.attempt(position_id=packet["admission"]["position_id"], side="ENTRY", attempt_key="CORRUPT", as_of="2026-10-05T12:40:00Z")
        self.assertEqual(self.runner.readback()["modeled_attempts"], [])
        research = self.data / "research-data"
        backup = self.data / "research-removed"
        research.rename(backup)
        completed = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/trading_continuity.py"), "load",
            "--repository-root", str(self.root), "--data-root", str(self.data), "--strategy", self.strategy_rel], cwd=ROOT, capture_output=True, timeout=30)
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(json.loads(completed.stdout)["status"], "BLOCKED")
        self.assertFalse(research.exists())

    def test_mixed_stream_pause_resume_policy_revision_route_loss_restart_conservation(self):
        self.prepare()
        packet = self.decision()
        self.decision()
        bot_id, pid = packet["admission"]["bot_instance_id"], packet["admission"]["position_id"]
        for command_type, key in (("PAUSE_NEW_ENTRIES", "STREAM-PAUSE"), ("RESUME_NEW_ENTRIES", "STREAM-RESUME")):
            command = {"command_type": command_type, "idempotency_key": key, "bot_instance_id": bot_id}
            self.runner.command(command)
            self.runner.command(command)
        store = PaperPlaneStore(self.runner.store_path)
        try:
            apply_policy(ROOT, store, mode="PAPER", candidate_raw={"new_entries_enabled": True,
                "global_entry_notional_cap_usd": "15", "max_total_open_positions": 2}, expected_current_sha256="0" * 64,
                idempotency_key="STREAM-POLICY", owner_authorization_phrase="AUTHORIZE PAPER SHADOW TRADING RUNTIME POLICY APPLY", reason="SYNTHETIC_STREAM")
        finally:
            store.close()
        self.runner = TradingContinuityRunner(self.root, data_root=self.data, strategy_relative=self.strategy_rel)
        attempted = self.runner.attempt(position_id=pid, side="ENTRY", attempt_key="STREAM-ENTRY", as_of="2026-10-05T12:40:00Z")
        self.runner.result(self._result(attempted["attempt_id"], "LANDED_SUCCESS", unit_price_usd="0.000003", filled_notional_usd="30", chargeable_cost_usd="0"))
        # Revision cannot resize an already frozen admission.
        self.assertEqual(self.runner.readback()["positions"][0]["entered_notional_usd_dec"], "30")
        self.runner.command({"command_type": "REQUEST_CLOSE_POSITION", "idempotency_key": "STREAM-CLOSE", "position_id": pid})
        exit1 = self.runner.attempt(position_id=pid, side="EXIT", attempt_key="STREAM-NO-ROUTE", as_of="2026-10-05T12:40:02Z")
        self.runner.result({"attempt_id": exit1["attempt_id"], "result_id": "STREAM-NO-ROUTE", "outcome": "NO_ROUTE", "observed_at": "2026-10-05T12:40:03Z", "chargeable_cost_usd": "0"})
        self.runner = TradingContinuityRunner(self.root, data_root=self.data, strategy_relative=self.strategy_rel)
        exit2 = self.runner.attempt(position_id=pid, side="EXIT", attempt_key="STREAM-RECOVERY", as_of="2026-10-05T12:40:04Z")
        self.runner.result({"attempt_id": exit2["attempt_id"], "result_id": "STREAM-FINAL", "outcome": "LANDED_SUCCESS", "observed_at": "2026-10-05T12:40:05Z", "unit_price_usd": "0.0000033", "chargeable_cost_usd": "0"})
        view = self.runner.readback()
        self.assertEqual(len(view["positions"]), 1)
        self.assertEqual(view["positions"][0]["state"], "RECONCILED")
        self.assertEqual(len(view["modeled_attempts"]), 3)
        self.assertEqual(len(view["modeled_results"]), 3)
        identities = {r["event_id"] for r in view["modeled_attempts"]}
        self.assertEqual(len(identities), 3)
        self.assertTrue(all(r["payload"]["result"]["attempt_id"] in identities and r["position_id"] == pid for r in view["modeled_results"]))

    def test_pause_between_admission_and_attempt_cancels(self):
        self.prepare()
        packet = self.decision()
        pid = packet["admission"]["position_id"]
        self.runner.command({"command_type": "PAUSE_NEW_ENTRIES", "idempotency_key": "PAUSE-BEFORE-ATTEMPT",
                             "bot_instance_id": packet["admission"]["bot_instance_id"]})
        refused = self.runner.attempt(position_id=pid, side="ENTRY", attempt_key="ENTRY-1", as_of="2026-10-05T12:40:01Z")
        self.assertFalse(refused["send_permitted"])
        self.assertEqual(self.runner.readback()["positions"][0]["state"], "CANCELLED")
        self.assertEqual(self.runner.readback()["modeled_attempts"], [])

    def test_version_V2_handoff_boundary_is_explicit_and_V1_exit_survives_list_removal(self):
        self.prepare()
        pid, attempt = self._attempt()
        self.runner.result(self._result(attempt, "LANDED_SUCCESS", unit_price_usd="0.000003", filled_notional_usd="30", chargeable_cost_usd="0"))
        # Deliberately invalid candidate: never accept/activate it or bypass VERIFY.
        candidate = dict(self.runner.strategy)
        candidate["strategy_version"] = "V2"
        candidate["spec_sha256"] = canonical_spec_sha256({k: v for k, v in candidate.items() if k != "spec_sha256"})
        with self.assertRaisesRegex(PromotionHandoffError, "HANDOFF_MANIFEST_INVALID"):
            verify_strategy_version(self.root, candidate, manifest=self.manifest,
                decision_event_id=self.manifest["decision_event_id"], execution_evidence_binding=self.binding)
        # Membership disappears in a later real nomination; historical T0 stays frozen.
        later = datetime(2026, 10, 5, 16, 5, tzinfo=UTC)
        nominate(self.source.market, later, {"toptraded": [], "toptrending": []})
        self.source.tick(later)
        exited = self.runner.exit(position_id=pid, source_relative="source/observation_schedule_state.sqlite", as_of="2026-10-05T16:10:00Z")
        self.assertEqual(exited["decision"]["action"], "EXIT")
        self.assertEqual(exited["decision"]["strategy_version"], "V1")
        attempted = self.runner.attempt(position_id=pid, side="EXIT", attempt_key="ORIGIN-EXIT", as_of="2026-10-05T16:10:00Z")
        self.runner.result({"attempt_id": attempted["attempt_id"], "result_id": "ORIGIN-EXIT-FINAL", "outcome": "LANDED_SUCCESS",
            "observed_at": "2026-10-05T16:10:01Z", "unit_price_usd": "0.0000033", "chargeable_cost_usd": "0"})
        view = self.runner.readback()
        self.assertEqual({p["strategy_version_label"] for p in view["positions"]}, {"V1"})
        self.assertEqual(view["positions"][0]["state"], "RECONCILED")
        self.assertEqual(len(view["bots"]), 1)

    def test_after_commit_exit_result_replay_finishes_drain_once(self):
        self.prepare()
        pid, attempt = self._attempt()
        self.runner.result(self._result(attempt, "LANDED_SUCCESS", unit_price_usd="0.000003", filled_notional_usd="30", chargeable_cost_usd="0"))
        bot_id = self.runner.readback()["positions"][0]["bot_instance_id"]
        self.runner.command({"command_type": "STOP_BOT", "idempotency_key": "POST-COMMIT-STOP", "bot_instance_id": bot_id})
        self.runner.command({"command_type": "REQUEST_CLOSE_POSITION", "idempotency_key": "POST-COMMIT-CLOSE", "position_id": pid})
        exited = self.runner.attempt(position_id=pid, side="EXIT", attempt_key="POST-COMMIT-EXIT", as_of="2026-10-05T12:40:02Z")
        result = {"attempt_id": exited["attempt_id"], "result_id": "POST-COMMIT-FINAL", "outcome": "LANDED_SUCCESS",
            "observed_at": "2026-10-05T12:40:03Z", "unit_price_usd": "0.0000033", "chargeable_cost_usd": "0"}
        with patch("solana_alpha_lab.factory.trading_runner.maybe_finish_drain", side_effect=RuntimeError("AFTER_RESULT_COMMIT")):
            with self.assertRaisesRegex(RuntimeError, "AFTER_RESULT_COMMIT"):
                self.runner.result(result)
        self.runner = TradingContinuityRunner(self.root, data_root=self.data, strategy_relative=self.strategy_rel)
        before = self.runner.readback()
        self.assertEqual(before["positions"][0]["state"], "RECONCILED")
        self.assertEqual(before["bots"][0]["status"], "DRAINING")
        self.assertEqual(self.runner.result(result)["drain"]["bot_status"], "STOPPED")
        after = self.runner.readback()
        self.assertEqual(after["positions"], before["positions"])
        self.assertEqual(after["modeled_results"], before["modeled_results"])
        self.assertEqual(len(after["modeled_results"]), 2)

    def test_independent_source_action_admission_terminal_sets(self):
        self.prepare()
        first = self.decision()
        expected = {self.admission["episode_id"]: "ENTER"}
        packets = [first]
        expected_denied = {}
        for index, action in ((1, "NO_ENTER"), (2, "UNKNOWN"), (3, "ENTER")):
            start = self.start + timedelta(days=7 * index)
            name = "stream-source-" + str(index)
            source = EpisodeScenario(self.data / name, start=start, stops=start + timedelta(minutes=1))
            obj = token_object(self.mint, price=0.000003, liquidity=10000, holders=60)
            nominate(source.market, start, {"toptraded": [obj], "toptrending": [] if action == "NO_ENTER" else [obj]})
            source.market.series[self.mint] = lambda now: token_object(self.mint, price=0.000003,
                liquidity=10000, holders=(66 if now.minute >= 35 else 60) if action == "ENTER" else None)
            source.tick(start)
            admission = source.admissions()[0]
            source.tick(start.replace(minute=10, second=0))
            source.tick(start.replace(minute=35, second=0))
            expected[admission["episode_id"]] = action
            args = dict(source_relative=name + "/observation_schedule_state.sqlite", episode_id=admission["episode_id"],
                epoch_id=self.epoch, mode="PAPER", as_of=start.replace(minute=40, second=0).strftime("%Y-%m-%dT%H:%M:%SZ"))
            if action == "ENTER":
                self.fixture_policy(False, key="DENOMINATOR-DISABLE")
                expected_denied[admission["episode_id"]] = "BLOCK_NEW_ENTRIES_DISABLED"
            packets.append(self.runner.episode(**args))
            self.runner.episode(**args)
        self.assertEqual({p["provenance"]["logical_key"]["episode_id"]: p["decision"]["action"] for p in packets}, expected)
        self.fixture_policy(True, key="DENOMINATOR-ENABLE")
        pid = first["admission"]["position_id"]
        attempted = self.runner.attempt(position_id=pid, side="ENTRY", attempt_key="SET-ENTRY", as_of="2026-10-05T12:40:00Z")
        self.runner.result(self._result(attempted["attempt_id"], "LANDED_SUCCESS", unit_price_usd="0.000003", filled_notional_usd="30", chargeable_cost_usd="0"))
        self.runner.command({"command_type": "REQUEST_CLOSE_POSITION", "idempotency_key": "SET-CLOSE", "position_id": pid})
        exited = self.runner.attempt(position_id=pid, side="EXIT", attempt_key="SET-EXIT", as_of="2026-10-05T12:40:02Z")
        self.runner.result({"attempt_id": exited["attempt_id"], "result_id": "SET-FINAL", "outcome": "LANDED_SUCCESS",
            "observed_at": "2026-10-05T12:40:03Z", "unit_price_usd": "0.0000033", "chargeable_cost_usd": "0"})
        reader = PaperPlaneStore(self.runner.store_path, readonly=True)
        try:
            sources = [e for e in reader.execution_events() if e["event_type"] == "SOURCE_DECISION_PRODUCED"]
            actual = {e["payload"]["provenance"]["logical_key"]["episode_id"]: e["payload"]["decision"]["action"] for e in sources}
            self.assertEqual(actual, expected)
            self.assertEqual(len(sources), len(expected))
            signals = {e["payload"]["decision"]["signal_decision_id"]: e["payload"]["provenance"]["logical_key"]["episode_id"] for e in sources}
            positions = reader.positions()
            admitted = {signals[p["signal_decision_id"]] for p in positions}
            terminal = {signals[p["signal_decision_id"]] for p in positions if p["state"] == "RECONCILED"}
            source_enters = {episode for episode, action in expected.items() if action == "ENTER"}
            denials = [e for e in reader.execution_events() if e["event_type"] == "SIGNAL_ADMISSION_DENIED"]
            actual_denied = {signals[e["payload"]["signal_decision_id"]]: e["payload"]["reason_code"] for e in denials}
            self.assertEqual(actual_denied, expected_denied)
            self.assertEqual(len(denials), 1)
            self.assertEqual(admitted, {self.admission["episode_id"]})
            self.assertLess(admitted, source_enters)
            self.assertEqual(source_enters - admitted, set(expected_denied))
            self.assertEqual(terminal, {self.admission["episode_id"]})
            self.assertEqual(len(positions), 1)
            attempts = [e for e in reader.execution_events() if e["event_type"] == "MODELED_ATTEMPT_STARTED"]
            results = [e for e in reader.execution_events() if e["event_type"] == "MODELED_RESULT_ACCEPTED"]
            self.assertEqual(len(attempts), 2)
            self.assertEqual(len(results), 2)
            self.assertEqual({e["position_id"] for e in attempts + results}, {pid})
        finally:
            reader.close()

    def test_half_cent_tie_is_literal_HALF_UP_in_ordinary_exit(self):
        self.prepare()
        pid, attempted = self._attempt()
        self.runner.result(self._result(attempted, "LANDED_SUCCESS", unit_price_usd="0.000003", filled_notional_usd="30", chargeable_cost_usd="0"))
        self.runner.command({"command_type": "REQUEST_CLOSE_POSITION", "idempotency_key": "TIE-CLOSE", "position_id": pid})
        exited = self.runner.attempt(position_id=pid, side="EXIT", attempt_key="TIE-EXIT", as_of="2026-10-05T12:40:02Z")
        position = self.runner.result({"attempt_id": exited["attempt_id"], "result_id": "TIE-FINAL", "outcome": "LANDED_SUCCESS",
            "observed_at": "2026-10-05T12:40:03Z", "unit_price_usd": "0.00000325", "chargeable_cost_usd": "0"})["position"]
        # 10,000,000 * .00000325 = 32.50; * .002 = .065, HALF_UP -> .07.
        self.assertEqual(position["exit_fee_usd_dec"], "0.07")
        self.assertEqual(position["realized_gross_pnl_usd_dec"], "2.50")
        self.assertEqual(position["realized_net_pnl_usd_dec"], "2.37")

    def test_cumulative_cost_floor_clock_and_partial_exit_refusal(self):
        self.prepare()
        pid, attempt = self._attempt()
        known = self._result(attempt, "UNKNOWN_REQUIRES_RECONCILIATION", chargeable_cost_usd="0.01")
        self.runner.result(known)
        before = self.runner.readback()["modeled_results"]
        with self.assertRaisesRegex(PaperPlaneError, "MODELED_RESULT_COST_REGRESSION"):
            self.runner.result({**known, "result_id": "COST-REGRESSION", "observed_at": "2026-10-05T12:40:02Z", "chargeable_cost_usd": "0"})
        with self.assertRaisesRegex(PaperPlaneError, "MODELED_RESULT_CLOCK_REGRESSION"):
            self.runner.result({**known, "result_id": "CLOCK-REGRESSION", "observed_at": "2026-10-05T12:40:00Z", "chargeable_cost_usd": "0.02"})
        self.assertEqual(self.runner.readback()["modeled_results"], before)
        unknown = {**known, "result_id": "COST-UNKNOWN", "observed_at": "2026-10-05T12:40:03Z", "chargeable_cost_usd": None}
        self.runner.result(unknown)
        view = self.runner.readback()
        self.assertEqual(view["modeled_attempt_costs"]["known_additional_cost_usd"], "0.01")
        self.assertEqual(view["modeled_attempt_costs"]["additional_cost_status"], "UNKNOWN")
        self.assertIsNone(view["modeled_net_after_additional_costs_usd"])
        self.runner.result({"attempt_id": attempt, "result_id": "COST-FINAL-ENTRY", "outcome": "LANDED_SUCCESS",
            "observed_at": "2026-10-05T12:40:04Z", "unit_price_usd": "0.000003", "filled_notional_usd": "30", "chargeable_cost_usd": "0.02"})
        self.runner.command({"command_type": "REQUEST_CLOSE_POSITION", "idempotency_key": "COST-CLOSE", "position_id": pid})
        exited = self.runner.attempt(position_id=pid, side="EXIT", attempt_key="COST-EXIT", as_of="2026-10-05T12:40:05Z")
        before = self.runner.readback()
        result = {"attempt_id": exited["attempt_id"], "result_id": "COST-FINAL-EXIT", "outcome": "LANDED_SUCCESS",
            "observed_at": "2026-10-05T12:40:06Z", "unit_price_usd": "0.0000033", "chargeable_cost_usd": "0"}
        with self.assertRaisesRegex(PaperPlaneError, "PARTIAL_EXIT_MODEL_UNSUPPORTED"):
            self.runner.result({**result, "outcome": "PARTIAL"})
        after = self.runner.readback()
        self.assertEqual(after["positions"], before["positions"])
        self.assertEqual(after["modeled_results"], before["modeled_results"])
        self.runner.result(result)
        view = self.runner.readback()
        self.assertEqual(view["modeled_attempt_costs"]["known_additional_cost_usd"], "0.02")
        self.assertEqual(view["modeled_attempt_costs"]["additional_cost_status"], "KNOWN")
        self.assertEqual(view["modeled_net_after_additional_costs_usd"], "2.85")

    def test_windows_rooted_and_drive_relative_source_paths_refused(self):
        self.prepare()
        for path in ("C:source/observation_schedule_state.sqlite", "\\source\\observation_schedule_state.sqlite"):
            with self.assertRaisesRegex(PaperPlaneError, "OFFLINE_SOURCE_PATH_UNSAFE"):
                self.runner.episode(source_relative=path, episode_id=self.admission["episode_id"], epoch_id=self.epoch,
                    mode="PAPER", as_of="2026-10-05T12:40:00Z")
        self.assertEqual(self.runner.readback()["positions"], [])

    def test_cli_live_and_unowned_root_fail_before_effect(self):
        from scripts.trading_continuity import main
        target = self.root / "local/untouched"
        with redirect_stdout(StringIO()):
            code = main(["init", "--repository-root", str(self.root), "--data-root", str(target), "--mode", "LIVE"])
        self.assertEqual(code, 2)
        self.assertFalse(target.exists())

    def test_O2_same_mint_other_episode_does_not_inherit_membership(self):
        self.prepare()
        first = self.decision()
        start = self.start + timedelta(days=7)
        second = EpisodeScenario(self.data / "source2", start=start, stops=start + timedelta(minutes=1))
        obj = token_object(self.mint, price=0.000003, liquidity=10000, holders=66)
        nominate(second.market, start, {"toptraded": [obj], "toptrending": []})
        second.market.series[self.mint] = lambda now: obj
        second.tick(start)
        record = second.admissions()[0]
        second.tick(datetime(2026, 10, 12, 12, 10, tzinfo=UTC))
        second.tick(datetime(2026, 10, 12, 12, 35, tzinfo=UTC))
        packet = self.runner.episode(source_relative="source2/observation_schedule_state.sqlite", episode_id=record["episode_id"],
            epoch_id=self.epoch, mode="PAPER", as_of="2026-10-12T12:40:00Z")
        self.assertEqual(packet["decision"]["action"], "NO_ENTER")
        self.assertNotEqual(packet["decision"]["signal_decision_id"], first["decision"]["signal_decision_id"])
        self.assertEqual(packet["provenance"]["read_set"], [])
        self.assertEqual(len(self.runner.readback()["positions"]), 1)

    def test_result_terminal_classes_and_partial_inventory(self):
        self.prepare()
        _pid, attempt = self._attempt()
        partial = self._result(attempt, "PARTIAL", unit_price_usd="0.000003", filled_notional_usd="15", chargeable_cost_usd="0")
        position = self.runner.result(partial)["position"]
        self.assertEqual(position["state"], "PARTIAL")
        self.assertEqual(position["qty_dec"], "5000000.00000000")
        self.assertIsNone(position["realized_net_pnl_usd_dec"])
        with self.assertRaisesRegex(PaperPlaneError, "MODELED_RESULT_ALREADY_FINAL"):
            self.runner.result(self._result(attempt, "LANDED_SUCCESS", result_id="OTHER", unit_price_usd="0.000003", filled_notional_usd="30"))

    def test_atomic_fault_and_uncertain_attempt_do_not_resend(self):
        self.prepare()
        packet = self.decision()
        pid = packet["admission"]["position_id"]
        with fail_once_on_event("MODELED_ATTEMPT_STARTED"):
            with self.assertRaisesRegex(RuntimeError, "INJECTED_CRASH"):
                self.runner.attempt(position_id=pid, side="ENTRY", attempt_key="ENTRY-1", as_of="2026-10-05T12:40:00Z")
        self.assertEqual(self.runner.readback()["positions"][0]["state"], "WATCHED")
        self.assertEqual(self.runner.readback()["modeled_attempts"], [])
        attempt = self.runner.attempt(position_id=pid, side="ENTRY", attempt_key="ENTRY-1", as_of="2026-10-05T12:40:00Z")
        self.assertFalse(self.runner.attempt(position_id=pid, side="ENTRY", attempt_key="ENTRY-1", as_of="2026-10-05T12:40:01Z")["send_permitted"])
        result = self._result(attempt["attempt_id"], "LANDED_SUCCESS", unit_price_usd="0.000003", filled_notional_usd="30", chargeable_cost_usd="0")
        with fail_once_on_event("MODELED_RESULT_ACCEPTED"):
            with self.assertRaisesRegex(RuntimeError, "INJECTED_CRASH"):
                self.runner.result(result)
        read = self.runner.readback()
        self.assertEqual(read["positions"][0]["state"], "ATTEMPTING")
        self.assertIsNone(read["positions"][0]["qty_dec"])
        self.assertEqual(read["modeled_results"], [])
        self.assertEqual(self.runner.result(result)["position"]["state"], "OPEN")

    def test_restore_pending_inventory_and_policy_in_fresh_root(self):
        self.prepare()
        store = PaperPlaneStore(self.runner.store_path)
        try:
            applied = apply_policy(ROOT, store, mode="PAPER", candidate_raw={"new_entries_enabled": True,
                "global_entry_notional_cap_usd": "30", "max_total_open_positions": 2}, expected_current_sha256="0" * 64,
                idempotency_key="RESTORE-POLICY", owner_authorization_phrase="AUTHORIZE PAPER SHADOW TRADING RUNTIME POLICY APPLY", reason="SYNTHETIC_RESTORE_PROBE")
        finally:
            store.close()
        _pid, attempt = self._attempt()
        self.runner.result(self._result(attempt, "UNKNOWN_REQUIRES_RECONCILIATION"))
        copied_root = self.root.parent / "restore-repo"
        shutil.copytree(self.root, copied_root, ignore=shutil.ignore_patterns("paper_plane.sqlite", "paper_plane.sqlite-wal", "paper_plane.sqlite-shm"))
        restored_data = copied_root / "local/offline-synth"
        source_connection = sqlite3.connect(f"file:{self.runner.store_path.as_posix()}?mode=ro", uri=True)
        target_connection = sqlite3.connect(restored_data / "paper_plane.sqlite")
        try:
            source_connection.backup(target_connection)
            self.assertEqual(target_connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        finally:
            source_connection.close()
            target_connection.close()
        restored = TradingContinuityRunner(copied_root, data_root=restored_data, strategy_relative=self.strategy_rel)
        read = restored.readback()
        self.assertEqual(read["positions"][0]["state"], "UNKNOWN")
        reader = PaperPlaneStore(restored.store_path, readonly=True)
        try:
            self.assertEqual(show_policy(reader, "PAPER")["policy_sha256"], applied["readback"]["policy_sha256"])
        finally:
            reader.close()
        self.assertFalse(restored.attempt(position_id=read["positions"][0]["position_id"], side="ENTRY", attempt_key="ENTRY-1", as_of="2026-10-05T12:40:02Z")["send_permitted"])

    def test_no_route_exit_preserves_inventory_then_operator_reconciles_and_drains(self):
        self.prepare()
        pid, attempt = self._attempt()
        self.runner.result(self._result(attempt, "LANDED_SUCCESS", unit_price_usd="0.000003", filled_notional_usd="30", chargeable_cost_usd="0"))
        bot_id = self.runner.readback()["positions"][0]["bot_instance_id"]
        self.runner.command({"command_type": "STOP_BOT", "idempotency_key": "STOP-WITH-INVENTORY", "bot_instance_id": bot_id})
        self.runner.command({"command_type": "REQUEST_CLOSE_POSITION", "idempotency_key": "CLOSE-ORIGINATING-POSITION", "position_id": pid})
        attempted = self.runner.attempt(position_id=pid, side="EXIT", attempt_key="EXIT-NO-ROUTE", as_of="2026-10-05T12:40:02Z")
        failure = {"attempt_id": attempted["attempt_id"], "result_id": "EXIT-NO-ROUTE", "outcome": "NO_ROUTE", "observed_at": "2026-10-05T12:40:03Z", "chargeable_cost_usd": "0"}
        position = self.runner.result(failure)["position"]
        self.assertEqual(position["state"], "UNRESOLVED")
        self.assertEqual(position["qty_dec"], "10000000.00000000")
        self.assertIsNone(position["realized_net_pnl_usd_dec"])
        self.assertEqual(self.runner.readback()["bots"][0]["status"], "DRAINING")
        attention = next(a for a in self.runner.readback()["attention"] if a["code"] == "BOT_DRAINING")
        self.assertEqual(attention["NEXT_SAFE_ACTION"], "REQUEST_CLOSE_OR_RECONCILE_ATTEMPT")
        with self.assertRaisesRegex(PaperPlaneError, "AUTOMATIC_EXIT_INACTIVE_EPOCH_UNRESOLVED_USE_OPERATOR"):
            self.runner.exit(position_id=pid, source_relative="source/observation_schedule_state.sqlite", as_of="2026-10-05T16:10:00Z")
        retry = self.runner.attempt(position_id=pid, side="EXIT", attempt_key="EXIT-ROUTE-RECOVERED", as_of="2026-10-05T12:40:04Z")
        final = {"attempt_id": retry["attempt_id"], "result_id": "EXIT-RECOVERED", "outcome": "LANDED_SUCCESS", "observed_at": "2026-10-05T12:40:05Z", "unit_price_usd": "0.0000033", "chargeable_cost_usd": "0"}
        self.assertEqual(self.runner.result(final)["drain"]["bot_status"], "STOPPED")


class SelectorOracleTests(unittest.TestCase):
    def test_literal_exactly_two_at_least_two_unknown_invalid_and_aliases(self):
        ids = ["A", "B", "C"]
        for low, high, expected in ((2, 2, {2}), (2, 3, {2, 3})):
            selector = scope.canonical_selector({"clauses": [{"count": {"of": ids, "min": low, "max": high}}]}, lambda value: value)
            for count in range(4):
                states = {item: scope.TRUE if i < count else scope.FALSE for i, item in enumerate(ids)}
                self.assertEqual(scope.evaluate_selector(selector, states), scope.TRUE if count in expected else scope.FALSE)
            self.assertEqual(scope.evaluate_selector(selector, {"A": scope.TRUE, "B": scope.TRUE, "C": scope.UNKNOWN}), scope.UNKNOWN)
            self.assertEqual(scope.evaluate_selector(selector, {"A": scope.TRUE, "B": scope.TRUE, "C": scope.INVALID}), scope.INVALID)
