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

from jsonschema import Draft202012Validator
from solana_alpha_lab.factory.hfic_identity import IDENTITY_FIELDS, normalize_text
from solana_alpha_lab.factory.hfic_preflight import MAX_RANKED_PRIORS, rank_prior_candidate_ids
from solana_alpha_lab.factory.hfic_prior_memory import (
    MEMORY_AMBIGUOUS,
    MEMORY_HARD_CLOSE,
    MEMORY_HISTORICAL,
    MEMORY_NOT_SELECTED,
    MEMORY_PARK,
    PriorMemoryCapacityError,
    PriorMemoryUnidentifiedError,
    build_prior_memory_snapshot,
)
from solana_alpha_lab.factory.hfic_session import HficSessionError, freeze_draft, lookup_prior
from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent, ResearchStore
from tests.test_hfic_cli import bind_draft, run_cli
from tests.test_hfic_session import valid_draft
from tests.test_hypothesis_forge_independent_critic_v1 import CRITIC_PACKET_FIXTURE

HAPPY = ROOT / "tests/fixtures/hypothesis_forge/draft_v1_2_valid.json"
CRITIC_SCHEMA = ROOT / "catalog/schemas/hypothesis_critic_input_v1.schema.json"
P_TRUE_ID = "HYP-PTRUE-SEED-CIRCLE-001"
HARD_CLOSE_ID = "HYP-MEM-HARD-CLOSE-001"
PARK_ID = "HYP-MEM-PARK-001"
NOT_SELECTED_ID = "HYP-MEM-NOT-SELECTED-001"
AMBIGUOUS_ID = "HYP-MEM-AMBIGUOUS-001"
HISTORICAL_ID = "HYP-MEM-HISTORICAL-001"
DECOY_IDS = [f"HYP-DECOY-0{index}-TAKER-LIQ" for index in range(1, 9)]

H_CARD = {
    "claim": (
        "Creator-linked wallets accumulate inventory before public mint visibility "
        "then dump into first-wave retail"
    ),
    "mechanism": (
        "Creator-linked wallets accumulate inventory before public mint visibility "
        "then dump into first-wave retail flow"
    ),
    "actor_counterparty": "insider-linked wallets versus first public buyers",
    "population": "early pumpfun mints aged 300-899 seconds",
    "decision_timestamp": "first public quote after bonding-curve visibility",
    "primary_x_family": "CREATOR_PRE_LAUNCH_INVENTORY_SHADOW",
    "primary_y": "MARKET_EXECUTION_UNAVAILABLE",
    "horizon_notional": "H900 / 0.01 SOL quote-only reverse sell",
    "negative_control": "matched mints without creator-linked pre-visibility accumulation",
    "cheapest_falsifier": (
        "stratified H900 MEU by creator-linked pre-visibility inventory bucket on offline panel"
    ),
}
P_TRUE_CARD = {
    "claim": (
        "Affiliated seed-circle wallets stockpile tokens before listing then exit "
        "into naive demand"
    ),
    "mechanism": (
        "Affiliated seed-circle wallets stockpile tokens before listing then exit "
        "into naive demand"
    ),
    "actor_counterparty": "clustered insiders versus uninformed listing-wave takers",
    "population": "newly listed pumpfun tokens in the first 5-15 minutes",
    "decision_timestamp": "first public pool quote after graduation",
    "primary_x_family": "AFFILIATED_PRE_LISTING_STOCKPILE",
    "primary_y": "EXIT_ROUTE_WITHDRAWAL",
    "horizon_notional": "fifteen-minute horizon at one-hundredth SOL intended notional",
    "negative_control": "matched listings without affiliated pre-listing stockpile",
    "cheapest_falsifier": (
        "offline bucket test of exit withdrawal by affiliated pre-listing stockpile intensity"
    ),
}


def _event(
    *,
    record_id: str,
    kind: RecordKind,
    entity_id: str,
    payload: dict[str, object],
    created: datetime,
    hypothesis_version_id: str | None = None,
    transaction_id: str = "RESEARCH-TXN-PRIOR-MEM-001",
) -> ResearchEvent:
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return ResearchEvent(
        record_id=record_id,
        record_kind=kind,
        entity_id=entity_id,
        hypothesis_version_id=hypothesis_version_id,
        run_id=None,
        transaction_id=transaction_id,
        effective_at=created,
        first_reliable_available_at=created,
        supersedes_record_id=None,
        payload_json=payload_json,
        payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        schema_version="1.0",
        producer_capability_id="CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
        producer_git_sha="0" * 40,
        created_at=created,
    )


def _hyp_payload(hyp_id: str, card: dict[str, str], *, protocol: str | None) -> dict[str, object]:
    payload: dict[str, object] = {
        "hypothesis_version_id": hyp_id,
        "claim": card["claim"],
        "statement": card["claim"],
        "mechanism": card["mechanism"],
        "actor_counterparty": card["actor_counterparty"],
        "population": card["population"],
        "decision_timestamp": card["decision_timestamp"],
        "primary_x_family": card["primary_x_family"],
        "primary_y": card["primary_y"],
        "horizon_notional": card["horizon_notional"],
        "negative_control": card["negative_control"],
        "cheapest_falsifier": card["cheapest_falsifier"],
        "falsifier": card["cheapest_falsifier"],
        "definition_sha256": "ab" * 32,
    }
    if protocol:
        payload["hfic_protocol"] = protocol
        payload["session_id"] = "HFIC-SESS-PRIORSEED0001"
    return payload


def _decoy_card(index: int) -> dict[str, str]:
    blob = (
        f"taker volume mix valuation liquidity divergence decoy {index:02d} "
        "predicts later MEU without insider cluster"
    )
    return {
        "claim": blob,
        "mechanism": blob,
        "actor_counterparty": "taker flow versus residual liquidity",
        "population": "early taker-volume mix panel",
        "decision_timestamp": "frozen T+5 taker mix clock",
        "primary_x_family": "R0_TAKER_VOLUME_MIX",
        "primary_y": "MARKET_EXECUTION_UNAVAILABLE",
        "horizon_notional": "H16 taker-mix notional 1 SOL",
        "negative_control": "matched mix without taker divergence",
        "cheapest_falsifier": "offline taker mix bucket table",
    }


def seed_adversarial_store(store: ResearchStore, created: datetime | None = None) -> None:
    now = created or datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
    records = [
        _event(
            record_id=f"REC-{P_TRUE_ID}",
            kind=RecordKind.HYPOTHESIS_VERSION,
            entity_id=P_TRUE_ID,
            hypothesis_version_id=P_TRUE_ID,
            payload=_hyp_payload(P_TRUE_ID, P_TRUE_CARD, protocol="HFIC-V1.1"),
            created=now,
        )
    ]
    for index, hyp_id in enumerate(DECOY_IDS, start=1):
        records.append(
            _event(
                record_id=f"REC-{hyp_id}",
                kind=RecordKind.HYPOTHESIS_VERSION,
                entity_id=hyp_id,
                hypothesis_version_id=hyp_id,
                payload=_hyp_payload(hyp_id, _decoy_card(index), protocol="HFIC-V1.1"),
                created=now,
            )
        )
    semantics = (
        (HARD_CLOSE_ID, "REJECT", "KILL_MECHANISM", "HFIC-V1.1"),
        (PARK_ID, "PARK", "PARK_FAMILY", "HFIC-V1.1"),
        (NOT_SELECTED_ID, "PAUSE", "NOT_SELECTED_IN_SESSION", "HFIC-V1.1"),
        (AMBIGUOUS_ID, None, None, "HFIC-V1.1"),
        (HISTORICAL_ID, None, None, None),
    )
    for hyp_id, kind, reason, protocol in semantics:
        card = {
            "claim": f"{hyp_id} visible prior claim",
            "mechanism": f"{hyp_id} visible prior mechanism",
            "actor_counterparty": f"{hyp_id} actor",
            "population": f"{hyp_id} population",
            "decision_timestamp": "historical decision clock",
            "primary_x_family": f"{hyp_id}_X",
            "primary_y": "MARKET_EXECUTION_UNAVAILABLE",
            "horizon_notional": "H900 / 0.01 SOL",
            "negative_control": f"{hyp_id} control",
            "cheapest_falsifier": f"{hyp_id} falsifier",
        }
        records.append(
            _event(
                record_id=f"REC-{hyp_id}",
                kind=RecordKind.HYPOTHESIS_VERSION,
                entity_id=hyp_id,
                hypothesis_version_id=hyp_id,
                payload=_hyp_payload(hyp_id, card, protocol=protocol),
                created=now,
            )
        )
        if kind is not None and reason is not None:
            records.append(
                _event(
                    record_id=f"DEC-{hyp_id}",
                    kind=RecordKind.DECISION_EVENT,
                    entity_id=f"DEC-{hyp_id}",
                    hypothesis_version_id=hyp_id,
                    payload={
                        "decision_event_id": f"DEC-{hyp_id}",
                        "hypothesis_version_id": hyp_id,
                        "decision_kind": kind,
                        "reason_code": reason,
                    },
                    created=now,
                    transaction_id="RESEARCH-TXN-PRIOR-MEM-001",
                )
            )
    store.append(records, transaction_id="RESEARCH-TXN-PRIOR-MEM-001")


def h_draft_from_happy(receipt: dict) -> dict:
    draft = bind_draft(json.loads(HAPPY.read_text(encoding="utf-8")), receipt)
    selected = dict(draft["candidates"][0])
    selected.update(H_CARD)
    selected["material_difference_from_prior"] = (
        "Uses creator-linked pre-visibility inventory rather than taker-mix decoys."
    )
    draft["candidates"] = [selected, *draft["candidates"][1:]]
    return draft


_MATERIAL_SELECTED = (
    ("claim", "claim"),
    ("mechanism", "mechanism"),
    ("actor_counterparty", "actor_counterparty"),
    ("population", "population"),
    ("decision_timestamp", "decision_timestamp"),
    ("primary_x", "primary_x_family"),
    ("cheapest_falsifier", "cheapest_falsifier"),
)


def packet_only_considered_prior_ids(packet: dict) -> list[str]:
    """Packet-only material comparison. No ResearchStore, no RDP, no synonym CLI."""
    selected = packet["selected_candidate"]
    scored: list[tuple[int, str]] = []
    for capsule in packet["prior_memory"]["capsules"]:
        score = 0
        for selected_field, capsule_field in _MATERIAL_SELECTED:
            left = str(selected.get(selected_field) or "")
            right = str(capsule.get(capsule_field) or "")
            if not left or not right:
                continue
            score += len(set(normalize_text(left).split()) & set(normalize_text(right).split()))
        scored.append((score, str(capsule["hypothesis_version_id"])))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [hyp_id for score, hyp_id in scored if score > 0]


class PriorMemoryUnitTests(unittest.TestCase):
    def test_ranker_constants_unchanged(self) -> None:
        self.assertEqual(MAX_RANKED_PRIORS, 8)

    def test_identity_fields_are_lexically_disjoint(self) -> None:
        for field in IDENTITY_FIELDS:
            self.assertNotEqual(normalize_text(H_CARD[field]), normalize_text(P_TRUE_CARD[field]))

    def test_t1_forge_shortlist_still_blind(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            seed_adversarial_store(store)
            ranked, dropped = rank_prior_candidate_ids(
                store,
                owner_focus="AUTO",
                feature_hints=["R0_TAKER_VOLUME_MIX"],
            )
            self.assertEqual(len(ranked), MAX_RANKED_PRIORS)
            self.assertNotIn(P_TRUE_ID, ranked)
            self.assertEqual(set(ranked), set(DECOY_IDS))
            self.assertGreaterEqual(dropped, 1)
            matches = lookup_prior(store, candidate=H_CARD, query=None)
            hit_ids = {
                str(item.get("candidate_id") or item.get("hypothesis_version_id") or "")
                for item in matches.get("matches") or []
            }
            self.assertNotIn(P_TRUE_ID, hit_ids)

    def test_t5_builder_capacity_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            seed_adversarial_store(store)
            digest = store.diagnostics().committed_inventory_sha256
            with self.assertRaises(PriorMemoryCapacityError) as raised:
                build_prior_memory_snapshot(
                    store,
                    store_inventory_digest=digest,
                    max_records=2,
                )
            self.assertEqual(raised.exception.code, "PRIOR_MEMORY_CONTEXT_CAPACITY_EXCEEDED")
            self.assertGreater(raised.exception.eligible_count, 2)
            self.assertEqual(raised.exception.emitted_count, 0)

    def test_t6_memory_statuses_remain_distinct(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            seed_adversarial_store(store)
            snapshot = build_prior_memory_snapshot(
                store,
                store_inventory_digest=store.diagnostics().committed_inventory_sha256,
            )
            by_id = {
                item["hypothesis_version_id"]: item["memory_status"]
                for item in snapshot["capsules"]
            }
            self.assertEqual(by_id[HARD_CLOSE_ID], MEMORY_HARD_CLOSE)
            self.assertEqual(by_id[PARK_ID], MEMORY_PARK)
            self.assertEqual(by_id[NOT_SELECTED_ID], MEMORY_NOT_SELECTED)
            self.assertEqual(by_id[AMBIGUOUS_ID], MEMORY_AMBIGUOUS)
            self.assertEqual(by_id[HISTORICAL_ID], MEMORY_HISTORICAL)
            self.assertEqual(len(set(by_id.values())), 5)

    def test_unidentified_hypothesis_version_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            now = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
            payload_json = "[]"
            store.append(
                [
                    ResearchEvent(
                        record_id="REC-UNIDENTIFIED",
                        record_kind=RecordKind.HYPOTHESIS_VERSION,
                        entity_id="HYP-BROKEN-JSON-001",
                        hypothesis_version_id="HYP-BROKEN-JSON-001",
                        run_id=None,
                        transaction_id="RESEARCH-TXN-PRIOR-MEM-001",
                        effective_at=now,
                        first_reliable_available_at=now,
                        supersedes_record_id=None,
                        payload_json=payload_json,
                        payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
                        schema_version="1.0",
                        producer_capability_id="CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
                        producer_git_sha="0" * 40,
                        created_at=now,
                    )
                ],
                transaction_id="RESEARCH-TXN-PRIOR-MEM-001",
            )
            with self.assertRaises(PriorMemoryUnidentifiedError) as raised:
                build_prior_memory_snapshot(
                    store,
                    store_inventory_digest=store.diagnostics().committed_inventory_sha256,
                )
            self.assertEqual(raised.exception.code, "PRIOR_MEMORY_RECORD_UNIDENTIFIED")

    def test_t7_historical_packets_remain_readable(self) -> None:
        schema = json.loads(CRITIC_SCHEMA.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        v10 = json.loads(CRITIC_PACKET_FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(list(validator.iter_errors(v10)), [])
        v11 = dict(v10)
        v11["packet_version"] = "1.1"
        v11["generator_prompt_version"] = "HFIC-V1.1"
        v11["session_id"] = "HFIC-SESS-HISTORICAL001"
        self.assertNotIn("prior_memory", v11)
        self.assertEqual(list(validator.iter_errors(v11)), [])
        v12 = dict(v11)
        v12["packet_version"] = "1.2"
        v12["generator_prompt_version"] = "HFIC-V1.2"
        self.assertNotIn("prior_memory", v12)
        self.assertEqual(list(validator.iter_errors(v12)), [])
        frozen = freeze_draft(
            valid_draft(),
            preflight_receipt={"receipt_id": "HFIC-PREFLIGHT-FIXTURE-001"},
            repo_root=ROOT,
        )
        packet = frozen["critic_input_packet"]
        self.assertEqual(packet["packet_version"], "1.1")
        self.assertNotIn("prior_memory", packet)
        self.assertEqual(list(validator.iter_errors(packet)), [])

    def test_historical_v12_without_prior_memory_readable(self) -> None:
        schema = json.loads(CRITIC_SCHEMA.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        v10 = json.loads(CRITIC_PACKET_FIXTURE.read_text(encoding="utf-8"))
        historical = dict(v10)
        historical["packet_version"] = "1.2"
        historical["generator_prompt_version"] = "HFIC-V1.2"
        historical["session_id"] = "HFIC-SESS-HISTORICALV12"
        self.assertNotIn("prior_memory", historical)
        self.assertEqual(list(validator.iter_errors(historical)), [])
        from solana_alpha_lab.factory.hfic_prior_memory import empty_prior_memory_snapshot

        with_memory = dict(historical)
        with_memory["prior_memory"] = empty_prior_memory_snapshot(
            store_inventory_digest="0" * 64
        )
        self.assertEqual(list(validator.iter_errors(with_memory)), [])


class PriorMemoryFreezeE2ETests(unittest.TestCase):
    def test_t2_t3_t4_t5_freeze_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            first = run_cli(
                "preflight",
                "--owner-focus",
                "AUTO",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            store = ResearchStore(data_root)
            seed_adversarial_store(store)
            second = run_cli(
                "preflight",
                "--owner-focus",
                "AUTO",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(second.returncode, 0, second.stderr)
            receipt = json.loads(second.stdout)
            ranked = receipt["forge_context_packet"]["ranked_prior_candidate_ids"]
            self.assertNotIn(P_TRUE_ID, ranked)
            self.assertLessEqual(len(ranked), MAX_RANKED_PRIORS)

            draft = h_draft_from_happy(receipt)
            receipt_path = Path(tmp) / "preflight.json"
            draft_path = Path(tmp) / "draft.json"
            receipt_path.write_text(second.stdout, encoding="utf-8")
            draft_path.write_text(json.dumps(draft), encoding="utf-8")

            stale_store = ResearchStore(data_root)
            stale_store.append(
                [
                    _event(
                        record_id="REC-STALE-AFTER-PREFLIGHT",
                        kind=RecordKind.HYPOTHESIS_VERSION,
                        entity_id="HYP-STALE-AFTER-PREFLIGHT-001",
                        hypothesis_version_id="HYP-STALE-AFTER-PREFLIGHT-001",
                        payload=_hyp_payload(
                            "HYP-STALE-AFTER-PREFLIGHT-001",
                            _decoy_card(99),
                            protocol="HFIC-V1.1",
                        ),
                        created=datetime(2026, 9, 8, 13, 0, tzinfo=UTC),
                        transaction_id="RESEARCH-TXN-PRIOR-MEM-STALE",
                    )
                ],
                transaction_id="RESEARCH-TXN-PRIOR-MEM-STALE",
            )
            stale_freeze = run_cli(
                "freeze",
                "--draft",
                str(draft_path),
                "--preflight-receipt",
                str(receipt_path),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertNotEqual(stale_freeze.returncode, 0, stale_freeze.stdout)
            self.assertIn("PREFLIGHT_STORE_DIGEST_MISMATCH", stale_freeze.stderr)

            store_after_stale = ResearchStore(data_root)
            session_records = [
                record
                for record in store_after_stale.iter_committed_records()
                if str(getattr(record.record_kind, "value", record.record_kind))
                == RecordKind.RESEARCH_CYCLE.value
            ]
            self.assertEqual(session_records, [])

            fresh = run_cli(
                "preflight",
                "--owner-focus",
                "AUTO",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(fresh.returncode, 0, fresh.stderr)
            fresh_receipt = json.loads(fresh.stdout)
            self.assertNotIn(
                P_TRUE_ID,
                fresh_receipt["forge_context_packet"]["ranked_prior_candidate_ids"],
            )
            bound = h_draft_from_happy(fresh_receipt)
            fresh_receipt_path = Path(tmp) / "preflight_fresh.json"
            fresh_draft_path = Path(tmp) / "draft_fresh.json"
            fresh_receipt_path.write_text(fresh.stdout, encoding="utf-8")
            fresh_draft_path.write_text(json.dumps(bound), encoding="utf-8")

            with patch(
                "solana_alpha_lab.factory.hfic_prior_memory.prior_memory_bounds",
                return_value=(2, 65536),
            ):
                with self.assertRaises(HficSessionError) as raised:
                    freeze_draft(
                        bound,
                        preflight_receipt=fresh_receipt,
                        store=ResearchStore(data_root),
                        repo_root=ROOT,
                    )
            self.assertEqual(str(raised.exception), "PRIOR_MEMORY_CONTEXT_CAPACITY_EXCEEDED")
            store_after_cap = ResearchStore(data_root)
            self.assertEqual(
                [
                    record
                    for record in store_after_cap.iter_committed_records()
                    if str(getattr(record.record_kind, "value", record.record_kind))
                    == RecordKind.RESEARCH_CYCLE.value
                ],
                [],
            )

            store_before = ResearchStore(data_root)
            unique_before = {
                str(
                    json.loads(record.payload_json).get("hypothesis_version_id")
                    or getattr(record, "hypothesis_version_id", "")
                    or record.entity_id
                )
                for record in store_before.iter_committed_records()
                if str(getattr(record.record_kind, "value", record.record_kind))
                == RecordKind.HYPOTHESIS_VERSION.value
            }

            frozen_run = run_cli(
                "freeze",
                "--draft",
                str(fresh_draft_path),
                "--preflight-receipt",
                str(fresh_receipt_path),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(frozen_run.returncode, 0, frozen_run.stderr)
            frozen = json.loads(frozen_run.stdout)
            packet = frozen["critic_input_packet"]
            memory = packet["prior_memory"]
            self.assertTrue(memory["complete"])
            self.assertEqual(memory["eligible_count"], memory["emitted_count"])
            self.assertGreaterEqual(memory["eligible_count"], len(DECOY_IDS) + 1)
            ids = [item["hypothesis_version_id"] for item in memory["capsules"]]
            self.assertIn(P_TRUE_ID, ids)
            self.assertNotIn(frozen["selected_candidate_id"], ids)
            self.assertEqual(memory["eligible_count"], len(unique_before))
            self.assertEqual(set(ids), unique_before)
            self.assertEqual(
                memory["store_inventory_digest"],
                fresh_receipt["store_inventory_digest"],
            )
            self.assertEqual(packet["packet_version"], "1.4")
            self.assertEqual(packet["generator_prompt_version"], "HFIC-V1.2")
            self.assertTrue(memory["snapshot_sha256"])
            self.assertGreater(memory["bytes"], 0)

            packet_only = json.loads(json.dumps(packet))
            considered = packet_only_considered_prior_ids(packet_only)
            self.assertIn(P_TRUE_ID, considered)
            self.assertEqual(considered[0], P_TRUE_ID)
