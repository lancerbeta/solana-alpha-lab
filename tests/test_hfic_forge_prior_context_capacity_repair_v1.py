"""HFIC_FORGE_PRIOR_CONTEXT_CAPACITY_REPAIR_V1 regressions."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.hfic_memory_policy import (  # noqa: E402
    iter_search_memory_hypothesis_payloads,
)
from solana_alpha_lab.factory.hfic_preflight import (  # noqa: E402
    AUTO_SESSIONS_PER_EPOCH,
    HficPreflightError,
    MAX_DISTINCT_FOCUSES_PER_EPOCH,
    MAX_PACKET_BYTES,
    MAX_RANKED_PRIORS,
    ORDINARY_FORGE_MAX_PACKET_BYTES,
    build_forge_context_packet,
    decide_preflight_action,
    evidence_epoch_material,
    forge_context_packet_max_bytes,
    rank_prior_candidate_ids,
)
from solana_alpha_lab.factory.hfic_prior_memory import (  # noqa: E402
    MEMORY_HARD_CLOSE,
    MEMORY_NOT_SELECTED,
    MEMORY_PARK,
    build_prior_memory_snapshot,
    compact_forge_prior_entry,
    compact_prior_entry,
    latest_hypothesis_decisions,
)
from solana_alpha_lab.factory.hfic_reopened_prior_routing import (  # noqa: E402
    BODY_INCOMPLETE,
    ReopenedPriorRoutingError,
    ranked_prior_entries_for_ids,
    resolve_all_reopened_priors,
)
from solana_alpha_lab.factory.hfic_session import (  # noqa: E402
    PROMPT_VERSION,
    evidence_epoch_sha256,
    focus_key_sha256,
    search_key_sha256,
)
from solana_alpha_lab.factory.research_store import (  # noqa: E402
    RecordKind,
    ResearchEvent,
    ResearchStore,
)
from solana_alpha_lab.factory.run_passport import canonical_json_bytes  # noqa: E402

CREATED = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)
CONTROL_SESSION = "HFIC-SESS-60FB3DA7C8EB33FC"
FOCUS = "IDENTIFIABLE_NOW"


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


def _fat_hfic_candidate(index: int, *, transaction_id: str) -> ResearchEvent:
    hyp_id = f"HFIC-CAND-FAT{index:04d}DEADBEEF"
    claim = (
        f"candidate {index} claims a long causal story about coverage missingness "
        f"and competing-risk clocks that must remain distinguishable from closed "
        f"families while staying PIT-valid on the current Factory surface " * 3
    )
    mechanism = (
        f"mechanism {index} explains how observable state at decision time changes "
        f"recovery versus exit hazard without new provider attribution " * 3
    )
    payload = {
        "hypothesis_version_id": hyp_id,
        "hfic_protocol": "HFIC-V1.2",
        "session_id": CONTROL_SESSION,
        "claim": claim,
        "mechanism": mechanism,
        "actor_counterparty": f"actor-counterparty-role-{index}-market-maker-vs-taker",
        "population": "imported live lifecycle discovery corpus yield-eligible members",
        "decision_timestamp": "discovery_first_reliable_available_at plus R0",
        "primary_x_family": f"family_x_{index}_coverage_or_clock",
        "primary_y": "H900 PathRisk process outcome",
        "horizon_notional": "H900 / zero-notional process study",
        "negative_control": "shuffled pseudo-clock matched on wall clock",
        "cheapest_falsifier": (
            "offline canonical receipt replay stratified hazard probe under "
            "accepted classify_audition_terminal allowlist only"
        ),
        "definition_sha256": hashlib.sha256(f"def-{index}".encode()).hexdigest(),
        "role_in_session": "PORTFOLIO" if index > 2 else ("SELECTED" if index == 1 else "RUNNER_UP"),
    }
    return _event(
        record_id=f"REC-{hyp_id}",
        kind=RecordKind.HYPOTHESIS_VERSION,
        entity_id=hyp_id,
        payload=payload,
        transaction_id=transaction_id,
        hypothesis_version_id=hyp_id,
    )


def _decision_event(
    hyp_id: str,
    *,
    decision_kind: str,
    reason_code: str,
    transaction_id: str,
) -> ResearchEvent:
    return _event(
        record_id=f"DEC-{hyp_id}",
        kind=RecordKind.DECISION_EVENT,
        entity_id=f"DEC-{hyp_id}",
        hypothesis_version_id=hyp_id,
        payload={
            "decision_event_id": f"DEC-{hyp_id}",
            "hypothesis_version_id": hyp_id,
            "decision_kind": decision_kind,
            "reason_code": reason_code,
        },
        transaction_id=transaction_id,
    )


def _complete_session_receipt(*, transaction_id: str) -> ResearchEvent:
    payload = {
        "artifact_kind": "SESSION_RECEIPT",
        "session_id": CONTROL_SESSION,
        "payload_canonical": json.dumps(
            {
                "session_id": CONTROL_SESSION,
                "session_state": "SYNTHESIS_COMPLETE",
                "evidence_epoch_sha256": "ab" * 32,
                "focus_key_sha256": "cd" * 32,
                "search_key_sha256": "ef" * 32,
                "prompt_version": PROMPT_VERSION,
                "critic_terminal": "KILL_STATISTICALLY_UNIDENTIFIABLE",
                "final_session_terminal": "KILL_DATA_INFEASIBLE",
                "owner_focus": "AUTO",
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        "payload_sha256": "11" * 32,
        "research_artifact_id": f"HFIC-ART-SESSION-{CONTROL_SESSION}",
        "hfic_protocol": "HFIC-V1.2",
    }
    return _event(
        record_id=f"ART-SESSION-{CONTROL_SESSION}",
        kind=RecordKind.RESEARCH_ARTIFACT,
        entity_id=CONTROL_SESSION,
        payload=payload,
        transaction_id=transaction_id,
    )


class ForgePriorContextCapacityRepairTests(unittest.TestCase):
    def test_t1_legacy_capsule_oversize_on_fat_priors(self) -> None:
        """Old Critic-grade capsule projection exceeds the Forge packet bound."""
        with tempfile.TemporaryDirectory() as raw:
            store = ResearchStore(Path(raw))
            txn = "RESEARCH-TXN-CAPACITY-T1"
            store.append(
                [_fat_hfic_candidate(i, transaction_id=txn) for i in range(1, 6)]
                + [_complete_session_receipt(transaction_id=txn)],
                transaction_id=txn,
            )
            payloads = list(iter_search_memory_hypothesis_payloads(store))
            ranked = [str(item["hypothesis_version_id"]) for item in payloads][:5]
            with patch(
                "solana_alpha_lab.factory.hfic_reopened_prior_routing.compact_forge_prior_entry",
                compact_prior_entry,
            ):
                entries = ranked_prior_entries_for_ids(ranked, payloads)
            prior_bytes = len(canonical_json_bytes(entries))
            # Five fat Critic capsules alone already approach/exceed the Forge budget.
            self.assertGreater(prior_bytes, 9000)

    def test_t2_t3_forge_projection_fits_one_to_one(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            data_root = Path(raw)
            store = ResearchStore(data_root)
            txn = "RESEARCH-TXN-CAPACITY-T2"
            extras = [item["payload"] for item in resolve_all_reopened_priors(ROOT)]
            events = [_fat_hfic_candidate(i, transaction_id=txn) for i in range(1, 6)] + [
                _event(
                    record_id=f"REC-{payload['hypothesis_version_id']}",
                    kind=RecordKind.HYPOTHESIS_VERSION,
                    entity_id=str(payload["hypothesis_version_id"]),
                    payload=dict(payload),
                    transaction_id=txn,
                    hypothesis_version_id=str(payload["hypothesis_version_id"]),
                )
                for payload in extras
            ]
            store.append(events, transaction_id=txn)
            payloads = list(iter_search_memory_hypothesis_payloads(store))
            epoch = "aa" * 32
            focus_key = focus_key_sha256(FOCUS)
            search_key = search_key_sha256(epoch, FOCUS, PROMPT_VERSION, "bb" * 32, None)
            packet, _digest = build_forge_context_packet(
                ROOT,
                data_root,
                owner_focus=FOCUS,
                evidence_epoch=epoch,
                search_key=search_key,
                commissioning_status="FAST_LANE_COMMISSIONED",
                research_memory_as_of="2026-09-16T00:00:00Z",
                store=store,
                persist=False,
                search_payloads=payloads,
            )
            encoded = canonical_json_bytes(packet)
            self.assertLessEqual(len(encoded), ORDINARY_FORGE_MAX_PACKET_BYTES)
            self.assertEqual(
                packet["truncation_receipt"]["max_packet_bytes"],
                ORDINARY_FORGE_MAX_PACKET_BYTES,
            )
            ranked = packet["ranked_prior_candidate_ids"]
            entries = packet["ranked_prior_entries"]
            self.assertEqual(len(ranked), len(entries))
            self.assertEqual(
                {item["hypothesis_version_id"] for item in entries},
                set(ranked),
            )
            self.assertLessEqual(len(ranked), MAX_RANKED_PRIORS)
            self.assertEqual(packet["vision_integrity"]["status"], "PASS")
            self.assertNotIn("related_prior_recipe_ids", packet)
            self.assertEqual(
                packet["prior_work_receipts"],
                [
                    "QUERY-HFIC-EXACT-RELATED-PRIOR-001",
                    "QUERY-HFIC-SESSION-BY-SEARCH-KEY-001",
                    "QUERY-HFIC-PENDING-SESSION-001",
                ],
            )
            # Budget constants unchanged.
            self.assertEqual(AUTO_SESSIONS_PER_EPOCH, 1)
            self.assertEqual(MAX_DISTINCT_FOCUSES_PER_EPOCH, 3)
            sessions = [
                {
                    "session_id": CONTROL_SESSION,
                    "session_state": "SYNTHESIS_COMPLETE",
                    "evidence_epoch_sha256": epoch,
                    "focus_key_sha256": "cd" * 32,
                    "search_key_sha256": "ef" * 32,
                    "owner_focus": "AUTO",
                    "memory_eligibility_sha256": "bb" * 32,
                }
            ]
            action, _sid = decide_preflight_action(
                sessions,
                evidence_epoch=epoch,
                focus_key=focus_key,
                search_key=search_key,
                owner_focus=FOCUS,
                memory_eligibility_sha256="bb" * 32,
            )
            self.assertEqual(action, "START_NEW_SESSION")

    def test_t4_legacy_h11_h13_remain_decision_useful(self) -> None:
        resolved = resolve_all_reopened_priors(ROOT)
        by_id = {
            str(item["hypothesis_version_id"]): item["payload"] for item in resolved
        }
        self.assertIn("HYP-RC002-H11-LIFECYCLE-CLOCK-V1", by_id)
        self.assertIn("RC001-H13-COMPOSITE-VETO", by_id)
        for hyp_id, payload in by_id.items():
            forge = compact_forge_prior_entry(hyp_id, payload)
            critic = compact_prior_entry(hyp_id, payload)
            self.assertEqual(forge["hypothesis_version_id"], hyp_id)
            self.assertIn("legacy_definition", forge)
            self.assertIn("legacy_definition", critic)
            legacy = forge["legacy_definition"]
            self.assertTrue(
                any(
                    str(legacy.get(key) or "").strip()
                    for key in (
                        "primary_question",
                        "falsifier",
                        "frozen_definition_id",
                        "park_terminal",
                    )
                )
            )

    def test_t5_critic_prior_memory_unchanged_vs_forge_projection(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = ResearchStore(Path(raw))
            txn = "RESEARCH-TXN-CAPACITY-T5"
            store.append(
                [
                    _fat_hfic_candidate(1, transaction_id=txn),
                    _fat_hfic_candidate(2, transaction_id=txn),
                ],
                transaction_id=txn,
            )
            snapshot = build_prior_memory_snapshot(
                store,
                store_inventory_digest=store.diagnostics().committed_inventory_sha256,
                repo_root=ROOT,
            )
            payloads = list(iter_search_memory_hypothesis_payloads(store))
            forge_ids = {
                compact_forge_prior_entry(
                    str(item["hypothesis_version_id"]), item
                )["hypothesis_version_id"]
                for item in payloads
            }
            critic_ids = {
                item["hypothesis_version_id"] for item in snapshot["capsules"]
            }
            self.assertEqual(forge_ids, critic_ids)
            for capsule in snapshot["capsules"]:
                # Critic capsule still carries the full field set.
                self.assertIn("population", capsule)
                self.assertIn("negative_control", capsule)
                self.assertIn("session_id", capsule)

    def test_t6_missing_body_still_incomplete(self) -> None:
        with self.assertRaises(ReopenedPriorRoutingError) as raised:
            ranked_prior_entries_for_ids(["MISSING-ID"], [])
        self.assertEqual(str(raised.exception), BODY_INCOMPLETE)

    def test_t6b_population_only_source_not_mislabeled_incomplete(self) -> None:
        """Source useful only via Critic-rich fields must not raise BODY_INCOMPLETE."""
        payload = {
            "hypothesis_version_id": "HFIC-CAND-POP-ONLY",
            "session_id": "HFIC-SESS-POP",
            "hfic_protocol": "HFIC_V1_2",
            "definition_sha256": "ab" * 32,
            "population": "yield-eligible members with sparse Y coverage",
            "claim": "",
            "mechanism": "",
            "actor_counterparty": "",
            "primary_x_family": "",
            "primary_y": "",
            "cheapest_falsifier": "",
        }
        entries = ranked_prior_entries_for_ids(
            ["HFIC-CAND-POP-ONLY"],
            [payload],
        )
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["hypothesis_version_id"], "HFIC-CAND-POP-ONLY")
        self.assertEqual(
            entries[0]["population"],
            "yield-eligible members with sparse Y coverage",
        )
        forge = compact_forge_prior_entry("HFIC-CAND-POP-ONLY", payload)
        self.assertIn("population", forge)
        critic = compact_prior_entry("HFIC-CAND-POP-ONLY", payload)
        self.assertIn("population", critic)
        self.assertIn("session_id", critic)

    def test_t7_capacity_terminal_distinct_from_missing_body(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = ResearchStore(Path(raw))
            txn = "RESEARCH-TXN-CAPACITY-T7"
            store.append(
                [_fat_hfic_candidate(i, transaction_id=txn) for i in range(1, 6)],
                transaction_id=txn,
            )
            payloads = list(iter_search_memory_hypothesis_payloads(store))
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.ORDINARY_FORGE_MAX_PACKET_BYTES",
                64,
            ):
                with self.assertRaises(HficPreflightError) as raised:
                    build_forge_context_packet(
                        ROOT,
                        Path(raw),
                        owner_focus=FOCUS,
                        evidence_epoch="aa" * 32,
                        search_key="bb" * 32,
                        commissioning_status="FAST_LANE_COMMISSIONED",
                        research_memory_as_of="2026-09-16T00:00:00Z",
                        store=store,
                        persist=False,
                        search_payloads=payloads,
                    )
            self.assertEqual(
                str(raised.exception),
                "FORGE_CONTEXT_PACKET_CAPACITY_EXCEEDED",
            )
            self.assertNotEqual(str(raised.exception), BODY_INCOMPLETE)

    def test_minimal_forge_context_exceeds_bound_when_scope_required(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = ResearchStore(Path(raw))
            txn = "RESEARCH-TXN-MINIMAL-BOUND"
            hyp = _fat_hfic_candidate(1, transaction_id=txn)
            store.append(
                [
                    hyp,
                    _decision_event(
                        "HFIC-CAND-FAT0001DEADBEEF",
                        decision_kind="REJECT",
                        reason_code="KILL_DATA_INFEASIBLE",
                        transaction_id=txn,
                    ),
                ],
                transaction_id=txn,
            )
            payloads = list(iter_search_memory_hypothesis_payloads(store))
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.ORDINARY_FORGE_MAX_PACKET_BYTES",
                2500,
            ):
                with self.assertRaises(HficPreflightError) as raised:
                    build_forge_context_packet(
                        ROOT,
                        Path(raw),
                        owner_focus=FOCUS,
                        evidence_epoch="aa" * 32,
                        search_key="bb" * 32,
                        commissioning_status="FAST_LANE_COMMISSIONED",
                        research_memory_as_of="2026-09-16T00:00:00Z",
                        store=store,
                        persist=False,
                        search_payloads=payloads,
                    )
            self.assertEqual(
                str(raised.exception),
                "MINIMAL_FORGE_CONTEXT_EXCEEDS_BOUND",
            )
            self.assertNotEqual(str(raised.exception), BODY_INCOMPLETE)

    def test_mode_scoped_packet_bounds(self) -> None:
        from solana_alpha_lab.factory.hfic_control_integrity import (
            CURRENT_REPRESENTATION_CONTROL_V1,
        )

        self.assertEqual(forge_context_packet_max_bytes(None), 20480)
        self.assertEqual(forge_context_packet_max_bytes(""), 20480)
        self.assertEqual(
            forge_context_packet_max_bytes(CURRENT_REPRESENTATION_CONTROL_V1),
            16384,
        )
        self.assertEqual(MAX_PACKET_BYTES, 16384)
        self.assertEqual(ORDINARY_FORGE_MAX_PACKET_BYTES, 20480)

    def test_ordinary_exceeds_20kib_still_capacity_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = ResearchStore(Path(raw))
            txn = "RESEARCH-TXN-ORDINARY-20K"
            events = [_fat_hfic_candidate(i, transaction_id=txn) for i in range(1, 9)]
            for i in range(1, 3):
                events.append(
                    _decision_event(
                        f"HFIC-CAND-FAT{i:04d}DEADBEEF",
                        decision_kind="REJECT",
                        reason_code="KILL_DATA_INFEASIBLE",
                        transaction_id=txn,
                    )
                )
            store.append(events, transaction_id=txn)
            payloads = list(iter_search_memory_hypothesis_payloads(store))
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.ORDINARY_FORGE_MAX_PACKET_BYTES",
                4000,
            ):
                with self.assertRaises(HficPreflightError) as raised:
                    build_forge_context_packet(
                        ROOT,
                        Path(raw),
                        owner_focus=FOCUS,
                        evidence_epoch="aa" * 32,
                        search_key="bb" * 32,
                        commissioning_status="FAST_LANE_COMMISSIONED",
                        research_memory_as_of="2026-09-16T00:00:00Z",
                        store=store,
                        persist=False,
                        search_payloads=payloads,
                    )
            self.assertIn(
                str(raised.exception),
                {
                    "FORGE_CONTEXT_PACKET_CAPACITY_EXCEEDED",
                    "MINIMAL_FORGE_CONTEXT_EXCEEDS_BOUND",
                    "FORGE_VISION_INTEGRITY_BLOCKED",
                },
            )

    def test_decision_event_flows_into_forge_ranked_entries(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = ResearchStore(Path(raw))
            txn = "RESEARCH-TXN-DECISION-FORGE"
            selected = _fat_hfic_candidate(1, transaction_id=txn)
            runner = _fat_hfic_candidate(2, transaction_id=txn)
            portfolio = _fat_hfic_candidate(3, transaction_id=txn)
            store.append(
                [
                    selected,
                    runner,
                    portfolio,
                    _decision_event(
                        "HFIC-CAND-FAT0001DEADBEEF",
                        decision_kind="REJECT",
                        reason_code="KILL_STATISTICALLY_UNIDENTIFIABLE",
                        transaction_id=txn,
                    ),
                    _decision_event(
                        "HFIC-CAND-FAT0002DEADBEEF",
                        decision_kind="REJECT",
                        reason_code="KILL_DATA_INFEASIBLE",
                        transaction_id=txn,
                    ),
                    _decision_event(
                        "HFIC-CAND-FAT0003DEADBEEF",
                        decision_kind="PAUSE",
                        reason_code="NOT_SELECTED_IN_SESSION",
                        transaction_id=txn,
                    ),
                ],
                transaction_id=txn,
            )
            payloads = list(iter_search_memory_hypothesis_payloads(store))
            ranked = [
                "HFIC-CAND-FAT0001DEADBEEF",
                "HFIC-CAND-FAT0002DEADBEEF",
                "HFIC-CAND-FAT0003DEADBEEF",
            ]
            entries = ranked_prior_entries_for_ids(ranked, payloads, store=store)
            by_id = {item["hypothesis_version_id"]: item for item in entries}
            self.assertEqual(
                by_id["HFIC-CAND-FAT0001DEADBEEF"]["reason_code"],
                "KILL_STATISTICALLY_UNIDENTIFIABLE",
            )
            self.assertEqual(
                by_id["HFIC-CAND-FAT0001DEADBEEF"]["memory_status"],
                MEMORY_HARD_CLOSE,
            )
            self.assertEqual(
                by_id["HFIC-CAND-FAT0002DEADBEEF"]["reason_code"],
                "KILL_DATA_INFEASIBLE",
            )
            self.assertEqual(
                by_id["HFIC-CAND-FAT0003DEADBEEF"]["reason_code"],
                "NOT_SELECTED_IN_SESSION",
            )
            self.assertEqual(
                by_id["HFIC-CAND-FAT0003DEADBEEF"]["memory_status"],
                MEMORY_NOT_SELECTED,
            )
            # Shared resolver matches Critic.
            decisions = latest_hypothesis_decisions(store)
            self.assertEqual(
                decisions["HFIC-CAND-FAT0001DEADBEEF"]["reason_code"],
                "KILL_STATISTICALLY_UNIDENTIFIABLE",
            )

    def test_hard_close_retains_scope_axes_for_anti_rediscovery(self) -> None:
        shared_mech = "same mechanism text for both scoped variants"
        shared_x = "SAME_X_FAMILY"
        shared_y = "SAME_Y"
        pop_a = "yield-eligible members in cohort A"
        pop_b = "yield-eligible members in cohort B"
        horizon_a = "H900 / 0.01 SOL"
        horizon_b = "H3600 / 1.0 SOL"
        payload_a = {
            "hypothesis_version_id": "HFIC-CAND-SCOPE-A",
            "hfic_protocol": "HFIC-V1.2",
            "mechanism": shared_mech,
            "claim": "scoped claim A",
            "population": pop_a,
            "decision_timestamp": "clock-A",
            "primary_x_family": shared_x,
            "primary_y": shared_y,
            "horizon_notional": horizon_a,
            "negative_control": "control-A",
            "cheapest_falsifier": "falsifier-A",
            "definition_sha256": "aa" * 32,
        }
        payload_b = {
            **payload_a,
            "hypothesis_version_id": "HFIC-CAND-SCOPE-B",
            "population": pop_b,
            "decision_timestamp": "clock-B",
            "horizon_notional": horizon_b,
            "negative_control": "control-B",
            "definition_sha256": "bb" * 32,
        }
        decision = {
            "decision_kind": "REJECT",
            "reason_code": "KILL_MECHANISM",
        }
        forge_a = compact_forge_prior_entry(
            "HFIC-CAND-SCOPE-A", payload_a, decision
        )
        forge_b = compact_forge_prior_entry(
            "HFIC-CAND-SCOPE-B", payload_b, decision
        )
        self.assertEqual(forge_a["memory_status"], MEMORY_HARD_CLOSE)
        self.assertEqual(forge_a["population"], pop_a)
        self.assertEqual(forge_a["horizon_notional"], horizon_a)
        self.assertEqual(forge_a["negative_control"], "control-A")
        self.assertEqual(forge_a["decision_timestamp"], "clock-A")
        self.assertEqual(forge_b["population"], pop_b)
        self.assertEqual(forge_b["horizon_notional"], horizon_b)
        # Same mechanism must not collapse to an unscoped close.
        self.assertEqual(forge_a["mechanism"], forge_b["mechanism"])
        self.assertNotEqual(forge_a["population"], forge_b["population"])
        self.assertNotEqual(forge_a["horizon_notional"], forge_b["horizon_notional"])

    def test_not_selected_may_omit_scope_when_lean_distinguisher_exists(self) -> None:
        payload = {
            "hypothesis_version_id": "HFIC-CAND-NS",
            "hfic_protocol": "HFIC-V1.2",
            "mechanism": "portfolio runner mechanism text",
            "population": "should-omit-for-not-selected",
            "decision_timestamp": "should-omit-ts",
            "horizon_notional": "should-omit-horizon",
            "negative_control": "should-omit-nc",
            "primary_x_family": "X_NS",
            "primary_y": "Y_NS",
            "definition_sha256": "cc" * 32,
        }
        forge = compact_forge_prior_entry(
            "HFIC-CAND-NS",
            payload,
            {"decision_kind": "PAUSE", "reason_code": "NOT_SELECTED_IN_SESSION"},
        )
        self.assertEqual(forge["memory_status"], MEMORY_NOT_SELECTED)
        self.assertEqual(forge["mechanism"], "portfolio runner mechanism text")
        self.assertNotIn("population", forge)
        self.assertNotIn("horizon_notional", forge)

    def test_critic_snapshot_unchanged_with_forge_decision_wiring(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = ResearchStore(Path(raw))
            txn = "RESEARCH-TXN-CRITIC-UNCHANGED"
            hyp = _fat_hfic_candidate(1, transaction_id=txn)
            store.append(
                [
                    hyp,
                    _decision_event(
                        "HFIC-CAND-FAT0001DEADBEEF",
                        decision_kind="REJECT",
                        reason_code="KILL_DATA_INFEASIBLE",
                        transaction_id=txn,
                    ),
                ],
                transaction_id=txn,
            )
            snapshot = build_prior_memory_snapshot(
                store,
                store_inventory_digest=store.diagnostics().committed_inventory_sha256,
                repo_root=ROOT,
            )
            capsule = snapshot["capsules"][0]
            self.assertEqual(capsule["reason_code"], "KILL_DATA_INFEASIBLE")
            self.assertIn("session_id", capsule)
            self.assertIn("population", capsule)
            self.assertIn("hfic_protocol", capsule)
            forge = compact_forge_prior_entry(
                capsule["hypothesis_version_id"],
                {
                    "hypothesis_version_id": capsule["hypothesis_version_id"],
                    "session_id": capsule["session_id"],
                    "hfic_protocol": capsule["hfic_protocol"],
                    "mechanism": capsule["mechanism"],
                    "claim": capsule.get("claim"),
                    "population": capsule["population"],
                    "decision_timestamp": capsule["decision_timestamp"],
                    "primary_x_family": capsule["primary_x_family"],
                    "primary_y": capsule["primary_y"],
                    "horizon_notional": capsule["horizon_notional"],
                    "negative_control": capsule["negative_control"],
                    "cheapest_falsifier": capsule["cheapest_falsifier"],
                    "definition_sha256": capsule["definition_sha256"],
                },
                {
                    "decision_kind": capsule["decision_kind"],
                    "reason_code": capsule["reason_code"],
                },
            )
            # Critic remains richer than Forge; Forge still gets kill + scope.
            self.assertIn("session_id", capsule)
            self.assertNotIn("session_id", forge)
            self.assertEqual(forge["reason_code"], "KILL_DATA_INFEASIBLE")
            self.assertEqual(forge["population"], capsule["population"])

    def test_park_historical_semantics_preserved_on_forge(self) -> None:
        payload = {
            "hypothesis_version_id": "HYP-RC002-H11-LIFECYCLE-CLOCK-V1",
            "legacy_definition": {
                "primary_question": "lifecycle clock park question",
                "park_terminal": "PARK_FAMILY",
                "falsifier": "offline park falsifier",
            },
            "definition_sha256": "dd" * 32,
        }
        forge = compact_forge_prior_entry(
            "HYP-RC002-H11-LIFECYCLE-CLOCK-V1",
            payload,
            {"decision_kind": "PARK", "reason_code": "PARK_FAMILY"},
        )
        critic = compact_prior_entry(
            "HYP-RC002-H11-LIFECYCLE-CLOCK-V1",
            payload,
            {"decision_kind": "PARK", "reason_code": "PARK_FAMILY"},
        )
        self.assertEqual(forge["memory_status"], MEMORY_PARK)
        self.assertEqual(critic["memory_status"], MEMORY_PARK)
        self.assertIn("legacy_definition", forge)
        self.assertEqual(forge.get("reason_code"), "PARK_FAMILY")


if __name__ == "__main__":
    unittest.main()
