"""Self-contained LIVE cohort release: schedule artifact across seal/import."""

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

from solana_alpha_lab.factory.discovery_evidence_release import (  # noqa: E402
    DiscoveryReleaseError,
)
from solana_alpha_lab.factory.live_cohort_discovery_release import (  # noqa: E402
    LiveCohortReleaseError,
    build_live_observation_source_from_rdp,
    cohort_id_for_admission,
    current_corpus_partition_rows,
    import_live_cohort,
    load_live_corpus_lineage,
    seal_live_cohort,
    verify_live_cohort,
    write_observation_rdp_source,
)
from solana_alpha_lab.factory.live_cohort_schedule_artifact import (  # noqa: E402
    OBSERVATION_SCHEDULE_ARTIFACT_NAME,
    RELEASE_SCHEMA_VERSION_LEGACY,
    RELEASE_SCHEMA_VERSION_SELF_CONTAINED,
    SCHEDULE_ARTIFACT_HASH_MISMATCH,
    SCHEDULE_ARTIFACT_MISSING,
    SCHEDULE_PARSER_INVALID,
    SCHEDULE_SEMANTIC_SHA_MISMATCH,
    decode_schedule_artifact,
    encode_schedule_artifact,
)
from solana_alpha_lab.factory.live_cohort_source_bundle import (  # noqa: E402
    SOURCE_SCHEDULE_NAME,
    sha256_file_streaming,
)
from solana_alpha_lab.factory.live_cohort_to_forge import (  # noqa: E402
    LiveCohortToForgeError,
    assert_closure_ready,
    assert_source_matches_receipt,
    build_closure_receipt,
    hash_release_tree,
    verify_transported_release,
)
from solana_alpha_lab.factory.observation_panel_publisher import (  # noqa: E402
    persist_observation_schedule,
    publish_observation_batch,
)
from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    schedule_sha256,
    validate_observation_schedule,
)
from solana_alpha_lab.factory.scientific_eligibility_projection import (  # noqa: E402
    CANONICAL_SCHEDULE_UNBOUND,
    ScientificEligibilityError,
    project_scientific_eligibility,
    resolve_canonical_release_schedule,
)
from tests.test_live_cohort_discovery_release_series import (  # noqa: E402
    CAMPAIGN_STARTS,
    CAMPAIGN_STOPS,
    _snapshot_for_week,
)
from tests.test_live_cohort_to_forge_operational_closure_v1 import (  # noqa: E402
    ACTIVATION,
    AS_OF_C1,
    AS_OF_C2,
    C1_ADMIT,
    C2_ADMIT,
    COHORT1,
    COHORT2,
    PRODUCER_A,
    PRODUCER_C,
    PUBLISH_C1,
    PUBLISH_C2,
    _cli_module,
    _entity,
    _obs,
    _prod_member,
    _schedule,
    _seed_ops,
)



def _alt_schedule(base: dict) -> dict:
    alt = dict(base)
    sampling = dict(alt.get("sampling") or {})
    sampling["inclusion_probability"] = "0.0510"
    alt["sampling"] = sampling
    alt.pop("schedule_sha256", None)
    validated = validate_observation_schedule(alt, root=ROOT)
    digest = schedule_sha256(validated)
    validated["schedule_sha256"] = digest
    return validated


def _seed_rdp(
    observation_rdp: Path,
    *,
    schedule: dict,
    entities: list[str],
    admission: datetime,
    producer: str,
    now: datetime,
) -> None:
    digest = schedule["schedule_sha256"]
    persist_observation_schedule(
        data_root=observation_rdp,
        schedule=schedule,
        now=admission,
        producer_git_sha=producer,
        activation_id=None,
    )
    publish_observation_batch(
        data_root=observation_rdp,
        root=ROOT,
        schedule=schedule,
        activation_id=ACTIVATION,
        now=now,
        producer_git_sha=producer,
        members=[_prod_member(digest, entity, admission) for entity in entities],
        observations=[_obs(digest, entity, admission) for entity in entities],
    )


def _build_and_seal(
    *,
    observation_rdp: Path,
    ops: Path,
    digest: str,
    cohort_id: str,
    as_of: datetime,
    release_root: Path,
) -> dict:
    receipt = build_closure_receipt(
        ops_store=ops,
        observation_rdp=observation_rdp,
        schedule_sha256=digest,
        activation_id=ACTIVATION,
        cohort_id=cohort_id,
        as_of=as_of,
    )
    assert_closure_ready(receipt)
    source = build_live_observation_source_from_rdp(
        observation_rdp_root=observation_rdp,
        schedule_sha256=digest,
        activation_id=ACTIVATION,
        cohort_id=cohort_id,
        as_of=as_of,
        closure_receipt=receipt,
        discovery_coverage_class="EMPIRICAL_OVERLAP_ONLY",
        ops_store=ops,
    )
    assert_source_matches_receipt(source, receipt)
    return seal_live_cohort(
        observation_rdp_root=observation_rdp,
        cohort_id=cohort_id,
        release_root=release_root,
        sealed_at=as_of,
        as_of=as_of,
        release_builder_git_sha=PRODUCER_A,
    )


def _project_from_root(data_root: Path) -> dict:
    census = current_corpus_partition_rows(data_root, kind="census")
    observations = current_corpus_partition_rows(data_root, kind="observations")
    canonical = resolve_canonical_release_schedule(data_root, census)
    return project_scientific_eligibility(
        census,
        observations,
        canonical_schedule=canonical,
        require_canonical_schedule=True,
    )


def _cohort_parquet_hashes(data_root: Path, cohort_id: str) -> tuple[str, str]:
    lineage = load_live_corpus_lineage(data_root)
    row = next(
        item
        for item in lineage.get("cohorts") or []
        if str(item.get("cohort_id")) == cohort_id
    )
    census = Path(data_root) / str(row["census_rel"])
    obs = Path(data_root) / str(row["obs_rel"])
    return sha256_file_streaming(census), sha256_file_streaming(obs)


class SelfContainedLiveCohortReleaseTests(unittest.TestCase):
    def test_forward_self_contained_release_vertical(self) -> None:
        schedule = _schedule(ROOT)
        digest = schedule["schedule_sha256"]
        members = [_entity("A", i) for i in range(3)]
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            observation_rdp = base / "observation_rdp"
            observation_rdp.mkdir()
            ops = base / "ops.sqlite"
            release = base / "release"
            transport = base / "transport"
            data_root = base / "data_plane"
            data_root.mkdir()
            _seed_rdp(
                observation_rdp,
                schedule=schedule,
                entities=members,
                admission=C1_ADMIT,
                producer=PRODUCER_A,
                now=PUBLISH_C1,
            )
            _seed_ops(ops, digest=digest, cohort1=members, cohort2=[])
            manifest = _build_and_seal(
                observation_rdp=observation_rdp,
                ops=ops,
                digest=digest,
                cohort_id=COHORT1,
                as_of=AS_OF_C1,
                release_root=release,
            )
            self.assertEqual(manifest["schema_version"], RELEASE_SCHEMA_VERSION_SELF_CONTAINED)
            artifact = release / OBSERVATION_SCHEDULE_ARTIFACT_NAME
            self.assertTrue(artifact.is_file())
            document = decode_schedule_artifact(
                artifact.read_bytes(),
                wanted_sha=digest,
                expected_byte_sha256=manifest["observation_schedule_sha256"],
            )
            self.assertEqual(schedule_sha256(document), digest)
            verified = verify_live_cohort(release)
            self.assertEqual(verified["schedule_sha256"], digest)
            hashes = verify_transported_release(source_root=release, dest_root=transport)
            self.assertEqual(
                hashes[OBSERVATION_SCHEDULE_ARTIFACT_NAME],
                sha256_file_streaming(artifact),
            )
            imported = import_live_cohort(
                release_root=transport,
                data_root=data_root,
                import_time=AS_OF_C1 + timedelta(hours=1),
            )
            self.assertEqual(imported["status"], "IMPORTED")
            projection = _project_from_root(data_root)
            self.assertNotEqual(projection.get("outcome_readiness"), CANONICAL_SCHEDULE_UNBOUND)
            canonical = resolve_canonical_release_schedule(
                data_root,
                current_corpus_partition_rows(data_root, kind="census"),
            )
            self.assertEqual(schedule_sha256(canonical), digest)
            source_dir = observation_rdp / "live_observation_rebuild" / f"cohort={COHORT1}"
            self.assertTrue((source_dir / SOURCE_SCHEDULE_NAME).is_file())

    def test_tampered_schedule_artifact_fails_verify_and_transport(self) -> None:
        schedule = _schedule(ROOT)
        digest = schedule["schedule_sha256"]
        members = [_entity("A", i) for i in range(3)]
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            observation_rdp = base / "observation_rdp"
            observation_rdp.mkdir()
            ops = base / "ops.sqlite"
            release = base / "release"
            _seed_rdp(
                observation_rdp,
                schedule=schedule,
                entities=members,
                admission=C1_ADMIT,
                producer=PRODUCER_A,
                now=PUBLISH_C1,
            )
            _seed_ops(ops, digest=digest, cohort1=members, cohort2=[])
            _build_and_seal(
                observation_rdp=observation_rdp,
                ops=ops,
                digest=digest,
                cohort_id=COHORT1,
                as_of=AS_OF_C1,
                release_root=release,
            )
            artifact = release / OBSERVATION_SCHEDULE_ARTIFACT_NAME
            artifact.write_bytes(artifact.read_bytes() + b" ")
            with self.assertRaises(
                (LiveCohortReleaseError, DiscoveryReleaseError)
            ) as verify_exc:
                verify_live_cohort(release)
            self.assertIn(
                str(verify_exc.exception),
                {
                    SCHEDULE_ARTIFACT_HASH_MISMATCH,
                    SCHEDULE_PARSER_INVALID,
                    SCHEDULE_SEMANTIC_SHA_MISMATCH,
                },
            )
            dest = base / "transport"
            with self.assertRaises(
                (LiveCohortReleaseError, LiveCohortToForgeError, DiscoveryReleaseError)
            ) as transport_exc:
                verify_transported_release(source_root=release, dest_root=dest)
            self.assertTrue(str(transport_exc.exception))

    def test_semantic_mismatch_fails_closed(self) -> None:
        schedule = _schedule(ROOT)
        other = _alt_schedule(schedule)
        digest = schedule["schedule_sha256"]
        members = [_entity("A", i) for i in range(3)]
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            observation_rdp = base / "observation_rdp"
            observation_rdp.mkdir()
            ops = base / "ops.sqlite"
            release = base / "release"
            _seed_rdp(
                observation_rdp,
                schedule=schedule,
                entities=members,
                admission=C1_ADMIT,
                producer=PRODUCER_A,
                now=PUBLISH_C1,
            )
            _seed_ops(ops, digest=digest, cohort1=members, cohort2=[])
            _build_and_seal(
                observation_rdp=observation_rdp,
                ops=ops,
                digest=digest,
                cohort_id=COHORT1,
                as_of=AS_OF_C1,
                release_root=release,
            )
            _other_doc, payload, byte_sha = encode_schedule_artifact(
                other, wanted_sha=other["schedule_sha256"]
            )
            (release / OBSERVATION_SCHEDULE_ARTIFACT_NAME).write_bytes(payload)
            manifest_path = release / "release_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["observation_schedule_sha256"] = byte_sha
            manifest_path.write_text(
                json.dumps(manifest, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            inventory_path = release / "source_inventory.json"
            inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
            inventory["observation_schedule_sha256"] = byte_sha
            inventory_path.write_text(
                json.dumps(inventory, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            with self.assertRaises((LiveCohortReleaseError, DiscoveryReleaseError)) as exc:
                verify_live_cohort(release)
            self.assertEqual(str(exc.exception), SCHEDULE_SEMANTIC_SHA_MISMATCH)

    def test_missing_artifact_on_new_schema_fails_closed(self) -> None:
        schedule = _schedule(ROOT)
        digest = schedule["schedule_sha256"]
        members = [_entity("A", i) for i in range(3)]
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            observation_rdp = base / "observation_rdp"
            observation_rdp.mkdir()
            ops = base / "ops.sqlite"
            release = base / "release"
            _seed_rdp(
                observation_rdp,
                schedule=schedule,
                entities=members,
                admission=C1_ADMIT,
                producer=PRODUCER_A,
                now=PUBLISH_C1,
            )
            _seed_ops(ops, digest=digest, cohort1=members, cohort2=[])
            _build_and_seal(
                observation_rdp=observation_rdp,
                ops=ops,
                digest=digest,
                cohort_id=COHORT1,
                as_of=AS_OF_C1,
                release_root=release,
            )
            (release / OBSERVATION_SCHEDULE_ARTIFACT_NAME).unlink()
            with self.assertRaises((LiveCohortReleaseError, DiscoveryReleaseError)) as exc:
                verify_live_cohort(release)
            self.assertEqual(str(exc.exception), SCHEDULE_ARTIFACT_MISSING)
            with self.assertRaises(LiveCohortToForgeError) as tree:
                hash_release_tree(release)
            self.assertEqual(str(tree.exception), SCHEDULE_ARTIFACT_MISSING)

    def test_idempotent_import_same_schedule(self) -> None:
        schedule = _schedule(ROOT)
        digest = schedule["schedule_sha256"]
        members = [_entity("A", i) for i in range(3)]
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            observation_rdp = base / "observation_rdp"
            observation_rdp.mkdir()
            ops = base / "ops.sqlite"
            release = base / "release"
            data_root = base / "data_plane"
            data_root.mkdir()
            _seed_rdp(
                observation_rdp,
                schedule=schedule,
                entities=members,
                admission=C1_ADMIT,
                producer=PRODUCER_A,
                now=PUBLISH_C1,
            )
            _seed_ops(ops, digest=digest, cohort1=members, cohort2=[])
            _build_and_seal(
                observation_rdp=observation_rdp,
                ops=ops,
                digest=digest,
                cohort_id=COHORT1,
                as_of=AS_OF_C1,
                release_root=release,
            )
            first = import_live_cohort(
                release_root=release,
                data_root=data_root,
                import_time=AS_OF_C1 + timedelta(hours=1),
            )
            second = import_live_cohort(
                release_root=release,
                data_root=data_root,
                import_time=AS_OF_C1 + timedelta(hours=2),
            )
            self.assertEqual(first["status"], "IMPORTED")
            self.assertEqual(second["status"], "IDEMPOTENT_REIMPORT")
            canonical = resolve_canonical_release_schedule(
                data_root,
                current_corpus_partition_rows(data_root, kind="census"),
            )
            self.assertEqual(schedule_sha256(canonical), digest)

    def test_shared_schedule_later_cohort_binds_earlier_without_rewrite(self) -> None:
        schedule = _schedule(ROOT)
        digest = schedule["schedule_sha256"]
        cohort_a = [_entity("A", i) for i in range(3)]
        cohort_b = [_entity("C", i) for i in range(3)]
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            data_root = base / "data_plane"
            data_root.mkdir()
            legacy_rdp = base / "legacy_rdp"
            legacy_release = base / "legacy_release"
            snap = {
                "schedule_sha256": digest,
                "activation_id": ACTIVATION,
                "producer_git_sha": PRODUCER_A,
                "starts_at": "2026-09-02T11:19:00Z",
                "stops_admitting_at": "2026-09-23T11:19:00Z",
                "discovery_coverage_class": "EMPIRICAL_OVERLAP_ONLY",
                "open_publication": False,
                "unresolved_due": False,
                "in_flight": False,
                "budget_blocked": False,
                "closure_receipt_sha256": "c" * 64,
                "members": [
                    {
                        "mint": entity,
                        "discovery_first_reliable_available_at": C1_ADMIT.strftime(
                            "%Y-%m-%dT%H:%M:%SZ"
                        ),
                        "authoritative_anchor": C1_ADMIT.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "candidate_state": "ADMITTED",
                        "membership_state": "OBSERVED",
                        "denominator_state": "observed",
                        "sampling_policy": "DETERMINISTIC_HASH_BERNOULLI",
                        "sampling_seed": "ALWAYS-ON-LIFECYCLE-COLLECTOR-V1",
                        "inclusion_probability": "0.0425",
                        "selected_or_excluded": "SELECTED",
                        "exclusion_reason": None,
                    }
                    for entity in cohort_a
                ],
                "observations": [
                    {
                        "mint": entity,
                        "point_id": "X300",
                        "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                        "field_id": "FIELD-LIQUIDITY-USD-001",
                        "value_kind": "DECIMAL",
                        "typed_value": "1.0",
                        "state": "OBSERVED",
                        "missing_reason": None,
                        "event_time": C1_ADMIT.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "request_started_at": C1_ADMIT.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "response_received_at": C1_ADMIT.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "first_reliable_available_at": (
                            C1_ADMIT + timedelta(seconds=1)
                        ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "request_sha256": "e" * 64,
                        "response_sha256": "f" * 64,
                        "call_occurrence_id": "1" * 64,
                        "http_status": 200,
                        "http_class": "OK",
                    }
                    for entity in cohort_a
                ],
            }
            write_observation_rdp_source(legacy_rdp, snap)
            sealed_a = seal_live_cohort(
                observation_rdp_root=legacy_rdp,
                cohort_id=COHORT1,
                release_root=legacy_release,
                sealed_at=AS_OF_C1,
                as_of=AS_OF_C1,
            )
            self.assertEqual(sealed_a["schema_version"], RELEASE_SCHEMA_VERSION_LEGACY)
            self.assertFalse((legacy_release / OBSERVATION_SCHEDULE_ARTIFACT_NAME).exists())
            import_live_cohort(
                release_root=legacy_release,
                data_root=data_root,
                import_time=AS_OF_C1 + timedelta(hours=1),
            )
            hashes_before = _cohort_parquet_hashes(data_root, COHORT1)
            census_a = [
                row
                for row in current_corpus_partition_rows(data_root, kind="census")
                if str(row.get("cohort_id")) == COHORT1
            ]
            with self.assertRaises(ScientificEligibilityError) as unbound:
                resolve_canonical_release_schedule(data_root, census_a)
            self.assertEqual(unbound.exception.code, CANONICAL_SCHEDULE_UNBOUND)

            later_rdp = base / "later_rdp"
            later_rdp.mkdir()
            later_ops = base / "later_ops.sqlite"
            later_release = base / "later_release"
            _seed_rdp(
                later_rdp,
                schedule=schedule,
                entities=cohort_b,
                admission=C2_ADMIT,
                producer=PRODUCER_C,
                now=PUBLISH_C2,
            )
            _seed_ops(
                later_ops,
                digest=digest,
                cohort1=cohort_b,
                cohort2=[],
                cohort1_admissions={entity: C2_ADMIT for entity in cohort_b},
            )
            _build_and_seal(
                observation_rdp=later_rdp,
                ops=later_ops,
                digest=digest,
                cohort_id=COHORT2,
                as_of=AS_OF_C2,
                release_root=later_release,
            )
            import_live_cohort(
                release_root=later_release,
                data_root=data_root,
                import_time=AS_OF_C2 + timedelta(hours=1),
            )
            hashes_after = _cohort_parquet_hashes(data_root, COHORT1)
            self.assertEqual(hashes_before, hashes_after)
            census_all = current_corpus_partition_rows(data_root, kind="census")
            shared = resolve_canonical_release_schedule(data_root, census_all)
            self.assertEqual(schedule_sha256(shared), digest)
            for cohort_id in (COHORT1, COHORT2):
                rows = [row for row in census_all if str(row.get("cohort_id")) == cohort_id]
                bound = resolve_canonical_release_schedule(data_root, rows)
                self.assertEqual(schedule_sha256(bound), digest)

    def test_different_schedule_does_not_satisfy_other_cohort(self) -> None:
        schedule = _schedule(ROOT)
        other = _alt_schedule(schedule)
        digest = schedule["schedule_sha256"]
        other_digest = other["schedule_sha256"]
        self.assertNotEqual(digest, other_digest)
        cohort_a = [_entity("A", i) for i in range(3)]
        cohort_b = [_entity("C", i) for i in range(3)]
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            data_root = base / "data_plane"
            data_root.mkdir()
            legacy_rdp = base / "legacy_rdp"
            legacy_release = base / "legacy_release"
            snap = {
                "schedule_sha256": digest,
                "activation_id": ACTIVATION,
                "producer_git_sha": PRODUCER_A,
                "starts_at": "2026-09-02T11:19:00Z",
                "stops_admitting_at": "2026-09-23T11:19:00Z",
                "discovery_coverage_class": "EMPIRICAL_OVERLAP_ONLY",
                "open_publication": False,
                "unresolved_due": False,
                "in_flight": False,
                "budget_blocked": False,
                "closure_receipt_sha256": "c" * 64,
                "members": [
                    {
                        "mint": entity,
                        "discovery_first_reliable_available_at": C1_ADMIT.strftime(
                            "%Y-%m-%dT%H:%M:%SZ"
                        ),
                        "authoritative_anchor": C1_ADMIT.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "candidate_state": "ADMITTED",
                        "membership_state": "OBSERVED",
                        "denominator_state": "observed",
                        "sampling_policy": "DETERMINISTIC_HASH_BERNOULLI",
                        "sampling_seed": "ALWAYS-ON-LIFECYCLE-COLLECTOR-V1",
                        "inclusion_probability": "0.0425",
                        "selected_or_excluded": "SELECTED",
                        "exclusion_reason": None,
                    }
                    for entity in cohort_a
                ],
                "observations": [],
            }
            write_observation_rdp_source(legacy_rdp, snap)
            seal_live_cohort(
                observation_rdp_root=legacy_rdp,
                cohort_id=COHORT1,
                release_root=legacy_release,
                sealed_at=AS_OF_C1,
                as_of=AS_OF_C1,
            )
            import_live_cohort(
                release_root=legacy_release,
                data_root=data_root,
                import_time=AS_OF_C1 + timedelta(hours=1),
            )
            later_rdp = base / "later_rdp"
            later_rdp.mkdir()
            later_ops = base / "later_ops.sqlite"
            later_release = base / "later_release"
            _seed_rdp(
                later_rdp,
                schedule=other,
                entities=cohort_b,
                admission=C2_ADMIT,
                producer=PRODUCER_C,
                now=PUBLISH_C2,
            )
            _seed_ops(
                later_ops,
                digest=other_digest,
                cohort1=cohort_b,
                cohort2=[],
                cohort1_admissions={entity: C2_ADMIT for entity in cohort_b},
            )
            receipt = build_closure_receipt(
                ops_store=later_ops,
                observation_rdp=later_rdp,
                schedule_sha256=other_digest,
                activation_id=ACTIVATION,
                cohort_id=COHORT2,
                as_of=AS_OF_C2,
            )
            assert_closure_ready(receipt)
            source = build_live_observation_source_from_rdp(
                observation_rdp_root=later_rdp,
                schedule_sha256=other_digest,
                activation_id=ACTIVATION,
                cohort_id=COHORT2,
                as_of=AS_OF_C2,
                closure_receipt=receipt,
                discovery_coverage_class="EMPIRICAL_OVERLAP_ONLY",
            )
            assert_source_matches_receipt(source, receipt)
            seal_live_cohort(
                observation_rdp_root=later_rdp,
                cohort_id=COHORT2,
                release_root=later_release,
                sealed_at=AS_OF_C2,
                as_of=AS_OF_C2,
                release_builder_git_sha=PRODUCER_C,
            )
            import_live_cohort(
                release_root=later_release,
                data_root=data_root,
                import_time=AS_OF_C2 + timedelta(hours=1),
            )
            census_a = [
                row
                for row in current_corpus_partition_rows(data_root, kind="census")
                if str(row.get("cohort_id")) == COHORT1
            ]
            with self.assertRaises(ScientificEligibilityError) as unbound:
                resolve_canonical_release_schedule(data_root, census_a)
            self.assertEqual(unbound.exception.code, CANONICAL_SCHEDULE_UNBOUND)
            census_b = [
                row
                for row in current_corpus_partition_rows(data_root, kind="census")
                if str(row.get("cohort_id")) == COHORT2
            ]
            bound_b = resolve_canonical_release_schedule(data_root, census_b)
            self.assertEqual(schedule_sha256(bound_b), other_digest)

    def test_legacy_release_without_artifact_stays_unbound(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            obs_rdp = base / "obs"
            release = base / "rel"
            data_root = base / "rdp"
            data_root.mkdir()
            snap = _snapshot_for_week(0)
            write_observation_rdp_source(obs_rdp, snap)
            cohort = cohort_id_for_admission(
                datetime(2026, 1, 5, 12, tzinfo=UTC),
                starts_at=CAMPAIGN_STARTS,
                stops_admitting_at=CAMPAIGN_STOPS,
            )
            assert cohort is not None
            as_of = datetime(2026, 1, 20, tzinfo=UTC)
            sealed = seal_live_cohort(
                observation_rdp_root=obs_rdp,
                cohort_id=cohort,
                release_root=release,
                sealed_at=as_of,
                as_of=as_of,
            )
            self.assertEqual(sealed["schema_version"], RELEASE_SCHEMA_VERSION_LEGACY)
            self.assertNotIn("observation_schedule_sha256", sealed)
            self.assertFalse((release / OBSERVATION_SCHEDULE_ARTIFACT_NAME).exists())
            verified = verify_live_cohort(release)
            self.assertEqual(verified["schema_version"], RELEASE_SCHEMA_VERSION_LEGACY)
            import_live_cohort(
                release_root=release,
                data_root=data_root,
                import_time=as_of + timedelta(hours=1),
            )
            census = current_corpus_partition_rows(data_root, kind="census")
            with self.assertRaises(ScientificEligibilityError) as unbound:
                resolve_canonical_release_schedule(data_root, census)
            self.assertEqual(unbound.exception.code, CANONICAL_SCHEDULE_UNBOUND)
            hashes = hash_release_tree(release)
            self.assertNotIn(OBSERVATION_SCHEDULE_ARTIFACT_NAME, hashes)

    def test_operator_flow_has_no_schedule_specific_command(self) -> None:
        cli_text = (ROOT / "scripts" / "discovery_evidence_release.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("bind-schedule", cli_text)
        self.assertNotIn("attach-schedule", cli_text)
        self.assertNotIn("--schedule-document", cli_text)
        docs = (ROOT / "docs" / "operator" / "FACTORY_LIFECYCLE_COLLECTOR.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("observation_schedule.json", docs)
        self.assertIn("no separate bind-schedule", docs.lower())
        _cli_module()


if __name__ == "__main__":
    unittest.main()
