from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.hypothesis_fast_lane import execute_submit  # noqa: E402
from solana_alpha_lab.factory.hfic_session import (  # noqa: E402
    apply_classification,
    finalize_session,
    freeze_draft,
)
from solana_alpha_lab.factory.lane_classifier import Lane, classify_lane  # noqa: E402
from solana_alpha_lab.factory.observation_panel_publisher import (  # noqa: E402
    build_panel_snapshot,
    persist_observation_schedule,
    persist_panel_snapshot_binding,
)
from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    load_observation_schedule,
)
from solana_alpha_lab.factory.research_store import (  # noqa: E402
    RecordKind,
    ResearchEvent,
    ResearchStore,
)
from solana_alpha_lab.factory.commissioning_fixture import (  # noqa: E402
    publish_commissioning_dataset,
)
from tests.test_fast_lane_classifier import (  # noqa: E402
    AS_OF as V11_AS_OF,
    HYPOTHESIS_DEFINITION_SHA256,
    experiment_spec as v11_experiment_spec,
    submission as v11_submission,
)
from tests.test_fast_lane_runner import offline_v1_1_spec  # noqa: E402
from tests.test_hfic_session import (  # noqa: E402
    _critic_result,
    _preflight_receipt,
    valid_draft,
)


SCHEMA_PATH = ROOT / "catalog/schemas/experiment_spec_v1_2.schema.json"
SCHEMA_SHA = hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest()
GIT_SHA = "c" * 40
NOW = datetime(2026, 9, 1, tzinfo=UTC)
AS_OF_START = datetime(2026, 9, 1, tzinfo=UTC)
AS_OF_NOON = datetime(2026, 9, 1, 12, tzinfo=UTC)
OBS_CAPABILITY = "CAP-OBSERVATION-SCHEDULE-COMPILE-BIND-001"


def _observation_request(name: str, *, mode: str, role: str) -> dict:
    raw = yaml.safe_load(
        (ROOT / "tests/fixtures/observation_schedule" / name).read_text(encoding="utf-8")
    )
    request = {
        key: value
        for key, value in raw.items()
        if key not in {"schema", "schema_version", "schedule_sha256"}
    }
    request["collection_mode"] = mode
    request["requested_evidence_role"] = role
    return request


def v1_2_spec(
    *,
    fixture: str = "common_panel.yaml",
    mode: str = "SCHEDULE_ONLY",
    role: str = "PROSPECTIVE_OOS",
    as_of: str = "2026-09-01T00:00:00Z",
    availability_cutoff: str = "2026-09-01T00:00:00Z",
    primitive_id: str | None = None,
    experiment_id: str = "EXP-OBS-FAST-LANE-ROUTING-001",
) -> dict[str, object]:
    request = _observation_request(fixture, mode=mode, role=role)
    if primitive_id is not None:
        request["source_poll"] = dict(request["source_poll"])
        request["source_poll"]["primitive_id"] = primitive_id
    return {
        "schema": "smial.experiment-spec",
        "schema_version": "1.2",
        "experiment_id": experiment_id,
        "hypothesis_version": "HYP-VERSION-OBS-FAST-LANE-V1",
        "question": "Does a valid in-envelope observation request stay on Fast Lane?",
        "estimand": "Typed observation terminal agreement",
        "population": "Registered observation schedule fixture",
        "data_requirements": [
            {
                "requirement_id": "EXPERIMENT_SPEC_V12",
                "kind": "CATALOG_ASSET",
                "path": "catalog/schemas/experiment_spec_v1_2.schema.json",
                "sha256": SCHEMA_SHA,
            }
        ],
        "capabilities": [OBS_CAPABILITY],
        "falsifier": "Valid envelope request becomes infra or mismatch",
        "method": "observe_schedule_compile",
        "parameters": {},
        "evidence_budget": {"provider_api_rpc_wss_calls": 0},
        "holdout_policy": "No holdout is opened by classification",
        "terminal_outcomes": ["SUPPORTED", "FALSIFIED", "INCONCLUSIVE"],
        "data_bindings": [
            {
                "binding_id": "BINDING-EXPERIMENT-SPEC-V12-001",
                "source_kind": "CATALOG_ASSET",
                "stable_id": "SCHEMA-EXPERIMENT-SPEC-V1-2-001",
                "expected_content_sha256_or_dataset_fingerprint": SCHEMA_SHA,
            }
        ],
        "query_recipe_ids": [],
        "capability_id": OBS_CAPABILITY,
        "parameter_schema_asset_id": "SCHEMA-EXPERIMENT-SPEC-V1-2-001",
        "as_of": as_of,
        "availability_cutoff": availability_cutoff,
        "what_changed": ["INITIAL_OBSERVATION_FAST_LANE_FIXTURE"],
        "observation_request": request,
    }


def packet_for(spec: dict[str, object], definition_sha256: str = HYPOTHESIS_DEFINITION_SHA256) -> dict:
    return {
        "experiment_spec": spec,
        "hypothesis_definition_sha256": definition_sha256,
    }


def write_packet(directory: Path, packet: dict) -> Path:
    path = directory / "packet.yaml"
    path.write_text(yaml.safe_dump(packet, sort_keys=False), encoding="utf-8")
    return path


def persist_active_schedule(data_root: Path, schedule: dict[str, object]) -> None:
    persist_observation_schedule(
        data_root=data_root,
        schedule=schedule,
        now=NOW,
        producer_git_sha=GIT_SHA,
        activation_id="ACT-OBS-ROUTING-001",
    )
    digest = str(schedule["schedule_sha256"])
    payload = {
        "activation_id": "ACT-OBS-ROUTING-001",
        "schedule_sha256": digest,
        "state": "ACTIVE",
        "transition_sequence": 1,
    }
    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    event = ResearchEvent(
        record_id=f"OBS-STATE-{digest[:16].upper()}",
        record_kind=RecordKind.OBSERVATION_SCHEDULE_STATE,
        entity_id=digest,
        hypothesis_version_id=None,
        run_id="ACT-OBS-ROUTING-001",
        transaction_id=f"RESEARCH-TXN-OBS-STATE-{digest[:12].upper()}",
        effective_at=NOW,
        first_reliable_available_at=NOW,
        supersedes_record_id=None,
        payload_json=payload_json,
        payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        schema_version="1.0",
        producer_capability_id=OBS_CAPABILITY,
        producer_git_sha=GIT_SHA,
        created_at=NOW,
    )
    ResearchStore(data_root).append(
        [event],
        transaction_id=event.transaction_id,
    )


def persist_covering_snapshot(data_root: Path, schedule: dict[str, object]) -> dict[str, str]:
    persist_observation_schedule(
        data_root=data_root,
        schedule=schedule,
        now=NOW,
        producer_git_sha=GIT_SHA,
    )
    snapshot = build_panel_snapshot(
        schedule_sha256=str(schedule["schedule_sha256"]),
        availability_cutoff=NOW,
        dataset_manifest_ids=["dataset-" + "b" * 64],
        dataset_fingerprints=["c" * 64],
    )
    persist_panel_snapshot_binding(
        data_root=data_root,
        schedule=schedule,
        snapshot=snapshot,
        now=NOW,
        producer_git_sha=GIT_SHA,
        evidence_role="EXPLORATORY_REUSE",
        hypothesis_version_id="HYP-VERSION-OBS-FAST-LANE-V1",
        run_id="RUN-OBS-COVER-001",
    )
    return {
        "schedule_sha256": str(schedule["schedule_sha256"]),
        "snapshot_sha256": str(snapshot["snapshot_sha256"]),
    }


def classify(packet: dict, data_root: Path, as_of: datetime) -> object:
    return classify_lane(packet, root=ROOT, data_root=data_root, as_of=as_of)


def forge_classify(packet: dict, data_root: Path) -> dict[str, object]:
    store = ResearchStore(data_root)
    frozen = freeze_draft(valid_draft(), preflight_receipt=_preflight_receipt())
    finalize_session(
        frozen,
        _critic_result(frozen, "PASS_TO_CLASSIFICATION"),
        store=store,
        repo_root=ROOT,
        data_root=data_root,
    )
    live_packet = dict(packet)
    live_packet["hypothesis_definition_sha256"] = frozen["selected_definition_sha256"]
    done = apply_classification(
        frozen,
        live_packet,
        store=store,
        repo_root=ROOT,
        data_root=data_root,
    )
    receipt: dict[str, object] | None = None
    if isinstance(done.get("classifier_receipt"), dict):
        receipt = done["classifier_receipt"]
    if receipt is None:
        for record in store.iter_committed_records():
            if record.record_kind != RecordKind.RESEARCH_ARTIFACT.value:
                continue
            payload = json.loads(record.payload_json)
            if payload.get("artifact_kind") != "CLASSIFIER_RECEIPT":
                continue
            raw = payload.get("payload_canonical")
            if isinstance(raw, str):
                loaded = json.loads(raw)
                if isinstance(loaded, dict):
                    receipt = loaded
                    break
    if receipt is None:
        receipt = {
            "lane_classifier_terminal": done.get("lane_classifier_terminal"),
        }
    return {
        "hfic_terminal": done.get("critic_terminal"),
        "classifier_terminal": receipt.get("lane_classifier_terminal"),
        "next_action": receipt.get("next_action"),
        "lane": receipt.get("lane"),
        "session_state": done.get("session_state"),
        "capability_gap": any(
            record.record_kind == RecordKind.CAPABILITY_GAP.value
            for record in store.iter_committed_records()
        ),
        "error": None,
    }


class ObservationFastLaneRoutingClosureTests(unittest.TestCase):
    def test_t1_forge_panel_reuse(self) -> None:
        covering = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/common_panel.yaml"
        )
        spec = v1_2_spec(
            mode="REUSE_OR_SCHEDULE",
            role="EXPLORATORY_REUSE",
            as_of="2026-09-01T12:00:00Z",
            availability_cutoff="2026-09-01T12:00:00Z",
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            persist_covering_snapshot(data_root, covering)
            packet = packet_for(spec)
            decision = classify(packet, data_root, AS_OF_NOON)
            self.assertEqual(decision.lane, Lane.FAST_LANE)
            self.assertEqual(decision.terminal, "PANEL_REUSE_READY")
            forged = forge_classify(packet, data_root)
            self.assertEqual(forged["hfic_terminal"], "PASS_FAST_LANE_READY")
            self.assertEqual(forged["classifier_terminal"], "PANEL_REUSE_READY")
            self.assertEqual(forged["error"], None)
            self.assertNotEqual(forged["hfic_terminal"], "CLASSIFIER_TERMINAL_MISMATCH")

    def test_t2_forge_activation_required(self) -> None:
        spec = v1_2_spec()
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            packet = packet_for(spec)
            decision = classify(packet, data_root, AS_OF_START)
            self.assertEqual(decision.lane, Lane.FAST_LANE)
            self.assertEqual(decision.terminal, "SCHEDULE_ACTIVATION_REQUIRED")
            forged = forge_classify(packet, data_root)
            self.assertEqual(forged["hfic_terminal"], "OWNER_DECISION_REQUIRED")
            self.assertEqual(forged["classifier_terminal"], "SCHEDULE_ACTIVATION_REQUIRED")
            self.assertEqual(forged["lane"], "FAST_LANE")
            self.assertFalse(forged["capability_gap"])
            self.assertNotEqual(forged["hfic_terminal"], "PASS_CHANGE_LANE_REQUIRED")

    def test_t3_forge_active_attach(self) -> None:
        covering = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/common_panel.yaml"
        )
        spec = v1_2_spec(
            fixture="x300_y900.yaml",
            mode="SCHEDULE_ONLY",
            role="PROSPECTIVE_OOS",
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            persist_active_schedule(data_root, covering)
            packet = packet_for(spec)
            decision = classify(packet, data_root, AS_OF_START)
            self.assertEqual(decision.terminal, "ATTACHED_TO_ACTIVE_SCHEDULE")
            self.assertEqual(decision.next_action, "ATTACH_HYPOTHESIS_BINDING")
            forged = forge_classify(packet, data_root)
            self.assertEqual(forged["hfic_terminal"], "PASS_FAST_LANE_READY")
            self.assertEqual(forged["classifier_terminal"], "ATTACHED_TO_ACTIVE_SCHEDULE")
            self.assertEqual(forged["next_action"], "ATTACH_HYPOTHESIS_BINDING")

    def test_t4_forge_successor(self) -> None:
        predecessor = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        spec = v1_2_spec(
            fixture="successor_y259200.yaml",
            mode="SCHEDULE_ONLY",
            role="PROSPECTIVE_OOS",
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            persist_active_schedule(data_root, predecessor)
            packet = packet_for(spec)
            decision = classify(packet, data_root, AS_OF_START)
            self.assertEqual(decision.terminal, "NEW_VERSION_FOR_FUTURE_COHORTS_REQUIRED")
            forged = forge_classify(packet, data_root)
            self.assertEqual(forged["hfic_terminal"], "OWNER_DECISION_REQUIRED")
            self.assertEqual(
                forged["classifier_terminal"],
                "NEW_VERSION_FOR_FUTURE_COHORTS_REQUIRED",
            )
            self.assertEqual(forged["lane"], "FAST_LANE")
            self.assertFalse(forged["capability_gap"])
            self.assertNotEqual(forged["hfic_terminal"], "PASS_CHANGE_LANE_REQUIRED")

    def test_t5_public_submit_activation_required(self) -> None:
        spec = v1_2_spec()
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            packet = packet_for(spec)
            packet_path = write_packet(data_root, packet)
            result = execute_submit(
                ROOT,
                data_root,
                packet_path,
                AS_OF_START,
                run=True,
                authority_phrase=None,
            )
            self.assertNotEqual(result["status"], "FAILED_INFRA")
            self.assertEqual(result["status"], "BLOCKED_AUTHORITY")
            self.assertEqual(result["lane"], "FAST_LANE")
            self.assertEqual(result["observation_terminal"], "SCHEDULE_ACTIVATION_REQUIRED")
            self.assertEqual(result["next_action"], "AUTHORIZE_COMPILED_SCHEDULE")
            self.assertIsNone(result["run_id_or_null"])
            self.assertEqual(result["provider_calls_actual"], 0)
            self.assertEqual(result["git_mutation_count"], 0)
            self.assertEqual(result["scientific_terminal"], "INVALID")
            self.assertIsNone(ResearchStore(data_root).find_completed_run(result["run_key_sha256"]))

    def test_t6_no_false_replay_after_activation_required(self) -> None:
        spec = v1_2_spec()
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            packet = packet_for(spec)
            packet_path = write_packet(data_root, packet)
            first = execute_submit(
                ROOT,
                data_root,
                packet_path,
                AS_OF_START,
                run=True,
                authority_phrase=None,
            )
            self.assertEqual(first["status"], "BLOCKED_AUTHORITY")
            second = classify(packet, data_root, AS_OF_START)
            self.assertNotEqual(second.terminal, "REPLAY_AVAILABLE")
            self.assertEqual(second.terminal, "SCHEDULE_ACTIVATION_REQUIRED")

    def test_t7_panel_reuse_real_passport(self) -> None:
        covering = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/common_panel.yaml"
        )
        spec = v1_2_spec(
            mode="REUSE_OR_SCHEDULE",
            role="EXPLORATORY_REUSE",
            as_of="2026-09-01T12:00:00Z",
            availability_cutoff="2026-09-01T12:00:00Z",
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            identities = persist_covering_snapshot(data_root, covering)
            packet = packet_for(spec)
            packet_path = write_packet(data_root, packet)
            result = execute_submit(
                ROOT,
                data_root,
                packet_path,
                AS_OF_NOON,
                run=True,
                authority_phrase=None,
            )
            self.assertEqual(result["status"], "COMPLETE")
            self.assertEqual(result["observation_terminal"], "PANEL_REUSE_READY")
            self.assertEqual(
                result["observation_schedule_sha256"],
                identities["schedule_sha256"],
            )
            self.assertEqual(
                result["observation_panel_snapshot_sha256"],
                identities["snapshot_sha256"],
            )
            self.assertEqual(result["provider_calls_actual"], 0)
            self.assertEqual(result["git_mutation_count"], 0)
            self.assertIsNotNone(result["run_id_or_null"])
            passport = ResearchStore(data_root).find_completed_run(result["run_key_sha256"])
            self.assertIsNotNone(passport)
            assert passport is not None
            self.assertEqual(
                passport.observation_schedule_sha256,
                identities["schedule_sha256"],
            )
            self.assertEqual(
                passport.observation_panel_snapshot_sha256,
                identities["snapshot_sha256"],
            )
            self.assertEqual(len(passport.runner_git_sha), 40)
            self.assertNotEqual(passport.runner_git_sha, GIT_SHA)

    def test_t8_replay_only_after_complete_binding(self) -> None:
        covering = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/common_panel.yaml"
        )
        spec = v1_2_spec(
            mode="REUSE_OR_SCHEDULE",
            role="EXPLORATORY_REUSE",
            as_of="2026-09-01T12:00:00Z",
            availability_cutoff="2026-09-01T12:00:00Z",
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            persist_covering_snapshot(data_root, covering)
            packet = packet_for(spec)
            packet_path = write_packet(data_root, packet)
            first = execute_submit(
                ROOT,
                data_root,
                packet_path,
                AS_OF_NOON,
                run=True,
                authority_phrase=None,
            )
            self.assertEqual(first["status"], "COMPLETE")
            second = classify(packet, data_root, AS_OF_NOON)
            self.assertEqual(second.terminal, "REPLAY_AVAILABLE")
            self.assertEqual(second.prior_run_id, first["run_id_or_null"])

    def test_t9_change_lane_still_change_lane(self) -> None:
        spec = v1_2_spec(primitive_id="PRIM-UNKNOWN-ROUTE-001")
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            packet = packet_for(spec)
            decision = classify(packet, data_root, AS_OF_START)
            self.assertEqual(decision.lane, Lane.CHANGE_LANE)
            packet_path = write_packet(data_root, packet)
            result = execute_submit(
                ROOT,
                data_root,
                packet_path,
                AS_OF_START,
                run=True,
                authority_phrase=None,
            )
            self.assertEqual(result["lane"], "CHANGE_LANE")
            self.assertEqual(result["provider_calls_actual"], 0)
            self.assertEqual(result["git_mutation_count"], 0)
            self.assertIsNone(result["run_id_or_null"])

    def test_v1_1_fast_lane_terminals_remain_compatible(self) -> None:
        spec = v11_experiment_spec()
        packet = v11_submission()
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            decision = classify(packet, data_root, V11_AS_OF)
            self.assertEqual(decision.lane, Lane.FAST_LANE)
            self.assertEqual(decision.terminal, "FAST_LANE_READY")
            publish_commissioning_dataset(data_root)
            offline = offline_v1_1_spec()
            offline_packet = packet_for(offline)
            packet_path = write_packet(data_root, offline_packet)
            offline_decision = classify(offline_packet, data_root, V11_AS_OF)
            self.assertEqual(offline_decision.terminal, "FAST_LANE_READY")
            result = execute_submit(
                ROOT,
                data_root,
                packet_path,
                V11_AS_OF,
                run=True,
                authority_phrase=None,
            )
            self.assertEqual(result["status"], "COMPLETE")
            self.assertEqual(result["lane"], "FAST_LANE")
            self.assertEqual(result["provider_calls_actual"], 0)
            self.assertEqual(result["git_mutation_count"], 0)
            self.assertIsNotNone(result["run_id_or_null"])
            self.assertNotIn("observation_terminal", result)

    def test_attached_submit_does_not_create_run(self) -> None:
        covering = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/common_panel.yaml"
        )
        spec = v1_2_spec(
            fixture="x300_y900.yaml",
            mode="SCHEDULE_ONLY",
            role="PROSPECTIVE_OOS",
        )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            persist_active_schedule(data_root, covering)
            packet = packet_for(spec)
            packet_path = write_packet(data_root, packet)
            result = execute_submit(
                ROOT,
                data_root,
                packet_path,
                AS_OF_START,
                run=True,
                authority_phrase=None,
            )
            self.assertEqual(result["status"], "BLOCKED_DATA")
            self.assertEqual(result["observation_terminal"], "ATTACHED_TO_ACTIVE_SCHEDULE")
            self.assertEqual(result["next_action"], "ATTACH_HYPOTHESIS_BINDING")
            self.assertIsNone(result["run_id_or_null"])
            self.assertNotEqual(result["status"], "FAILED_INFRA")
            self.assertIsNone(ResearchStore(data_root).find_completed_run(result["run_key_sha256"]))


if __name__ == "__main__":
    unittest.main()
