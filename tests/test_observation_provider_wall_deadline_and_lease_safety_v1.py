"""OBSERVATION_PROVIDER_WALL_DEADLINE_AND_LEASE_SAFETY_V1 proofs."""

from __future__ import annotations

import sys
import tempfile
import threading
import time
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.observation_primitives import (  # noqa: E402
    execute_primitive,
)
from solana_alpha_lab.factory.observation_provider_wall_deadline import (  # noqa: E402
    DEFAULT_PROVIDER_CALL_WALL_SECONDS,
    PROVIDER_CALL_WALL_DEADLINE,
    ProviderWallDeadlineError,
    WallDeadlineOpener,
    resolve_provider_call_wall_seconds,
    run_with_provider_wall_deadline,
    wrap_opener_with_wall_deadline,
)
from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    canonical_sha256,
    load_observation_schedule,
    render_utc,
)
from solana_alpha_lab.factory.observation_schedule_store import (  # noqa: E402
    LEASE_SECONDS,
    ObservationScheduleStore,
)
from solana_alpha_lab.factory.observation_scheduler import tick_once  # noqa: E402

GIT_SHA = "d" * 40
MINT = "MintWallDeadl11111111111111111111111111111"
NOW = datetime(2026, 9, 1, 0, 10, tzinfo=UTC)


class _FastOpener:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def open(self, url: str) -> dict:
        self.urls.append(url)
        if "/tokens/v2/search" in url:
            return {"http_status": 200, "body": [{"id": MINT, "liquidity": "2000"}]}
        if "/swap/v2/order" in url:
            return {"http_status": 200, "body": {"outAmount": "9900000"}}
        return {"http_status": 200, "body": [{"id": MINT, "firstPool": {"createdAt": "2026-09-01T00:00:00Z"}}]}


class _StallOpener:
    """Simulates a provider op that ignores socket timeouts (sleeps forever-ish)."""

    def __init__(self, stall_seconds: float) -> None:
        self.stall_seconds = stall_seconds
        self.entered = threading.Event()
        self.urls: list[str] = []

    def open(self, url: str) -> dict:
        self.urls.append(url)
        self.entered.set()
        time.sleep(self.stall_seconds)
        return {"http_status": 200, "body": [{"id": MINT}]}


def _activate(store: ObservationScheduleStore, schedule: dict) -> str:
    from solana_alpha_lab.factory.observation_schedule_lifecycle import (
        _authority_policy,
        _minimum_expiry,
        _used_provider_route_ids,
        authorize_schedule,
        expected_authority_phrase,
    )

    activation_id = "ACT-WALL-001"
    data_root = store.path.parent / "rdp"
    data_root.mkdir(parents=True, exist_ok=True)
    store.persist_registered_schedule(
        schedule_sha256=schedule["schedule_sha256"],
        schedule_key=schedule["schedule_key"],
        document=schedule,
        clock=NOW,
    )
    expires_at = render_utc(_minimum_expiry(schedule))
    _, routes = _used_provider_route_ids(ROOT, schedule)
    policy = _authority_policy(
        root=ROOT,
        document=schedule,
        schedule_key=schedule["schedule_key"],
        expires_at=expires_at,
    )
    authority = authorize_schedule(
        root=ROOT,
        data_root=data_root,
        store=store,
        schedule_sha256=schedule["schedule_sha256"],
        phrase=expected_authority_phrase(
            schedule_sha256=schedule["schedule_sha256"],
            schedule_key=schedule["schedule_key"],
            activation_starts_at=schedule["activation"]["starts_at"],
            activation_stops_admitting_at=schedule["activation"]["stops_admitting_at"],
            provider_route_ids=routes,
            expires_at=expires_at,
            policy_digest=canonical_sha256(policy),
        ),
        now=NOW,
        producer_git_sha=GIT_SHA,
    )
    store.upsert_activation(
        {
            "schedule_sha256": schedule["schedule_sha256"],
            "activation_id": activation_id,
            "schedule_key": schedule["schedule_key"],
            "state": "ACTIVE",
            "authority_receipt_sha256": authority["receipt_sha256"],
            "starts_at": schedule["activation"]["starts_at"],
            "stops_admitting_at": schedule["activation"]["stops_admitting_at"],
            "payload": {},
        },
        clock=NOW,
    )
    return activation_id


class WallDeadlineUnitTests(unittest.TestCase):
    def test_wall_default_below_lease(self) -> None:
        self.assertLess(DEFAULT_PROVIDER_CALL_WALL_SECONDS, LEASE_SECONDS)
        self.assertEqual(resolve_provider_call_wall_seconds({}), DEFAULT_PROVIDER_CALL_WALL_SECONDS)
        self.assertEqual(
            resolve_provider_call_wall_seconds({"provider_call_wall_seconds": 45}),
            45,
        )
        with self.assertRaisesRegex(ValueError, "PROVIDER_CALL_WALL_SECONDS_MUST_BE_BELOW_LEASE"):
            resolve_provider_call_wall_seconds({"provider_call_wall_seconds": LEASE_SECONDS})
        with self.assertRaisesRegex(ValueError, "PROVIDER_CALL_WALL_SECONDS_MUST_BE_BELOW_LEASE"):
            resolve_provider_call_wall_seconds({"provider_call_wall_seconds": LEASE_SECONDS + 1})

    def test_stall_beyond_wall_raises_typed_timeout_not_hang(self) -> None:
        started = time.monotonic()
        with self.assertRaises(ProviderWallDeadlineError) as ctx:
            run_with_provider_wall_deadline(
                lambda: time.sleep(30),
                wall_seconds=1,
                heartbeat_every_seconds=0.2,
            )
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 5.0)
        self.assertIn(PROVIDER_CALL_WALL_DEADLINE, str(ctx.exception))

    def test_heartbeat_runs_during_wait(self) -> None:
        beats: list[int] = []

        def heart() -> None:
            beats.append(1)

        with self.assertRaises(ProviderWallDeadlineError):
            run_with_provider_wall_deadline(
                lambda: time.sleep(30),
                wall_seconds=1.0,
                heartbeat=heart,
                heartbeat_every_seconds=0.2,
            )
        self.assertGreaterEqual(len(beats), 2)

    def test_execute_primitive_maps_wall_deadline_to_timeout_missingness(self) -> None:
        opener = WallDeadlineOpener(_StallOpener(30), wall_seconds=1)
        result = execute_primitive(
            primitive_id="PRIM-JUPITER-TOKENS-V2-RECENT-001",
            primitive_version="1.0",
            method="GET",
            url="https://api.jup.ag/tokens/v2/recent",
            opener=opener,
            clock=lambda: NOW,
        )
        self.assertEqual(result["status"], "MISSING_TYPED")
        self.assertEqual(result["missing_reason"], "TIMEOUT")
        self.assertEqual(result["http_class"], "TIMEOUT")

    def test_fast_path_unchanged(self) -> None:
        inner = _FastOpener()
        wrapped = wrap_opener_with_wall_deadline(inner, wall_seconds=30)
        out = wrapped.open("https://api.jup.ag/tokens/v2/recent")  # type: ignore[union-attr]
        self.assertEqual(out["http_status"], 200)
        self.assertEqual(inner.urls, ["https://api.jup.ag/tokens/v2/recent"])

    def test_no_secret_in_wall_error_or_thread_name(self) -> None:
        marker = "WALL_DEADLINE_MARKER_NOT_FOR_TRANSPORT"
        opener = WallDeadlineOpener(_StallOpener(30), wall_seconds=1)
        with self.assertRaises(ProviderWallDeadlineError) as ctx:
            opener.open("https://api.jup.ag/tokens/v2/recent")
        self.assertNotIn(marker, str(ctx.exception))
        self.assertNotIn(marker, PROVIDER_CALL_WALL_DEADLINE)
        self.assertEqual(str(ctx.exception), PROVIDER_CALL_WALL_DEADLINE)


class WallDeadlineTickIntegrationTests(unittest.TestCase):
    def test_stall_over_lease_equivalent_does_not_lease_fence(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        stall = _StallOpener(stall_seconds=30)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            try:
                data_root = Path(tmp) / "rdp"
                data_root.mkdir()
                activation_id = _activate(store, schedule)
                # Wall << LEASE_SECONDS; stall would outlive lease without the wall.
                result = tick_once(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    schedule=schedule,
                    activation_id=activation_id,
                    now=NOW + timedelta(minutes=15),
                    opener=stall,
                    producer_git_sha=GIT_SHA,
                    provider_call_wall_seconds=2,
                )
                self.assertNotEqual(result.get("terminal"), "LEASE_FENCED")
                self.assertIn(
                    result.get("terminal"),
                    {"TICK_COMPLETE", "PACE_WAIT", "TICK_PARTIAL"},
                )
                # Discovery call must not remain STARTED after wall timeout.
                rows = store._conn.execute(
                    "SELECT state FROM call_ledger WHERE primitive_id=?",
                    ("PRIM-JUPITER-TOKENS-V2-RECENT-001",),
                ).fetchall()
                self.assertTrue(rows)
                self.assertTrue(all(str(r[0]) != "STARTED" for r in rows))
                # Lease released after tick.
                held = store._conn.execute(
                    "SELECT owner FROM scheduler_leases WHERE lease_id=?",
                    ("observation-scheduler",),
                ).fetchone()
                self.assertIsNone(held)
            finally:
                store.close()

    def test_restart_after_started_is_in_flight_indeterminate(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            try:
                data_root = Path(tmp) / "rdp"
                data_root.mkdir()
                activation_id = _activate(store, schedule)
                from solana_alpha_lab.factory.observation_primitives import (
                    RECENT_URL,
                    call_occurrence_id,
                    request_sha256,
                )
                from solana_alpha_lab.factory.observation_scheduler import poll_slot_id

                tick_now = NOW + timedelta(minutes=15)
                digest = schedule["schedule_sha256"]
                request_digest = request_sha256(
                    method="GET", url=RECENT_URL, body=None, primitive_version="1.0"
                )
                slot = poll_slot_id(
                    primitive_id=str(schedule["source_poll"]["primitive_id"]),
                    query_profile_id=str(schedule["source_poll"]["query_profile_id"]),
                    period_seconds=int(schedule["source_poll"]["period_seconds"]),
                    now=tick_now,
                    schedule_sha256=digest,
                    activation_id=activation_id,
                )
                occurrence = call_occurrence_id(
                    schedule_sha256=digest,
                    activation_id=activation_id,
                    primitive_id="PRIM-JUPITER-TOKENS-V2-RECENT-001",
                    point_id="DISCOVERY",
                    due_at=slot,
                    claim_identity_set=(),
                    request_digest=request_digest,
                )
                token = store.acquire_lease("crash-sim", clock=tick_now)
                self.assertIsNotNone(token)
                store.start_call(
                    request_sha256=request_digest,
                    call_occurrence_id=occurrence,
                    attempt_id="ATT-CRASH",
                    primitive_id="PRIM-JUPITER-TOKENS-V2-RECENT-001",
                    payload={"url": RECENT_URL, "poll_slot_id": slot},
                    clock=tick_now,
                )
                store.release_lease(str(token))
                self.assertEqual(store.call_state(occurrence), "STARTED")

                fast = _FastOpener()
                result = tick_once(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    schedule=schedule,
                    activation_id=activation_id,
                    now=tick_now,
                    opener=fast,
                    producer_git_sha=GIT_SHA,
                    provider_call_wall_seconds=30,
                )
                self.assertNotEqual(result.get("terminal"), "LEASE_FENCED")
                # Honest: STARTED remains; discovery does not open a retry.
                self.assertEqual(store.call_state(occurrence), "STARTED")
                self.assertTrue(
                    all("/tokens/v2/recent" not in u for u in fast.urls)
                    or result.get("terminal") in {"TICK_COMPLETE", "PACE_WAIT"}
                )
                # No RECENT retry: opener must not have been asked for recent again.
                self.assertEqual(
                    [u for u in fast.urls if "/tokens/v2/recent" in u],
                    [],
                )
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
