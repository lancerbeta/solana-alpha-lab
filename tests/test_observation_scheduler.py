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

from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    load_observation_schedule,
)
from solana_alpha_lab.factory.observation_schedule_store import (  # noqa: E402
    ObservationScheduleStore,
)
from solana_alpha_lab.factory.observation_scheduler import (  # noqa: E402
    ObservationSchedulerError,
    apply_recovery_gap,
    tick_once,
)
from scripts.observation_schedule import main as cli_main  # noqa: E402


GIT_SHA = "c" * 40
MINT = "Mint111111111111111111111111111111111111111"
NOW = datetime(2026, 9, 1, 0, 10, tzinfo=UTC)


class _Opener:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def open(self, url: str) -> dict:
        self.urls.append(url)
        if "/tokens/v2/search" in url:
            return {"http_status": 200, "body": [{"id": MINT, "liquidity": "2000"}]}
        if "/swap/v2/order" in url:
            return {"http_status": 200, "body": {"outAmount": "9900000"}}
        return {"http_status": 200, "body": [{"id": MINT}]}


def _activate(store: ObservationScheduleStore, schedule: dict) -> str:
    activation_id = "ACT-OBS-001"
    store.upsert_activation(
        {
            "schedule_sha256": schedule["schedule_sha256"],
            "activation_id": activation_id,
            "schedule_key": schedule["schedule_key"],
            "state": "ACTIVE",
            "starts_at": schedule["activation"]["starts_at"],
            "stops_admitting_at": schedule["activation"]["stops_admitting_at"],
            "payload": {},
        },
        clock=NOW,
    )
    return activation_id


class ObservationSchedulerTests(unittest.TestCase):
    def test_tick_admits_and_observes_due_x_without_live_network(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            activation_id = _activate(store, schedule)
            opener = _Opener()
            try:
                result = tick_once(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    schedule=schedule,
                    activation_id=activation_id,
                    now=NOW,
                    opener=opener,
                    producer_git_sha=GIT_SHA,
                    discovery_rows=[
                        {
                            "id": MINT,
                            "liquidity": "2000",
                            "firstPool": {
                                "createdAt": "2026-09-01T00:00:00Z",
                                "source": "pump.fun",
                            },
                        }
                    ],
                )
                self.assertEqual(result["terminal"], "TICK_COMPLETE")
                self.assertGreater(result["provider_calls"], 0)
                self.assertEqual(result["credential_reads"], 0)
                self.assertTrue(opener.urls)
            finally:
                store.close()

    def test_started_call_is_not_replayed(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            activation_id = _activate(store, schedule)
            store.insert_due(
                {
                    "schedule_sha256": schedule["schedule_sha256"],
                    "activation_id": activation_id,
                    "entity_id": MINT,
                    "point_id": "X300",
                    "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                    "state": "PENDING",
                    "due_at": "2026-09-01T00:05:00Z",
                    "deadline_at": "2026-09-01T00:10:00Z",
                    "payload": {},
                },
                clock=NOW,
            )
            from solana_alpha_lab.factory.observation_primitives import (
                request_sha256,
                search_url,
            )

            digest = request_sha256(
                method="GET",
                url=search_url([MINT]),
                body=None,
                primitive_version="1.0",
            )
            store.start_call(
                request_sha256=digest,
                attempt_id="ATT-PRIOR",
                primitive_id="PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                payload={"url": search_url([MINT])},
                clock=NOW,
            )
            opener = _Opener()
            tick_once(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule=schedule,
                activation_id=activation_id,
                now=NOW,
                opener=opener,
                producer_git_sha=GIT_SHA,
                discovery_rows=[],
            )
            self.assertEqual(opener.urls, [])
            self.assertEqual(store.due_counts().get("IN_FLIGHT_CALL_INDETERMINATE"), 1)
            store.close()

    def test_late_claim_is_censored(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            activation_id = _activate(store, schedule)
            store.insert_due(
                {
                    "schedule_sha256": schedule["schedule_sha256"],
                    "activation_id": activation_id,
                    "entity_id": MINT,
                    "point_id": "Y900",
                    "primitive_id": "PRIM-JUPITER-SWAP-V2-DEPENDENT-REVERSE-SELL-001",
                    "state": "PENDING",
                    "due_at": "2026-09-01T00:15:00Z",
                    "deadline_at": "2026-09-01T00:17:00Z",
                    "payload": {},
                },
                clock=NOW,
            )
            opener = _Opener()
            tick_once(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule=schedule,
                activation_id=activation_id,
                now=datetime(2026, 9, 1, 0, 20, tzinfo=UTC),
                opener=opener,
                producer_git_sha=GIT_SHA,
                discovery_rows=[],
            )
            self.assertEqual(opener.urls, [])
            self.assertEqual(store.due_counts().get("CENSORED"), 1)
            store.close()

    def test_clock_backward_and_restore_marker_refuse_tick(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            activation_id = _activate(store, schedule)
            with self.assertRaisesRegex(ObservationSchedulerError, "CLOCK_WENT_BACKWARDS"):
                tick_once(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    schedule=schedule,
                    activation_id=activation_id,
                    now=NOW,
                    last_tick_at=NOW + timedelta(seconds=5),
                    producer_git_sha=GIT_SHA,
                )
            store.set_restore_marker("RECOVERY-001", clock=NOW)
            with self.assertRaisesRegex(ObservationSchedulerError, "RESTORE_MARKER_UNRESOLVED"):
                tick_once(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    schedule=schedule,
                    activation_id=activation_id,
                    now=NOW,
                    producer_git_sha=GIT_SHA,
                )
            store.close()

    def test_recovery_gap_marks_pending_censored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            store.insert_due(
                {
                    "schedule_sha256": "a" * 64,
                    "activation_id": "ACT-OBS-001",
                    "entity_id": MINT,
                    "point_id": "X300",
                    "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                    "state": "PENDING",
                    "due_at": "2026-09-01T00:05:00Z",
                    "deadline_at": "2026-09-01T00:10:00Z",
                    "payload": {},
                },
                clock=NOW,
            )
            changed = apply_recovery_gap(store, cutoff=NOW)
            self.assertEqual(changed, 1)
            self.assertEqual(store.due_counts().get("CENSORED"), 1)
            store.close()

    def test_cli_tick_refuses_live_default(self) -> None:
        from contextlib import redirect_stdout
        from io import StringIO

        with tempfile.TemporaryDirectory() as tmp:
            buf = StringIO()
            with redirect_stdout(buf):
                code = cli_main(
                    [
                        "tick",
                        "--once",
                        "--data-root",
                        str(Path(tmp).resolve()),
                        "--schedule-sha256",
                        "a" * 64,
                        "--activation-id",
                        "ACT-OBS-001",
                    ]
                )
            self.assertEqual(code, 2)
            self.assertIn("TICK_REFUSED_NO_LIVE_DEFAULT", buf.getvalue())

    def test_dependent_sell_without_buy_out_is_dependency_missing(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            activation_id = _activate(store, schedule)
            store.insert_due(
                {
                    "schedule_sha256": schedule["schedule_sha256"],
                    "activation_id": activation_id,
                    "entity_id": MINT,
                    "point_id": "Y900",
                    "primitive_id": "PRIM-JUPITER-SWAP-V2-DEPENDENT-REVERSE-SELL-001",
                    "state": "PENDING",
                    "due_at": "2026-09-01T00:05:00Z",
                    "deadline_at": "2026-09-01T00:20:00Z",
                    "payload": {},
                },
                clock=NOW,
            )
            opener = _Opener()
            tick_once(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule=schedule,
                activation_id=activation_id,
                now=NOW,
                opener=opener,
                producer_git_sha=GIT_SHA,
                discovery_rows=[],
            )
            self.assertEqual(opener.urls, [])
            self.assertEqual(store.due_counts().get("DEPENDENCY_MISSING"), 1)
            store.close()

    def test_claimed_started_is_classified_without_replay(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            activation_id = _activate(store, schedule)
            store.insert_due(
                {
                    "schedule_sha256": schedule["schedule_sha256"],
                    "activation_id": activation_id,
                    "entity_id": MINT,
                    "point_id": "X300",
                    "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                    "state": "CLAIMED",
                    "due_at": "2026-09-01T00:05:00Z",
                    "deadline_at": "2026-09-01T00:20:00Z",
                    "payload": {},
                },
                clock=NOW,
            )
            from solana_alpha_lab.factory.observation_primitives import (
                request_sha256,
                search_url,
            )

            digest = request_sha256(
                method="GET",
                url=search_url([MINT]),
                body=None,
                primitive_version="1.0",
            )
            store.start_call(
                request_sha256=digest,
                attempt_id="ATT-CRASH",
                primitive_id="PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                payload={"url": search_url([MINT])},
                clock=NOW,
            )
            opener = _Opener()
            tick_once(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule=schedule,
                activation_id=activation_id,
                now=NOW,
                opener=opener,
                producer_git_sha=GIT_SHA,
                discovery_rows=[],
            )
            self.assertEqual(opener.urls, [])
            self.assertEqual(store.due_counts().get("IN_FLIGHT_CALL_INDETERMINATE"), 1)
            store.close()

    def test_population_predicate_fail_closed(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            activation_id = _activate(store, schedule)
            opener = _Opener()
            result = tick_once(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule=schedule,
                activation_id=activation_id,
                now=NOW,
                opener=opener,
                producer_git_sha=GIT_SHA,
                discovery_rows=[
                    {
                        "id": MINT,
                        "liquidity": "10",
                        "firstPool": {
                            "createdAt": "2026-09-01T00:00:00Z",
                            "source": "other",
                        },
                    }
                ],
            )
            self.assertEqual(result["provider_calls"], 0)
            self.assertEqual(store.due_counts(), {})
            store.close()

    def test_all_predicate_operators_are_typed(self) -> None:
        from solana_alpha_lab.factory.observation_scheduler import _predicate_holds

        row = {
            "id": MINT,
            "liquidity": "2500",
            "firstPool": {"createdAt": "2026-09-01T00:00:00Z", "source": "pump.fun"},
        }
        self.assertTrue(
            _predicate_holds(
                {"field_id": "FIELD-LIQUIDITY-USD-001", "operator": "EQ", "value_decimal": "2500"},
                row,
            )
        )
        self.assertTrue(
            _predicate_holds(
                {"field_id": "FIELD-LIQUIDITY-USD-001", "operator": "NEQ", "value_decimal": "1"},
                row,
            )
        )
        self.assertTrue(
            _predicate_holds(
                {"field_id": "FIELD-LIQUIDITY-USD-001", "operator": "GT", "value_decimal": "1000"},
                row,
            )
        )
        self.assertTrue(
            _predicate_holds(
                {"field_id": "FIELD-LIQUIDITY-USD-001", "operator": "GTE", "value_decimal": "2500"},
                row,
            )
        )
        self.assertTrue(
            _predicate_holds(
                {"field_id": "FIELD-LIQUIDITY-USD-001", "operator": "LT", "value_decimal": "3000"},
                row,
            )
        )
        self.assertTrue(
            _predicate_holds(
                {"field_id": "FIELD-LIQUIDITY-USD-001", "operator": "LTE", "value_decimal": "2500"},
                row,
            )
        )
        self.assertFalse(
            _predicate_holds(
                {
                    "field_id": "FIELD-FIRST-POOL-SOURCE-001",
                    "operator": "GT",
                    "value_text": "pump.fun",
                },
                row,
            )
        )
        self.assertTrue(
            _predicate_holds(
                {
                    "field_id": "FIELD-FIRST-POOL-SOURCE-001",
                    "operator": "NEQ",
                    "value_text": "other",
                },
                row,
            )
        )

    def test_omitted_entity_is_missing_not_aggregate_status(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        missing = "MintMissing111111111111111111111111111111"
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            activation_id = _activate(store, schedule)

            class Partial:
                def open(self, url: str) -> dict:
                    if "/tokens/v2/search" in url:
                        return {"http_status": 200, "body": [{"id": MINT, "liquidity": "2000"}]}
                    if "/swap/v2/order" in url:
                        return {"http_status": 200, "body": {"outAmount": "9900000"}}
                    return {"http_status": 200, "body": []}

            tick_once(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule=schedule,
                activation_id=activation_id,
                now=NOW,
                opener=Partial(),
                producer_git_sha=GIT_SHA,
                discovery_rows=[
                    {
                        "id": MINT,
                        "liquidity": "2000",
                        "firstPool": {"createdAt": "2026-09-01T00:00:00Z", "source": "pump.fun"},
                    },
                    {
                        "id": missing,
                        "liquidity": "2000",
                        "firstPool": {"createdAt": "2026-09-01T00:00:00Z", "source": "pump.fun"},
                    },
                ],
            )
            dues = store.due_in_states(("OBSERVED", "MISSING_TYPED", "DISAPPEARED"))
            search_states = {
                row["entity_id"]: row["state"]
                for row in dues
                if row["primitive_id"] == "PRIM-JUPITER-TOKENS-V2-SEARCH-001"
            }
            self.assertEqual(search_states[MINT], "OBSERVED")
            self.assertEqual(search_states[missing], "MISSING_TYPED")
            store.close()

    def test_two_mint_started_search_is_not_replayed(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        other = "Mint222222222222222222222222222222222222222"
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            activation_id = _activate(store, schedule)
            for entity in (MINT, other):
                store.insert_due(
                    {
                        "schedule_sha256": schedule["schedule_sha256"],
                        "activation_id": activation_id,
                        "entity_id": entity,
                        "point_id": "X300",
                        "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                        "state": "PENDING",
                        "due_at": "2026-09-01T00:05:00Z",
                        "deadline_at": "2026-09-01T00:20:00Z",
                        "payload": {},
                    },
                    clock=NOW,
                )
            from solana_alpha_lab.factory.observation_primitives import (
                request_sha256,
                search_url,
            )

            url = search_url([MINT, other])
            digest = request_sha256(
                method="GET", url=url, body=None, primitive_version="1.0"
            )
            store.start_call(
                request_sha256=digest,
                attempt_id="ATT-BATCH",
                primitive_id="PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                payload={"url": url},
                clock=NOW,
            )
            opener = _Opener()
            tick_once(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule=schedule,
                activation_id=activation_id,
                now=NOW,
                opener=opener,
                producer_git_sha=GIT_SHA,
                discovery_rows=[],
            )
            self.assertEqual(opener.urls, [])
            self.assertEqual(store.due_counts().get("IN_FLIGHT_CALL_INDETERMINATE"), 2)
            store.close()

    def test_source_poll_slot_is_reused(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            activation_id = _activate(store, schedule)
            opener = _Opener()
            first = tick_once(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule=schedule,
                activation_id=activation_id,
                now=NOW,
                opener=opener,
                producer_git_sha=GIT_SHA,
            )
            recents = [url for url in opener.urls if "/tokens/v2/recent" in url]
            self.assertEqual(len(recents), 1)
            self.assertFalse(first.get("source_poll_reused"))
            second = tick_once(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule=schedule,
                activation_id=activation_id,
                now=NOW,
                opener=opener,
                producer_git_sha=GIT_SHA,
            )
            recents_after = [url for url in opener.urls if "/tokens/v2/recent" in url]
            self.assertEqual(len(recents_after), 1)
            self.assertTrue(second.get("source_poll_reused"))
            store.close()

    def test_rejected_members_remain_in_denominator(self) -> None:
        import pyarrow.parquet as pq

        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        rejected = "MintReject1111111111111111111111111111111"
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            activation_id = _activate(store, schedule)
            tick_once(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule=schedule,
                activation_id=activation_id,
                now=NOW,
                opener=_Opener(),
                producer_git_sha=GIT_SHA,
                discovery_rows=[
                    {
                        "id": MINT,
                        "liquidity": "2000",
                        "firstPool": {
                            "createdAt": "2026-09-01T00:00:00Z",
                            "source": "pump.fun",
                        },
                    },
                    {
                        "id": rejected,
                        "liquidity": "10",
                        "firstPool": {
                            "createdAt": "2026-09-01T00:00:00Z",
                            "source": "other",
                        },
                    },
                ],
            )
            members_path = next((data_root / "datasets" / "parquet").rglob("members.parquet"))
            states = set(pq.read_table(members_path).column("membership_state").to_pylist())
            self.assertIn("PREDICATE_REJECTED", states)
            store.close()


if __name__ == "__main__":
    unittest.main()
