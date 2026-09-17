"""TASK-06 LIVE CORPUS metadata repair proofs. Temporary fixtures only."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.contracts.schema_v1 import (  # noqa: E402
    DatasetManifest,
    PartitionManifest,
)
from solana_alpha_lab.factory.discovery_evidence_release import (  # noqa: E402
    DiscoveryReleaseError,
    _publish_bytes,
    _schema_sha256,
    sha256_bytes,
)
from solana_alpha_lab.factory.hfic_preflight import (  # noqa: E402
    enumerate_rdp_datasets,
    evidence_epoch_material,
)
from solana_alpha_lab.factory.hfic_session import evidence_epoch_sha256  # noqa: E402
from solana_alpha_lab.factory.live_cohort_discovery_release import (  # noqa: E402
    CORPUS_DATASET_ID,
    LIVE_EVIDENCE_ROLE,
    LiveCohortReleaseError,
    REQUIRED_LABELS,
    cohort_id_for_admission,
    import_live_cohort,
    repair_live_corpus_manifests,
    seal_live_cohort,
    select_current_datasets_for_forge,
    write_observation_rdp_source,
)
from solana_alpha_lab.factory.live_cohort_source_bundle import (  # noqa: E402
    CENSUS_RELEASE_SCHEMA,
    OBS_RELEASE_SCHEMA,
    RELEASE_PARQUET_WRITE_KWARGS,
    sha256_file_streaming,
    sha256_files_concat_streaming,
)
from solana_alpha_lab.factory.live_corpus_logical_rows import (  # noqa: E402
    CANONICAL_METADATA_SUFFIX,
    LOGICAL_ROW_PROFILE,
    hash_logical_rows,
    live_corpus_schema_sha256,
    measure_live_corpus_parquet,
    write_parquet_and_confirm_logical_hash,
)
from solana_alpha_lab.factory.live_corpus_manifest_publish import (  # noqa: E402
    LEGACY_CORPUS_REQUIRES_REPAIR,
)
from solana_alpha_lab.factory.run_passport import canonical_sha256  # noqa: E402
from solana_alpha_lab.storage.manifests import (  # noqa: E402
    compute_dataset_manifest_id,
    canonical_manifest_bytes,
    verify_dataset_manifest,
    verify_partition_manifest,
)
from tests.test_live_cohort_discovery_release_series import (  # noqa: E402
    CAMPAIGN_STARTS,
    CAMPAIGN_STOPS,
    _snapshot_for_week,
)

REAL_DATA_PLANE = ROOT / "local" / "factory_v1" / "data_plane"


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _real_corpus_fingerprint() -> str | None:
    lineage = REAL_DATA_PLANE / "datasets" / "live_lifecycle_corpus" / "lineage.json"
    if not REAL_DATA_PLANE.is_dir() or not lineage.is_file():
        return None
    parts = [lineage.read_bytes()]
    manifests = REAL_DATA_PLANE / "datasets" / "manifests"
    if manifests.is_dir():
        for path in sorted(manifests.rglob("*")):
            if path.is_file() and not path.is_symlink():
                parts.append(path.relative_to(REAL_DATA_PLANE).as_posix().encode())
                parts.append(path.read_bytes())
    return hashlib.sha256(b"\n".join(parts)).hexdigest()


def _legacy_rebind_id(dataset_manifest_id: str, partition_id: str) -> str:
    digest = hashlib.sha256(
        f"{dataset_manifest_id}:{partition_id}".encode("utf-8")
    ).hexdigest()
    return f"partition-{digest}"


def _parse_utc(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text).astimezone(UTC)


class _VisibilityFault(RuntimeError):
    pass


def _seal_week(base: Path, week: int) -> tuple[Path, dict[str, object], str]:
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
    sealed = seal_live_cohort(
        observation_rdp_root=obs_rdp,
        cohort_id=cohort,
        release_root=release,
        sealed_at=as_of,
        as_of=as_of,
    )
    return release, sealed, cohort


def _install_legacy_corpus(
    *,
    data_root: Path,
    release: Path,
    sealed: dict[str, object],
    imported_at: datetime,
) -> dict[str, str]:
    cohort_id = str(sealed["cohort_id"])
    release_id = str(sealed["release_id"])
    census_src = release / "census.parquet"
    obs_src = release / "observations.parquet"
    census_sha = sha256_file_streaming(census_src)
    obs_sha = sha256_file_streaming(obs_src)
    pair_sha = sha256_files_concat_streaming([census_src, obs_src])
    dataset_version = f"corpus-v1-{cohort_id}"
    dataset_manifest_id = compute_dataset_manifest_id(CORPUS_DATASET_ID, dataset_version)
    census_part_id = f"PARTITION-LIVE-COHORT-{cohort_id}-CENSUS"
    obs_part_id = f"PARTITION-LIVE-COHORT-{cohort_id}-OBS"
    date_key = imported_at.strftime("%Y-%m-%d")
    census_rel = (
        f"datasets/partitions/date={date_key}/{census_part_id}-{release_id[:16]}.parquet"
    )
    obs_rel = (
        f"datasets/partitions/date={date_key}/{obs_part_id}-{release_id[:16]}.parquet"
    )
    dest_census = data_root / census_rel
    dest_obs = data_root / obs_rel
    dest_census.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(census_src, dest_census)
    shutil.copyfile(obs_src, dest_obs)
    sealed_at = _parse_utc(str(sealed["sealed_at"]))
    fingerprint = canonical_sha256(
        {
            "dataset_manifest_id": dataset_manifest_id,
            "cumulative_components": [
                {
                    "cohort_id": cohort_id,
                    "release_id": release_id,
                    "content_sha256": pair_sha,
                }
            ],
            "projection_id": "unused",
        }
    )
    dataset = DatasetManifest(
        dataset_manifest_id=dataset_manifest_id,
        dataset_id=CORPUS_DATASET_ID,
        dataset_version=dataset_version,
        schema_id="SCHEMA-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001",
        schema_sha256=_schema_sha256(),
        dataset_fingerprint=fingerprint,
        generation_task_id="LIVE_COHORT_DISCOVERY_RELEASE_SERIES_V1",
        generation_run_id=f"import-{release_id[:16]}",
        validation_receipt_sha256=sha256_bytes(
            (release / "release_manifest.json").read_bytes()
        ),
        first_reliable_available_at=imported_at,
        created_at=imported_at,
        content_sha256=canonical_sha256({"ordered_component_content": [pair_sha]}),
    )
    for part_id, rel, file_sha, rows, suffix in (
        (
            census_part_id,
            census_rel,
            census_sha,
            int(sealed["census_row_count"]),
            "-CENSUS",
        ),
        (
            obs_part_id,
            obs_rel,
            obs_sha,
            int(sealed["observation_row_count"]),
            "-OBS",
        ),
    ):
        del suffix
        part = PartitionManifest(
            partition_manifest_id=_legacy_rebind_id(dataset_manifest_id, part_id),
            dataset_manifest_id=dataset_manifest_id,
            partition_id=part_id,
            logical_location=rel,
            file_sha256=file_sha,
            content_sha256=file_sha,
            row_count=rows,
            min_event_time=sealed_at,
            max_event_time=sealed_at,
            min_available_to_strategy_at=imported_at,
            max_available_to_strategy_at=imported_at,
            first_reliable_available_at=imported_at,
            created_at=imported_at,
        )
        _publish_bytes(
            data_root / "datasets" / "manifests" / "partitions" / f"{part.partition_manifest_id}.json",
            canonical_manifest_bytes(part),
        )
    labels = {
        **REQUIRED_LABELS,
        "release_id": release_id,
        "cohort_id": cohort_id,
        "corpus_version": 1,
        "dataset_version": dataset_version,
        "cohort_lineage": [cohort_id],
        "feature_families": list(sealed["feature_families"]),
        "feature_hint": None,
        "yield_eligible": int(sealed["yield_eligible"]),
        "yield_missing": int(sealed["yield_missing"]),
        "census_row_count_cumulative": int(sealed["census_row_count"]),
        "observation_row_count_cumulative": int(sealed["observation_row_count"]),
        "dataset_terminal": "SAMPLE_VALID",
        "readiness_state": sealed.get("readiness_state"),
        "discovery_coverage_class": sealed.get("discovery_coverage_class"),
        "imported_at": imported_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "accepted_hypothesis_id": None,
        "is_current_corpus_version": True,
        "cumulative_composition": True,
    }
    published = {
        "commit_point": "LIVE_LIFECYCLE_DISCOVERY_CORPUS_PUBLICATION_V1",
        "dataset_manifest_id": dataset_manifest_id,
        "dataset_fingerprint": fingerprint,
        "release_id": release_id,
        "cohort_id": cohort_id,
        "corpus_version": 1,
        "imported_at": imported_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "cumulative_cohort_count": 1,
    }
    manifests = data_root / "datasets" / "manifests"
    _publish_bytes(manifests / f"{dataset_manifest_id}.json", canonical_manifest_bytes(dataset))
    _publish_bytes(
        manifests / f"{dataset_manifest_id}.labels.json",
        json.dumps(labels, sort_keys=True, separators=(",", ":")).encode("utf-8"),
    )
    _publish_bytes(
        manifests / f"{dataset_manifest_id}.published",
        json.dumps(published, sort_keys=True, separators=(",", ":")).encode("utf-8"),
    )
    lineage = {
        "corpus_dataset_id": CORPUS_DATASET_ID,
        "current_corpus_version": 1,
        "current_dataset_manifest_id": dataset_manifest_id,
        "cohorts": [
            {
                "cohort_id": cohort_id,
                "release_id": release_id,
                "content_sha256": pair_sha,
                "corpus_version": 1,
                "dataset_manifest_id": dataset_manifest_id,
                "dataset_version": dataset_version,
                "imported_at": imported_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "census_rel": census_rel,
                "obs_rel": obs_rel,
                "census_sha256": census_sha,
                "observations_sha256": obs_sha,
                "census_row_count": int(sealed["census_row_count"]),
                "observation_row_count": int(sealed["observation_row_count"]),
                "feature_families": list(sealed["feature_families"]),
                "yield_eligible": int(sealed["yield_eligible"]),
                "yield_missing": int(sealed["yield_missing"]),
                "sealed_at": str(sealed["sealed_at"]),
                "first_reliable_available_at": imported_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        ],
        "versions": [
            {
                "corpus_version": 1,
                "dataset_manifest_id": dataset_manifest_id,
                "cohort_id": cohort_id,
            }
        ],
    }
    lineage_path = data_root / "datasets" / "live_lifecycle_corpus" / "lineage.json"
    lineage_path.parent.mkdir(parents=True, exist_ok=True)
    lineage_path.write_bytes(
        json.dumps(lineage, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    return {
        "dataset_manifest_id": dataset_manifest_id,
        "census_rel": census_rel,
        "obs_rel": obs_rel,
        "census_sha256": census_sha,
        "observations_sha256": obs_sha,
        "legacy_dataset_bytes": _sha256_path(manifests / f"{dataset_manifest_id}.json"),
    }


class LiveCorpusManifestContractRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._real_before = _real_corpus_fingerprint()

    def tearDown(self) -> None:
        self.assertEqual(_real_corpus_fingerprint(), getattr(self, "_real_before", None))

    def test_pre_post_parquet_logical_hash_and_schema_identity(self) -> None:
        census_rows = [
            {
                "release_id": "r1",
                "cohort_id": "REL-A",
                "source_schedule_sha256": "a" * 64,
                "activation_id": "act",
                "producer_git_sha": "b" * 40,
                "mint": "MintA",
                "discovery_first_reliable_available_at": "2026-01-05T12:00:00Z",
                "authoritative_anchor": "2026-01-05T12:00:00Z",
                "candidate_state": "ADMITTED",
                "membership_state": "OBSERVED",
                "denominator_state": "observed",
                "sampling_policy": "HASH_SAMPLE",
                "sampling_seed": "seed",
                "inclusion_probability": "0.1",
                "selected_or_excluded": "SELECTED",
                "exclusion_reason": None,
                "discovery_coverage_class": "EMPIRICAL_OVERLAP_ONLY",
                "source_request_sha256": "c" * 64,
                "source_response_sha256": "d" * 64,
                "evidence_role": LIVE_EVIDENCE_ROLE,
            },
            {
                "release_id": "r1",
                "cohort_id": "REL-A",
                "source_schedule_sha256": "a" * 64,
                "activation_id": "act",
                "producer_git_sha": "b" * 40,
                "mint": "MintA",
                "discovery_first_reliable_available_at": "2026-01-05T12:00:00Z",
                "authoritative_anchor": "2026-01-05T12:00:00Z",
                "candidate_state": "ADMITTED",
                "membership_state": "OBSERVED",
                "denominator_state": "observed",
                "sampling_policy": "HASH_SAMPLE",
                "sampling_seed": "seed",
                "inclusion_probability": "0.1",
                "selected_or_excluded": "SELECTED",
                "exclusion_reason": None,
                "discovery_coverage_class": "EMPIRICAL_OVERLAP_ONLY",
                "source_request_sha256": "c" * 64,
                "source_response_sha256": "d" * 64,
                "evidence_role": LIVE_EVIDENCE_ROLE,
            },
        ]
        obs_rows = [
            {
                "release_id": "r1",
                "cohort_id": "REL-A",
                "mint": "MintA",
                "point_id": "X300",
                "primitive_id": "PRIM-1",
                "field_id": "FIELD-1",
                "value_kind": "DECIMAL",
                "typed_value": "1.25",
                "state": "OBSERVED",
                "missing_reason": None,
                "event_time": "2026-01-05T12:00:00Z",
                "request_started_at": "2026-01-05T12:00:00Z",
                "response_received_at": "2026-01-05T12:00:00Z",
                "first_reliable_available_at": "2026-01-05T12:00:00Z",
                "request_sha256": "e" * 64,
                "response_sha256": "f" * 64,
                "call_occurrence_id": "1" * 64,
                "http_status": 200,
                "http_class": "OK",
                "evidence_role": LIVE_EVIDENCE_ROLE,
                "confirmatory_reuse_forbidden": True,
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            census_path = base / "census.parquet"
            obs_path = base / "obs.parquet"
            census_hash = write_parquet_and_confirm_logical_hash(
                census_path,
                census_rows,
                schema=CENSUS_RELEASE_SCHEMA,
                write_kwargs=RELEASE_PARQUET_WRITE_KWARGS,
            )
            obs_hash = write_parquet_and_confirm_logical_hash(
                obs_path,
                obs_rows,
                schema=OBS_RELEASE_SCHEMA,
                write_kwargs=RELEASE_PARQUET_WRITE_KWARGS,
            )
            self.assertEqual(census_hash, hash_logical_rows(census_rows, schema=CENSUS_RELEASE_SCHEMA))
            self.assertEqual(obs_hash, hash_logical_rows(obs_rows, schema=OBS_RELEASE_SCHEMA))
            census_claims = measure_live_corpus_parquet(
                census_path,
                kind="CENSUS",
                partition_id="CENSUS",
                logical_location="census.parquet",
            )
            obs_claims = measure_live_corpus_parquet(
                obs_path,
                kind="OBS",
                partition_id="OBS",
                logical_location="obs.parquet",
            )
            self.assertEqual(census_claims.content_sha256, census_hash)
            self.assertNotEqual(census_claims.content_sha256, census_claims.file_sha256)
            self.assertIsNone(census_claims.min_event_time)
            self.assertIsNone(census_claims.max_event_time)
            self.assertEqual(obs_claims.row_count, 1)
            self.assertEqual(
                obs_claims.min_event_time,
                datetime(2026, 1, 5, 12, tzinfo=UTC),
            )
            self.assertNotEqual(obs_claims.content_sha256, obs_claims.file_sha256)
        live_sha = live_corpus_schema_sha256()
        self.assertNotEqual(live_sha, _schema_sha256())
        self.assertEqual(LOGICAL_ROW_PROFILE, "smial-live-corpus-logical-rows-v1")

    def test_legacy_repair_future_import_and_idempotence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            data_root = base / "rdp"
            data_root.mkdir()
            release0, sealed0, cohort0 = _seal_week(base, 0)
            imported_at = datetime(2026, 1, 20, 1, tzinfo=UTC)
            legacy = _install_legacy_corpus(
                data_root=data_root,
                release=release0,
                sealed=sealed0,
                imported_at=imported_at,
            )
            census_path = data_root / legacy["census_rel"]
            obs_path = data_root / legacy["obs_rel"]
            census_before = _sha256_path(census_path)
            obs_before = _sha256_path(obs_path)
            legacy_manifest_path = (
                data_root / "datasets" / "manifests" / f"{legacy['dataset_manifest_id']}.json"
            )
            legacy_bytes = legacy_manifest_path.read_bytes()
            release1, _sealed1, cohort1 = _seal_week(base, 1)
            with self.assertRaises(Exception):
                verify_partition_manifest(
                    PartitionManifest.model_validate_json(
                        next(
                            (
                                data_root / "datasets" / "manifests" / "partitions"
                            ).glob("partition-*.json")
                        ).read_bytes()
                    )
                )
            with self.assertRaises(LiveCohortReleaseError) as blocked:
                import_live_cohort(
                    release_root=release1,
                    data_root=data_root,
                    import_time=datetime(2026, 1, 27, 1, tzinfo=UTC),
                )
            self.assertEqual(str(blocked.exception), LEGACY_CORPUS_REQUIRES_REPAIR)
            with self.assertRaises(LiveCohortReleaseError) as reimport:
                import_live_cohort(
                    release_root=release0,
                    data_root=data_root,
                    import_time=datetime(2026, 1, 27, 1, tzinfo=UTC),
                )
            self.assertEqual(str(reimport.exception), LEGACY_CORPUS_REQUIRES_REPAIR)

            published_at = datetime(2026, 9, 17, 10, tzinfo=UTC)
            repaired = repair_live_corpus_manifests(
                data_root=data_root,
                published_at=published_at,
            )
            self.assertEqual(repaired["status"], "REPAIRED")
            self.assertEqual(repaired["corpus_version"], 1)
            self.assertEqual(repaired["superseded_dataset_manifest_id"], legacy["dataset_manifest_id"])
            self.assertTrue(str(repaired["dataset_version"]).endswith(CANONICAL_METADATA_SUFFIX))
            self.assertNotEqual(repaired["dataset_manifest_id"], legacy["dataset_manifest_id"])
            self.assertEqual(_sha256_path(census_path), census_before)
            self.assertEqual(_sha256_path(obs_path), obs_before)
            self.assertEqual(legacy_manifest_path.read_bytes(), legacy_bytes)

            new_mid = repaired["dataset_manifest_id"]
            dataset = DatasetManifest.model_validate_json(
                (data_root / "datasets" / "manifests" / f"{new_mid}.json").read_bytes()
            )
            self.assertEqual(dataset.schema_sha256, live_corpus_schema_sha256())
            self.assertNotEqual(dataset.schema_sha256, _schema_sha256())
            partitions = []
            for path in sorted(
                (data_root / "datasets" / "manifests" / "partitions").glob("partition-*.json")
            ):
                payload = json.loads(path.read_text(encoding="utf-8"))
                if payload.get("dataset_manifest_id") != new_mid:
                    continue
                part = PartitionManifest.model_validate_json(path.read_bytes())
                verify_partition_manifest(part)
                partitions.append(part)
                self.assertNotEqual(part.content_sha256, part.file_sha256)
                self.assertNotEqual(
                    part.partition_manifest_id,
                    _legacy_rebind_id(new_mid, part.partition_id),
                )
                if part.partition_id.endswith("-CENSUS"):
                    self.assertIsNone(part.min_event_time)
                    self.assertIsNone(part.max_event_time)
                    self.assertEqual(part.file_sha256, legacy["census_sha256"])
                else:
                    admission = CAMPAIGN_STARTS
                    self.assertEqual(part.min_event_time, admission)
                    self.assertEqual(part.max_event_time, admission)
                    self.assertNotEqual(part.min_event_time, _parse_utc(str(sealed0["sealed_at"])))
                    self.assertEqual(part.file_sha256, legacy["observations_sha256"])
            verify_dataset_manifest(dataset, partitions=partitions)
            receipt_path = data_root / "datasets" / "manifests" / f"{new_mid}.validation.json"
            receipt = json.loads(receipt_path.read_bytes().decode("utf-8"))
            self.assertNotIn("content_sha256", receipt)
            self.assertNotIn("dataset_content_sha256", receipt)
            self.assertEqual(
                hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
                dataset.validation_receipt_sha256,
            )
            self.assertEqual(receipt["dataset_fingerprint"], dataset.dataset_fingerprint)
            self.assertEqual(receipt["superseded_dataset_manifest_id"], legacy["dataset_manifest_id"])
            repaired_labels = json.loads(
                (
                    data_root / "datasets" / "manifests" / f"{new_mid}.labels.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(repaired_labels["dataset_terminal"], "SAMPLE_VALID")
            self.assertEqual(repaired_labels["yield_eligible"], int(sealed0["yield_eligible"]))
            lineage = json.loads(
                (data_root / "datasets" / "live_lifecycle_corpus" / "lineage.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(lineage["current_corpus_version"], 1)
            self.assertEqual(len(lineage["cohorts"]), 1)
            self.assertEqual(lineage["cohorts"][0]["dataset_manifest_id"], new_mid)
            self.assertEqual(
                lineage["cohorts"][0]["superseded_dataset_manifest_id"],
                legacy["dataset_manifest_id"],
            )
            enumerated, _ = enumerate_rdp_datasets(data_root)
            current = [
                item
                for item in select_current_datasets_for_forge(enumerated)
                if item.get("dataset_id") == CORPUS_DATASET_ID
            ]
            self.assertEqual(len(current), 1)
            self.assertEqual(current[0]["dataset_manifest_id"], new_mid)

            again = repair_live_corpus_manifests(
                data_root=data_root,
                published_at=datetime(2026, 9, 18, tzinfo=UTC),
            )
            self.assertEqual(again["status"], "IDEMPOTENT_REPAIR")
            self.assertEqual(again["dataset_manifest_id"], new_mid)
            self.assertEqual(_sha256_path(census_path), census_before)

            second = import_live_cohort(
                release_root=release1,
                data_root=data_root,
                import_time=datetime(2026, 1, 27, 2, tzinfo=UTC),
            )
            self.assertEqual(second["status"], "IMPORTED")
            self.assertEqual(second["corpus_version"], 2)
            self.assertEqual(second["logical_rows_measured_partitions"], 2)
            measured = list(second.get("measured_logical_locations") or [])
            self.assertEqual(len(measured), 2)
            self.assertTrue(
                all(
                    legacy["census_rel"] not in loc and legacy["obs_rel"] not in loc
                    for loc in measured
                )
            )
            self.assertEqual(_sha256_path(census_path), census_before)
            self.assertEqual(len(json.loads(
                (data_root / "datasets" / "live_lifecycle_corpus" / "lineage.json").read_text(
                    encoding="utf-8"
                )
            )["cohorts"]), 2)
            second_dataset = DatasetManifest.model_validate_json(
                (
                    data_root
                    / "datasets"
                    / "manifests"
                    / f"{second['dataset_manifest_id']}.json"
                ).read_bytes()
            )
            second_parts = []
            for path in sorted(
                (data_root / "datasets" / "manifests" / "partitions").glob("partition-*.json")
            ):
                payload = json.loads(path.read_text(encoding="utf-8"))
                if payload.get("dataset_manifest_id") != second["dataset_manifest_id"]:
                    continue
                part = PartitionManifest.model_validate_json(path.read_bytes())
                verify_partition_manifest(part)
                second_parts.append(part)
            self.assertEqual(len(second_parts), 4)
            verify_dataset_manifest(second_dataset, partitions=second_parts)

    def test_interrupt_before_visibility_then_rerun(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            data_root = base / "rdp"
            data_root.mkdir()
            release0, sealed0, _cohort0 = _seal_week(base, 0)
            imported_at = datetime(2026, 1, 20, 1, tzinfo=UTC)
            legacy = _install_legacy_corpus(
                data_root=data_root,
                release=release0,
                sealed=sealed0,
                imported_at=imported_at,
            )
            census_path = data_root / legacy["census_rel"]
            census_before = _sha256_path(census_path)
            published_at = datetime(2026, 9, 17, 11, tzinfo=UTC)

            def _fault() -> None:
                raise _VisibilityFault("before published")

            with self.assertRaises(_VisibilityFault):
                repair_live_corpus_manifests(
                    data_root=data_root,
                    published_at=published_at,
                    fault_before_visibility=_fault,
                )
            lineage = json.loads(
                (data_root / "datasets" / "live_lifecycle_corpus" / "lineage.json").read_text(
                    encoding="utf-8"
                )
            )
            new_mid = lineage["current_dataset_manifest_id"]
            published_path = data_root / "datasets" / "manifests" / f"{new_mid}.published"
            self.assertFalse(published_path.is_file())
            enumerated, warnings = enumerate_rdp_datasets(data_root)
            current = [
                item
                for item in select_current_datasets_for_forge(enumerated)
                if item.get("dataset_id") == CORPUS_DATASET_ID
            ]
            self.assertTrue(current)
            self.assertNotEqual(current[0]["dataset_manifest_id"], new_mid)
            self.assertEqual(_sha256_path(census_path), census_before)
            self.assertEqual(len(lineage["cohorts"]), 1)
            release1, _sealed1, _cohort1 = _seal_week(base, 1)
            with self.assertRaises(LiveCohortReleaseError) as blocked:
                import_live_cohort(
                    release_root=release1,
                    data_root=data_root,
                    import_time=datetime(2026, 1, 27, 1, tzinfo=UTC),
                )
            self.assertEqual(str(blocked.exception), LEGACY_CORPUS_REQUIRES_REPAIR)

            rerun = repair_live_corpus_manifests(
                data_root=data_root,
                published_at=datetime(2026, 9, 19, tzinfo=UTC),
            )
            self.assertEqual(rerun["dataset_manifest_id"], new_mid)
            self.assertTrue(published_path.is_file())
            published_dataset = DatasetManifest.model_validate_json(
                (data_root / "datasets" / "manifests" / f"{new_mid}.json").read_bytes()
            )
            self.assertEqual(
                published_dataset.first_reliable_available_at,
                datetime(2026, 9, 19, tzinfo=UTC),
            )
            self.assertEqual(_sha256_path(census_path), census_before)
            enumerated, _ = enumerate_rdp_datasets(data_root)
            current = [
                item
                for item in select_current_datasets_for_forge(enumerated)
                if item.get("dataset_id") == CORPUS_DATASET_ID
            ]
            self.assertEqual(current[0]["dataset_manifest_id"], new_mid)
            self.assertEqual(
                json.loads(
                    (
                        data_root / "datasets" / "live_lifecycle_corpus" / "lineage.json"
                    ).read_text(encoding="utf-8")
                )["current_corpus_version"],
                1,
            )

    def test_repair_fail_closed_on_missing_yield(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            data_root = base / "rdp"
            data_root.mkdir()
            release0, sealed0, _cohort0 = _seal_week(base, 0)
            _install_legacy_corpus(
                data_root=data_root,
                release=release0,
                sealed=sealed0,
                imported_at=datetime(2026, 1, 20, 1, tzinfo=UTC),
            )
            lineage_path = data_root / "datasets" / "live_lifecycle_corpus" / "lineage.json"
            lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
            del lineage["cohorts"][0]["yield_eligible"]
            lineage_path.write_text(
                json.dumps(lineage, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            with self.assertRaises(LiveCohortReleaseError) as missing:
                repair_live_corpus_manifests(
                    data_root=data_root,
                    published_at=datetime(2026, 9, 17, tzinfo=UTC),
                )
            self.assertEqual(str(missing.exception), "CORPUS_LINEAGE_INCOMPLETE")

    def test_first_import_interrupt_not_selected_current(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            data_root = base / "rdp"
            data_root.mkdir()
            release0, _sealed0, _cohort0 = _seal_week(base, 0)

            def _fault() -> None:
                raise _VisibilityFault("before published")

            with self.assertRaises(_VisibilityFault):
                import_live_cohort(
                    release_root=release0,
                    data_root=data_root,
                    import_time=datetime(2026, 1, 20, 1, tzinfo=UTC),
                    fault_before_visibility=_fault,
                )
            lineage = json.loads(
                (
                    data_root / "datasets" / "live_lifecycle_corpus" / "lineage.json"
                ).read_text(encoding="utf-8")
            )
            new_mid = lineage["current_dataset_manifest_id"]
            enumerated, warnings = enumerate_rdp_datasets(data_root)
            current = [
                item
                for item in select_current_datasets_for_forge(enumerated)
                if item.get("dataset_id") == CORPUS_DATASET_ID
            ]
            self.assertEqual(current, [])
            self.assertFalse(
                (data_root / "datasets" / "manifests" / f"{new_mid}.json").is_file()
            )
            rerun = import_live_cohort(
                release_root=release0,
                data_root=data_root,
                import_time=datetime(2026, 1, 20, 2, tzinfo=UTC),
            )
            self.assertEqual(rerun["dataset_manifest_id"], new_mid)
            self.assertTrue(
                (
                    data_root / "datasets" / "manifests" / f"{new_mid}.published"
                ).is_file()
            )


if __name__ == "__main__":
    unittest.main()
