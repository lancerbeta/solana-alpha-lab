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
    canonical_sha256,
    load_observation_schedule,
    render_utc,
    schedule_sha256,
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


def _activate(
    store: ObservationScheduleStore,
    schedule: dict,
    activation_id: str = "ACT-OBS-001",
) -> str:
    from solana_alpha_lab.factory.observation_schedule_lifecycle import (
        _authority_policy,
        _minimum_expiry,
        _used_provider_route_ids,
        authorize_schedule,
        expected_authority_phrase,
    )

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


class ObservationSchedulerTests(unittest.TestCase):
    def test_live_tick_requires_exact_bound_authority(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            store.upsert_activation(
                {
                    "schedule_sha256": schedule["schedule_sha256"],
                    "activation_id": "ACT-OBS-UNAUTHORIZED",
                    "schedule_key": schedule["schedule_key"],
                    "state": "ACTIVE",
                    "starts_at": schedule["activation"]["starts_at"],
                    "stops_admitting_at": schedule["activation"]["stops_admitting_at"],
                    "payload": {},
                },
                clock=NOW,
            )
            try:
                with self.assertRaisesRegex(
                    ObservationSchedulerError, "AUTHORITY_MISSING"
                ):
                    tick_once(
                        root=ROOT,
                        data_root=data_root,
                        store=store,
                        schedule=schedule,
                        activation_id="ACT-OBS-UNAUTHORIZED",
                        now=NOW,
                        opener=_Opener(),
                        producer_git_sha=GIT_SHA,
                        discovery_rows=[],
                    )
                self.assertEqual(store.due_counts(), {})
            finally:
                store.close()

    def test_missing_transport_terminalizes_claimed_work_without_credentials(self) -> None:
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
                    "deadline_at": "2026-09-01T00:20:00Z",
                    "payload": {},
                },
                clock=NOW,
            )
            credential_calls: list[str] = []
            try:
                result = tick_once(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    schedule=schedule,
                    activation_id=activation_id,
                    now=NOW,
                    opener=None,
                    credential_loader=lambda: (
                        credential_calls.append("read") or "credential-placeholder"
                    ),
                    producer_git_sha=GIT_SHA,
                    discovery_rows=[],
                )
                self.assertEqual(result["terminal"], "DEPENDENCY_MISSING")
                self.assertEqual(credential_calls, [])
                self.assertEqual(store.due_counts().get("CLAIMED", 0), 0)
                self.assertEqual(
                    store.due_counts().get("DEPENDENCY_MISSING"),
                    1,
                )
            finally:
                store.close()

    def test_tick_does_not_claim_another_schedule(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        other_schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/common_panel.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            self.addCleanup(store.close)
            activation_id = _activate(store, schedule)
            foreign = {
                "schedule_sha256": other_schedule["schedule_sha256"],
                "activation_id": "ACT-OTHER",
                "entity_id": MINT,
                "point_id": "X300",
                "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                "state": "PENDING",
                "due_at": "2026-09-01T00:05:00Z",
                "deadline_at": "2026-09-01T00:20:00Z",
                "payload": {},
            }
            store.insert_due(foreign, clock=NOW)

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

            retained = store.get_due(foreign)
            self.assertIsNotNone(retained)
            assert retained is not None
            self.assertEqual(retained["state"], "PENDING")
            self.assertEqual(opener.urls, [])
            store.close()
    def test_x_predicate_waits_for_all_x_point_evidence(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        schedule = dict(schedule)
        schedule["population"] = dict(schedule["population"])
        schedule["population"]["x_eligibility_predicates"] = [
            {
                "field_id": "FIELD-QUOTE-BUY-OUT-AMOUNT-001",
                "operator": "GTE",
                "value_decimal": "1",
            }
        ]
        schedule["budgets"] = dict(schedule["budgets"])
        schedule["budgets"]["min_provider_pace_seconds"] = 0
        schedule["schedule_sha256"] = schedule_sha256(schedule)
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            self.addCleanup(store.close)
            activation_id = _activate(store, schedule)
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
                discovery_rows=[
                    {
                        "id": MINT,
                        "liquidity": "10",
                        "firstPool": {
                            "createdAt": "2026-09-01T00:00:00Z",
                            "source": "pump.fun",
                        },
                    }
                ],
            )

            candidate = store.list_candidates(
                schedule_sha256=schedule["schedule_sha256"],
                activation_id=activation_id,
            )[0]
            self.assertEqual(candidate["state"], "X_ELIGIBLE")
            self.assertIn("/swap/v2/order", "\n".join(opener.urls))
            self.assertEqual(
                store.get_due(
                    {
                        "schedule_sha256": schedule["schedule_sha256"],
                        "activation_id": activation_id,
                        "entity_id": MINT,
                        "point_id": "X300",
                        "primitive_id": "PRIM-JUPITER-SWAP-V2-QUOTE-BUY-001",
                    }
                )["state"],
                "OBSERVED",
            )
            store.close()

    def test_discovery_x_values_do_not_substitute_for_x_evidence(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        schedule = dict(schedule)
        schedule["budgets"] = dict(schedule["budgets"])
        schedule["budgets"]["min_provider_pace_seconds"] = 0
        schedule["schedule_sha256"] = schedule_sha256(schedule)
        observed_at = datetime(2026, 9, 1, 0, 16, tzinfo=UTC)

        class LowXOpener:
            def __init__(self) -> None:
                self.urls: list[str] = []

            def open(self, url: str) -> dict:
                self.urls.append(url)
                if "/tokens/v2/search" in url:
                    return {
                        "http_status": 200,
                        "body": [
                            {
                                "id": MINT,
                                "liquidity": "10",
                                "firstPool": {
                                    "createdAt": "2026-09-01T00:10:00Z",
                                    "source": "pump.fun",
                                },
                            }
                        ],
                    }
                return {"http_status": 200, "body": {"outAmount": "9900000"}}

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            self.addCleanup(store.close)
            activation_id = _activate(store, schedule)
            opener = LowXOpener()
            discovery = {
                "id": MINT,
                "liquidity": "999999",
                "firstPool": {
                    "createdAt": "2026-09-01T00:10:00Z",
                    "source": "pump.fun",
                },
            }
            tick_once(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule=schedule,
                activation_id=activation_id,
                now=observed_at,
                opener=opener,
                producer_git_sha=GIT_SHA,
                discovery_rows=[discovery],
            )
            tick_once(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule=schedule,
                activation_id=activation_id,
                now=observed_at + timedelta(seconds=1),
                opener=opener,
                producer_git_sha=GIT_SHA,
                discovery_rows=[],
            )
            candidate = store.list_candidates(
                schedule_sha256=schedule["schedule_sha256"],
                activation_id=activation_id,
            )[0]
            self.assertEqual(candidate["state"], "X_POPULATION_INELIGIBLE")
            self.assertNotIn(f"inputMint={MINT}", "\n".join(opener.urls))
            y_sell = store.get_due(
                {
                    "schedule_sha256": schedule["schedule_sha256"],
                    "activation_id": activation_id,
                    "entity_id": MINT,
                    "point_id": "Y900",
                    "primitive_id": "PRIM-JUPITER-SWAP-V2-DEPENDENT-REVERSE-SELL-001",
                }
            )
            self.assertIsNotNone(y_sell)
            assert y_sell is not None
            self.assertEqual(y_sell["state"], "CENSORED")
            from solana_alpha_lab.factory.observation_panel_publisher import (
                rebuild_observation_panel_from_rdp,
            )

            rebuilt = rebuild_observation_panel_from_rdp(
                data_root=data_root,
                schedule_sha256=schedule["schedule_sha256"],
            )
            member_states = {
                row["entity_id"]: row["membership_state"] for row in rebuilt["members"]
            }
            self.assertEqual(member_states[MINT], "X_POPULATION_INELIGIBLE")
            store.close()

    def test_provider_timeout_after_prior_observation_is_missing_not_disappeared(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        schedule = dict(schedule)
        schedule["budgets"] = dict(schedule["budgets"])
        schedule["budgets"]["min_provider_pace_seconds"] = 0
        schedule["schedule_sha256"] = schedule_sha256(schedule)
        search = "PRIM-JUPITER-TOKENS-V2-SEARCH-001"
        buy = "PRIM-JUPITER-SWAP-V2-QUOTE-BUY-001"
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            try:
                activation_id = _activate(store, schedule)
                store.insert_due(
                    {
                        "schedule_sha256": schedule["schedule_sha256"],
                        "activation_id": activation_id,
                        "entity_id": MINT,
                        "point_id": "X300",
                        "primitive_id": search,
                        "state": "OBSERVED",
                        "due_at": "2026-09-01T00:05:00Z",
                        "deadline_at": "2026-09-01T00:10:00Z",
                        "payload": {},
                    },
                    clock=NOW,
                )
                store.insert_due(
                    {
                        "schedule_sha256": schedule["schedule_sha256"],
                        "activation_id": activation_id,
                        "entity_id": MINT,
                        "point_id": "X300",
                        "primitive_id": buy,
                        "state": "PENDING",
                        "due_at": "2026-09-01T00:05:00Z",
                        "deadline_at": "2026-09-01T00:20:00Z",
                        "payload": {},
                    },
                    clock=NOW,
                )

                class TimeoutBuy:
                    def open(self, url: str) -> dict:
                        if "/swap/v2/order" in url:
                            raise TimeoutError("provider timeout")
                        return {"http_status": 200, "body": [{"id": MINT, "liquidity": "2000"}]}

                tick_once(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    schedule=schedule,
                    activation_id=activation_id,
                    now=NOW,
                    opener=TimeoutBuy(),
                    producer_git_sha=GIT_SHA,
                    discovery_rows=[],
                )
                failed = store.get_due(
                    {
                        "schedule_sha256": schedule["schedule_sha256"],
                        "activation_id": activation_id,
                        "entity_id": MINT,
                        "point_id": "X300",
                        "primitive_id": buy,
                    }
                )
                self.assertIsNotNone(failed)
                assert failed is not None
                self.assertEqual(failed["state"], "MISSING_TYPED")
                self.assertEqual(
                    (failed.get("payload") or {}).get("missing_reason"),
                    "TIMEOUT",
                )
            finally:
                store.close()

    def test_http_404_after_prior_observation_is_missing_not_disappeared(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        schedule = dict(schedule)
        schedule["budgets"] = dict(schedule["budgets"])
        schedule["budgets"]["min_provider_pace_seconds"] = 0
        schedule["schedule_sha256"] = schedule_sha256(schedule)
        search = "PRIM-JUPITER-TOKENS-V2-SEARCH-001"
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            try:
                activation_id = _activate(store, schedule)
                store.insert_due(
                    {
                        "schedule_sha256": schedule["schedule_sha256"],
                        "activation_id": activation_id,
                        "entity_id": MINT,
                        "point_id": "X300",
                        "primitive_id": search,
                        "state": "OBSERVED",
                        "due_at": "2026-09-01T00:05:00Z",
                        "deadline_at": "2026-09-01T00:10:00Z",
                        "payload": {},
                    },
                    clock=NOW,
                )
                store.insert_due(
                    {
                        "schedule_sha256": schedule["schedule_sha256"],
                        "activation_id": activation_id,
                        "entity_id": MINT,
                        "point_id": "Y900",
                        "primitive_id": search,
                        "state": "PENDING",
                        "due_at": "2026-09-01T00:15:00Z",
                        "deadline_at": "2026-09-01T00:17:00Z",
                        "payload": {},
                    },
                    clock=NOW,
                )

                class NotFound:
                    def open(self, url: str) -> dict:
                        return {"http_status": 404, "body": {"error": "not found"}}

                tick_once(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    schedule=schedule,
                    activation_id=activation_id,
                    now=datetime(2026, 9, 1, 0, 16, tzinfo=UTC),
                    opener=NotFound(),
                    producer_git_sha=GIT_SHA,
                    discovery_rows=[],
                )
                failed = store.get_due(
                    {
                        "schedule_sha256": schedule["schedule_sha256"],
                        "activation_id": activation_id,
                        "entity_id": MINT,
                        "point_id": "Y900",
                        "primitive_id": search,
                    }
                )
                self.assertIsNotNone(failed)
                assert failed is not None
                self.assertEqual(failed["state"], "MISSING_TYPED")
                self.assertEqual(
                    (failed.get("payload") or {}).get("missing_reason"),
                    "NO_ROUTE",
                )
            finally:
                store.close()

    def test_search_batches_do_not_alias_distinct_due_at(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        schedule = dict(schedule)
        schedule["budgets"] = dict(schedule["budgets"])
        schedule["budgets"]["min_provider_pace_seconds"] = 0
        schedule["schedule_sha256"] = schedule_sha256(schedule)
        search = "PRIM-JUPITER-TOKENS-V2-SEARCH-001"
        mint_b = "Mint222222222222222222222222222222222222222"
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            try:
                activation_id = _activate(store, schedule)
                for entity_id, due_at, deadline in (
                    (MINT, "2026-09-01T00:05:00Z", "2026-09-01T00:20:00Z"),
                    (mint_b, "2026-09-01T00:06:00Z", "2026-09-01T00:20:00Z"),
                ):
                    store.insert_due(
                        {
                            "schedule_sha256": schedule["schedule_sha256"],
                            "activation_id": activation_id,
                            "entity_id": entity_id,
                            "point_id": "X300",
                            "primitive_id": search,
                            "state": "PENDING",
                            "due_at": due_at,
                            "deadline_at": deadline,
                            "payload": {},
                        },
                        clock=NOW,
                    )

                class Capture:
                    def __init__(self) -> None:
                        self.urls: list[str] = []

                    def open(self, url: str) -> dict:
                        self.urls.append(url)
                        body = []
                        if MINT in url:
                            body.append({"id": MINT, "liquidity": "5000"})
                        if mint_b in url:
                            body.append({"id": mint_b, "liquidity": "5000"})
                        return {"http_status": 200, "body": body}

                opener = Capture()
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
                search_urls = [url for url in opener.urls if "/tokens/v2/search" in url]
                self.assertEqual(len(search_urls), 2, search_urls)
                self.assertTrue(any(MINT in url and mint_b not in url for url in search_urls))
                self.assertTrue(any(mint_b in url and MINT not in url for url in search_urls))
            finally:
                store.close()

    def test_non_call_terminal_does_not_synthesize_request_clocks(self) -> None:
        from solana_alpha_lab.factory.observation_scheduler import _observation_row

        row = _observation_row(
            {
                "schedule_sha256": "a" * 64,
                "activation_id": "ACT",
                "entity_id": MINT,
                "point_id": "Y900",
                "primitive_id": "PRIM-JUPITER-SWAP-V2-DEPENDENT-REVERSE-SELL-001",
                "due_at": "2026-09-01T00:15:00Z",
                "deadline_at": "2026-09-01T00:17:00Z",
                "payload": {},
            },
            "CENSORED",
            NOW,
            None,
            missing_reason="CENSORED_LATE",
        )
        self.assertIsNone(row["request_started_at"])
        self.assertIsNone(row["response_received_at"])
        self.assertEqual(row["first_reliable_available_at"], render_utc(NOW))

    def test_authoritative_anchor_reanchors_other_claimed_x_primitives(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        schedule = dict(schedule)
        schedule["budgets"] = dict(schedule["budgets"])
        schedule["budgets"]["min_provider_pace_seconds"] = 0
        schedule["schedule_sha256"] = schedule_sha256(schedule)

        class AnchoredOpener(_Opener):
            def open(self, url: str) -> dict:
                self.urls.append(url)
                if "/tokens/v2/search" in url:
                    return {
                        "http_status": 200,
                        "body": [
                            {
                                "id": MINT,
                                "liquidity": "2000",
                                "firstPool": {
                                    "createdAt": "2026-09-01T00:04:00Z",
                                    "source": "pump.fun",
                                },
                            }
                        ],
                    }
                if "/swap/v2/order" in url:
                    return {"http_status": 200, "body": {"outAmount": "9900000"}}
                return {"http_status": 200, "body": []}

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            self.addCleanup(store.close)
            activation_id = _activate(store, schedule)
            opener = AnchoredOpener()
            tick_once(
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
                        "first_seen_at": "2026-09-01T00:00:00Z",
                        "source": "pump.fun",
                    }
                ],
            )
            buy = store.get_due(
                {
                    "schedule_sha256": schedule["schedule_sha256"],
                    "activation_id": activation_id,
                    "entity_id": MINT,
                    "point_id": "X300",
                    "primitive_id": "PRIM-JUPITER-SWAP-V2-QUOTE-BUY-001",
                }
            )
            self.assertIsNotNone(buy)
            assert buy is not None
            self.assertEqual(buy["state"], "PENDING")
            self.assertEqual(buy["due_at"], "2026-09-01T00:09:00Z")
            candidate = store.list_candidates(
                schedule_sha256=schedule["schedule_sha256"],
                activation_id=activation_id,
            )[0]
            self.assertEqual(
                candidate["payload"]["authoritative_anchor"],
                "2026-09-01T00:04:00Z",
            )
            self.assertFalse(candidate["payload"]["provisional_due"])
            self.assertNotIn(f"inputMint={MINT}", "\n".join(opener.urls))
            store.close()

    def test_late_authoritative_anchor_censors_stale_point_and_dependents(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        schedule = dict(schedule)
        schedule["budgets"] = dict(schedule["budgets"])
        schedule["budgets"]["min_provider_pace_seconds"] = 0
        schedule["schedule_sha256"] = schedule_sha256(schedule)

        class LateAnchoredOpener(_Opener):
            def open(self, url: str) -> dict:
                self.urls.append(url)
                if "/tokens/v2/search" in url:
                    return {
                        "http_status": 200,
                        "body": [
                            {
                                "id": MINT,
                                "liquidity": "2000",
                                "firstPool": {
                                    "createdAt": "2026-09-01T00:09:00Z",
                                    "source": "pump.fun",
                                },
                            }
                        ],
                    }
                return {"http_status": 200, "body": {"outAmount": "9900000"}}

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            self.addCleanup(store.close)
            activation_id = _activate(store, schedule)
            opener = LateAnchoredOpener()
            tick_once(
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
                        "first_seen_at": "2026-09-01T00:00:00Z",
                        "source": "pump.fun",
                    }
                ],
            )
            states = {
                (row["point_id"], row["primitive_id"]): row["state"]
                for row in store.due_in_states(
                    (
                        "CENSORED_LATE",
                        "CENSORED",
                        "PENDING",
                        "OBSERVED",
                    )
                )
                if row["entity_id"] == MINT
            }
            self.assertEqual(
                states[
                    ("X300", "PRIM-JUPITER-TOKENS-V2-SEARCH-001")
                ],
                "CENSORED_LATE",
            )
            self.assertEqual(
                states[
                    ("X300", "PRIM-JUPITER-SWAP-V2-QUOTE-BUY-001")
                ],
                "CENSORED",
            )
            self.assertEqual(
                states[
                    ("Y900", "PRIM-JUPITER-SWAP-V2-DEPENDENT-REVERSE-SELL-001")
                ],
                "CENSORED",
            )
            late_search = store.get_due(
                {
                    "schedule_sha256": schedule["schedule_sha256"],
                    "activation_id": activation_id,
                    "entity_id": MINT,
                    "point_id": "X300",
                    "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                }
            )
            self.assertIsNotNone(late_search)
            assert late_search is not None
            self.assertIsNotNone(late_search["request_sha256"])
            self.assertIsNotNone(late_search["call_occurrence_id"])
            self.assertNotIn(f"inputMint={MINT}", "\n".join(opener.urls))
            candidate = store.list_candidates(
                schedule_sha256=schedule["schedule_sha256"],
                activation_id=activation_id,
            )[0]
            self.assertEqual(candidate["state"], "X_POPULATION_INELIGIBLE")
            store.close()

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
                self.assertTrue(any("/tokens/v2/search" in url for url in opener.urls))
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
                call_occurrence_id,
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
                call_occurrence_id=call_occurrence_id(
                    schedule_sha256=schedule["schedule_sha256"],
                    activation_id=activation_id,
                    primitive_id="PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                    point_id="BATCH",
                    due_at="2026-09-01T00:05:00Z",
                    claim_identity_set=[
                        f"{MINT}:X300:2026-09-01T00:05:00Z"
                    ],
                    request_digest=digest,
                ),
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
            try:
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
                self.assertEqual(store.due_counts().get("CENSORED_LATE"), 1)
            finally:
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
                call_occurrence_id,
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
                call_occurrence_id=call_occurrence_id(
                    schedule_sha256=schedule["schedule_sha256"],
                    activation_id=activation_id,
                    primitive_id="PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                    point_id="BATCH",
                    due_at="2026-09-01T00:05:00Z",
                    claim_identity_set=[
                        f"{MINT}:X300:2026-09-01T00:05:00Z"
                    ],
                    request_digest=digest,
                ),
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

    def test_zero_typed_source_value_is_not_treated_as_missing(self) -> None:
        from solana_alpha_lab.factory.observation_scheduler import _predicate_holds

        self.assertTrue(
            _predicate_holds(
                {
                    "field_id": "FIELD-LIQUIDITY-USD-001",
                    "operator": "EQ",
                    "value_decimal": "0",
                },
                {"id": MINT, "liquidity": 0},
            )
        )

    def test_pacing_uses_latest_completion_across_utc_days(self) -> None:
        from solana_alpha_lab.factory.observation_scheduler import _Accounting

        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            store.save_accounting(
                schedule_sha256=schedule["schedule_sha256"],
                activation_id="ACT-OBS-PACE",
                utc_day="2026-08-31",
                values={
                    "provider_calls": 1,
                    "modeled_credits": 1,
                    "candidates": 0,
                    "members": 0,
                    "raw_bytes": 1,
                    "canonical_bytes": 1,
                    "last_provider_call_at": "2026-08-31T23:59:59Z",
                },
                clock=NOW,
            )
            accounting = _Accounting(
                store,
                schedule,
                "ACT-OBS-PACE",
                datetime(2026, 9, 1, 0, 0, 1, tzinfo=UTC),
            )
            self.assertEqual(
                accounting.gate(
                    now=datetime(2026, 9, 1, 0, 0, 1, tzinfo=UTC)
                ),
                "PACE_WAIT",
            )
            store.close()

    def test_observation_values_follow_registered_output_fields(self) -> None:
        from solana_alpha_lab.factory.observation_primitive_registry import (
            load_observation_primitive_registry,
        )
        from solana_alpha_lab.factory.observation_scheduler import (
            _typed_observation_values,
        )

        registry = load_observation_primitive_registry(ROOT)
        registry.primitives["PRIM-JUPITER-TOKENS-V2-SEARCH-001"][
            "output_field_ids"
        ] = ["FIELD-LIQUIDITY-USD-001"]
        values = _typed_observation_values(
            claim={
                "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                "point_id": "X300",
                "event_time": "2026-09-01T00:05:00Z",
                "first_reliable_available_at": "2026-09-01T00:05:07Z",
                "request_sha256": "a" * 64,
                "call_occurrence_id": "b" * 64,
            },
            state="OBSERVED",
            response_payload={"liquidity": 0},
            buy_out=None,
            missing_reason=None,
            registry=registry,
        )
        self.assertEqual(
            [item["field_id"] for item in values],
            ["FIELD-LIQUIDITY-USD-001"],
        )
        self.assertEqual(values[0]["typed_value_or_null"], "0")

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
                call_occurrence_id,
                request_sha256,
                search_url,
            )

            url = search_url([MINT, other])
            digest = request_sha256(
                method="GET", url=url, body=None, primitive_version="1.0"
            )
            store.start_call(
                request_sha256=digest,
                call_occurrence_id=call_occurrence_id(
                    schedule_sha256=schedule["schedule_sha256"],
                    activation_id=activation_id,
                    primitive_id="PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                    point_id="BATCH",
                    due_at="2026-09-01T00:05:00Z",
                    claim_identity_set=[
                        f"{MINT}:X300:2026-09-01T00:05:00Z",
                        f"{other}:X300:2026-09-01T00:05:00Z",
                    ],
                    request_digest=digest,
                ),
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
            members_path = next((data_root / "datasets").rglob("members.parquet"))
            states = set(pq.read_table(members_path).column("membership_state").to_pylist())
            self.assertIn("PREDICATE_REJECTED", states)
            store.close()

    def test_identical_sell_payload_at_two_horizons_makes_two_calls(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        schedule = dict(schedule)
        schedule["y_points"] = list(schedule["y_points"]) + [
            {
                "point_id": "Y3600",
                "due_offset_seconds": 3600,
                "allowed_lateness_seconds": 300,
                "bundle_ids": ["BUNDLE-JUPITER-DEPENDENT-REVERSE-SELL-001"],
            }
        ]
        schedule["budgets"] = dict(schedule["budgets"])
        schedule["budgets"]["min_provider_pace_seconds"] = 0
        schedule["schedule_sha256"] = schedule_sha256(schedule)
        sell = "PRIM-JUPITER-SWAP-V2-DEPENDENT-REVERSE-SELL-001"
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            self.addCleanup(store.close)
            activation_id = _activate(store, schedule)
            for point_id, due_at, deadline_at in (
                ("Y900", "2026-09-01T00:15:00Z", "2026-09-01T00:17:00Z"),
                ("Y3600", "2026-09-01T01:00:00Z", "2026-09-01T01:05:00Z"),
            ):
                store.insert_due(
                    {
                        "schedule_sha256": schedule["schedule_sha256"],
                        "activation_id": activation_id,
                        "entity_id": MINT,
                        "point_id": point_id,
                        "primitive_id": sell,
                        "state": "PENDING",
                        "due_at": due_at,
                        "deadline_at": deadline_at,
                        "payload": {"buy_out_amount": "9900000"},
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
                now=datetime(2026, 9, 1, 0, 16, tzinfo=UTC),
                opener=opener,
                producer_git_sha=GIT_SHA,
                discovery_rows=[],
            )
            tick_once(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule=schedule,
                activation_id=activation_id,
                now=datetime(2026, 9, 1, 1, 1, tzinfo=UTC),
                opener=opener,
                producer_git_sha=GIT_SHA,
                discovery_rows=[],
            )
            sell_urls = [url for url in opener.urls if "/swap/v2/order" in url]
            self.assertEqual(len(sell_urls), 2)
            self.assertEqual(sell_urls[0], sell_urls[1])
            calls = store.list_calls(primitive_id=sell)
            completed = [row for row in calls if row["state"] == "COMPLETED"]
            self.assertEqual(len(completed), 2)
            self.assertEqual(completed[0]["request_sha256"], completed[1]["request_sha256"])
            self.assertNotEqual(
                completed[0]["call_occurrence_id"],
                completed[1]["call_occurrence_id"],
            )
            store.close()

    def test_same_search_url_in_two_activations_is_two_occurrences(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        schedule = dict(schedule)
        schedule["budgets"] = dict(schedule["budgets"])
        schedule["budgets"]["min_provider_pace_seconds"] = 0
        schedule["schedule_sha256"] = schedule_sha256(schedule)
        search = "PRIM-JUPITER-TOKENS-V2-SEARCH-001"
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            self.addCleanup(store.close)
            first = _activate(store, schedule, "ACT-OCC-A")
            second = _activate(store, schedule, "ACT-OCC-B")
            for activation_id, due_at in (
                (first, "2026-09-01T00:05:00Z"),
                (second, "2026-09-01T00:06:00Z"),
            ):
                store.insert_due(
                    {
                        "schedule_sha256": schedule["schedule_sha256"],
                        "activation_id": activation_id,
                        "entity_id": MINT,
                        "point_id": "X300",
                        "primitive_id": search,
                        "state": "PENDING",
                        "due_at": due_at,
                        "deadline_at": "2026-09-01T00:20:00Z",
                        "payload": {},
                    },
                    clock=NOW,
                )
            opener = _Opener()
            for activation_id in (first, second):
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
            search_urls = [url for url in opener.urls if "/tokens/v2/search" in url]
            self.assertEqual(len(search_urls), 2)
            self.assertEqual(search_urls[0], search_urls[1])
            calls = [row for row in store.list_calls(primitive_id=search) if row["state"] == "COMPLETED"]
            self.assertEqual(len(calls), 2)
            self.assertEqual(calls[0]["request_sha256"], calls[1]["request_sha256"])
            self.assertNotEqual(calls[0]["call_occurrence_id"], calls[1]["call_occurrence_id"])
            store.close()

    def test_discovery_low_liquidity_does_not_block_x_eligible_search(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        schedule = dict(schedule)
        schedule["budgets"] = dict(schedule["budgets"])
        schedule["budgets"]["min_provider_pace_seconds"] = 0
        schedule["schedule_sha256"] = schedule_sha256(schedule)
        observed_at = datetime(2026, 9, 1, 0, 16, tzinfo=UTC)

        class HighXOpener:
            def __init__(self) -> None:
                self.urls: list[str] = []

            def open(self, url: str) -> dict:
                self.urls.append(url)
                if "/tokens/v2/search" in url:
                    return {
                        "http_status": 200,
                        "body": [
                            {
                                "id": MINT,
                                "liquidity": "2000",
                                "firstPool": {
                                    "createdAt": "2026-09-01T00:10:00Z",
                                    "source": "pump.fun",
                                },
                            }
                        ],
                    }
                return {"http_status": 200, "body": {"outAmount": "9900000"}}

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            self.addCleanup(store.close)
            activation_id = _activate(store, schedule)
            opener = HighXOpener()
            tick_once(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule=schedule,
                activation_id=activation_id,
                now=observed_at,
                opener=opener,
                producer_git_sha=GIT_SHA,
                discovery_rows=[
                    {
                        "id": MINT,
                        "liquidity": "10",
                        "firstPool": {
                            "createdAt": "2026-09-01T00:10:00Z",
                            "source": "pump.fun",
                        },
                    }
                ],
            )
            candidate = store.list_candidates(
                schedule_sha256=schedule["schedule_sha256"],
                activation_id=activation_id,
            )[0]
            self.assertNotEqual(candidate["state"], "X_POPULATION_INELIGIBLE")
            self.assertIn(MINT, "\n".join(opener.urls))
            tick_once(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule=schedule,
                activation_id=activation_id,
                now=observed_at + timedelta(seconds=1),
                opener=opener,
                producer_git_sha=GIT_SHA,
                discovery_rows=[],
            )
            self.assertTrue(
                any("/swap/v2/order" in url and MINT in url for url in opener.urls)
            )
            store.close()

    def test_prior_observed_absence_is_disappeared_not_missing(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        schedule = dict(schedule)
        schedule["y_points"] = list(schedule["y_points"]) + [
            {
                "point_id": "Y3600",
                "due_offset_seconds": 3600,
                "allowed_lateness_seconds": 300,
                "bundle_ids": ["BUNDLE-JUPITER-DEPENDENT-REVERSE-SELL-001"],
            }
        ]
        schedule["budgets"] = dict(schedule["budgets"])
        schedule["budgets"]["min_provider_pace_seconds"] = 0
        schedule["schedule_sha256"] = schedule_sha256(schedule)
        search = "PRIM-JUPITER-TOKENS-V2-SEARCH-001"
        sell = "PRIM-JUPITER-SWAP-V2-DEPENDENT-REVERSE-SELL-001"
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            try:
                activation_id = _activate(store, schedule)
                store.insert_due(
                    {
                        "schedule_sha256": schedule["schedule_sha256"],
                        "activation_id": activation_id,
                        "entity_id": MINT,
                        "point_id": "X300",
                        "primitive_id": search,
                        "state": "OBSERVED",
                        "due_at": "2026-09-01T00:05:00Z",
                        "deadline_at": "2026-09-01T00:10:00Z",
                        "payload": {},
                    },
                    clock=NOW,
                )
                store.insert_due(
                    {
                        "schedule_sha256": schedule["schedule_sha256"],
                        "activation_id": activation_id,
                        "entity_id": MINT,
                        "point_id": "Y900",
                        "primitive_id": search,
                        "state": "PENDING",
                        "due_at": "2026-09-01T00:15:00Z",
                        "deadline_at": "2026-09-01T00:17:00Z",
                        "payload": {},
                    },
                    clock=NOW,
                )
                store.insert_due(
                    {
                        "schedule_sha256": schedule["schedule_sha256"],
                        "activation_id": activation_id,
                        "entity_id": MINT,
                        "point_id": "Y3600",
                        "primitive_id": sell,
                        "state": "PENDING",
                        "due_at": "2026-09-01T01:00:00Z",
                        "deadline_at": "2026-09-01T01:05:00Z",
                        "payload": {"buy_out_amount": "9900000"},
                    },
                    clock=NOW,
                )

                class Absent:
                    def open(self, url: str) -> dict:
                        if "/tokens/v2/search" in url:
                            return {"http_status": 200, "body": []}
                        return {"http_status": 200, "body": {"outAmount": "1"}}

                tick_once(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    schedule=schedule,
                    activation_id=activation_id,
                    now=datetime(2026, 9, 1, 0, 16, tzinfo=UTC),
                    opener=Absent(),
                    producer_git_sha=GIT_SHA,
                    discovery_rows=[],
                )
                gone = store.get_due(
                    {
                        "schedule_sha256": schedule["schedule_sha256"],
                        "activation_id": activation_id,
                        "entity_id": MINT,
                        "point_id": "Y900",
                        "primitive_id": search,
                    }
                )
                self.assertIsNotNone(gone)
                assert gone is not None
                self.assertEqual(gone["state"], "DISAPPEARED")
                later = store.get_due(
                    {
                        "schedule_sha256": schedule["schedule_sha256"],
                        "activation_id": activation_id,
                        "entity_id": MINT,
                        "point_id": "Y3600",
                        "primitive_id": sell,
                    }
                )
                self.assertIsNotNone(later)
                assert later is not None
                self.assertEqual(later["state"], "PENDING")
            finally:
                store.close()

    def test_disappearance_censor_remaining_points_is_atomic(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        schedule = dict(schedule)
        schedule["disappearance"] = dict(schedule["disappearance"])
        schedule["disappearance"]["default"] = "CENSOR_REMAINING_POINTS"
        schedule["y_points"] = list(schedule["y_points"]) + [
            {
                "point_id": "Y3600",
                "due_offset_seconds": 3600,
                "allowed_lateness_seconds": 300,
                "bundle_ids": ["BUNDLE-JUPITER-DEPENDENT-REVERSE-SELL-001"],
            }
        ]
        schedule["budgets"] = dict(schedule["budgets"])
        schedule["budgets"]["min_provider_pace_seconds"] = 0
        schedule["schedule_sha256"] = schedule_sha256(schedule)
        search = "PRIM-JUPITER-TOKENS-V2-SEARCH-001"
        sell = "PRIM-JUPITER-SWAP-V2-DEPENDENT-REVERSE-SELL-001"
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            try:
                activation_id = _activate(store, schedule)
                store.insert_due(
                    {
                        "schedule_sha256": schedule["schedule_sha256"],
                        "activation_id": activation_id,
                        "entity_id": MINT,
                        "point_id": "X300",
                        "primitive_id": search,
                        "state": "OBSERVED",
                        "due_at": "2026-09-01T00:05:00Z",
                        "deadline_at": "2026-09-01T00:10:00Z",
                        "payload": {},
                    },
                    clock=NOW,
                )
                store.insert_due(
                    {
                        "schedule_sha256": schedule["schedule_sha256"],
                        "activation_id": activation_id,
                        "entity_id": MINT,
                        "point_id": "Y900",
                        "primitive_id": search,
                        "state": "PENDING",
                        "due_at": "2026-09-01T00:15:00Z",
                        "deadline_at": "2026-09-01T00:17:00Z",
                        "payload": {},
                    },
                    clock=NOW,
                )
                store.insert_due(
                    {
                        "schedule_sha256": schedule["schedule_sha256"],
                        "activation_id": activation_id,
                        "entity_id": MINT,
                        "point_id": "Y3600",
                        "primitive_id": sell,
                        "state": "PENDING",
                        "due_at": "2026-09-01T01:00:00Z",
                        "deadline_at": "2026-09-01T01:05:00Z",
                        "payload": {"buy_out_amount": "9900000"},
                    },
                    clock=NOW,
                )

                class Absent:
                    def open(self, url: str) -> dict:
                        if "/tokens/v2/search" in url:
                            return {"http_status": 200, "body": []}
                        return {"http_status": 200, "body": {"outAmount": "1"}}

                tick_once(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    schedule=schedule,
                    activation_id=activation_id,
                    now=datetime(2026, 9, 1, 0, 16, tzinfo=UTC),
                    opener=Absent(),
                    producer_git_sha=GIT_SHA,
                    discovery_rows=[],
                )
                later = store.get_due(
                    {
                        "schedule_sha256": schedule["schedule_sha256"],
                        "activation_id": activation_id,
                        "entity_id": MINT,
                        "point_id": "Y3600",
                        "primitive_id": sell,
                    }
                )
                self.assertIsNotNone(later)
                assert later is not None
                self.assertEqual(later["state"], "CENSORED")
            finally:
                store.close()

    def test_missing_without_continue_later_points_censors_remainder(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        schedule = dict(schedule)
        schedule["missingness"] = dict(schedule["missingness"])
        schedule["missingness"]["continue_later_points_after_missing"] = False
        schedule["budgets"] = dict(schedule["budgets"])
        schedule["budgets"]["min_provider_pace_seconds"] = 0
        schedule["schedule_sha256"] = schedule_sha256(schedule)
        search = "PRIM-JUPITER-TOKENS-V2-SEARCH-001"
        sell = "PRIM-JUPITER-SWAP-V2-DEPENDENT-REVERSE-SELL-001"
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            self.addCleanup(store.close)
            activation_id = _activate(store, schedule)
            store.insert_due(
                {
                    "schedule_sha256": schedule["schedule_sha256"],
                    "activation_id": activation_id,
                    "entity_id": MINT,
                    "point_id": "X300",
                    "primitive_id": search,
                    "state": "PENDING",
                    "due_at": "2026-09-01T00:05:00Z",
                    "deadline_at": "2026-09-01T00:20:00Z",
                    "payload": {},
                },
                clock=NOW,
            )
            store.insert_due(
                {
                    "schedule_sha256": schedule["schedule_sha256"],
                    "activation_id": activation_id,
                    "entity_id": MINT,
                    "point_id": "Y900",
                    "primitive_id": sell,
                    "state": "PENDING",
                    "due_at": "2026-09-01T00:15:00Z",
                    "deadline_at": "2026-09-01T00:17:00Z",
                    "payload": {"buy_out_amount": "9900000"},
                },
                clock=NOW,
            )

            class Absent:
                def open(self, url: str) -> dict:
                    if "/tokens/v2/search" in url:
                        return {"http_status": 200, "body": []}
                    return {"http_status": 200, "body": {"outAmount": "1"}}

            tick_once(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule=schedule,
                activation_id=activation_id,
                now=NOW,
                opener=Absent(),
                producer_git_sha=GIT_SHA,
                discovery_rows=[],
            )
            missing = store.get_due(
                {
                    "schedule_sha256": schedule["schedule_sha256"],
                    "activation_id": activation_id,
                    "entity_id": MINT,
                    "point_id": "X300",
                    "primitive_id": search,
                }
            )
            self.assertIsNotNone(missing)
            assert missing is not None
            self.assertEqual(missing["state"], "MISSING_TYPED")
            later = store.get_due(
                {
                    "schedule_sha256": schedule["schedule_sha256"],
                    "activation_id": activation_id,
                    "entity_id": MINT,
                    "point_id": "Y900",
                    "primitive_id": sell,
                }
            )
            self.assertIsNotNone(later)
            assert later is not None
            self.assertEqual(later["state"], "CENSORED")
            store.close()

    def test_rollover_assigns_candidates_on_cutover_boundary(self) -> None:
        predecessor = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        successor = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/successor_y259200.yaml"
        )
        predecessor = dict(predecessor)
        predecessor["budgets"] = dict(predecessor["budgets"])
        predecessor["budgets"]["min_provider_pace_seconds"] = 0
        predecessor["schedule_sha256"] = schedule_sha256(predecessor)
        successor = dict(successor)
        successor["budgets"] = dict(successor["budgets"])
        successor["budgets"]["min_provider_pace_seconds"] = 0
        successor["schedule_sha256"] = schedule_sha256(successor)
        cutover = "2026-09-01T00:20:00Z"
        early = "MintEarly111111111111111111111111111111111"
        exact = "MintExact111111111111111111111111111111111"
        late = "MintLate1111111111111111111111111111111111"
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            self.addCleanup(store.close)
            pred_act = _activate(store, predecessor, "ACT-PRE")
            suc_act = _activate(store, successor, "ACT-SUC")
            pred_authority = store.get_activation(predecessor["schedule_sha256"], pred_act)
            assert pred_authority is not None
            store.persist_rollover(
                predecessor_schedule_sha256=predecessor["schedule_sha256"],
                predecessor_activation_id=pred_act,
                successor_schedule_sha256=successor["schedule_sha256"],
                successor_activation_id=suc_act,
                cutover_at=cutover,
                authority_receipt_sha256=str(pred_authority["authority_receipt_sha256"]),
                clock=NOW,
            )
            store.transition_activation(
                schedule_sha256=predecessor["schedule_sha256"],
                activation_id=pred_act,
                new_state="DRAINING",
                clock=NOW,
            )
            rows = [
                {
                    "id": early,
                    "first_seen_at": "2026-09-01T00:19:59Z",
                    "source": "pump.fun",
                    "firstPool": {
                        "createdAt": "2026-09-01T00:19:59Z",
                        "source": "pump.fun",
                    },
                },
                {
                    "id": exact,
                    "first_seen_at": cutover,
                    "source": "pump.fun",
                    "firstPool": {"createdAt": cutover, "source": "pump.fun"},
                },
                {
                    "id": late,
                    "first_seen_at": "2026-09-01T00:20:01Z",
                    "source": "pump.fun",
                    "firstPool": {
                        "createdAt": "2026-09-01T00:20:01Z",
                        "source": "pump.fun",
                    },
                },
            ]
            tick_once(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule=predecessor,
                activation_id=pred_act,
                now=datetime(2026, 9, 1, 0, 19, 30, tzinfo=UTC),
                opener=_Opener(),
                producer_git_sha=GIT_SHA,
                discovery_rows=rows,
            )
            tick_once(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule=successor,
                activation_id=suc_act,
                now=datetime(2026, 9, 1, 0, 19, 30, tzinfo=UTC),
                opener=_Opener(),
                producer_git_sha=GIT_SHA,
                discovery_rows=rows,
            )
            pred_before = {
                row["entity_id"]
                for row in store.list_candidates(
                    schedule_sha256=predecessor["schedule_sha256"],
                    activation_id=pred_act,
                )
            }
            suc_before = {
                row["entity_id"]
                for row in store.list_candidates(
                    schedule_sha256=successor["schedule_sha256"],
                    activation_id=suc_act,
                )
            }
            self.assertEqual(pred_before, {early})
            self.assertEqual(suc_before, set())
            tick_once(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule=predecessor,
                activation_id=pred_act,
                now=datetime(2026, 9, 1, 0, 20, tzinfo=UTC),
                opener=_Opener(),
                producer_git_sha=GIT_SHA,
                discovery_rows=rows,
            )
            tick_once(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule=successor,
                activation_id=suc_act,
                now=datetime(2026, 9, 1, 0, 20, tzinfo=UTC),
                opener=_Opener(),
                producer_git_sha=GIT_SHA,
                discovery_rows=rows,
            )
            pred_ids = {
                row["entity_id"]
                for row in store.list_candidates(
                    schedule_sha256=predecessor["schedule_sha256"],
                    activation_id=pred_act,
                )
            }
            suc_ids = {
                row["entity_id"]
                for row in store.list_candidates(
                    schedule_sha256=successor["schedule_sha256"],
                    activation_id=suc_act,
                )
            }
            self.assertEqual(pred_ids, {early})
            self.assertEqual(suc_ids, {exact, late})
            self.assertFalse(pred_ids & suc_ids)
            store.insert_due(
                {
                    "schedule_sha256": predecessor["schedule_sha256"],
                    "activation_id": pred_act,
                    "entity_id": early,
                    "point_id": "Y900",
                    "primitive_id": "PRIM-JUPITER-SWAP-V2-DEPENDENT-REVERSE-SELL-001",
                    "state": "PENDING",
                    "due_at": "2026-09-01T00:25:00Z",
                    "deadline_at": "2026-09-01T00:27:00Z",
                    "payload": {"buy_out_amount": "9900000"},
                },
                clock=datetime(2026, 9, 1, 0, 21, tzinfo=UTC),
            )
            opener = _Opener()
            tick_once(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule=predecessor,
                activation_id=pred_act,
                now=datetime(2026, 9, 1, 0, 26, tzinfo=UTC),
                opener=opener,
                producer_git_sha=GIT_SHA,
                discovery_rows=[],
            )
            self.assertTrue(any("/swap/v2/order" in url for url in opener.urls))
            store.close()

    def test_two_due_calls_same_tick_obey_pace_without_duplicate(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        sell = "PRIM-JUPITER-SWAP-V2-DEPENDENT-REVERSE-SELL-001"
        other = "MintPace1111111111111111111111111111111111"
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            self.addCleanup(store.close)
            activation_id = _activate(store, schedule)
            for entity, due_at in (
                (MINT, "2026-09-01T00:15:00Z"),
                (other, "2026-09-01T00:15:01Z"),
            ):
                store.insert_due(
                    {
                        "schedule_sha256": schedule["schedule_sha256"],
                        "activation_id": activation_id,
                        "entity_id": entity,
                        "point_id": "Y900",
                        "primitive_id": sell,
                        "state": "PENDING",
                        "due_at": due_at,
                        "deadline_at": "2026-09-01T00:20:00Z",
                        "payload": {"buy_out_amount": "9900000"},
                    },
                    clock=NOW,
                )
            opener = _Opener()
            first = tick_once(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule=schedule,
                activation_id=activation_id,
                now=datetime(2026, 9, 1, 0, 16, tzinfo=UTC),
                opener=opener,
                producer_git_sha=GIT_SHA,
                discovery_rows=[],
            )
            self.assertEqual(first["terminal"], "TICK_COMPLETE")
            self.assertEqual(sum(1 for url in opener.urls if "/swap/v2/order" in url), 2)
            second = tick_once(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule=schedule,
                activation_id=activation_id,
                now=datetime(2026, 9, 1, 0, 16, tzinfo=UTC),
                opener=opener,
                producer_git_sha=GIT_SHA,
                discovery_rows=[],
            )
            self.assertEqual(second["terminal"], "TICK_COMPLETE")
            self.assertEqual(sum(1 for url in opener.urls if "/swap/v2/order" in url), 2)
            third = tick_once(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule=schedule,
                activation_id=activation_id,
                now=datetime(2026, 9, 1, 0, 16, 3, tzinfo=UTC),
                opener=opener,
                producer_git_sha=GIT_SHA,
                discovery_rows=[],
            )
            self.assertEqual(third["terminal"], "TICK_COMPLETE")
            self.assertEqual(sum(1 for url in opener.urls if "/swap/v2/order" in url), 2)
            store.close()

    def test_budget_exhaustion_terminalizes_remaining_claimed_work(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        schedule = dict(schedule)
        schedule["budgets"] = dict(schedule["budgets"])
        schedule["budgets"]["min_provider_pace_seconds"] = 0
        schedule["budgets"]["provider_calls_per_tick_max"] = 1
        schedule["schedule_sha256"] = schedule_sha256(schedule)
        sell = "PRIM-JUPITER-SWAP-V2-DEPENDENT-REVERSE-SELL-001"
        other = "MintBudget11111111111111111111111111111111"
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            self.addCleanup(store.close)
            activation_id = _activate(store, schedule)
            for entity in (MINT, other):
                store.insert_due(
                    {
                        "schedule_sha256": schedule["schedule_sha256"],
                        "activation_id": activation_id,
                        "entity_id": entity,
                        "point_id": "Y900",
                        "primitive_id": sell,
                        "state": "PENDING",
                        "due_at": "2026-09-01T00:15:00Z",
                        "deadline_at": "2026-09-01T00:20:00Z",
                        "payload": {"buy_out_amount": "9900000"},
                    },
                    clock=NOW,
                )
            opener = _Opener()
            result = tick_once(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule=schedule,
                activation_id=activation_id,
                now=datetime(2026, 9, 1, 0, 16, tzinfo=UTC),
                opener=opener,
                producer_git_sha=GIT_SHA,
                discovery_rows=[],
            )
            self.assertEqual(result["terminal"], "BLOCKED_BUDGET")
            self.assertEqual(sum(1 for url in opener.urls if "/swap/v2/order" in url), 1)
            states = {
                row["entity_id"]: row["state"]
                for row in store.due_in_states(("OBSERVED", "BLOCKED_BUDGET", "CLAIMED", "PENDING"))
                if row["primitive_id"] == sell
            }
            self.assertEqual(sorted(states.values()), ["BLOCKED_BUDGET", "OBSERVED"])
            store.close()

    def test_unresolved_restore_marker_denies_tick(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            self.addCleanup(store.close)
            activation_id = _activate(store, schedule)
            store.set_restore_marker("RECOVERY-QA13", clock=NOW)
            with self.assertRaisesRegex(ObservationSchedulerError, "RESTORE_MARKER_UNRESOLVED"):
                tick_once(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    schedule=schedule,
                    activation_id=activation_id,
                    now=NOW,
                    opener=_Opener(),
                    producer_git_sha=GIT_SHA,
                    discovery_rows=[],
                )
            store.close()

    def test_tampered_authority_policy_digest_denies_tick(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            self.addCleanup(store.close)
            activation_id = _activate(store, schedule)
            activation = store.get_activation(schedule["schedule_sha256"], activation_id)
            assert activation is not None
            receipt = store.get_authority(str(activation["authority_receipt_sha256"]))
            assert receipt is not None
            receipt["policy_digest"] = "0" * 64
            store._conn.execute(
                "UPDATE authority_receipts SET payload_json = ? WHERE receipt_sha256 = ?",
                (
                    json.dumps(receipt, sort_keys=True, ensure_ascii=False),
                    str(activation["authority_receipt_sha256"]),
                ),
            )
            store._conn.commit()
            with self.assertRaisesRegex(ObservationSchedulerError, "AUTHORITY_MISMATCH"):
                tick_once(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    schedule=schedule,
                    activation_id=activation_id,
                    now=NOW,
                    opener=_Opener(),
                    producer_git_sha=GIT_SHA,
                    discovery_rows=[],
                )
            store.close()

    def test_execute_path_rebuilds_typed_values_after_sqlite_delete(self) -> None:
        from solana_alpha_lab.factory.observation_panel_publisher import (
            rebuild_observation_panel_from_rdp,
        )

        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        schedule = dict(schedule)
        schedule["budgets"] = dict(schedule["budgets"])
        schedule["budgets"]["min_provider_pace_seconds"] = 0
        schedule["schedule_sha256"] = schedule_sha256(schedule)
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store_path = Path(tmp) / "ops.sqlite"
            store = ObservationScheduleStore(store_path)
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
                    }
                ],
            )
            tick_once(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule=schedule,
                activation_id=activation_id,
                now=datetime(2026, 9, 1, 0, 16, tzinfo=UTC),
                opener=_Opener(),
                producer_git_sha=GIT_SHA,
                discovery_rows=[],
            )
            store.close()
            store_path.unlink()
            rebuilt = rebuild_observation_panel_from_rdp(
                data_root=data_root,
                schedule_sha256=schedule["schedule_sha256"],
            )
            self.assertEqual({row["entity_id"] for row in rebuilt["members"]}, {MINT})
            values = {
                (row["point_id"], row["primitive_id"], item["field_id"]): item
                for row in rebuilt["observations"]
                for item in row.get("field_values") or []
            }
            self.assertEqual(
                values[
                    (
                        "X300",
                        "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                        "FIELD-LIQUIDITY-USD-001",
                    )
                ]["typed_value_or_null"],
                "2000",
            )
            self.assertEqual(
                values[
                    (
                        "X300",
                        "PRIM-JUPITER-SWAP-V2-QUOTE-BUY-001",
                        "FIELD-QUOTE-BUY-OUT-AMOUNT-001",
                    )
                ]["typed_value_or_null"],
                "9900000",
            )
            self.assertEqual(
                values[
                    (
                        "Y900",
                        "PRIM-JUPITER-SWAP-V2-DEPENDENT-REVERSE-SELL-001",
                        "FIELD-QUOTE-SELL-OUT-AMOUNT-001",
                    )
                ]["typed_value_or_null"],
                "9900000",
            )


if __name__ == "__main__":
    unittest.main()
