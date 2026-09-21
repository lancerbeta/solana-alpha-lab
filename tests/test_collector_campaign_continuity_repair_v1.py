from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.collector_operational_packet import (
    assess_campaign_successor_continuity,
    build_collector_operational_packet,
    compose_health_classes,
)
from solana_alpha_lab.factory.collector_read_model import (
    build_collector_read_model,
    classify_doctor_current_activation,
    select_current_activation,
)
from solana_alpha_lab.factory.observation_panel_coverage import admission_window_open
from solana_alpha_lab.factory.observation_schedule import (
    load_observation_schedule,
    parse_utc,
    render_utc,
    schedule_sha256,
)
from solana_alpha_lab.factory.observation_schedule_lifecycle import (
    ObservationLifecycleError,
    _authority_policy,
    activate_schedule,
    authorize_schedule,
    drain_expired_admission,
    expected_authority_phrase,
    owner_next_action_for_lifecycle_error,
    register_schedule,
    resolve_late_recovery_proof,
    rollover_schedule,
)
from solana_alpha_lab.factory.observation_schedule_store import (
    ObservationScheduleStore,
    ObservationScheduleStoreError,
)
from solana_alpha_lab.factory.operability_watch import (
    INCIDENT_GRACE_SECONDS,
    classify_incidents,
    evaluate_operability,
)
from solana_alpha_lab.factory.observation_schedule import canonical_sha256

GIT = "c" * 40
NOW = datetime(2026, 9, 1, 0, 10, tzinfo=UTC)


def _phrase(document: dict) -> str:
    horizon = max(
        int(point["due_offset_seconds"]) + int(point["allowed_lateness_seconds"])
        for point in [document["x_point"], *document["y_points"]]
    )
    expires_at = render_utc(
        parse_utc(document["activation"]["stops_admitting_at"])
        + timedelta(seconds=horizon)
    )
    policy = _authority_policy(
        root=ROOT,
        document=document,
        schedule_key=document["schedule_key"],
        expires_at=expires_at,
    )
    return expected_authority_phrase(
        schedule_sha256=document["schedule_sha256"],
        schedule_key=document["schedule_key"],
        activation_starts_at=document["activation"]["starts_at"],
        activation_stops_admitting_at=document["activation"]["stops_admitting_at"],
        provider_route_ids=policy["provider_route_ids"],
        expires_at=expires_at,
        policy_digest=canonical_sha256(policy),
    )


def _with_window(
    document: dict,
    *,
    starts_at: str,
    stops_admitting_at: str,
    schedule_key: str | None = None,
) -> dict:
    out = json.loads(json.dumps(document))
    out["activation"] = dict(out["activation"])
    out["activation"]["starts_at"] = starts_at
    out["activation"]["stops_admitting_at"] = stops_admitting_at
    if schedule_key is not None:
        out["schedule_key"] = schedule_key
    out.pop("schedule_sha256", None)
    out["schedule_sha256"] = schedule_sha256(out)
    return out


def _register_and_authorize(
    store: ObservationScheduleStore,
    data_root: Path,
    document: dict,
    *,
    now: datetime = NOW,
) -> tuple[dict, dict]:
    registered = register_schedule(
        root=ROOT,
        data_root=data_root,
        store=store,
        document=document,
        now=now,
        producer_git_sha=GIT,
    )
    authority = authorize_schedule(
        root=ROOT,
        data_root=data_root,
        store=store,
        schedule_sha256=registered["schedule_sha256"],
        phrase=_phrase(document),
        now=now,
        producer_git_sha=GIT,
    )
    return registered, authority


def _activate_campaign(
    store: ObservationScheduleStore,
    data_root: Path,
    document: dict,
    *,
    activation_id: str,
    now: datetime = NOW,
) -> tuple[dict, dict]:
    registered, authority = _register_and_authorize(
        store, data_root, document, now=now
    )
    activate_schedule(
        root=ROOT,
        data_root=data_root,
        store=store,
        schedule_sha256=registered["schedule_sha256"],
        activation_id=activation_id,
        now=now,
        producer_git_sha=GIT,
    )
    return registered, authority


class CollectorCampaignContinuityRepairTests(unittest.TestCase):
    def test_active_peer_still_requires_cutover(self) -> None:
        predecessor = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        successor = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/successor_y259200.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            digests: list[str] = []
            for document in (predecessor, successor):
                registered = register_schedule(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    document=document,
                    now=NOW,
                    producer_git_sha=GIT,
                )
                digests.append(registered["schedule_sha256"])
                authorize_schedule(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    schedule_sha256=registered["schedule_sha256"],
                    phrase=_phrase(document),
                    now=NOW,
                    producer_git_sha=GIT,
                )
            activate_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule_sha256=digests[0],
                activation_id="ACT-PRE",
                now=NOW,
                producer_git_sha=GIT,
            )
            with self.assertRaisesRegex(
                ObservationLifecycleError, "COHORT_CUTOVER_REQUIRED"
            ):
                activate_schedule(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    schedule_sha256=digests[1],
                    activation_id="ACT-SUC",
                    now=NOW,
                    producer_git_sha=GIT,
                )
            store.close()

    def test_late_non_admitting_draining_allows_forward_successor(self) -> None:
        predecessor = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        successor = _with_window(
            load_observation_schedule(
                ROOT, "tests/fixtures/observation_schedule/successor_y259200.yaml"
            ),
            # The late recovery point is 01:00Z; the successor must start
            # there, not at the predecessor's historical stop time.
            starts_at="2026-09-02T01:00:00Z",
            stops_admitting_at="2026-09-03T00:00:00Z",
            schedule_key="OBS-EARLY-PUMPFUN-SUCCESSOR-LATE-001",
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            pred = register_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                document=predecessor,
                now=NOW,
                producer_git_sha=GIT,
            )
            authorize_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule_sha256=pred["schedule_sha256"],
                phrase=_phrase(predecessor),
                now=NOW,
                producer_git_sha=GIT,
            )
            activate_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule_sha256=pred["schedule_sha256"],
                activation_id="ACT-PRE",
                now=NOW,
                producer_git_sha=GIT,
            )
            store.insert_due(
                {
                    "schedule_sha256": pred["schedule_sha256"],
                    "activation_id": "ACT-PRE",
                    "entity_id": "mint-pending",
                    "point_id": "Y900",
                    "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                    "state": "PENDING",
                    "due_at": "2026-09-02T12:00:00Z",
                    "deadline_at": "2026-09-02T13:00:00Z",
                    "payload": {},
                },
                clock=NOW,
            )
            late = datetime(2026, 9, 2, 1, 0, tzinfo=UTC)
            drained = drain_expired_admission(
                data_root=data_root,
                store=store,
                schedule_sha256=pred["schedule_sha256"],
                activation_id="ACT-PRE",
                now=late,
                producer_git_sha=GIT,
            )
            self.assertEqual(drained["terminal"], "DRAINED")
            self.assertEqual(
                store.get_activation(pred["schedule_sha256"], "ACT-PRE")["state"],
                "DRAINING",
            )
            draining_row = store.get_activation(pred["schedule_sha256"], "ACT-PRE")
            assert draining_row is not None
            proof = resolve_late_recovery_proof(data_root, draining_row, now=late)
            self.assertEqual(
                proof["late_recovery_proof"], "APPEND_ONLY_DRAINING_TRANSITION"
            )
            self.assertEqual(proof["late_recovery_at"], "2026-09-02T01:00:00Z")
            forged_payload = dict(draining_row["payload"])
            forged_payload["transition_effective_at"] = "2026-09-01T00:00:00Z"
            with self.assertRaisesRegex(
                ObservationScheduleStoreError, "DENY_RETROACTIVE_MUTATION"
            ):
                store.upsert_activation(
                    {**draining_row, "payload": forged_payload},
                    clock=late,
                )
            succ = register_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                document=successor,
                now=late,
                producer_git_sha=GIT,
            )
            authorize_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule_sha256=succ["schedule_sha256"],
                phrase=_phrase(successor),
                now=late,
                producer_git_sha=GIT,
            )
            activated = activate_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule_sha256=succ["schedule_sha256"],
                activation_id="ACT-SUC",
                now=late,
                producer_git_sha=GIT,
            )
            self.assertEqual(activated["terminal"], "ACTIVATED")
            self.assertEqual(
                store.get_activation(pred["schedule_sha256"], "ACT-PRE")["state"],
                "DRAINING",
            )
            self.assertEqual(
                store.get_activation(succ["schedule_sha256"], "ACT-SUC")["state"],
                "ACTIVE",
            )
            dues = store.due_in_states(("PENDING",))
            self.assertTrue(
                any(
                    str(row["activation_id"]) == "ACT-PRE"
                    and str(row["entity_id"]) == "mint-pending"
                    for row in dues
                )
            )
            admitting = [
                row
                for row in store.list_activations()
                if str(row["state"]) == "ACTIVE"
            ]
            self.assertEqual(len(admitting), 1)
            self.assertEqual(admitting[0]["activation_id"], "ACT-SUC")
            self.assertEqual(len(store.list_rollovers()), 0)
            pred_doc = store.get_registered_schedule(pred["schedule_sha256"])[
                "document"
            ]
            succ_doc = store.get_registered_schedule(succ["schedule_sha256"])[
                "document"
            ]
            self.assertFalse(admission_window_open(pred_doc, late))
            self.assertTrue(admission_window_open(succ_doc, late))
            store.close()

    def test_late_successor_backdated_to_recovery_is_denied(self) -> None:
        predecessor = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        successor = _with_window(
            load_observation_schedule(
                ROOT, "tests/fixtures/observation_schedule/successor_y259200.yaml"
            ),
            starts_at="2026-09-02T00:30:00Z",
            stops_admitting_at="2026-09-03T00:00:00Z",
            schedule_key="OBS-EARLY-PUMPFUN-SUCCESSOR-RECOVERY-BACKDATED-001",
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            pred = register_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                document=predecessor,
                now=NOW,
                producer_git_sha=GIT,
            )
            authorize_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule_sha256=pred["schedule_sha256"],
                phrase=_phrase(predecessor),
                now=NOW,
                producer_git_sha=GIT,
            )
            activate_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule_sha256=pred["schedule_sha256"],
                activation_id="ACT-PRE",
                now=NOW,
                producer_git_sha=GIT,
            )
            late = datetime(2026, 9, 2, 1, 0, tzinfo=UTC)
            drain_expired_admission(
                data_root=data_root,
                store=store,
                schedule_sha256=pred["schedule_sha256"],
                activation_id="ACT-PRE",
                now=late,
                producer_git_sha=GIT,
            )
            succ = register_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                document=successor,
                now=late,
                producer_git_sha=GIT,
            )
            authorize_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule_sha256=succ["schedule_sha256"],
                phrase=_phrase(successor),
                now=late,
                producer_git_sha=GIT,
            )
            with self.assertRaisesRegex(
                ObservationLifecycleError, "LATE_SUCCESSOR_BACKDATED"
            ):
                activate_schedule(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    schedule_sha256=succ["schedule_sha256"],
                    activation_id="ACT-SUC",
                    now=late,
                    producer_git_sha=GIT,
                )
            store.close()

    def test_draining_without_proven_closed_still_denied(self) -> None:
        predecessor = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        successor = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/successor_y259200.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            pred = register_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                document=predecessor,
                now=NOW,
                producer_git_sha=GIT,
            )
            authorize_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule_sha256=pred["schedule_sha256"],
                phrase=_phrase(predecessor),
                now=NOW,
                producer_git_sha=GIT,
            )
            activate_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule_sha256=pred["schedule_sha256"],
                activation_id="ACT-PRE",
                now=NOW,
                producer_git_sha=GIT,
            )
            store.transition_activation(
                schedule_sha256=pred["schedule_sha256"],
                activation_id="ACT-PRE",
                new_state="DRAINING",
                effective_at=render_utc(NOW),
                payload={},
                clock=NOW,
            )
            succ = register_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                document=successor,
                now=NOW,
                producer_git_sha=GIT,
            )
            authorize_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule_sha256=succ["schedule_sha256"],
                phrase=_phrase(successor),
                now=NOW,
                producer_git_sha=GIT,
            )
            with self.assertRaisesRegex(
                ObservationLifecycleError, "COHORT_CUTOVER_REQUIRED"
            ):
                activate_schedule(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    schedule_sha256=succ["schedule_sha256"],
                    activation_id="ACT-SUC",
                    now=NOW,
                    producer_git_sha=GIT,
                )
            store.close()

    def test_backdated_late_successor_denied(self) -> None:
        predecessor = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        # starts before predecessor stops_admitting_at → backdated repair
        successor = _with_window(
            load_observation_schedule(
                ROOT, "tests/fixtures/observation_schedule/successor_y259200.yaml"
            ),
            starts_at="2026-09-01T12:00:00Z",
            stops_admitting_at="2026-09-03T00:00:00Z",
            schedule_key="OBS-EARLY-PUMPFUN-SUCCESSOR-BACKDATED-001",
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            pred = register_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                document=predecessor,
                now=NOW,
                producer_git_sha=GIT,
            )
            authorize_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule_sha256=pred["schedule_sha256"],
                phrase=_phrase(predecessor),
                now=NOW,
                producer_git_sha=GIT,
            )
            activate_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule_sha256=pred["schedule_sha256"],
                activation_id="ACT-PRE",
                now=NOW,
                producer_git_sha=GIT,
            )
            late = datetime(2026, 9, 2, 1, 0, tzinfo=UTC)
            drain_expired_admission(
                data_root=data_root,
                store=store,
                schedule_sha256=pred["schedule_sha256"],
                activation_id="ACT-PRE",
                now=late,
                producer_git_sha=GIT,
            )
            succ = register_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                document=successor,
                now=late,
                producer_git_sha=GIT,
            )
            authorize_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule_sha256=succ["schedule_sha256"],
                phrase=_phrase(successor),
                now=late,
                producer_git_sha=GIT,
            )
            with self.assertRaisesRegex(
                ObservationLifecycleError, "LATE_SUCCESSOR_BACKDATED"
            ):
                activate_schedule(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    schedule_sha256=succ["schedule_sha256"],
                    activation_id="ACT-SUC",
                    now=late,
                    producer_git_sha=GIT,
                )
            store.close()

    def test_in_window_rollover_still_works(self) -> None:
        predecessor = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        successor = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/successor_y259200.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            pred = register_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                document=predecessor,
                now=NOW,
                producer_git_sha=GIT,
            )
            succ = register_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                document=successor,
                now=NOW,
                producer_git_sha=GIT,
            )
            authorize_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule_sha256=pred["schedule_sha256"],
                phrase=_phrase(predecessor),
                now=NOW,
                producer_git_sha=GIT,
            )
            authorize_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule_sha256=succ["schedule_sha256"],
                phrase=_phrase(successor),
                now=NOW,
                producer_git_sha=GIT,
            )
            activate_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule_sha256=pred["schedule_sha256"],
                activation_id="ACT-PRE",
                now=NOW,
                producer_git_sha=GIT,
            )
            result = rollover_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                predecessor_schedule_sha256=pred["schedule_sha256"],
                predecessor_activation_id="ACT-PRE",
                successor_schedule_sha256=succ["schedule_sha256"],
                successor_activation_id="ACT-SUC",
                cutover_at="2026-09-01T00:20:00Z",
                now=NOW,
                producer_git_sha=GIT,
            )
            self.assertEqual(result["terminal"], "ROLLOVER_COMMITTED")
            store.close()

    def test_read_model_prefers_draining_over_historical_aborted(self) -> None:
        activations = [
            {
                "activation_id": "ACT-1AC239",
                "state": "ABORTED_SAFETY",
                "updated_at": "2026-09-10T00:00:00Z",
                "created_at": "2026-09-01T00:00:00Z",
            },
            {
                "activation_id": "ACT-E0CC",
                "state": "DRAINING",
                "updated_at": "2026-09-20T00:00:00Z",
                "created_at": "2026-09-15T00:00:00Z",
            },
        ]
        current = select_current_activation(activations)
        assert current is not None
        self.assertEqual(current["activation_id"], "ACT-E0CC")
        self.assertEqual(current["state"], "DRAINING")

    def test_read_model_prefers_active_successor_over_draining_and_aborted(self) -> None:
        activations = [
            {
                "activation_id": "ACT-ABORT",
                "state": "ABORTED_SAFETY",
                "updated_at": "2026-09-21T00:00:00Z",
                "created_at": "2026-09-01T00:00:00Z",
            },
            {
                "activation_id": "ACT-DRAIN",
                "state": "DRAINING",
                "updated_at": "2026-09-20T12:00:00Z",
                "created_at": "2026-09-10T00:00:00Z",
            },
            {
                "activation_id": "ACT-SUC",
                "state": "ACTIVE",
                "updated_at": "2026-09-20T12:05:00Z",
                "created_at": "2026-09-20T12:05:00Z",
            },
        ]
        current = select_current_activation(activations)
        assert current is not None
        self.assertEqual(current["activation_id"], "ACT-SUC")

    def test_read_model_keeps_genuine_current_aborted(self) -> None:
        activations = [
            {
                "activation_id": "ACT-OLD",
                "state": "COMPLETE",
                "updated_at": "2026-09-01T00:00:00Z",
                "created_at": "2026-09-01T00:00:00Z",
            },
            {
                "activation_id": "ACT-ABORT",
                "state": "ABORTED_SAFETY",
                "updated_at": "2026-09-20T00:00:00Z",
                "created_at": "2026-09-10T00:00:00Z",
            },
        ]
        current = select_current_activation(activations)
        assert current is not None
        self.assertEqual(current["state"], "ABORTED_SAFETY")

    def test_doctor_skips_historical_aborted_when_draining_current(self) -> None:
        activations = [
            {
                "activation_id": "ACT-1AC239",
                "state": "ABORTED_SAFETY",
                "updated_at": "2026-08-02T00:00:00Z",
                "created_at": "2026-08-01T00:00:00Z",
            },
            {
                "activation_id": "ACT-E0CC",
                "state": "DRAINING",
                "updated_at": "2026-09-02T01:00:00Z",
                "created_at": "2026-09-01T00:10:00Z",
            },
        ]
        report = classify_doctor_current_activation(activations)
        self.assertEqual(report["terminal"], "DOCTOR_CURRENT_OK")
        self.assertEqual(report["current_activation_state"], "DRAINING")
        self.assertEqual(report["current_activation_id"], "ACT-E0CC")
        self.assertFalse(report["live_activation"])
        self.assertNotEqual(report["terminal"], "DOCTOR_ABORTED_SAFETY")

    def test_doctor_exposes_late_recovery_point_and_proof(self) -> None:
        report = classify_doctor_current_activation(
            [
                {
                    "activation_id": "ACT-DRAIN",
                    "schedule_sha256": "d" * 64,
                    "state": "DRAINING",
                    "stops_admitting_at": "2026-09-02T00:00:00Z",
                    "updated_at": "2026-09-02T01:00:00Z",
                    "created_at": "2026-09-01T00:00:00Z",
                    "payload": {
                        "admission_window_closed": True,
                        "transition_effective_at": "2026-09-02T01:00:00Z",
                    },
                }
            ],
            recovery_proofs={
                "ACT-DRAIN": {
                    "late_recovery_at": "2026-09-02T01:00:00Z",
                    "late_recovery_proof": "APPEND_ONLY_DRAINING_TRANSITION",
                }
            },
        )
        self.assertEqual(report["stops_admitting_at"], "2026-09-02T00:00:00Z")
        self.assertEqual(report["late_recovery_at"], "2026-09-02T01:00:00Z")
        self.assertEqual(
            report["late_recovery_proof"], "APPEND_ONLY_DRAINING_TRANSITION"
        )

    def test_lifecycle_denials_have_owner_next_actions(self) -> None:
        self.assertEqual(
            owner_next_action_for_lifecycle_error("LATE_SUCCESSOR_BACKDATED"),
            "REGISTER_AUTHORIZE_FORWARD_SUCCESSOR_FROM_LATE_RECOVERY",
        )
        self.assertEqual(
            owner_next_action_for_lifecycle_error("LATE_SUCCESSOR_RECOVERY_UNPROVEN"),
            "REVALIDATE_DRAINING_RECOVERY_PROOF",
        )

    def test_doctor_reports_genuine_current_aborted(self) -> None:
        activations = [
            {
                "activation_id": "ACT-OLD",
                "state": "COMPLETE",
                "updated_at": "2026-09-01T00:00:00Z",
                "created_at": "2026-09-01T00:00:00Z",
            },
            {
                "activation_id": "ACT-ABORT",
                "state": "ABORTED_SAFETY",
                "updated_at": "2026-09-20T00:00:00Z",
                "created_at": "2026-09-10T00:00:00Z",
            },
        ]
        report = classify_doctor_current_activation(activations)
        self.assertEqual(report["terminal"], "DOCTOR_ABORTED_SAFETY")
        self.assertEqual(report["current_activation_id"], "ACT-ABORT")
        self.assertEqual(report["next_action"], "MUST_NOT_RESUME")

    def test_campaign_successor_attention_emits_once_and_recovers(self) -> None:
        document = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        # Shrink remaining window into the 24h warning band.
        document = _with_window(
            document,
            starts_at="2026-09-01T00:00:00Z",
            stops_admitting_at="2026-09-01T12:00:00Z",
            schedule_key="OBS-EARLY-PUMPFUN-SHORT-WINDOW-001",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_root = root / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(root / "ops.sqlite")
            registered = register_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                document=document,
                now=NOW,
                producer_git_sha=GIT,
            )
            authorize_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule_sha256=registered["schedule_sha256"],
                phrase=_phrase(document),
                now=NOW,
                producer_git_sha=GIT,
            )
            activate_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule_sha256=registered["schedule_sha256"],
                activation_id="ACT-WARN",
                now=NOW,
                producer_git_sha=GIT,
            )
            packet = build_collector_operational_packet(
                root=root,
                store=store,
                now=NOW,
                deploy_git_sha=GIT,
            )
            self.assertTrue(packet["campaign_successor_required"])
            self.assertEqual(packet["campaign_successor_state"], "NONE")
            health = compose_health_classes(packet)
            self.assertIn("CAMPAIGN_SUCCESSOR_REQUIRED", health)
            present = classify_incidents(packet)
            self.assertIn("CAMPAIGN_SUCCESSOR_REQUIRED", present)
            self.assertNotIn("SOURCE_DATA_STALE", present)
            self.assertEqual(INCIDENT_GRACE_SECONDS["CAMPAIGN_SUCCESSOR_REQUIRED"], 0)
            self.assertEqual(INCIDENT_GRACE_SECONDS["SOURCE_DATA_STALE"], 1800)

            first = evaluate_operability(
                root=root,
                store=store,
                now=NOW,
                deploy_git_sha=GIT,
                emit=False,
                persist=True,
                unit_status={
                    "factory-observation-schedule.timer": "active",
                    "factory-remote-backup.timer": "active",
                    "factory-collector-owner-pulse.timer": "active",
                    "factory-hot90-closed-day-archive.timer": "active",
                    "factory-operability-watch.timer": "active",
                    "factory-v1-workbench.service": "active",
                },
            )
            self.assertIn("CAMPAIGN_SUCCESSOR_REQUIRED", first["present"])
            self.assertEqual(
                sum(
                    1
                    for msg in first["messages"]
                    if msg.get("code") == "CAMPAIGN_SUCCESSOR_REQUIRED"
                ),
                1,
            )
            attention_preview = "\n".join(first["preview_messages"])
            self.assertIn("FACTORY / ATTENTION — ACTION", attention_preview)
            self.assertIn("MESSAGE_TYPE=ATTENTION", attention_preview)
            self.assertIn(
                "OWNER_ACTION=CAMPAIGN_SUCCESSOR_REQUIRED", attention_preview
            )
            self.assertIn(
                "ATTENTION=CAMPAIGN_SUCCESSOR_REQUIRED", attention_preview
            )
            self.assertNotIn(
                "INCIDENT=CAMPAIGN_SUCCESSOR_REQUIRED", attention_preview
            )
            self.assertNotIn("FACTORY / INCIDENT — ACTION", attention_preview)
            second = evaluate_operability(
                root=root,
                store=store,
                now=NOW + timedelta(minutes=15),
                deploy_git_sha=GIT,
                emit=False,
                persist=True,
                unit_status={
                    "factory-observation-schedule.timer": "active",
                    "factory-remote-backup.timer": "active",
                    "factory-collector-owner-pulse.timer": "active",
                    "factory-hot90-closed-day-archive.timer": "active",
                    "factory-operability-watch.timer": "active",
                    "factory-v1-workbench.service": "active",
                },
            )
            self.assertIn("CAMPAIGN_SUCCESSOR_REQUIRED", second["present"])
            self.assertEqual(
                [
                    msg
                    for msg in second["messages"]
                    if msg.get("code") == "CAMPAIGN_SUCCESSOR_REQUIRED"
                ],
                [],
            )

            successor = _with_window(
                load_observation_schedule(
                    ROOT, "tests/fixtures/observation_schedule/successor_y259200.yaml"
                ),
                starts_at="2026-09-01T12:00:00Z",
                stops_admitting_at="2026-09-02T12:00:00Z",
                schedule_key="OBS-EARLY-PUMPFUN-SUCCESSOR-WARN-001",
            )
            succ = register_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                document=successor,
                now=NOW,
                producer_git_sha=GIT,
            )
            authorize_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule_sha256=succ["schedule_sha256"],
                phrase=_phrase(successor),
                now=NOW,
                producer_git_sha=GIT,
            )
            continuity = assess_campaign_successor_continuity(
                store,
                now=NOW,
                activation=store.get_activation(
                    registered["schedule_sha256"], "ACT-WARN"
                ),
            )
            self.assertEqual(continuity["campaign_successor_state"], "AUTHORIZED")
            self.assertFalse(continuity["campaign_successor_required"])
            recovered = evaluate_operability(
                root=root,
                store=store,
                now=NOW + timedelta(minutes=30),
                deploy_git_sha=GIT,
                emit=False,
                persist=True,
                unit_status={
                    "factory-observation-schedule.timer": "active",
                    "factory-remote-backup.timer": "active",
                    "factory-collector-owner-pulse.timer": "active",
                    "factory-hot90-closed-day-archive.timer": "active",
                    "factory-operability-watch.timer": "active",
                    "factory-v1-workbench.service": "active",
                },
            )
            self.assertNotIn("CAMPAIGN_SUCCESSOR_REQUIRED", recovered["present"])
            self.assertTrue(
                any(
                    msg.get("kind") == "RECOVERED"
                    and msg.get("code") == "CAMPAIGN_SUCCESSOR_REQUIRED"
                    for msg in recovered["messages"]
                )
            )
            store.close()

    def test_historical_authorized_same_family_does_not_clear_warning(self) -> None:
        current = _with_window(
            load_observation_schedule(
                ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
            ),
            starts_at="2026-09-01T00:00:00Z",
            stops_admitting_at="2026-09-01T12:00:00Z",
            schedule_key="OBS-EARLY-PUMPFUN-CONTINUITY-HIST-CURRENT-001",
        )
        historical = _with_window(
            load_observation_schedule(
                ROOT, "tests/fixtures/observation_schedule/successor_y259200.yaml"
            ),
            starts_at="2026-08-01T00:00:00Z",
            stops_admitting_at="2026-08-02T00:00:00Z",
            schedule_key="OBS-EARLY-PUMPFUN-CONTINUITY-HIST-001",
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            current_registered, _ = _activate_campaign(
                store,
                data_root,
                current,
                activation_id="ACT-CURRENT",
            )
            _register_and_authorize(store, data_root, historical)
            continuity = assess_campaign_successor_continuity(
                store,
                now=NOW,
                activation=store.get_activation(
                    current_registered["schedule_sha256"], "ACT-CURRENT"
                ),
            )
            self.assertEqual(continuity["campaign_successor_state"], "REGISTERED")
            self.assertTrue(continuity["campaign_successor_required"])
            store.close()

    def test_missing_active_registration_keeps_successor_warning_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            continuity = assess_campaign_successor_continuity(
                store,
                now=NOW,
                activation={
                    "schedule_sha256": "e" * 64,
                    "activation_id": "ACT-UNBOUND",
                    "state": "ACTIVE",
                    "stops_admitting_at": "2026-09-01T12:00:00Z",
                },
            )
            self.assertEqual(continuity["campaign_successor_state"], "UNKNOWN")
            self.assertTrue(continuity["campaign_successor_required"])
            self.assertIn("reconcile", continuity["campaign_successor_owner_action"])
            store.close()

    def test_missing_active_boundary_keeps_successor_warning_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            for stops in (None, "not-an-utc-timestamp"):
                continuity = assess_campaign_successor_continuity(
                    store,
                    now=NOW,
                    activation={
                        "schedule_sha256": "f" * 64,
                        "activation_id": "ACT-BOUNDARY-UNKNOWN",
                        "state": "ACTIVE",
                        "stops_admitting_at": stops,
                    },
                )
                self.assertEqual(continuity["campaign_successor_state"], "UNKNOWN")
                self.assertTrue(continuity["campaign_successor_required"])
                self.assertIn("reconcile", continuity["campaign_successor_owner_action"])
            store.close()

    def test_authorized_successor_after_gap_does_not_clear_warning(self) -> None:
        current = _with_window(
            load_observation_schedule(
                ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
            ),
            starts_at="2026-09-01T00:00:00Z",
            stops_admitting_at="2026-09-01T12:00:00Z",
            schedule_key="OBS-EARLY-PUMPFUN-CONTINUITY-GAP-CURRENT-001",
        )
        gap_successor = _with_window(
            load_observation_schedule(
                ROOT, "tests/fixtures/observation_schedule/successor_y259200.yaml"
            ),
            starts_at="2026-09-01T18:00:00Z",
            stops_admitting_at="2026-09-02T18:00:00Z",
            schedule_key="OBS-EARLY-PUMPFUN-CONTINUITY-GAP-001",
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            current_registered, _ = _activate_campaign(
                store,
                data_root,
                current,
                activation_id="ACT-CURRENT",
            )
            _register_and_authorize(store, data_root, gap_successor)
            continuity = assess_campaign_successor_continuity(
                store,
                now=NOW,
                activation=store.get_activation(
                    current_registered["schedule_sha256"], "ACT-CURRENT"
                ),
            )
            self.assertEqual(continuity["campaign_successor_state"], "AUTHORIZED")
            self.assertTrue(continuity["campaign_successor_required"])
            store.close()

    def test_valid_rollover_clears_warning(self) -> None:
        current = _with_window(
            load_observation_schedule(
                ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
            ),
            starts_at="2026-09-01T00:00:00Z",
            stops_admitting_at="2026-09-01T12:00:00Z",
            schedule_key="OBS-EARLY-PUMPFUN-CONTINUITY-ROLLOVER-CURRENT-001",
        )
        successor = _with_window(
            load_observation_schedule(
                ROOT, "tests/fixtures/observation_schedule/successor_y259200.yaml"
            ),
            starts_at="2026-09-01T06:00:00Z",
            stops_admitting_at="2026-09-02T12:00:00Z",
            schedule_key="OBS-EARLY-PUMPFUN-CONTINUITY-ROLLOVER-001",
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            current_registered, _ = _activate_campaign(
                store,
                data_root,
                current,
                activation_id="ACT-CURRENT",
            )
            successor_registered, successor_authority = _register_and_authorize(
                store, data_root, successor
            )
            store.persist_rollover(
                predecessor_schedule_sha256=current_registered["schedule_sha256"],
                predecessor_activation_id="ACT-CURRENT",
                successor_schedule_sha256=successor_registered["schedule_sha256"],
                successor_activation_id="ACT-SUCCESSOR",
                cutover_at="2026-09-01T06:00:00Z",
                authority_receipt_sha256=successor_authority["receipt_sha256"],
                clock=NOW,
            )
            continuity = assess_campaign_successor_continuity(
                store,
                now=NOW,
                activation=store.get_activation(
                    current_registered["schedule_sha256"], "ACT-CURRENT"
                ),
            )
            self.assertEqual(continuity["campaign_successor_state"], "ROLLOVER_READY")
            self.assertFalse(continuity["campaign_successor_required"])
            store.close()

    def test_source_data_stale_unchanged(self) -> None:
        packet = {
            "health_classes": ["DATA_STALE"],
            "activation_state": "ACTIVE",
            "source_poll_age": 200,
            "period_seconds": 60,
            "campaign_successor_required": False,
        }
        # age > period*3 still maps only to SOURCE_DATA_STALE
        found = classify_incidents(
            {
                **packet,
                "health_classes": compose_health_classes(
                    {
                        "activation_state": "ACTIVE",
                        "source_poll_age": 200,
                        "period_seconds": 60,
                        "campaign_successor_required": False,
                        "HTTP_401_24h": 0,
                        "HTTP_403_24h": 0,
                        "HTTP_429_24h": 0,
                        "HTTP_5XX_24h": 0,
                        "TIMEOUT_24h": 0,
                        "TRANSPORT_ERROR_24h": 0,
                        "discovery_coverage_class": "COVERED",
                        "due_pressure": {
                            "pending_due_count": 0,
                            "in_flight_count": 0,
                            "blocked_budget_count": 0,
                            "oldest_overdue_age_seconds": 0,
                            "due_now_count": 0,
                            "claimed_count": 0,
                            "actually_overdue_count": 0,
                        },
                        "blocked_budget": 0,
                        "publication_jobs_open_count": 0,
                        "observation_rdp_last_publish_at": render_utc(NOW),
                        "observed_at": render_utc(NOW),
                        "backup_domain": "ok",
                        "backup_age_seconds": 60,
                        "last_backup_at": render_utc(NOW),
                        "offhost_backup_state": "OK",
                        "immutable_archive_backlog_days": 0,
                        "immutable_archive_last_terminal": "OK",
                        "filesystem_disk_used_pct": 10,
                        "projected_97d_status": "OK",
                        "release_state": "OK",
                        "restore_marker_unresolved": False,
                    }
                ),
            }
        )
        self.assertIn("SOURCE_DATA_STALE", found)
        self.assertNotIn("CAMPAIGN_SUCCESSOR_REQUIRED", found)


if __name__ == "__main__":
    unittest.main()
