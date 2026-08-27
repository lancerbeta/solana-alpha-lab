from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.document_runner import repository_git_snapshot
from solana_alpha_lab.factory.hfic_clock import (
    FrozenClock,
    HficClockError,
    capture_stage_time,
    render_canonical_utc,
    validate_hfic_timestamp,
)
from solana_alpha_lab.factory.hfic_preflight import (
    build_offline_commission_packet,
    persist_forge_context_packet,
    run_preflight,
)
from solana_alpha_lab.factory.hfic_provenance import (
    PROVENANCE_CORRECTED,
    PROVENANCE_VALID,
    apply_provenance_correction,
    inventory_placeholder_hfic_records,
    resolve_provenance_status,
)
from solana_alpha_lab.factory.hfic_session import (
    HficSessionError,
    PROMPT_VERSION,
    _display_session_receipt,
    freeze_draft,
    persist_frozen_session,
    persist_no_worthy_session,
    prove_runtime,
    show_session,
)
from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent, ResearchStore
from solana_alpha_lab.factory.run_passport import canonical_sha256
from tests.test_hfic_cli import bind_draft
from tests.test_hfic_session import _critic_result, valid_draft

HAPPY = ROOT / "tests/fixtures/hypothesis_forge/draft_happy_path_v1.json"
NO_WORTHY = ROOT / "tests/fixtures/hypothesis_forge/draft_no_worthy_v1.json"
STARTED = datetime(2026, 8, 27, 12, 0, 0, tzinfo=UTC)
STAGE = datetime(2026, 8, 27, 13, 15, 0, tzinfo=UTC)
CORRECTION_TIME = datetime(2026, 8, 27, 15, 0, 0, tzinfo=UTC)
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
STARTED_TEXT = "2026-08-27T12:00:00Z"
STAGE_TEXT = "2026-08-27T13:15:00Z"
RECEIPT_SCHEMA = ROOT / "catalog/schemas/hypothesis_forge_session_receipt_v1.schema.json"


def _git() -> dict[str, str]:
    snap = repository_git_snapshot(ROOT)
    return {"head_sha": snap.head_sha, "composite_sha256": snap.composite_sha256}


def _commission(data_root: Path) -> None:
    path = ROOT / "scripts/hypothesis_fast_lane.py"
    spec = importlib.util.spec_from_file_location("hfic_fast_lane_clock_helper", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("FAST_LANE_NOT_COMMISSIONABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    packet = build_offline_commission_packet(ROOT)
    packet_path = data_root / "offline_commission.json"
    packet_path.write_text(json.dumps(packet), encoding="utf-8")
    module.execute_commission_offline(ROOT, data_root, packet_path)


def _preflight(data_root: Path, clock: object, owner_focus: str = "AUTO") -> dict:
    return run_preflight(
        ROOT,
        data_root,
        owner_focus=owner_focus,
        auto_commission=True,
        commission_fn=lambda repo, root: _commission(root),
        git_snapshot=_git(),
        clock=clock,
    )


def _placeholder_event(
    record_id: str,
    session_id: str,
    *,
    transaction_id: str,
    kind: RecordKind = RecordKind.RESEARCH_ARTIFACT,
    artifact_kind: str | None = "SESSION_RECEIPT",
    extra: dict | None = None,
) -> ResearchEvent:
    payload = {
        "hfic_protocol": PROMPT_VERSION,
        "session_id": session_id,
        "created_at": "1970-01-01T00:00:00Z",
        **(extra or {}),
    }
    if artifact_kind is not None:
        payload["artifact_kind"] = artifact_kind
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return ResearchEvent(
        record_id=record_id,
        record_kind=kind,
        entity_id=record_id,
        hypothesis_version_id=None,
        run_id=None,
        transaction_id=transaction_id,
        effective_at=EPOCH,
        first_reliable_available_at=EPOCH,
        supersedes_record_id=None,
        payload_json=encoded,
        payload_sha256=hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        schema_version="1.0",
        producer_capability_id="CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
        producer_git_sha="0" * 40,
        created_at=EPOCH,
    )


def _schema_errors(document: dict) -> list[str]:
    schema = json.loads(RECEIPT_SCHEMA.read_text(encoding="utf-8"))
    return sorted(str(error.message) for error in Draft202012Validator(schema).iter_errors(document))


class HficClockUnitTests(unittest.TestCase):
    def test_placeholder_naive_malformed_denied(self) -> None:
        with self.assertRaises(HficClockError) as raised:
            validate_hfic_timestamp("1970-01-01T00:00:00Z")
        self.assertEqual(str(raised.exception), "HFIC_TIMESTAMP_PLACEHOLDER")
        with self.assertRaises(HficClockError) as raised:
            render_canonical_utc(datetime(2026, 8, 27, 12, 0, 0))
        self.assertEqual(str(raised.exception), "HFIC_TIMESTAMP_NAIVE")
        with self.assertRaises(HficClockError) as raised:
            validate_hfic_timestamp("2026-08-27T12:00:00+00:00")
        self.assertEqual(str(raised.exception), "HFIC_TIMESTAMP_MALFORMED")
        with self.assertRaises(HficClockError) as raised:
            validate_hfic_timestamp("not-a-time")
        self.assertEqual(str(raised.exception), "HFIC_TIMESTAMP_MALFORMED")
        with self.assertRaises(HficClockError) as raised:
            validate_hfic_timestamp(None)
        self.assertEqual(str(raised.exception), "HFIC_TIMESTAMP_MISSING")
        with self.assertRaises(HficClockError) as raised:
            capture_stage_time(FrozenClock(EPOCH))
        self.assertEqual(str(raised.exception), "HFIC_TIMESTAMP_PLACEHOLDER")

    def test_canonical_utc_render(self) -> None:
        self.assertEqual(render_canonical_utc(STARTED), STARTED_TEXT)


class HficPreflightClockTests(unittest.TestCase):
    def test_preflight_emits_bound_canonical_session_started_at(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            receipt = _preflight(data_root, FrozenClock(STARTED))
            self.assertEqual(receipt["session_started_at"], STARTED_TEXT)
            self.assertEqual(receipt["action"], "START_NEW_SESSION")
            packet = receipt["forge_context_packet"]
            self.assertNotIn("session_started_at", packet)
            self.assertNotEqual(receipt["research_memory_as_of"], receipt["session_started_at"])
            self.assertFalse(str(receipt["research_memory_as_of"]).startswith("1970-01-01"))

    def test_clock_does_not_change_evidence_epoch_or_search_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            first = _preflight(data_root, FrozenClock(STARTED))
            second = _preflight(data_root, FrozenClock(STAGE))
            self.assertEqual(first["evidence_epoch_sha256"], second["evidence_epoch_sha256"])
            self.assertEqual(first["search_key_sha256"], second["search_key_sha256"])
            self.assertEqual(
                first["forge_context_packet_sha256"],
                second["forge_context_packet_sha256"],
            )
            self.assertEqual(canonical_sha256(first["forge_context_packet"]), first["forge_context_packet_sha256"])
            self.assertNotEqual(first["session_started_at"], second["session_started_at"])
            self.assertNotEqual(first["preflight_receipt_sha256"], second["preflight_receipt_sha256"])

    def test_context_artifact_envelope_time_does_not_change_packet_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ResearchStore(data_root)
            packet = {
                "schema": "smial.forge-context-packet",
                "owner_focus": "AUTO",
                "evidence_epoch_sha256": "aa" * 32,
            }
            first = persist_forge_context_packet(
                data_root,
                packet,
                store=store,
                repo_root=ROOT,
                clock=FrozenClock(STARTED),
            )
            second = persist_forge_context_packet(
                data_root,
                packet,
                store=store,
                repo_root=ROOT,
                clock=FrozenClock(STAGE),
            )
            self.assertEqual(first, second)
            records = [
                item
                for item in store.iter_committed_records()
                if getattr(item.record_kind, "value", item.record_kind) == "RESEARCH_ARTIFACT"
            ]
            self.assertEqual(len(records), 1)
            self.assertEqual(render_canonical_utc(records[0].created_at), STARTED_TEXT)
            payload = json.loads(records[0].payload_json)
            self.assertEqual(payload["payload_sha256"], first)
            self.assertNotIn("session_started_at", json.loads(payload["payload_canonical"]))


class HficPersistBoundTimeTests(unittest.TestCase):
    def test_selected_and_no_worthy_use_bound_session_time(self) -> None:
        from solana_alpha_lab.factory.hfic_identity import assign_portfolio_ids

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            receipt = {
                **{
                    "receipt_id": "HFIC-PREFLIGHT-FIXTURE-001",
                    "evidence_epoch_sha256": "aa" * 32,
                    "focus_key_sha256": "bb" * 32,
                    "search_key_sha256": "cc" * 32,
                    "owner_focus": "AUTO",
                    "session_started_at": STARTED_TEXT,
                    "live_git_head": repository_git_snapshot(ROOT).head_sha.lower(),
                    "git_composite_sha256": repository_git_snapshot(ROOT).composite_sha256,
                    "store_inventory_digest": "ee" * 32,
                }
            }
            selected = freeze_draft(valid_draft(), preflight_receipt=receipt)
            persist_frozen_session(
                store,
                selected,
                repo_root=ROOT,
                identities=assign_portfolio_ids(valid_draft()["candidates"]),
                draft=valid_draft(),
            )
            no_worthy_receipt = {
                **receipt,
                "evidence_epoch_sha256": "11" * 32,
                "focus_key_sha256": "22" * 32,
                "search_key_sha256": "33" * 32,
                "forge_context_packet_sha256": "dd" * 32,
            }
            no_worthy_draft = json.loads(NO_WORTHY.read_text(encoding="utf-8"))
            no_worthy = freeze_draft(no_worthy_draft, preflight_receipt=no_worthy_receipt)
            persist_no_worthy_session(
                store,
                no_worthy,
                repo_root=ROOT,
                identities=assign_portfolio_ids(no_worthy_draft["candidates"]),
                draft=no_worthy_draft,
                preflight_receipt=no_worthy_receipt,
            )
            frozen_times = [
                render_canonical_utc(item.created_at)
                for item in store.iter_committed_records()
                if str(item.record_id).startswith("HFIC-")
            ]
            self.assertTrue(frozen_times)
            self.assertTrue(all(item == STARTED_TEXT for item in frozen_times))
            shown = show_session(store, str(selected["session_id"]), repo_root=ROOT)
            self.assertEqual(shown["provenance_time_status"], PROVENANCE_VALID)
            no_worthy_receipt_payload = None
            for item in store.iter_committed_records():
                if str(item.record_id).endswith("SESSION-RECEIPT-" + str(no_worthy["session_id"])):
                    nested = json.loads(json.loads(item.payload_json)["payload_canonical"])
                    no_worthy_receipt_payload = nested
                    break
                payload = json.loads(item.payload_json)
                if payload.get("artifact_kind") == "SESSION_RECEIPT" and payload.get("session_id") == no_worthy["session_id"]:
                    no_worthy_receipt_payload = json.loads(payload["payload_canonical"])
                    break
            self.assertIsNotNone(no_worthy_receipt_payload)
            self.assertEqual(no_worthy_receipt_payload["created_at"], STARTED_TEXT)
            self.assertEqual(no_worthy_receipt_payload["session_started_at"], STARTED_TEXT)

    def test_persist_frozen_rejects_placeholder_stage_time(self) -> None:
        from solana_alpha_lab.factory.hfic_identity import assign_portfolio_ids

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            receipt = {
                "receipt_id": "HFIC-PREFLIGHT-FIXTURE-001",
                "evidence_epoch_sha256": "aa" * 32,
                "focus_key_sha256": "bb" * 32,
                "search_key_sha256": "cc" * 32,
                "owner_focus": "AUTO",
                "session_started_at": STARTED_TEXT,
                "live_git_head": repository_git_snapshot(ROOT).head_sha.lower(),
                "git_composite_sha256": repository_git_snapshot(ROOT).composite_sha256,
            }
            selected = freeze_draft(valid_draft(), preflight_receipt=receipt)
            with self.assertRaises(HficSessionError) as raised:
                persist_frozen_session(
                    store,
                    selected,
                    repo_root=ROOT,
                    identities=assign_portfolio_ids(valid_draft()["candidates"]),
                    draft=valid_draft(),
                    stage_time=EPOCH,
                )
            self.assertEqual(str(raised.exception), "HFIC_TIMESTAMP_PLACEHOLDER")

    def test_critic_finalize_uses_stage_time(self) -> None:
        from solana_alpha_lab.factory.hfic_identity import assign_portfolio_ids
        from solana_alpha_lab.factory.hfic_session import finalize_session

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            draft = valid_draft()
            receipt = {
                "receipt_id": "HFIC-PREFLIGHT-FIXTURE-001",
                "evidence_epoch_sha256": "aa" * 32,
                "focus_key_sha256": "bb" * 32,
                "search_key_sha256": "cc" * 32,
                "owner_focus": "AUTO",
                "session_started_at": STARTED_TEXT,
                "live_git_head": repository_git_snapshot(ROOT).head_sha.lower(),
                "git_composite_sha256": repository_git_snapshot(ROOT).composite_sha256,
            }
            frozen = freeze_draft(draft, preflight_receipt=receipt)
            persist_frozen_session(
                store,
                frozen,
                repo_root=ROOT,
                identities=assign_portfolio_ids(draft["candidates"]),
                draft=draft,
            )
            finalize_session(
                frozen,
                _critic_result(frozen, "KILL_PREPARATORY_LOOP"),
                store=store,
                repo_root=ROOT,
                clock=FrozenClock(STAGE),
            )
            freeze_ids = []
            final_ids = []
            for item in store.iter_committed_records():
                rendered = render_canonical_utc(item.created_at)
                if "FROZEN" in str(item.record_id):
                    freeze_ids.append(rendered)
                if "COMPLETE" in str(item.record_id) or "CRITIC-RESULT" in str(item.record_id):
                    final_ids.append(rendered)
            self.assertTrue(freeze_ids)
            self.assertTrue(all(item == STARTED_TEXT for item in freeze_ids))
            self.assertTrue(final_ids)
            self.assertTrue(all(item == STAGE_TEXT for item in final_ids))

    def test_crash_before_and_after_append_replay(self) -> None:
        from solana_alpha_lab.factory.hfic_identity import assign_portfolio_ids

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            draft = valid_draft()
            receipt = {
                "receipt_id": "HFIC-PREFLIGHT-FIXTURE-001",
                "evidence_epoch_sha256": "aa" * 32,
                "focus_key_sha256": "bb" * 32,
                "search_key_sha256": "cc" * 32,
                "owner_focus": "AUTO",
                "session_started_at": STARTED_TEXT,
                "live_git_head": repository_git_snapshot(ROOT).head_sha.lower(),
                "git_composite_sha256": repository_git_snapshot(ROOT).composite_sha256,
            }
            frozen = freeze_draft(draft, preflight_receipt=receipt)
            identities = assign_portfolio_ids(draft["candidates"])
            persist_frozen_session(
                store,
                frozen,
                repo_root=ROOT,
                identities=identities,
                draft=draft,
            )
            first_hashes = {
                item.record_id: item.payload_sha256 for item in store.iter_committed_records()
            }
            persist_frozen_session(
                store,
                frozen,
                repo_root=ROOT,
                identities=identities,
                draft=draft,
            )
            second_hashes = {
                item.record_id: item.payload_sha256 for item in store.iter_committed_records()
            }
            self.assertEqual(first_hashes, second_hashes)
            self.assertTrue(
                all(
                    render_canonical_utc(item.created_at) == STARTED_TEXT
                    for item in store.iter_committed_records()
                )
            )


class HficReplayAndReceiptSchemaTests(unittest.TestCase):
    def test_same_evidence_focus_returns_existing_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            first = _preflight(data_root, FrozenClock(STARTED))
            draft = bind_draft(json.loads(HAPPY.read_text(encoding="utf-8")), first)
            frozen = freeze_draft(
                draft,
                preflight_receipt=first,
                store=ResearchStore(data_root),
                repo_root=ROOT,
            )
            from solana_alpha_lab.factory.hfic_session import finalize_session

            finalize_session(
                frozen,
                _critic_result(frozen, "KILL_PREPARATORY_LOOP"),
                store=ResearchStore(data_root),
                repo_root=ROOT,
                clock=FrozenClock(STAGE),
            )
            replay = _preflight(data_root, FrozenClock(datetime(2026, 8, 27, 18, 0, tzinfo=UTC)))
            self.assertEqual(replay["action"], "RETURN_EXISTING_SESSION")
            self.assertEqual(replay["session_id"], frozen["session_id"])
            self.assertEqual(replay["evidence_epoch_sha256"], first["evidence_epoch_sha256"])
            self.assertEqual(replay["search_key_sha256"], first["search_key_sha256"])

    def test_historical_placeholder_session_replays_without_regeneration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            first = _preflight(data_root, FrozenClock(STARTED))
            self.assertEqual(first["action"], "START_NEW_SESSION")
            session_id = "HFIC-SESS-" + str(first["search_key_sha256"])[:16].upper()
            receipt_body = {
                "session_id": session_id,
                "session_state": "SYNTHESIS_COMPLETE",
                "evidence_epoch_sha256": first["evidence_epoch_sha256"],
                "focus_key_sha256": first["focus_key_sha256"],
                "search_key_sha256": first["search_key_sha256"],
                "prompt_version": PROMPT_VERSION,
                "live_git_head": "ab" * 20,
                "store_inventory_digest": "dd" * 32,
                "candidate_ids": [],
                "selected_candidate_id": None,
                "runner_up_candidate_id": None,
                "critic_input_packet_sha256": None,
                "critic_result_sha256": None,
                "critic_launched": False,
                "critic_terminal": "NO_WORTHY_HYPOTHESIS",
                "lane_classifier_terminal": None,
                "decision_event_ids": [],
                "next": "STOP",
                "forge_context_packet_sha256": first["forge_context_packet_sha256"],
                "authority": {
                    "git_mutation": 0,
                    "experiment_execution": 0,
                    "provider_api_rpc_wss_calls": 0,
                },
                "created_at": "1970-01-01T00:00:00Z",
                "session_started_at": "1970-01-01T00:00:00Z",
            }
            receipt_bytes = json.dumps(
                receipt_body,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            receipt_sha = hashlib.sha256(receipt_bytes.encode("utf-8")).hexdigest()
            txn = "RESEARCH-TXN-HFICHISTC10401"
            store = ResearchStore(data_root)
            store.append(
                [
                    _placeholder_event(
                        f"HFIC-CYCLE-{session_id}-NO-WORTHY",
                        session_id,
                        transaction_id=txn,
                        kind=RecordKind.RESEARCH_CYCLE,
                        artifact_kind=None,
                        extra={
                            "research_cycle_id": f"{session_id}-NO-WORTHY",
                            "phase": "SYNTHESIS_COMPLETE",
                            "prompt_version": PROMPT_VERSION,
                            "owner_focus": "AUTO",
                            "evidence_epoch_sha256": first["evidence_epoch_sha256"],
                            "focus_key_sha256": first["focus_key_sha256"],
                            "search_key_sha256": first["search_key_sha256"],
                            "selected_candidate_id": None,
                            "candidate_ids": [],
                            "critic_launched": False,
                            "critic_terminal": "NO_WORTHY_HYPOTHESIS",
                            "next": "STOP",
                            "session_receipt_sha256": receipt_sha,
                            "forge_context_packet_sha256": first["forge_context_packet_sha256"],
                        },
                    ),
                    _placeholder_event(
                        f"HFIC-ART-SESSION-RECEIPT-{session_id}",
                        session_id,
                        transaction_id=txn,
                        extra={
                            "research_artifact_id": f"HFIC-ART-SESSION-RECEIPT-{session_id}",
                            "payload_canonical": receipt_bytes,
                            "payload_sha256": receipt_sha,
                        },
                    ),
                ],
                transaction_id=txn,
            )
            replay = _preflight(data_root, FrozenClock(datetime(2026, 8, 27, 18, 0, tzinfo=UTC)))
            self.assertEqual(replay["action"], "RETURN_EXISTING_SESSION")
            self.assertEqual(replay["session_id"], session_id)
            self.assertEqual(replay["critic_terminal"], "NO_WORTHY_HYPOTHESIS")
            self.assertEqual(replay["evidence_epoch_sha256"], first["evidence_epoch_sha256"])
            self.assertEqual(replay["search_key_sha256"], first["search_key_sha256"])
            shown = show_session(store, session_id, repo_root=ROOT)
            self.assertEqual(shown["provenance_time_status"], "PLACEHOLDER_UNCOVERED")
            self.assertNotIn("1970-01-01", json.dumps(shown["session_receipt"]))
            self.assertNotEqual(replay["action"], "START_NEW_SESSION")

    def test_selected_and_no_worthy_schema_reject_placeholder_receipt_time(self) -> None:
        selected = {
            "session_id": "HFIC-SESS-SCHEMASEL001",
            "session_state": "SYNTHESIS_COMPLETE",
            "evidence_epoch_sha256": "aa" * 32,
            "focus_key_sha256": "bb" * 32,
            "search_key_sha256": "cc" * 32,
            "prompt_version": "HFIC-V1.1",
            "live_git_head": "ab" * 20,
            "store_inventory_digest": "dd" * 32,
            "candidate_ids": [f"HFIC-CAND-{'A' * 12}{index}" for index in range(4)],
            "selected_candidate_id": "HFIC-CAND-" + "A" * 12 + "0",
            "runner_up_candidate_id": "HFIC-CAND-" + "A" * 12 + "1",
            "critic_input_packet_sha256": "ee" * 32,
            "critic_result_sha256": "ff" * 32,
            "critic_terminal": "KILL_PREPARATORY_LOOP",
            "lane_classifier_terminal": None,
            "decision_event_ids": [],
            "next": "STOP",
            "authority": {
                "git_mutation": 0,
                "experiment_execution": 0,
                "provider_api_rpc_wss_calls": 0,
            },
            "no_git_fence_receipt": {},
            "created_at": "1970-01-01T00:00:00Z",
        }
        self.assertTrue(_schema_errors(selected))
        selected["created_at"] = STARTED_TEXT
        self.assertEqual(_schema_errors(selected), [])
        no_worthy = dict(selected)
        no_worthy.update(
            {
                "selected_candidate_id": None,
                "critic_input_packet_sha256": None,
                "critic_result_sha256": None,
                "critic_launched": False,
                "critic_terminal": "NO_WORTHY_HYPOTHESIS",
                "forge_context_packet_sha256": "11" * 32,
                "created_at": "1970-01-01T00:00:00Z",
            }
        )
        self.assertTrue(_schema_errors(no_worthy))
        no_worthy["created_at"] = STARTED_TEXT
        self.assertEqual(_schema_errors(no_worthy), [])


class HficProvenanceCorrectionTests(unittest.TestCase):
    def test_inventory_correction_idempotence_and_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            txn_a = "RESEARCH-TXN-PLACEHOLD01"
            store.append(
                [
                    _placeholder_event(
                        "HFIC-ART-PLACEHOLDER-A",
                        "HFIC-SESS-PLACEHOLD01",
                        transaction_id=txn_a,
                        extra={"payload_canonical": json.dumps({"created_at": "1970-01-01T00:00:00Z"})},
                    ),
                    _placeholder_event(
                        "HFIC-CYCLE-PLACEHOLDER-B",
                        "HFIC-SESS-PLACEHOLD01",
                        transaction_id=txn_a,
                        kind=RecordKind.RESEARCH_CYCLE,
                        artifact_kind=None,
                    ),
                ],
                transaction_id=txn_a,
            )
            inventory = inventory_placeholder_hfic_records(store)
            self.assertEqual(inventory["record_count"], 2)
            self.assertEqual(inventory["counts_by_session_id"]["HFIC-SESS-PLACEHOLD01"], 2)
            self.assertIn("RESEARCH_ARTIFACT", inventory["counts_by_record_kind"])
            self.assertIn("created_at", inventory["counts_by_affected_field"])
            self.assertTrue(all(item["payload_sha256"] for item in inventory["records"]))
            with self.assertRaises(HficSessionError) as raised:
                resolve_provenance_status(store)
            self.assertEqual(str(raised.exception), "PROVENANCE_TIME_UNCOVERED")
            first = apply_provenance_correction(
                store,
                repo_root=ROOT,
                clock=FrozenClock(CORRECTION_TIME),
            )
            self.assertTrue(first["correction_appended"])
            self.assertEqual(first["status"], PROVENANCE_CORRECTED)
            self.assertEqual(first["original_exact_time_status"], "UNKNOWN")
            self.assertTrue(first["chronological_use_forbidden"])
            self.assertEqual(first["provider_calls_actual"], 0)
            self.assertTrue(first["git_unchanged"])
            second = apply_provenance_correction(
                store,
                repo_root=ROOT,
                clock=FrozenClock(datetime(2026, 8, 27, 16, 0, tzinfo=UTC)),
            )
            self.assertFalse(second["correction_appended"])
            self.assertEqual(second["correction_id"], first["correction_id"])
            store.append(
                [
                    _placeholder_event(
                        "HFIC-ART-PLACEHOLDER-C",
                        "HFIC-SESS-PLACEHOLD02",
                        transaction_id="RESEARCH-TXN-PLACEHOLD02",
                    )
                ],
                transaction_id="RESEARCH-TXN-PLACEHOLD02",
            )
            with self.assertRaises(HficSessionError) as raised:
                apply_provenance_correction(store, repo_root=ROOT, clock=FrozenClock(CORRECTION_TIME))
            self.assertEqual(str(raised.exception), "PROVENANCE_CORRECTION_MISMATCH")
            with self.assertRaises(HficSessionError) as raised:
                resolve_provenance_status(store)
            self.assertEqual(str(raised.exception), "PROVENANCE_CORRECTION_MISMATCH")

    def test_corrupt_and_partial_correction_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            store.append(
                [_placeholder_event("HFIC-ART-PLACEHOLDER-D", "HFIC-SESS-PLACEHOLD03", transaction_id="RESEARCH-TXN-PLACEHOLD03")],
                transaction_id="RESEARCH-TXN-PLACEHOLD03",
            )
            encoded = json.dumps(
                {
                    "artifact_kind": "PROVENANCE_TIME_CORRECTION",
                    "payload_canonical": "{",
                    "payload_sha256": "00" * 32,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            store.append(
                [
                    ResearchEvent(
                        record_id="HFIC-ART-PROVENANCE-CORR-BAD",
                        record_kind=RecordKind.RESEARCH_ARTIFACT,
                        entity_id="HFIC-ART-PROVENANCE-CORR-BAD",
                        hypothesis_version_id=None,
                        run_id=None,
                        transaction_id="RESEARCH-TXN-CORRUPT",
                        effective_at=STAGE,
                        first_reliable_available_at=STAGE,
                        supersedes_record_id=None,
                        payload_json=encoded,
                        payload_sha256=hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
                        schema_version="1.0",
                        producer_capability_id="CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
                        producer_git_sha="0" * 40,
                        created_at=STAGE,
                    )
                ],
                transaction_id="RESEARCH-TXN-CORRUPT",
            )
            with self.assertRaises(HficSessionError) as raised:
                resolve_provenance_status(store)
            self.assertEqual(str(raised.exception), "PROVENANCE_CORRECTION_CORRUPT")

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            txn = "RESEARCH-TXN-PARTIAL01"
            store.append(
                [
                    _placeholder_event("HFIC-ART-PARTIAL-A", "HFIC-SESS-PARTIAL01", transaction_id=txn),
                    _placeholder_event("HFIC-ART-PARTIAL-B", "HFIC-SESS-PARTIAL01", transaction_id=txn),
                ],
                transaction_id=txn,
            )
            inventory = inventory_placeholder_hfic_records(store)
            body = {
                "schema": "smial.hfic-provenance-time-correction",
                "schema_version": "1.0",
                "correction_id": "HFIC-ART-PROVENANCE-CORR-PARTIAL01",
                "artifact_kind": "PROVENANCE_TIME_CORRECTION",
                "hfic_protocol": PROMPT_VERSION,
                "affected_records": inventory["records"][:1],
                "original_placeholder_value": "1970-01-01T00:00:00Z",
                "original_exact_time_status": "UNKNOWN",
                "chronological_use_forbidden": True,
                "correction_created_at": STAGE_TEXT,
                "producer_git_sha": "ab" * 20,
                "reason_code": "HFIC_PLACEHOLDER_PROVENANCE_TIME",
                "inventory_sha256": inventory["inventory_sha256"],
                "authority": {
                    "git_mutation": 0,
                    "experiment_execution": 0,
                    "provider_api_rpc_wss_calls": 0,
                },
                "non_claims": ["NO_RECOVERED_EXACT_TIME"],
            }
            inner = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            wrapper = json.dumps(
                {
                    "artifact_kind": "PROVENANCE_TIME_CORRECTION",
                    "hfic_protocol": PROMPT_VERSION,
                    "payload_canonical": inner,
                    "payload_sha256": hashlib.sha256(inner.encode("utf-8")).hexdigest(),
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            store.append(
                [
                    ResearchEvent(
                        record_id="HFIC-ART-PROVENANCE-CORR-PARTIAL01",
                        record_kind=RecordKind.RESEARCH_ARTIFACT,
                        entity_id="HFIC-ART-PROVENANCE-CORR-PARTIAL01",
                        hypothesis_version_id=None,
                        run_id=None,
                        transaction_id="RESEARCH-TXN-PARTIALC",
                        effective_at=STAGE,
                        first_reliable_available_at=STAGE,
                        supersedes_record_id=None,
                        payload_json=wrapper,
                        payload_sha256=hashlib.sha256(wrapper.encode("utf-8")).hexdigest(),
                        schema_version="1.0",
                        producer_capability_id="CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
                        producer_git_sha="ab" * 20,
                        created_at=STAGE,
                    )
                ],
                transaction_id="RESEARCH-TXN-PARTIALC",
            )
            with self.assertRaises(HficSessionError) as raised:
                resolve_provenance_status(store)
            self.assertEqual(str(raised.exception), "PROVENANCE_CORRECTION_PARTIAL")

    def test_show_session_and_prove_runtime_correction_contract(self) -> None:
        from solana_alpha_lab.factory.hfic_identity import assign_portfolio_ids
        from solana_alpha_lab.factory.hfic_session import finalize_session

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            draft = valid_draft()
            receipt = {
                "receipt_id": "HFIC-PREFLIGHT-FIXTURE-001",
                "evidence_epoch_sha256": "aa" * 32,
                "focus_key_sha256": "bb" * 32,
                "search_key_sha256": "cc" * 32,
                "owner_focus": "AUTO",
                "session_started_at": STARTED_TEXT,
                "live_git_head": repository_git_snapshot(ROOT).head_sha.lower(),
                "git_composite_sha256": repository_git_snapshot(ROOT).composite_sha256,
            }
            frozen = freeze_draft(draft, preflight_receipt=receipt)
            persist_frozen_session(
                store,
                frozen,
                repo_root=ROOT,
                identities=assign_portfolio_ids(draft["candidates"]),
                draft=draft,
            )
            finalize_session(
                frozen,
                _critic_result(frozen, "KILL_PREPARATORY_LOOP"),
                store=store,
                repo_root=ROOT,
                clock=FrozenClock(STAGE),
            )
            proven = prove_runtime(store, str(frozen["session_id"]), repo_root=ROOT)
            self.assertEqual(proven["provenance_time_status"], PROVENANCE_VALID)
            self.assertFalse(proven["recovered_exact_time"])
            store.append(
                [
                    _placeholder_event(
                        "HFIC-ART-OTHER-SESS-X",
                        "HFIC-SESS-OTHERCLOCK01",
                        transaction_id="RESEARCH-TXN-OTHERCLOCK01",
                    )
                ],
                transaction_id="RESEARCH-TXN-OTHERCLOCK01",
            )
            shown_valid = show_session(store, str(frozen["session_id"]), repo_root=ROOT)
            self.assertEqual(shown_valid["provenance_time_status"], PROVENANCE_VALID)
            with self.assertRaises(HficSessionError) as other_uncovered:
                prove_runtime(store, str(frozen["session_id"]), repo_root=ROOT)
            self.assertEqual(str(other_uncovered.exception), "PROVENANCE_TIME_UNCOVERED")
            store.append(
                [
                    _placeholder_event(
                        "HFIC-ART-UNCOVERED-X",
                        str(frozen["session_id"]),
                        transaction_id="RESEARCH-TXN-UNCOVEREDX",
                    )
                ],
                transaction_id="RESEARCH-TXN-UNCOVEREDX",
            )
            with self.assertRaises(HficSessionError) as raised:
                prove_runtime(store, str(frozen["session_id"]), repo_root=ROOT)
            self.assertEqual(str(raised.exception), "PROVENANCE_TIME_UNCOVERED")
            apply_provenance_correction(
                store,
                repo_root=ROOT,
                clock=FrozenClock(CORRECTION_TIME),
            )
            shown = show_session(store, str(frozen["session_id"]), repo_root=ROOT)
            self.assertEqual(shown["provenance_time_status"], PROVENANCE_CORRECTED)
            self.assertNotIn("1970-01-01", json.dumps(shown["session_receipt"]))
            displayed = _display_session_receipt(
                {"created_at": "1970-01-01T00:00:00Z", "session_started_at": "1970-01-01T00:00:00Z"},
                PROVENANCE_CORRECTED,
            )
            self.assertEqual(displayed["created_at"], "UNKNOWN")
            self.assertEqual(displayed["session_started_at"], "UNKNOWN")
            self.assertTrue(displayed["chronological_use_forbidden"])
            proven = prove_runtime(store, str(frozen["session_id"]), repo_root=ROOT)
            self.assertEqual(proven["provenance_time_status"], PROVENANCE_CORRECTED)
            self.assertEqual(proven["original_exact_time_status"], "UNKNOWN")
            self.assertFalse(proven["recovered_exact_time"])
            self.assertTrue(proven["chronological_use_forbidden"])
            self.assertEqual(proven["provider_calls_actual"], 0)
            self.assertTrue(proven["git_composite_unchanged"])


class HficAuthoritySurfaceTests(unittest.TestCase):
    def test_slash_skill_operator_config_zero_mid_cycle(self) -> None:
        config = Path(ROOT / "configs/hypothesis_forge_independent_critic_v1.yaml").read_text(
            encoding="utf-8"
        )
        skill = (ROOT / ".agents/skills/hypothesis-forge/SKILL.md").read_text(encoding="utf-8")
        command = (ROOT / ".cursor/commands/hypothesis-forge.md").read_text(encoding="utf-8")
        operator = (
            ROOT / "docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md"
        ).read_text(encoding="utf-8")
        for text in (config, skill, command, operator):
            self.assertIn("ZERO_MID_CYCLE_OWNER_INTERVENTION", text)
            self.assertIn("PASS_TO_CLASSIFICATION", text)
            self.assertIn("REVISE_ONCE", text)
            self.assertIn("AUTO_HANDOFF_UNAVAILABLE", text)
            self.assertIn("ONE_SLASH_ONE_SESSION", text)
        self.assertNotIn("only if subagent launch is unavailable", skill)
        self.assertIn("AFTER_EXACT_OWNER_MERGE_PHRASE", config)
        self.assertIn("inventory-placeholder-times", operator)
        self.assertIn("apply-provenance-correction", operator)
        self.assertIn("manual fallback only", operator.casefold())


if __name__ == "__main__":
    unittest.main()
