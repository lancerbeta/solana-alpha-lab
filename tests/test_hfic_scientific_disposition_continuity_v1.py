"""FORGE_SCIENTIFIC_DISPOSITION_CONTINUITY_V1 acceptance on portable disposable stores.

Every store here is built by production writers (published corpus, preflight,
ordinary operation, discovery-execute) inside a temp directory. Values are
synthetic and are not market oracles; the checks are identity, basis, scope,
lineage and applicability. Fault-injection helpers append deliberately broken
disposition rows to simulate restored/corrupt history; they are labelled as such.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import threading
import unittest
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest import mock

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory import hfic_scientific_disposition as disp  # noqa: E402
from solana_alpha_lab.factory.hfic_grounded_discovery import list_discovery_looks  # noqa: E402
from solana_alpha_lab.factory.hfic_ordinary_operation import (  # noqa: E402
    RESERVATION_KIND,
    _iter_kind,
    list_operations,
    record_operation,
)
from solana_alpha_lab.factory.hfic_preflight import FORGE_OPERATIONAL_PACKET_MAX_BYTES  # noqa: E402
from solana_alpha_lab.factory.hfic_provenance import is_hfic_record  # noqa: E402
from solana_alpha_lab.factory.hfic_temporal_discovery import temporal_target_label  # noqa: E402
from solana_alpha_lab.factory.research_store import (  # noqa: E402
    RecordKind,
    ResearchEvent,
    ResearchStore,
)
from tests.test_hfic_cli import run_cli  # noqa: E402
from tests.test_hfic_ordinary_operation_acceptance_v1 import (  # noqa: E402
    _operation,
    _publish_focus,
    _simple,
)

FOCUS = "WINDOW_SURVIVAL_SYNTHETIC_FOCUS"
ROOT_DIR = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Portable fixture built through production paths
# ---------------------------------------------------------------------------


def _execute_question(workspace: Path, root: Path, *, qid: str, value: float, journal: str, market: str) -> dict:
    spec = _simple(qid, value=value)
    spec_path = workspace / f"{qid}.spec.json"
    scope_path = workspace / f"{qid}.scope.json"
    op_path = workspace / f"{qid}.op.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    scope_path.write_text(
        json.dumps(
            {
                "population": "BASE_X",
                "decision_timestamp": "Y3600",
                "target": temporal_target_label(spec),
                "estimand": "price_relative_proxy",
                "explanatory_condition": "mark",
                "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1",
            }
        ),
        encoding="utf-8",
    )
    op_path.write_text(
        json.dumps(
            _operation(
                spec,
                focus=FOCUS,
                journal=journal,
                market=market,
                text=f"synthetic ordinary question {qid}",
                cap={"main": 1, "adaptive": 0, "preview": 0},
            )
        ),
        encoding="utf-8",
    )
    completed = run_cli(
        "discovery-execute",
        "--store",
        str(root),
        "--spec",
        str(spec_path),
        "--candidate-scope",
        str(scope_path),
        "--journal-scope",
        journal,
        "--operation",
        str(op_path),
        "--format",
        "json",
        data_root=root,
    )
    if completed.returncode != 0:
        raise AssertionError(completed.stderr + completed.stdout)
    for path in (spec_path, scope_path, op_path):
        path.unlink()
    return json.loads(completed.stdout)


def _build_origin(workspace: Path) -> dict:
    root, receipt = _publish_focus(workspace, FOCUS)
    journal = str(receipt["search_key_sha256"])
    market = str(receipt["market_evidence_epoch_sha256"])
    _execute_question(workspace, root, qid="q1-synthetic", value=0.0, journal=journal, market=market)
    _execute_question(workspace, root, qid="q2-synthetic", value=0.5, journal=journal, market=market)
    return {"journal": journal, "market": market}


def _ctx(workspace: Path) -> dict:
    root = workspace / "rdp"
    store = ResearchStore(root, create_if_missing=False)
    operations = list_operations(store)
    journal = str(operations[0]["journal_scope"])
    market = str(operations[0]["market_evidence_epoch_sha256"])
    looks = list_discovery_looks(store, journal)
    by_query = {str((item.get("result") or {}).get("query_id")): item for item in looks}
    return {
        "root": root,
        "journal": journal,
        "market": market,
        "q1": by_query["q1-synthetic"],
        "q2": by_query["q2-synthetic"],
    }


def _ref(look: Mapping[str, Any]) -> dict:
    return {
        "result_ref": look["record_id"],
        "result_sha256": look["result_sha256"],
        "calculation_version": look["calculation_version"],
    }


def question_packet(ctx: dict, look: Mapping[str, Any], *, text: str = "does the synthetic mark predict the proxy?") -> dict:
    return {
        "subject": {
            "subject_kind": "QUESTION",
            "market_evidence_epoch_sha256": ctx["market"],
            "owner_focus": FOCUS,
            "journal_scope": ctx["journal"],
            "question_spec_sha256": look["spec_sha256"],
            "question_text": text,
        },
        "basis": {
            "result_refs": [_ref(look)],
            "saved_results_read": True,
            "values_loaded": False,
            "scientific_look_delta": 0,
        },
        "judgement": {
            "verdict": "LIMITED_NON_CANDIDATE_FOR_THIS_QUESTION",
            "recommendation": "STOP_THIS_QUESTION",
            "source_wording": "limited non-candidate for this question",
            "rationale": "Pooled proxy is small and cohorts are not independent replications.",
            "caveats": ["cohort slices are descriptive", "PRICE_RELATIVE_PROXY is not net return"],
        },
        "provenance": {
            "author_role": "MODEL",
            "source_episode": "SYNTHETIC-EPISODE-Q",
            "source_refs": ["tests/test_hfic_scientific_disposition_continuity_v1.py"],
        },
    }


def search_packet(ctx: dict, looks: list[Mapping[str, Any]], *, tier: str = "SIMPLE_SCREEN", constraints: list[str] | None = None) -> dict:
    return {
        "subject": {
            "subject_kind": "BOUNDED_SEARCH_ASSESSMENT",
            "market_evidence_epoch_sha256": ctx["market"],
            "owner_focus": FOCUS,
            "journal_scope": ctx["journal"],
            "search_scope": {
                "search_tier": tier,
                "population": "BASE_X",
                "window": "UNKNOWN_NOT_FIXED",
                "constraints": constraints if constraints is not None else ["single point_value feature on price"],
            },
        },
        "basis": {
            "result_refs": [_ref(item) for item in looks],
            "saved_results_read": True,
            "values_loaded": False,
            "scientific_look_delta": 0,
            "considered_proposals": [
                {"label": "P1", "representation": "SIMPLE point threshold at Y3600", "disposition_reason": "same predicate as q1"},
                {"label": "P2", "representation": "SIMPLE point threshold at Y900", "disposition_reason": "no new information versus q2"},
                {"label": "P3", "representation": "SIMPLE liquidity floor", "disposition_reason": "feature not grounded"},
            ],
            "synthesis_basis": "Three SIMPLE proposals reviewed against saved q1/q2 results; none adds a worthy next question.",
        },
        "judgement": (
            {
                "verdict": "NO_WORTHY_SIMPLE_NEXT",
                "recommendation": "PAUSE_CONSIDERED_SIMPLE_SCOPE",
                "source_wording": "PARK_FAMILY (operator wording) for the considered SIMPLE scope",
                "rationale": "The considered SIMPLE proposals repeat saved questions or lack grounded features.",
                "caveats": ["COMPOUND scope untested", "not a family close"],
            }
            if tier == "SIMPLE_SCREEN"
            else {
                "verdict": "INSUFFICIENT_EVIDENCE",
                "recommendation": "REVIEW_BOUNDED_SCOPE",
                "source_wording": "compound scope not yet assessed",
                "rationale": "No compound result exists.",
                "caveats": [],
            }
        ),
        "provenance": {
            "author_role": "MODEL",
            "source_episode": "SYNTHETIC-EPISODE-S",
            "source_refs": ["synthetic pre-values synthesis"],
        },
    }


def _cli_record(root: Path, packet: dict, *extra: str) -> tuple[int, dict]:
    with tempfile.TemporaryDirectory() as raw:
        path = Path(raw) / "packet.json"
        path.write_text(json.dumps(packet), encoding="utf-8")
        completed = run_cli("disposition-record", "--input", str(path), *extra, "--format", "json", data_root=root)
    # The packet file is gone: nothing below may depend on a sidecar.
    return completed.returncode, json.loads(completed.stdout)


def _forge_run(root: Path) -> dict:
    completed = run_cli("forge-run", "--owner-focus", FOCUS, "--no-write", "--format", "json", data_root=root)
    if completed.returncode not in {0, 2}:
        raise AssertionError(completed.stderr + completed.stdout)
    body = json.loads(completed.stdout)
    body["_stderr"] = completed.stderr
    body["_exit"] = completed.returncode
    return body


def _preflight(root: Path) -> dict:
    completed = run_cli("preflight", "--discovery-contract", "--owner-focus", FOCUS, "--format", "json", data_root=root)
    if completed.returncode != 0:
        raise AssertionError(completed.stderr + completed.stdout)
    return json.loads(completed.stdout)


def _show(root: Path, *extra: str) -> dict:
    completed = run_cli("disposition-show", "--owner-focus", FOCUS, *extra, "--format", "json", data_root=root)
    if completed.returncode != 0:
        raise AssertionError(completed.stderr + completed.stdout)
    return json.loads(completed.stdout)


def _science_snapshot(root: Path, journal: str) -> dict:
    """Numerical/budget state that an assessment must never change."""

    store = ResearchStore(root, create_if_missing=False)
    looks = list_discovery_looks(store, journal)
    return {
        "looks": sorted((item["record_id"], item["result_sha256"], item.get("look_class"), item.get("new_look")) for item in looks),
        "main": sum(1 for item in looks if item.get("look_class") == "MAIN" and item.get("new_look") is True),
        "adaptive": sum(1 for item in looks if item.get("look_class") == "ADAPTIVE" and item.get("new_look") is True),
        "previews": len(_iter_kind(store, "DISCOVERY_FEATURE_PREVIEW")),
        "reservations": sorted(str(item.get("record_id")) for item in _iter_kind(store, RESERVATION_KIND)),
        "operations": sorted((str(item.get("operation_sha256")), str(item.get("status"))) for item in list_operations(store)),
        "sessions": len(_iter_kind(store, "FORGE_DRAFT")),
    }


def _entries(capsule: Mapping[str, Any]) -> dict[str, dict]:
    return {str(item["kind"]) + ":" + str(item["subject_key"]): item for item in capsule.get("entries") or []}


def _by_kind(capsule: Mapping[str, Any], kind: str) -> list[dict]:
    return [item for item in capsule.get("entries") or [] if item.get("kind") == kind]


def _inject(root: Path, *, record_id: str, payload_json: str, supersedes: str | None = None) -> None:
    """FAULT INJECTION: append a raw row the production writer would refuse."""

    from solana_alpha_lab.factory.research_store import _canonical_payload

    payload_json, _ = _canonical_payload(payload_json)
    now = datetime.now(timezone.utc)
    txn = "RESEARCH-TXN-FAULT-" + hashlib.sha256(record_id.encode()).hexdigest()[:24].upper()
    event = ResearchEvent(
        record_id=record_id,
        record_kind=RecordKind.RESEARCH_ARTIFACT,
        entity_id=record_id,
        hypothesis_version_id=None,
        run_id=None,
        transaction_id=txn,
        effective_at=now,
        first_reliable_available_at=now,
        supersedes_record_id=supersedes,
        payload_json=payload_json,
        payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        schema_version="1.0",
        producer_capability_id="CAP-TEST-FAULT-INJECTION-001",
        producer_git_sha="0" * 40,
        created_at=now,
    )
    ResearchStore(root, create_if_missing=False).append([event], transaction_id=txn)


def _inject_body(root: Path, body: dict, *, supersedes: str | None = None) -> str:
    """FAULT INJECTION of a well-formed disposition body that bypasses lineage checks."""

    body = dict(body)
    body["disposition_sha256"] = disp._sha(disp._identity(body))
    body["ingestion"] = {
        "recorded_at": "2026-01-01T00:00:00.000000Z",
        "writer_module_sha256": "0" * 64,
        "writer_git_sha": None,
        "writer": disp.WRITER_NAME,
    }
    canonical = disp._canonical(body)
    wrapper = {
        "artifact_kind": disp.ARTIFACT_KIND,
        "payload_canonical": canonical,
        "payload_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }
    record_id = disp.record_id_for(body["disposition_sha256"])
    _inject(root, record_id=record_id, payload_json=json.dumps(wrapper, sort_keys=True, separators=(",", ":")), supersedes=supersedes)
    return record_id


class _Base(unittest.TestCase):
    origin: tempfile.TemporaryDirectory

    @classmethod
    def setUpClass(cls) -> None:
        cls.origin = tempfile.TemporaryDirectory(prefix="disp-origin-")
        _build_origin(Path(cls.origin.name))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.origin.cleanup()

    def workspace(self) -> Path:
        # Every test works on a copy at a different absolute path.
        holder = tempfile.TemporaryDirectory(prefix="disp-copy-")
        self.addCleanup(holder.cleanup)
        target = Path(holder.name) / "moved" / "workspace"
        shutil.copytree(self.origin.name, target)
        return target


# ---------------------------------------------------------------------------
# V1 — normal question -> authored assessment -> cold consumers
# ---------------------------------------------------------------------------


class V1QuestionAssessmentTests(_Base):
    def test_normal_writer_cold_readback_and_pre_values_capsule(self) -> None:
        ctx = _ctx(self.workspace())
        root = ctx["root"]
        before = _science_snapshot(root, ctx["journal"])
        preflight_before = _preflight(root)
        run_before = _forge_run(root)
        # Calculation saved, assessment not written: visible as NOT_RECORDED, not invented.
        self.assertEqual(
            sorted(item["result_ref"] for item in run_before["scientific_disposition_context"]["not_recorded"]),
            sorted([ctx["q1"]["record_id"], ctx["q2"]["record_id"]]),
        )
        self.assertEqual(run_before["scientific_disposition_context"]["total_subjects"], 0)
        code, written = _cli_record(root, question_packet(ctx, ctx["q1"]))
        self.assertEqual(code, 0, written)
        self.assertEqual(written["disposition"], "CREATED")
        self.assertEqual(written["writes"], {"research_store": 1})
        self.assertEqual(set(written["scientific_delta"].values()), {0})
        self.assertEqual(written["readback"]["status"], disp.STATUS_CURRENT)
        # Numerical, budget and lifecycle state are untouched by the append.
        self.assertEqual(_science_snapshot(root, ctx["journal"]), before)
        run_after = _forge_run(root)
        self.assertEqual(run_after["_exit"], run_before["_exit"])
        # Machine next action stays with the ordinary resolver.
        self.assertEqual(run_after["next_action"], run_before["next_action"])
        self.assertEqual(run_after.get("owner_final"), run_before.get("owner_final"))
        # Market identity and slot do not move with an endogenous assessment.
        self.assertEqual(run_after.get("market_evidence_epoch_sha256"), run_before.get("market_evidence_epoch_sha256"))
        self.assertEqual(run_after.get("scientific_slot_sha256"), run_before.get("scientific_slot_sha256"))
        # Hash boundary: the canonical receipt is identical; the overlay is outside it.
        self.assertEqual(run_after["receipt_sha256"], run_before["receipt_sha256"])
        overlay = run_after["scientific_disposition_context"]
        self.assertEqual(overlay["receipt_hash_domain"], "EXCLUDED_DERIVED_OVERLAY")
        self.assertFalse(overlay["authority_granted"])
        questions = _by_kind(overlay, "QUESTION")
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0]["ref"], written["record_id"])
        self.assertEqual(questions[0]["status"], disp.STATUS_CURRENT)
        self.assertEqual(questions[0]["result_refs"], [ctx["q1"]["record_id"]])
        self.assertTrue(questions[0]["recommendation_active"])
        # Technical operation state is shown separately from the advice.
        self.assertEqual(run_after["ordinary_operation"]["status"], run_before["ordinary_operation"]["status"])
        self.assertIn("scientific_context (advisory; not next_action, not authority):", run_after["_stderr"])
        self.assertIn(f"next_action: {run_after['next_action']}", run_after["_stderr"])
        # Q2 has a saved calculation but no assessment: distinct, not invented.
        self.assertEqual([item["result_ref"] for item in overlay["not_recorded"]], [ctx["q2"]["record_id"]])
        # Pre-values consumer: the same resolver feeds the context packet.
        preflight_after = _preflight(root)
        # Search/journal key, market, slot and memory eligibility do not move.
        for key in ("search_key_sha256", "market_evidence_epoch_sha256", "scientific_slot_sha256", "action"):
            self.assertEqual(preflight_after.get(key), preflight_before.get(key), key)
        self.assertEqual(preflight_after["search_key_sha256"], ctx["journal"])
        packet = preflight_after["forge_context_packet"]
        capsule = packet["scientific_disposition_context"]
        self.assertEqual(_by_kind(capsule, "QUESTION")[0]["ref"], written["record_id"])
        self.assertEqual(_by_kind(capsule, "QUESTION")[0]["status"], disp.STATUS_CURRENT)
        self.assertNotIn(written["record_id"], json.dumps(packet.get("ranked_prior_candidate_ids")))
        self.assertLessEqual(len(disp._canonical(capsule).encode("utf-8")), disp.COMPACT_CONTEXT_MAX_BYTES)
        # Detail by exact ref, read in a fresh process.
        detail = _show(root, "--record-id", written["record_id"])
        self.assertEqual(detail["records"][0]["body"]["judgement"]["verdict"], "LIMITED_NON_CANDIDATE_FOR_THIS_QUESTION")
        self.assertFalse(detail["values_loaded"])

    def test_record_is_endogenous_and_exact_repeat_replays(self) -> None:
        ctx = _ctx(self.workspace())
        store = ResearchStore(ctx["root"], create_if_missing=False)
        first = disp.record_disposition(store, question_packet(ctx, ctx["q1"]), current_market=ctx["market"])
        again = disp.record_disposition(store, question_packet(ctx, ctx["q1"]), current_market=ctx["market"])
        self.assertEqual(again["disposition"], "REPLAY_EXISTING")
        self.assertEqual(again["record_id"], first["record_id"])
        self.assertEqual(again["ingestion"]["recorded_at"], first["ingestion"]["recorded_at"])
        rows = [record for record in store.iter_committed_records() if record.record_id == first["record_id"]]
        self.assertEqual(len(rows), 1)
        self.assertTrue(is_hfic_record(rows[0]))
        self.assertEqual(rows[0].producer_capability_id, disp.CAPABILITY_ID)

    def test_invalid_packets_are_refused_before_append(self) -> None:
        ctx = _ctx(self.workspace())
        store = ResearchStore(ctx["root"], create_if_missing=False)
        inventory = store.diagnostics().committed_inventory_sha256
        cases: list[tuple[str, dict]] = []
        wrong_focus = question_packet(ctx, ctx["q1"])
        wrong_focus["subject"]["owner_focus"] = "OTHER_FOCUS"
        cases.append(("DISPOSITION_BASIS_SCOPE_MISMATCH", wrong_focus))
        wrong_spec = question_packet(ctx, ctx["q1"])
        wrong_spec["subject"]["question_spec_sha256"] = ctx["q2"]["spec_sha256"]
        cases.append(("DISPOSITION_BASIS_SPEC_MISMATCH", wrong_spec))
        wrong_hash = question_packet(ctx, ctx["q1"])
        wrong_hash["basis"]["result_refs"][0]["result_sha256"] = "0" * 64
        cases.append(("DISPOSITION_BASIS_RESULT_MISMATCH", wrong_hash))
        missing = question_packet(ctx, ctx["q1"])
        missing["basis"]["result_refs"][0]["result_ref"] = "HFIC-ART-DISCOVERY-" + "A" * 40
        cases.append(("DISPOSITION_BASIS_RESULT_NOT_FOUND", missing))
        wrong_market = question_packet(ctx, ctx["q1"])
        wrong_market["subject"]["market_evidence_epoch_sha256"] = "cd" * 32
        cases.append(("DISPOSITION_MARKET_NOT_CURRENT", wrong_market))
        absolute = question_packet(ctx, ctx["q1"])
        absolute["provenance"]["source_refs"] = ["C:\\Users\\owner\\sidecar\\readout.json"]
        cases.append(("DISPOSITION_ABSOLUTE_PATH_FORBIDDEN", absolute))
        simple_on_compound = search_packet(ctx, [ctx["q1"]], tier="COMPOUND_SCREEN")
        simple_on_compound["judgement"]["verdict"] = "NO_WORTHY_SIMPLE_NEXT"
        simple_on_compound["judgement"]["recommendation"] = "PAUSE_CONSIDERED_SIMPLE_SCOPE"
        cases.append(("DISPOSITION_SCOPE_TIER_MISMATCH", simple_on_compound))
        park = question_packet(ctx, ctx["q1"])
        park["judgement"]["verdict"] = "PARK_FAMILY"
        cases.append(("DISPOSITION_VERDICT_NOT_ALLOWED_FOR_SUBJECT", park))
        spend = search_packet(ctx, [ctx["q1"]])
        spend["basis"]["scientific_look_delta"] = 1
        cases.append(("DISPOSITION_LOOK_DELTA_FORBIDDEN", spend))
        fake_session = question_packet(ctx, ctx["q1"])
        fake_session["session_id"] = "HFIC-SESS-FAKE"
        cases.append(("DISPOSITION_PACKET_UNKNOWN_FIELD", fake_session))
        for code, packet in cases:
            with self.subTest(code=code):
                with self.assertRaises(disp.DispositionError) as caught:
                    disp.record_disposition(store, packet, current_market=ctx["market"])
                self.assertEqual(caught.exception.code, code)
        self.assertEqual(store.diagnostics().committed_inventory_sha256, inventory)
        code, refused = _cli_record(ctx["root"], wrong_focus)
        self.assertEqual(code, 2)
        self.assertEqual(refused["refusal_code"], "DISPOSITION_BASIS_SCOPE_MISMATCH")
        self.assertEqual(refused["writes"], {"research_store": 0})


# ---------------------------------------------------------------------------
# V2 — no-spend synthesis -> durable assessment without fake execution
# ---------------------------------------------------------------------------


class V2NoSpendSearchTests(_Base):
    def test_no_spend_search_assessment_without_fake_objects(self) -> None:
        ctx = _ctx(self.workspace())
        root = ctx["root"]
        for look in (ctx["q1"], ctx["q2"]):
            code, _ = _cli_record(root, question_packet(ctx, look))
            self.assertEqual(code, 0)
        before = _science_snapshot(root, ctx["journal"])
        preview_code, preview = _cli_record(root, search_packet(ctx, [ctx["q1"], ctx["q2"]]), "--preview")
        self.assertEqual(preview_code, 0, preview)
        self.assertTrue(preview["would_append"])
        self.assertEqual(preview["expected_inventory_delta_records"], 1)
        self.assertEqual(_science_snapshot(root, ctx["journal"]), before)
        code, written = _cli_record(root, search_packet(ctx, [ctx["q1"], ctx["q2"]]))
        self.assertEqual(code, 0, written)
        self.assertEqual(written["record_id"], preview["record_id"])
        self.assertEqual(_science_snapshot(root, ctx["journal"]), before)
        body = _show(root, "--record-id", written["record_id"])["records"][0]["body"]
        self.assertIsNone(body["basis"]["operation_sha256"])
        self.assertFalse(body["basis"]["values_loaded"])
        self.assertTrue(body["basis"]["saved_results_read"])
        self.assertEqual(body["basis"]["scientific_look_delta"], 0)
        self.assertEqual(
            {item["attempt_ref"] for item in body["basis"]["journal_frontier"]["attempts"]},
            {ctx["q1"]["record_id"], ctx["q2"]["record_id"]},
        )
        self.assertNotIn("session_id", json.dumps(body))
        self.assertEqual(body["judgement"]["source_wording"], "PARK_FAMILY (operator wording) for the considered SIMPLE scope")
        run = _forge_run(root)
        overlay = run["scientific_disposition_context"]
        search = _by_kind(overlay, "BOUNDED_SEARCH_ASSESSMENT")
        self.assertEqual(len(search), 1)
        self.assertEqual(search[0]["verdict"], "NO_WORTHY_SIMPLE_NEXT")
        self.assertEqual(search[0]["scope"]["search_tier"], "SIMPLE_SCREEN")
        self.assertEqual(search[0]["status"], disp.STATUS_CURRENT)
        self.assertEqual(len(_by_kind(overlay, "QUESTION")), 2)
        self.assertEqual(overlay["not_recorded"], [])
        # The technical journal state is the ordinary resolver's, unchanged by advice.
        self.assertIn(run["ordinary_operation"]["search_open"], {True, False})
        self.assertNotEqual(run["next_action"], "NO_WORTHY_HYPOTHESIS")
        packet = _preflight(root)["forge_context_packet"]
        self.assertEqual(_by_kind(packet["scientific_disposition_context"], "BOUNDED_SEARCH_ASSESSMENT")[0]["ref"], written["record_id"])
        self.assertNotIn("NO_WORTHY", json.dumps(packet.get("closed_family_ledger")))


# ---------------------------------------------------------------------------
# V3 — evidence drift, supersession, withdrawal, isolation
# ---------------------------------------------------------------------------


class V3DriftAndLineageTests(_Base):
    def _seed(self) -> tuple[dict, dict, dict, dict]:
        ctx = _ctx(self.workspace())
        store = ResearchStore(ctx["root"], create_if_missing=False)
        q1 = disp.record_disposition(store, question_packet(ctx, ctx["q1"]), current_market=ctx["market"])
        q2 = disp.record_disposition(store, question_packet(ctx, ctx["q2"]), current_market=ctx["market"])
        s1 = disp.record_disposition(store, search_packet(ctx, [ctx["q1"], ctx["q2"]]), current_market=ctx["market"])
        return ctx, q1, q2, s1

    def _capsule(self, ctx: dict, market: str | None = None) -> dict:
        store = ResearchStore(ctx["root"], create_if_missing=False)
        return disp.disposition_context(store, owner_focus=FOCUS, current_market=market or ctx["market"], journal_scope=ctx["journal"])

    def test_unrelated_writes_keep_search_current_and_new_look_requires_review(self) -> None:
        ctx, q1, q2, s1 = self._seed()
        store = ResearchStore(ctx["root"], create_if_missing=False)
        # Unrelated HFIC writes: another focus's operation and this atom's own records.
        record_operation(
            store,
            {
                "owner_request_text": "unrelated focus request",
                "owner_focus": "UNRELATED_FOCUS",
                "journal_scope": "ee" * 32,
                "market_evidence_epoch_sha256": ctx["market"],
                "owner_cap": {"main": 0, "adaptive": 0, "preview": 0},
            },
        )
        statuses = {item["ref"]: item["status"] for item in self._capsule(ctx)["entries"]}
        self.assertEqual(statuses, {q1["record_id"]: disp.STATUS_CURRENT, q2["record_id"]: disp.STATUS_CURRENT, s1["record_id"]: disp.STATUS_CURRENT})
        # A new relevant look in the same journal/market.
        _execute_question(ctx["root"].parent, ctx["root"], qid="q3-synthetic", value=0.25, journal=ctx["journal"], market=ctx["market"])
        capsule = self._capsule(ctx)
        statuses = {item["ref"]: item for item in capsule["entries"]}
        self.assertEqual(statuses[s1["record_id"]]["status"], disp.STATUS_REVIEW)
        self.assertIn("FRONTIER_CHANGED", statuses[s1["record_id"]]["reasons"])
        self.assertIn("NEW_ATTEMPTS:1", statuses[s1["record_id"]]["reasons"])
        self.assertFalse(statuses[s1["record_id"]]["recommendation_active"])
        self.assertEqual(statuses[q1["record_id"]]["status"], disp.STATUS_CURRENT)
        self.assertEqual(statuses[q2["record_id"]]["status"], disp.STATUS_CURRENT)
        self.assertEqual(len(capsule["not_recorded"]), 1)
        # A stale frontier cannot be re-asserted as current by a NEW submission.
        stale = search_packet(ctx, [ctx["q1"], ctx["q2"]])
        stale["basis"]["journal_frontier"] = {"attempts": [], "frontier_sha256": "0" * 64}
        stale["supersedes"] = {"record_id": s1["record_id"], "disposition_sha256": s1["disposition_sha256"]}
        with self.assertRaises(disp.DispositionError) as caught:
            disp.record_disposition(store, stale, current_market=ctx["market"])
        self.assertEqual(caught.exception.code, "DISPOSITION_FRONTIER_STALE")

    def test_market_change_and_compound_scope_are_not_inherited(self) -> None:
        ctx, q1, _q2, s1 = self._seed()
        other = self._capsule(ctx, market="ab" * 32)
        for item in other["entries"]:
            self.assertEqual(item["status"], disp.STATUS_HISTORICAL)
            self.assertEqual(item["scope_match"], "RELATED_OTHER_MARKET")
            self.assertFalse(item["recommendation_active"])
        store = ResearchStore(ctx["root"], create_if_missing=False)
        compound = disp.record_disposition(
            store, search_packet(ctx, [], tier="COMPOUND_SCREEN"), current_market=ctx["market"]
        )
        self.assertEqual(compound["disposition"], "CREATED")
        capsule = self._capsule(ctx)
        search = {item["scope"]["search_tier"]: item for item in _by_kind(capsule, "BOUNDED_SEARCH_ASSESSMENT")}
        self.assertEqual(set(search), {"SIMPLE_SCREEN", "COMPOUND_SCREEN"})
        self.assertNotEqual(search["SIMPLE_SCREEN"]["subject_key"], search["COMPOUND_SCREEN"]["subject_key"])
        self.assertEqual(search["SIMPLE_SCREEN"]["ref"], s1["record_id"])
        self.assertEqual(search["COMPOUND_SCREEN"]["verdict"], "INSUFFICIENT_EVIDENCE")
        # No fuzzy family inference: a near-identical focus name sees nothing.
        near = disp.disposition_context(store, owner_focus=FOCUS + "_V2", current_market=ctx["market"])
        self.assertEqual(near["total_subjects"], 0)
        self.assertIn(q1["record_id"], {item["ref"] for item in capsule["entries"]})

    def test_supersession_withdrawal_stale_parent_and_fork(self) -> None:
        ctx, q1, _q2, s1 = self._seed()
        store = ResearchStore(ctx["root"], create_if_missing=False)
        with self.assertRaises(disp.DispositionError) as dup:
            revised = question_packet(ctx, ctx["q1"])
            revised["judgement"]["rationale"] = "second opinion without a predecessor"
            disp.record_disposition(store, revised, current_market=ctx["market"])
        self.assertEqual(dup.exception.code, "DISPOSITION_SUBJECT_HAS_HEAD")
        self.assertEqual(dup.exception.head_refs, [q1["record_id"]])
        # The refusal names the head hash a successor must cite.
        self.assertEqual(dup.exception.detail, f"{q1['record_id']}:{q1['disposition_sha256']}")
        successor = question_packet(ctx, ctx["q1"])
        successor["judgement"]["verdict"] = "INSUFFICIENT_EVIDENCE"
        successor["judgement"]["recommendation"] = "REVIEW_BOUNDED_SCOPE"
        successor["supersedes"] = {"record_id": q1["record_id"], "disposition_sha256": q1["disposition_sha256"]}
        second = disp.record_disposition(store, successor, current_market=ctx["market"])
        stale = question_packet(ctx, ctx["q1"])
        stale["judgement"]["rationale"] = "competing successor on the old parent"
        stale["supersedes"] = {"record_id": q1["record_id"], "disposition_sha256": q1["disposition_sha256"]}
        with self.assertRaises(disp.DispositionError) as caught:
            disp.record_disposition(store, stale, current_market=ctx["market"])
        self.assertEqual(caught.exception.code, "DISPOSITION_STALE_PARENT")
        self.assertEqual(caught.exception.head_refs, [second["record_id"]])
        entry = next(item for item in self._capsule(ctx)["entries"] if item["kind"] == "QUESTION" and item["ref"] == second["record_id"])
        self.assertEqual(entry["verdict"], "INSUFFICIENT_EVIDENCE")
        withdrawal = {
            "entry": "WITHDRAWAL",
            "subject": question_packet(ctx, ctx["q1"])["subject"],
            "withdrawal": {"reason": "assessment written against the wrong question text"},
            "supersedes": {"record_id": second["record_id"], "disposition_sha256": second["disposition_sha256"]},
            "provenance": {"author_role": "OPERATOR", "source_episode": "SYNTHETIC-WITHDRAWAL", "source_refs": []},
        }
        withdrawn = disp.record_disposition(store, withdrawal, current_market=ctx["market"])
        self.assertEqual(withdrawn["readback"]["status"], disp.STATUS_WITHDRAWN)
        detail = disp.disposition_detail(store, owner_focus=FOCUS, current_market=ctx["market"], subject_key_value=withdrawn["subject_key"])
        self.assertEqual(len(detail["records"]), 3, "history is append-only")
        self.assertFalse(detail["entries"][0]["recommendation_active"])
        # Fork injected as restored history: shown as CONFLICT, never latest-wins.
        forked = dict(disp._View(store).by_subject()[s1["subject_key"]][0]["body"])
        forked.pop("disposition_sha256")
        forked.pop("ingestion")
        for rationale in ("fork branch A", "fork branch B"):
            branch = json.loads(json.dumps(forked))
            branch["judgement"]["rationale"] = rationale
            branch["supersedes"] = {"record_id": s1["record_id"], "disposition_sha256": s1["disposition_sha256"]}
            _inject_body(ctx["root"], branch, supersedes=s1["record_id"])
        conflict = next(item for item in self._capsule(ctx)["entries"] if item["subject_key"] == s1["subject_key"])
        self.assertEqual(conflict["status"], disp.STATUS_CONFLICT)
        self.assertEqual(len(conflict["heads"]), 2)
        with self.assertRaises(disp.DispositionError) as fork_refusal:
            follow = search_packet(ctx, [ctx["q1"], ctx["q2"]])
            follow["supersedes"] = {"record_id": s1["record_id"], "disposition_sha256": s1["disposition_sha256"]}
            follow["judgement"]["rationale"] = "third branch"
            disp.record_disposition(store, follow, current_market=ctx["market"])
        self.assertEqual(fork_refusal.exception.code, "DISPOSITION_SUBJECT_CONFLICT")

    def test_corrupt_relevant_and_unrelated_records_are_localized(self) -> None:
        ctx, q1, q2, s1 = self._seed()
        # Relevant: a well-formed assessment whose bound result does not resolve.
        missing = disp.normalize_packet(question_packet(ctx, ctx["q1"], text="question bound to a lost result"))
        missing["subject"]["question_spec_sha256"] = "12" * 32
        missing["subject_key"] = disp.subject_key(missing["subject"])
        missing["basis"]["result_refs"][0]["result_ref"] = "HFIC-ART-DISCOVERY-" + "B" * 40
        missing["basis"]["operation_sha256"] = None
        missing["basis"]["data_binding_sha256"] = None
        lost_ref = _inject_body(ctx["root"], missing)
        # Unrelated: an unparseable row under the disposition kind.
        _inject(
            ctx["root"],
            record_id="HFIC-ART-DISP-" + "F" * 40,
            payload_json=json.dumps({"artifact_kind": disp.ARTIFACT_KIND, "payload_canonical": "{not json", "payload_sha256": "0" * 64}),
        )
        capsule = self._capsule(ctx)
        entries = {item["ref"] or item["subject_key"]: item for item in capsule["entries"]}
        self.assertEqual(entries[lost_ref]["status"], disp.STATUS_UNREADABLE)
        self.assertTrue(any(reason.startswith("BASIS_RESULT_MISSING") for reason in entries[lost_ref]["reasons"]))
        for good in (q1, q2, s1):
            self.assertEqual(entries[good["record_id"]]["status"], disp.STATUS_CURRENT)
        self.assertEqual(capsule["unreadable_unscoped_records"], 1)
        # Numerical and ordinary paths stay readable; no whole-store outage.
        run = _forge_run(ctx["root"])
        self.assertEqual(run["ordinary_operation"]["result_refs"][0][:19], "HFIC-ART-DISCOVERY-")
        self.assertNotEqual(run["scientific_disposition_context"].get("status"), "UNAVAILABLE")
        self.assertIn("scientific_disposition_context", _preflight(ctx["root"])["forge_context_packet"])

    def test_consumer_isolation_when_reader_fails(self) -> None:
        ctx = _ctx(self.workspace())
        store = ResearchStore(ctx["root"], create_if_missing=False)
        with mock.patch.object(disp, "resolve_focus", side_effect=RuntimeError("boom")):
            capsule = disp.safe_disposition_context(store, owner_focus=FOCUS, current_market=ctx["market"])
        self.assertEqual(capsule["status"], "UNAVAILABLE")
        self.assertEqual(capsule["reason_code"], "DISPOSITION_CONTEXT_READ_FAILED")
        self.assertEqual(capsule["error_class"], "RuntimeError")
        self.assertIn("UNAVAILABLE", disp.format_context_lines(capsule)[0])


class V3CalculationRevisionTests(unittest.TestCase):
    """Old-writer result -> assessment -> explicit calculation revision."""

    def test_revision_requires_new_assessment_then_successor_is_current(self) -> None:
        from solana_alpha_lab.factory.hfic_grounded_discovery import run_recorded_discovery_query
        from tests.test_hfic_temporal_result_coherence_v1 import (
            COHORT,
            GIT_SHA,
            MATCH,
            RELEASE,
            _bind,
            _member_rows,
            _query,
            _rows,
            old_writer,
        )

        parts = [
            _member_rows("a", COHORT, RELEASE, mark=MATCH, exit_price=1.2),
            _member_rows("b", COHORT, RELEASE, mark=MATCH, exit_price=0.9),
        ]
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            census, observations = _rows(parts)
            journal, market, focus = "44" * 32, "ab" * 32, "REVISION_FOCUS"
            spec = _query("disposition-revision")
            operation = record_operation(
                ResearchStore(root),
                {
                    "owner_request_text": "revision disposition",
                    "owner_focus": focus,
                    "journal_scope": journal,
                    "market_evidence_epoch_sha256": market,
                    "spec": spec,
                    "owner_cap": {"main": 1, "adaptive": 0, "preview": 0},
                    "requested_completion": "LIMITED_RESULT",
                },
            )
            kwargs = dict(
                census=census,
                observations=observations,
                spec=spec,
                binding=[_bind(COHORT, RELEASE)],
                journal_scope=journal,
                candidate_scope={},
                git_sha=GIT_SHA,
                operation_sha256=operation["operation_sha256"],
                verified_market=market,
            )
            with old_writer():
                v3 = run_recorded_discovery_query(ResearchStore(root), **kwargs)
            store = ResearchStore(root)
            look = next(item for item in list_discovery_looks(store, journal) if item["record_id"] == v3["result_refs"][0])
            ctx = {"market": market, "journal": journal}
            packet = question_packet(ctx, look)
            packet["subject"]["owner_focus"] = focus
            first = disp.record_disposition(store, packet, current_market=market)
            self.assertEqual(first["readback"]["status"], disp.STATUS_CURRENT)
            revised = run_recorded_discovery_query(
                ResearchStore(root),
                correction={"source_result_ref": v3["result_refs"][0], "source_result_sha256": v3["result_sha256"]},
                **kwargs,
            )
            capsule = disp.disposition_context(store, owner_focus=focus, current_market=market)
            entry = capsule["entries"][0]
            self.assertEqual(entry["status"], disp.STATUS_REVIEW)
            self.assertEqual(entry["reasons"], [f"BASIS_RESULT_REVISED:{v3['result_refs'][0]}"])
            # The old judgement is not carried onto the new version automatically.
            self.assertFalse(entry["recommendation_active"])
            # NEW writes on the superseded version are refused.
            again = json.loads(json.dumps(packet))
            again["supersedes"] = {"record_id": first["record_id"], "disposition_sha256": first["disposition_sha256"]}
            again["judgement"]["rationale"] = "retry on old basis"
            with self.assertRaises(disp.DispositionError) as caught:
                disp.record_disposition(store, again, current_market=market)
            self.assertEqual(caught.exception.code, "DISPOSITION_BASIS_NOT_CURRENT")
            new_look = next(item for item in list_discovery_looks(store, journal) if item["record_id"] == revised["result_refs"][0])
            successor = question_packet(ctx, new_look)
            successor["subject"]["owner_focus"] = focus
            successor["supersedes"] = {"record_id": first["record_id"], "disposition_sha256": first["disposition_sha256"]}
            second = disp.record_disposition(store, successor, current_market=market)
            entry = disp.disposition_context(store, owner_focus=focus, current_market=market)["entries"][0]
            self.assertEqual(entry["status"], disp.STATUS_CURRENT)
            self.assertEqual(entry["ref"], second["record_id"])
            self.assertEqual(entry["result_refs"], [revised["result_refs"][0]])
            # A historical import on the old basis stays readable but not current.
            detail = disp.disposition_detail(store, owner_focus=focus, current_market=market)
            self.assertEqual(detail["entries"][0]["history_refs"], [first["record_id"]])


# ---------------------------------------------------------------------------
# V4 — portability, retry, crash, concurrency, bounded context
# ---------------------------------------------------------------------------


class V4OperabilityTests(_Base):
    def test_relocated_root_fresh_process_reads_same_semantics(self) -> None:
        workspace = self.workspace()
        ctx = _ctx(workspace)
        for packet in (question_packet(ctx, ctx["q1"]), question_packet(ctx, ctx["q2"]), search_packet(ctx, [ctx["q1"], ctx["q2"]])):
            code, _ = _cli_record(ctx["root"], packet)
            self.assertEqual(code, 0)
        before = _show(ctx["root"])
        holder = tempfile.TemporaryDirectory(prefix="disp-relocated-")
        self.addCleanup(holder.cleanup)
        moved = Path(holder.name) / "elsewhere" / "store-home"
        shutil.move(str(workspace), str(moved))
        root = moved / "rdp"
        after = _show(root)
        project = lambda payload: sorted(  # noqa: E731
            (item.get("head_ref"), item.get("status"), tuple(item.get("reasons") or [])) for item in payload["entries"]
        )
        self.assertEqual(project(after), project(before))
        self.assertEqual({item["status"] for item in after["entries"]}, {disp.STATUS_CURRENT})
        self.assertTrue(after["market_verified"])
        # No stored disposition byte carries a host path.
        for record in ResearchStore(root, create_if_missing=False).iter_committed_records():
            if record.record_id.startswith(disp.RECORD_PREFIX):
                self.assertNotIn(str(workspace), record.payload_json)
                self.assertNotIn(str(moved), record.payload_json)
        run = _forge_run(root)
        self.assertEqual(len(run["scientific_disposition_context"]["entries"]), 3)

    def test_lost_response_crash_and_concurrent_writes(self) -> None:
        from solana_alpha_lab.factory import research_store as research_store_module

        ctx = _ctx(self.workspace())
        root = ctx["root"]
        packet = question_packet(ctx, ctx["q1"])
        real_publish = research_store_module._publish_immutable

        def crash_on_manifest(path, payload):
            if "manifests" in str(path):
                raise OSError("simulated crash before manifest commit")
            return real_publish(path, payload)

        with mock.patch.object(research_store_module, "_publish_immutable", side_effect=crash_on_manifest):
            with self.assertRaises(OSError):
                disp.record_disposition(ResearchStore(root, create_if_missing=False), packet, current_market=ctx["market"])
        self.assertEqual(
            disp.disposition_context(ResearchStore(root, create_if_missing=False), owner_focus=FOCUS, current_market=ctx["market"])["total_subjects"],
            0,
            "no visible success before commit",
        )
        first = disp.record_disposition(ResearchStore(root, create_if_missing=False), packet, current_market=ctx["market"])
        self.assertEqual(first["disposition"], "CREATED")
        # Lost response: the caller retries and gets the saved ref and original metadata.
        retry = disp.record_disposition(ResearchStore(root, create_if_missing=False), packet, current_market=ctx["market"])
        self.assertEqual((retry["disposition"], retry["record_id"]), ("REPLAY_EXISTING", first["record_id"]))
        self.assertEqual(retry["ingestion"], first["ingestion"])
        # Concurrent identical submissions converge on one record.
        same = question_packet(ctx, ctx["q2"])
        outcomes: list[Any] = []

        def submit(body: dict) -> None:
            try:
                outcomes.append(disp.record_disposition(ResearchStore(root, create_if_missing=False), body, current_market=ctx["market"]))
            except Exception as exc:  # noqa: BLE001
                outcomes.append(exc)

        threads = [threading.Thread(target=submit, args=(same,)) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertTrue(all(isinstance(item, dict) for item in outcomes), outcomes)
        self.assertEqual(len({item["record_id"] for item in outcomes}), 1)
        self.assertEqual(sum(1 for item in outcomes if item["disposition"] == "CREATED"), 1)
        # Competing successors on one parent: exactly one wins, others see the head.
        competitors = []
        for index in range(3):
            body = question_packet(ctx, ctx["q1"])
            body["judgement"]["rationale"] = f"competing successor {index}"
            body["supersedes"] = {"record_id": first["record_id"], "disposition_sha256": first["disposition_sha256"]}
            competitors.append(body)
        outcomes.clear()
        threads = [threading.Thread(target=submit, args=(body,)) for body in competitors]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        winners = [item for item in outcomes if isinstance(item, dict)]
        losers = [item for item in outcomes if isinstance(item, disp.DispositionError)]
        self.assertEqual(len(winners), 1, outcomes)
        self.assertEqual({item.code for item in losers}, {"DISPOSITION_STALE_PARENT"})
        self.assertTrue(all(item.head_refs == [winners[0]["record_id"]] for item in losers))

    def test_bounded_context_reports_omitted_and_pages_detail(self) -> None:
        ctx = _ctx(self.workspace())
        store = ResearchStore(ctx["root"], create_if_missing=False)
        total = 24
        for index in range(total):
            packet = search_packet(ctx, [ctx["q1"], ctx["q2"]], constraints=[f"synthetic constraint {index:02d}"])
            disp.record_disposition(store, packet, current_market=ctx["market"])
        calls = {"n": 0}
        real_iter = ResearchStore.iter_committed_records

        def counting(self_store):
            calls["n"] += 1
            return real_iter(self_store)

        with mock.patch.object(ResearchStore, "iter_committed_records", counting):
            capsule = disp.disposition_context(store, owner_focus=FOCUS, current_market=ctx["market"], journal_scope=ctx["journal"])
        self.assertEqual(calls["n"], 1, "one read view per request, not one scan per row")
        self.assertLessEqual(len(disp._canonical(capsule).encode("utf-8")), disp.COMPACT_CONTEXT_MAX_BYTES)
        self.assertEqual(capsule["total_subjects"], total)
        self.assertGreater(capsule["omitted"], 0)
        self.assertEqual(capsule["shown"] + capsule["omitted"], total)
        self.assertEqual(sum(capsule["status_counts"].get(key, 0) for key in capsule["status_counts"] if key != disp.STATUS_NOT_RECORDED), total)
        self.assertIn("disposition-show", capsule["detail_query"])
        self.assertEqual(FORGE_OPERATIONAL_PACKET_MAX_BYTES, 65536)
        seen: set[str] = set()
        offset: int | None = 0
        with mock.patch(
            "solana_alpha_lab.factory.hfic_temporal_discovery.execute_temporal_discovery",
            side_effect=AssertionError("detail must not evaluate outcomes"),
        ):
            while offset is not None:
                page = disp.disposition_detail(
                    store, owner_focus=FOCUS, current_market=ctx["market"], offset=offset, limit=10
                )
                seen |= {item["head_ref"] for item in page["entries"]}
                offset = page["next_offset"]
        self.assertEqual(len(seen), total)
        # The same pages through the CLI in a fresh process.
        cli_page = _show(ctx["root"], "--offset", "20", "--limit", "10")
        self.assertEqual(cli_page["total_subjects"], total)
        self.assertEqual(len(cli_page["entries"]), total - 20)
        packet = _preflight(ctx["root"])["forge_context_packet"]
        self.assertLessEqual(len(json.dumps(packet["scientific_disposition_context"], sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()), disp.COMPACT_CONTEXT_MAX_BYTES)
        self.assertEqual(packet["truncation_receipt"]["max_packet_bytes"], FORGE_OPERATIONAL_PACKET_MAX_BYTES)


# ---------------------------------------------------------------------------
# Review round 1 regressions (architecture, code, goal/DoD, owner-UX findings)
# ---------------------------------------------------------------------------


class ReviewRegressionTests(_Base):
    def _recorded(self) -> tuple[dict, dict, dict, dict]:
        ctx = _ctx(self.workspace())
        store = ResearchStore(ctx["root"], create_if_missing=False)
        q1 = disp.record_disposition(store, question_packet(ctx, ctx["q1"]), current_market=ctx["market"])
        q2 = disp.record_disposition(store, question_packet(ctx, ctx["q2"]), current_market=ctx["market"])
        s1 = disp.record_disposition(store, search_packet(ctx, [ctx["q1"], ctx["q2"]]), current_market=ctx["market"])
        return ctx, q1, q2, s1

    def test_unknown_market_and_rotated_journal_are_never_current(self) -> None:
        ctx, q1, _q2, s1 = self._recorded()
        store = ResearchStore(ctx["root"], create_if_missing=False)
        unknown = disp.disposition_context(store, owner_focus=FOCUS, current_market=None)
        self.assertEqual({item["status"] for item in unknown["entries"]}, {disp.STATUS_REVIEW})
        self.assertTrue(all(item["reasons"] == ["MARKET_UNVERIFIED"] for item in unknown["entries"]))
        self.assertFalse(any(item["recommendation_active"] for item in unknown["entries"]))
        self.assertIn("market UNVERIFIED", "\n".join(disp.format_context_lines(unknown)))
        rotated = disp.disposition_context(
            store, owner_focus=FOCUS, current_market=ctx["market"], journal_scope="9" * 64
        )
        by_ref = {item["ref"]: item for item in rotated["entries"]}
        self.assertEqual(by_ref[s1["record_id"]]["status"], disp.STATUS_REVIEW)
        self.assertEqual(by_ref[s1["record_id"]]["reasons"], ["JOURNAL_CHANGED"])
        # A question stays about its own bound result.
        self.assertEqual(by_ref[q1["record_id"]]["status"], disp.STATUS_CURRENT)
        # The consumer wrapper without a market (the blocked forge-run path) shows no active advice.
        capsule = disp.safe_disposition_context(store, owner_focus=FOCUS, current_market=None)
        self.assertFalse(any(item.get("recommendation_active") for item in capsule["entries"]))
        # An unknown current journal never reads search advice as current; questions keep their basis.
        no_journal = disp.disposition_context(store, owner_focus=FOCUS, current_market=ctx["market"])
        by_ref = {item["ref"]: item for item in no_journal["entries"]}
        self.assertEqual(by_ref[s1["record_id"]]["reasons"], ["JOURNAL_UNVERIFIED"])
        self.assertEqual(by_ref[q1["record_id"]]["status"], disp.STATUS_CURRENT)
        self.assertIn("current journal UNVERIFIED", "\n".join(disp.format_context_lines(no_journal)))
        # The CLI computes the current journal like preflight; a bad override is refused.
        self.assertEqual(disp.current_search_key(store, market=ctx["market"], owner_focus=FOCUS), ctx["journal"])
        completed = run_cli("disposition-show", "--owner-focus", FOCUS, "--journal-scope", "nothex", "--format", "json", data_root=ctx["root"])
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(json.loads(completed.stdout)["refusal_code"], "DISPOSITION_JOURNAL_SCOPE_INVALID")

    def test_host_paths_are_refused_and_never_break_readback(self) -> None:
        ctx = _ctx(self.workspace())
        store = ResearchStore(ctx["root"], create_if_missing=False)
        for text in (
            "copied from /srv/lab/data",
            "see E:\\lab\\data",
            "window from /mnt/research/store",
            f"snapshot at {ctx['root']}",
            "SMIAL_DATA_ROOT snapshot",
            "notes at https://example.org/readout",
            "see //server/share/x",
            "ratio a\\b\\c",
            "C:foo\\bar",
            "noise \\sigma est",
        ):
            with self.subTest(text=text):
                packet = question_packet(ctx, ctx["q1"])
                packet["judgement"]["caveats"] = [text]
                with self.assertRaises(disp.DispositionError) as caught:
                    disp.record_disposition(store, packet, current_market=ctx["market"])
                self.assertEqual(caught.exception.code, "DISPOSITION_ABSOLUTE_PATH_FORBIDDEN")
        allowed = question_packet(ctx, ctx["q1"])
        allowed["judgement"]["caveats"] = [
            "PASS/FAIL wording and the /hypothesis-forge slash kept literal",
            "input file: x.csv; units: /s/ rate",
        ]
        self.assertEqual(disp.record_disposition(store, allowed, current_market=ctx["market"])["disposition"], "CREATED")
        # FAULT INJECTION: restored history that carries the real data-root path.
        leaky = disp.normalize_packet(question_packet(ctx, ctx["q2"]))
        leaky["judgement"]["caveats"] = [f"restored from a host copy at {ctx['root']}"]
        leaky["basis"]["operation_sha256"] = None
        leaky["basis"]["data_binding_sha256"] = ctx["q2"]["data_binding_sha256"]
        _inject_body(ctx["root"], leaky)
        # FAIL-CLOSED on a second shape the writer would refuse, the CLI guard's UNC form.
        unc = disp.normalize_packet(question_packet(ctx, ctx["q2"], text="another restored question"))
        unc["subject"]["question_spec_sha256"] = "34" * 32
        unc["subject_key"] = disp.subject_key(unc["subject"])
        unc["judgement"]["caveats"] = ["see //server/share/x"]
        unc["basis"]["operation_sha256"] = None
        unc["basis"]["data_binding_sha256"] = ctx["q2"]["data_binding_sha256"]
        _inject_body(ctx["root"], unc)
        run = _forge_run(ctx["root"])
        self.assertEqual(run["_exit"], 0, run["_stderr"][-400:])
        overlay = run["scientific_disposition_context"]
        self.assertNotEqual(overlay.get("status"), "UNAVAILABLE")
        unreadable = [item for item in overlay["entries"] if item["status"] == disp.STATUS_UNREADABLE]
        self.assertEqual(len(unreadable), 2)
        self.assertTrue(all(item["reasons"][0].startswith("HOST_PATH_IN_STORED_TEXT") for item in unreadable))
        self.assertNotIn(str(ctx["root"]), json.dumps(run))
        self.assertNotIn("//server", json.dumps(run))
        self.assertIn("ordinary_operation", run)
        packet = _preflight(ctx["root"])["forge_context_packet"]
        self.assertNotIn("//server", json.dumps(packet))
        shown = _show(ctx["root"])
        self.assertNotIn("//server", json.dumps(shown))
        # A caller-supplied forbidden text is also caught inside the boundary.
        guarded = disp.safe_disposition_context(
            store, owner_focus=FOCUS, current_market=ctx["market"], forbidden_texts=("WINDOW_SURVIVAL",)
        )
        self.assertEqual(guarded["reason_code"], "DISPOSITION_CONTEXT_PATH_LEAK")

    def test_writer_guard_is_a_superset_of_the_cli_guard(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location("hfic_forge_cli_guard", ROOT_DIR / "scripts" / "hypothesis_forge.py")
        forge = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(forge)
        self.assertEqual(forge._WINDOWS_PHYSICAL_PATH_RE.pattern, disp.CLI_PHYSICAL_PATH_RE.pattern)
        self.assertEqual(forge._WINDOWS_PHYSICAL_PATH_RE.flags, disp.CLI_PHYSICAL_PATH_RE.flags)

    def test_capsule_shrinks_first_under_packet_budget(self) -> None:
        import contextlib
        import io
        import importlib.util

        from solana_alpha_lab.factory import hfic_preflight
        from solana_alpha_lab.factory.hfic_preflight import canonical_json_bytes

        ctx, *_ = self._recorded()
        spec = importlib.util.spec_from_file_location("hfic_forge_cli_budget", ROOT_DIR / "scripts" / "hypothesis_forge.py")
        forge = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(forge)

        def preflight() -> dict:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = forge.main(
                    ["--root", str(ROOT_DIR), "--data-root", str(ctx["root"]), "preflight", "--discovery-contract",
                     "--owner-focus", FOCUS, "--format", "json"]
                )
            self.assertEqual(code, 0, out.getvalue()[-400:])
            return json.loads(out.getvalue())["forge_context_packet"]

        baseline = preflight()
        capsule = baseline["scientific_disposition_context"]
        full = len(canonical_json_bytes(baseline))
        saved = len(canonical_json_bytes(capsule)) - len(canonical_json_bytes(disp.compact_counts_only(capsule)))
        self.assertGreater(saved, 600)
        bound = full - saved + 300
        with mock.patch.object(hfic_preflight, "forge_context_packet_max_bytes", return_value=bound):
            squeezed = preflight()
        reduced = squeezed["scientific_disposition_context"]
        self.assertTrue(reduced["reduced_for_packet_budget"])
        self.assertEqual(reduced["entries"], [])
        self.assertEqual(reduced["omitted"], capsule["total_subjects"])
        self.assertIn("disposition-show", reduced["detail_query"])
        # Scientific and navigation sections are untouched.
        self.assertEqual(squeezed["semantic_capability_entries"], baseline["semantic_capability_entries"])
        self.assertEqual(squeezed["feature_grounding_entries"], baseline["feature_grounding_entries"])
        self.assertFalse(squeezed["truncation_receipt"].get("feature_grounding_truncated"))
        # Inside the window the reduced capsule cannot fit either: advice goes first, entirely.
        reduced_bytes = len(canonical_json_bytes(disp.compact_counts_only(capsule)))
        tight = full - len(canonical_json_bytes(capsule)) + reduced_bytes // 2
        with mock.patch.object(hfic_preflight, "forge_context_packet_max_bytes", return_value=tight):
            dropped = preflight()
        self.assertNotIn("scientific_disposition_context", dropped)
        self.assertEqual(dropped["truncation_receipt"]["disposition_subjects_omitted"], capsule["total_subjects"])
        self.assertEqual(dropped["semantic_capability_entries"], baseline["semantic_capability_entries"])
        self.assertEqual(dropped["feature_grounding_entries"], baseline["feature_grounding_entries"])

    def test_packets_without_assessment_history_keep_their_shape(self) -> None:
        ctx = _ctx(self.workspace())
        packet = _preflight(ctx["root"])["forge_context_packet"]
        self.assertNotIn("scientific_disposition_context", packet)

    def test_not_recorded_is_scoped_and_matches_the_detail_query(self) -> None:
        ctx = _ctx(self.workspace())
        root = ctx["root"]
        run = _forge_run(root)
        shown = _show(root)
        expected = sorted([ctx["q1"]["record_id"], ctx["q2"]["record_id"]])
        self.assertEqual(sorted(item["result_ref"] for item in run["scientific_disposition_context"]["not_recorded"]), expected)
        self.assertEqual(sorted(item["result_ref"] for item in shown["not_recorded"]), expected)
        row = next(item for item in shown["not_recorded"] if item["result_ref"] == ctx["q2"]["record_id"])
        # Everything the writer needs is in the row.
        self.assertEqual(row["result_sha256"], ctx["q2"]["result_sha256"])
        self.assertEqual(row["calculation_version"], ctx["q2"]["calculation_version"])
        self.assertEqual(row["question_spec_sha256"], ctx["q2"]["spec_sha256"])
        self.assertEqual(row["market_evidence_epoch_sha256"], ctx["market"])
        self.assertIn(f"sha256={ctx['q2']['result_sha256']}", run["_stderr"])
        store = ResearchStore(root, create_if_missing=False)
        first = disp.record_disposition(store, question_packet(ctx, ctx["q1"]), current_market=ctx["market"])
        after = disp.disposition_context(store, owner_focus=FOCUS, current_market=ctx["market"])
        self.assertEqual([item["result_ref"] for item in after["not_recorded"]], [ctx["q2"]["record_id"]])
        # A withdrawn assessment no longer covers its question.
        disp.record_disposition(
            store,
            {
                "entry": "WITHDRAWAL",
                "subject": question_packet(ctx, ctx["q1"])["subject"],
                "withdrawal": {"reason": "wrong question text"},
                "supersedes": {"record_id": first["record_id"], "disposition_sha256": first["disposition_sha256"]},
                "provenance": {"author_role": "OPERATOR", "source_episode": "SYNTHETIC-WITHDRAWAL", "source_refs": []},
            },
            current_market=ctx["market"],
        )
        final = disp.disposition_context(store, owner_focus=FOCUS, current_market=ctx["market"])
        # The withdrawn question is shown once, as WITHDRAWN with how to re-assess.
        self.assertEqual([item["result_ref"] for item in final["not_recorded"]], [ctx["q2"]["record_id"]])
        self.assertEqual(final["status_counts"], {disp.STATUS_NOT_RECORDED: 1, disp.STATUS_WITHDRAWN: 1})
        lines = "\n".join(disp.format_context_lines(final))
        self.assertIn("withdrawn because: wrong question text", lines)
        self.assertIn("advice_next: none required; a new assessment uses disposition-record with supersedes=", lines)

    def test_historical_import_paths(self) -> None:
        ctx = _ctx(self.workspace())
        store = ResearchStore(ctx["root"], create_if_missing=False)
        source_sha = hashlib.sha256(b"synthetic historical readout").hexdigest()

        def imported(packet: dict) -> dict:
            packet["provenance"].update(
                {"mode": "HISTORICAL_IMPORT", "source_sha256": source_sha, "source_encoding": "utf-8", "assessed_at": "UNKNOWN"}
            )
            return packet

        question = imported(question_packet(ctx, ctx["q1"]))
        code, written = _cli_record(ctx["root"], question)
        self.assertEqual(code, 0, written)
        self.assertEqual(written["readback"]["status"], disp.STATUS_CURRENT)
        missing_sha = question_packet(ctx, ctx["q2"])
        missing_sha["provenance"]["mode"] = "HISTORICAL_IMPORT"
        with self.assertRaises(disp.DispositionError) as caught:
            disp.record_disposition(store, missing_sha, current_market=ctx["market"])
        self.assertEqual(caught.exception.code, "DISPOSITION_IMPORT_SOURCE_SHA_REQUIRED")
        no_frontier = imported(search_packet(ctx, [ctx["q1"], ctx["q2"]]))
        with self.assertRaises(disp.DispositionError) as caught:
            disp.record_disposition(store, no_frontier, current_market=ctx["market"])
        self.assertEqual(caught.exception.code, "DISPOSITION_IMPORT_FRONTIER_REQUIRED")
        unresolved = imported(search_packet(ctx, [ctx["q1"]]))
        unresolved["basis"]["journal_frontier"] = {
            "attempts": [{"attempt_ref": "X", "evidence_ref": "HFIC-ART-DISCOVERY-" + "C" * 40,
                          "result_sha256": "0" * 64, "calculation_version": "V4"}]
        }
        with self.assertRaises(disp.DispositionError) as caught:
            disp.record_disposition(store, unresolved, current_market=ctx["market"])
        self.assertEqual(caught.exception.code, "DISPOSITION_FRONTIER_UNRESOLVED")
        # The historical author saw only q1: importing that frontier reads REVIEW_REQUIRED, not current.
        older = imported(search_packet(ctx, [ctx["q1"]]))
        older["basis"]["journal_frontier"] = {
            "attempts": [{"attempt_ref": ctx["q1"]["record_id"], "evidence_ref": ctx["q1"]["record_id"],
                          "result_sha256": ctx["q1"]["result_sha256"], "calculation_version": ctx["q1"]["calculation_version"]}]
        }
        wrong_root = json.loads(json.dumps(older))
        wrong_root["basis"]["journal_frontier"]["attempts"][0]["attempt_ref"] = "attempt-7605"
        with self.assertRaises(disp.DispositionError) as caught:
            disp.record_disposition(store, wrong_root, current_market=ctx["market"])
        self.assertEqual(caught.exception.code, "DISPOSITION_FRONTIER_UNRESOLVED")
        frontiers = _show(ctx["root"])["journal_frontiers"][ctx["journal"]]["attempts"]
        self.assertIn(older["basis"]["journal_frontier"]["attempts"][0], frontiers)
        preview_code, preview = _cli_record(ctx["root"], older, "--preview")
        self.assertEqual(preview_code, 0, preview)
        self.assertTrue(preview["would_append"])
        self.assertEqual(preview["would_be_applicability"], {"status": disp.STATUS_REVIEW, "reasons": ["FRONTIER_CHANGED", "NEW_ATTEMPTS:1"]})
        self.assertEqual(preview["writes"], {"research_store": 0})
        code, written = _cli_record(ctx["root"], older)
        self.assertEqual(code, 0, written)
        self.assertEqual(written["record_id"], preview["record_id"])
        entry = next(
            item
            for item in disp.disposition_context(
                store, owner_focus=FOCUS, current_market=ctx["market"], journal_scope=ctx["journal"]
            )["entries"]
            if item["ref"] == written["record_id"]
        )
        self.assertEqual(entry["status"], disp.STATUS_REVIEW)
        self.assertEqual(entry["reasons"], ["FRONTIER_CHANGED", "NEW_ATTEMPTS:1"])
        body = _show(ctx["root"], "--record-id", written["record_id"])["records"][0]["body"]
        self.assertEqual(body["provenance"]["mode"], "HISTORICAL_IMPORT")
        self.assertEqual(body["provenance"]["source_sha256"], source_sha)

    def test_localized_hash_mismatch_blocks_writes_to_that_subject_only(self) -> None:
        ctx, q1, q2, _s1 = self._recorded()
        store = ResearchStore(ctx["root"], create_if_missing=False)
        body = json.loads(json.dumps(disp._View(store).by_subject()[q1["subject_key"]][0]["body"]))
        body["judgement"]["rationale"] = "tampered after hashing"
        body["supersedes"] = {"record_id": q1["record_id"], "disposition_sha256": q1["disposition_sha256"]}
        # FAULT INJECTION: keep the stale disposition_sha256 so the body no longer matches its hash.
        canonical = disp._canonical(body)
        wrapper = {"artifact_kind": disp.ARTIFACT_KIND, "payload_canonical": canonical,
                   "payload_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest()}
        _inject(ctx["root"], record_id="HFIC-ART-DISP-" + "E" * 40, payload_json=json.dumps(wrapper))
        capsule = disp.disposition_context(store, owner_focus=FOCUS, current_market=ctx["market"])
        by_key = {item["subject_key"]: item for item in capsule["entries"]}
        self.assertEqual(by_key[q1["subject_key"]]["status"], disp.STATUS_UNREADABLE)
        self.assertEqual(by_key[q1["subject_key"]]["owner_action"], "STOP_OWNER_RESOLUTION")
        self.assertTrue(any(reason.startswith("DISPOSITION_HASH_MISMATCH") for reason in by_key[q1["subject_key"]]["reasons"]))
        self.assertEqual(by_key[q2["subject_key"]]["status"], disp.STATUS_CURRENT)
        follow = question_packet(ctx, ctx["q1"])
        follow["supersedes"] = {"record_id": q1["record_id"], "disposition_sha256": q1["disposition_sha256"]}
        follow["judgement"]["rationale"] = "successor on a damaged subject"
        with self.assertRaises(disp.DispositionError) as caught:
            disp.record_disposition(store, follow, current_market=ctx["market"])
        self.assertEqual(caught.exception.code, "DISPOSITION_SUBJECT_UNREADABLE")
        self.assertIn("STOP for this subject", "\n".join(disp.format_context_lines(capsule)))

    def test_auto_focus_is_labelled_not_empty(self) -> None:
        lines = disp.format_context_lines(
            {"owner_focus": "AUTO", "focus_resolved": False, "market_verified": True, "entries": [],
             "not_recorded": [], "detail_query": "q"}
        )
        self.assertIn("not a named focus", "\n".join(lines))
        self.assertNotIn("none recorded", "\n".join(lines))


if __name__ == "__main__":
    unittest.main()
