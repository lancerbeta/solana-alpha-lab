from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.observation_schedule import (
    canonical_sha256,
    load_observation_schedule,
    parse_utc,
    render_utc,
)
from solana_alpha_lab.factory.observation_schedule_lifecycle import (
    ObservationLifecycleError,
    _authority_policy,
    activate_schedule,
    authorize_schedule,
    complete_draining_schedule,
    expected_authority_phrase,
    pause_schedule,
    register_schedule,
    resume_schedule,
    rollover_schedule,
    status_schedule,
)
from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
from solana_alpha_lab.factory.research_store import ResearchStore
from scripts.observation_schedule import main as cli_main


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


class ObservationScheduleLifecycleTests(unittest.TestCase):
    def test_equivalent_schedule_key_attaches_without_rdp_conflict(self) -> None:
        document = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        equivalent = dict(document)
        equivalent["schedule_key"] = "OBS-ALIAS-PUMPFUN-X300-Y900-001"
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            try:
                first = register_schedule(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    document=document,
                    now=NOW,
                    producer_git_sha=GIT,
                )
                second = register_schedule(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    document=equivalent,
                    now=NOW,
                    producer_git_sha=GIT,
                )
                self.assertEqual(second["terminal"], "ATTACHED_TO_EXISTING_PLAN")
                registered = store.get_registered_schedule(first["schedule_sha256"])
                self.assertIsNotNone(registered)
                assert registered is not None
                self.assertEqual(
                    {item["schedule_key"] for item in registered["aliases"]},
                    {document["schedule_key"], equivalent["schedule_key"]},
                )
            finally:
                store.close()

    def test_register_authorize_activate_pause_status_are_durable(self) -> None:
        document = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            registered = register_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                document=document,
                now=NOW,
                producer_git_sha=GIT,
            )
            self.assertEqual(registered["terminal"], "REGISTERED")
            digest = registered["schedule_sha256"]
            again = register_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                document=document,
                now=NOW,
                producer_git_sha=GIT,
            )
            self.assertEqual(again["terminal"], "REGISTER_REPLAY")
            auth = authorize_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule_sha256=digest,
                phrase=_phrase(document),
                now=NOW,
                producer_git_sha=GIT,
            )
            self.assertEqual(auth["terminal"], "AUTHORIZED")
            activated = activate_schedule(
                data_root=data_root,
                store=store,
                schedule_sha256=digest,
                activation_id="ACT-OBS-LIFE-001",
                now=NOW,
                producer_git_sha=GIT,
            )
            self.assertEqual(activated["terminal"], "ACTIVATED")
            with self.assertRaisesRegex(ObservationLifecycleError, "ACTIVATION_ALREADY_LIVE"):
                activate_schedule(
                    data_root=data_root,
                    store=store,
                    schedule_sha256=digest,
                    activation_id="ACT-OBS-LIFE-LIVE-2",
                    now=NOW,
                    producer_git_sha=GIT,
                )
            paused = pause_schedule(
                data_root=data_root,
                store=store,
                schedule_sha256=digest,
                activation_id="ACT-OBS-LIFE-001",
                now=NOW,
                producer_git_sha=GIT,
            )
            self.assertEqual(paused["terminal"], "PAUSED")
            with self.assertRaisesRegex(ObservationLifecycleError, "ACTIVATION_ALREADY_LIVE"):
                activate_schedule(
                    data_root=data_root,
                    store=store,
                    schedule_sha256=digest,
                    activation_id="ACT-OBS-LIFE-LIVE-3",
                    now=NOW,
                    producer_git_sha=GIT,
                )
            still = activate_schedule(
                data_root=data_root,
                store=store,
                schedule_sha256=digest,
                activation_id="ACT-OBS-LIFE-001",
                now=NOW,
                producer_git_sha=GIT,
            )
            self.assertEqual(still["terminal"], "ACTIVATE_STILL_PAUSED")
            self.assertEqual(still["next_action"], "RESUME")
            resumed = resume_schedule(
                data_root=data_root,
                store=store,
                schedule_sha256=digest,
                activation_id="ACT-OBS-LIFE-001",
                now=NOW,
                producer_git_sha=GIT,
            )
            self.assertEqual(resumed["terminal"], "RESUMED")
            replay = resume_schedule(
                data_root=data_root,
                store=store,
                schedule_sha256=digest,
                activation_id="ACT-OBS-LIFE-001",
                now=NOW,
                producer_git_sha=GIT,
            )
            self.assertEqual(replay["terminal"], "RESUME_REPLAY")
            status = status_schedule(
                store,
                schedule_sha256=digest,
                activation_id="ACT-OBS-LIFE-001",
            )
            self.assertEqual(status["terminal"], "STATUS")
            self.assertEqual(status["activations"][0]["state"], "ACTIVE")
            store.close()

    def test_activate_without_authority_fails_before_network(self) -> None:
        document = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            registered = register_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                document=document,
                now=NOW,
                producer_git_sha=GIT,
            )
            with self.assertRaisesRegex(ObservationLifecycleError, "AUTHORITY_MISSING"):
                activate_schedule(
                    data_root=data_root,
                    store=store,
                    schedule_sha256=registered["schedule_sha256"],
                    activation_id="ACT-OBS-LIFE-002",
                    now=NOW,
                    producer_git_sha=GIT,
                )
            with self.assertRaisesRegex(ObservationLifecycleError, "BLOCKED_AUTHORITY"):
                authorize_schedule(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    schedule_sha256=registered["schedule_sha256"],
                    phrase="garbage",
                    now=NOW,
                    producer_git_sha=GIT,
                )
            exact = _phrase(document)
            with self.assertRaisesRegex(ObservationLifecycleError, "BLOCKED_AUTHORITY"):
                authorize_schedule(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    schedule_sha256=registered["schedule_sha256"],
                    phrase=exact[:-1] + ("A" if exact[-1] != "A" else "B"),
                    now=NOW,
                    producer_git_sha=GIT,
                )
            store.close()

    def test_repeated_pause_resume_transitions_have_distinct_rdp_ids(self) -> None:
        document = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            registered = register_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                document=document,
                now=NOW,
                producer_git_sha=GIT,
            )
            digest = registered["schedule_sha256"]
            authorize_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule_sha256=digest,
                phrase=_phrase(document),
                now=NOW,
                producer_git_sha=GIT,
            )
            activate_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule_sha256=digest,
                activation_id="ACT-OBS-LIFE-REPEAT",
                now=NOW,
                producer_git_sha=GIT,
            )
            first_pause = pause_schedule(
                data_root=data_root,
                store=store,
                schedule_sha256=digest,
                activation_id="ACT-OBS-LIFE-REPEAT",
                now=NOW,
                producer_git_sha=GIT,
            )
            resume_schedule(
                data_root=data_root,
                store=store,
                schedule_sha256=digest,
                activation_id="ACT-OBS-LIFE-REPEAT",
                now=NOW,
                producer_git_sha=GIT,
            )
            second_pause = pause_schedule(
                data_root=data_root,
                store=store,
                schedule_sha256=digest,
                activation_id="ACT-OBS-LIFE-REPEAT",
                now=NOW,
                producer_git_sha=GIT,
            )
            self.assertNotEqual(
                first_pause["transition_event_id"],
                second_pause["transition_event_id"],
            )
            events = [
                item
                for item in ResearchStore(data_root).iter_committed_records()
                if str(item.record_kind) == "OBSERVATION_SCHEDULE_STATE"
            ]
            self.assertEqual(len(events), 4)
            self.assertEqual(len({item.record_id for item in events}), 4)
            final_state = json.loads(
                max(
                    events,
                    key=lambda item: json.loads(item.payload_json)["transition_sequence"],
                ).payload_json
            )["state"]
            self.assertEqual(final_state, "PAUSED_OPERATOR")
            store.close()

    def test_draining_completion_waits_for_terminal_due_work(self) -> None:
        document = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            registered = register_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                document=document,
                now=NOW,
                producer_git_sha=GIT,
            )
            digest = registered["schedule_sha256"]
            authorize_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule_sha256=digest,
                phrase=_phrase(document),
                now=NOW,
                producer_git_sha=GIT,
            )
            activate_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule_sha256=digest,
                activation_id="ACT-OBS-DRAIN",
                now=NOW,
                producer_git_sha=GIT,
            )
            store.transition_activation(
                schedule_sha256=digest,
                activation_id="ACT-OBS-DRAIN",
                new_state="DRAINING",
                effective_at="2026-09-01T00:20:00Z",
                clock=NOW,
            )
            due = {
                "schedule_sha256": digest,
                "activation_id": "ACT-OBS-DRAIN",
                "entity_id": "MintDrain",
                "point_id": "X300",
                "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                "state": "PENDING",
                "due_at": "2026-09-01T00:21:00Z",
                "deadline_at": "2026-09-01T00:25:00Z",
                "payload": {},
            }
            store.insert_due(due, clock=NOW)
            pending = complete_draining_schedule(
                data_root=data_root,
                store=store,
                schedule_sha256=digest,
                activation_id="ACT-OBS-DRAIN",
                now=NOW,
                producer_git_sha=GIT,
            )
            self.assertEqual(pending["terminal"], "DRAINING_PENDING")
            self.assertEqual(
                store.get_activation(digest, "ACT-OBS-DRAIN")["state"],
                "DRAINING",
            )
            store.insert_due({**due, "state": "CENSORED"}, clock=NOW)
            completed = complete_draining_schedule(
                data_root=data_root,
                store=store,
                schedule_sha256=digest,
                activation_id="ACT-OBS-DRAIN",
                now=NOW,
                producer_git_sha=GIT,
            )
            self.assertEqual(completed["terminal"], "COMPLETED")
            self.assertEqual(
                store.get_activation(digest, "ACT-OBS-DRAIN")["state"],
                "COMPLETE",
            )
            store.close()

    def test_rollover_binds_one_cutover_and_is_idempotent(self) -> None:
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
            predecessor_result = register_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                document=predecessor,
                now=NOW,
                producer_git_sha=GIT,
            )
            successor_result = register_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                document=successor,
                now=NOW,
                producer_git_sha=GIT,
            )
            predecessor_digest = predecessor_result["schedule_sha256"]
            successor_digest = successor_result["schedule_sha256"]
            authorize_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule_sha256=predecessor_digest,
                phrase=_phrase(predecessor),
                now=NOW,
                producer_git_sha=GIT,
            )
            authorize_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule_sha256=successor_digest,
                phrase=_phrase(successor),
                now=NOW,
                producer_git_sha=GIT,
            )
            activate_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule_sha256=predecessor_digest,
                activation_id="ACT-PRE",
                now=NOW,
                producer_git_sha=GIT,
            )
            first = rollover_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                predecessor_schedule_sha256=predecessor_digest,
                predecessor_activation_id="ACT-PRE",
                successor_schedule_sha256=successor_digest,
                successor_activation_id="ACT-SUC",
                cutover_at="2026-09-01T00:20:00Z",
                now=NOW,
                producer_git_sha=GIT,
            )
            second = rollover_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                predecessor_schedule_sha256=predecessor_digest,
                predecessor_activation_id="ACT-PRE",
                successor_schedule_sha256=successor_digest,
                successor_activation_id="ACT-SUC",
                cutover_at="2026-09-01T00:20:00Z",
                now=NOW,
                producer_git_sha=GIT,
            )
            self.assertEqual(first["terminal"], "ROLLOVER_COMMITTED")
            self.assertEqual(second["terminal"], "ROLLOVER_REPLAY")
            self.assertEqual(len(store.list_rollovers()), 1)
            self.assertEqual(
                store.get_activation(predecessor_digest, "ACT-PRE")["state"],
                "DRAINING",
            )
            self.assertEqual(
                store.get_activation(successor_digest, "ACT-SUC")["state"],
                "ACTIVE",
            )
            store.close()

    def test_same_cohort_second_active_without_cutover_is_denied(self) -> None:
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

    def test_pause_resume_preserves_authority_receipt_identity(self) -> None:
        document = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
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
            activated = activate_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule_sha256=registered["schedule_sha256"],
                activation_id="ACT-OBS-AUTH-ID",
                now=NOW,
                producer_git_sha=GIT,
            )
            before = store.get_activation(
                registered["schedule_sha256"], "ACT-OBS-AUTH-ID"
            )
            assert before is not None
            receipt_before = before["authority_receipt_sha256"]
            self.assertEqual(activated["receipt_sha256"], receipt_before)
            pause_schedule(
                data_root=data_root,
                store=store,
                schedule_sha256=registered["schedule_sha256"],
                activation_id="ACT-OBS-AUTH-ID",
                now=NOW,
                producer_git_sha=GIT,
            )
            resume_schedule(
                data_root=data_root,
                store=store,
                schedule_sha256=registered["schedule_sha256"],
                activation_id="ACT-OBS-AUTH-ID",
                now=NOW + timedelta(seconds=1),
                producer_git_sha=GIT,
            )
            after = store.get_activation(
                registered["schedule_sha256"], "ACT-OBS-AUTH-ID"
            )
            assert after is not None
            self.assertEqual(after["authority_receipt_sha256"], receipt_before)
            self.assertEqual(after["state"], "ACTIVE")
            store.close()

    def test_authority_binds_used_routes_and_covers_last_admitted_horizon(self) -> None:
        from solana_alpha_lab.factory.observation_primitive_registry import (
            load_observation_primitive_registry,
        )
        from solana_alpha_lab.factory.observation_schedule_lifecycle import (
            _minimum_expiry,
            _used_provider_route_ids,
        )

        document = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            registered = register_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                document=document,
                now=NOW,
                producer_git_sha=GIT,
            )
            authorized = authorize_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule_sha256=registered["schedule_sha256"],
                phrase=_phrase(document),
                now=NOW,
                producer_git_sha=GIT,
            )
            receipt = store.get_authority(authorized["receipt_sha256"])
            self.assertIsNotNone(receipt)
            assert receipt is not None
            primitive_ids, routes = _used_provider_route_ids(ROOT, document)
            self.assertEqual(receipt["used_primitive_ids"], primitive_ids)
            self.assertEqual(receipt["provider_route_ids"], routes)
            registry = load_observation_primitive_registry(ROOT)
            used = set(primitive_ids)
            unused_primitives = sorted(set(registry.primitives) - used)
            self.assertTrue(unused_primitives)
            for primitive_id in unused_primitives:
                self.assertNotIn(primitive_id, receipt["used_primitive_ids"])
            # Unused primitives may share a provider route with used ones
            # (1M quote primitives reuse the Fast Lane Jupiter swap endpoint).
            # Exclusive unused routes must not leak into this schedule's receipt.
            used_routes = set(routes)
            exclusive_unused_routes = {
                str(route)
                for primitive_id in unused_primitives
                for route in registry.require_primitive(primitive_id)["provider_route_ids"]
                if str(route) not in used_routes
            }
            self.assertTrue(exclusive_unused_routes.isdisjoint(receipt["provider_route_ids"]))
            self.assertEqual(
                receipt["expires_at"],
                render_utc(_minimum_expiry(document)),
            )
            store.close()

    def test_cli_stubs_are_gone(self) -> None:
        from io import StringIO
        from contextlib import redirect_stdout

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            buf = StringIO()
            with redirect_stdout(buf):
                code = cli_main(
                    [
                        "doctor",
                        "--runtime-config",
                        "tests/fixtures/observation_schedule/runtime_commissioning.yaml",
                        "--data-root",
                        str(data_root.resolve()),
                    ]
                )
        payload = json.loads(buf.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(payload["terminal"], "DOCTOR_NO_LIVE_ACTIVATION")
        self.assertNotIn("_RECORDED", payload["terminal"])


if __name__ == "__main__":
    unittest.main()
