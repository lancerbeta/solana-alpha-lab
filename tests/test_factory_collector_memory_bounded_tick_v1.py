"""Collector tick memory bounds, identity parity, and production-shape stress."""

from __future__ import annotations

import json
import os
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

from solana_alpha_lab.factory.live_cohort_source_bundle import (  # noqa: E402
    SOURCE_BUILD_RSS_CEILING_BYTES,
    peak_rss_bytes,
)
from solana_alpha_lab.factory.members_snapshot_delta import (  # noqa: E402
    append_delta_publication,
    write_snapshot_unit,
)
from solana_alpha_lab.factory.observation_panel_publisher import (  # noqa: E402
    PublicationFault,
    publish_observation_batch,
    repair_open_publication_jobs,
)
from solana_alpha_lab.factory.observation_publication_jobs import (  # noqa: E402
    open_dir,
)
from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    canonical_sha256,
    canonical_sha256_members_observations,
    load_observation_schedule,
    render_utc,
)
from solana_alpha_lab.factory.observation_schedule_store import (  # noqa: E402
    ObservationScheduleStore,
    reset_store_read_stats,
    store_read_stats,
)
from solana_alpha_lab.factory.observation_scheduler import (  # noqa: E402
    SEARCH,
    _member_snapshot,
    iter_member_snapshot,
    tick_once,
)

GIT_SHA = "c" * 40
NOW = datetime(2026, 9, 1, 0, 10, tzinfo=UTC)
STRESS_MEMBERS = 150_000
STRESS_DUE = 10_000
HARD_RSS_CEILING = 1024 * 1024 * 1024
TARGET_RSS = 768 * 1024 * 1024
C1_WORKER_RSS_CEILING = SOURCE_BUILD_RSS_CEILING_BYTES
HOST_RAM = int(5.8 * 1024 * 1024 * 1024)
INTERPRETER = [sys.executable, "-B"]
UNIT = ROOT / "configs" / "factory_remote_ops" / "factory-observation-schedule.service"
CLI = ROOT / "scripts" / "discovery_evidence_release.py"


class _Opener:
    def open(self, url: str) -> dict:
        if "/tokens/v2/search" in url:
            return {"http_status": 200, "body": [{"id": "MintStress", "liquidity": "2000"}]}
        return {"http_status": 200, "body": [{"id": "MintStress"}]}


def _activate(store: ObservationScheduleStore, schedule: dict, activation_id: str = "ACT-OBS-MEM-001") -> str:
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


def _entity(index: int) -> str:
    return f"Mint{index:06d}{'p' * 32}"


def _source_row(entity: str) -> dict:
    return {
        "id": entity,
        "symbol": "TST",
        "name": "test-token",
        "launchpad": "pump.fun",
        "liquidity": "12345.67",
        "mcap": "99999.12",
        "holderCount": 42,
        "stats5m": {"buyVolume": "10", "sellVolume": "11", "numBuys": 3, "numSells": 2},
        "firstPool": {"createdAt": "2026-09-01T00:00:00Z", "id": "pool-1"},
    }


def _candidate_row(digest: str, activation_id: str, entity: str, state: str = "SAMPLED_MEMBER") -> dict:
    return {
        "schedule_sha256": digest,
        "activation_id": activation_id,
        "entity_id": entity,
        "state": state,
        "payload": {
            "authoritative_anchor": "2026-09-01T00:00:00Z",
            "discovery_available_at": "2026-09-01T00:00:01Z",
            "inclusion_probability": "0.5",
            "sampling_seed": "seed-1",
            "source_row": _source_row(entity),
        },
    }


class CollectorMemoryBoundedTickTests(unittest.TestCase):
    def test_streaming_identity_matches_canonical_object_hash(self) -> None:
        cases = [
            [{"entity_id": "a", "text": "юникод", "flag": True, "missing": None, "nested": {"k": [1, False]}}],
            [{"entity_id": "b", "field_values": [{"field_id": "F1", "typed_value_or_null": None}]}],
            [{"entity_id": "c1"}, {"entity_id": "c0"}],
        ]
        observations = [
            {"primitive_id": SEARCH, "state": "OBSERVED", "ok": False},
            {"primitive_id": SEARCH, "state": "MISSING_TYPED", "nested": {"z": None}},
        ]
        for members in cases:
            old = canonical_sha256({"members": members, "observations": observations})
            streamed = canonical_sha256_members_observations(members, observations)
            self.assertEqual(old, streamed)

    def test_member_snapshot_matches_list_wrapper(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            try:
                activation_id = _activate(store, schedule)
                digest = schedule["schedule_sha256"]
                for index, state in enumerate(("SAMPLED_MEMBER", "ADMITTED", "CANDIDATE")):
                    store.insert_candidate(
                        _candidate_row(digest, activation_id, _entity(index), state),
                        clock=NOW,
                    )
                store.insert_due(
                    {
                        "schedule_sha256": digest,
                        "activation_id": activation_id,
                        "entity_id": _entity(0),
                        "point_id": "X300",
                        "primitive_id": SEARCH,
                        "state": "OBSERVED",
                        "due_at": "2026-09-01T00:05:00Z",
                        "deadline_at": "2026-09-01T00:20:00Z",
                        "payload": {},
                    },
                    clock=NOW,
                )
                listed = _member_snapshot(
                    store, digest=digest, activation_id=activation_id, now=NOW
                )
                streamed = list(
                    iter_member_snapshot(
                        store, digest=digest, activation_id=activation_id, now=NOW
                    )
                )
                self.assertEqual(listed, streamed)
                self.assertEqual([row["entity_id"] for row in listed], sorted(row["entity_id"] for row in listed))
            finally:
                store.close()

    def test_due_ledger_growth_uses_sql_count_not_fetchall(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            token = store.acquire_lease("owner", clock=NOW)
            try:
                digest = "a" * 64
                activation_id = "ACT-LEDGER"
                now_text = render_utc(NOW)
                batch = []
                for index in range(500_000):
                    batch.append(
                        (
                            digest,
                            activation_id,
                            _entity(index),
                            "X300",
                            SEARCH,
                            "OBSERVED",
                            "2026-09-01T00:01:00Z",
                            "2026-09-01T00:20:00Z",
                            "{}",
                            now_text,
                            now_text,
                        )
                    )
                    if len(batch) >= 5000:
                        store._conn.executemany(
                            """
                            INSERT INTO due_observations(
                                schedule_sha256, activation_id, entity_id, point_id, primitive_id,
                                state, due_at, deadline_at, payload_json, created_at, updated_at
                            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                            """,
                            batch,
                        )
                        batch = []
                if batch:
                    store._conn.executemany(
                        """
                        INSERT INTO due_observations(
                            schedule_sha256, activation_id, entity_id, point_id, primitive_id,
                            state, due_at, deadline_at, payload_json, created_at, updated_at
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        batch,
                    )
                store._conn.commit()
                reset_store_read_stats()
                count = store.count_due_in_states(
                    ("PENDING", "DUE", "CLAIMED"),
                    schedule_sha256=digest,
                    activation_id=activation_id,
                    due_at_max=NOW,
                    deadline_after=NOW,
                )
                bounded = store.list_due_in_states_scoped(
                    ("CLAIMED",),
                    schedule_sha256=digest,
                    activation_id=activation_id,
                    due_at_max=NOW,
                    limit=60,
                )
                stats = store_read_stats()
                self.assertEqual(count, 0)
                self.assertEqual(bounded, [])
                self.assertEqual(stats["due_in_states_calls"], 0)
                self.assertEqual(stats["due_in_states_rows"], 0)
                self.assertGreaterEqual(stats["count_due_in_states_calls"], 1)
            finally:
                if token:
                    store.release_lease(token)
                store.close()

    def test_per_claim_lookup_does_not_scan_full_candidate_universe(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            try:
                activation_id = _activate(store, schedule)
                digest = schedule["schedule_sha256"]
                token = store.acquire_lease("owner", clock=NOW)
                now_text = render_utc(NOW)
                candidates = [
                    (
                        digest,
                        activation_id,
                        _entity(index),
                        "SAMPLED_MEMBER",
                        json.dumps(_candidate_row(digest, activation_id, _entity(index))["payload"], sort_keys=True),
                        now_text,
                        now_text,
                    )
                    for index in range(3_000)
                ]
                store._conn.executemany(
                    """
                    INSERT INTO candidate_members(
                        schedule_sha256, activation_id, entity_id, state,
                        payload_json, created_at, updated_at
                    ) VALUES (?,?,?,?,?,?,?)
                    """,
                    candidates,
                )
                dues = []
                for index in range(60):
                    dues.append(
                        (
                            digest,
                            activation_id,
                            _entity(index),
                            "X300",
                            SEARCH,
                            "PENDING",
                            "2026-09-01T00:05:00Z",
                            "2026-09-01T00:20:00Z",
                            "{}",
                            now_text,
                            now_text,
                        )
                    )
                store._conn.executemany(
                    """
                    INSERT INTO due_observations(
                        schedule_sha256, activation_id, entity_id, point_id, primitive_id,
                        state, due_at, deadline_at, payload_json, created_at, updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    dues,
                )
                store._conn.commit()
                if token:
                    store.release_lease(token)
                reset_store_read_stats()
                tick_once(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    schedule=schedule,
                    activation_id=activation_id,
                    now=NOW,
                    opener=_Opener(),
                    producer_git_sha=GIT_SHA,
                    max_claims=60,
                    discovery_rows=[],
                )
                stats = store_read_stats()
                self.assertEqual(stats["list_candidates_calls"], 0)
                self.assertEqual(stats["due_in_states_calls"], 0)
                self.assertGreaterEqual(stats["get_candidate_calls"], 0)
            finally:
                store.close()

    def test_open_publication_job_does_not_embed_member_universe(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            members = [
                {
                    "schedule_sha256": schedule["schedule_sha256"],
                    "entity_id": _entity(index),
                    "membership_state": "SAMPLED_MEMBER",
                }
                for index in range(40)
            ]
            observations = [
                {
                    "schedule_sha256": schedule["schedule_sha256"],
                    "entity_id": members[0]["entity_id"],
                    "point_id": "X300",
                    "primitive_id": SEARCH,
                    "state": "OBSERVED",
                    "event_time": "2026-09-01T00:05:00Z",
                    "first_reliable_available_at": "2026-09-01T00:10:00Z",
                }
            ]
            with self.assertRaises(PublicationFault):
                publish_observation_batch(
                    data_root=data_root,
                    root=ROOT,
                    schedule=schedule,
                    activation_id="ACT-OBS-001",
                    now=NOW,
                    producer_git_sha=GIT_SHA,
                    members=members,
                    observations=observations,
                    fault_after="AFTER_ARTIFACTS",
                )
            open_jobs = list(open_dir(data_root).glob("*.json"))
            self.assertEqual(len(open_jobs), 1)
            payload = json.loads(open_jobs[0].read_text(encoding="utf-8"))
            self.assertNotIn("members", payload)
            self.assertEqual(payload["member_count"], 40)
            repaired = repair_open_publication_jobs(
                data_root=data_root,
                root=ROOT,
                schedule=schedule,
                activation_id="ACT-OBS-001",
                now=NOW,
                producer_git_sha=GIT_SHA,
            )
            self.assertEqual(len(repaired), 1)
            self.assertFalse(repaired[0]["replay"])

    def test_compact_delta_bytes_scale_with_changes(self) -> None:
        n = 4_096
        digest = "a" * 64
        previous = [
            {
                "entity_id": _entity(index),
                "membership_state": "SAMPLED_MEMBER",
                "field_values": [{"field_id": "F", "typed_value_or_null": "1"}],
            }
            for index in range(n)
        ]
        current = [dict(row) for row in previous]
        for index in range(100):
            current[index] = {
                **current[index],
                "membership_state": "OBSERVED",
            }
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            write_snapshot_unit(
                data_root,
                utc_day="20260901",
                dataset_manifest_id="dataset-000",
                rows=previous,
            )
            unit = append_delta_publication(
                data_root,
                utc_day="20260901",
                dataset_manifest_id="dataset-001",
                rows=current,
            )
            last = unit["publications"][-1]
            delta_path = data_root / str(last["rel"])
            self.assertLess(delta_path.stat().st_size, 200_000)
            self.assertEqual(last["row_count"], n)
            from solana_alpha_lab.factory.members_snapshot_delta import (
                _delta_file_is_monolith,
                reconstruct_publication,
                reset_fingerprint_work,
                reconstruct_stats,
            )

            self.assertFalse(_delta_file_is_monolith(delta_path, b""))
            reset_fingerprint_work()
            rows = reconstruct_publication(
                data_root, unit, str(last["dataset_manifest_id"])
            )
            self.assertEqual(len(rows), n)
            self.assertLessEqual(reconstruct_stats()["peak_sqlite_rows"], n)

    def test_due_points_prove_required_avoids_due_census(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            try:
                activation_id = _activate(store, schedule)
                digest = schedule["schedule_sha256"]
                for index in range(5_000):
                    store.insert_due(
                        {
                            "schedule_sha256": digest,
                            "activation_id": activation_id,
                            "entity_id": _entity(index),
                            "point_id": "X300",
                            "primitive_id": SEARCH,
                            "state": "OBSERVED",
                            "due_at": "2026-09-01T00:05:00Z",
                            "deadline_at": "2026-09-01T00:20:00Z",
                            "payload": {},
                        },
                        clock=NOW,
                    )
                # Microsecond-form due_at must not TEXT-order false-fail vs seconds now.
                store.insert_due(
                    {
                        "schedule_sha256": digest,
                        "activation_id": activation_id,
                        "entity_id": _entity(5_000),
                        "point_id": "X300",
                        "primitive_id": SEARCH,
                        "state": "OBSERVED",
                        "due_at": "2026-09-01T00:05:00.500000Z",
                        "deadline_at": "2026-09-01T00:20:00Z",
                        "payload": {},
                    },
                    clock=NOW,
                )
                reset_store_read_stats()
                proved = store.due_points_prove_required(
                    schedule_sha256=digest,
                    activation_id=activation_id,
                    required_points=["X300"],
                    now=NOW,
                )
                stats = store_read_stats()
                self.assertTrue(proved)
                self.assertEqual(stats["due_in_states_calls"], 0)
                self.assertEqual(stats["due_in_states_rows"], 0)
                # Exact-second now matching a seconds-form due_at is not "future".
                # Keep only dues at/before the equality bound for this check.
                self.assertTrue(
                    store.due_points_prove_required(
                        schedule_sha256=digest,
                        activation_id=activation_id,
                        required_points=["X300"],
                        now=datetime(2026, 9, 1, 0, 5, 0, 500000, tzinfo=UTC),
                    )
                )
                # Seconds-form bound must not TEXT-order-beat a later microsecond due_at.
                self.assertFalse(
                    store.due_points_prove_required(
                        schedule_sha256=digest,
                        activation_id=activation_id,
                        required_points=["X300"],
                        now=datetime(2026, 9, 1, 0, 5, 0, tzinfo=UTC),
                    )
                )
                self.assertFalse(
                    store.due_points_prove_required(
                        schedule_sha256=digest,
                        activation_id=activation_id,
                        required_points=["X300"],
                        now=datetime(2026, 9, 1, 0, 4, 59, tzinfo=UTC),
                    )
                )
            finally:
                store.close()

    def test_recovered_claimed_not_capped_by_max_claims(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            try:
                activation_id = _activate(store, schedule)
                digest = schedule["schedule_sha256"]
                for index in range(5):
                    store.insert_due(
                        {
                            "schedule_sha256": digest,
                            "activation_id": activation_id,
                            "entity_id": _entity(index),
                            "point_id": "X300",
                            "primitive_id": SEARCH,
                            "state": "CLAIMED",
                            "due_at": "2026-09-01T00:04:00Z",
                            "deadline_at": "2026-09-01T00:06:00Z",
                            "payload": {},
                        },
                        clock=NOW,
                    )
                recovered = store.list_due_in_states_scoped(
                    ("CLAIMED",),
                    schedule_sha256=digest,
                    activation_id=activation_id,
                    due_at_max=NOW,
                )
                capped = store.list_due_in_states_scoped(
                    ("CLAIMED",),
                    schedule_sha256=digest,
                    activation_id=activation_id,
                    due_at_max=NOW,
                    limit=2,
                )
                self.assertEqual(len(recovered), 5)
                self.assertEqual(len(capped), 2)
                # Tick contract: recovered path uses uncapped selection.
                self.assertGreater(len(recovered), 2)
            finally:
                store.close()

    def test_long_delta_chain_reconstruct_peak_is_census(self) -> None:
        from solana_alpha_lab.factory.members_snapshot_delta import (
            reconstruct_publication,
            reset_fingerprint_work,
            reconstruct_stats,
        )

        n = 512
        rows = [
            {
                "entity_id": _entity(index),
                "membership_state": "SAMPLED_MEMBER",
                "field_values": [{"field_id": "F", "typed_value_or_null": "0"}],
            }
            for index in range(n)
        ]
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            write_snapshot_unit(
                data_root,
                utc_day="20260901",
                dataset_manifest_id="dataset-000",
                rows=rows,
            )
            unit = None
            current = rows
            for step in range(1, 21):
                nxt = [dict(row) for row in current]
                nxt[step % n] = {
                    **nxt[step % n],
                    "field_values": [
                        {"field_id": "F", "typed_value_or_null": str(step)}
                    ],
                }
                unit = append_delta_publication(
                    data_root,
                    utc_day="20260901",
                    dataset_manifest_id=f"dataset-{step:03d}",
                    rows=nxt,
                )
                current = nxt
            assert unit is not None
            reset_fingerprint_work()
            reconstructed = reconstruct_publication(
                data_root, unit, str(unit["publications"][-1]["dataset_manifest_id"])
            )
            self.assertEqual(len(reconstructed), n)
            self.assertLessEqual(reconstruct_stats()["peak_sqlite_rows"], n)


    def test_systemd_template_has_memory_fence_not_timeout(self) -> None:
        text = UNIT.read_text(encoding="utf-8")
        self.assertIn("MemoryHigh=768M", text)
        self.assertIn("MemoryMax=1G", text)
        self.assertIn("MemoryAccounting=yes", text)
        self.assertNotIn("TimeoutStartSec=", text)

    def test_joint_software_concurrency_budget(self) -> None:
        collector_max = HARD_RSS_CEILING
        c1_worker = C1_WORKER_RSS_CEILING
        os_and_workbench = 768 * 1024 * 1024
        remaining = HOST_RAM - collector_max - c1_worker - os_and_workbench
        self.assertGreater(remaining, 256 * 1024 * 1024)
        self.assertLessEqual(collector_max + c1_worker, HOST_RAM - os_and_workbench)

    def test_downstream_vps_killer_audit_fenced_and_local(self) -> None:
        cli = CLI.read_text(encoding="utf-8")
        self.assertIn("build-live-source", cli)
        self.assertIn("list-live-cohorts", cli)
        self.assertIn("live-status", cli)
        self.assertIn("seal-live-cohort", cli)
        self.assertIn("verify-live", cli)
        self.assertIn("SOURCE_BUILD_WORKER_ENV", cli)
        self.assertIn("import-live", cli)
        self.assertIn("forge-control-ready", cli)
        self.assertIn("apply_source_build_address_limit", SRC.joinpath("solana_alpha_lab/factory/live_cohort_source_bundle.py").read_text(encoding="utf-8"))

    def test_production_shape_tick_stays_under_rss_ceiling(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            payload_path = Path(tmp) / "payload.json"
            result_path = Path(tmp) / "result.json"
            payload_path.write_text(
                json.dumps(
                    {
                        "tmp": tmp,
                        "root": str(ROOT),
                        "schedule_rel": "tests/fixtures/observation_schedule/x300_y900.yaml",
                        "n": STRESS_MEMBERS,
                        "due": STRESS_DUE,
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [*INTERPRETER, str(Path(__file__).resolve()), str(payload_path), str(result_path)],
                cwd=str(ROOT),
                env={**os.environ, "FACTORY_COLLECTOR_STRESS_WORKER": "1", "PYTHONPATH": str(SRC)},
                capture_output=True,
                text=True,
            )
            if proc.returncode != 0:
                self.fail(proc.stderr[-4000:] or proc.stdout[-4000:] or str(proc.returncode))
            result = json.loads(result_path.read_text(encoding="utf-8"))
            print(
                f"COLLECTOR_STRESS_MAX_RSS_BYTES={result['max_rss_bytes']}",
                file=sys.stderr,
                flush=True,
            )
            self.assertEqual(result["candidates"], STRESS_MEMBERS)
            self.assertEqual(result["due_in_states_calls"], 0)
            self.assertEqual(result["list_candidates_calls"], 0)
            self.assertLessEqual(int(result["max_rss_bytes"]), HARD_RSS_CEILING)
            self.assertLessEqual(int(result["open_job_members_embedded"]), 0)
            if int(result["max_rss_bytes"]) > TARGET_RSS:
                self.assertLessEqual(int(result["max_rss_bytes"]), HARD_RSS_CEILING)


def _stress_worker(payload_path: str, result_path: str) -> None:
    from unittest.mock import patch

    from solana_alpha_lab.factory.hot90_activation import STAGE_WRITE_ONLY_SHADOW

    payload = json.loads(Path(payload_path).read_text(encoding="utf-8"))
    tmp = Path(payload["tmp"])
    n = int(payload["n"])
    due_n = int(payload["due"])
    schedule = load_observation_schedule(ROOT, payload["schedule_rel"])
    data_root = tmp / "rdp" if isinstance(tmp, Path) else Path(payload["tmp"]) / "rdp"
    data_root.mkdir(parents=True, exist_ok=True)
    store = ObservationScheduleStore(Path(payload["tmp"]) / "ops.sqlite")
    activation_id = _activate(store, schedule, activation_id="ACT-OBS-STRESS")
    digest = schedule["schedule_sha256"]
    token = store.acquire_lease("owner", clock=NOW)
    now_text = render_utc(NOW)
    hot90 = {
        "activation_stage": STAGE_WRITE_ONLY_SHADOW,
        "production_compaction_enabled": False,
        "production_eviction_enabled": False,
        "drive_writes_enabled": False,
        "members_layout": "SNAPSHOT_PLUS_DELTA",
        "new_write_zstd": True,
        "activation_source": "OVERRIDE",
    }
    batch = []
    mixed = ("PENDING", "OBSERVED", "MISSING_TYPED", "CENSORED", "CENSORED_LATE", "DISAPPEARED")
    for index in range(n):
        entity = _entity(index)
        cand_payload = json.dumps(
            _candidate_row(digest, activation_id, entity)["payload"], sort_keys=True
        )
        batch.append(
            (digest, activation_id, entity, "SAMPLED_MEMBER", cand_payload, now_text, now_text)
        )
        if len(batch) >= 1000:
            store._conn.executemany(
                """
                INSERT INTO candidate_members(
                    schedule_sha256, activation_id, entity_id, state,
                    payload_json, created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?)
                """,
                batch,
            )
            batch = []
    if batch:
        store._conn.executemany(
            """
            INSERT INTO candidate_members(
                schedule_sha256, activation_id, entity_id, state,
                payload_json, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?)
            """,
            batch,
        )
    due_rows = []
    for index in range(due_n):
        due_rows.append(
            (
                digest,
                activation_id,
                _entity(index),
                "Y900",
                SEARCH,
                mixed[index % len(mixed)],
                "2026-09-01T00:01:00Z",
                "2026-09-01T00:30:00Z",
                "{}",
                now_text,
                now_text,
            )
        )
    for index in range(60):
        due_rows.append(
            (
                digest,
                activation_id,
                _entity(index),
                "X300",
                SEARCH,
                "PENDING",
                "2026-09-01T00:05:00Z",
                "2026-09-01T00:20:00Z",
                "{}",
                now_text,
                now_text,
            )
        )
    store._conn.executemany(
        """
        INSERT INTO due_observations(
            schedule_sha256, activation_id, entity_id, point_id, primitive_id,
            state, due_at, deadline_at, payload_json, created_at, updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        due_rows,
    )
    store._conn.commit()
    if token:
        store.release_lease(token)
    write_snapshot_unit(
        data_root,
        utc_day="20260901",
        dataset_manifest_id="dataset-prev",
        rows=iter_member_snapshot(
            store, digest=digest, activation_id=activation_id, now=NOW
        ),
    )
    reset_store_read_stats()
    with patch(
        "solana_alpha_lab.factory.observation_panel_publisher.load_hot90_activation",
        return_value=hot90,
    ):
        tick_once(
            root=ROOT,
            data_root=data_root,
            store=store,
            schedule=schedule,
            activation_id=activation_id,
            now=NOW + timedelta(seconds=1),
            opener=_Opener(),
            producer_git_sha=GIT_SHA,
            max_claims=60,
            discovery_rows=[],
        )
    stats = store_read_stats()
    open_jobs = list(open_dir(data_root).glob("*.json"))
    embedded = 0
    for path in open_jobs:
        job = json.loads(path.read_text(encoding="utf-8"))
        members = job.get("members")
        if isinstance(members, list):
            embedded = max(embedded, len(members))
    Path(result_path).write_text(
        json.dumps(
            {
                "candidates": n,
                "max_rss_bytes": peak_rss_bytes(),
                "due_in_states_calls": stats["due_in_states_calls"],
                "list_candidates_calls": stats["list_candidates_calls"],
                "open_job_members_embedded": embedded,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    store.close()


if os.environ.get("FACTORY_COLLECTOR_STRESS_WORKER") == "1":
    _stress_worker(sys.argv[1], sys.argv[2])
elif __name__ == "__main__":
    unittest.main()
