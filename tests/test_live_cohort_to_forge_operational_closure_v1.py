"""Production-shape live cohort → Forge CONTROL closure. Zero network."""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.discovery_evidence_release import DiscoveryReleaseError  # noqa: E402
from solana_alpha_lab.factory.live_cohort_discovery_release import (  # noqa: E402
    LiveCohortReleaseError,
    _worst_coverage,
    build_live_observation_source_from_rdp,
    classify_cohort_readiness,
    cohort_id_for_admission,
    load_observation_rdp_source,
    write_observation_rdp_source,
)
from solana_alpha_lab.factory.live_cohort_to_forge import (  # noqa: E402
    CONTROL_NEXT,
    LiveCohortToForgeError,
    assert_closure_ready,
    build_closure_receipt,
    default_sealed_release_root,
    forge_control_ready,
    hash_release_tree,
    list_live_cohorts,
    publish_live_cohort,
    resolve_operator_path,
    synthetic_closed_receipt,
    verify_transported_release,
)
from solana_alpha_lab.factory.observation_panel_publisher import (  # noqa: E402
    persist_observation_schedule,
    publish_observation_batch,
)
from solana_alpha_lab.factory.observation_publication_jobs import (  # noqa: E402
    open_dir,
)
from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    load_observation_schedule,
    schedule_sha256,
    validate_observation_schedule,
)

PRODUCER_A = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
PRODUCER_B = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
PRODUCER_C = "cccccccccccccccccccccccccccccccccccccccc"
ACTIVATION = "ACT-619AE64E885E995E"
COHORT1 = "REL-20260902T111900Z-20260909T111900Z"
COHORT2 = "REL-20260909T111900Z-20260916T111900Z"
AS_OF_C1 = datetime(2026, 9, 10, 16, 58, 0, tzinfo=UTC)
AS_OF_C2 = datetime(2026, 9, 17, 12, 0, 0, tzinfo=UTC)
C1_ADMIT = datetime(2026, 9, 2, 12, 0, 0, tzinfo=UTC)
C2_ADMIT = datetime(2026, 9, 9, 12, 0, 0, tzinfo=UTC)
PUBLISH_C1 = C1_ADMIT
PUBLISH_C2 = C2_ADMIT


def _schedule(root: Path) -> dict:
    schedule = load_observation_schedule(
        root, "tests/fixtures/observation_schedule/x300_y900.yaml"
    )
    schedule = dict(schedule)
    schedule.pop("schedule_sha256", None)
    schedule["activation"] = {
        **dict(schedule.get("activation") or {}),
        "starts_at": "2026-09-02T11:19:00Z",
        "stops_admitting_at": "2026-09-23T11:19:00Z",
        "cadence_alignment": "UTC_EPOCH",
    }
    schedule["sampling"] = {
        "policy": "DETERMINISTIC_HASH_BERNOULLI",
        "seed": "ALWAYS-ON-LIFECYCLE-COLLECTOR-V1",
        "inclusion_probability": "0.0425",
        "max_candidates_per_utc_day": 2000,
        "max_members_per_utc_day": 85,
        "overflow_state": "NOT_SELECTED_CAPACITY",
    }
    validated = validate_observation_schedule(schedule, root=root)
    digest = schedule_sha256(validated)
    validated["schedule_sha256"] = digest
    return validated


def _entity(prefix: str, index: int) -> str:
    return f"{prefix}{index:02d}{'1' * 32}"


def _member(digest: str, entity: str, admission: datetime) -> dict:
    stamp = admission.strftime("%Y-%m-%dT%H:%M:%SZ")
    available = (admission + timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "schedule_sha256": digest,
        "activation_id": ACTIVATION,
        "entity_id": entity,
        "membership_state": "OBSERVED",
        "candidate_state": "ADMITTED",
        "authoritative_anchor": stamp,
        "inclusion_probability": "0.0425",
        "sampling_seed": "ALWAYS-ON-LIFECYCLE-COLLECTOR-V1",
        "first_reliable_available_at": available,
        "request_sha256": "a" * 64,
        "response_sha256": "b" * 64,
    }


def _obs(digest: str, entity: str, admission: datetime) -> dict:
    stamp = admission.strftime("%Y-%m-%dT%H:%M:%SZ")
    available = (admission + timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "schedule_sha256": digest,
        "activation_id": ACTIVATION,
        "entity_id": entity,
        "point_id": "X300",
        "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
        "state": "OBSERVED",
        "event_time": stamp,
        "first_reliable_available_at": available,
        "request_started_at": stamp,
        "response_received_at": available,
        "request_sha256": "c" * 64,
        "response_sha256": "d" * 64,
        "call_occurrence_id": "e" * 64,
        "http_status": 200,
        "http_class": "HTTP_OK",
        "field_values": [
            {
                "field_id": "FIELD-LIQUIDITY-USD-001",
                "value_kind": "DECIMAL",
                "typed_value_or_null": "1.0",
                "state": "OBSERVED",
                "missing_reason": None,
                "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                "point_id": "X300",
                "event_time": stamp,
                "first_reliable_available_at": available,
                "request_sha256": "c" * 64,
                "call_occurrence_id": "e" * 64,
            }
        ],
    }


def _init_ops(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE candidate_members (
                schedule_sha256 TEXT NOT NULL,
                activation_id TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                state TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (schedule_sha256, activation_id, entity_id)
            );
            CREATE TABLE due_observations (
                schedule_sha256 TEXT NOT NULL,
                activation_id TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                point_id TEXT NOT NULL,
                primitive_id TEXT NOT NULL,
                state TEXT NOT NULL,
                due_at TEXT NOT NULL,
                deadline_at TEXT NOT NULL,
                request_sha256 TEXT,
                call_occurrence_id TEXT,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (
                    schedule_sha256, activation_id, entity_id, point_id, primitive_id
                )
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def _put_member_due(
    conn: sqlite3.Connection,
    *,
    digest: str,
    entity: str,
    admission: datetime,
    member_state: str,
    due_state: str,
    due_at: datetime,
    write_due: bool = True,
) -> None:
    payload = json.dumps(
        {"first_reliable_available_at": admission.strftime("%Y-%m-%dT%H:%M:%SZ")},
        sort_keys=True,
    )
    conn.execute(
        """
        INSERT INTO candidate_members(
            schedule_sha256, activation_id, entity_id, state,
            payload_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            digest,
            ACTIVATION,
            entity,
            member_state,
            payload,
            "2026-09-02T12:00:00Z",
            "2026-09-02T12:00:00Z",
        ),
    )
    if not write_due:
        return
    conn.execute(
        """
        INSERT INTO due_observations(
            schedule_sha256, activation_id, entity_id, point_id, primitive_id,
            state, due_at, deadline_at, payload_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            digest,
            ACTIVATION,
            entity,
            "X300",
            "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
            due_state,
            due_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            (due_at + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "{}",
            "2026-09-02T12:00:00Z",
            "2026-09-02T12:00:00Z",
        ),
    )


def _seed_ops(
    path: Path,
    *,
    digest: str,
    cohort1: list[str],
    cohort2: list[str],
    c1_due: str = "OBSERVED",
    dues: bool = True,
) -> None:
    _init_ops(path)
    conn = sqlite3.connect(path)
    try:
        for entity in cohort1:
            _put_member_due(
                conn,
                digest=digest,
                entity=entity,
                admission=C1_ADMIT,
                member_state="ADMITTED",
                due_state=c1_due,
                due_at=datetime(2026, 9, 3, 0, 0, tzinfo=UTC),
                write_due=dues,
            )
        for entity in cohort2:
            _put_member_due(
                conn,
                digest=digest,
                entity=entity,
                admission=C2_ADMIT,
                member_state="ADMITTED",
                due_state="PENDING",
                due_at=datetime(2026, 9, 11, 12, 0, tzinfo=UTC),
                write_due=dues,
            )
        conn.commit()
    finally:
        conn.close()


def _cli_module():
    spec = importlib.util.spec_from_file_location(
        "discovery_evidence_release_cli",
        ROOT / "scripts" / "discovery_evidence_release.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LiveCohortToForgeOperationalClosureTests(unittest.TestCase):
    def test_worst_coverage_does_not_upgrade(self) -> None:
        self.assertEqual(
            _worst_coverage(["EMPIRICAL_OVERLAP_ONLY", "GAP_SUSPECTED"]),
            "GAP_SUSPECTED",
        )
        self.assertEqual(_worst_coverage(["GAP_CONFIRMED", "GAP_SUSPECTED"]), "GAP_CONFIRMED")
        self.assertEqual(_worst_coverage([]), "DISCOVERY_COVERAGE_UNKNOWN")

    def test_relative_operator_path_resolves_against_repo_root(self) -> None:
        resolved = resolve_operator_path(ROOT, "local/factory_v1/observation_rdp")
        self.assertEqual(
            resolved, (ROOT / "local/factory_v1/observation_rdp").resolve()
        )
        self.assertTrue(resolved.is_absolute())

    def test_register_before_activation_multi_producer_and_coverage(self) -> None:
        schedule = _schedule(ROOT)
        digest = schedule["schedule_sha256"]
        c1 = [_entity("A", i) for i in range(6)]
        c1_b = [_entity("B", i) for i in range(6)]
        c2 = [_entity("C", i) for i in range(3)]
        with tempfile.TemporaryDirectory() as tmp:
            observation_rdp = Path(tmp) / "observation_rdp"
            observation_rdp.mkdir()
            persist_observation_schedule(
                data_root=observation_rdp,
                schedule=schedule,
                now=C1_ADMIT,
                producer_git_sha=PRODUCER_A,
                activation_id=None,
            )
            publish_observation_batch(
                data_root=observation_rdp,
                root=ROOT,
                schedule=schedule,
                activation_id=ACTIVATION,
                now=PUBLISH_C1,
                producer_git_sha=PRODUCER_A,
                members=[_member(digest, entity, C1_ADMIT) for entity in c1],
                observations=[_obs(digest, entity, C1_ADMIT) for entity in c1],
            )
            publish_observation_batch(
                data_root=observation_rdp,
                root=ROOT,
                schedule=schedule,
                activation_id=ACTIVATION,
                now=C1_ADMIT + timedelta(minutes=1),
                producer_git_sha=PRODUCER_B,
                members=[_member(digest, entity, C1_ADMIT + timedelta(minutes=1)) for entity in c1_b],
                observations=[
                    _obs(digest, entity, C1_ADMIT + timedelta(minutes=1)) for entity in c1_b
                ],
            )
            receipt = synthetic_closed_receipt(
                schedule_sha256=digest,
                activation_id=ACTIVATION,
                cohort_id=COHORT1,
                as_of=AS_OF_C1,
                members_total=12,
            )
            source = build_live_observation_source_from_rdp(
                observation_rdp_root=observation_rdp,
                schedule_sha256=digest,
                activation_id=ACTIVATION,
                cohort_id=COHORT1,
                as_of=AS_OF_C1,
                closure_receipt=receipt,
                discovery_coverage_class="GAP_SUSPECTED",
            )
            self.assertEqual(
                source["contributing_producer_git_shas"],
                [PRODUCER_A, PRODUCER_B],
            )
            self.assertNotIn("producer_git_sha", source)
            self.assertEqual(source["discovery_coverage_class"], "GAP_SUSPECTED")
            self.assertEqual(source["cohort_id"], COHORT1)
            self.assertEqual(len(source["members"]), 12)
            first_sha = source["source_sha256"]
            publish_observation_batch(
                data_root=observation_rdp,
                root=ROOT,
                schedule=schedule,
                activation_id=ACTIVATION,
                now=PUBLISH_C2,
                producer_git_sha=PRODUCER_C,
                members=[_member(digest, entity, C2_ADMIT) for entity in c2]
                + [_member(digest, c1[0], C1_ADMIT)],
                observations=[_obs(digest, entity, C2_ADMIT) for entity in c2]
                + [_obs(digest, c1[0], C2_ADMIT)],
            )
            again = build_live_observation_source_from_rdp(
                observation_rdp_root=observation_rdp,
                schedule_sha256=digest,
                activation_id=ACTIVATION,
                cohort_id=COHORT1,
                as_of=AS_OF_C1,
                closure_receipt=receipt,
                discovery_coverage_class="GAP_SUSPECTED",
            )
            self.assertEqual(again["source_sha256"], first_sha)
            later_clock = build_live_observation_source_from_rdp(
                observation_rdp_root=observation_rdp,
                schedule_sha256=digest,
                activation_id=ACTIVATION,
                cohort_id=COHORT1,
                as_of=AS_OF_C1 + timedelta(hours=3),
                closure_receipt=synthetic_closed_receipt(
                    schedule_sha256=digest,
                    activation_id=ACTIVATION,
                    cohort_id=COHORT1,
                    as_of=AS_OF_C1 + timedelta(hours=3),
                    members_total=12,
                ),
                discovery_coverage_class="GAP_SUSPECTED",
            )
            self.assertEqual(later_clock["source_sha256"], first_sha)
            self.assertEqual(later_clock["closure_receipt_sha256"], again["closure_receipt_sha256"])
            self.assertEqual(again["contributing_producer_git_shas"], [PRODUCER_A, PRODUCER_B])
            c2_source = build_live_observation_source_from_rdp(
                observation_rdp_root=observation_rdp,
                schedule_sha256=digest,
                activation_id=ACTIVATION,
                cohort_id=COHORT2,
                as_of=AS_OF_C2,
                closure_receipt=synthetic_closed_receipt(
                    schedule_sha256=digest,
                    activation_id=ACTIVATION,
                    cohort_id=COHORT2,
                    as_of=AS_OF_C2,
                    members_total=3,
                ),
            )
            self.assertEqual(c2_source["contributing_producer_git_shas"], [PRODUCER_C])
            self.assertEqual(len(c2_source["members"]), 3)
            self.assertTrue(
                set(m["mint"] for m in c2_source["members"]).isdisjoint(
                    {m["mint"] for m in again["members"]}
                )
            )

    def test_missing_activation_and_missing_receipt_fail_closed(self) -> None:
        schedule = _schedule(ROOT)
        digest = schedule["schedule_sha256"]
        with tempfile.TemporaryDirectory() as tmp:
            observation_rdp = Path(tmp) / "observation_rdp"
            observation_rdp.mkdir()
            persist_observation_schedule(
                data_root=observation_rdp,
                schedule=schedule,
                now=C1_ADMIT,
                producer_git_sha=PRODUCER_A,
                activation_id=None,
            )
            receipt = synthetic_closed_receipt(
                schedule_sha256=digest,
                activation_id=ACTIVATION,
                cohort_id=COHORT1,
                as_of=AS_OF_C1,
            )
            with self.assertRaises(LiveCohortReleaseError) as missing:
                build_live_observation_source_from_rdp(
                    observation_rdp_root=observation_rdp,
                    schedule_sha256=digest,
                    activation_id=ACTIVATION,
                    cohort_id=COHORT1,
                    closure_receipt=receipt,
                )
            self.assertEqual(str(missing.exception), "LIVE_SOURCE_ACTIVATION_MISSING")
            with self.assertRaises(DiscoveryReleaseError) as no_receipt:
                build_live_observation_source_from_rdp(
                    observation_rdp_root=observation_rdp,
                    schedule_sha256=digest,
                    activation_id=ACTIVATION,
                    cohort_id=COHORT1,
                )
            self.assertEqual(str(no_receipt.exception), "CLOSED_RECEIPT_MISSING")

    def test_cohort2_pending_does_not_block_cohort1_closure(self) -> None:
        schedule = _schedule(ROOT)
        digest = schedule["schedule_sha256"]
        c1 = [_entity("A", i) for i in range(3)]
        c2 = [_entity("C", i) for i in range(2)]
        with tempfile.TemporaryDirectory() as tmp:
            observation_rdp = Path(tmp) / "observation_rdp"
            ops = Path(tmp) / "ops.sqlite"
            observation_rdp.mkdir()
            _seed_ops(ops, digest=digest, cohort1=c1, cohort2=c2)
            receipt = build_closure_receipt(
                ops_store=ops,
                observation_rdp=observation_rdp,
                schedule_sha256=digest,
                activation_id=ACTIVATION,
                cohort_id=COHORT1,
                as_of=AS_OF_C1,
            )
            self.assertEqual(receipt["pending_due_for_cohort"], 0)
            self.assertEqual(receipt["pending_future"], 0)
            assert_closure_ready(receipt)
            open_receipt = build_closure_receipt(
                ops_store=ops,
                observation_rdp=observation_rdp,
                schedule_sha256=digest,
                activation_id=ACTIVATION,
                cohort_id=COHORT2,
                as_of=AS_OF_C2,
            )
            self.assertGreater(open_receipt["pending_due_for_cohort"], 0)
            with self.assertRaises(LiveCohortToForgeError) as pending:
                assert_closure_ready(open_receipt)
            self.assertEqual(str(pending.exception), "COHORT_DUE_OPEN")

    def test_open_publication_and_incomplete_dues_fail_closed(self) -> None:
        schedule = _schedule(ROOT)
        digest = schedule["schedule_sha256"]
        c1 = [_entity("A", i) for i in range(3)]
        with tempfile.TemporaryDirectory() as tmp:
            observation_rdp = Path(tmp) / "observation_rdp"
            ops = Path(tmp) / "ops.sqlite"
            observation_rdp.mkdir()
            _seed_ops(ops, digest=digest, cohort1=c1, cohort2=[], c1_due="PENDING")
            receipt = build_closure_receipt(
                ops_store=ops,
                observation_rdp=observation_rdp,
                schedule_sha256=digest,
                activation_id=ACTIVATION,
                cohort_id=COHORT1,
                as_of=AS_OF_C1,
            )
            with self.assertRaises(LiveCohortToForgeError):
                assert_closure_ready(receipt)
            empty = Path(tmp) / "empty.sqlite"
            _seed_ops(empty, digest=digest, cohort1=c1, cohort2=[], dues=False)
            missing_dues = build_closure_receipt(
                ops_store=empty,
                observation_rdp=observation_rdp,
                schedule_sha256=digest,
                activation_id=ACTIVATION,
                cohort_id=COHORT1,
                as_of=AS_OF_C1,
            )
            with self.assertRaises(LiveCohortToForgeError) as incomplete:
                assert_closure_ready(missing_dues)
            self.assertEqual(str(incomplete.exception), "CLOSED_RECEIPT_INCOMPLETE")
            jobs = open_dir(observation_rdp)
            jobs.mkdir(parents=True)
            (jobs / "job.json").write_text(
                json.dumps(
                    {
                        "schedule_sha256": digest,
                        "activation_id": ACTIVATION,
                        "members": [
                            {
                                "first_reliable_available_at": "2026-09-02T12:00:00Z",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            _seed_ops(Path(tmp) / "ops2.sqlite", digest=digest, cohort1=c1, cohort2=[])
            pub = build_closure_receipt(
                ops_store=Path(tmp) / "ops2.sqlite",
                observation_rdp=observation_rdp,
                schedule_sha256=digest,
                activation_id=ACTIVATION,
                cohort_id=COHORT1,
                as_of=AS_OF_C1,
            )
            with self.assertRaises(LiveCohortToForgeError) as opened:
                assert_closure_ready(pub)
            self.assertEqual(str(opened.exception), "PUBLICATION_OPEN")

    def test_gap_confirmed_not_sealable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snap = {
                "schedule_sha256": "a" * 64,
                "activation_id": ACTIVATION,
                "producer_git_sha": PRODUCER_A,
                "starts_at": "2026-09-02T11:19:00Z",
                "stops_admitting_at": "2026-09-23T11:19:00Z",
                "discovery_coverage_class": "GAP_CONFIRMED",
                "open_publication": False,
                "unresolved_due": False,
                "in_flight": False,
                "budget_blocked": False,
                "closure_receipt_sha256": "c" * 64,
                "members": [
                    {
                        "mint": f"Mint{i}",
                        "discovery_first_reliable_available_at": "2026-09-02T12:00:00Z",
                        "authoritative_anchor": "2026-09-02T12:00:00Z",
                        "candidate_state": "ADMITTED",
                        "membership_state": "OBSERVED",
                        "denominator_state": "observed",
                        "sampling_policy": "HASH",
                        "sampling_seed": "s",
                        "inclusion_probability": "0.1",
                        "selected_or_excluded": "SELECTED",
                    }
                    for i in range(5)
                ],
                "observations": [],
            }
            write_observation_rdp_source(root, snap)
            ready = classify_cohort_readiness(
                load_observation_rdp_source(root),
                cohort_id=COHORT1,
                as_of=AS_OF_C1,
            )
            self.assertEqual(ready["state"], "COVERAGE_CONFIRMED_BROKEN")
            self.assertFalse(ready["sealable"])

    def test_transport_hash_and_publish_forge_control_ready(self) -> None:
        schedule = _schedule(ROOT)
        digest = schedule["schedule_sha256"]
        c1 = [_entity("A", i) for i in range(6)]
        c1_b = [_entity("B", i) for i in range(6)]
        c2 = [_entity("C", i) for i in range(3)]
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            observation_rdp = base / "observation_rdp"
            data_root = base / "data_plane"
            ops = base / "ops.sqlite"
            observation_rdp.mkdir()
            data_root.mkdir()
            persist_observation_schedule(
                data_root=observation_rdp,
                schedule=schedule,
                now=C1_ADMIT,
                producer_git_sha=PRODUCER_A,
                activation_id=None,
            )
            publish_observation_batch(
                data_root=observation_rdp,
                root=ROOT,
                schedule=schedule,
                activation_id=ACTIVATION,
                now=PUBLISH_C1,
                producer_git_sha=PRODUCER_A,
                members=[_member(digest, entity, C1_ADMIT) for entity in c1],
                observations=[_obs(digest, entity, C1_ADMIT) for entity in c1],
            )
            publish_observation_batch(
                data_root=observation_rdp,
                root=ROOT,
                schedule=schedule,
                activation_id=ACTIVATION,
                now=C1_ADMIT + timedelta(minutes=2),
                producer_git_sha=PRODUCER_B,
                members=[
                    _member(digest, entity, C1_ADMIT + timedelta(minutes=2))
                    for entity in c1_b
                ],
                observations=[
                    _obs(digest, entity, C1_ADMIT + timedelta(minutes=2))
                    for entity in c1_b
                ],
            )
            publish_observation_batch(
                data_root=observation_rdp,
                root=ROOT,
                schedule=schedule,
                activation_id=ACTIVATION,
                now=PUBLISH_C2,
                producer_git_sha=PRODUCER_C,
                members=[_member(digest, entity, C2_ADMIT) for entity in c2],
                observations=[_obs(digest, entity, C2_ADMIT) for entity in c2],
            )
            _seed_ops(ops, digest=digest, cohort1=c1 + c1_b, cohort2=c2)
            listed = list_live_cohorts(
                observation_rdp=observation_rdp,
                ops_store=ops,
                schedule_sha256=digest,
                activation_id=ACTIVATION,
                data_root=data_root,
                as_of=AS_OF_C1,
            )
            self.assertEqual(listed["next_unimported_mature"], COHORT1)
            cli = _cli_module()
            from io import StringIO
            from contextlib import redirect_stdout

            buf = StringIO()
            with redirect_stdout(buf):
                code = cli.main(
                    [
                        "publish-live-cohort",
                        "--observation-rdp",
                        str(observation_rdp),
                        "--ops-store",
                        str(ops),
                        "--schedule-sha256",
                        digest,
                        "--activation-id",
                        ACTIVATION,
                        "--data-root",
                        str(data_root),
                        "--as-of",
                        "2026-09-10T16:58:00Z",
                        "--release-builder-git-sha",
                        PRODUCER_B,
                        "--discovery-coverage-class",
                        "GAP_SUSPECTED",
                    ]
                )
            self.assertEqual(code, 0, buf.getvalue())
            envelope = json.loads(buf.getvalue())
            self.assertEqual(envelope["status"], "PASS")
            published = envelope["result"]
            self.assertEqual(published["terminal"], "LIVE_COHORT_PUBLISHED_TO_FORGE")
            sealed = Path(published["sealed_release_root"])
            self.assertEqual(sealed, default_sealed_release_root(observation_rdp, COHORT1))
            self.assertTrue((sealed / "release_manifest.json").is_file())
            self.assertTrue((sealed / "census.parquet").is_file())
            self.assertEqual(published["next"], CONTROL_NEXT)
            self.assertEqual(
                published["readiness"]["state"],
                "READY_VALID_WITH_COVERAGE_LIMITATION",
            )
            self.assertEqual(
                published["readiness"]["discovery_coverage_class"],
                "GAP_SUSPECTED",
            )
            self.assertTrue(published["forge"]["control_run_required_first"])
            self.assertFalse(published["forge"]["normalized_trajectory_executed"])
            self.assertEqual(published["forge"]["next"], CONTROL_NEXT)
            self.assertGreaterEqual(published["forge"]["yield_eligible"], 10)
            self.assertNotEqual(published["epoch_before"], published["epoch_after"])
            retry = publish_live_cohort(
                repo_root=ROOT,
                observation_rdp=observation_rdp,
                ops_store=ops,
                schedule_sha256=digest,
                activation_id=ACTIVATION,
                cohort_id=COHORT1,
                data_root=data_root,
                as_of=AS_OF_C1,
                discovery_coverage_class="GAP_SUSPECTED",
            )
            self.assertEqual(retry["import"]["status"], "IDEMPOTENT_REIMPORT")
            self.assertEqual(retry["epoch_after"], retry["epoch_before"])
            self.assertEqual(retry["sealed_release_root"], published["sealed_release_root"])
            self.assertTrue(Path(published["sealed_release_root"]).is_dir())
            conn = sqlite3.connect(ops)
            try:
                conn.execute(
                    "UPDATE due_observations SET state='OBSERVED' WHERE entity_id LIKE 'C%'"
                )
                conn.commit()
            finally:
                conn.close()
            second = publish_live_cohort(
                repo_root=ROOT,
                observation_rdp=observation_rdp,
                ops_store=ops,
                schedule_sha256=digest,
                activation_id=ACTIVATION,
                cohort_id=COHORT2,
                data_root=data_root,
                as_of=AS_OF_C2,
            )
            self.assertEqual(second["terminal"], "LIVE_COHORT_PUBLISHED_TO_FORGE")
            self.assertNotEqual(second["epoch_after"], published["epoch_after"])
            control = forge_control_ready(
                data_root=data_root,
                repo_root=ROOT,
                imported_cohort_id=COHORT1,
            )
            self.assertEqual(control["terminal"], "FORGE_CONTROL_READY")
            self.assertEqual(control["next"], CONTROL_NEXT)

    def test_transport_byte_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            other = Path(tmp) / "other"
            src.mkdir()
            other.mkdir()
            for name in ("release_manifest.json", "source_inventory.json"):
                (src / name).write_text("{}", encoding="utf-8")
                (other / name).write_text("{}", encoding="utf-8")
            (src / "census.parquet").write_bytes(b"abc")
            (src / "observations.parquet").write_bytes(b"def")
            (other / "census.parquet").write_bytes(b"xyz")
            (other / "observations.parquet").write_bytes(b"def")
            self.assertNotEqual(hash_release_tree(src), hash_release_tree(other))
            dest = Path(tmp) / "dest"
            dest.mkdir()
            import shutil as _shutil

            orig_copy = _shutil.copy2

            def _tamper(src_path: object, dest_path: object) -> object:
                result = orig_copy(src_path, dest_path)
                if Path(str(dest_path)).name == "census.parquet":
                    Path(dest_path).write_bytes(b"tampered")
                return result

            from unittest.mock import patch

            with self.assertRaises(DiscoveryReleaseError) as blocked:
                with patch(
                    "solana_alpha_lab.factory.live_cohort_to_forge.shutil.copy2",
                    _tamper,
                ):
                    verify_transported_release(source_root=src, dest_root=dest)
            self.assertEqual(str(blocked.exception), "TRANSPORT_HASH_MISMATCH")

    def test_cli_relative_path_and_typed_terminal(self) -> None:
        cli = _cli_module()
        with tempfile.TemporaryDirectory() as tmp:
            rel = Path(tmp) / "observation_rdp"
            rel.mkdir()
            from io import StringIO
            from contextlib import redirect_stdout

            buf = StringIO()
            with redirect_stdout(buf):
                code = cli.main(
                    [
                        "forge-control-ready",
                        "--data-root",
                        str(rel),
                    ]
                )
            self.assertEqual(code, 2)
            self.assertIn("CURRENT_CORPUS_MISSING", buf.getvalue())
            self.assertIn("IMPORT_VERIFIED_RELEASE_FIRST", buf.getvalue())
            buf2 = StringIO()
            with redirect_stdout(buf2):
                code2 = cli.main(
                    [
                        "publish-live-cohort",
                        "--observation-rdp",
                        str(rel),
                        "--ops-store",
                        str(Path(tmp) / "missing.sqlite"),
                        "--schedule-sha256",
                        "a" * 64,
                        "--activation-id",
                        ACTIVATION,
                        "--cohort-id",
                        COHORT1,
                        "--data-root",
                        str(rel),
                    ]
                )
            self.assertEqual(code2, 2)
            self.assertIn("CLOSED_RECEIPT_STORE_MISSING", buf2.getvalue())
            self.assertIn("STOP_MISSING_CLOSURE_EVIDENCE", buf2.getvalue())
            buf3 = StringIO()
            with redirect_stdout(buf3):
                code3 = cli.main(
                    [
                        "build-live-source",
                        "--observation-rdp",
                        str(rel),
                        "--ops-store",
                        str(Path(tmp) / "missing.sqlite"),
                        "--schedule-sha256",
                        "a" * 64,
                        "--activation-id",
                        ACTIVATION,
                        "--cohort-id",
                        COHORT1,
                    ]
                )
            self.assertEqual(code3, 2)
            self.assertIn("CLOSED_RECEIPT_STORE_MISSING", buf3.getvalue())

    def test_low_yield_before_import_with_empty_corpus(self) -> None:
        schedule = _schedule(ROOT)
        digest = schedule["schedule_sha256"]
        c1 = [_entity("A", i) for i in range(3)]
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            observation_rdp = base / "observation_rdp"
            data_root = base / "data_plane"
            ops = base / "ops.sqlite"
            observation_rdp.mkdir()
            data_root.mkdir()
            persist_observation_schedule(
                data_root=observation_rdp,
                schedule=schedule,
                now=C1_ADMIT,
                producer_git_sha=PRODUCER_A,
                activation_id=None,
            )
            publish_observation_batch(
                data_root=observation_rdp,
                root=ROOT,
                schedule=schedule,
                activation_id=ACTIVATION,
                now=PUBLISH_C1,
                producer_git_sha=PRODUCER_A,
                members=[_member(digest, entity, C1_ADMIT) for entity in c1],
                observations=[_obs(digest, entity, C1_ADMIT) for entity in c1],
            )
            _seed_ops(ops, digest=digest, cohort1=c1, cohort2=[])
            with self.assertRaises(LiveCohortToForgeError) as blocked:
                publish_live_cohort(
                    repo_root=ROOT,
                    observation_rdp=observation_rdp,
                    ops_store=ops,
                    schedule_sha256=digest,
                    activation_id=ACTIVATION,
                    cohort_id=COHORT1,
                    data_root=data_root,
                    as_of=AS_OF_C1,
                )
            self.assertEqual(str(blocked.exception), "LOW_YIELD")
            self.assertFalse((data_root / "datasets" / "live_lifecycle_corpus").exists())

    def test_cohort_id_for_admission_matches_production_windows(self) -> None:
        self.assertEqual(
            cohort_id_for_admission(
                C1_ADMIT,
                starts_at=datetime(2026, 9, 2, 11, 19, tzinfo=UTC),
                stops_admitting_at=datetime(2026, 9, 23, 11, 19, tzinfo=UTC),
            ),
            COHORT1,
        )
        self.assertEqual(
            cohort_id_for_admission(
                C2_ADMIT,
                starts_at=datetime(2026, 9, 2, 11, 19, tzinfo=UTC),
                stops_admitting_at=datetime(2026, 9, 23, 11, 19, tzinfo=UTC),
            ),
            COHORT2,
        )


if __name__ == "__main__":
    unittest.main()
