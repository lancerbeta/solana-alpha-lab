"""LIVE_EVIDENCE_CONSUMER_TRUTH_CLOSURE_V1 — real RDP adapter + cumulative corpus."""

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

from solana_alpha_lab.factory.hfic_preflight import (  # noqa: E402
    enumerate_rdp_datasets,
    evidence_epoch_material,
)
from solana_alpha_lab.factory.hfic_session import evidence_epoch_sha256  # noqa: E402
from solana_alpha_lab.factory.live_cohort_discovery_release import (  # noqa: E402
    COHORT_ADMISSION_FIELD,
    CORPUS_DATASET_ID,
    LiveCohortReleaseError,
    build_live_observation_source_from_rdp,
    campaign_cohort_windows,
    cohort_id_for_admission,
    current_corpus_partition_rows,
    import_live_cohort,
    load_observation_rdp_source,
    seal_live_cohort,
    select_current_datasets_for_forge,
    verify_live_cohort,
    write_observation_rdp_source,
)
from solana_alpha_lab.factory.observation_panel_publisher import (  # noqa: E402
    persist_observation_schedule,
    publish_observation_batch,
)
from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    load_observation_schedule,
)
from solana_alpha_lab.factory.research_store import ResearchStore  # noqa: E402

PRODUCER = "669745ec8de59c6db4aa04418af845253872bfde"
ACTIVATION = "ACT-619AE64E885E995E"
C4_STARTS = datetime(2026, 9, 2, 11, 19, 0, tzinfo=UTC)
C4_STOPS = datetime(2026, 9, 23, 11, 19, 0, tzinfo=UTC)
NOW = datetime(2026, 9, 2, 11, 31, 18, tzinfo=UTC)


def _c4_style_schedule(root: Path) -> dict:
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
    from solana_alpha_lab.factory.observation_schedule import (
        schedule_sha256,
        validate_observation_schedule,
    )

    validated = validate_observation_schedule(schedule, root=root)
    digest = schedule_sha256(validated)
    validated["schedule_sha256"] = digest
    return validated


class LiveEvidenceConsumerTruthClosureTests(unittest.TestCase):
    def test_c4_campaign_relative_cohort_windows(self) -> None:
        windows = campaign_cohort_windows(C4_STARTS, C4_STOPS)
        self.assertEqual(len(windows), 3)
        self.assertEqual(
            [w[0] for w in windows],
            [
                "REL-20260902T111900Z-20260909T111900Z",
                "REL-20260909T111900Z-20260916T111900Z",
                "REL-20260916T111900Z-20260923T111900Z",
            ],
        )
        self.assertIsNone(
            cohort_id_for_admission(
                C4_STARTS - timedelta(seconds=1),
                starts_at=C4_STARTS,
                stops_admitting_at=C4_STOPS,
            )
        )
        self.assertEqual(
            cohort_id_for_admission(
                C4_STARTS,
                starts_at=C4_STARTS,
                stops_admitting_at=C4_STOPS,
            ),
            "REL-20260902T111900Z-20260909T111900Z",
        )
        self.assertEqual(
            cohort_id_for_admission(
                C4_STARTS + timedelta(days=7) - timedelta(microseconds=1),
                starts_at=C4_STARTS,
                stops_admitting_at=C4_STOPS,
            ),
            "REL-20260902T111900Z-20260909T111900Z",
        )
        self.assertEqual(
            cohort_id_for_admission(
                C4_STARTS + timedelta(days=7),
                starts_at=C4_STARTS,
                stops_admitting_at=C4_STOPS,
            ),
            "REL-20260909T111900Z-20260916T111900Z",
        )
        self.assertEqual(
            cohort_id_for_admission(
                C4_STARTS + timedelta(days=14),
                starts_at=C4_STARTS,
                stops_admitting_at=C4_STOPS,
            ),
            "REL-20260916T111900Z-20260923T111900Z",
        )
        self.assertIsNone(
            cohort_id_for_admission(
                C4_STOPS,
                starts_at=C4_STARTS,
                stops_admitting_at=C4_STOPS,
            )
        )
        # No unix-epoch partial bucket spanning 2026-08-27…2026-09-02.
        for cid, _a, _b in windows:
            self.assertFalse(cid.startswith("UTC-20260827"))

    def test_real_rdp_publish_rebuild_live_source_vertical(self) -> None:
        schedule = _c4_style_schedule(ROOT)
        digest = schedule["schedule_sha256"]
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "observation_rdp"
            data_root.mkdir()
            persist_observation_schedule(
                data_root=data_root,
                schedule=schedule,
                now=NOW,
                producer_git_sha=PRODUCER,
                activation_id=ACTIVATION,
            )
            publish_observation_batch(
                data_root=data_root,
                root=ROOT,
                schedule=schedule,
                activation_id=ACTIVATION,
                now=NOW,
                producer_git_sha=PRODUCER,
                members=[
                    {
                        "schedule_sha256": digest,
                        "activation_id": ACTIVATION,
                        "entity_id": "EyGHwfTbPyfw9o7Kxic7pZdAmNScjXchnV5kzHmtpump",
                        "membership_state": "ADMITTED",
                        "candidate_state": "ADMITTED",
                        "authoritative_anchor": "2026-09-02T11:25:54Z",
                        "inclusion_probability": "0.0425",
                        "sampling_seed": "ALWAYS-ON-LIFECYCLE-COLLECTOR-V1",
                        "first_reliable_available_at": "2026-09-02T11:27:15.090924Z",
                        "request_sha256": "a" * 64,
                        "response_sha256": "b" * 64,
                    },
                    {
                        "schedule_sha256": digest,
                        "activation_id": ACTIVATION,
                        "entity_id": "HashExcludedMint111111111111111111111111111",
                        "membership_state": "PREDICATE_REJECTED",
                        "candidate_state": "NOT_SELECTED_HASH_SAMPLE",
                        "authoritative_anchor": "2026-09-02T11:26:00Z",
                        "inclusion_probability": "0.0425",
                        "sampling_seed": "ALWAYS-ON-LIFECYCLE-COLLECTOR-V1",
                        "first_reliable_available_at": "2026-09-02T11:27:15.090924Z",
                    },
                ],
                observations=[
                    {
                        "schedule_sha256": digest,
                        "activation_id": ACTIVATION,
                        "entity_id": "EyGHwfTbPyfw9o7Kxic7pZdAmNScjXchnV5kzHmtpump",
                        "point_id": "X300",
                        "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                        "state": "OBSERVED",
                        "event_time": "2026-09-02T11:25:54Z",
                        "first_reliable_available_at": "2026-09-02T11:31:18.240168Z",
                        "request_started_at": "2026-09-02T11:31:18.083900Z",
                        "response_received_at": "2026-09-02T11:31:18.240040Z",
                        "request_sha256": "c" * 64,
                        "response_sha256": "d" * 64,
                        "call_occurrence_id": "e" * 64,
                        "http_status": 200,
                        "http_class": "HTTP_OK",
                        "missing_reason": "X_POPULATION_PREDICATE_FAIL_CLOSED",
                        "field_values": [
                            {
                                "field_id": "FIELD-LIQUIDITY-USD-001",
                                "value_kind": "DECIMAL",
                                "typed_value_or_null": None,
                                "state": "MISSING_TYPED",
                                "missing_reason": "X_POPULATION_PREDICATE_FAIL_CLOSED",
                                "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                                "point_id": "X300",
                                "event_time": "2026-09-02T11:25:54Z",
                                "first_reliable_available_at": "2026-09-02T11:31:18.240168Z",
                                "request_sha256": "c" * 64,
                                "call_occurrence_id": "e" * 64,
                            }
                        ],
                    }
                ],
            )
            for path in data_root.glob("**/*.sqlite"):
                path.unlink()

            source = build_live_observation_source_from_rdp(
                observation_rdp_root=data_root,
                schedule_sha256=digest,
                activation_id=ACTIVATION,
            )
            self.assertEqual(source["activation_id"], ACTIVATION)
            self.assertEqual(source["producer_git_sha"], PRODUCER)
            self.assertEqual(source["starts_at"], "2026-09-02T11:19:00Z")
            self.assertEqual(source["stops_admitting_at"], "2026-09-23T11:19:00Z")
            mints = {m["mint"] for m in source["members"]}
            self.assertIn("EyGHwfTbPyfw9o7Kxic7pZdAmNScjXchnV5kzHmtpump", mints)
            admitted = next(
                m
                for m in source["members"]
                if m["mint"] == "EyGHwfTbPyfw9o7Kxic7pZdAmNScjXchnV5kzHmtpump"
            )
            self.assertEqual(
                admitted[COHORT_ADMISSION_FIELD], "2026-09-02T11:27:15.090924Z"
            )
            self.assertEqual(admitted["authoritative_anchor"], "2026-09-02T11:25:54Z")
            self.assertEqual(admitted["inclusion_probability"], "0.0425")
            self.assertEqual(admitted["sampling_seed"], "ALWAYS-ON-LIFECYCLE-COLLECTOR-V1")
            self.assertEqual(admitted["sampling_policy"], "DETERMINISTIC_HASH_BERNOULLI")
            self.assertEqual(admitted["selected_or_excluded"], "SELECTED")
            excluded = next(
                m
                for m in source["members"]
                if m["mint"].startswith("HashExcluded")
            )
            self.assertEqual(excluded["selected_or_excluded"], "EXCLUDED")
            self.assertEqual(excluded["denominator_state"], "hash_not_selected")
            self.assertNotEqual(excluded["selected_or_excluded"], "SELECTED")

            field_rows = [
                o
                for o in source["observations"]
                if o["point_id"] == "X300" and o["field_id"] == "FIELD-LIQUIDITY-USD-001"
            ]
            self.assertEqual(len(field_rows), 1)
            field = field_rows[0]
            self.assertIsNone(field["typed_value"])
            self.assertEqual(field["missing_reason"], "X_POPULATION_PREDICATE_FAIL_CLOSED")
            self.assertEqual(field["request_sha256"], "c" * 64)
            self.assertEqual(field["response_sha256"], "d" * 64)
            self.assertEqual(field["call_occurrence_id"], "e" * 64)
            self.assertEqual(field["http_status"], 200)
            self.assertEqual(field["http_class"], "HTTP_OK")

            again = build_live_observation_source_from_rdp(
                observation_rdp_root=data_root,
                schedule_sha256=digest,
                activation_id=ACTIVATION,
            )
            self.assertEqual(again["source_sha256"], source["source_sha256"])
            loaded = load_observation_rdp_source(data_root)
            self.assertEqual(loaded["source_sha256"], source["source_sha256"])
            self.assertFalse((data_root / "observation_schedule_state.sqlite").exists())

            cohort = cohort_id_for_admission(
                datetime(2026, 9, 2, 11, 27, 15, tzinfo=UTC),
                starts_at=C4_STARTS,
                stops_admitting_at=C4_STOPS,
            )
            assert cohort is not None
            # Not sealable yet (still collecting / maturing) — but status consumes source.
            from solana_alpha_lab.factory.live_cohort_discovery_release import (
                live_cohort_status,
            )

            status = live_cohort_status(
                observation_rdp_root=data_root,
                cohort_id=cohort,
                as_of=datetime(2026, 9, 2, 12, 0, tzinfo=UTC),
            )
            self.assertEqual(status["schedule_sha256"], digest)
            self.assertEqual(status["readiness"]["state"], "COLLECTING")

    def test_predicate_exclude_not_discovered_and_missing_reason_key(self) -> None:
        from solana_alpha_lab.factory.live_cohort_discovery_release import (
            _explode_observation_rows,
            _normalize_member_row,
        )

        member = _normalize_member_row(
            {
                "schedule_sha256": "a" * 64,
                "activation_id": ACTIVATION,
                "entity_id": "PredMint",
                "candidate_state": "NOT_SELECTED_PREDICATE",
                "membership_state": "PREDICATE_REJECTED",
                "first_reliable_available_at": "2026-09-02T12:00:00Z",
                "inclusion_probability": "",
            },
            schedule_sha256="a" * 64,
            activation_id=ACTIVATION,
            sampling_policy="DETERMINISTIC_HASH_BERNOULLI",
            sampling_seed_default="seed",
            inclusion_probability_default="0.0425",
        )
        assert member is not None
        self.assertEqual(member["selected_or_excluded"], "EXCLUDED")
        self.assertEqual(member["denominator_state"], "unknown")
        self.assertEqual(member["inclusion_probability"], "0.0425")

        rows = _explode_observation_rows(
            {
                "schedule_sha256": "a" * 64,
                "activation_id": ACTIVATION,
                "entity_id": "PredMint",
                "point_id": "X300",
                "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                "state": "OBSERVED",
                "missing_reason": "PARENT_REASON",
                "field_values": [
                    {
                        "field_id": "FIELD-LIQUIDITY-USD-001",
                        "value_kind": "DECIMAL",
                        "typed_value_or_null": "1.0",
                        "state": "OBSERVED",
                        "missing_reason": None,
                        "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                        "point_id": "X300",
                        "event_time": "2026-09-02T12:00:00Z",
                        "first_reliable_available_at": "2026-09-02T12:00:00Z",
                        "request_sha256": "c" * 64,
                        "call_occurrence_id": "e" * 64,
                    }
                ],
            },
            schedule_sha256="a" * 64,
            activation_id=ACTIVATION,
        )
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["missing_reason"])
        self.assertEqual(rows[0]["typed_value"], "1.0")

    def test_misaligned_cohort_id_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_observation_rdp_source(
                root,
                {
                    "schedule_sha256": "a" * 64,
                    "activation_id": ACTIVATION,
                    "producer_git_sha": PRODUCER,
                    "starts_at": "2026-09-02T11:19:00Z",
                    "stops_admitting_at": "2026-09-23T11:19:00Z",
                    "discovery_coverage_class": "EMPIRICAL_OVERLAP_ONLY",
                    "open_publication": False,
                    "unresolved_due": False,
                    "in_flight": False,
                    "budget_blocked": False,
                    "members": [
                        {
                            "mint": "M1",
                            COHORT_ADMISSION_FIELD: "2026-09-02T12:00:00Z",
                            "authoritative_anchor": "2026-09-02T12:00:00Z",
                            "candidate_state": "ADMITTED",
                            "membership_state": "OBSERVED",
                            "denominator_state": "observed",
                            "sampling_policy": "DETERMINISTIC_HASH_BERNOULLI",
                            "sampling_seed": "seed",
                            "inclusion_probability": "0.0425",
                            "selected_or_excluded": "SELECTED",
                            "exclusion_reason": None,
                        }
                    ]
                    * 3,
                    "observations": [],
                },
            )
            with self.assertRaises(LiveCohortReleaseError):
                seal_live_cohort(
                    observation_rdp_root=root,
                    cohort_id="REL-20260827T000000Z-20260902T000000Z",
                    release_root=root / "rel",
                    sealed_at=datetime(2026, 9, 20, tzinfo=UTC),
                    as_of=datetime(2026, 9, 20, tzinfo=UTC),
                )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snap = {
                "schedule_sha256": "a" * 64,
                "activation_id": ACTIVATION,
                "producer_git_sha": PRODUCER,
                "starts_at": "2026-09-02T11:19:00Z",
                "stops_admitting_at": "2026-09-23T11:19:00Z",
                "discovery_coverage_class": "EMPIRICAL_OVERLAP_ONLY",
                "open_publication": False,
                "unresolved_due": False,
                "in_flight": False,
                "budget_blocked": False,
                "members": [
                    {
                        "mint": "UnknownMint",
                        COHORT_ADMISSION_FIELD: "2026-09-02T12:00:00Z",
                        "authoritative_anchor": "2026-09-02T12:00:00Z",
                        "candidate_state": "WEIRD_NEW_STATE",
                        "membership_state": "WEIRD_NEW_STATE",
                        "denominator_state": "unknown",
                        "sampling_policy": "DETERMINISTIC_HASH_BERNOULLI",
                        "sampling_seed": "seed",
                        "inclusion_probability": "0.0425",
                        "selected_or_excluded": "UNKNOWN",
                        "exclusion_reason": None,
                    },
                    {
                        "mint": "ObservedMintA",
                        COHORT_ADMISSION_FIELD: "2026-09-02T12:01:00Z",
                        "authoritative_anchor": "2026-09-02T12:01:00Z",
                        "candidate_state": "ADMITTED",
                        "membership_state": "OBSERVED",
                        "denominator_state": "observed",
                        "sampling_policy": "DETERMINISTIC_HASH_BERNOULLI",
                        "sampling_seed": "seed",
                        "inclusion_probability": "0.0425",
                        "selected_or_excluded": "SELECTED",
                        "exclusion_reason": None,
                    },
                    {
                        "mint": "ObservedMintB",
                        COHORT_ADMISSION_FIELD: "2026-09-02T12:02:00Z",
                        "authoritative_anchor": "2026-09-02T12:02:00Z",
                        "candidate_state": "ADMITTED",
                        "membership_state": "OBSERVED",
                        "denominator_state": "observed",
                        "sampling_policy": "DETERMINISTIC_HASH_BERNOULLI",
                        "sampling_seed": "seed",
                        "inclusion_probability": "0.0425",
                        "selected_or_excluded": "SELECTED",
                        "exclusion_reason": None,
                    },
                ],
                "observations": [],
            }
            write_observation_rdp_source(root, snap)
            source = load_observation_rdp_source(root)
            self.assertEqual(source["members"][0]["selected_or_excluded"], "UNKNOWN")
            cohort = "REL-20260902T111900Z-20260909T111900Z"
            sealed = seal_live_cohort(
                observation_rdp_root=root,
                cohort_id=cohort,
                release_root=root / "release",
                sealed_at=datetime(2026, 9, 20, tzinfo=UTC),
                as_of=datetime(2026, 9, 20, tzinfo=UTC),
            )
            self.assertGreaterEqual(sealed["census_row_count"], 3)

    def test_cumulative_corpus_rows_not_latest_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            data_root = base / "rdp"
            data_root.mkdir()
            starts = datetime(2026, 9, 2, 11, 19, 0, tzinfo=UTC)
            stops = starts + timedelta(days=21)
            epochs: list[str] = []
            for week, mint in enumerate(["MintC1", "MintC2", "MintC3"]):
                admission = starts + timedelta(days=7 * week, hours=1)
                snap = {
                    "schedule_sha256": "a" * 64,
                    "activation_id": ACTIVATION,
                    "producer_git_sha": PRODUCER,
                    "starts_at": starts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "stops_admitting_at": stops.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "discovery_coverage_class": "EMPIRICAL_OVERLAP_ONLY",
                    "open_publication": False,
                    "unresolved_due": False,
                    "in_flight": False,
                    "budget_blocked": False,
                    "members": [
                        {
                            "mint": f"{mint}{suffix}",
                            COHORT_ADMISSION_FIELD: admission.strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "authoritative_anchor": admission.strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "candidate_state": "ADMITTED",
                            "membership_state": "OBSERVED",
                            "denominator_state": "observed",
                            "sampling_policy": "DETERMINISTIC_HASH_BERNOULLI",
                            "sampling_seed": "seed",
                            "inclusion_probability": "0.0425",
                            "selected_or_excluded": "SELECTED",
                            "exclusion_reason": None,
                            "source_request_sha256": "c" * 64,
                            "source_response_sha256": "d" * 64,
                        }
                        for suffix in ("A", "B", "C")
                    ],
                    "observations": [
                        {
                            "mint": f"{mint}A",
                            "point_id": "X300",
                            "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                            "field_id": "FIELD-USD-PRICE-001",
                            "value_kind": "DECIMAL",
                            "typed_value": "1.0",
                            "state": "OBSERVED",
                            "missing_reason": None,
                            "event_time": admission.strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "request_started_at": admission.strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "response_received_at": admission.strftime(
                                "%Y-%m-%dT%H:%M:%SZ"
                            ),
                            "first_reliable_available_at": admission.strftime(
                                "%Y-%m-%dT%H:%M:%SZ"
                            ),
                            "request_sha256": "e" * 64,
                            "response_sha256": "f" * 64,
                            "call_occurrence_id": "1" * 64,
                            "http_status": 200,
                            "http_class": "OK",
                        }
                    ],
                }
                obs_rdp = base / f"obs_{week}"
                release = base / f"rel_{week}"
                write_observation_rdp_source(obs_rdp, snap)
                cohort = cohort_id_for_admission(
                    admission, starts_at=starts, stops_admitting_at=stops
                )
                assert cohort is not None
                as_of = admission + timedelta(days=10)
                seal_live_cohort(
                    observation_rdp_root=obs_rdp,
                    cohort_id=cohort,
                    release_root=release,
                    sealed_at=as_of,
                    as_of=as_of,
                )
                verify_live_cohort(release)
                imported = import_live_cohort(
                    release_root=release,
                    data_root=data_root,
                    import_time=as_of + timedelta(hours=1),
                )
                self.assertTrue(imported["epoch_bump"])
                epochs.append(
                    evidence_epoch_sha256(evidence_epoch_material(ROOT, data_root))
                )

            self.assertEqual(len(set(epochs)), 3)
            rows = current_corpus_partition_rows(data_root, kind="census")
            mints = {r["mint"] for r in rows}
            self.assertIn("MintC1A", mints)
            self.assertIn("MintC2A", mints)
            self.assertIn("MintC3A", mints)
            self.assertEqual(len(rows), 9)

            enumerated, _ = enumerate_rdp_datasets(data_root)
            current = select_current_datasets_for_forge(enumerated)
            current_corpus = [
                e
                for e in current
                if e.get("dataset_id") == CORPUS_DATASET_ID
                or (e.get("labels") or {}).get("logical_dataset_id") == CORPUS_DATASET_ID
            ]
            self.assertEqual(len(current_corpus), 1)
            labels = current_corpus[0].get("labels") or {}
            self.assertEqual(len(labels.get("cohort_lineage") or []), 3)
            self.assertTrue(labels.get("cumulative_composition"))
            self.assertEqual(labels.get("census_row_count_cumulative"), 9)

            # Source rebuild on a side RDP does not bump the corpus Forge epoch.
            side_schedule = _c4_style_schedule(ROOT)
            side_digest = side_schedule["schedule_sha256"]
            side = base / "side_obs"
            side.mkdir()
            persist_observation_schedule(
                data_root=side,
                schedule=side_schedule,
                now=NOW,
                producer_git_sha=PRODUCER,
                activation_id=ACTIVATION,
            )
            publish_observation_batch(
                data_root=side,
                root=ROOT,
                schedule=side_schedule,
                activation_id=ACTIVATION,
                now=NOW,
                producer_git_sha=PRODUCER,
                members=[
                    {
                        "schedule_sha256": side_digest,
                        "activation_id": ACTIVATION,
                        "entity_id": "MintSideRebuildOnly1111111111111111111111",
                        "membership_state": "ADMITTED",
                        "candidate_state": "ADMITTED",
                        "authoritative_anchor": "2026-09-02T11:25:54Z",
                        "inclusion_probability": "0.0425",
                        "sampling_seed": "ALWAYS-ON-LIFECYCLE-COLLECTOR-V1",
                        "first_reliable_available_at": "2026-09-02T11:27:15.090924Z",
                        "request_sha256": "a" * 64,
                        "response_sha256": "b" * 64,
                    }
                ],
                observations=[],
            )
            build_live_observation_source_from_rdp(
                observation_rdp_root=side,
                schedule_sha256=side_digest,
                activation_id=ACTIVATION,
            )
            rebuild_epoch = evidence_epoch_sha256(
                evidence_epoch_material(ROOT, data_root)
            )
            self.assertEqual(rebuild_epoch, epochs[-1])

            # Idempotent reimport
            re = import_live_cohort(
                release_root=base / "rel_2",
                data_root=data_root,
                import_time=datetime(2026, 10, 1, tzinfo=UTC),
            )
            self.assertEqual(re["status"], "IDEMPOTENT_REIMPORT")
            self.assertFalse(re["epoch_bump"])

    def test_activation_scoped_producer_ignores_foreign_activation(self) -> None:
        schedule = _c4_style_schedule(ROOT)
        digest = schedule["schedule_sha256"]
        other_act = "ACT-OTHER-ACTIVATION-001"
        other_producer = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "observation_rdp"
            data_root.mkdir()
            persist_observation_schedule(
                data_root=data_root,
                schedule=schedule,
                now=NOW,
                producer_git_sha=PRODUCER,
                activation_id=ACTIVATION,
            )
            publish_observation_batch(
                data_root=data_root,
                root=ROOT,
                schedule=schedule,
                activation_id=ACTIVATION,
                now=NOW,
                producer_git_sha=PRODUCER,
                members=[
                    {
                        "schedule_sha256": digest,
                        "activation_id": ACTIVATION,
                        "entity_id": "MintScopedProducerAAAA111111111111111111111",
                        "membership_state": "ADMITTED",
                        "candidate_state": "ADMITTED",
                        "authoritative_anchor": "2026-09-02T11:25:54Z",
                        "inclusion_probability": "0.0425",
                        "sampling_seed": "ALWAYS-ON-LIFECYCLE-COLLECTOR-V1",
                        "first_reliable_available_at": "2026-09-02T11:27:15.090924Z",
                        "request_sha256": "a" * 64,
                        "response_sha256": "b" * 64,
                    }
                ],
                observations=[],
            )
            # Foreign activation batch on same schedule digest must not mix producers.
            publish_observation_batch(
                data_root=data_root,
                root=ROOT,
                schedule=schedule,
                activation_id=other_act,
                now=NOW + timedelta(minutes=1),
                producer_git_sha=other_producer,
                members=[
                    {
                        "schedule_sha256": digest,
                        "activation_id": other_act,
                        "entity_id": "MintForeignActivationBBBB222222222222222222",
                        "membership_state": "ADMITTED",
                        "candidate_state": "ADMITTED",
                        "authoritative_anchor": "2026-09-02T11:26:54Z",
                        "inclusion_probability": "0.0425",
                        "sampling_seed": "ALWAYS-ON-LIFECYCLE-COLLECTOR-V1",
                        "first_reliable_available_at": "2026-09-02T11:28:15.090924Z",
                        "request_sha256": "1" * 64,
                        "response_sha256": "2" * 64,
                    }
                ],
                observations=[],
            )
            for path in data_root.glob("**/*.sqlite"):
                path.unlink()
            source = build_live_observation_source_from_rdp(
                observation_rdp_root=data_root,
                schedule_sha256=digest,
                activation_id=ACTIVATION,
            )
            self.assertEqual(source["producer_git_sha"], PRODUCER)
            mints = {m["mint"] for m in source["members"]}
            self.assertIn("MintScopedProducerAAAA111111111111111111111", mints)
            # Foreign activation members stay out of this activation's source.
            self.assertNotIn("MintForeignActivationBBBB222222222222222222", mints)


if __name__ == "__main__":
    unittest.main()
