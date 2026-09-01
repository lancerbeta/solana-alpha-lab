"""Zero-network vertical proof for ALWAYS_ON_LIFECYCLE_COLLECTOR_READINESS_V1."""

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

from solana_alpha_lab.factory.collector_campaign_preflight import (  # noqa: E402
    SANCTIONED_CREDENTIAL_ENV,
    run_campaign_preflight,
)
from solana_alpha_lab.factory.collector_read_model import (  # noqa: E402
    build_collector_read_model,
)
from solana_alpha_lab.factory.collector_schedulability_oracle import (  # noqa: E402
    STOP_FREE_TIER_CAPACITY_NOT_PROVEN,
    classify_discovery_coverage,
    evaluate_schedulability,
    select_x_point,
)
from solana_alpha_lab.factory.observation_primitives import (  # noqa: E402
    HTTP_CLASS_401,
    HTTP_CLASS_403,
    HTTP_CLASS_429,
    HTTP_CLASS_5XX,
    HTTP_CLASS_TIMEOUT,
    HTTP_CLASS_TRANSPORT,
    classify_http_transport,
    execute_primitive,
)
from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    load_observation_schedule,
    render_utc,
)
from solana_alpha_lab.factory.observation_schedule_runtime import (  # noqa: E402
    ALLOWED_CREDENTIAL_ENV,
    CREDENTIAL_COMPAT_ALIAS_ENV,
    load_credential_after_activation,
)
from solana_alpha_lab.factory.observation_schedule_store import (  # noqa: E402
    ObservationScheduleStore,
)
from solana_alpha_lab.factory.observation_scheduler import (  # noqa: E402
    _recovered_result_from_ledger,
    tick_once,
)
from tests.test_observation_scheduler import (  # noqa: E402
    GIT_SHA,
    MINT,
    NOW,
    _Opener,
    _activate,
)


class _StatusOpener:
    def __init__(self, http_status: int | None = None, *, timeout: bool = False, transport: bool = False) -> None:
        self.http_status = http_status
        self.timeout = timeout
        self.transport = transport
        self.urls: list[str] = []

    def open(self, url: str) -> dict:
        self.urls.append(url)
        if self.timeout:
            raise TimeoutError("timeout")
        if self.transport:
            raise OSError("transport")
        assert self.http_status is not None
        return {"http_status": self.http_status, "body": {"error": "x"}, "url_has_api_key": False}


class CollectorReadinessTests(unittest.TestCase):
    def test_due_work_cannot_starve_source_poll(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            self.addCleanup(store.close)
            activation_id = _activate(store, schedule)
            # Seed a due observation so the old gate would suppress discovery.
            store.insert_due(
                {
                    "schedule_sha256": schedule["schedule_sha256"],
                    "activation_id": activation_id,
                    "entity_id": MINT,
                    "point_id": "X300",
                    "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                    "state": "DUE",
                    "due_at": render_utc(NOW),
                    "deadline_at": render_utc(NOW + timedelta(seconds=300)),
                    "request_sha256": None,
                    "call_occurrence_id": None,
                    "payload": {},
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
                now=NOW,
                opener=opener,
                producer_git_sha=GIT_SHA,
                max_claims=1,
            )
            self.assertTrue(
                any("/tokens/v2/recent" in url for url in opener.urls),
                msg=f"source poll starved; urls={opener.urls} result={result}",
            )
            # Continuous due backlog still cannot suppress the next poll slot.
            later = NOW + timedelta(seconds=60)
            opener2 = _Opener()
            tick_once(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule=schedule,
                activation_id=activation_id,
                now=later,
                opener=opener2,
                producer_git_sha=GIT_SHA,
                max_claims=1,
                last_tick_at=NOW,
            )
            self.assertTrue(
                any("/tokens/v2/recent" in url for url in opener2.urls),
                msg=f"second-period poll starved; urls={opener2.urls}",
            )
            store.close()

    def test_http_class_persists_and_recovers(self) -> None:
        cases = [
            (401, HTTP_CLASS_401),
            (403, HTTP_CLASS_403),
            (429, HTTP_CLASS_429),
            (503, HTTP_CLASS_5XX),
        ]
        for status, expected_class in cases:
            with self.subTest(status=status):
                schedule = load_observation_schedule(
                    ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
                )
                with tempfile.TemporaryDirectory() as tmp:
                    data_root = Path(tmp) / "rdp"
                    data_root.mkdir()
                    store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
                    self.addCleanup(store.close)
                    activation_id = _activate(store, schedule)
                    opener = _StatusOpener(status)
                    tick_once(
                        root=ROOT,
                        data_root=data_root,
                        store=store,
                        schedule=schedule,
                        activation_id=activation_id,
                        now=NOW,
                        opener=opener,
                        producer_git_sha=GIT_SHA,
                        max_claims=1,
                    )
                    calls = store.list_calls(
                        primitive_id="PRIM-JUPITER-TOKENS-V2-RECENT-001"
                    )
                    self.assertTrue(calls)
                    payload = calls[-1]["payload"]
                    self.assertEqual(payload.get("http_status"), status)
                    self.assertEqual(payload.get("http_class"), expected_class)
                    self.assertNotEqual(payload.get("status"), "OBSERVED")
                    recovered = _recovered_result_from_ledger(payload)
                    self.assertEqual(recovered["http_class"], expected_class)
                    self.assertEqual(recovered["http_status"], status)
                    self.assertEqual(
                        classify_http_transport(http_status=status)[1],
                        expected_class,
                    )
                    # Health readout sees the same class from the ledger.
                    model = build_collector_read_model(
                        store, now=NOW, empirical_overlap_seconds=60
                    )
                    bucket = {
                        401: "HTTP_401_24h",
                        403: "HTTP_403_24h",
                        429: "HTTP_429_24h",
                        503: "HTTP_5XX_24h",
                    }[status]
                    self.assertGreaterEqual(model[bucket], 1)
                    store.close()

    def test_timeout_and_transport_not_empty_market(self) -> None:
        for mode in ("timeout", "transport"):
            with self.subTest(mode=mode):
                opener = _StatusOpener(
                    timeout=(mode == "timeout"),
                    transport=(mode == "transport"),
                )
                result = execute_primitive(
                    primitive_id="PRIM-JUPITER-TOKENS-V2-RECENT-001",
                    primitive_version="1.0",
                    method="GET",
                    url="https://api.jup.ag/tokens/v2/recent",
                    opener=opener,
                    clock=lambda: NOW,
                )
                expected = (
                    HTTP_CLASS_TIMEOUT if mode == "timeout" else HTTP_CLASS_TRANSPORT
                )
                self.assertEqual(result.get("http_class"), expected)
                self.assertNotEqual(result.get("status"), "OBSERVED")
                self.assertNotEqual(result.get("missing_reason"), "EMPTY_MARKET")

    def test_credential_name_contract(self) -> None:
        self.assertEqual(ALLOWED_CREDENTIAL_ENV, frozenset({SANCTIONED_CREDENTIAL_ENV}))
        previous = {
            SANCTIONED_CREDENTIAL_ENV: os.environ.get(SANCTIONED_CREDENTIAL_ENV),
            CREDENTIAL_COMPAT_ALIAS_ENV: os.environ.get(CREDENTIAL_COMPAT_ALIAS_ENV),
        }
        try:
            os.environ.pop(SANCTIONED_CREDENTIAL_ENV, None)
            os.environ.pop(CREDENTIAL_COMPAT_ALIAS_ENV, None)
            os.environ[CREDENTIAL_COMPAT_ALIAS_ENV] = "PLACEHOLDER_ALIAS_ONLY"
            value = load_credential_after_activation(
                {"credential_env": SANCTIONED_CREDENTIAL_ENV}
            )
            self.assertEqual(value, "PLACEHOLDER_ALIAS_ONLY")
            os.environ[SANCTIONED_CREDENTIAL_ENV] = "PLACEHOLDER_SANCTIONED"
            value = load_credential_after_activation(
                {"credential_env": SANCTIONED_CREDENTIAL_ENV}
            )
            self.assertEqual(value, "PLACEHOLDER_SANCTIONED")
        finally:
            for key, prior in previous.items():
                if prior is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = prior

    def test_discovery_coverage_and_x_selection(self) -> None:
        self.assertEqual(
            classify_discovery_coverage(
                period_seconds=60, empirical_overlap_seconds=60
            ),
            "EMPIRICAL_OVERLAP_ONLY",
        )
        self.assertEqual(
            classify_discovery_coverage(
                period_seconds=60, empirical_overlap_seconds=None
            ),
            "GAP_SUSPECTED",
        )
        x, basis = select_x_point(timing_evidence_seconds=None)
        self.assertEqual(x, 300)
        self.assertIn("X300", basis)
        x2, _ = select_x_point(timing_evidence_seconds=[400, 450, 500])
        self.assertEqual(x2, 600)

    def test_campaign_preflight_deterministic_and_no_authority(self) -> None:
        first = run_campaign_preflight(
            root=ROOT,
            starts_at=datetime(2026, 9, 1, tzinfo=UTC),
            max_members_per_utc_day=50,
            candidate_launches_per_utc_day=2000,
            empirical_overlap_seconds=60,
        )
        second = run_campaign_preflight(
            root=ROOT,
            starts_at=datetime(2026, 9, 1, tzinfo=UTC),
            max_members_per_utc_day=50,
            candidate_launches_per_utc_day=2000,
            empirical_overlap_seconds=60,
        )
        self.assertEqual(first["terminal"], "CAMPAIGN_PREFLIGHT_PROPOSED")
        self.assertEqual(first["schedule_sha256"], second["schedule_sha256"])
        self.assertFalse(first["live_authority_granted"])
        self.assertEqual(first["authority_status"], "PROPOSED_NOT_AUTHORITY")
        self.assertEqual(first["network_calls"], 0)
        self.assertEqual(first["credential_reads"], 0)
        self.assertEqual(
            first["credential_runtime"]["sanctioned_env"], SANCTIONED_CREDENTIAL_ENV
        )
        text = json.dumps(first)
        self.assertNotIn("PLACEHOLDER", text)
        oracle = first["schedulability"]
        self.assertNotEqual(oracle["terminal"], STOP_FREE_TIER_CAPACITY_NOT_PROVEN)
        self.assertGreaterEqual(oracle["headroom_pct"], 25)
        schedule = first["schedule"]
        day = int(schedule["budgets"]["provider_calls_per_utc_day_max"])
        life = int(schedule["budgets"]["provider_calls_lifetime_max"])
        self.assertGreaterEqual(life, day)
        self.assertEqual(schedule["x_point"]["due_offset_seconds"], 300)

    def test_schedulability_models_worst_case_and_pace(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        result = evaluate_schedulability(
            root=ROOT,
            schedule=schedule,
            candidate_launches_per_utc_day=2000,
        )
        self.assertIn("WORST_CASE_UNBATCHED_SEARCH", result.stress_cases)
        self.assertGreaterEqual(result.min_provider_pace_seconds, 3)
        self.assertEqual(result.timer_cadence_seconds, 60)

    def test_collector_read_model_exposes_http_and_poll_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            self.addCleanup(store.close)
            store.start_call(
                request_sha256="a" * 64,
                call_occurrence_id="OCC-1",
                attempt_id="ATT-1",
                primitive_id="PRIM-JUPITER-TOKENS-V2-RECENT-001",
                payload={},
                clock=NOW,
            )
            store.complete_call(
                request_sha256="a" * 64,
                call_occurrence_id="OCC-1",
                attempt_id="ATT-1",
                payload={
                    "status": "MISSING_TYPED",
                    "missing_reason": "HTTP_ERROR",
                    "http_status": 429,
                    "http_class": HTTP_CLASS_429,
                },
                clock=NOW,
            )
            model = build_collector_read_model(store, now=NOW)
            self.assertEqual(model["HTTP_429_24h"], 1)
            self.assertIsNotNone(model["last_source_poll_attempt_at"])
            self.assertIn("discovery_coverage_class", model)
            self.assertIn("pending_due_count", model)
            store.close()


if __name__ == "__main__":
    unittest.main()
