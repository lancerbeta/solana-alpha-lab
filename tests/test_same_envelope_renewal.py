from __future__ import annotations

import json
import sys
import tempfile
import unittest
from unittest import mock
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.collector_read_model import project_activation_as_of
from solana_alpha_lab.factory.observation_schedule import (
    load_observation_schedule,
    parse_utc,
    render_utc,
    schedule_from_observation_request,
)
from solana_alpha_lab.factory.observation_schedule_lifecycle import (
    _authority_policy,
    _minimum_expiry,
    _used_provider_route_ids,
    activate_schedule,
    authorize_schedule,
    expected_authority_phrase,
    register_schedule,
)
from solana_alpha_lab.factory.observation_schedule import canonical_sha256
from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
from solana_alpha_lab.factory.same_envelope_renewal import (
    _budgets_match,
    _shift_source,
    renew_same_envelope,
    successor_activation_id,
)

GIT = "c" * 40
FIXTURE = "tests/fixtures/observation_schedule/x300_y900.yaml"


def _phrase(root: Path, document: dict) -> str:
    _primitives, routes = _used_provider_route_ids(root, document)
    del _primitives
    expires_at = render_utc(_minimum_expiry(document))
    policy = _authority_policy(
        root=root,
        document=document,
        schedule_key=document["schedule_key"],
        expires_at=expires_at,
    )
    return expected_authority_phrase(
        schedule_sha256=document["schedule_sha256"],
        schedule_key=document["schedule_key"],
        activation_starts_at=document["activation"]["starts_at"],
        activation_stops_admitting_at=document["activation"]["stops_admitting_at"],
        provider_route_ids=routes,
        expires_at=expires_at,
        policy_digest=canonical_sha256(policy),
    )


def _source_window() -> dict:
    loaded = load_observation_schedule(ROOT, FIXTURE)
    source = schedule_from_observation_request(loaded)
    source.pop("schedule_sha256", None)
    return source


class SameEnvelopeRenewalTests(unittest.TestCase):
    def _live(self, store: ObservationScheduleStore, data_root: Path, *, key: str | None = None):
        source = _source_window()
        if key is not None:
            source["schedule_key"] = key
        registered = register_schedule(
            root=ROOT,
            data_root=data_root,
            store=store,
            document=source,
            now=parse_utc(source["activation"]["starts_at"]),
            producer_git_sha=GIT,
        )
        digest = registered["schedule_sha256"]
        stored = store.get_registered_schedule(digest)["document"]
        authorize_schedule(
            root=ROOT,
            data_root=data_root,
            store=store,
            schedule_sha256=digest,
            phrase=_phrase(ROOT, stored),
            now=parse_utc(source["activation"]["starts_at"]),
            producer_git_sha=GIT,
        )
        activate_schedule(
            root=ROOT,
            data_root=data_root,
            store=store,
            schedule_sha256=digest,
            activation_id="ACT-LIVE",
            now=parse_utc(source["activation"]["starts_at"]) + timedelta(hours=1),
            producer_git_sha=GIT,
        )
        return stored

    def test_inside_lead_commits_rollover_at_the_boundary_not_now(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            try:
                document = self._live(store, data_root)
                stops = parse_utc(document["activation"]["stops_admitting_at"])
                now = stops - timedelta(hours=12)
                store._conn.execute(
                    """
                    INSERT INTO schedule_activations(
                        schedule_sha256, activation_id, schedule_key, state,
                        authority_receipt_sha256, starts_at, stops_admitting_at,
                        payload_json, created_at, updated_at, transition_sequence,
                        last_transition_event_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "b" * 64,
                        "ACT-OLD",
                        "OBS-OLD-DRAINING",
                        "DRAINING",
                        "d" * 64,
                        "2026-08-01T00:00:00Z",
                        "2026-08-02T00:00:00Z",
                        json.dumps(
                            {
                                "prior_state": "ACTIVE",
                                "new_state": "DRAINING",
                                "transition_effective_at": "2026-08-02T00:00:00Z",
                            }
                        ),
                        "2026-08-02T00:00:00Z",
                        "2026-08-02T00:00:00Z",
                        2,
                        "evt-old",
                    ),
                )
                store._conn.commit()
                first = renew_same_envelope(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    now=now,
                    producer_git_sha=GIT,
                )
                self.assertEqual(first["terminal"], "RENEWED")
                self.assertNotIn("AUTHORIZE OBSERVATION SCHEDULE", json.dumps(first))
                successor_sha = first["successor_schedule_sha256"]
                successor_id = successor_activation_id(successor_sha)
                successor = store.get_activation(successor_sha, successor_id)
                self.assertEqual(successor["state"], "ACTIVE")
                self.assertEqual(
                    successor["payload"]["transition_effective_at"],
                    render_utc(stops),
                )
                self.assertEqual(
                    str(project_activation_as_of(successor, now).get("state")),
                    "UNKNOWN",
                )
                predecessor = store.get_activation(
                    document["schedule_sha256"], "ACT-LIVE"
                )
                self.assertEqual(predecessor["state"], "DRAINING")
                self.assertEqual(
                    str(project_activation_as_of(predecessor, now).get("state")),
                    "ACTIVE",
                )
                self.assertEqual(len(store.list_rollovers()), 1)
                second = renew_same_envelope(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    now=now + timedelta(hours=1),
                    producer_git_sha=GIT,
                )
                self.assertEqual(second["terminal"], "ALREADY_PROVEN")
                self.assertEqual(len(store.list_rollovers()), 1)
            finally:
                store.close()

    def test_too_early_and_past_cutover_do_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            try:
                document = self._live(store, data_root)
                stops = parse_utc(document["activation"]["stops_admitting_at"])
                with mock.patch(
                    "solana_alpha_lab.factory.same_envelope_renewal.RENEW_LEAD",
                    timedelta(hours=1),
                ):
                    early = renew_same_envelope(
                        root=ROOT,
                        data_root=data_root,
                        store=store,
                        now=stops - timedelta(hours=6),
                        producer_git_sha=GIT,
                    )
                self.assertEqual(early["terminal"], "TOO_EARLY")
                past = renew_same_envelope(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    now=stops + timedelta(seconds=1),
                    producer_git_sha=GIT,
                )
                self.assertEqual(past["terminal"], "REFUSED_PAST_CUTOVER")
                self.assertEqual(store.list_rollovers(), [])
            finally:
                store.close()

    def test_two_projected_active_rows_refuse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            try:
                self._live(store, data_root)
                store._conn.execute(
                    """
                    INSERT INTO schedule_activations(
                        schedule_sha256, activation_id, schedule_key, state,
                        authority_receipt_sha256, starts_at, stops_admitting_at,
                        payload_json, created_at, updated_at, transition_sequence,
                        last_transition_event_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "e" * 64,
                        "ACT-OTHER",
                        "OBS-EARLY-OTHER",
                        "ACTIVE",
                        "f" * 64,
                        "2026-09-01T00:00:00Z",
                        "2026-09-02T00:00:00Z",
                        json.dumps(
                            {
                                "prior_state": "UNREGISTERED",
                                "new_state": "ACTIVE",
                                "transition_effective_at": "2026-09-01T00:00:00Z",
                            }
                        ),
                        "2026-09-01T00:00:00Z",
                        "2026-09-01T00:00:00Z",
                        1,
                        "evt-other",
                    ),
                )
                store._conn.commit()
                result = renew_same_envelope(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    now=datetime(2026, 9, 6, tzinfo=UTC),
                    producer_git_sha=GIT,
                )
                self.assertEqual(result["terminal"], "REFUSED_AMBIGUOUS")
                self.assertEqual(store.list_rollovers(), [])
            finally:
                store.close()

    def test_busy_writer_does_not_write_or_spin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            try:
                document = self._live(store, data_root)
                stops = parse_utc(document["activation"]["stops_admitting_at"])
                expires = render_utc(datetime.now(UTC) + timedelta(hours=1))
                store._conn.execute(
                    """
                    INSERT INTO scheduler_leases(
                        lease_id, owner, lease_token, expires_at, created_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        "observation-scheduler",
                        "tick",
                        "held",
                        expires,
                        expires,
                    ),
                )
                store._conn.commit()
                result = renew_same_envelope(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    now=stops - timedelta(hours=12),
                    producer_git_sha=GIT,
                    lease_wait_seconds=0,
                    sleep=lambda _seconds: None,
                )
                self.assertEqual(result["terminal"], "REFUSED_PROOF")
                self.assertEqual(result["detail"], "WRITER_BUSY")
                self.assertEqual(store.list_rollovers(), [])
            finally:
                store.close()

    def test_seed_change_is_not_a_pure_shift(self) -> None:
        loaded = load_observation_schedule(ROOT, FIXTURE)
        shifted = _shift_source(loaded)
        self.assertIsNotNone(shifted)
        assert shifted is not None
        shifted["sampling"]["seed"] = "DIFFERENT"
        self.assertFalse(_budgets_match(ROOT, loaded, shifted))
