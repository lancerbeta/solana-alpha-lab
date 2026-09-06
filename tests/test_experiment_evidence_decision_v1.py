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
            "observed_n": 24,
            "robustness": "HOLD_SPLIT",
            "outcome": "INCONCLUSIVE",
        },
        transaction_id="RESEARCH-TXN-ELIGIBLE-001",
    )


def _eligible_binding(**overrides: object) -> ResearchEvent:
    record_id = str(overrides.pop("record_id", "EVIDENCE-BINDING-ELIGIBLE-001"))
    txn = str(overrides.pop("transaction_id", "RESEARCH-TXN-BINDING-001"))
    return _event(
        record_id=record_id,
        record_kind="EVIDENCE_BINDING",
        entity_id=record_id,
        hypothesis_version_id=HYPOTHESIS_ID,
        payload=_scientific_payload(**overrides),
        transaction_id=txn,
    )


def _eligible_records() -> tuple[ResearchEvent, ResearchEvent]:
    return _eligible_run(), _eligible_binding(
        transaction_id="RESEARCH-TXN-ELIGIBLE-001"
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
        self.assertEqual(statuses["EVIDENCE_CLASS"], "MISSING")
        self.assertEqual(statuses["PIT_AVAILABILITY"], "MISSING")
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
        related_decision = _event(
            record_id="DECISION-EVENT-PRIOR-HYP-001",
            record_kind="DECISION_EVENT",
            entity_id="DECISION-EVENT-PRIOR-HYP-001",
            hypothesis_version_id=HYPOTHESIS_ID,
            payload={
                "decision_kind": "PROMOTE",
                "target_entity_id": "EXP-OTHER-001",
                "target_native_kind": "EXPERIMENT_SPEC",
            },
            transaction_id="RESEARCH-TXN-PRIOR-DEC-001",
        )
        polluted = compose_experiment_dossier(
            projection,
            LOCATOR,
            root=ROOT,
            records=(run, prior, related_decision),
            records_status="AVAILABLE",
        )
        self.assertEqual(polluted["planes"]["decision"], "NO_DECISION")
        history_ids = {item.get("record_id") for item in polluted["decision_history"]}
        self.assertNotIn("DECISION-EVENT-PRIOR-HYP-001", history_ids)
        related_ids_after = {item["record_id"] for item in polluted["related_prior_memory"]}
        self.assertIn("DECISION-EVENT-PRIOR-HYP-001", related_ids_after)

    def test_run_completed_does_not_satisfy_pit(self) -> None:
        projection = build_lifecycle_projection(ROOT, projected_at="2026-09-06T00:00:00Z")
        dossier = compose_experiment_dossier(
            projection,
            LOCATOR,
            root=ROOT,
            records=(_eligible_run(),),
            records_status="AVAILABLE",
        )
        statuses = {item["code"]: item["status"] for item in dossier["obligations"]}
        self.assertEqual(dossier["planes"]["execution"], "COMPLETED")
        self.assertEqual(statuses["PIT_AVAILABILITY"], "MISSING")
        self.assertEqual(statuses["EVIDENCE_CLASS"], "MISSING")
        self.assertNotEqual(statuses["PIT_AVAILABILITY"], "PRESENT")
        self.assertNotEqual(statuses["EVIDENCE_CLASS"], "PRESENT")
        self.assertNotEqual(statuses["EVIDENCE_CLASS"], "NOT_APPLICABLE")
        self.assertFalse(dossier["science_guard"]["allowed"])
        self.assertIn("PIT_AVAILABILITY", dossier["science_guard"]["blocked_codes"])

    def test_conflict_and_holdout_empty_list_stay_distinct(self) -> None:
        binding_a = _eligible_binding()
        binding_b = _eligible_binding(
            record_id="EVIDENCE-BINDING-ELIGIBLE-002",
            transaction_id="RESEARCH-TXN-BINDING-002",
            observed_n=7,
        )
        projection = build_lifecycle_projection(ROOT, projected_at="2026-09-06T00:00:00Z")
        dossier = compose_experiment_dossier(
            projection,
            LOCATOR,
            root=ROOT,
            records=(_eligible_run(), binding_a, binding_b),
            records_status="AVAILABLE",
        )
        statuses = {item["code"]: item["status"] for item in dossier["obligations"]}
        self.assertEqual(statuses["POPULATION_N"], "CONFLICT")
        self.assertEqual(statuses["HOLDOUT"], "NOT_APPLICABLE")
        complementary = _eligible_binding(
            record_id="EVIDENCE-BINDING-PIT-CLOCKS-001",
            transaction_id="RESEARCH-TXN-PIT-CLOCKS-001",
        )
        clocks = compose_experiment_dossier(
            projection,
            LOCATOR,
            root=ROOT,
            records=(_eligible_run(), complementary),
            records_status="AVAILABLE",
        )
        clock_status = {item["code"]: item["status"] for item in clocks["obligations"]}
        self.assertEqual(clock_status["PIT_AVAILABILITY"], "PRESENT")
        pit_values = next(
            item["values"] for item in clocks["obligations"] if item["code"] == "PIT_AVAILABILITY"
        )
        self.assertNotEqual(
            pit_values.get("availability_cutoff"),
            pit_values.get("first_reliable_available_at"),
        )
        na = _eligible_binding(
            record_id="EVIDENCE-BINDING-HOLDOUT-NA-001",
            transaction_id="RESEARCH-TXN-HOLDOUT-NA-001",
            holdout_applicable=False,
            holdout_consumption_ids=[],
        )
        consumed = _eligible_binding(
            record_id="EVIDENCE-BINDING-HOLDOUT-USED-001",
            transaction_id="RESEARCH-TXN-HOLDOUT-USED-001",
            holdout_applicable=True,
            holdout_consumption_ids=["HOLDOUT-001"],
        )
        holdout_conflict = compose_experiment_dossier(
            projection,
            LOCATOR,
            root=ROOT,
            records=(na, consumed),
            records_status="AVAILABLE",
        )
        holdout_status = {
            item["code"]: item["status"] for item in holdout_conflict["obligations"]
        }
        self.assertEqual(holdout_status["HOLDOUT"], "CONFLICT")
        foreign_metric = _event(
            record_id="METRIC-FOREIGN-RUN-001",
            record_kind="EXPERIMENT_METRIC",
            entity_id="METRIC-FOREIGN-RUN-001",
            run_id="RUN-FOREIGN-001",
            hypothesis_version_id=HYPOTHESIS_ID,
            payload={"run_id": "RUN-FOREIGN-001", "observed_n": 99, "evidence_class": "DIAGNOSTIC"},
            transaction_id="RESEARCH-TXN-FOREIGN-METRIC-001",
        )
        binding_with_foreign_run = _eligible_binding(
            record_id="EVIDENCE-BINDING-FOREIGN-RUN-001",
            transaction_id="RESEARCH-TXN-FOREIGN-RUN-001",
            run_id="RUN-FOREIGN-001",
        )
        harvested = compose_experiment_dossier(
            projection,
            LOCATOR,
            root=ROOT,
            records=(binding_with_foreign_run, foreign_metric),
            records_status="AVAILABLE",
        )
        harvested_ids = {item.get("record_id") for item in harvested["direct_evidence"]}
        self.assertNotIn("METRIC-FOREIGN-RUN-001", harvested_ids)
        self.assertNotEqual(statuses["POPULATION_N"], statuses.get("MISSINGNESS"))
        self.assertFalse(dossier["science_guard"]["allowed"])
        self.assertIn("POPULATION_N", dossier["science_guard"]["blocked_codes"])
        sentinel = _eligible_binding(
            record_id="EVIDENCE-BINDING-SENTINEL-001",
            transaction_id="RESEARCH-TXN-SENTINEL-001",
            robustness="NOT_TESTED",
        )
        sentinel_dossier = compose_experiment_dossier(
            projection,
            LOCATOR,
            root=ROOT,
            records=(sentinel,),
            records_status="AVAILABLE",
        )
        sentinel_status = {
            item["code"]: item["status"] for item in sentinel_dossier["obligations"]
        }
        self.assertEqual(sentinel_status["ROBUSTNESS"], "UNKNOWN")
        self.assertNotEqual(sentinel_status["ROBUSTNESS"], "MISSING")
        self.assertFalse(sentinel_dossier["science_guard"]["allowed"])

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
        self.assertNotIn("NOT_APPLICABLE", detail)
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
                "next_condition": "Вернуться после holdout.",
            }
            recorded = app.record_research_decision(command)
            self.assertEqual(recorded["decision_result"]["status"], "DECISION_RECORDED")
            self.assertEqual(recorded["dossier"]["planes"]["decision"], "REJECT")
            stored = [
                item
                for item in recorded["dossier"]["decision_history"]
                if item.get("decision_kind") == "REJECT"
            ]
            self.assertEqual(stored[0].get("rationale"), command["rationale"])
            self.assertEqual(stored[0].get("next_condition"), command["next_condition"])
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
            store.append(
                list(_eligible_records()),
                transaction_id="RESEARCH-TXN-ELIGIBLE-001",
            )
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
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            ResearchStore(data_root)
            app = FactoryApplication(
                root=ROOT,
                spec_relative="configs/experiment_specs/ordinary_price_path_buy_pressure_v1.yaml",
                research_data_root=data_root,
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
            self.assertIn('disabled', body)

    def test_http_records_reject_and_surfaces_done(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            store = ResearchStore(data_root)
            store.append([_eligible_run()], transaction_id="RESEARCH-TXN-ELIGIBLE-001")
            app = FactoryApplication(
                root=ROOT,
                spec_relative="configs/experiment_specs/ordinary_price_path_buy_pressure_v1.yaml",
                research_data_root=data_root,
            )
            href = (
                f"/research?entity_id={EXPERIMENT_ID}"
                "&truth_plane=GIT&native_kind=EXPERIMENT_SPEC"
            )
            _, body = _http(app, "GET", href)
            marker = 'name="expected_evidence_snapshot_sha256" value="'
            start = body.index(marker) + len(marker)
            snapshot = body[start : body.index('"', start)]
            posted = urlencode(
                {
                    "command": "RESEARCH_DECISION",
                    "entity_id": EXPERIMENT_ID,
                    "truth_plane": "GIT",
                    "native_kind": "EXPERIMENT_SPEC",
                    "decision_kind": "REJECT",
                    "expected_evidence_snapshot_sha256": snapshot,
                    "rationale": "Отклоняю по текущему снимку.",
                }
            )
            status, recorded = _http(app, "POST", "/research", posted)
            self.assertEqual(status, 200)
            self.assertIn("Решение записано", recorded)
            self.assertIn("REJECT", recorded)
            self.assertIn("DIRECT", recorded)

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
