from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task21_owner_pulse import (
    CORRECTED_NEXT_ATOM,
    EXPECTED_GATE_ID,
    EXPECTED_NEXT_ATOM,
    Task21OwnerPulseError,
    build_owner_pulse,
    canonical_json_bytes,
    evaluate_time_gate,
    render_owner_pulse_text,
)


CONFIG_PATH = ROOT / "configs" / "task21_owner_pulse_read_model_v1.yaml"
MARKER_PATH = ROOT / "control" / "active_time_gates.json"
AGENTS_PATH = ROOT / "AGENTS.md"
CORE_CATALOG_PATH = ROOT / "catalog" / "assets" / "core.yaml"
PRODUCTION_MEMORY_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task17"
    / "first_bounded_hypothesis_cycle_v1.json"
)
SOURCE_RECEIPT_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task21"
    / "real_nomination_source_offline_acceptance_v1.json"
)
ACCEPTANCE_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task21"
    / "owner_pulse_read_model_acceptance_v1.json"
)
WAITING_AT = datetime(2026, 7, 31, 12, tzinfo=timezone.utc)
DUE_AT = datetime(2026, 8, 6, 16, 28, 59, 84_000, tzinfo=timezone.utc)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestTask21OwnerPulse(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        cls.marker = json.loads(MARKER_PATH.read_text(encoding="utf-8"))

    def test_marker_is_exact_and_source_receipt_is_pinned(self) -> None:
        self.assertEqual(self.marker["schema_version"], "1.0")
        self.assertEqual(len(self.marker["gates"]), 1)
        gate = self.marker["gates"][0]
        self.assertEqual(gate["gate_id"], EXPECTED_GATE_ID)
        self.assertEqual(gate["status"], "SUPERSEDED_WITH_EVIDENCE")
        self.assertEqual(gate["required_next_atom"], EXPECTED_NEXT_ATOM)
        self.assertEqual(
            gate["effective_next_boundary"]["required_next_atom"],
            CORRECTED_NEXT_ATOM,
        )
        self.assertFalse(
            gate["effective_next_boundary"]["calendar_wait_required"]
        )
        self.assertEqual(
            _sha256(SOURCE_RECEIPT_PATH),
            gate["source_receipt"]["sha256"],
        )
        self.assertTrue(
            all(
                value == 0
                for value in gate["authority_granted_by_marker"].values()
            )
        )

    def test_waiting_gate_allows_only_non_interfering_parallel_work(self) -> None:
        historical = copy.deepcopy(self.marker["gates"][0])
        historical["status"] = "ACTIVE_WAITING"
        gate = evaluate_time_gate(
            historical,
            as_of=WAITING_AT,
        )
        self.assertEqual(gate["state"], "WAITING_PARALLEL_WORK_ALLOWED")
        self.assertTrue(gate["parallel_work_allowed"])
        self.assertFalse(gate["owner_action_required"])
        self.assertGreater(gate["remaining_seconds"], 0)
        self.assertFalse(gate["external_authority_granted"])

    def test_due_gate_preempts_new_parallel_mutation(self) -> None:
        historical = copy.deepcopy(self.marker["gates"][0])
        historical["status"] = "ACTIVE_WAITING"
        gate = evaluate_time_gate(
            historical,
            as_of=DUE_AT,
        )
        self.assertEqual(gate["state"], "DUE_PREEMPT_PARALLEL_WORK")
        self.assertFalse(gate["parallel_work_allowed"])
        self.assertTrue(gate["owner_action_required"])
        self.assertEqual(gate["remaining_seconds"], 0)
        self.assertEqual(gate["required_next_atom"], EXPECTED_NEXT_ATOM)

    def test_marker_cannot_grant_external_authority(self) -> None:
        changed = copy.deepcopy(self.marker["gates"][0])
        changed["authority_granted_by_marker"]["provider_api_rpc_wss_calls"] = 1
        with self.assertRaisesRegex(
            Task21OwnerPulseError,
            "external_authority_inferred_from_marker",
        ):
            evaluate_time_gate(changed, as_of=WAITING_AT)

    def test_owner_pulse_binds_real_state_without_product_overclaim(self) -> None:
        pulse = build_owner_pulse(
            repository_root=ROOT,
            as_of=WAITING_AT,
            free_disk_bytes=9_000_000_000,
        )
        forward = pulse["task21_forward_state"]
        self.assertEqual(forward["real_nominations"], 3)
        self.assertEqual(forward["real_admissions"], 0)
        self.assertEqual(forward["panels_captured"], 0)
        self.assertFalse(forward["exclusive_p7d_wait_active"])
        self.assertFalse(forward["next_capture_wait_required"])
        self.assertEqual(
            forward["observation_horizon_policy_id"],
            "OBSERVATION-HORIZON-POLICY-T21-001",
        )
        partition = self.marker["gates"][0]["frozen_replay_partition"]
        partition_path = ROOT / partition["path"]
        expected_present = partition_path.is_file()
        expected_identity_ok = (
            expected_present
            and partition_path.stat().st_size == partition["bytes"]
            and _sha256(partition_path) == partition["sha256"]
        )
        self.assertEqual(
            forward["local_replay_partition_present"],
            expected_present,
        )
        self.assertEqual(
            forward["local_replay_partition_identity_ok"],
            expected_identity_ok,
        )
        self.assertEqual(
            forward["local_dataset_bytes"],
            partition["bytes"] if expected_identity_ok else 0,
        )
        if not expected_identity_ok:
            self.assertIn(
                "LOCAL_REPLAY_PARTITION_MISSING_OR_DRIFTED",
                {item["code"] for item in pulse["attention"]},
            )
        self.assertEqual(
            pulse["unavailable_product_truth"],
            {
                "open_positions": "NOT_IMPLEMENTED",
                "realized_pnl": "NOT_IMPLEMENTED",
                "hypothetical_pnl": "NOT_ESTABLISHED",
                "alpha": "NOT_ESTABLISHED",
            },
        )

    def test_runtime_binding_matches_production_memory_and_preserves_legacy(
        self,
    ) -> None:
        pulse = build_owner_pulse(
            repository_root=ROOT,
            as_of=WAITING_AT,
            free_disk_bytes=9_000_000_000,
        )
        factory = pulse["hypothesis_factory_state"]
        self.assertEqual(
            factory["runtime_binding"]["hypothesis_version_id"],
            "HYP-VERSION-EXECUTION-CAPACITY-CURVATURE-V1",
        )
        self.assertEqual(factory["runtime_binding"]["state"], "PAUSED")
        memory = factory["production_hypothesis_memory"]
        self.assertEqual(
            memory["asset_id"],
            "DATA-T17-HYPOTHESIS-RESEARCH-MEMORY-001",
        )
        self.assertEqual(
            memory["hypothesis_version_id"],
            "HYP-VERSION-EXECUTION-CAPACITY-CURVATURE-V1",
        )
        self.assertEqual(memory["current_state_as_of_memory"], "PAUSED")
        self.assertEqual(
            memory["content_sha256"],
            "8c9da2232ab0feec86da130985eaa4e5168539adaa036d0c48f44b00567c06b6",
        )
        self.assertTrue(memory["runtime_binding_consistent"])
        legacy = factory["legacy_lifecycle_registries"]
        self.assertTrue(legacy["intentionally_empty"])
        self.assertEqual(
            legacy["role"],
            "TASK03_SKELETONS_PRESERVED_NO_SYNTHETIC_BACKFILL",
        )
        self.assertEqual(
            legacy["counts"],
            {
                "hypotheses": 0,
                "research_cycles": 0,
                "strategies": 0,
                "bot_instances": 0,
            },
        )
        self.assertEqual(
            factory["truth_note"],
            "TASK21_RUNTIME_BINDING_MATCHES_TASK17_PRODUCTION_MEMORY;"
            "LEGACY_REGISTRIES_ARE_NOT_THE_PRODUCTION_MEMORY",
        )
        self.assertNotIn(
            "OFFICIAL_HYPOTHESIS_REGISTRY_EMPTY",
            {item["code"] for item in pulse["attention"]},
        )

    def test_recovery_and_cost_are_derived_with_fixed_clock(self) -> None:
        pulse = build_owner_pulse(
            repository_root=ROOT,
            as_of=WAITING_AT,
            free_disk_bytes=9_000_000_000,
        )
        recovery = pulse["recovery_and_storage"]
        self.assertEqual(recovery["health_state"], "HEALTHY")
        self.assertEqual(recovery["backup_readback_status"], "EXACT_MATCH")
        self.assertEqual(recovery["free_disk_bytes"], 9_000_000_000)
        costs = pulse["cost_and_authority"]
        self.assertEqual(costs["provider_or_source_requests_used"], 4)
        self.assertEqual(costs["provider_or_source_requests_cap"], 192)
        self.assertEqual(costs["cash_spend_usd_cents"], 0)
        self.assertFalse(costs["external_authority_granted_by_pulse"])

    def test_corrected_gate_requests_authority_without_calendar_block(self) -> None:
        pulse = build_owner_pulse(
            repository_root=ROOT,
            as_of=DUE_AT,
            free_disk_bytes=9_000_000_000,
        )
        self.assertEqual(
            pulse["attention"][0],
            {
                "severity": "HIGH",
                "code": "TASK21_CAPTURE_AUTHORITY_REQUIRED",
                "action": CORRECTED_NEXT_ATOM,
            },
        )
        self.assertEqual(
            pulse["active_time_gates"][0]["state"],
            "READY_FOR_ADMISSION_AND_CAPTURE_AUTHORITY",
        )
        self.assertTrue(
            pulse["active_time_gates"][0]["parallel_work_allowed"]
        )

    def test_output_is_deterministic_relative_and_sanitized(self) -> None:
        first = build_owner_pulse(
            repository_root=ROOT,
            as_of=WAITING_AT,
            free_disk_bytes=9_000_000_000,
        )
        second = build_owner_pulse(
            repository_root=ROOT,
            as_of=WAITING_AT,
            free_disk_bytes=9_000_000_000,
        )
        self.assertEqual(canonical_json_bytes(first), canonical_json_bytes(second))
        for source in first["evidence_sources"]:
            self.assertFalse(Path(source["path"]).is_absolute())
        text = render_owner_pulse_text(first)
        self.assertIn("TASK-21 OWNER PULSE", text)
        self.assertIn("READY_FOR_ADMISSION_AND_CAPTURE_AUTHORITY", text)
        self.assertIn("nominations=3, admissions=0, panels=0", text)
        self.assertIn(
            "Production memory: "
            "HYP-VERSION-EXECUTION-CAPACITY-CURVATURE-V1; state=PAUSED",
            text,
        )
        self.assertIn("Legacy registries (намеренно пусты)", text)
        memory_source = next(
            source
            for source in first["evidence_sources"]
            if source["path"]
            == "docs/evidence/task17/first_bounded_hypothesis_cycle_v1.json"
        )
        self.assertEqual(memory_source["sha256"], _sha256(PRODUCTION_MEMORY_PATH))
        source = json.loads(SOURCE_RECEIPT_PATH.read_text(encoding="utf-8"))
        for candidate in source["offline_receipt"][
            "selected_structural_candidates"
        ]:
            self.assertNotIn(candidate["mint"], text)

    def test_config_authority_and_agent_entry_rule_are_exact(self) -> None:
        self.assertEqual(self.config["read_model_version"], "1.2")
        authority = self.config["authority"]
        self.assertEqual(authority["class"], "LOCAL_WRITE_ONLY")
        self.assertEqual(
            authority["gate_phrase"],
            "T21-P2R_OWNER_PULSE_PRODUCTION_MEMORY_BINDING_V1",
        )
        self.assertEqual(
            authority["managed_files"],
            [
                "configs/task21_owner_pulse_read_model_v1.yaml",
                "docs/contracts/task21_owner_pulse_read_model_contract_v1.md",
                "src/solana_alpha_lab/task21_owner_pulse.py",
                "tests/test_task21_owner_pulse.py",
                "docs/evidence/task21/owner_pulse_read_model_acceptance_v1.json",
            ],
        )
        for key in (
            "network_calls",
            "provider_api_rpc_wss_calls",
            "drive_reads",
            "drive_writes",
            "raw_or_dataset_writes",
            "credentials",
            "cash_spend_usd_cents",
            "wallet_signer_transaction_actions",
            "dependency_changes",
        ):
            self.assertEqual(authority[key], 0, key)
        for key in (
            "scheduler_or_background_process",
            "commit",
            "push",
            "pull_request",
            "merge",
            "destructive_actions",
        ):
            self.assertFalse(authority[key], key)

        agents = AGENTS_PATH.read_text(encoding="utf-8")
        self.assertIn("## ACTIVE_TIME_GATE_CHECK", agents)
        self.assertIn("control/active_time_gates.json", agents)
        self.assertIn("required_next_atom", agents)
        catalog = yaml.safe_load(CORE_CATALOG_PATH.read_text(encoding="utf-8"))
        agents_asset = next(
            item
            for item in catalog["records"]
            if item["asset_id"] == "CTRL-AGENTS-001"
        )
        self.assertEqual(agents_asset["record_version"], "1.8")
        self.assertEqual(
            agents_asset["integrity"]["sha256"],
            _sha256(AGENTS_PATH),
        )

    def test_side_effect_receipt_is_zero(self) -> None:
        pulse = build_owner_pulse(
            repository_root=ROOT,
            as_of=WAITING_AT,
            free_disk_bytes=9_000_000_000,
        )
        effects = pulse["side_effects"]
        for key, value in effects.items():
            if key == "scheduler_or_background_process":
                self.assertFalse(value)
            else:
                self.assertEqual(value, 0, key)

    def test_acceptance_receipt_binds_exact_candidate(self) -> None:
        receipt = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(
            receipt["verdict"],
            "LOCAL_OWNER_PULSE_HORIZON_CORRECTION_BOUND",
        )
        self.assertEqual(receipt["targeted_validation"], "12_OF_12_PASS")
        for artifact in receipt["artifacts"]:
            self.assertEqual(
                _sha256(ROOT / artifact["path"]),
                artifact["sha256"],
                artifact["path"],
            )
        for artifact in receipt["protected_inputs"]:
            self.assertEqual(
                _sha256(ROOT / artifact["path"]),
                artifact["sha256"],
                artifact["path"],
            )
        self.assertEqual(
            receipt["durable_resume_gate"]["required_next_atom"],
            CORRECTED_NEXT_ATOM,
        )
        self.assertEqual(
            receipt["durable_resume_gate"]["earliest_at"],
            "2026-08-06T16:28:59.084Z",
        )
        self.assertFalse(
            receipt["durable_resume_gate"][
                "preempts_new_parallel_mutation_when_due"
            ]
        )
        for key, value in receipt["actual_actions"].items():
            if key == "scheduler_or_background_process":
                self.assertFalse(value)
            else:
                self.assertEqual(value, 0, key)


if __name__ == "__main__":
    unittest.main()
