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

from solana_alpha_lab.factory.hfic_memory_policy import (  # noqa: E402
    GENESIS_MEMORY_ELIGIBILITY_SHA256,
    HficMemoryPolicyError,
    NO_CHANGE,
    POLICY_ARTIFACT_KIND,
    REASON_OWNER_CALIBRATION_RESET,
    REASON_OWNER_MEMORY_RESTORE,
    apply_memory_policy,
    eligible_counts,
    iter_search_memory_hypothesis_payloads,
    load_policy_records,
    memory_eligibility_sha256,
    memory_policy_status,
    preview_memory_policy,
    quarantined_session_ids,
    search_identity_sha256,
)
from solana_alpha_lab.factory.hfic_preflight import (  # noqa: E402
    decide_preflight_action,
    evidence_epoch_material,
    rank_prior_candidate_ids,
)
from solana_alpha_lab.factory.hfic_prior_memory import build_prior_memory_snapshot  # noqa: E402
from solana_alpha_lab.factory.hfic_session import (  # noqa: E402
    PROMPT_VERSION,
    focus_key_sha256,
    lookup_prior,
    search_key_sha256,
    show_session,
)
from solana_alpha_lab.factory.research_store import (  # noqa: E402
    RecordKind,
    ResearchEvent,
    ResearchStore,
)
from tests.test_hfic_cli import run_cli  # noqa: E402

CREATED = datetime(2026, 9, 9, 12, 0, tzinfo=UTC)
CLOCK = lambda: CREATED  # noqa: E731


def _event(
    *,
    record_id: str,
    kind: RecordKind,
    entity_id: str,
    payload: dict[str, object],
    transaction_id: str,
    hypothesis_version_id: str | None = None,
) -> ResearchEvent:
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return ResearchEvent(
        record_id=record_id,
        record_kind=kind,
        entity_id=entity_id,
        hypothesis_version_id=hypothesis_version_id,
        run_id=None,
        transaction_id=transaction_id,
        effective_at=CREATED,
        first_reliable_available_at=CREATED,
        supersedes_record_id=None,
        payload_json=payload_json,
        payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        schema_version="1.0",
        producer_capability_id="CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
        producer_git_sha="0" * 40,
        created_at=CREATED,
    )


def _session_records(
    session_id: str,
    hyp_ids: list[str],
    *,
    phase: str = "SYNTHESIS_COMPLETE",
    memory_eligibility_sha256: str | None = None,
) -> list[ResearchEvent]:
    txn = f"RESEARCH-TXN-{session_id}"
    receipt = {
        "session_id": session_id,
        "session_state": "SYNTHESIS_COMPLETE",
        "critic_terminal": "NO_WORTHY_HYPOTHESIS",
        "critic_launched": False,
        "selected_candidate_id": None,
        "prompt_version": "HFIC-V1.1",
    }
    receipt_raw = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
    receipt_sha = hashlib.sha256(receipt_raw.encode("utf-8")).hexdigest()
    cycle_payload = {
        "research_cycle_id": session_id,
        "session_id": session_id,
        "phase": phase,
        "hfic_protocol": "HFIC-V1.1",
        "prompt_version": "HFIC-V1.1",
        "owner_focus": "AUTO",
        "evidence_epoch_sha256": "aa" * 32,
        "focus_key_sha256": "bb" * 32,
        "search_key_sha256": session_id.replace("HFIC-SESS-", "").lower() + "0" * 32,
        "memory_eligibility_sha256": memory_eligibility_sha256,
        "selected_candidate_id": None,
        "critic_launched": False,
        "critic_terminal": "NO_WORTHY_HYPOTHESIS",
        "session_receipt_sha256": receipt_sha if phase == "SYNTHESIS_COMPLETE" else None,
    }
    records = [
        _event(
            record_id=f"HFIC-CYCLE-{session_id}",
            kind=RecordKind.RESEARCH_CYCLE,
            entity_id=session_id,
            transaction_id=txn,
            payload=cycle_payload,
        )
    ]
    if phase == "SYNTHESIS_COMPLETE":
        records.append(
            _event(
                record_id=f"HFIC-ART-RECEIPT-{session_id}",
                kind=RecordKind.RESEARCH_ARTIFACT,
                entity_id=f"HFIC-ART-RECEIPT-{session_id}",
                transaction_id=txn,
                payload={
                    "research_artifact_id": f"HFIC-ART-RECEIPT-{session_id}",
                    "session_id": session_id,
                    "hfic_protocol": "HFIC-V1.1",
                    "artifact_kind": "SESSION_RECEIPT",
                    "payload_canonical": receipt_raw,
                    "payload_sha256": receipt_sha,
                },
            )
        )
    for hyp_id in hyp_ids:
        records.append(
            _event(
                record_id=f"HFIC-HYP-{hyp_id}",
                kind=RecordKind.HYPOTHESIS_VERSION,
                entity_id=hyp_id,
                hypothesis_version_id=hyp_id,
                transaction_id=txn,
                payload={
                    "hypothesis_version_id": hyp_id,
                    "session_id": session_id,
                    "hfic_protocol": "HFIC-V1.1",
                    "claim": f"{hyp_id} taker mix claim",
                    "statement": f"{hyp_id} taker mix claim",
                    "mechanism": f"{hyp_id} mechanism",
                    "actor_counterparty": "actor",
                    "population": "population",
                    "decision_timestamp": "t0",
                    "primary_x_family": "R0_TAKER_VOLUME_MIX",
                    "primary_y": "MEU",
                    "horizon_notional": "H900",
                    "negative_control": "control",
                    "cheapest_falsifier": "falsifier",
                    "definition_sha256": "cd" * 32,
                },
            )
        )
    return records


def _non_hfic(hyp_id: str, *, transaction_id: str) -> ResearchEvent:
    return _event(
        record_id=f"HYPOTHESIS-VERSION-{hyp_id}",
        kind=RecordKind.HYPOTHESIS_VERSION,
        entity_id=hyp_id,
        hypothesis_version_id=hyp_id,
        transaction_id=transaction_id,
        payload={
            "hypothesis_version_id": hyp_id,
            "claim": f"{hyp_id} non-hfic science claim",
            "statement": f"{hyp_id} non-hfic science claim",
            "mechanism": "science mechanism",
            "actor_counterparty": "actor",
            "population": "population",
            "decision_timestamp": "t0",
            "primary_x_family": "QUOTE_FRICTION",
            "primary_y": "H900",
            "horizon_notional": "H900",
            "negative_control": "control",
            "cheapest_falsifier": "falsifier",
            "definition_sha256": "ef" * 32,
        },
    )


def _capacity_store(root: Path) -> tuple[ResearchStore, list[str]]:
    store = ResearchStore(root)
    session_ids: list[str] = []
    for index in range(13):
        session_id = f"HFIC-SESS-CAP{index:02d}AAAAAAAA"
        session_ids.append(session_id)
        hyp_ids = [f"HFIC-CAND-CAP{index:02d}{slot}" for slot in range(5)]
        store.append(_session_records(session_id, hyp_ids), transaction_id=f"RESEARCH-TXN-{session_id}")
    store.append(
        [_non_hfic("HYP-QUOTE-NATIVE-FRICTION-H900-V1", transaction_id="RESEARCH-TXN-NON-1")],
        transaction_id="RESEARCH-TXN-NON-1",
    )
    store.append(
        [_non_hfic("HYP-EARLY-TAKER-VOLUME-MIX-H900-V1", transaction_id="RESEARCH-TXN-NON-2")],
        transaction_id="RESEARCH-TXN-NON-2",
    )
    return store, session_ids


def _apply(store: ResearchStore, session_ids: list[str], reason: str = REASON_OWNER_CALIBRATION_RESET):
    preview = preview_memory_policy(
        store,
        repo_root=ROOT,
        quarantine_session_ids=session_ids,
        reason_code=reason,
    )
    return apply_memory_policy(
        store,
        repo_root=ROOT,
        proposal=preview["proposal"],
        confirm_append_only=True,
        clock=CLOCK,
    )


class HficOperationalMemoryQuarantineTests(unittest.TestCase):
    def test_t1_no_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store, session_ids = _capacity_store(Path(raw))
            before = {
                record.record_id: record.payload_sha256
                for record in store.iter_committed_records()
            }
            _apply(store, session_ids[:1])
            after = {
                record.record_id: record.payload_sha256
                for record in store.iter_committed_records()
            }
            for record_id, digest in before.items():
                self.assertEqual(after[record_id], digest)

    def test_t2_central_eligibility(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store, session_ids = _capacity_store(Path(raw))
            _apply(store, session_ids[:1])
            payloads = iter_search_memory_hypothesis_payloads(store)
            hfic_ids = sorted(
                str(item["hypothesis_version_id"])
                for item in payloads
                if item.get("hfic_protocol")
            )
            ranked, _dropped = rank_prior_candidate_ids(
                store, owner_focus="AUTO", feature_hints=[]
            )
            snapshot = build_prior_memory_snapshot(
                store, store_inventory_digest="ab" * 32, repo_root=ROOT
            )
            snapshot_hfic = sorted(
                str(item["hypothesis_version_id"])
                for item in snapshot["capsules"]
                if item.get("hfic_protocol")
            )
            lookup = lookup_prior(store, query="taker mix")
            lookup_ids = sorted(
                {
                    str(item["candidate_id"])
                    for item in lookup["matches"]
                    if item.get("candidate_id")
                }
            )
            self.assertEqual(hfic_ids, snapshot_hfic)
            self.assertTrue(set(ranked).issubset(set(hfic_ids) | {
                "HYP-QUOTE-NATIVE-FRICTION-H900-V1",
                "HYP-EARLY-TAKER-VOLUME-MIX-H900-V1",
            }))
            self.assertEqual(lookup_ids, hfic_ids)
            quarantined = {f"HFIC-CAND-CAP00{slot}" for slot in range(5)}
            self.assertTrue(quarantined.isdisjoint(hfic_ids))

    def test_t3_non_hfic_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store, session_ids = _capacity_store(Path(raw))
            before = eligible_counts(store)
            _apply(store, session_ids)
            after = eligible_counts(store)
            self.assertEqual(before["eligible_non_hfic_hv_count"], 2)
            self.assertEqual(after["eligible_non_hfic_hv_count"], 2)
            self.assertEqual(after["eligible_hfic_hv_count"], 0)

    def test_t4_capacity(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store, session_ids = _capacity_store(Path(raw))
            before = memory_policy_status(store, repo_root=ROOT)
            self.assertEqual(before["total_eligible_prior_memory_count"], 67)
            self.assertEqual(before["fresh_freeze_capacity"], "BLOCKED")
            preview = preview_memory_policy(
                store,
                repo_root=ROOT,
                quarantine_all_current_hfic=True,
                reason_code=REASON_OWNER_CALIBRATION_RESET,
            )
            self.assertEqual(len(preview["proposal"]["quarantine_all_current_hfic_resolved"]), 13)
            apply_memory_policy(
                store,
                repo_root=ROOT,
                proposal=preview["proposal"],
                confirm_append_only=True,
                clock=CLOCK,
            )
            after = memory_policy_status(store, repo_root=ROOT)
            self.assertEqual(after["quarantined_hfic_hv_count"], 65)
            self.assertEqual(after["total_eligible_prior_memory_count"], 2)
            self.assertEqual(after["fresh_freeze_capacity"], "PASS")
            build_prior_memory_snapshot(
                store, store_inventory_digest="ab" * 32, repo_root=ROOT
            )

    def test_t5_audit_visible(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store, session_ids = _capacity_store(Path(raw))
            target = session_ids[0]
            _apply(store, [target])
            shown = show_session(store, target, repo_root=ROOT)
            self.assertEqual(shown["session_id"], target)
            self.assertTrue(shown["search_memory_quarantined"])
            self.assertEqual(shown["session_state"], "SYNTHESIS_COMPLETE")

    def test_t6_evidence_epoch_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            store, session_ids = _capacity_store(root)
            from solana_alpha_lab.factory.hfic_session import evidence_epoch_sha256

            before = evidence_epoch_sha256(evidence_epoch_material(ROOT, root))
            _apply(store, session_ids)
            after = evidence_epoch_sha256(evidence_epoch_material(ROOT, root))
            self.assertEqual(before, after)

    def test_t7_search_context_changes(self) -> None:
        epoch = "aa" * 32
        genesis = search_key_sha256(epoch, "AUTO", PROMPT_VERSION)
        other = search_identity_sha256(
            epoch, "AUTO", PROMPT_VERSION, memory_eligibility_sha256(["HFIC-SESS-X"])
        )
        self.assertNotEqual(genesis, other)
        self.assertEqual(search_key_sha256(epoch, "AUTO", PROMPT_VERSION, GENESIS_MEMORY_ELIGIBILITY_SHA256), genesis)

    def test_t8_noop_no_new_search(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store, session_ids = _capacity_store(Path(raw))
            first = _apply(store, session_ids[:2])
            eligibility = first["memory_eligibility_sha256"]
            second = _apply(store, session_ids[:2])
            self.assertEqual(second["status"], NO_CHANGE)
            self.assertEqual(second["memory_eligibility_sha256"], eligibility)
            self.assertEqual(len(load_policy_records(store)), 1)
            action, _sid = decide_preflight_action(
                [
                    {
                        "session_id": "HFIC-SESS-OLD",
                        "session_state": "SYNTHESIS_COMPLETE",
                        "evidence_epoch_sha256": "ee" * 32,
                        "focus_key_sha256": focus_key_sha256("AUTO"),
                        "search_key_sha256": search_key_sha256(
                            "ee" * 32, "AUTO", PROMPT_VERSION, eligibility
                        ),
                        "owner_focus": "AUTO",
                        "memory_eligibility_sha256": eligibility,
                    }
                ],
                search_key=search_key_sha256(
                    "ee" * 32, "AUTO", PROMPT_VERSION, eligibility
                ),
                evidence_epoch="ee" * 32,
                focus_key=focus_key_sha256("AUTO"),
                owner_focus="AUTO",
                memory_eligibility_sha256=eligibility,
            )
            self.assertEqual(action, "RETURN_EXISTING_SESSION")

    def test_t9_restore_identity(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store, session_ids = _capacity_store(Path(raw))
            a = _apply(store, session_ids[:3])
            a_sha = a["memory_eligibility_sha256"]
            b_preview = preview_memory_policy(
                store,
                repo_root=ROOT,
                quarantine_session_ids=session_ids[:5],
                reason_code=REASON_OWNER_CALIBRATION_RESET,
            )
            apply_memory_policy(
                store,
                repo_root=ROOT,
                proposal=b_preview["proposal"],
                confirm_append_only=True,
                clock=CLOCK,
            )
            restore = preview_memory_policy(
                store,
                repo_root=ROOT,
                restore_session_ids=session_ids[3:5],
                reason_code=REASON_OWNER_MEMORY_RESTORE,
            )
            back = apply_memory_policy(
                store,
                repo_root=ROOT,
                proposal=restore["proposal"],
                confirm_append_only=True,
                clock=CLOCK,
            )
            self.assertEqual(back["memory_eligibility_sha256"], a_sha)
            self.assertEqual(
                search_identity_sha256("ee" * 32, "AUTO", PROMPT_VERSION, a_sha),
                search_identity_sha256(
                    "ee" * 32, "AUTO", PROMPT_VERSION, back["memory_eligibility_sha256"]
                ),
            )

    def test_t10_pending_deny(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = ResearchStore(Path(raw))
            session_id = "HFIC-SESS-PENDING000001"
            store.append(
                _session_records(
                    session_id,
                    ["HFIC-CAND-PEND01"],
                    phase="FROZEN_AWAITING_CRITIC",
                ),
                transaction_id=f"RESEARCH-TXN-{session_id}",
            )
            with self.assertRaises(HficMemoryPolicyError) as ctx:
                preview_memory_policy(
                    store,
                    repo_root=ROOT,
                    quarantine_session_ids=[session_id],
                )
            self.assertEqual(str(ctx.exception), "HFIC_MEMORY_POLICY_PENDING_SESSION")

    def test_t11_stale_preview_deny(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store, session_ids = _capacity_store(Path(raw))
            preview = preview_memory_policy(
                store,
                repo_root=ROOT,
                quarantine_session_ids=session_ids[:1],
            )
            store.append(
                [_non_hfic("HYP-STALE-DRIFT-001", transaction_id="RESEARCH-TXN-STALE")],
                transaction_id="RESEARCH-TXN-STALE",
            )
            with self.assertRaises(HficMemoryPolicyError) as ctx:
                apply_memory_policy(
                    store,
                    repo_root=ROOT,
                    proposal=preview["proposal"],
                    confirm_append_only=True,
                    clock=CLOCK,
                )
            self.assertEqual(str(ctx.exception), "HFIC_MEMORY_POLICY_PREVIEW_STALE")

    def test_t12_policy_chain(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store, session_ids = _capacity_store(Path(raw))
            _apply(store, session_ids[:1])
            bogus = {
                "research_artifact_id": "HFIC-MEMPOL-BOGUS",
                "hfic_protocol": "HFIC-MEMORY-POLICY-V1",
                "artifact_kind": POLICY_ARTIFACT_KIND,
                "schema": "smial.hfic-search-memory-policy",
                "schema_version": "1.0",
                "policy_id": "HFIC-MEMPOL-0002",
                "policy_sequence": 1,
                "previous_policy_sha256": "11" * 32,
                "quarantined_session_ids": session_ids[:2],
                "reason_code": REASON_OWNER_CALIBRATION_RESET,
                "created_at": "2026-09-09T12:00:00Z",
                "producer_git_sha": "0" * 40,
                "policy_sha256": "22" * 32,
                "memory_eligibility_sha256": memory_eligibility_sha256(session_ids[:2]),
            }
            store.append(
                [
                    _event(
                        record_id="HFIC-MEMPOL-BOGUS",
                        kind=RecordKind.RESEARCH_ARTIFACT,
                        entity_id="HFIC-MEMPOL-BOGUS",
                        payload=bogus,
                        transaction_id="RESEARCH-TXN-BOGUS",
                    )
                ],
                transaction_id="RESEARCH-TXN-BOGUS",
            )
            with self.assertRaises(HficMemoryPolicyError) as ctx:
                load_policy_records(store)
            self.assertIn(
                str(ctx.exception),
                {"HFIC_MEMORY_POLICY_FORK", "HFIC_MEMORY_POLICY_INVALID"},
            )

    def test_t13_genesis_search_compat(self) -> None:
        epoch = "aa" * 32
        legacy = hashlib.sha256(
            f"{epoch}{focus_key_sha256('AUTO')}{PROMPT_VERSION}".encode("utf-8")
        ).hexdigest()
        self.assertEqual(search_key_sha256(epoch, "AUTO", PROMPT_VERSION), legacy)
        self.assertEqual(
            search_key_sha256(epoch, "AUTO", PROMPT_VERSION, GENESIS_MEMORY_ELIGIBILITY_SHA256),
            legacy,
        )

    def test_cli_status_preview_confirm(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            _capacity_store(root)
            status = run_cli("memory-policy-status", data_root=root)
            self.assertEqual(status.returncode, 0)
            payload = json.loads(status.stdout)
            self.assertEqual(payload["fresh_freeze_capacity"], "BLOCKED")
            preview = run_cli(
                "memory-policy-preview",
                "--quarantine-all-current-hfic",
                data_root=root,
            )
            self.assertEqual(preview.returncode, 0)
            body = json.loads(preview.stdout)
            denied = run_cli(
                "memory-policy-apply",
                "--proposal",
                str(root / "missing.json"),
                data_root=root,
            )
            self.assertNotEqual(denied.returncode, 0)
            proposal_path = root / "proposal.json"
            proposal_path.write_text(
                json.dumps(body["proposal"], ensure_ascii=False, sort_keys=True),
                encoding="utf-8",
            )
            unconfirmed = run_cli(
                "memory-policy-apply",
                "--proposal",
                str(proposal_path),
                data_root=root,
            )
            self.assertNotEqual(unconfirmed.returncode, 0)
            self.assertIn("HFIC_MEMORY_POLICY_CONFIRM_REQUIRED", unconfirmed.stderr)


    def test_t14_duckdb_projects_memory_eligibility(self) -> None:
        from solana_alpha_lab.factory.hfic_preflight import _query_hfic_sessions

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            store, session_ids = _capacity_store(root)
            applied = _apply(store, session_ids[:1])
            eligibility = applied["memory_eligibility_sha256"]
            extra = "HFIC-SESS-CAP99AAAAAAAA"
            store.append(
                _session_records(
                    extra,
                    ["HFIC-CAND-CAP990"],
                    memory_eligibility_sha256=eligibility,
                ),
                transaction_id=f"RESEARCH-TXN-{extra}",
            )
            store.rebuild_projection()
            projection = root / "projections" / "research_memory.duckdb"
            import duckdb

            connection = duckdb.connect(str(projection), read_only=True)
            try:
                row = connection.execute(
                    """
                    SELECT memory_eligibility_sha256
                    FROM hfic_sessions
                    WHERE session_id = ?
                    """,
                    [extra],
                ).fetchone()
            finally:
                connection.close()
            self.assertEqual(row[0], eligibility)
            listed = _query_hfic_sessions(root)
            by_id = {str(item["session_id"]): item for item in listed}
            self.assertEqual(by_id[extra]["memory_eligibility_sha256"], eligibility)
            action, sid = decide_preflight_action(
                listed,
                search_key=search_key_sha256(
                    "aa" * 32, "AUTO", PROMPT_VERSION, eligibility
                ),
                evidence_epoch="aa" * 32,
                focus_key=focus_key_sha256("AUTO"),
                owner_focus="AUTO",
                memory_eligibility_sha256=eligibility,
            )
            self.assertEqual(action, "STOP")
            self.assertEqual(sid, "SEARCH_BUDGET_EXHAUSTED")
            genesis_action, genesis_sid = decide_preflight_action(
                listed,
                search_key=search_key_sha256("aa" * 32, "AUTO", PROMPT_VERSION),
                evidence_epoch="aa" * 32,
                focus_key=focus_key_sha256("AUTO"),
                owner_focus="AUTO",
                memory_eligibility_sha256=GENESIS_MEMORY_ELIGIBILITY_SHA256,
            )
            self.assertNotEqual(genesis_sid, extra)
            self.assertNotEqual(genesis_action, "RETURN_EXISTING_SESSION")


if __name__ == "__main__":
    unittest.main()
