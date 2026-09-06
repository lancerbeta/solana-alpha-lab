from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.application import FactoryApplication
from solana_alpha_lab.factory.experiment_evidence import evidence_snapshot_sha256
from solana_alpha_lab.factory.lifecycle_projection import build_lifecycle_projection
from solana_alpha_lab.factory.promotion_handoff import (
    compose_science_to_strategy_handoff,
    freeze_promotion_handoff_manifest,
    materialize_strategy_candidate,
    render_strategy_version,
)
from solana_alpha_lab.factory.research_store import ResearchEvent, ResearchStore
from solana_alpha_lab.factory.research_workbench import LifecycleEntityLocatorV1
from solana_alpha_lab.factory.workbench import serve
from solana_alpha_lab.factory_semantic_operability import (
    load_semantic_catalog_views,
    load_semantic_projection,
    search_semantic_routes,
)

EXPERIMENT_ID = "EXP-ORDINARY-PRICE-PATH-HYPOTHESIS-001"
HYPOTHESIS_ID = "HYP-ORDINARY-PRICE-PATH-BUY-PRESSURE-V1"
LOCATOR = LifecycleEntityLocatorV1(EXPERIMENT_ID, "GIT", "EXPERIMENT_SPEC")
NOW = datetime(2026, 9, 6, 12, 0, tzinfo=UTC)
EXECUTION_INPUTS = {
    "max_age_seconds": 30,
    "notional_usd": 25.0,
    "fee_bps": 100,
    "max_open_positions": 1,
    "shadow": False,
}


def _event(
    *,
    record_id: str,
    record_kind: str,
    entity_id: str,
    payload: dict,
    hypothesis_version_id: str | None = None,
    transaction_id: str,
    run_id: str | None = None,
) -> ResearchEvent:
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return ResearchEvent(
        record_id=record_id,
        record_kind=record_kind,
        entity_id=entity_id,
        hypothesis_version_id=hypothesis_version_id,
        run_id=run_id,
        transaction_id=transaction_id,
        effective_at=NOW,
        first_reliable_available_at=NOW,
        supersedes_record_id=None,
        payload_json=payload_json,
        payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        schema_version="1.0",
        producer_capability_id="CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
        producer_git_sha="a" * 40,
        created_at=NOW,
    )


def _inventory(path: Path) -> dict[str, str]:
    digest: dict[str, str] = {}
    if not path.exists():
        return digest
    for item in sorted(path.rglob("*")):
        if item.is_file():
            digest[item.relative_to(path).as_posix()] = hashlib.sha256(
                item.read_bytes()
            ).hexdigest()
    return digest


def _http(app: FactoryApplication, method: str, path: str, body: str | None = None):
    server = serve(app, host="127.0.0.1", port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        conn = HTTPConnection(host, port, timeout=12)
        headers = {"Content-Type": "application/x-www-form-urlencoded"} if body else {}
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        payload = response.read().decode("utf-8")
        status = response.status
        conn.close()
        return status, payload
    finally:
        server.shutdown()
        server.server_close()


def _scientific_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "experiment_id": EXPERIMENT_ID,
        "availability_cutoff": "2026-09-01T00:00:00Z",
        "first_reliable_available_at": "2026-09-01T01:00:00Z",
        "availability_provenance": "GIT_CANONICAL_RECEIPT",
        "observed_n": 24,
        "missing_count": 3,
        "survival_visible": 21,
        "holdout_applicable": False,
        "holdout_consumption_ids": [],
        "entry_artifact_id": "ART-ENTRY-001",
        "exit_artifact_id": "ART-EXIT-001",
        "cost_assumptions_artifact_id": "ART-COST-001",
        "outcome": "INCONCLUSIVE",
        "uncertainty": ["SMALL_SAMPLE"],
        "robustness": "HOLD_SPLIT",
        "evidence_class": "DIAGNOSTIC",
    }
    payload.update(overrides)
    return payload


def _eligible_records() -> list[ResearchEvent]:
    return [
        _event(
            record_id="RUN-ELIGIBLE-001",
            record_kind="RUN_COMPLETED",
            entity_id="RUN-ELIGIBLE-001",
            run_id="RUN-ELIGIBLE-001",
            hypothesis_version_id=HYPOTHESIS_ID,
            payload={
                "experiment_id": EXPERIMENT_ID,
                "run_id": "RUN-ELIGIBLE-001",
                "availability_cutoff": "2026-09-01T00:00:00Z",
                "first_reliable_available_at": "2026-09-01T00:00:00Z",
                "observed_n": 24,
                "robustness": "HOLD_SPLIT",
                "outcome": "INCONCLUSIVE",
            },
            transaction_id="RESEARCH-TXN-ELIGIBLE-001",
        ),
        _event(
            record_id="EVIDENCE-BINDING-ELIGIBLE-001",
            record_kind="EVIDENCE_BINDING",
            entity_id="EVIDENCE-BINDING-ELIGIBLE-001",
            hypothesis_version_id=HYPOTHESIS_ID,
            payload=_scientific_payload(),
            transaction_id="RESEARCH-TXN-ELIGIBLE-001",
        ),
    ]


def _app(data_root: Path) -> FactoryApplication:
    return FactoryApplication(
        root=ROOT,
        spec_relative="configs/experiment_specs/ordinary_price_path_buy_pressure_v1.yaml",
        research_data_root=data_root,
    )


def _promote(app: FactoryApplication) -> dict:
    eligible = app.research_detail(LOCATOR)
    return app.record_research_decision(
        {
            "entity_id": EXPERIMENT_ID,
            "truth_plane": "GIT",
            "native_kind": "EXPERIMENT_SPEC",
            "decision_kind": "PROMOTE",
            "expected_evidence_snapshot_sha256": eligible["dossier"][
                "evidence_snapshot_sha256"
            ],
            "promote_scientific_only": "1",
            "rationale": "Научное продвижение только. StrategyVersion не создавать.",
        }
    )


def _schema_root(tmp: Path) -> Path:
    (tmp / "catalog" / "schemas").mkdir(parents=True)
    (tmp / "configs" / "strategies").mkdir(parents=True)
    shutil.copy(
        ROOT / "catalog/schemas/strategy_version_v1_1.schema.json",
        tmp / "catalog/schemas/strategy_version_v1_1.schema.json",
    )
    shutil.copy(
        ROOT / "catalog/schemas/promotion_handoff_manifest_v1.schema.json",
        tmp / "catalog/schemas/promotion_handoff_manifest_v1.schema.json",
    )
    return tmp


class ScienceToStrategyHandoffTests(unittest.TestCase):
    def test_scenario_a_happy_path_vertical(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            store = ResearchStore(data_root)
            store.append(_eligible_records(), transaction_id="RESEARCH-TXN-ELIGIBLE-001")
            app = _app(data_root)
            before = evidence_snapshot_sha256
            recorded = _promote(app)
            history = recorded["dossier"]["decision_history"]
            promote = [item for item in history if item.get("decision_kind") == "PROMOTE"][-1]
            manifest = None
            for record in store.iter_committed_records():
                if record.record_id == recorded["decision_result"]["decision_event_id"]:
                    manifest = json.loads(record.payload_json)["promotion_handoff_manifest"]
            self.assertIsNotNone(manifest)
            self.assertEqual(before, evidence_snapshot_sha256)
            self.assertFalse(recorded["decision_result"]["creates_strategy_version"])
            self.assertEqual(
                promote["promotion_handoff_manifest_sha256"],
                manifest["manifest_sha256"],
            )
            handoff = recorded["dossier"]["science_to_strategy_handoff"]
            self.assertEqual(handoff["state"]["handoff_state"], "BLOCKED")
            self.assertIn("EXECUTION_INPUT_GAP", handoff["state"]["blocker_codes"])
            rendered = materialize_strategy_candidate(
                root=ROOT,
                manifest=manifest,
                decision_event_id=recorded["decision_result"]["decision_event_id"],
                created_at="2026-09-06T12:00:00Z",
                execution_inputs=EXECUTION_INPUTS,
            )
            self.assertEqual(rendered["handoff_state"], "READY_TO_MATERIALIZE")
            self.assertEqual(rendered["disposition"], "RENDERED")
            self.assertEqual(rendered["candidate"]["schema_version"], "1.1")
            self.assertFalse(rendered["authority_granted"])
            self.assertFalse(rendered["activation_created"])
            projection = build_lifecycle_projection(
                ROOT,
                research_store=store,
                projected_at="2026-09-06T12:00:00Z",
            )
            decision_id = recorded["decision_result"]["decision_event_id"]
            related = [
                item
                for item in projection["relations"]
                if item.get("relation_type") == "DECISION_FOR_EXPERIMENT"
                and item.get("from_entity_id") == decision_id
            ]
            self.assertEqual(related[0]["to_entity_id"], EXPERIMENT_ID)
            self.assertEqual(related[0]["resolution"], "RESOLVED")
            href = (
                f"/research?entity_id={EXPERIMENT_ID}"
                "&truth_plane=GIT&native_kind=EXPERIMENT_SPEC"
            )
            status, body = _http(app, "GET", href)
            self.assertEqual(status, 200)
            self.assertIn("Переход в стратегию", body)
            self.assertIn("Переход заблокирован", body)
            self.assertIn("EXECUTION_INPUT_GAP", body)
            self.assertIn("PAPER", body)
            self.assertNotIn("Create strategy and commit", body)
            self.assertNotIn("Promote &amp; run", body)

    def test_scenario_b_later_evidence_does_not_rewrite_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            store = ResearchStore(data_root)
            store.append(_eligible_records(), transaction_id="RESEARCH-TXN-ELIGIBLE-001")
            app = _app(data_root)
            recorded = _promote(app)
            event_id = recorded["decision_result"]["decision_event_id"]
            frozen = None
            for record in store.iter_committed_records():
                if record.record_id == event_id:
                    frozen = json.loads(record.payload_json)["promotion_handoff_manifest"]
            store.append(
                [
                    _event(
                        record_id="EVIDENCE-BINDING-LATER-001",
                        record_kind="EVIDENCE_BINDING",
                        entity_id="EVIDENCE-BINDING-LATER-001",
                        hypothesis_version_id=HYPOTHESIS_ID,
                        payload=_scientific_payload(observed_n=48),
                        transaction_id="RESEARCH-TXN-LATER-001",
                    )
                ],
                transaction_id="RESEARCH-TXN-LATER-001",
            )
            later = app.research_detail(LOCATOR)
            self.assertNotEqual(
                later["dossier"]["evidence_snapshot_sha256"],
                frozen["evidence_snapshot_sha256"],
            )
            still = None
            for record in store.iter_committed_records():
                if record.record_id == event_id:
                    still = json.loads(record.payload_json)["promotion_handoff_manifest"]
            self.assertEqual(still, frozen)
            self.assertEqual(
                later["dossier"]["science_to_strategy_handoff"]["science"][
                    "handoff_manifest_sha256"
                ],
                frozen["manifest_sha256"],
            )

    def test_scenario_c_legacy_promote_is_explicit_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            store = ResearchStore(data_root)
            store.append(
                [
                    _event(
                        record_id="DECISION-EVENT-LEGACY-001",
                        record_kind="DECISION_EVENT",
                        entity_id="DECISION-EVENT-LEGACY-001",
                        hypothesis_version_id=HYPOTHESIS_ID,
                        payload={
                            "decision_event_id": "DECISION-EVENT-LEGACY-001",
                            "decision_kind": "PROMOTE",
                            "target_entity_id": EXPERIMENT_ID,
                            "target_native_kind": "EXPERIMENT_SPEC",
                            "evidence_snapshot_sha256": "ab" * 32,
                            "creates_strategy_version": False,
                        },
                        transaction_id="RESEARCH-TXN-LEGACY-001",
                    )
                ],
                transaction_id="RESEARCH-TXN-LEGACY-001",
            )
            handoff = compose_science_to_strategy_handoff(
                root=ROOT,
                experiment_id=EXPERIMENT_ID,
                records=tuple(store.iter_committed_records()),
                records_status="AVAILABLE",
            )
            self.assertEqual(handoff["state"]["handoff_state"], "BLOCKED")
            self.assertEqual(handoff["state"]["blocker_codes"], ["LEGACY_PROVENANCE_GAP"])
            self.assertEqual(handoff["provenance"]["manifest_status"], "LEGACY_ABSENT")

    def test_scenario_d_execution_input_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            store = ResearchStore(data_root)
            store.append(_eligible_records(), transaction_id="RESEARCH-TXN-ELIGIBLE-001")
            app = _app(data_root)
            recorded = _promote(app)
            self.assertEqual(recorded["dossier"]["planes"]["decision"], "PROMOTE")
            handoff = recorded["dossier"]["science_to_strategy_handoff"]
            self.assertEqual(handoff["state"]["handoff_state"], "BLOCKED")
            self.assertIn("EXECUTION_INPUT_GAP", handoff["state"]["blocker_codes"])
            self.assertIsNone(handoff["materialization"]["strategy_identity"])

    def test_scenario_e_and_f_collision_and_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            store = ResearchStore(data_root)
            store.append(_eligible_records(), transaction_id="RESEARCH-TXN-ELIGIBLE-001")
            app = _app(data_root)
            recorded = _promote(app)
            event_id = recorded["decision_result"]["decision_event_id"]
            manifest = freeze_promotion_handoff_manifest(
                recorded["dossier"], root=ROOT
            )
            candidate = render_strategy_version(
                root=ROOT,
                manifest=manifest,
                decision_event_id=event_id,
                created_at="2026-09-06T12:00:00Z",
                execution_inputs=EXECUTION_INPUTS,
            )
            schema_root = _schema_root(Path(tmp) / "git")
            replay = dict(candidate)
            (schema_root / "configs" / "strategies" / "replay.yaml").write_text(
                yaml.safe_dump(replay, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )
            identical = materialize_strategy_candidate(
                root=schema_root,
                manifest=manifest,
                decision_event_id=event_id,
                created_at="2026-09-06T12:00:00Z",
                execution_inputs=EXECUTION_INPUTS,
            )
            self.assertEqual(identical["handoff_state"], "MATERIALIZED")
            self.assertEqual(identical["disposition"], "REPLAY_IDENTICAL")
            conflicted = dict(replay)
            conflicted["notional_policy"] = {"notional_usd": 99.0, "fee_bps": 100}
            unsigned = {key: value for key, value in conflicted.items() if key != "spec_sha256"}
            from solana_alpha_lab.factory.strategy_runtime import canonical_spec_sha256

            conflicted["spec_sha256"] = canonical_spec_sha256(unsigned)
            (schema_root / "configs" / "strategies" / "replay.yaml").write_text(
                yaml.safe_dump(conflicted, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )
            clash = materialize_strategy_candidate(
                root=schema_root,
                manifest=manifest,
                decision_event_id=event_id,
                created_at="2026-09-06T12:00:00Z",
                execution_inputs=EXECUTION_INPUTS,
            )
            self.assertEqual(clash["handoff_state"], "CONFLICT")
            self.assertIn("STRATEGY_CONTENT_CONFLICT", clash["blocker_codes"])
            self.assertIsNone(clash["candidate"])

    def test_scenario_g_get_is_non_mutating(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            store = ResearchStore(data_root)
            store.append(_eligible_records(), transaction_id="RESEARCH-TXN-ELIGIBLE-001")
            app = _app(data_root)
            _promote(app)
            before_store = _inventory(data_root)
            before_git = _inventory(ROOT / "configs" / "strategies")
            href = (
                f"/research?entity_id={EXPERIMENT_ID}"
                "&truth_plane=GIT&native_kind=EXPERIMENT_SPEC"
            )
            status, body = _http(app, "GET", href)
            self.assertEqual(status, 200)
            self.assertIn("Переход в стратегию", body)
            self.assertEqual(_inventory(data_root), before_store)
            self.assertEqual(_inventory(ROOT / "configs" / "strategies"), before_git)

    def test_scenario_h_no_activation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            store = ResearchStore(data_root)
            store.append(_eligible_records(), transaction_id="RESEARCH-TXN-ELIGIBLE-001")
            app = _app(data_root)
            recorded = _promote(app)
            kinds = {
                str(getattr(item.record_kind, "value", item.record_kind))
                for item in store.iter_committed_records()
            }
            self.assertNotIn("ACTIVATION_EPOCH", kinds)
            self.assertFalse(
                recorded["dossier"]["science_to_strategy_handoff"]["authority"][
                    "activation_created"
                ]
            )
            self.assertFalse(recorded["decision_result"]["creates_strategy_version"])
            paper = ROOT / "local" / "factory_v1" / "paper_plane_state.sqlite"
            if paper.is_file():
                before = paper.stat().st_mtime_ns
                href = (
                    f"/research?entity_id={EXPERIMENT_ID}"
                    "&truth_plane=GIT&native_kind=EXPERIMENT_SPEC"
                )
                _http(app, "GET", href)
                self.assertEqual(paper.stat().st_mtime_ns, before)

    def test_deterministic_render_and_snapshot_meaning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            store = ResearchStore(data_root)
            store.append(_eligible_records(), transaction_id="RESEARCH-TXN-ELIGIBLE-001")
            app = _app(data_root)
            recorded = _promote(app)
            event_id = recorded["decision_result"]["decision_event_id"]
            manifest = freeze_promotion_handoff_manifest(
                recorded["dossier"], root=ROOT
            )
            first = render_strategy_version(
                root=ROOT,
                manifest=manifest,
                decision_event_id=event_id,
                created_at="2026-09-06T12:00:00Z",
                execution_inputs=EXECUTION_INPUTS,
            )
            second = render_strategy_version(
                root=ROOT,
                manifest=manifest,
                decision_event_id=event_id,
                created_at="2026-09-06T12:00:00Z",
                execution_inputs=EXECUTION_INPUTS,
            )
            self.assertEqual(first, second)
            self.assertEqual(
                recorded["dossier"]["evidence_snapshot_sha256"],
                manifest["evidence_snapshot_sha256"],
            )

    def test_semantic_gold_query(self) -> None:
        projection = load_semantic_projection(ROOT)
        assets, bindings, _queries = load_semantic_catalog_views(ROOT)
        for query in (
            "How does an accepted scientific experiment become a StrategyVersion?",
            "Почему эта стратегия вообще существует и каким evidence она разрешена?",
        ):
            hits = search_semantic_routes(
                projection, query, assets=assets, bindings=bindings, limit=5
            )
            self.assertEqual(hits[0]["semantic_route_id"], "SEM-OWNER-LIFECYCLE", query)
        handoff = assets["DOC-SCIENCE-TO-STRATEGY-HANDOFF-001"]
        related = {item["target_asset_id"] for item in handoff.get("relations") or []}
        self.assertIn("DOC-EXPERIMENT-EVIDENCE-DECISION-001", related)
        self.assertIn("SCHEMA-STRATEGY-VERSION-V1-1-001", related)


if __name__ == "__main__":
    unittest.main()
