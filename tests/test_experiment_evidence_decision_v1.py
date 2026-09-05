from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.application import ApplicationError, FactoryApplication
from solana_alpha_lab.factory.experiment_evidence import (
    OWNER_DECISION_KINDS,
    classify_record,
    compose_experiment_dossier,
    science_guard,
)
from solana_alpha_lab.factory.lifecycle_projection import build_lifecycle_projection
from solana_alpha_lab.factory.owner_language import FORBIDDEN_RESEARCH_FIXED_LABELS
from solana_alpha_lab.factory.research_store import (
    ResearchEvent,
    ResearchStore,
    ResearchStoreError,
)
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


def _eligible_run() -> ResearchEvent:
    return _event(
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
            "robustness": "NOT_TESTED",
            "evidence_class": "DIAGNOSTIC",
        },
        transaction_id="RESEARCH-TXN-ELIGIBLE-001",
    )


class ExperimentEvidenceDecisionTests(unittest.TestCase):
    def test_real_incomplete_experiment_is_truthful(self) -> None:
        projection = build_lifecycle_projection(ROOT, projected_at="2026-09-06T00:00:00Z")
        dossier = compose_experiment_dossier(
            projection,
            LOCATOR,
            root=ROOT,
            records=(),
            records_status="NOT_PRESENT",
            write_capability={"read": "AVAILABLE", "write": "UNAVAILABLE"},
        )
        self.assertEqual(dossier["tested"]["hypothesis_version_id"], HYPOTHESIS_ID)
        self.assertTrue(dossier["tested"]["question"])
        statuses = {item["code"]: item["status"] for item in dossier["obligations"]}
        self.assertEqual(statuses["FALSIFIER"], "PRESENT")
        self.assertIn(statuses["RESULT"], {"MISSING", "UNKNOWN"})
        self.assertNotEqual(statuses["MISSINGNESS"], "NOT_APPLICABLE")
        self.assertFalse(dossier["science_guard"]["allowed"])
        self.assertEqual(dossier["planes"]["execution"], "NO_RUN")
        self.assertEqual(dossier["planes"]["decision"], "NO_DECISION")
        self.assertNotEqual(dossier["planes"]["execution"], dossier["planes"]["evidence"])

    def test_direct_vs_related_classification(self) -> None:
        run = _eligible_run()
        prior = _event(
            record_id="TRIAL-PRIOR-SAME-HYP-001",
            record_kind="TRIAL",
            entity_id="TRIAL-PRIOR-SAME-HYP-001",
            hypothesis_version_id=HYPOTHESIS_ID,
            payload={"trial_id": "TRIAL-PRIOR-SAME-HYP-001", "outcome": "NEGATIVE"},
            transaction_id="RESEARCH-TXN-PRIOR-001",
        )
        self.assertEqual(
            classify_record(
                run,
                experiment_id=EXPERIMENT_ID,
                hypothesis_version_id=HYPOTHESIS_ID,
                direct_run_ids={"RUN-ELIGIBLE-001"},
                direct_trial_ids=set(),
            ),
            "DIRECT",
        )
        self.assertEqual(
            classify_record(
                prior,
                experiment_id=EXPERIMENT_ID,
                hypothesis_version_id=HYPOTHESIS_ID,
                direct_run_ids={"RUN-ELIGIBLE-001"},
                direct_trial_ids=set(),
            ),
            "RELATED",
        )
        projection = build_lifecycle_projection(ROOT, projected_at="2026-09-06T00:00:00Z")
        dossier = compose_experiment_dossier(
            projection,
            LOCATOR,
            root=ROOT,
            records=(run, prior),
            records_status="AVAILABLE",
        )
        direct_ids = {item["record_id"] for item in dossier["direct_evidence"]}
        related_ids = {item["record_id"] for item in dossier["related_prior_memory"]}
        self.assertIn("RUN-ELIGIBLE-001", direct_ids)
        self.assertIn("TRIAL-PRIOR-SAME-HYP-001", related_ids)
        self.assertNotIn("TRIAL-PRIOR-SAME-HYP-001", direct_ids)

    def test_degraded_source_keeps_definition_and_unknown_obligations(self) -> None:
        projection = build_lifecycle_projection(ROOT, projected_at="2026-09-06T00:00:00Z")
        dossier = compose_experiment_dossier(
            projection,
            LOCATOR,
            root=ROOT,
            records=None,
            records_status="UNAVAILABLE",
        )
        self.assertTrue(dossier["tested"]["question"])
        statuses = {item["code"]: item["status"] for item in dossier["obligations"]}
        self.assertEqual(statuses["FALSIFIER"], "PRESENT")
        self.assertEqual(statuses["RESULT"], "UNKNOWN")
        self.assertFalse(dossier["science_guard"]["allowed"])

    def test_get_experiment_detail_is_non_mutating(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            store = ResearchStore(data_root)
            store.append([_eligible_run()], transaction_id="RESEARCH-TXN-ELIGIBLE-001")
            before = _inventory(data_root)
            app = FactoryApplication(
                root=ROOT,
                spec_relative="configs/experiment_specs/ordinary_price_path_buy_pressure_v1.yaml",
                research_data_root=data_root,
            )
            href = (
                f"/research?entity_id={EXPERIMENT_ID}"
                "&truth_plane=GIT&native_kind=EXPERIMENT_SPEC"
            )
            status, body = _http(app, "GET", href)
            self.assertEqual(status, 200)
            self.assertIn("Что проверяли", body)
            self.assertEqual(_inventory(data_root), before)

    def test_owner_language_ru_pass(self) -> None:
        app = FactoryApplication(
            root=ROOT,
            spec_relative="configs/experiment_specs/ordinary_price_path_buy_pressure_v1.yaml",
        )
        status, overview = _http(app, "GET", "/research")
        self.assertEqual(status, 200)
        self.assertIn("Исследования", overview)
        self.assertIn("Активно сейчас", overview)
        self.assertIn("Требует внимания", overview)
        self.assertIn("<th>вид</th>", overview)
        href = (
            f"/research?entity_id={EXPERIMENT_ID}"
            "&truth_plane=GIT&native_kind=EXPERIMENT_SPEC"
        )
        _, detail = _http(app, "GET", href)
        self.assertIn("Прямые доказательства", detail)
        self.assertIn("Связанные прошлые исследования", detail)
        self.assertIn("Решение", detail)
        for label in FORBIDDEN_RESEARCH_FIXED_LABELS:
            self.assertNotIn(label, overview)
            self.assertNotIn(label, detail)
        self.assertIn(EXPERIMENT_ID, detail)
        self.assertIn("UNKNOWN", detail)
        self.assertNotIn("gettext", detail)
        self.assertNotIn("i18next", detail)

    def test_decision_loop_stale_retry_and_writer_busy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            store = ResearchStore(data_root)
            store.append([_eligible_run()], transaction_id="RESEARCH-TXN-ELIGIBLE-001")
            app = FactoryApplication(
                root=ROOT,
                spec_relative="configs/experiment_specs/ordinary_price_path_buy_pressure_v1.yaml",
                research_data_root=data_root,
            )
            detail = app.research_detail(LOCATOR)
            snapshot = detail["dossier"]["evidence_snapshot_sha256"]
            command = {
                "entity_id": EXPERIMENT_ID,
                "truth_plane": "GIT",
                "native_kind": "EXPERIMENT_SPEC",
                "decision_kind": "REJECT",
                "expected_evidence_snapshot_sha256": snapshot,
                "rationale": "Отклоняю: доказательств недостаточно.",
            }
            recorded = app.record_research_decision(command)
            self.assertEqual(recorded["decision_result"]["status"], "DECISION_RECORDED")
            self.assertEqual(recorded["dossier"]["planes"]["decision"], "REJECT")
            replay = app.record_research_decision(command)
            self.assertEqual(replay["decision_result"]["status"], "DECISION_RECORDED")
            self.assertEqual(replay["decision_result"]["disposition"], "REPLAY_IDENTICAL")
            decisions = [
                item
                for item in recorded["dossier"]["decision_history"]
                if item.get("decision_kind") == "REJECT"
            ]
            replay_decisions = [
                item
                for item in replay["dossier"]["decision_history"]
                if item.get("decision_kind") == "REJECT"
            ]
            self.assertEqual(len(replay_decisions), len(decisions))
            self.assertEqual(len(decisions), 1)

            store.append(
                [
                    _event(
                        record_id="METRIC-STALE-001",
                        record_kind="EXPERIMENT_METRIC",
                        entity_id="METRIC-STALE-001",
                        hypothesis_version_id=HYPOTHESIS_ID,
                        payload={
                            "experiment_id": EXPERIMENT_ID,
                            "metric_id": "METRIC-STALE-001",
                            "observed_n": 99,
                        },
                        transaction_id="RESEARCH-TXN-STALE-001",
                    )
                ],
                transaction_id="RESEARCH-TXN-STALE-001",
            )
            app._research_reader = None
            before = _inventory(data_root)
            with self.assertRaises(ApplicationError) as raised:
                app.record_research_decision(
                    {
                        **command,
                        "decision_kind": "PAUSE",
                        "expected_evidence_snapshot_sha256": snapshot,
                    }
                )
            self.assertEqual(raised.exception.code, "STALE_EVIDENCE_SNAPSHOT")
            self.assertEqual(_inventory(data_root), before)

            writer = ResearchStore(data_root, create_if_missing=False)
            fresh = app.research_detail(LOCATOR)
            busy_command = {
                **command,
                "decision_kind": "REVISE",
                "expected_evidence_snapshot_sha256": fresh["dossier"][
                    "evidence_snapshot_sha256"
                ],
            }
            with writer.writer_lease():
                with self.assertRaises(ApplicationError) as busy:
                    app.record_research_decision(busy_command)
            self.assertEqual(busy.exception.code, "WRITER_BUSY")
            readable = app.research_detail(LOCATOR)
            self.assertEqual(readable["header"]["entity_id"], EXPERIMENT_ID)

    def test_promote_guard_and_strategy_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            store = ResearchStore(data_root)
            store.append(
                [
                    _event(
                        record_id="HYP-MIN-001",
                        record_kind="HYPOTHESIS_VERSION",
                        entity_id=HYPOTHESIS_ID,
                        hypothesis_version_id=HYPOTHESIS_ID,
                        payload={
                            "hypothesis_version_id": HYPOTHESIS_ID,
                            "claim": "min",
                            "mechanism": "min",
                            "falsifier": "min",
                        },
                        transaction_id="RESEARCH-TXN-MIN-001",
                    )
                ],
                transaction_id="RESEARCH-TXN-MIN-001",
            )
            app = FactoryApplication(
                root=ROOT,
                spec_relative="configs/experiment_specs/ordinary_price_path_buy_pressure_v1.yaml",
                research_data_root=data_root,
            )
            incomplete = app.research_detail(LOCATOR)
            self.assertFalse(incomplete["dossier"]["science_guard"]["allowed"])
            with self.assertRaises(ApplicationError) as blocked:
                app.record_research_decision(
                    {
                        "entity_id": EXPERIMENT_ID,
                        "truth_plane": "GIT",
                        "native_kind": "EXPERIMENT_SPEC",
                        "decision_kind": "PROMOTE",
                        "expected_evidence_snapshot_sha256": incomplete["dossier"][
                            "evidence_snapshot_sha256"
                        ],
                        "promote_scientific_only": "1",
                    }
                )
            self.assertEqual(blocked.exception.code, "PROMOTE_BLOCKED")

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            store = ResearchStore(data_root)
            store.append([_eligible_run()], transaction_id="RESEARCH-TXN-ELIGIBLE-001")
            app = FactoryApplication(
                root=ROOT,
                spec_relative="configs/experiment_specs/ordinary_price_path_buy_pressure_v1.yaml",
                research_data_root=data_root,
            )
            eligible = app.research_detail(LOCATOR)
            self.assertTrue(eligible["dossier"]["science_guard"]["allowed"])
            strategies = ROOT / "registries" / "strategies.yaml"
            before_strategies = strategies.read_bytes()
            recorded = app.record_research_decision(
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
            self.assertEqual(recorded["decision_result"]["status"], "DECISION_RECORDED")
            self.assertFalse(recorded["decision_result"]["creates_strategy_version"])
            self.assertEqual(recorded["dossier"]["planes"]["decision"], "PROMOTE")
            self.assertEqual(strategies.read_bytes(), before_strategies)
            self.assertIn("REJECT", OWNER_DECISION_KINDS)

    def test_html_decision_and_promote_guard_copy(self) -> None:
        app = FactoryApplication(
            root=ROOT,
            spec_relative="configs/experiment_specs/ordinary_price_path_buy_pressure_v1.yaml",
        )
        href = (
            f"/research?entity_id={EXPERIMENT_ID}"
            "&truth_plane=GIT&native_kind=EXPERIMENT_SPEC"
        )
        _, body = _http(app, "GET", href)
        self.assertIn("PROMOTE закрыт", body)
        self.assertIn("StrategyVersion", body)
        self.assertIn("CONTROL_SURFACE", body)
        self.assertIn("Вопрос", body)

    def test_semantic_anti_hijack(self) -> None:
        projection = load_semantic_projection(ROOT)
        assets, bindings, _queries = load_semantic_catalog_views(ROOT)
        cases = (
            ("show experiment evidence", "SEM-OWNER-LIFECYCLE"),
            ("покажи evidence эксперимента", "SEM-OWNER-LIFECYCLE"),
            ("чего не хватает для решения", "SEM-OWNER-LIFECYCLE"),
            ("has this mechanism been tested before?", "SEM-PRIOR-WORK"),
            ("can this experiment be run?", "SEM-EXPERIMENT-CAPABILITIES"),
            ("generate a hypothesis", "SEM-HYPOTHESIS-FORGE"),
        )
        for query, route in cases:
            hits = search_semantic_routes(
                projection, query, assets=assets, bindings=bindings, limit=5
            )
            self.assertEqual(hits[0]["semantic_route_id"], route, query)
        vps = search_semantic_routes(
            projection,
            "is this running on VPS?",
            assets=assets,
            bindings=bindings,
            limit=5,
        )
        self.assertIn(
            vps[0]["semantic_route_id"],
            {"SEM-REMOTE-OPS-RECOVERY", "SEM-LIVE-COLLECTION"},
        )
        self.assertNotEqual(vps[0]["semantic_route_id"], "SEM-OWNER-LIFECYCLE")


if __name__ == "__main__":
    unittest.main()
