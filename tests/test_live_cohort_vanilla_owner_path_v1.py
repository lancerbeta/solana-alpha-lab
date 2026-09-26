"""Vanilla owner path: identity, bounded plan, incremental import, current Forge view."""

from __future__ import annotations

import inspect
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
    enumerate_work,
    reset_enumerate_work,
)
from solana_alpha_lab.factory.live_cohort_discovery_release import (  # noqa: E402
    LiveCohortReleaseError,
    import_live_cohort,
    seal_live_cohort,
    verify_live_cohort,
    write_observation_rdp_source,
)
from solana_alpha_lab.factory.live_cohort_to_forge import synthetic_closed_receipt  # noqa: E402
from solana_alpha_lab.factory.hfic_evidence_identity import (  # noqa: E402
    compute_market_epoch_for_data_root,
)
from solana_alpha_lab.factory.live_cohort_vanilla_path import (  # noqa: E402
    capture_freeze_export,
    classify_mirror,
    collect_bounded_transfer_manifest,
    place_missing,
    select_next_mature_unimported_cohort,
    unpack_next_live_cohort,
)
from solana_alpha_lab.storage.manifests import (  # noqa: E402
    build_dataset_manifest,
    build_partition_manifest,
    compute_dataset_manifest_id,
)
from tests.test_live_cohort_discovery_release_series import (  # noqa: E402
    ACTIVATION,
    CAMPAIGN_STARTS,
    CAMPAIGN_STOPS,
    _snapshot_for_week,
    cohort_id_for_admission,
)

CORPUS_ID = "DATASET-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001"


class VanillaOwnerPathTests(unittest.TestCase):
    def test_rollover_does_not_invent_predecessor_successor_window(self) -> None:
        cutover = datetime(2026, 9, 14, 17, 35, 10, 845525, tzinfo=UTC)
        predecessor = {
            "schedule_sha256": "a" * 64,
            "activation_id": "ACT-PREDECESSOR",
            "starts_at": "2026-09-02T11:19:00Z",
            "stops_admitting_at": "2026-09-23T11:19:00Z",
        }
        successor = {
            "schedule_sha256": "b" * 64,
            "activation_id": "ACT-SUCCESSOR",
            "starts_at": "2026-09-14T17:35:10.845525Z",
            "stops_admitting_at": "2026-09-21T17:35:10.845525Z",
        }
        chosen = select_next_mature_unimported_cohort(
            activations=[predecessor, successor],
            rollovers=[
                {
                    "predecessor_schedule_sha256": predecessor["schedule_sha256"],
                    "predecessor_activation_id": predecessor["activation_id"],
                    "cutover_at": "2026-09-14T17:35:10.845525Z",
                }
            ],
            imported_cohort_ids={
                "REL-20260902T111900Z-20260909T111900Z",
                "REL-20260909T111900Z-20260916T111900Z",
            },
            as_of=datetime(2026, 9, 26, tzinfo=UTC),
        )
        assert chosen is not None
        self.assertEqual(chosen["cohort_id"], "REL-20260914T173510Z-20260921T173510Z")
        self.assertEqual(chosen["activation_id"], "ACT-SUCCESSOR")
        self.assertNotEqual(chosen["cohort_id"], "REL-20260916T111900Z-20260923T111900Z")
        self.assertGreaterEqual(cutover, chosen["window_start"])

    def test_unpack_rejects_open_future_before_build(self) -> None:
        receipt = synthetic_closed_receipt(
            schedule_sha256="b" * 64,
            activation_id="ACT-SUCCESSOR",
            cohort_id="REL-20260914T173510Z-20260921T173510Z",
            as_of=datetime(2026, 9, 26, tzinfo=UTC),
            members_total=1,
        )
        receipt["due_states"] = {"OBSERVED": 1}
        receipt["pending_future"] = 1
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(LiveCohortReleaseError) as raised:
                unpack_next_live_cohort(
                    observation_rdp=Path(tmp),
                    data_root=Path(tmp),
                    repo_root=ROOT,
                    activations=[],
                    rollovers=[],
                    closure_receipt=receipt,
                    as_of=datetime(2026, 9, 26, tzinfo=UTC),
                    plan_only=True,
                )
        self.assertEqual(str(raised.exception), "COHORT_PENDING_FUTURE")

    def test_capture_phase_cannot_materialize(self) -> None:
        import importlib.util

        source = inspect.getsource(capture_freeze_export)
        self.assertNotIn("build_live_observation_source_from_rdp", source)
        self.assertNotIn("seal_live_cohort", source)
        self.assertNotIn("import_live_cohort", source)
        spec = importlib.util.spec_from_file_location(
            "discovery_evidence_release_owner_path",
            ROOT / "scripts" / "discovery_evidence_release.py",
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        owner = inspect.getsource(module._owner_unpack_over_ssh)
        self.assertIn("capture_freeze_export", owner)
        self.assertNotIn("build_live_observation_source_from_rdp", owner)
        self.assertNotIn("seal_live_cohort", owner)
        self.assertNotIn("import_live_cohort", owner)

    def test_stale_mirror_transfer_makes_plan_bounded(self) -> None:
        from tests.test_bounded_cohort_materialization_v1 import (
            ACTIVATION_ID,
            AS_OF,
            COHORT_ID,
            PRODUCER,
            WINDOW_START,
            _append_event,
            _member,
            _schedule,
            persist_observation_schedule,
            write_snapshot_unit,
        )
        from solana_alpha_lab.factory.live_cohort_discovery_release import (
            build_live_observation_source_from_rdp,
        )
        from solana_alpha_lab.factory.research_store import RecordKind

        schedule = _schedule()
        digest = str(schedule["schedule_sha256"])
        admit = WINDOW_START + timedelta(hours=2)
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / "vps_rdp"
            mirror = base / "mirror"
            source.mkdir()
            mirror.mkdir()
            persist_observation_schedule(
                data_root=source,
                schedule=schedule,
                now=admit,
                producer_git_sha=PRODUCER,
                activation_id=ACTIVATION_ID,
            )
            unit = write_snapshot_unit(
                source,
                utc_day="20260910",
                dataset_manifest_id="cur",
                rows=[_member("mint1", admit=admit, digest=digest)],
            )
            _append_event(
                source,
                record_id="MEM-CUR",
                kind=RecordKind.OBSERVATION_MEMBER_BATCH,
                digest=digest,
                payload={
                    "schedule_sha256": digest,
                    "content_sha256": "ab" * 32,
                    "dataset_manifest_id": "cur",
                    "member_location": str(unit["publications"][0]["rel"]),
                    "row_count": 1,
                },
                now=admit,
                txn="RESEARCH-TXN-MEM-STALEMIRROR",
            )
            receipt = synthetic_closed_receipt(
                schedule_sha256=digest,
                activation_id=ACTIVATION_ID,
                cohort_id=COHORT_ID,
                as_of=AS_OF,
                members_total=1,
            )
            receipt["due_states"] = {"OBSERVED": 1}
            manifest = collect_bounded_transfer_manifest(
                observation_rdp=source,
                schedule_sha256=digest,
                activation_id=ACTIVATION_ID,
                cohort_id=COHORT_ID,
                closure_receipt=receipt,
            )
            paths = {item["path"] for item in manifest["entries"]}
            self.assertTrue(any(path.endswith("unit.json") for path in paths))
            self.assertTrue(any(path.endswith("members.layout.json") for path in paths))
            self.assertTrue(any(path.startswith("research/") for path in paths))
            classified = classify_mirror(manifest, mirror)
            self.assertEqual(
                classified["unique_paths_total"],
                classified["reused_files"] + classified["missing_files"] + classified["conflicts"],
            )
            self.assertGreater(classified["missing_files"], 0)
            self.assertEqual(classified["conflicts"], 0)
            place_missing(
                manifest=manifest,
                source_root=source,
                mirror_root=mirror,
                classification=classified,
            )
            verified = classify_mirror(manifest, mirror)
            self.assertEqual(verified["verified_paths_total"], verified["unique_paths_total"])
            self.assertEqual(verified["missing_files"], 0)
            plan = build_live_observation_source_from_rdp(
                observation_rdp_root=mirror,
                schedule_sha256=digest,
                activation_id=ACTIVATION_ID,
                cohort_id=COHORT_ID,
                closure_receipt=receipt,
                ops_store=None,
                plan_only=True,
            )
            self.assertEqual(plan["work_class"], "BOUNDED_COHORT_WINDOW")
            self.assertEqual(int(plan["observation_partition_index_files_read"]), 0)

    def test_mirror_conflict_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mirror = Path(tmp)
            target = mirror / "datasets" / "keep.parquet"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"local-bytes")
            manifest = {
                "entries": [
                    {
                        "path": "datasets/keep.parquet",
                        "sha256": "ab" * 32,
                        "bytes": 11,
                    }
                ]
            }
            classified = classify_mirror(manifest, mirror)
            self.assertEqual(classified["conflicts"], 1)
            self.assertEqual(classified["status"], "CONFLICT")

    def test_ordinary_append_does_not_rehash_historical_parquet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            data_root = base / "rdp"
            data_root.mkdir()
            first_bytes = 0
            for week in (0, 1):
                obs = base / f"obs-{week}"
                release = base / f"rel-{week}"
                snap = _snapshot_for_week(week, coverage="GAP_SUSPECTED")
                write_observation_rdp_source(obs, snap)
                cohort = cohort_id_for_admission(
                    CAMPAIGN_STARTS + timedelta(days=7 * week, hours=1),
                    starts_at=CAMPAIGN_STARTS,
                    stops_admitting_at=CAMPAIGN_STOPS,
                )
                assert cohort is not None
                as_of = CAMPAIGN_STARTS + timedelta(days=7 * week + 10)
                seal_live_cohort(
                    observation_rdp_root=obs,
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
                self.assertEqual(imported["status"], "IMPORTED")
                self.assertEqual(int(imported["historical_parquet_bytes_hashed"]), 0)
                self.assertGreater(int(imported["new_cohort_parquet_bytes_hashed"]), 0)
                if week == 0:
                    first_bytes = int(imported["new_cohort_parquet_bytes_hashed"])
                else:
                    self.assertNotEqual(
                        int(imported["new_cohort_parquet_bytes_hashed"]),
                        first_bytes + int(imported["new_cohort_parquet_bytes_hashed"]),
                    )
            from solana_alpha_lab.contracts.schema_v1 import (
                DatasetManifest,
                PartitionManifest,
            )
            from solana_alpha_lab.factory.cohort_import_readback import (
                build_cohort_import_readback,
            )
            from solana_alpha_lab.factory.hfic_evidence_identity import (
                build_market_evidence_basis,
                market_evidence_epoch_sha256,
            )
            from solana_alpha_lab.factory.hfic_preflight import (
                MIN_USABLE_YIELD_ELIGIBLE,
                SAMPLE_INVALID,
            )
            from solana_alpha_lab.factory.observation_schedule import canonical_sha256

            manifests = data_root / "datasets" / "manifests"
            lineage = json.loads(
                (data_root / "datasets" / "live_lifecycle_corpus" / "lineage.json").read_text(
                    encoding="utf-8"
                )
            )
            current_mid = str(lineage["current_dataset_manifest_id"])
            current_manifest = DatasetManifest.model_validate_json(
                (manifests / f"{current_mid}.json").read_bytes()
            )
            labels_path = manifests / f"{current_mid}.labels.json"
            labels = (
                json.loads(labels_path.read_text(encoding="utf-8"))
                if labels_path.is_file()
                else None
            )
            validation = json.loads(
                (manifests / f"{current_mid}.validation.json").read_text(encoding="utf-8")
            )
            composition = {
                (
                    str(row["cohort_id"]),
                    str(row["release_id"]),
                    str(row["content_sha256"]),
                )
                for row in validation["corpus_composition"]
            }
            bindings = []
            visible = []
            for cohort in lineage["cohorts"]:
                key = (
                    str(cohort["cohort_id"]),
                    str(cohort["release_id"]),
                    str(cohort["content_sha256"]),
                )
                visible.append(str(cohort["cohort_id"]))
                if key in composition:
                    bindings.append(
                        {
                            "cohort_id": key[0],
                            "release_id": key[1],
                            "source_sha256": key[2],
                        }
                    )
            named_parts = [
                PartitionManifest.model_validate_json(
                    (manifests / "partitions" / f"{part_id}.json").read_bytes()
                )
                for part_id in validation["partition_manifest_ids"]
            ]
            marker = canonical_sha256(
                {
                    "identity_version": "A3_DATASET_MANIFEST_PIT_AVAILABILITY_VALIDATION_V1",
                    "dataset_manifest": current_manifest.model_dump(mode="json"),
                    "partition_manifests": [
                        item.model_dump(mode="json")
                        for item in sorted(
                            named_parts, key=lambda item: item.partition_manifest_id
                        )
                    ],
                }
            )
            yield_eligible = int((labels or {}).get("yield_eligible") or 0)
            feature_usable = yield_eligible >= MIN_USABLE_YIELD_ELIGIBLE
            raw_base_x = None if labels is None else labels.get(
                "base_x_population_n", labels.get("base_x_n")
            )
            families = [
                item
                for item in ((labels or {}).get("feature_families") or [])
                if isinstance(item, str) and item
            ][:8]
            terminal = (labels or {}).get("dataset_terminal")
            if not isinstance(terminal, str):
                terminal = "SAMPLE_VALID" if feature_usable else SAMPLE_INVALID
            reference_basis = build_market_evidence_basis(
                datasets=[
                    {
                        "dataset_manifest_id": current_manifest.dataset_manifest_id,
                        "dataset_id": current_manifest.dataset_id,
                        "dataset_version": current_manifest.dataset_version,
                        "dataset_fingerprint": current_manifest.dataset_fingerprint,
                        "a3_pit_availability_validation_sha256": marker,
                        "evidence_role": str((labels or {}).get("evidence_role") or "UNSPECIFIED"),
                        "labels": labels,
                        "yield_eligible": yield_eligible,
                        "base_x_population_n": (
                            int(raw_base_x) if raw_base_x is not None else None
                        ),
                        "yield_missing": int((labels or {}).get("yield_missing") or 0),
                        "feature_usable": feature_usable,
                        "dataset_terminal": terminal,
                        "feature_hint": (labels or {}).get("feature_hint"),
                        "feature_families": families,
                    }
                ],
                visible_cohort_ids=visible,
                current_dataset_manifest_id=current_mid,
                corpus_version=build_cohort_import_readback(data_root).get("corpus_version"),
                lineage_bindings=bindings,
            )
            reference_epoch = market_evidence_epoch_sha256(reference_basis)
            reset_enumerate_work()
            optimized_epoch, _basis = compute_market_epoch_for_data_root(ROOT, data_root)
            optimized_work = enumerate_work()
            self.assertEqual(optimized_work["superseded_corpus_parquet_bytes_hashed"], 0)
            self.assertEqual(optimized_work["directory_partition_files_read"], 0)
            self.assertGreater(optimized_work["named_partition_manifests_opened"], 0)
            self.assertEqual(optimized_epoch, reference_epoch)
            reset_enumerate_work()
            enumerate_rdp_datasets(data_root, live_corpus_current_only=True)
            current_only_bytes = enumerate_work()["parquet_bytes_hashed"]
            part_dir = data_root / "datasets" / "manifests" / "partitions"
            current = json.loads(
                (data_root / "datasets" / "live_lifecycle_corpus" / "lineage.json").read_text(
                    encoding="utf-8"
                )
            )["current_dataset_manifest_id"]
            current_doc = json.loads(
                (data_root / "datasets" / "manifests" / f"{current}.json").read_text(encoding="utf-8")
            )
            for index in range(200):
                blob = b"x" * (32 + index)
                rel = f"datasets/partitions/date=2099-01-01/extra-{index}.parquet"
                dest = data_root / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(blob)
                digest = __import__("hashlib").sha256(blob).hexdigest()
                version = f"extra-corpus-{index}"
                part = build_partition_manifest(
                    dataset_id=CORPUS_ID,
                    dataset_version=version,
                    partition_id=f"extra-{index}",
                    logical_location=rel,
                    file_sha256=digest,
                    content_sha256=digest,
                    row_count=1,
                    first_reliable_available_at=CAMPAIGN_STARTS,
                    created_at=CAMPAIGN_STARTS,
                    min_event_time=CAMPAIGN_STARTS,
                    max_event_time=CAMPAIGN_STARTS,
                    min_available_to_strategy_at=CAMPAIGN_STARTS,
                    max_available_to_strategy_at=CAMPAIGN_STARTS,
                )
                part_path = part_dir / f"{part.partition_manifest_id}.json"
                part_path.write_text(part.model_dump_json(), encoding="utf-8")
                dataset = build_dataset_manifest(
                    dataset_id=CORPUS_ID,
                    dataset_version=version,
                    schema_id=current_doc["schema_id"],
                    schema_sha256=current_doc["schema_sha256"],
                    generation_task_id="EXTRA",
                    generation_run_id=f"extra-{index}",
                    validation_receipt_sha256="ab" * 32,
                    first_reliable_available_at=CAMPAIGN_STARTS,
                    created_at=CAMPAIGN_STARTS,
                    partitions=[part],
                )
                manifest_id = compute_dataset_manifest_id(CORPUS_ID, version)
                self.assertEqual(dataset.dataset_manifest_id, manifest_id)
                (data_root / "datasets" / "manifests" / f"{manifest_id}.json").write_text(
                    dataset.model_dump_json(),
                    encoding="utf-8",
                )
            reset_enumerate_work()
            enumerated, _warnings = enumerate_rdp_datasets(
                data_root,
                live_corpus_current_only=True,
            )
            work = enumerate_work()
            visible = [item["dataset_manifest_id"] for item in enumerated if item["dataset_id"] == CORPUS_ID]
            self.assertEqual(visible, [current])
            self.assertGreaterEqual(work["superseded_live_corpus_skipped"], 200)
            self.assertEqual(work["directory_partition_files_read"], 0)
            self.assertGreater(work["named_partition_manifests_opened"], 0)
            self.assertEqual(work["superseded_corpus_parquet_bytes_hashed"], 0)
            self.assertEqual(work["parquet_bytes_hashed"], current_only_bytes)

    def test_owner_stale_mirror_reaches_forge_and_c200_is_bounded(self) -> None:
        import shutil

        from solana_alpha_lab.factory.live_cohort_discovery_release import CORPUS_DATASET_ID
        from solana_alpha_lab.factory.live_cohort_to_forge import forge_control_ready
        from solana_alpha_lab.factory.live_cohort_vanilla_path import run_owner_live_cohort
        from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
        from tests.test_live_cohort_to_forge_operational_closure_v1 import (
            ACTIVATION as OPS_ACTIVATION,
            AS_OF_C1,
            C1_ADMIT,
            COHORT1,
            PRODUCER_A,
            PUBLISH_C1,
            _commission,
            _entity,
            _obs,
            _prod_member,
            _schedule,
            _seed_ops,
        )
        from solana_alpha_lab.factory.observation_panel_publisher import (
            persist_observation_schedule,
            publish_observation_batch,
        )

        schedule = _schedule(ROOT)
        digest = str(schedule["schedule_sha256"])
        members = [_entity("A", index) for index in range(12)]
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / "vps_rdp"
            mirror = base / "mirror"
            data_root = base / "data_plane"
            ops = base / "ops.sqlite"
            source.mkdir()
            mirror.mkdir()
            data_root.mkdir()
            persist_observation_schedule(
                data_root=source,
                schedule=schedule,
                now=C1_ADMIT,
                producer_git_sha=PRODUCER_A,
                activation_id=OPS_ACTIVATION,
            )
            publish_observation_batch(
                data_root=source,
                root=ROOT,
                schedule=schedule,
                activation_id=OPS_ACTIVATION,
                now=PUBLISH_C1,
                producer_git_sha=PRODUCER_A,
                members=[_prod_member(digest, entity, C1_ADMIT) for entity in members],
                observations=[_obs(digest, entity, C1_ADMIT) for entity in members],
            )
            _seed_ops(ops, digest=digest, cohort1=members, cohort2=[])
            ObservationScheduleStore(ops).close()
            import sqlite3

            conn = sqlite3.connect(ops)
            try:
                conn.execute(
                    """
                    INSERT INTO schedule_activations(
                        schedule_sha256, activation_id, schedule_key, state,
                        authority_receipt_sha256, starts_at, stops_admitting_at,
                        payload_json, created_at, updated_at, transition_sequence
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    """,
                    (
                        digest,
                        OPS_ACTIVATION,
                        "lifecycle",
                        "ACTIVE",
                        "c" * 64,
                        "2026-09-02T11:19:00Z",
                        "2026-09-23T11:19:00Z",
                        "{}",
                        "2026-09-02T11:19:00Z",
                        "2026-09-02T11:19:00Z",
                    ),
                )
                conn.commit()
            finally:
                conn.close()
            _commission(data_root)
            self.assertFalse(any(mirror.rglob("*")))

            def _transfer(manifest: dict, missing: list[str]) -> None:
                del manifest
                for relative in missing:
                    src = source / relative
                    dest = mirror / relative
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest)

            result = run_owner_live_cohort(
                capture=lambda: capture_freeze_export(
                    observation_rdp=source,
                    ops_store=ops,
                    imported_cohort_ids=set(),
                    as_of=AS_OF_C1,
                ),
                transfer=_transfer,
                mirror_root=mirror,
                data_root=data_root,
                repo_root=ROOT,
                as_of=AS_OF_C1,
                release_builder_git_sha="a" * 40,
            )
            self.assertEqual(result["terminal"], "FORGE_CONTROL_READY")
            self.assertEqual(result["cohort_id"], COHORT1)
            self.assertEqual(result["import_status"], "IMPORTED")
            self.assertEqual(
                result["verified_paths_total"], result["unique_paths_total"]
            )
            self.assertGreater(result["unique_paths_total"], 0)
            from solana_alpha_lab.factory.hfic_evidence_identity import (
                scientific_slot_sha256,
            )

            reset_enumerate_work()
            ready = forge_control_ready(data_root=data_root, repo_root=ROOT)
            before_work = enumerate_work()
            epoch_before = ready["market_evidence_epoch_sha256"]
            slot_before = scientific_slot_sha256(
                market_evidence_epoch_sha256=epoch_before,
                representation_id="BASE",
                representation_semantic_version="HFIC-V1.2",
                owner_focus="AUTO",
            )
            reset_enumerate_work()
            part_dir = data_root / "datasets" / "manifests" / "partitions"
            current = json.loads(
                (data_root / "datasets" / "live_lifecycle_corpus" / "lineage.json").read_text(
                    encoding="utf-8"
                )
            )["current_dataset_manifest_id"]
            current_doc = json.loads(
                (data_root / "datasets" / "manifests" / f"{current}.json").read_text(
                    encoding="utf-8"
                )
            )
            for index in range(200):
                blob = b"y" * (64 + index)
                rel = f"datasets/partitions/date=2099-01-01/c200-{index}.parquet"
                dest = data_root / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(blob)
                file_sha = __import__("hashlib").sha256(blob).hexdigest()
                version = f"c200-corpus-{index}"
                part = build_partition_manifest(
                    dataset_id=CORPUS_DATASET_ID,
                    dataset_version=version,
                    partition_id=f"c200-{index}",
                    logical_location=rel,
                    file_sha256=file_sha,
                    content_sha256=file_sha,
                    row_count=1,
                    first_reliable_available_at=CAMPAIGN_STARTS,
                    created_at=CAMPAIGN_STARTS,
                    min_event_time=CAMPAIGN_STARTS,
                    max_event_time=CAMPAIGN_STARTS,
                    min_available_to_strategy_at=CAMPAIGN_STARTS,
                    max_available_to_strategy_at=CAMPAIGN_STARTS,
                )
                (part_dir / f"{part.partition_manifest_id}.json").write_text(
                    part.model_dump_json(), encoding="utf-8"
                )
                dataset = build_dataset_manifest(
                    dataset_id=CORPUS_DATASET_ID,
                    dataset_version=version,
                    schema_id=current_doc["schema_id"],
                    schema_sha256=current_doc["schema_sha256"],
                    generation_task_id="C200",
                    generation_run_id=f"c200-{index}",
                    validation_receipt_sha256="cd" * 32,
                    first_reliable_available_at=CAMPAIGN_STARTS,
                    created_at=CAMPAIGN_STARTS,
                    partitions=[part],
                )
                (data_root / "datasets" / "manifests" / f"{dataset.dataset_manifest_id}.json").write_text(
                    dataset.model_dump_json(), encoding="utf-8"
                )
                (
                    data_root / "datasets" / "manifests" / f"{dataset.dataset_manifest_id}.validation.json"
                ).write_text(
                    json.dumps(
                        {"partition_manifest_ids": [part.partition_manifest_id]},
                        sort_keys=True,
                    ),
                    encoding="utf-8",
                )
            reset_enumerate_work()
            again = forge_control_ready(
                data_root=data_root,
                repo_root=ROOT,
                imported_cohort_id=COHORT1,
            )
            work = enumerate_work()
            self.assertEqual(again["terminal"], "FORGE_CONTROL_READY")
            self.assertEqual(again["market_evidence_epoch_sha256"], epoch_before)
            self.assertEqual(
                scientific_slot_sha256(
                    market_evidence_epoch_sha256=again["market_evidence_epoch_sha256"],
                    representation_id="BASE",
                    representation_semantic_version="HFIC-V1.2",
                    owner_focus="AUTO",
                ),
                slot_before,
            )
            self.assertEqual(work["superseded_corpus_parquet_bytes_hashed"], 0)
            self.assertEqual(
                work["directory_partition_files_read"],
                before_work["directory_partition_files_read"],
            )
            self.assertEqual(
                work["named_partition_manifests_opened"],
                before_work["named_partition_manifests_opened"],
            )
            self.assertGreaterEqual(work["superseded_corpus_metadata_only"], 200)
            self.assertGreater(work["named_partition_manifests_opened"], 0)
            self.assertLess(work["named_partition_manifests_opened"], 200)
            self.assertLess(work["directory_partition_files_read"], 200)


if __name__ == "__main__":
    unittest.main()
