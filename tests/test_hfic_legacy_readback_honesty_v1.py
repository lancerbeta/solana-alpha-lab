"""Legacy readback honesty. Fixtures are SYNTHETIC_AUDIT_FIXTURE shapes."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.document_runner import repository_git_snapshot
from solana_alpha_lab.factory.hfic_identity import assign_portfolio_ids
from solana_alpha_lab.factory.hfic_provenance import inventory_placeholder_hfic_records
from solana_alpha_lab.factory.hfic_session import (
    HficSessionError,
    freeze_draft,
    persist_frozen_session,
    prove_runtime,
    show_session,
)
from solana_alpha_lab.factory.observation_panel_coverage import (
    compute_evidence_role,
    resolve_authoritative_hypothesis_registered_at,
)
from solana_alpha_lab.factory.observation_schedule_compiler import compile_observation_request
from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent, ResearchStore
from tests.test_hfic_cli import run_cli, seed_minimal_market_basis
from tests.test_hfic_provenance_clock import _placeholder_event
from tests.test_hfic_session import _critic_result, finalize_kill_complete, valid_draft
from tests.test_observation_fast_lane_routing_closure import AS_OF_START, v1_2_spec

FIXTURES = ROOT / "tests/fixtures/hypothesis_forge/legacy_shapes"
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
STAGE = datetime(2026, 8, 27, 13, 15, tzinfo=UTC)
STARTED_TEXT = "2026-08-27T12:00:00Z"
ADMISSION = datetime(2026, 9, 1, tzinfo=UTC)


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _append_json(store: ResearchStore, record_id: str, kind: RecordKind, payload: dict, *, created_at: datetime) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    event = ResearchEvent(
        record_id=record_id,
        record_kind=kind,
        entity_id=str(payload.get("hypothesis_version_id") or payload.get("session_id") or record_id),
        hypothesis_version_id=payload.get("hypothesis_version_id"),
        run_id=None,
        transaction_id=f"RESEARCH-TXN-{record_id[-12:]}",
        effective_at=created_at,
        first_reliable_available_at=created_at,
        supersedes_record_id=None,
        payload_json=encoded,
        payload_sha256=hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        schema_version="1.0",
        producer_capability_id="CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
        producer_git_sha="0" * 40,
        created_at=created_at,
    )
    store.append([event], transaction_id=event.transaction_id)


def _append_correction(store: ResearchStore, body: dict) -> None:
    inner = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    wrapper = {
        "artifact_kind": "PROVENANCE_TIME_CORRECTION",
        "hfic_protocol": body["hfic_protocol"],
        "payload_canonical": inner,
        "payload_sha256": hashlib.sha256(inner.encode("utf-8")).hexdigest(),
        "session_id": None,
    }
    _append_json(
        store,
        str(body["correction_id"]),
        RecordKind.RESEARCH_ARTIFACT,
        wrapper,
        created_at=datetime(2026, 8, 27, 15, 0, tzinfo=UTC),
    )


def _fresh_completed(store: ResearchStore) -> str:
    draft = valid_draft()
    snap = repository_git_snapshot(ROOT)
    receipt = {
        "receipt_id": "HFIC-PREFLIGHT-LEGACY-READBACK",
        "evidence_epoch_sha256": "aa" * 32,
        "market_evidence_epoch_sha256": "aa" * 32,
        "focus_key_sha256": "bb" * 32,
        "search_key_sha256": "cc" * 32,
        "owner_focus": "AUTO",
        "session_started_at": STARTED_TEXT,
        "live_git_head": snap.head_sha.lower(),
        "git_composite_sha256": snap.composite_sha256,
    }
    frozen = freeze_draft(draft, preflight_receipt=receipt)
    persist_frozen_session(
        store,
        frozen,
        repo_root=ROOT,
        identities=assign_portfolio_ids(draft["candidates"]),
        draft=draft,
    )
    finalize_kill_complete(
        frozen,
        _critic_result(frozen, "KILL_PREPARATORY_LOOP"),
        store,
        repo_root=ROOT,
    )
    return str(frozen["session_id"])


def _l1_covering(store: ResearchStore) -> dict:
    shape = _load("l1_provenance_correction_v1_1.json")
    inventory = inventory_placeholder_hfic_records(store)
    body = {key: value for key, value in shape.items() if key != "fixture"}
    body["affected_records"] = list(inventory["records"])
    body["inventory_sha256"] = inventory["inventory_sha256"]
    return body


def _append_l2(store: ResearchStore) -> str:
    shape = _load("l2_runner_up_identity_cycles.json")
    session_id = str(shape["session_id"])
    for index, cycle in enumerate(shape["cycles"], start=1):
        _append_json(
            store,
            f"HFIC-CYCLE-LEGACY-RUNNER-{index}",
            RecordKind.RESEARCH_CYCLE,
            cycle,
            created_at=datetime(2026, 9, 16, 12, index, tzinfo=UTC),
        )
    return session_id


def _append_l3(store: ResearchStore) -> dict:
    shape = _load("l3_hypothesis_placeholder_created_at.json")
    payload = {key: value for key, value in shape.items() if key != "fixture"}
    _append_json(
        store,
        "HFIC-HYP-LEGACY-EPOCH-0001",
        RecordKind.HYPOTHESIS_VERSION,
        payload,
        created_at=EPOCH,
    )
    return payload


class LegacyReadbackHonestyTests(unittest.TestCase):
    def test_t1_fresh_session_proof_accepts_v11_correction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            session_id = _fresh_completed(store)
            txn = "RESEARCH-TXN-LEGACYL1"
            store.append(
                [
                    _placeholder_event(
                        "HFIC-ART-LEGACY-PLACEHOLDER-A",
                        "HFIC-SESS-LEGACYPLACE01",
                        transaction_id=txn,
                    ),
                    _placeholder_event(
                        "HFIC-CYCLE-LEGACY-PLACEHOLDER-B",
                        "HFIC-SESS-LEGACYPLACE01",
                        transaction_id=txn,
                        kind=RecordKind.RESEARCH_CYCLE,
                        artifact_kind=None,
                    ),
                    _placeholder_event(
                        "HFIC-HYP-LEGACY-PLACEHOLDER-C",
                        "HFIC-SESS-LEGACYPLACE01",
                        transaction_id=txn,
                        kind=RecordKind.HYPOTHESIS_VERSION,
                        artifact_kind=None,
                    ),
                ],
                transaction_id=txn,
            )
            _append_correction(store, _l1_covering(store))
            proven = prove_runtime(store, session_id, repo_root=ROOT)
        self.assertEqual(proven["runtime_no_git"], "PROVEN")
        self.assertNotIn("PROVENANCE_CORRECTION_CORRUPT", json.dumps(proven))

    def test_t2_placeholder_registration_is_exploratory_reuse(self) -> None:
        shape = _load("l3_hypothesis_placeholder_created_at.json")
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            payload = _append_l3(ResearchStore(data_root))
            registered = resolve_authoritative_hypothesis_registered_at(
                data_root,
                hypothesis_version_id=payload["hypothesis_version_id"],
                hypothesis_definition_sha256=payload["definition_sha256"],
            )
            role = compute_evidence_role(
                hypothesis_registered_at=registered,
                first_admission_at=ADMISSION,
                first_y_available_at=None,
                closed_or_consumed=False,
            )
            spec = v1_2_spec(as_of="2026-08-01T00:00:00Z", role="PROSPECTIVE_OOS")
            spec["hypothesis_version"] = payload["hypothesis_version_id"]
            compiled = compile_observation_request(
                spec,
                root=ROOT,
                data_root=data_root,
                now=AS_OF_START,
                hypothesis_version_id=payload["hypothesis_version_id"],
                hypothesis_definition_sha256=payload["definition_sha256"],
            )
        self.assertIsNone(registered)
        self.assertEqual(role, "EXPLORATORY_REUSE")
        self.assertEqual(compiled.evidence_role, "EXPLORATORY_REUSE")
        self.assertNotEqual(shape["created_at"], "USED_AS_PROSPECTIVE")

    def test_t3_legacy_runner_up_reads_as_unresolved_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            session_id = _append_l2(store)
            shown = show_session(store, session_id, repo_root=ROOT)
            proven_error = None
            try:
                prove_runtime(store, session_id, repo_root=ROOT)
            except HficSessionError as exc:
                proven_error = str(exc)
        self.assertEqual(shown.get("identity_status"), "UNRESOLVED_BINDING")
        self.assertIn("memory_eligibility_sha256", shown.get("identity_conflict_fields") or [])
        self.assertNotEqual(proven_error, "SCIENTIFIC_IDENTITY_CONFLICT")

    def test_t4_diagnostics_counts_unreadable_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _append_l2(ResearchStore(data_root))
            completed = run_cli("diagnostics", "--last", "20", "--format", "json", data_root=data_root)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["sessions_listed"], 1)
        unreadable = payload["sessions_unreadable"]
        unreadable_n = len(unreadable) if isinstance(unreadable, list) else int(unreadable)
        self.assertGreaterEqual(unreadable_n + int(payload["sessions_unresolved"]), 1)

    def test_t5_forge_run_readout_names_skipped_history(self) -> None:
        from solana_alpha_lab.factory.hfic_representation_ladder import evaluate_forge_run

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            seed_minimal_market_basis(data_root)
            _append_l2(ResearchStore(data_root))
            forge = evaluate_forge_run(ROOT, data_root, owner_focus="AUTO", persist=False)
        readout = str(forge.get("owner_readout") or "")
        self.assertIn("history:", readout)
        self.assertIn("LEGACYRUNNER01", readout)

    def test_t6_current_market_unreadable_history_is_not_start(self) -> None:
        from solana_alpha_lab.factory.hfic_representation_ladder import evaluate_forge_run

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            seed_minimal_market_basis(data_root)
            first = evaluate_forge_run(ROOT, data_root, owner_focus="AUTO", persist=False)
            market = str(first.get("market_evidence_epoch_sha256") or "")
            self.assertEqual(len(market), 64)
            shape = _load("l2_runner_up_identity_cycles.json")
            store = ResearchStore(data_root)
            for index, cycle in enumerate(shape["cycles"], start=1):
                stamped = dict(cycle)
                stamped["market_evidence_epoch_sha256"] = market
                _append_json(
                    store,
                    f"HFIC-CYCLE-CURRENT-MARKET-{index}",
                    RecordKind.RESEARCH_CYCLE,
                    stamped,
                    created_at=datetime(2026, 9, 16, 12, index, tzinfo=UTC),
                )
            second = evaluate_forge_run(ROOT, data_root, owner_focus="AUTO", persist=False)
        self.assertNotIn(str(second.get("next_action")), {"START_BASE", "START_V1"})
        self.assertIn("CURRENT_MARKET_HISTORY_UNREADABLE", second.get("blocking_reason_codes") or [])

    def test_t7_session_placeholder_under_invalid_correction_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            session_id = _fresh_completed(store)
            store.append(
                [
                    _placeholder_event(
                        "HFIC-ART-SESSION-UNCOVERED",
                        session_id,
                        transaction_id="RESEARCH-TXN-UNCOVEREDT7",
                    )
                ],
                transaction_id="RESEARCH-TXN-UNCOVEREDT7",
            )
            with self.assertRaises(HficSessionError) as raised:
                prove_runtime(store, session_id, repo_root=ROOT)
        self.assertEqual(str(raised.exception), "PROVENANCE_TIME_UNCOVERED")

    def test_t8_future_prompt_version_still_reads_legacy_shapes(self) -> None:
        import solana_alpha_lab.factory.hfic_provenance as provenance
        import solana_alpha_lab.factory.hfic_session as session_mod

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            store = ResearchStore(data_root)
            txn = "RESEARCH-TXN-T8LEGACY"
            store.append(
                [
                    _placeholder_event(
                        "HFIC-ART-LEGACY-PLACEHOLDER-A",
                        "HFIC-SESS-LEGACYPLACE01",
                        transaction_id=txn,
                    )
                ],
                transaction_id=txn,
            )
            body = _l1_covering(store)
            _append_correction(store, body)
            session_id = _append_l2(store)
            l3_root = data_root / "l3"
            l3_root.mkdir()
            _append_l3(ResearchStore(l3_root))
            original_session = session_mod.PROMPT_VERSION
            original_provenance = provenance.PROMPT_VERSION
            session_mod.PROMPT_VERSION = "HFIC-V1.3"
            provenance.PROMPT_VERSION = "HFIC-V1.3"
            try:
                self.assertEqual(
                    provenance.resolve_provenance_status(store),
                    "CORRECTED_ORIGINAL_UNKNOWN",
                )
                shown = show_session(store, session_id, repo_root=ROOT)
                self.assertEqual(shown.get("identity_status"), "UNRESOLVED_BINDING")
                registered = resolve_authoritative_hypothesis_registered_at(
                    l3_root,
                    hypothesis_version_id="HFIC-HYP-LEGACY-EPOCH-0001",
                )
                role = compute_evidence_role(
                    hypothesis_registered_at=registered,
                    first_admission_at=ADMISSION,
                    first_y_available_at=None,
                    closed_or_consumed=False,
                )
            finally:
                session_mod.PROMPT_VERSION = original_session
                provenance.PROMPT_VERSION = original_provenance
        self.assertIsNone(registered)
        self.assertEqual(role, "EXPLORATORY_REUSE")

    def test_t9_supported_protocols_match_schema_enum(self) -> None:
        from solana_alpha_lab.factory.hfic_provenance import SUPPORTED_CORRECTION_PROTOCOLS

        schema = json.loads(
            (ROOT / "catalog/schemas/hfic_provenance_time_correction_v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            set(SUPPORTED_CORRECTION_PROTOCOLS),
            set(schema["properties"]["hfic_protocol"]["enum"]),
        )

    def test_t10_completed_cycles_do_not_null_a_written_identity(self) -> None:
        fields = (
            "memory_eligibility_sha256",
            "market_evidence_epoch_sha256",
            "capability_epoch_sha256",
            "scientific_slot_sha256",
            "execution_binding_sha256",
        )
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            session_id = _fresh_completed(store)
            bundle = store and __import__(
                "solana_alpha_lab.factory.hfic_session",
                fromlist=["load_session_bundle"],
            ).load_session_bundle(store, session_id)
            self.assertIsNotNone(bundle)
            seen: dict[str, list] = {name: [] for name in fields}
            for record in store.iter_committed_records():
                kind = getattr(record.record_kind, "value", record.record_kind)
                if kind != "RESEARCH_CYCLE":
                    continue
                payload = json.loads(record.payload_json)
                if payload.get("session_id") != session_id:
                    continue
                for name in fields:
                    if name in payload:
                        seen[name].append(payload.get(name))
        for name, values in seen.items():
            concrete = [item for item in values if item not in (None, "")]
            self.assertFalse(
                concrete and any(item in (None, "") for item in values),
                name,
            )

    def test_fresh_session_does_not_inherit_store_corrected_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            session_id = _fresh_completed(store)
            txn = "RESEARCH-TXN-STORECORR"
            store.append(
                [
                    _placeholder_event(
                        "HFIC-ART-OTHER-CORR",
                        "HFIC-SESS-OTHERCORR01",
                        transaction_id=txn,
                    )
                ],
                transaction_id=txn,
            )
            _append_correction(store, _l1_covering(store))
            proven = prove_runtime(store, session_id, repo_root=ROOT)
        self.assertEqual(proven["proof_status"], "PROVEN")
        self.assertEqual(proven["provenance_time_status"], "VALID")
        self.assertEqual(proven["store_provenance_time_status"], "CORRECTED_ORIGINAL_UNKNOWN")
        self.assertNotIn("original_exact_time_status", proven)
        self.assertNotIn("chronological_use_forbidden", proven)

    def test_unresolved_proof_is_not_a_proof_and_cli_exits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            session_id = _append_l2(ResearchStore(data_root))
            proven = prove_runtime(ResearchStore(data_root), session_id, repo_root=ROOT)
            completed = run_cli("prove-runtime", "--session-id", session_id, "--format", "json", data_root=data_root)
        self.assertEqual(proven["proof_status"], "NOT_A_PROOF")
        self.assertEqual(proven["runtime_no_git"], "UNRESOLVED_BINDING")
        self.assertNotEqual(proven["store_provenance_time_status"], "NOT_A_PROOF")
        self.assertNotEqual(completed.returncode, 0)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["proof_status"], "NOT_A_PROOF")

    def test_phantom_affected_record_is_corrupt_and_digest_drift_is_visible(self) -> None:
        from solana_alpha_lab.factory.hfic_provenance import (
            inventory_digest_drift,
            resolve_provenance_status,
        )

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            txn = "RESEARCH-TXN-DRIFT01"
            store.append(
                [
                    _placeholder_event(
                        "HFIC-ART-DRIFT-A",
                        "HFIC-SESS-DRIFT0001",
                        transaction_id=txn,
                    )
                ],
                transaction_id=txn,
            )
            body = _l1_covering(store)
            phantom = dict(body)
            phantom["affected_records"] = list(body["affected_records"]) + [
                {
                    "record_id": "HFIC-ART-PHANTOM",
                    "payload_sha256": "ab" * 32,
                    "record_kind": "RESEARCH_ARTIFACT",
                    "affected_fields": ["created_at"],
                }
            ]
            _append_correction(store, phantom)
            with self.assertRaises(HficSessionError) as raised:
                resolve_provenance_status(store)
            self.assertEqual(str(raised.exception), "PROVENANCE_CORRECTION_CORRUPT")

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            txn = "RESEARCH-TXN-DRIFT02"
            store.append(
                [
                    _placeholder_event(
                        "HFIC-ART-DRIFT-B",
                        "HFIC-SESS-DRIFT0002",
                        transaction_id=txn,
                    )
                ],
                transaction_id=txn,
            )
            body = _l1_covering(store)
            body["inventory_sha256"] = "cd" * 32
            _append_correction(store, body)
            self.assertEqual(resolve_provenance_status(store), "CORRECTED_ORIGINAL_UNKNOWN")
            self.assertTrue(inventory_digest_drift(store))
