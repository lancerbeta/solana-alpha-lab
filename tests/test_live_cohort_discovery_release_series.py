"""Zero-network live cohort → versioned LIVE CORPUS → HFIC current-version proof."""

from __future__ import annotations

import json
import hashlib
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
    build_forge_context_packet,
    enumerate_rdp_datasets,
    evidence_epoch_material,
)
from solana_alpha_lab.factory.hfic_session import evidence_epoch_sha256  # noqa: E402
from solana_alpha_lab.factory.live_cohort_discovery_release import (  # noqa: E402
    COHORT_ADMISSION_FIELD,
    CORPUS_DATASET_ID,
    LIVE_EVIDENCE_ROLE,
    classify_cohort_readiness,
    cohort_id_for_admission,
    current_corpus_partition_rows,
    import_live_cohort,
    seal_live_cohort,
    select_current_datasets_for_forge,
    verify_live_cohort,
    write_observation_rdp_source,
)
from solana_alpha_lab.factory.research_store import ResearchStore  # noqa: E402
from solana_alpha_lab.factory.tokens_v2_typed_projection import (  # noqa: E402
    STATE_MISSING,
    STATE_OBSERVED,
)

SCHEDULE_SHA = "a" * 64
PRODUCER = "b70cf48508d0de84bfc5b1df311b41c04ea1d6ea"
ACTIVATION = "act-live-cohort-test-001"
CAMPAIGN_STARTS = datetime(2026, 1, 5, 12, 0, 0, tzinfo=UTC)
CAMPAIGN_STOPS = CAMPAIGN_STARTS + timedelta(days=84)


def _member(
    mint: str,
    admission: str,
    *,
    denom: str = "observed",
    selected: str = "SELECTED",
) -> dict:
    return {
        "mint": mint,
        COHORT_ADMISSION_FIELD: admission,
        "authoritative_anchor": admission,
        "candidate_state": "ADMITTED" if selected == "SELECTED" else "NOT_SELECTED_HASH_SAMPLE",
        "membership_state": "OBSERVED" if denom == "observed" else "ADMITTED",
        "denominator_state": denom,
        "sampling_policy": "HASH_SAMPLE",
        "sampling_seed": "seed-1",
        "inclusion_probability": "0.1",
        "selected_or_excluded": selected,
        "exclusion_reason": None if selected == "SELECTED" else "HASH_NOT_SELECTED",
        "source_request_sha256": "c" * 64,
        "source_response_sha256": "d" * 64,
    }


def _obs(mint: str, point_id: str, admission: str, *, missing: bool = False) -> dict:
    return {
        "mint": mint,
        "point_id": point_id,
        "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
        "field_id": "FIELD-USD-PRICE-001",
        "value_kind": "DECIMAL",
        "typed_value": None if missing else "1.23",
        "state": STATE_MISSING if missing else STATE_OBSERVED,
        "missing_reason": "PROVIDER_TIMEOUT" if missing else None,
        "event_time": admission,
        "request_started_at": admission,
        "response_received_at": admission,
        "first_reliable_available_at": admission,
        "request_sha256": "e" * 64,
        "response_sha256": "f" * 64,
        "call_occurrence_id": "1" * 64,
        "http_status": 504 if missing else 200,
        "http_class": "TIMEOUT" if missing else "OK",
    }


def _snapshot_for_week(
    week_index: int,
    *,
    coverage: str = "EMPIRICAL_OVERLAP_ONLY",
) -> dict:
    base = CAMPAIGN_STARTS + timedelta(days=7 * week_index)
    admission = base.strftime("%Y-%m-%dT%H:%M:%SZ")
    mints = [f"MintW{week_index}A", f"MintW{week_index}B", f"MintW{week_index}C"]
    members = [
        _member(mints[0], admission, denom="observed"),
        _member(mints[1], admission, denom="observed"),
        _member(mints[2], admission, denom="hash_not_selected", selected="EXCLUDED"),
        _member(f"MintW{week_index}X", admission, denom="x_ineligible", selected="EXCLUDED"),
        _member(f"MintW{week_index}M", admission, denom="typed_missing"),
    ]
    points = ["X300", "Y900", "Y1800", "Y3600"]
    observations = []
    for mint in mints[:2]:
        for point in points:
            observations.append(
                _obs(
                    mint,
                    point,
                    admission,
                    missing=(point == "Y3600" and mint.endswith("B")),
                )
            )
    observations.append(_obs(mints[0], "Y7200", admission, missing=True))
    return {
        "schedule_sha256": SCHEDULE_SHA,
        "activation_id": ACTIVATION,
        "producer_git_sha": PRODUCER,
        "starts_at": CAMPAIGN_STARTS.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stops_admitting_at": CAMPAIGN_STOPS.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "discovery_coverage_class": coverage,
        "open_publication": False,
        "unresolved_due": False,
        "in_flight": False,
        "budget_blocked": False,
        "as_of": (base + timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "members": members,
        "observations": observations,
    }


class LiveCohortDiscoveryReleaseSeriesTests(unittest.TestCase):
    def test_campaign_relative_7d_windows(self) -> None:
        a = cohort_id_for_admission(
            datetime(2026, 1, 5, 12, 0, 0, tzinfo=UTC),
            starts_at=CAMPAIGN_STARTS,
            stops_admitting_at=CAMPAIGN_STOPS,
        )
        b = cohort_id_for_admission(
            datetime(2026, 1, 12, 11, 59, 59, tzinfo=UTC),
            starts_at=CAMPAIGN_STARTS,
            stops_admitting_at=CAMPAIGN_STOPS,
        )
        c = cohort_id_for_admission(
            datetime(2026, 1, 12, 12, 0, 0, tzinfo=UTC),
            starts_at=CAMPAIGN_STARTS,
            stops_admitting_at=CAMPAIGN_STOPS,
        )
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertEqual(a, "REL-20260105T120000Z-20260112T120000Z")
        self.assertEqual(c, "REL-20260112T120000Z-20260119T120000Z")

    def test_blocked_states_not_sealable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snap = _snapshot_for_week(0)
            snap["unresolved_due"] = True
            write_observation_rdp_source(root, snap)
            from solana_alpha_lab.factory.live_cohort_discovery_release import (
                load_observation_rdp_source,
            )

            source = load_observation_rdp_source(root)
            cohort = cohort_id_for_admission(
                datetime(2026, 1, 5, 12, tzinfo=UTC),
                starts_at=CAMPAIGN_STARTS,
                stops_admitting_at=CAMPAIGN_STOPS,
            )
            assert cohort is not None
            ready = classify_cohort_readiness(
                source,
                cohort_id=cohort,
                as_of=datetime(2026, 1, 20, tzinfo=UTC),
            )
            self.assertEqual(ready["state"], "RELEASE_BLOCKED_UNRESOLVED_DUE")
            self.assertFalse(ready["sealable"])

    def test_vertical_rdp_to_corpus_to_hfic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            obs_rdp = base / "observation_rdp"
            release = base / "release"
            data_root = base / "rdp"
            data_root.mkdir()
            store = ResearchStore(data_root)

            snap = _snapshot_for_week(0, coverage="GAP_SUSPECTED")
            write_observation_rdp_source(obs_rdp, snap)
            cohort = cohort_id_for_admission(
                datetime(2026, 1, 5, 12, tzinfo=UTC),
                starts_at=CAMPAIGN_STARTS,
                stops_admitting_at=CAMPAIGN_STOPS,
            )
            assert cohort is not None
            as_of = datetime(2026, 1, 20, tzinfo=UTC)
            from solana_alpha_lab.factory.live_cohort_discovery_release import (
                load_observation_rdp_source,
            )

            ready = classify_cohort_readiness(
                load_observation_rdp_source(obs_rdp),
                cohort_id=cohort,
                as_of=as_of,
            )
            self.assertEqual(ready["state"], "READY_VALID_WITH_COVERAGE_LIMITATION")
            sealed = seal_live_cohort(
                observation_rdp_root=obs_rdp,
                cohort_id=cohort,
                release_root=release,
                sealed_at=as_of,
                as_of=as_of,
            )
            self.assertEqual(sealed["evidence_role"], LIVE_EVIDENCE_ROLE)
            self.assertTrue(sealed["confirmatory_reuse_forbidden"])
            verify_live_cohort(release)
            epoch_before = evidence_epoch_sha256(
                evidence_epoch_material(ROOT, data_root)
            )
            imported = import_live_cohort(
                release_root=release,
                data_root=data_root,
                import_time=as_of + timedelta(hours=1),
            )
            self.assertTrue(imported["epoch_bump"])
            self.assertEqual(imported["dataset_id"], CORPUS_DATASET_ID)
            epoch_after = evidence_epoch_sha256(
                evidence_epoch_material(ROOT, data_root)
            )
            self.assertNotEqual(epoch_before, epoch_after)
            reimport = import_live_cohort(
                release_root=release,
                data_root=data_root,
                import_time=as_of + timedelta(hours=2),
            )
            self.assertEqual(reimport["status"], "IDEMPOTENT_REIMPORT")
            self.assertFalse(reimport["epoch_bump"])
            epoch_re = evidence_epoch_sha256(evidence_epoch_material(ROOT, data_root))
            self.assertEqual(epoch_after, epoch_re)

            enumerated, _ = enumerate_rdp_datasets(data_root)
            self.assertGreaterEqual(len(enumerated), 1)
            packet, _digest = build_forge_context_packet(
                ROOT,
                data_root,
                owner_focus="AUTO",
                evidence_epoch=epoch_after,
                search_key="0" * 64,
                commissioning_status="NO_GIT_FAST_LANE_PROVEN",
                research_memory_as_of=as_of.strftime("%Y-%m-%dT%H:%M:%SZ"),
                store=store,
                stage_time=as_of + timedelta(hours=1),
            )
            self.assertIn(
                "current_version_per_dataset_id",
                packet["truncation_receipt"]["selection_policy"],
            )
            families = {f["feature_family"] for f in packet["feature_families"]}
            self.assertTrue(families)
            self.assertTrue(
                any(
                    item.get("confirmatory_reuse_forbidden")
                    for item in packet["feature_families"]
                )
            )
            live_entries = [
                e
                for e in enumerated
                if (e.get("labels") or {}).get("logical_dataset_id") == CORPUS_DATASET_ID
            ]
            self.assertTrue(live_entries)
            self.assertTrue(
                (live_entries[0].get("labels") or {}).get("confirmatory_reuse_forbidden")
            )

    def test_twelve_weekly_imports_no_context_explosion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            data_root = base / "rdp"
            data_root.mkdir()
            store = ResearchStore(data_root)
            epochs: list[str] = []
            manifest_ids: list[str] = []
            parquet_files_before = 0
            week0_parquet_sha: dict[str, str] = {}
            for week in range(12):
                obs_rdp = base / f"obs_{week}"
                release = base / f"rel_{week}"
                snap = _snapshot_for_week(week)
                write_observation_rdp_source(obs_rdp, snap)
                admission = CAMPAIGN_STARTS + timedelta(days=7 * week)
                cohort = cohort_id_for_admission(
                    admission,
                    starts_at=CAMPAIGN_STARTS,
                    stops_admitting_at=CAMPAIGN_STOPS,
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
                result = import_live_cohort(
                    release_root=release,
                    data_root=data_root,
                    import_time=as_of + timedelta(hours=1),
                )
                self.assertEqual(result["status"], "IMPORTED")
                self.assertEqual(result["corpus_version"], week + 1)
                manifest_ids.append(result["dataset_manifest_id"])
                epochs.append(
                    evidence_epoch_sha256(evidence_epoch_material(ROOT, data_root))
                )
                parquet_count = len(list((data_root / "datasets" / "partitions").rglob("*.parquet")))
                if week == 0:
                    parquet_files_before = parquet_count
                    for path in (data_root / "datasets" / "partitions").rglob("*.parquet"):
                        rel = path.relative_to(data_root).as_posix()
                        week0_parquet_sha[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
                else:
                    # Exactly two new parquet files per cohort (census+obs), no historical rewrite.
                    self.assertEqual(parquet_count, parquet_files_before + 2 * week)
                    for rel, digest in week0_parquet_sha.items():
                        live = data_root / rel
                        self.assertTrue(live.is_file(), rel)
                        self.assertEqual(
                            hashlib.sha256(live.read_bytes()).hexdigest(),
                            digest,
                            msg=f"week0 parquet mutated after week {week}: {rel}",
                        )

            enumerated, _ = enumerate_rdp_datasets(data_root)
            corpus_entries = [
                e
                for e in enumerated
                if e.get("dataset_id") == CORPUS_DATASET_ID
                or (e.get("labels") or {}).get("logical_dataset_id") == CORPUS_DATASET_ID
            ]
            self.assertEqual(len(corpus_entries), 12)
            self.assertEqual(len(set(manifest_ids)), 12)

            current = select_current_datasets_for_forge(enumerated)
            current_corpus = [
                e
                for e in current
                if e.get("dataset_id") == CORPUS_DATASET_ID
                or (e.get("labels") or {}).get("logical_dataset_id") == CORPUS_DATASET_ID
            ]
            self.assertEqual(len(current_corpus), 1)
            self.assertEqual(
                (current_corpus[0].get("labels") or {}).get("corpus_version"), 12
            )
            lineage = (current_corpus[0].get("labels") or {}).get("cohort_lineage")
            self.assertEqual(len(lineage), 12)

            census_rows = current_corpus_partition_rows(data_root, kind="census")
            mints = {row.get("mint") for row in census_rows}
            for week in range(12):
                self.assertIn(f"MintW{week}A", mints)
            self.assertEqual(
                len(census_rows),
                (current_corpus[0].get("labels") or {}).get("census_row_count_cumulative"),
            )

            packet, _ = build_forge_context_packet(
                ROOT,
                data_root,
                owner_focus="AUTO",
                evidence_epoch=epochs[-1],
                search_key="0" * 64,
                commissioning_status="NO_GIT_FAST_LANE_PROVEN",
                research_memory_as_of="2026-04-01T00:00:00Z",
                store=store,
                stage_time=datetime(2026, 4, 1, tzinfo=UTC),
            )
            corpus_in_packet = [
                mid
                for mid in packet["dataset_manifest_ids"]
                if mid in set(manifest_ids)
            ]
            self.assertEqual(len(corpus_in_packet), 1)
            self.assertLessEqual(len(packet["dataset_manifest_ids"]), 8)

            self.assertEqual(len(set(epochs)), 12)
            self.assertEqual(len(set(manifest_ids[:3])), 3)

            self.assertTrue(
                (current_corpus[0].get("labels") or {}).get(
                    "confirmatory_reuse_forbidden"
                )
            )
            self.assertEqual(
                (current_corpus[0].get("labels") or {}).get("evidence_role"),
                LIVE_EVIDENCE_ROLE,
            )

    def test_sqlite_not_required_for_readiness(self) -> None:
        """Immutable RDP snapshot alone is sufficient — no SQLite path."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_observation_rdp_source(root, _snapshot_for_week(0))
            self.assertFalse((root / "observation_schedule_state.sqlite").exists())
            cohort = cohort_id_for_admission(
                datetime(2026, 1, 5, 12, tzinfo=UTC),
                starts_at=CAMPAIGN_STARTS,
                stops_admitting_at=CAMPAIGN_STOPS,
            )
            assert cohort is not None
            from solana_alpha_lab.factory.live_cohort_discovery_release import (
                load_observation_rdp_source,
            )

            source = load_observation_rdp_source(root)
            ready = classify_cohort_readiness(
                source,
                cohort_id=cohort,
                as_of=datetime(2026, 1, 20, tzinfo=UTC),
            )
            self.assertTrue(ready["sealable"])

    def test_cannot_confirm_from_discovery_corpus(self) -> None:
        self.assertTrue(
            __import__(
                "solana_alpha_lab.factory.live_cohort_discovery_release",
                fromlist=["REQUIRED_LABELS"],
            ).REQUIRED_LABELS["confirmatory_reuse_forbidden"]
        )
        self.assertEqual(LIVE_EVIDENCE_ROLE, "EXPLORATORY_REUSE")
        self.assertNotEqual(LIVE_EVIDENCE_ROLE, "DISCOVERY_ONLY_SECOND_LOOK")


if __name__ == "__main__":
    unittest.main()
