from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.data_root import (  # noqa: E402
    DataRootError,
    resolve_active_data_root,
)
from solana_alpha_lab.factory.commissioning_fixture import (  # noqa: E402
    COMMISSIONING_DATASET_MANIFEST_ID,
)
from solana_alpha_lab.factory.commissioning_proof import (  # noqa: E402
    CommissioningProofError,
    apply_legacy_commissioning_hypothesis_link,
    verify_commissioning_passport,
)
from solana_alpha_lab.factory.hfic_clock import FrozenClock  # noqa: E402
from solana_alpha_lab.factory.hfic_preflight import (  # noqa: E402
    HficPreflightError,
    build_offline_commission_packet,
    enumerate_rdp_datasets,
    prove_fast_lane_commissioned,
    run_preflight,
)
from solana_alpha_lab.factory.research_store import (  # noqa: E402
    RecordKind,
    ResearchEvent,
    ResearchStore,
)


class DataRootResolverTests(unittest.TestCase):
    def test_single_commissioned_candidate_is_selected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            default_root = repo / "local/factory_v1/data_plane"
            env_root = Path(tmp) / "env_root"
            default_root.mkdir(parents=True)
            env_root.mkdir(parents=True)
            resolved = resolve_active_data_root(
                repo,
                env={"SMIAL_DATA_ROOT": str(env_root)},
                is_commissioned=lambda path: path == env_root,
            )
            self.assertEqual(resolved.root, env_root.resolve())
            self.assertEqual(resolved.selection_reason, "SINGLE_COMMISSIONED")
            self.assertNotIn(str(env_root), json.dumps(resolved.redacted_receipt()))

    def test_none_commissioned_prefers_valid_env_then_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            default_root = repo / "local/factory_v1/data_plane"
            env_root = Path(tmp) / "env_root"
            default_root.mkdir(parents=True)
            env_root.mkdir(parents=True)
            resolved = resolve_active_data_root(
                repo,
                env={"SMIAL_DATA_ROOT": str(env_root)},
                is_commissioned=lambda _path: False,
            )
            self.assertEqual(resolved.root, env_root.resolve())
            self.assertEqual(resolved.selection_reason, "ENV_UNCOMMISSIONED")

    def test_divergent_commissioned_roots_are_split_brain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            default_root = repo / "local/factory_v1/data_plane"
            env_root = Path(tmp) / "env_root"
            default_root.mkdir(parents=True)
            env_root.mkdir(parents=True)
            with self.assertRaises(DataRootError) as raised:
                resolve_active_data_root(
                    repo,
                    env={"SMIAL_DATA_ROOT": str(env_root)},
                    is_commissioned=lambda _path: True,
                    inventory_digest=lambda path: f"digest-{path.name}",
                )
            self.assertEqual(str(raised.exception), "DATA_ROOT_SPLIT_BRAIN")

    def test_identical_commissioned_roots_do_not_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            default_root = repo / "local/factory_v1/data_plane"
            env_root = Path(tmp) / "env_root"
            default_root.mkdir(parents=True)
            env_root.mkdir(parents=True)
            resolved = resolve_active_data_root(
                repo,
                env={"SMIAL_DATA_ROOT": str(env_root)},
                is_commissioned=lambda _path: True,
                inventory_digest=lambda _path: "same-digest",
            )
            self.assertEqual(resolved.root, env_root.resolve())
            self.assertEqual(resolved.selection_reason, "IDENTICAL_COMMISSIONED")
            self.assertTrue(resolved.duplicate_receipt)

    def test_symlink_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            real = Path(tmp) / "real"
            real.mkdir()
            link = Path(tmp) / "link"
            try:
                os.symlink(real, link, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlink unavailable")
            with self.assertRaises(DataRootError) as raised:
                resolve_active_data_root(
                    repo,
                    explicit_data_root=link,
                    is_commissioned=lambda _path: False,
                )
            self.assertEqual(str(raised.exception), "DATA_ROOT_INVALID")


class CommissioningProofTests(unittest.TestCase):
    def test_empty_directory_is_not_commissioned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(HficPreflightError) as raised:
                prove_fast_lane_commissioned(Path(tmp))
            self.assertEqual(str(raised.exception), "FAST_LANE_NOT_COMMISSIONED")

    def test_unrelated_store_records_do_not_prove_commissioning(self) -> None:
        from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent, ResearchStore

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            git_head = "0" * 40
            now = __import__("datetime").datetime(1970, 1, 1, tzinfo=__import__("datetime").UTC)
            payload = {
                "hypothesis_version_id": "HYP-UNRELATED-001",
                "statement": "noise",
            }
            encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            store.append(
                [
                    ResearchEvent(
                        record_id="HYP-UNRELATED-001",
                        record_kind=RecordKind.HYPOTHESIS_VERSION,
                        entity_id="HYP-UNRELATED-001",
                        hypothesis_version_id="HYP-UNRELATED-001",
                        run_id=None,
                        transaction_id="RESEARCH-TXN-NOISE-001",
                        effective_at=now,
                        first_reliable_available_at=now,
                        supersedes_record_id=None,
                        payload_json=encoded,
                        payload_sha256=__import__("hashlib").sha256(encoded.encode()).hexdigest(),
                        schema_version="1.0",
                        producer_capability_id="CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
                        producer_git_sha=git_head,
                        created_at=now,
                    )
                ],
                transaction_id="RESEARCH-TXN-NOISE-001",
            )
            with self.assertRaises(HficPreflightError) as raised:
                prove_fast_lane_commissioned(Path(tmp))
            self.assertEqual(str(raised.exception), "FAST_LANE_NOT_COMMISSIONED")

    def test_passport_git_mutation_is_rejected(self) -> None:
        from solana_alpha_lab.factory.commissioning_proof import (
            CommissioningProofError,
            verify_commissioning_passport,
        )

        with self.assertRaises(CommissioningProofError) as raised:
            verify_commissioning_passport({"git_mutation_count": 1, "provider_calls_actual": 0})
        self.assertEqual(str(raised.exception), "COMMISSION_GIT_MUTATION")

    def test_missing_git_mutation_count_is_rejected(self) -> None:
        from solana_alpha_lab.factory.commissioning_proof import (
            CommissioningProofError,
            verify_commissioning_passport,
        )

        passport = {
            "provider_calls_actual": 0,
            "run_id": "RUN-FAST-LANE-COMMISSIONING-FIXTURE-001",
        }
        with self.assertRaises(CommissioningProofError) as raised:
            verify_commissioning_passport(passport)
        self.assertEqual(str(raised.exception), "COMMISSION_GIT_MUTATION_COUNT_MISSING")

    def test_owner_json_never_contains_physical_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            default_root = repo / "local/factory_v1/data_plane"
            default_root.mkdir(parents=True)
            resolved = resolve_active_data_root(
                repo,
                env={},
                is_commissioned=lambda _path: False,
            )
            rendered = json.dumps(resolved.redacted_receipt(), sort_keys=True)
            self.assertNotIn(str(default_root), rendered)
            self.assertNotIn(":\\", rendered)
            self.assertNotIn("SMIAL_DATA_ROOT", rendered)


class ObservationScheduleInventoryRepairTests(unittest.TestCase):
    def test_sidecars_are_ignored_and_canonical_corrupt_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifests = Path(tmp) / "datasets" / "manifests"
            manifests.mkdir(parents=True)
            (manifests / "DATASET-MANIFEST-EARLY-ICP-FIRST-HIT-MIX-FALSIFIER-001.decision.json").write_text(
                "{not-json",
                encoding="utf-8",
            )
            (manifests / "DATASET-MANIFEST-EARLY-ICP-FIRST-HIT-MIX-FALSIFIER-001.labels.json").write_text(
                "{not-json",
                encoding="utf-8",
            )
            canonical = manifests / ("dataset-" + ("a" * 64) + ".json")
            canonical.write_text("{not-json", encoding="utf-8")
            stable = manifests / "DATASET-MANIFEST-EARLY-ICP-FIRST-HIT-MIX-FALSIFIER-001.json"
            stable.write_text("{not-json", encoding="utf-8")
            entries, warnings = enumerate_rdp_datasets(Path(tmp))
            self.assertEqual(entries, [])
            codes = [item["code"] for item in warnings]
            self.assertIn("DATASET_MANIFEST_CORRUPT", codes)
            self.assertEqual(codes.count("DATASET_MANIFEST_CORRUPT"), 1)
            self.assertEqual(
                [item["dataset_manifest_id"] for item in warnings if item["code"] == "DATASET_MANIFEST_CORRUPT"],
                [canonical.stem],
            )


GOLDEN_HYPOTHESIS_VERSION_ID = "HYP-QUOTE-NATIVE-FRICTION-H900-V1"
_COMPAT_PREFIX = "HYPOTHESIS-VERSION-COMPAT-"
_CLOCK = FrozenClock(datetime(2026, 8, 29, 20, 0, 0, tzinfo=UTC))


def _git_snapshot() -> dict[str, str]:
    from solana_alpha_lab.factory.document_runner import repository_git_snapshot

    snap = repository_git_snapshot(ROOT)
    return {"head_sha": snap.head_sha, "composite_sha256": snap.composite_sha256}


def _commission(data_root: Path) -> None:
    path = ROOT / "scripts/hypothesis_fast_lane.py"
    spec = importlib.util.spec_from_file_location(
        "hfic_compat_fast_lane_helper",
        path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("FAST_LANE_NOT_COMMISSIONABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    packet = build_offline_commission_packet(ROOT)
    packet_path = data_root / "offline_commission.json"
    packet_path.write_text(json.dumps(packet), encoding="utf-8")
    module.execute_commission_offline(ROOT, data_root, packet_path)


def _compat_records(store: ResearchStore) -> list[ResearchEvent]:
    return [
        record
        for record in store.iter_committed_records()
        if str(record.record_id).startswith(_COMPAT_PREFIX)
    ]


def _hypothesis_records(store: ResearchStore) -> list[ResearchEvent]:
    return [
        record
        for record in store.iter_committed_records()
        if str(getattr(record.record_kind, "value", record.record_kind))
        == RecordKind.HYPOTHESIS_VERSION.value
    ]


def _seed_unbound_hypothesis(
    store: ResearchStore,
    *,
    hypothesis_version_id: str = GOLDEN_HYPOTHESIS_VERSION_ID,
    statement: str = "preseeded commissioning hypothesis",
    record_id: str = "HYPOTHESIS-VERSION-PRESEED-001",
    transaction_id: str = "RESEARCH-TXN-PRESEED-001",
) -> None:
    payload = {
        "hypothesis_version_id": hypothesis_version_id,
        "family_id": "HYP-FAMILY-FAST-LANE-001",
        "version_ordinal": 1,
        "origin_id": "HYP-ORIGIN-FAST-LANE-001",
        "origin_kind": "DATA_ANALYSIS",
        "research_cycle_id": "RESEARCH-CYCLE-FAST-LANE-001",
        "definition_sha256": "1" * 64,
        "statement": statement,
        "mechanism": "preseed",
        "falsifier": "preseed",
        "expected_regime_terms": [],
        "what_changed": "PRESEED_UNBOUND_HYPOTHESIS",
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    now = datetime(2026, 8, 25, 12, 0, 0, tzinfo=UTC)
    store.append(
        [
            ResearchEvent(
                record_id=record_id,
                record_kind=RecordKind.HYPOTHESIS_VERSION,
                entity_id=hypothesis_version_id,
                hypothesis_version_id=hypothesis_version_id,
                run_id=None,
                transaction_id=transaction_id,
                effective_at=now,
                first_reliable_available_at=now,
                supersedes_record_id=None,
                payload_json=encoded,
                payload_sha256=hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
                schema_version="1.0",
                producer_capability_id="CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
                producer_git_sha="a" * 40,
                created_at=now,
            )
        ],
        transaction_id=transaction_id,
    )


def _commission_allow_search_gap(data_root: Path) -> None:
    try:
        _commission(data_root)
    except Exception as exc:
        if str(exc) != "COMMISSION_SEARCH_FAILED":
            raise


def _legacy_missing_link_store(data_root: Path) -> ResearchStore:
    store = ResearchStore(data_root)
    _seed_unbound_hypothesis(store)
    _commission_allow_search_gap(data_root)
    return ResearchStore(data_root)


def _schema_required_passport() -> dict[str, object]:
    return {
        "run_id": "RUN-FAST-LANE-COMMISSIONING-FIXTURE-001",
        "run_key_sha256": "2" * 64,
        "trial_id": "TRIAL-FAST-LANE-COMMISSIONING-FIXTURE-001",
        "hypothesis_version_id": GOLDEN_HYPOTHESIS_VERSION_ID,
        "hypothesis_definition_sha256": "1" * 64,
        "experiment_spec_sha256": "2" * 64,
        "runner_capability_id": "CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
        "runner_git_sha": "b" * 40,
        "capability_closure_sha256": "3" * 64,
        "uv_lock_sha256": "4" * 64,
        "dataset_manifest_ids": [COMMISSIONING_DATASET_MANIFEST_ID],
        "dataset_fingerprints": ["5" * 64],
        "query_recipe_ids": ["QUERY-RECIPE-001"],
        "query_recipe_sha256s": ["6" * 64],
        "config_sha256": "7" * 64,
        "as_of": "2026-08-25T11:00:00Z",
        "availability_cutoff": "2026-08-25T11:00:00Z",
        "holdout_consumption_ids": [],
        "random_seed_or_null": 17,
        "started_at": "2026-08-25T11:30:00Z",
        "completed_at": "2026-08-25T12:00:00Z",
        "first_reliable_available_at": "2026-08-25T12:00:00Z",
        "provider_calls_planned": 0,
        "provider_calls_actual": 0,
        "cash_spend_usd_cents": 0,
        "execution_status": "COMPLETE",
        "trial_outcome": "POSITIVE",
        "scientific_terminal": "RETAINED",
        "result_digest_sha256": "8" * 64,
        "artifact_manifest_sha256": "9" * 64,
        "limitations": [],
        "non_claims": [],
        "git_mutation_count": 0,
    }


class LegacyCommissioningCompatibilityTests(unittest.TestCase):
    def test_optional_observation_passport_keys_are_not_required(self) -> None:
        from solana_alpha_lab.factory.commissioning_proof import (
            RUN_PASSPORT_REQUIRED_FIELDS,
        )

        payload = verify_commissioning_passport(_schema_required_passport())
        self.assertEqual(payload["run_id"], "RUN-FAST-LANE-COMMISSIONING-FIXTURE-001")
        self.assertNotIn("observation_schedule_sha256", RUN_PASSPORT_REQUIRED_FIELDS)
        self.assertNotIn("observation_schedule_authority_sha256", RUN_PASSPORT_REQUIRED_FIELDS)
        self.assertNotIn("observation_panel_snapshot_sha256", RUN_PASSPORT_REQUIRED_FIELDS)

    def test_legacy_missing_link_preflight_repairs_without_owner_step(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _legacy_missing_link_store(data_root)
            with self.assertRaises(HficPreflightError) as raised:
                prove_fast_lane_commissioned(data_root)
            self.assertEqual(
                str(raised.exception),
                "COMMISSION_HYPOTHESIS_VERSION_MISSING",
            )
            commission_calls = {"count": 0}

            def _boom(_repo: Path, _root: Path) -> None:
                commission_calls["count"] += 1
                raise AssertionError("auto-commission must not run for missing-link repair")

            receipt = run_preflight(
                ROOT,
                data_root,
                owner_focus="AUTO",
                auto_commission=True,
                commission_fn=_boom,
                git_snapshot=_git_snapshot(),
                clock=_CLOCK,
            )
            self.assertEqual(commission_calls["count"], 0)
            self.assertEqual(receipt["action"], "START_NEW_SESSION")
            self.assertEqual(
                receipt["commissioning"]["status"],
                "NO_GIT_FAST_LANE_PROVEN",
            )
            self.assertFalse(receipt["commissioning"]["auto_commissioned"])
            self.assertEqual(
                receipt["commissioning"]["compatibility_repair"]["status"],
                "APPLIED",
            )
            self.assertEqual(
                receipt["commissioning"]["compatibility_repair"]["appended"],
                1,
            )
            self.assertEqual(len(_compat_records(ResearchStore(data_root))), 1)
            prove_fast_lane_commissioned(data_root)

    def test_legacy_repair_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _legacy_missing_link_store(data_root)
            first = run_preflight(
                ROOT,
                data_root,
                owner_focus="AUTO",
                auto_commission=True,
                commission_fn=lambda _repo, _root: (_ for _ in ()).throw(
                    AssertionError("no commission")
                ),
                git_snapshot=_git_snapshot(),
                clock=_CLOCK,
            )
            hyp_after_first = len(_hypothesis_records(ResearchStore(data_root)))
            compat_after_first = len(_compat_records(ResearchStore(data_root)))
            second = run_preflight(
                ROOT,
                data_root,
                owner_focus="AUTO",
                auto_commission=True,
                commission_fn=lambda _repo, _root: (_ for _ in ()).throw(
                    AssertionError("no commission")
                ),
                git_snapshot=_git_snapshot(),
                clock=_CLOCK,
            )
            self.assertEqual(first["commissioning"]["compatibility_repair"]["appended"], 1)
            self.assertEqual(second["commissioning"]["compatibility_repair"]["status"], "NONE")
            self.assertEqual(second["commissioning"]["compatibility_repair"]["appended"], 0)
            self.assertEqual(
                second["commissioning"]["status"],
                "NO_GIT_FAST_LANE_PROVEN",
            )
            self.assertEqual(
                len(_compat_records(ResearchStore(data_root))),
                compat_after_first,
            )
            self.assertEqual(
                len(_hypothesis_records(ResearchStore(data_root))),
                hyp_after_first,
            )

    def test_already_current_store_has_no_compatibility_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _commission(data_root)
            before = len(_hypothesis_records(ResearchStore(data_root)))
            receipt = run_preflight(
                ROOT,
                data_root,
                owner_focus="AUTO",
                auto_commission=True,
                commission_fn=lambda _repo, _root: (_ for _ in ()).throw(
                    AssertionError("already commissioned")
                ),
                git_snapshot=_git_snapshot(),
                clock=_CLOCK,
            )
            self.assertEqual(
                receipt["commissioning"]["status"],
                "NO_GIT_FAST_LANE_PROVEN",
            )
            self.assertEqual(receipt["commissioning"]["compatibility_repair"]["status"], "NONE")
            self.assertEqual(receipt["commissioning"]["compatibility_repair"]["appended"], 0)
            self.assertEqual(len(_compat_records(ResearchStore(data_root))), 0)
            self.assertEqual(len(_hypothesis_records(ResearchStore(data_root))), before)

    def test_ambiguous_payloads_fail_closed_without_invented_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            store = ResearchStore(data_root)
            _seed_unbound_hypothesis(store, statement="payload-a")
            _commission_allow_search_gap(data_root)
            _seed_unbound_hypothesis(
                ResearchStore(data_root),
                statement="payload-b",
                record_id="HYPOTHESIS-VERSION-PRESEED-002",
                transaction_id="RESEARCH-TXN-PRESEED-002",
            )
            before_ids = {
                record.record_id for record in ResearchStore(data_root).iter_committed_records()
            }
            with self.assertRaises(CommissioningProofError) as raised:
                apply_legacy_commissioning_hypothesis_link(
                    data_root,
                    now=datetime(2026, 8, 29, 20, 0, 0, tzinfo=UTC),
                )
            self.assertEqual(str(raised.exception), "REAL_DATA_MIGRATION_AMBIGUOUS")
            after_ids = {
                record.record_id for record in ResearchStore(data_root).iter_committed_records()
            }
            self.assertEqual(after_ids, before_ids)
            self.assertEqual(len(_compat_records(ResearchStore(data_root))), 0)
            with self.assertRaises(HficPreflightError) as preflight_raised:
                run_preflight(
                    ROOT,
                    data_root,
                    owner_focus="AUTO",
                    auto_commission=True,
                    commission_fn=lambda _repo, _root: (_ for _ in ()).throw(
                        AssertionError("ambiguous store must not auto-commission")
                    ),
                    git_snapshot=_git_snapshot(),
                    clock=_CLOCK,
                )
            self.assertEqual(
                str(preflight_raised.exception),
                "REAL_DATA_MIGRATION_AMBIGUOUS",
            )
            self.assertEqual(
                {record.record_id for record in ResearchStore(data_root).iter_committed_records()},
                before_ids,
            )

    def test_supersede_mixed_hashes_fail_closed_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _legacy_missing_link_store(data_root)
            source = [
                record
                for record in ResearchStore(data_root).iter_committed_records()
                if record.record_id == "HYPOTHESIS-VERSION-PRESEED-001"
            ][0]
            payload = json.loads(source.payload_json)
            payload["statement"] = "superseded-current-payload"
            body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            now = datetime(2026, 8, 25, 13, 0, 0, tzinfo=UTC)
            ResearchStore(data_root).append(
                [
                    ResearchEvent(
                        record_id="HYPOTHESIS-VERSION-PRESEED-002",
                        record_kind=RecordKind.HYPOTHESIS_VERSION,
                        entity_id=GOLDEN_HYPOTHESIS_VERSION_ID,
                        hypothesis_version_id=GOLDEN_HYPOTHESIS_VERSION_ID,
                        run_id=None,
                        transaction_id="RESEARCH-TXN-PRESEED-002",
                        effective_at=now,
                        first_reliable_available_at=now,
                        supersedes_record_id="HYPOTHESIS-VERSION-PRESEED-001",
                        payload_json=body,
                        payload_sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
                        schema_version="1.0",
                        producer_capability_id="CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
                        producer_git_sha="a" * 40,
                        created_at=now,
                    )
                ],
                transaction_id="RESEARCH-TXN-PRESEED-002",
            )
            before_ids = {
                record.record_id for record in ResearchStore(data_root).iter_committed_records()
            }
            with self.assertRaises(CommissioningProofError) as raised:
                apply_legacy_commissioning_hypothesis_link(
                    data_root,
                    now=datetime(2026, 8, 29, 20, 0, 0, tzinfo=UTC),
                )
            self.assertEqual(str(raised.exception), "REAL_DATA_MIGRATION_AMBIGUOUS")
            self.assertEqual(
                {record.record_id for record in ResearchStore(data_root).iter_committed_records()},
                before_ids,
            )

    def test_replay_collision_does_not_block_unique_legacy_repair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _legacy_missing_link_store(data_root)
            with self.assertRaises(HficPreflightError):
                prove_fast_lane_commissioned(data_root)

            def _replay(_repo: Path, _root: Path) -> None:
                raise RuntimeError("REPLAY_AVAILABLE")

            receipt = run_preflight(
                ROOT,
                data_root,
                owner_focus="AUTO",
                auto_commission=True,
                commission_fn=_replay,
                git_snapshot=_git_snapshot(),
                clock=_CLOCK,
            )
            self.assertEqual(receipt["action"], "START_NEW_SESSION")
            self.assertEqual(
                receipt["commissioning"]["status"],
                "NO_GIT_FAST_LANE_PROVEN",
            )
            self.assertEqual(
                receipt["commissioning"]["compatibility_repair"]["status"],
                "APPLIED",
            )

class SemanticOperabilityEpochTests(unittest.TestCase):
    def test_evidence_epoch_material_includes_semantic_digest_key(self) -> None:
        from solana_alpha_lab.factory.hfic_preflight import evidence_epoch_material
        from solana_alpha_lab.factory.hfic_session import _MATERIAL_EPOCH_KEYS

        self.assertIn("semantic_capability_digest_sha256", _MATERIAL_EPOCH_KEYS)
        material = evidence_epoch_material(ROOT)
        digest = material.get("semantic_capability_digest_sha256")
        self.assertIsInstance(digest, str)
        self.assertEqual(len(digest), 64)
