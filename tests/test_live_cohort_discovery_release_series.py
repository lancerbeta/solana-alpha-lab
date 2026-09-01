"""Zero-network live cohort → versioned LIVE CORPUS → HFIC current-version proof."""

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
    build_forge_context_packet,
    enumerate_rdp_datasets,
    evidence_epoch_material,
)
from solana_alpha_lab.factory.hfic_session import evidence_epoch_sha256  # noqa: E402
from solana_alpha_lab.factory.live_cohort_discovery_release import (  # noqa: E402
    COHORT_ADMISSION_FIELD,
    CORPUS_DATASET_ID,
    LIVE_EVIDENCE_ROLE,
    LiveCohortReleaseError,
    classify_cohort_readiness,
    cohort_id_for_admission,
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
        "candidate_state": "CANDIDATE",
        "membership_state": "INCLUDED",
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
    # Week 0 starts 2026-01-01 (Thursday) → cohort UTC-20251228-20260103 contains it?
    # Use explicit admissions inside known 7-day buckets.
    base = datetime(2026, 1, 5, 12, 0, 0, tzinfo=UTC) + timedelta(days=7 * week_index)
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
    def test_cohort_id_non_overlapping_7_utc_days(self) -> None:
        a = cohort_id_for_admission(datetime(2026, 1, 5, tzinfo=UTC))
        b = cohort_id_for_admission(datetime(2026, 1, 7, tzinfo=UTC))
        c = cohort_id_for_admission(datetime(2026, 1, 8, tzinfo=UTC))
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertEqual(a, "UTC-20260101-20260107")
        self.assertEqual(c, "UTC-20260108-20260114")

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
            cohort = cohort_id_for_admission(datetime(2026, 1, 5, tzinfo=UTC))
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
            cohort = cohort_id_for_admission(datetime(2026, 1, 5, tzinfo=UTC))
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
            for week in range(12):
                obs_rdp = base / f"obs_{week}"
                release = base / f"rel_{week}"
                snap = _snapshot_for_week(week)
                write_observation_rdp_source(obs_rdp, snap)
                admission = datetime(2026, 1, 5, tzinfo=UTC) + timedelta(days=7 * week)
                cohort = cohort_id_for_admission(admission)
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

            # All 12 corpus version manifests remain on disk / enumerable.
            enumerated, _ = enumerate_rdp_datasets(data_root)
            corpus_entries = [
                e
                for e in enumerated
                if e.get("dataset_id") == CORPUS_DATASET_ID
                or (e.get("labels") or {}).get("logical_dataset_id") == CORPUS_DATASET_ID
            ]
            self.assertEqual(len(corpus_entries), 12)
            self.assertEqual(len(set(manifest_ids)), 12)

            # HFIC forge context sees one current corpus version, not 12.
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

            # Epoch changes once per new cohort.
            self.assertEqual(len(set(epochs)), 12)

            # Three non-overlapping 7-day cohorts coexist (weeks 0,1,2).
            self.assertEqual(len(set(manifest_ids[:3])), 3)

            # Confirmatory fence holds on current corpus.
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
            cohort = cohort_id_for_admission(datetime(2026, 1, 5, tzinfo=UTC))
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
