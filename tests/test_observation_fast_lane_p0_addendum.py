from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.hypothesis_fast_lane import execute_submit  # noqa: E402
from solana_alpha_lab.factory.lane_classifier import Lane, classify_lane  # noqa: E402
from solana_alpha_lab.factory.observation_panel_coverage import (  # noqa: E402
    compute_evidence_role,
    resolve_authoritative_hypothesis_registered_at,
)
from solana_alpha_lab.factory.observation_panel_publisher import (  # noqa: E402
    load_pending_observation_bindings,
)
from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    load_observation_schedule,
    render_utc,
)
from solana_alpha_lab.factory.observation_schedule_capability import (  # noqa: E402
    compile_and_bind_observation_schedule,
)
from solana_alpha_lab.factory.observation_schedule_compiler import (  # noqa: E402
    compile_observation_request,
)
from solana_alpha_lab.factory.observation_schedule_lifecycle import (  # noqa: E402
    ObservationLifecycleError,
    activate_schedule,
    authorize_schedule,
    observation_ops_store_path,
)
from solana_alpha_lab.factory.observation_schedule_store import (  # noqa: E402
    ObservationScheduleStore,
)
from solana_alpha_lab.factory.observation_scheduler import tick_once  # noqa: E402
from solana_alpha_lab.factory.research_store import (  # noqa: E402
    RecordKind,
    ResearchEvent,
    ResearchStore,
)
from tests.test_fast_lane_classifier import HYPOTHESIS_DEFINITION_SHA256  # noqa: E402
from tests.test_observation_fast_lane_routing_closure import (  # noqa: E402
    AS_OF_NOON,
    AS_OF_START,
    GIT_SHA,
    NOW,
    OBS_CAPABILITY,
    packet_for,
    persist_active_schedule,
    persist_covering_snapshot,
    v1_2_spec,
    write_packet,
)
from tests.test_observation_scheduler import _Opener  # noqa: E402


T0 = datetime(2026, 8, 1, tzinfo=UTC)
T1 = datetime(2026, 8, 15, tzinfo=UTC)
T2 = datetime(2026, 9, 2, tzinfo=UTC)
STOPS = datetime(2026, 9, 2, tzinfo=UTC)


def real_git_sha() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    value = completed.stdout.decode("ascii", errors="ignore").strip()
    if len(value) != 40:
        raise AssertionError("RUNNER_GIT_SHA_UNAVAILABLE")
    return value


def persist_hypothesis_version(
    data_root: Path,
    *,
    hypothesis_version_id: str,
    definition_sha256: str,
    created_at: datetime,
) -> None:
    payload = {
        "hypothesis_version_id": hypothesis_version_id,
        "definition_sha256": definition_sha256,
        "family_id": "HYP-FAMILY-OBS-P0-001",
        "version_ordinal": 1,
        "origin_id": "HYP-ORIGIN-OBS-P0-001",
        "origin_kind": "DATA_ANALYSIS",
        "research_cycle_id": "RESEARCH-CYCLE-OBS-P0-001",
        "statement": "trusted clock",
        "mechanism": "rdp",
        "falsifier": "backdated as_of",
        "expected_regime_terms": [],
        "what_changed": "P0_CLOCK",
    }
    payload_json = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    event = ResearchEvent(
        record_id=f"HYP-VERSION-{hypothesis_version_id[-16:]}",
        record_kind=RecordKind.HYPOTHESIS_VERSION,
        entity_id=hypothesis_version_id,
        hypothesis_version_id=hypothesis_version_id,
        run_id=None,
        transaction_id=f"RESEARCH-TXN-HYP-{hypothesis_version_id[-12:]}",
        effective_at=created_at,
        first_reliable_available_at=created_at,
        supersedes_record_id=None,
        payload_json=payload_json,
        payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        schema_version="1.0",
        producer_capability_id=OBS_CAPABILITY,
        producer_git_sha=real_git_sha(),
        created_at=created_at,
    )
    ResearchStore(data_root).append([event], transaction_id=event.transaction_id)


class ObservationFastLaneP0AddendumTests(unittest.TestCase):
    def test_p0a_capability_rejects_missing_producer_git_sha(self) -> None:
        covering = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/common_panel.yaml"
        )
        spec = v1_2_spec(mode="REUSE_OR_SCHEDULE", role="EXPLORATORY_REUSE")
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            persist_covering_snapshot(data_root, covering)
            with self.assertRaisesRegex(
                ObservationLifecycleError, "PRODUCER_GIT_SHA_REQUIRED"
            ):
                compile_and_bind_observation_schedule(
                    spec,
                    root=ROOT,
                    data_root=data_root,
                    producer_git_sha=None,
                )

    def test_p0a_public_submit_binds_real_identities(self) -> None:
        covering = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/common_panel.yaml"
        )
        spec = v1_2_spec(
            mode="REUSE_OR_SCHEDULE",
            role="EXPLORATORY_REUSE",
            as_of="2026-09-01T12:00:00Z",
            availability_cutoff="2026-09-01T12:00:00Z",
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            persist_covering_snapshot(data_root, covering)
            result = execute_submit(
                ROOT,
                data_root,
                write_packet(data_root, packet_for(spec)),
                AS_OF_NOON,
                run=True,
                authority_phrase=None,
            )
            self.assertEqual(result["status"], "COMPLETE")
            passport = ResearchStore(data_root).find_completed_run(result["run_key_sha256"])
            self.assertIsNotNone(passport)
            assert passport is not None
            self.assertEqual(passport.runner_git_sha, real_git_sha())
            self.assertEqual(passport.hypothesis_version_id, spec["hypothesis_version"])
            self.assertEqual(passport.run_id, result["run_id_or_null"])
            durable = [
                record
                for record in ResearchStore(data_root).iter_committed_records()
                if record.producer_capability_id == OBS_CAPABILITY
                and record.created_at >= AS_OF_NOON
                and record.record_kind
                in {
                    RecordKind.OBSERVATION_SCHEDULE_BINDING.value,
                    RecordKind.RUN_COMPLETED.value,
                }
            ]
            self.assertTrue(durable)
            self.assertTrue(all(item.producer_git_sha == real_git_sha() for item in durable))

    def test_p0b_backdated_spec_cannot_manufacture_prospective_oos(self) -> None:
        covering = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/common_panel.yaml"
        )
        spec = v1_2_spec(
            mode="REUSE_OR_SCHEDULE",
            role="PROSPECTIVE_OOS",
            as_of=render_utc(T0),
            availability_cutoff=render_utc(T2),
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            persist_covering_snapshot(data_root, covering)
            persist_hypothesis_version(
                data_root,
                hypothesis_version_id=str(spec["hypothesis_version"]),
                definition_sha256=HYPOTHESIS_DEFINITION_SHA256,
                created_at=T2,
            )
            registered = resolve_authoritative_hypothesis_registered_at(
                data_root,
                hypothesis_version_id=str(spec["hypothesis_version"]),
                hypothesis_definition_sha256=HYPOTHESIS_DEFINITION_SHA256,
            )
            self.assertEqual(registered, T2)
            compiled = compile_observation_request(
                spec,
                root=ROOT,
                data_root=data_root,
                now=T2,
                hypothesis_version_id=str(spec["hypothesis_version"]),
                hypothesis_definition_sha256=HYPOTHESIS_DEFINITION_SHA256,
            )
            self.assertNotEqual(compiled.evidence_role, "PROSPECTIVE_OOS")
            self.assertEqual(compiled.hypothesis_registered_at, T2)
            self.assertEqual(compiled.experiment_as_of, T0)

    def test_p0b_genuine_prospective_uses_trusted_clock(self) -> None:
        spec = v1_2_spec(as_of=render_utc(AS_OF_START), role="PROSPECTIVE_OOS")
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            persist_hypothesis_version(
                data_root,
                hypothesis_version_id=str(spec["hypothesis_version"]),
                definition_sha256=HYPOTHESIS_DEFINITION_SHA256,
                created_at=T0,
            )
            compiled = compile_observation_request(
                spec,
                root=ROOT,
                data_root=data_root,
                now=AS_OF_START,
                hypothesis_version_id=str(spec["hypothesis_version"]),
                hypothesis_definition_sha256=HYPOTHESIS_DEFINITION_SHA256,
            )
            self.assertEqual(compiled.evidence_role, "PROSPECTIVE_OOS")
            self.assertEqual(compiled.hypothesis_registered_at, T0)

    def test_p0b_future_spec_is_denied(self) -> None:
        spec = v1_2_spec(as_of="2026-09-01T12:00:00Z")
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            decision = classify_lane(
                packet_for(spec),
                root=ROOT,
                data_root=data_root,
                as_of=AS_OF_START,
            )
            self.assertEqual(decision.terminal, "DENY_INVALID_SPEC")
            self.assertEqual(decision.lane, Lane.DENY)

    def test_p0b_later_maturation_does_not_rebase_registration(self) -> None:
        spec_early = v1_2_spec(as_of="2026-09-01T00:00:00Z")
        spec_late = v1_2_spec(as_of="2026-09-01T12:00:00Z")
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            persist_hypothesis_version(
                data_root,
                hypothesis_version_id=str(spec_early["hypothesis_version"]),
                definition_sha256=HYPOTHESIS_DEFINITION_SHA256,
                created_at=T0,
            )
            first = compile_observation_request(
                spec_early,
                root=ROOT,
                data_root=data_root,
                now=AS_OF_START,
                hypothesis_version_id=str(spec_early["hypothesis_version"]),
                hypothesis_definition_sha256=HYPOTHESIS_DEFINITION_SHA256,
            )
            second = compile_observation_request(
                spec_late,
                root=ROOT,
                data_root=data_root,
                now=AS_OF_NOON,
                hypothesis_version_id=str(spec_late["hypothesis_version"]),
                hypothesis_definition_sha256=HYPOTHESIS_DEFINITION_SHA256,
            )
            self.assertEqual(first.hypothesis_registered_at, T0)
            self.assertEqual(second.hypothesis_registered_at, T0)
            self.assertEqual(first.evidence_role, second.evidence_role)

    def test_p0b_missing_registration_never_claims_prospective(self) -> None:
        self.assertEqual(
            compute_evidence_role(
                hypothesis_registered_at=None,
                first_admission_at=AS_OF_START,
                first_y_available_at=None,
                closed_or_consumed=False,
            ),
            "EXPLORATORY_REUSE",
        )

    def test_p0c_prepare_new_schedule_is_proposed_not_authority(self) -> None:
        spec = v1_2_spec()
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            first = execute_submit(
                ROOT,
                data_root,
                write_packet(data_root, packet_for(spec)),
                AS_OF_START,
                run=True,
                authority_phrase=None,
            )
            self.assertEqual(first["status"], "BLOCKED_AUTHORITY")
            self.assertEqual(first["observation_terminal"], "SCHEDULE_ACTIVATION_REQUIRED")
            self.assertEqual(first["authority_status"], "PROPOSED_NOT_AUTHORITY")
            request = first["authority_request"]
            self.assertEqual(request["cash_usd_max"], "0")
            self.assertFalse(request["retry"])
            self.assertFalse(request["fallback"])
            self.assertTrue(request["exact_owner_phrase"])
            store = ObservationScheduleStore(observation_ops_store_path(data_root))
            try:
                self.assertIsNotNone(store.get_registered_schedule(request["schedule_sha256"]))
                self.assertIsNone(store.get_authority(request.get("receipt_sha256") or ""))
            finally:
                store.close()
            second = execute_submit(
                ROOT,
                data_root,
                write_packet(data_root, packet_for(spec)),
                AS_OF_START,
                run=True,
                authority_phrase=None,
            )
            self.assertEqual(
                second["authority_request"]["schedule_sha256"],
                request["schedule_sha256"],
            )
            self.assertEqual(
                second["authority_request"]["exact_owner_phrase"],
                request["exact_owner_phrase"],
            )
            store = ObservationScheduleStore(observation_ops_store_path(data_root))
            try:
                with self.assertRaises(ObservationLifecycleError):
                    authorize_schedule(
                        root=ROOT,
                        data_root=data_root,
                        store=store,
                        schedule_sha256=request["schedule_sha256"],
                        phrase="WRONG PHRASE",
                        now=AS_OF_START,
                        producer_git_sha=real_git_sha(),
                    )
                authorized = authorize_schedule(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    schedule_sha256=request["schedule_sha256"],
                    phrase=request["exact_owner_phrase"],
                    now=AS_OF_START,
                    producer_git_sha=real_git_sha(),
                )
            finally:
                store.close()
            self.assertEqual(authorized["terminal"], "AUTHORIZED")

    def test_p0c_successor_packet_names_predecessor(self) -> None:
        predecessor = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        spec = v1_2_spec(
            fixture="successor_y259200.yaml",
            mode="SCHEDULE_ONLY",
            role="PROSPECTIVE_OOS",
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            persist_active_schedule(data_root, predecessor)
            result = execute_submit(
                ROOT,
                data_root,
                write_packet(data_root, packet_for(spec)),
                AS_OF_START,
                run=True,
                authority_phrase=None,
            )
            self.assertEqual(
                result["observation_terminal"],
                "NEW_VERSION_FOR_FUTURE_COHORTS_REQUIRED",
            )
            request = result["authority_request"]
            self.assertEqual(
                request["predecessor_schedule_sha256"],
                predecessor["schedule_sha256"],
            )
            self.assertEqual(request["successor_schedule_sha256"], request["schedule_sha256"])
            self.assertTrue(request["cutover_at"])
            self.assertEqual(
                predecessor["activation"]["stops_admitting_at"],
                predecessor["activation"]["stops_admitting_at"],
            )

    def test_p0d_admission_stop_drains_and_blocks_new_members(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/common_panel.yaml"
        )
        spec = v1_2_spec(
            fixture="x300_y900.yaml",
            mode="SCHEDULE_ONLY",
            role="PROSPECTIVE_OOS",
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            persist_active_schedule(data_root, schedule)
            persist_hypothesis_version(
                data_root,
                hypothesis_version_id=str(spec["hypothesis_version"]),
                definition_sha256=HYPOTHESIS_DEFINITION_SHA256,
                created_at=T0,
            )
            attached = classify_lane(
                packet_for(spec),
                root=ROOT,
                data_root=data_root,
                as_of=STOPS - timedelta(seconds=1),
            )
            self.assertEqual(attached.terminal, "ATTACHED_TO_ACTIVE_SCHEDULE")
            expired = classify_lane(
                packet_for(spec),
                root=ROOT,
                data_root=data_root,
                as_of=STOPS,
            )
            self.assertNotEqual(expired.terminal, "ATTACHED_TO_ACTIVE_SCHEDULE")
            self.assertIn(
                expired.terminal,
                {
                    "SCHEDULE_ACTIVATION_REQUIRED",
                    "NEW_VERSION_FOR_FUTURE_COHORTS_REQUIRED",
                },
            )
            store = ObservationScheduleStore(observation_ops_store_path(data_root))
            try:
                prepared = execute_submit(
                    ROOT,
                    data_root,
                    write_packet(data_root, packet_for(v1_2_spec())),
                    AS_OF_START,
                    run=True,
                    authority_phrase=None,
                )
                request = prepared["authority_request"]
                authorize_schedule(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    schedule_sha256=request["schedule_sha256"],
                    phrase=request["exact_owner_phrase"],
                    now=AS_OF_START,
                    producer_git_sha=real_git_sha(),
                )
                activate_schedule(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    schedule_sha256=request["schedule_sha256"],
                    activation_id="ACT-P0D-001",
                    now=AS_OF_START,
                    producer_git_sha=real_git_sha(),
                )
                live = load_observation_schedule(
                    ROOT, "tests/fixtures/observation_schedule/common_panel.yaml"
                )
                opener = _Opener()
                before = tick_once(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    schedule=live,
                    activation_id="ACT-P0D-001",
                    now=STOPS - timedelta(seconds=1),
                    opener=opener,
                    producer_git_sha=real_git_sha(),
                )
                calls_before = before["provider_calls"]
                at_stop = tick_once(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    schedule=live,
                    activation_id="ACT-P0D-001",
                    now=STOPS,
                    opener=opener,
                    producer_git_sha=real_git_sha(),
                )
                self.assertEqual(at_stop["activation_state"], "DRAINING")
                self.assertEqual(at_stop["provider_calls"], 0)
                self.assertLessEqual(at_stop["provider_calls"], calls_before)
                self.assertEqual(
                    store.get_activation(request["schedule_sha256"], "ACT-P0D-001")["state"],
                    "DRAINING",
                )
            finally:
                store.close()

    def test_p0e_pending_binding_survives_restart_and_matures(self) -> None:
        covering = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/common_panel.yaml"
        )
        spec = v1_2_spec(
            fixture="x300_y900.yaml",
            mode="SCHEDULE_ONLY",
            role="PROSPECTIVE_OOS",
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            persist_active_schedule(data_root, covering)
            persist_hypothesis_version(
                data_root,
                hypothesis_version_id=str(spec["hypothesis_version"]),
                definition_sha256=HYPOTHESIS_DEFINITION_SHA256,
                created_at=T0,
            )
            packet_path = write_packet(data_root, packet_for(spec))
            first = execute_submit(
                ROOT,
                data_root,
                packet_path,
                AS_OF_START,
                run=True,
                authority_phrase=None,
            )
            self.assertEqual(first["status"], "BLOCKED_DATA")
            self.assertEqual(first["observation_terminal"], "ATTACHED_TO_ACTIVE_SCHEDULE")
            self.assertIsNone(first["run_id_or_null"])
            pending = first["pending_binding"]
            self.assertEqual(pending["state"], "WAITING_FOR_PANEL")
            self.assertIsNone(ResearchStore(data_root).find_completed_run(first["run_key_sha256"]))
            replay = classify_lane(packet_for(spec), root=ROOT, data_root=data_root, as_of=AS_OF_START)
            self.assertNotEqual(replay.terminal, "REPLAY_AVAILABLE")
            second = execute_submit(
                ROOT,
                data_root,
                packet_path,
                AS_OF_START,
                run=True,
                authority_phrase=None,
            )
            self.assertEqual(
                second["pending_binding"]["pending_binding_sha256"],
                pending["pending_binding_sha256"],
            )
            waiting = [
                item
                for item in load_pending_observation_bindings(data_root)
                if item["state"] == "WAITING_FOR_PANEL"
            ]
            self.assertEqual(len(waiting), 1)
            persist_covering_snapshot(data_root, covering)
            store = ObservationScheduleStore(observation_ops_store_path(data_root))
            try:
                from solana_alpha_lab.factory.observation_schedule_lifecycle import (
                    materialize_pending_observation_snapshots,
                )

                store.persist_registered_schedule(
                    schedule_sha256=covering["schedule_sha256"],
                    schedule_key=covering["schedule_key"],
                    document=covering,
                    clock=NOW,
                )
                materialize_pending_observation_snapshots(
                    data_root=data_root,
                    store=store,
                    schedule_sha256=covering["schedule_sha256"],
                    activation_id="ACT-OBS-ROUTING-001",
                    now=AS_OF_NOON,
                    producer_git_sha=real_git_sha(),
                )
            finally:
                store.close()
            matured = [
                item
                for item in load_pending_observation_bindings(data_root)
                if item["pending_binding_sha256"] == pending["pending_binding_sha256"]
            ]
            reuse_spec = v1_2_spec(
                fixture="x300_y900.yaml",
                mode="REUSE_OR_SCHEDULE",
                role="EXPLORATORY_REUSE",
                as_of="2026-09-01T12:00:00Z",
                availability_cutoff="2026-09-01T12:00:00Z",
            )
            reuse = classify_lane(
                packet_for(reuse_spec),
                root=ROOT,
                data_root=data_root,
                as_of=AS_OF_NOON,
            )
            self.assertEqual(reuse.terminal, "PANEL_REUSE_READY")
            self.assertNotEqual(reuse.terminal, "REPLAY_AVAILABLE")
            if matured:
                self.assertEqual(matured[0]["state"], "SATISFIED")

    def test_p0f_capability_status_does_not_lie(self) -> None:
        spec = v1_2_spec()
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            bound = compile_and_bind_observation_schedule(
                spec,
                root=ROOT,
                data_root=data_root,
                producer_git_sha=real_git_sha(),
                hypothesis_version_id=str(spec["hypothesis_version"]),
                run_id="RUN-P0F-001",
                now=AS_OF_START,
                hypothesis_definition_sha256=HYPOTHESIS_DEFINITION_SHA256,
            )
            self.assertEqual(bound["terminal"], "SCHEDULE_ACTIVATION_REQUIRED")
            self.assertEqual(bound["status"], "BLOCKED_AUTHORITY")
            self.assertNotEqual(bound["status"], "COMPLETE")

    def test_integrated_killing_smoke(self) -> None:
        covering = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/common_panel.yaml"
        )
        prepare_spec = v1_2_spec()
        wait_spec = v1_2_spec(
            fixture="x300_y900.yaml",
            mode="SCHEDULE_ONLY",
            role="PROSPECTIVE_OOS",
        )
        reuse_spec = v1_2_spec(
            mode="REUSE_OR_SCHEDULE",
            role="EXPLORATORY_REUSE",
            as_of="2026-09-01T12:00:00Z",
            availability_cutoff="2026-09-01T12:00:00Z",
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            persist_hypothesis_version(
                data_root,
                hypothesis_version_id=str(prepare_spec["hypothesis_version"]),
                definition_sha256=HYPOTHESIS_DEFINITION_SHA256,
                created_at=T0,
            )
            prepared = execute_submit(
                ROOT,
                data_root,
                write_packet(data_root, packet_for(prepare_spec)),
                AS_OF_START,
                run=True,
                authority_phrase=None,
            )
            self.assertEqual(prepared["status"], "BLOCKED_AUTHORITY")
            self.assertEqual(prepared["authority_status"], "PROPOSED_NOT_AUTHORITY")
            self.assertNotEqual(prepared["status"], "FAILED_INFRA")
            self.assertIsNone(ResearchStore(data_root).find_completed_run(prepared["run_key_sha256"]))
            request = prepared["authority_request"]
            store = ObservationScheduleStore(observation_ops_store_path(data_root))
            try:
                authorized = authorize_schedule(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    schedule_sha256=request["schedule_sha256"],
                    phrase=request["exact_owner_phrase"],
                    now=AS_OF_START,
                    producer_git_sha=real_git_sha(),
                )
                self.assertEqual(authorized["terminal"], "AUTHORIZED")
                activated = activate_schedule(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    schedule_sha256=request["schedule_sha256"],
                    activation_id="ACT-SMOKE-001",
                    now=AS_OF_START,
                    producer_git_sha=real_git_sha(),
                )
                self.assertEqual(activated["state"], "ACTIVE")
                attached = execute_submit(
                    ROOT,
                    data_root,
                    write_packet(data_root, packet_for(wait_spec)),
                    AS_OF_START,
                    run=True,
                    authority_phrase=None,
                )
                self.assertEqual(attached["observation_terminal"], "ATTACHED_TO_ACTIVE_SCHEDULE")
                self.assertEqual(attached["pending_binding"]["state"], "WAITING_FOR_PANEL")
                self.assertIsNone(
                    ResearchStore(data_root).find_completed_run(attached["run_key_sha256"])
                )
                opener = _Opener()
                tick_once(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    schedule=covering,
                    activation_id="ACT-SMOKE-001",
                    now=STOPS - timedelta(seconds=1),
                    opener=opener,
                    producer_git_sha=real_git_sha(),
                )
                at_stop = tick_once(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    schedule=covering,
                    activation_id="ACT-SMOKE-001",
                    now=STOPS,
                    opener=opener,
                    producer_git_sha=real_git_sha(),
                )
                self.assertEqual(at_stop["activation_state"], "DRAINING")
                persist_covering_snapshot(data_root, covering)
                tick_once(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    schedule=covering,
                    activation_id="ACT-SMOKE-001",
                    now=AS_OF_NOON,
                    opener=_Opener(),
                    producer_git_sha=real_git_sha(),
                    discovery_rows=[],
                )
            finally:
                store.close()
            reuse = execute_submit(
                ROOT,
                data_root,
                write_packet(data_root, packet_for(reuse_spec)),
                AS_OF_NOON,
                run=True,
                authority_phrase=None,
            )
            self.assertEqual(reuse["status"], "COMPLETE")
            self.assertEqual(reuse["observation_terminal"], "PANEL_REUSE_READY")
            self.assertEqual(reuse["git_mutation_count"], 0)
            self.assertEqual(reuse["provider_calls_actual"], 0)
            passport = ResearchStore(data_root).find_completed_run(reuse["run_key_sha256"])
            self.assertIsNotNone(passport)
            assert passport is not None
            self.assertEqual(passport.observation_schedule_sha256, covering["schedule_sha256"])
            self.assertEqual(len(passport.observation_panel_snapshot_sha256 or ""), 64)
            replay = classify_lane(
                packet_for(reuse_spec),
                root=ROOT,
                data_root=data_root,
                as_of=AS_OF_NOON,
            )
            self.assertEqual(replay.terminal, "REPLAY_AVAILABLE")


if __name__ == "__main__":
    unittest.main()
