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
    EXPECTED_GATE_ID,
    EXPECTED_NEXT_ATOM,
    H1_NEXT_ATOM,
    H6_NEXT_ATOM,
    H24_NEXT_ATOM,
    H72_NEXT_ATOM,
    H168_NEXT_ATOM,
    Task21OwnerPulseError,
    build_observation_schedule,
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
    / "owner_pulse_pre_h24_recovery_binding_acceptance_v1.json"
)
SCHEDULE_ACCEPTANCE_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task21"
    / "owner_pulse_post_h6_sentinel_rebase_acceptance_v2.json"
)
HORIZON_POLICY_PATH = (
    ROOT / "configs" / "task21_observation_horizon_policy_v1.yaml"
)
SENTINEL_REBASE_PATH = (
    ROOT / "configs" / "task21_post_h6_gap_sentinel_value_rebase_v1.yaml"
)
H0_RECEIPT_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task21"
    / "h0_admission_capture_runtime_acceptance_v1.json"
)
WAITING_AT = datetime(2026, 7, 31, 15, 0, tzinfo=timezone.utc)
DUE_AT = datetime(2026, 8, 1, 7, 55, tzinfo=timezone.utc)
MISSED_AT = datetime(2026, 8, 1, 8, 5, tzinfo=timezone.utc)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _unresolved_h24_gate(marker: dict) -> dict:
    gate = copy.deepcopy(marker["gates"][3])
    gate["status"] = "ACTIVE_WAITING"
    gate.pop("resolution", None)
    gate["capture_prep"]["status"] = "READY_NOT_AUTHORIZED"
    return gate


class TestTask21OwnerPulse(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        cls.marker = json.loads(MARKER_PATH.read_text(encoding="utf-8"))

    def test_marker_is_exact_and_source_receipt_is_pinned(self) -> None:
        self.assertEqual(self.marker["schema_version"], "1.0")
        self.assertEqual(len(self.marker["gates"]), 4)
        historical, h1_gate, h6_gate, gate = self.marker["gates"]
        self.assertEqual(historical["gate_id"], EXPECTED_GATE_ID)
        self.assertEqual(historical["status"], "SUPERSEDED_WITH_EVIDENCE")
        self.assertEqual(historical["required_next_atom"], EXPECTED_NEXT_ATOM)
        self.assertEqual(
            historical["effective_next_boundary"]["required_next_atom"],
            H1_NEXT_ATOM,
        )
        self.assertTrue(
            historical["effective_next_boundary"]["calendar_wait_required"]
        )
        self.assertEqual(h1_gate["status"], "RESOLVED_WITH_EVIDENCE")
        self.assertEqual(h1_gate["required_next_atom"], H1_NEXT_ATOM)
        self.assertEqual(h6_gate["status"], "RESOLVED_WITH_GAP_EVIDENCE")
        self.assertEqual(h6_gate["required_next_atom"], H6_NEXT_ATOM)
        self.assertEqual(gate["status"], "RESOLVED_WITH_EVIDENCE")
        self.assertEqual(gate["required_next_atom"], H24_NEXT_ATOM)
        self.assertEqual(
            gate["resolution"]["disposition"],
            "ONE_FROZEN_SENTINEL_CAPTURED_AT_H24_PLUS",
        )
        self.assertEqual(gate["resolution"]["actual_elapsed_seconds"], 90597)
        self.assertEqual(
            _sha256(SOURCE_RECEIPT_PATH),
            historical["source_receipt"]["sha256"],
        )
        self.assertTrue(
            all(
                value == 0
                for value in gate["authority_granted_by_marker"].values()
            )
        )

    def test_waiting_gate_allows_only_non_interfering_parallel_work(self) -> None:
        gate = evaluate_time_gate(
            _unresolved_h24_gate(self.marker),
            as_of=WAITING_AT,
        )
        self.assertEqual(gate["state"], "WAITING_PARALLEL_WORK_ALLOWED")
        self.assertTrue(gate["parallel_work_allowed"])
        self.assertFalse(gate["owner_action_required"])
        self.assertGreater(gate["remaining_seconds"], 0)
        self.assertFalse(gate["external_authority_granted"])

    def test_due_gate_preempts_new_parallel_mutation(self) -> None:
        gate = evaluate_time_gate(
            _unresolved_h24_gate(self.marker),
            as_of=DUE_AT,
        )
        self.assertEqual(gate["state"], "DUE_PREEMPT_PARALLEL_WORK")
        self.assertFalse(gate["parallel_work_allowed"])
        self.assertTrue(gate["owner_action_required"])
        self.assertEqual(gate["remaining_seconds"], 0)
        self.assertEqual(gate["required_next_atom"], H24_NEXT_ATOM)

    def test_late_h24_remains_due_without_expiry(self) -> None:
        gate = evaluate_time_gate(
            _unresolved_h24_gate(self.marker),
            as_of=MISSED_AT,
        )
        self.assertEqual(gate["state"], "DUE_PREEMPT_PARALLEL_WORK")
        self.assertFalse(gate["parallel_work_allowed"])
        self.assertTrue(gate["owner_action_required"])

    def test_marker_cannot_grant_external_authority(self) -> None:
        changed = _unresolved_h24_gate(self.marker)
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
        self.assertEqual(forward["real_admissions"], 3)
        self.assertEqual(forward["panels_captured"], 7)
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
            (partition["bytes"] if expected_identity_ok else 0)
            + 140414
            + 128958
            + 1126
            + 43852,
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
        schedule = pulse["observation_schedule"]
        self.assertEqual(
            schedule["status"],
            "H24_CAPTURED_H72_H168_TRIGGER_ONLY",
        )
        self.assertEqual(schedule["h0_anchor_at"], "2026-07-31T07:50:34.414367Z")
        self.assertEqual(
            [item["horizon_id"] for item in schedule["windows"]],
            ["H24", "H72", "H168"],
        )
        h24, h72, h168 = schedule["windows"]
        self.assertEqual(h24["state"], "RESOLVED_WITH_EVIDENCE")
        self.assertEqual(h24["required_next_atom"], H24_NEXT_ATOM)
        self.assertEqual(h72["state"], "DEFERRED_TRIGGER_ONLY")
        self.assertEqual(h72["required_next_atom"], H72_NEXT_ATOM)
        self.assertEqual(h72["earliest_at"], "2026-08-03T07:50:34.414367Z")
        self.assertEqual(h72["earliest_at_msk"], "2026-08-03T10:50:34.414367+03:00")
        self.assertEqual(h168["required_next_atom"], H168_NEXT_ATOM)
        self.assertEqual(h168["earliest_at"], "2026-08-07T07:50:34.414367Z")
        self.assertEqual(h168["earliest_at_msk"], "2026-08-07T10:50:34.414367+03:00")
        self.assertTrue(all(item["latest_at"] is None for item in schedule["windows"]))
        self.assertFalse(schedule["narrow_expiry_window_used"])
        self.assertTrue(
            all(
                item["external_authority_granted"] is False
                and item["automatic_execution"] is False
                for item in schedule["windows"]
            )
        )

    def test_schedule_fails_closed_for_offset_or_active_gate_drift(self) -> None:
        policy = yaml.safe_load(HORIZON_POLICY_PATH.read_text(encoding="utf-8"))
        sentinel_rebase = yaml.safe_load(
            SENTINEL_REBASE_PATH.read_text(encoding="utf-8")
        )
        h0_receipt = json.loads(H0_RECEIPT_PATH.read_text(encoding="utf-8"))
        active_gate = copy.deepcopy(self.marker["gates"][3])
        evaluated = evaluate_time_gate(active_gate, as_of=WAITING_AT)
        changed_policy = copy.deepcopy(policy)
        changed_policy["capture_clock"]["offsets"][4]["offset_seconds"] += 1
        with self.assertRaisesRegex(
            Task21OwnerPulseError, "horizon_schedule_offset_drift"
        ):
            build_observation_schedule(
                horizon_policy=changed_policy,
                sentinel_rebase=sentinel_rebase,
                h0_receipt=h0_receipt,
                active_gate=active_gate,
                evaluated_gate=evaluated,
                as_of=WAITING_AT,
            )
        changed_gate = copy.deepcopy(active_gate)
        changed_gate["latest_at"] = "2026-08-01T08:00:35.414367Z"
        with self.assertRaisesRegex(
            Task21OwnerPulseError, "horizon_schedule_active_gate_drift"
        ):
            build_observation_schedule(
                horizon_policy=policy,
                sentinel_rebase=sentinel_rebase,
                h0_receipt=h0_receipt,
                active_gate=changed_gate,
                evaluated_gate=evaluated,
                as_of=WAITING_AT,
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
        self.assertEqual(costs["provider_or_source_requests_used"], 60)
        self.assertEqual(costs["provider_or_source_requests_cap"], 192)
        self.assertEqual(costs["provider_credits_used"], 56)
        self.assertEqual(costs["response_bytes_used"], 86091)
        self.assertEqual(costs["cash_spend_usd_cents"], 0)
        self.assertFalse(costs["external_authority_granted_by_pulse"])

    def test_h24_resolution_clears_due_attention(self) -> None:
        pulse = build_owner_pulse(
            repository_root=ROOT,
            as_of=DUE_AT,
            free_disk_bytes=9_000_000_000,
        )
        self.assertNotIn(
            "TASK21_H24_CAPTURE_DUE",
            {item["code"] for item in pulse["attention"]},
        )
        self.assertEqual(
            pulse["active_time_gates"][0]["state"],
            "RESOLVED_WITH_EVIDENCE",
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
        self.assertIn("H24_CAPTURED_FUTURE_SENTINELS_TRIGGER_ONLY", text)
        self.assertIn("Расписание наблюдений (MSK)", text)
        self.assertIn("H72: DEFERRED_TRIGGER_ONLY", text)
        self.assertIn("H168: DEFERRED_TRIGGER_ONLY", text)
        self.assertIn("expires=NO", text)
        self.assertIn("nominations=3, admissions=3, panels=7", text)
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
        self.assertEqual(self.config["read_model_version"], "1.8")
        authority = self.config["authority"]
        self.assertEqual(authority["class"], "LOCAL_WRITE_ONLY")
        self.assertEqual(
            authority["gate_phrase"],
            "T21-A6S_POST_H6_GAP_SENTINEL_VALUE_REBASE_V1",
        )
        self.assertEqual(
            authority["managed_files"],
            [
                "configs/task21_owner_pulse_read_model_v1.yaml",
                "docs/contracts/task21_owner_pulse_read_model_contract_v1.md",
                "src/solana_alpha_lab/task21_owner_pulse.py",
                "tests/test_task21_owner_pulse.py",
                "docs/evidence/task21/observation_horizon_consumer_reconciliation_acceptance_v1.json",
                "docs/evidence/task21/owner_pulse_multi_horizon_schedule_acceptance_v1.json",
            ],
        )
        for key in (
            "network_calls",
            "provider_api_rpc_wss_calls",
            "raw_or_dataset_writes",
            "credentials",
            "cash_spend_usd_cents",
            "wallet_signer_transaction_actions",
            "dependency_changes",
        ):
            self.assertEqual(authority[key], 0, key)
        self.assertEqual(authority["drive_reads"], 0)
        self.assertEqual(authority["drive_writes"], 0)
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
        self.assertGreaterEqual(
            tuple(int(part) for part in agents_asset["record_version"].split(".")),
            (1, 8),
        )
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

    def test_historical_acceptance_receipt_remains_audit_only(self) -> None:
        receipt = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            _sha256(ACCEPTANCE_PATH),
            "ebfc7fd85a2e5fd20f2444a2618056f3a1d7f1d4750f355da8e662d2e1fed634",
        )
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(
            receipt["verdict"],
            "LOCAL_OWNER_PULSE_H24_RECOVERY_REFRESH_BOUND",
        )
        self.assertEqual(receipt["targeted_validation"], "13_OF_13_PASS")
        for artifact in receipt["protected_inputs"]:
            if artifact["path"] != "control/active_time_gates.json":
                self.assertEqual(
                    _sha256(ROOT / artifact["path"]),
                    artifact["sha256"],
                    artifact["path"],
                )
        self.assertEqual(
            receipt["durable_resume_gate"]["required_next_atom"],
            H24_NEXT_ATOM,
        )
        self.assertEqual(
            receipt["durable_resume_gate"]["earliest_at"],
            "2026-08-01T07:50:34.414367Z",
        )
        self.assertTrue(
            receipt["durable_resume_gate"]["preempts_new_mutation_when_due"]
        )
        actions = receipt["actual_actions"]
        self.assertEqual(actions["network_calls"], 9)
        self.assertEqual(actions["drive_reads"], 7)
        self.assertEqual(actions["drive_upload_attempts"], 2)
        self.assertEqual(actions["drive_writes"], 1)
        for key in (
            "provider_api_rpc_wss_calls",
            "raw_or_dataset_writes",
            "credentials",
            "cash_spend_usd_cents",
            "wallet_signer_transaction_actions",
            "dependency_changes",
            "commit",
            "push",
            "pull_request",
            "merge",
            "destructive_actions",
        ):
            self.assertEqual(actions[key], 0, key)
        self.assertFalse(actions["scheduler_or_background_process"])

    def test_rebased_schedule_acceptance_binds_exact_candidate(self) -> None:
        receipt = json.loads(SCHEDULE_ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(
            receipt["verdict"],
            "OWNER_PULSE_H24_MINIMUM_AGE_H72_H168_TRIGGER_ONLY",
        )
        self.assertEqual(receipt["targeted_validation"], "15_OF_15_PASS")
        forward_evolved = {
            "src/solana_alpha_lab/task21_owner_pulse.py",
            "tests/test_task21_owner_pulse.py",
        }
        for artifact in receipt["artifacts"]:
            if artifact["path"] in forward_evolved:
                continue
            self.assertEqual(
                _sha256(ROOT / artifact["path"]),
                artifact["sha256"],
                artifact["path"],
            )
        self.assertEqual(
            receipt["schedule"]["horizons"], ["H24", "H72", "H168"]
        )
        self.assertFalse(receipt["schedule"]["h72_active_gate_created"])
        self.assertFalse(receipt["schedule"]["h168_active_gate_created"])
        self.assertFalse(receipt["schedule"]["narrow_expiry_window_used"])
        for value in receipt["actual_actions"].values():
            if isinstance(value, bool):
                self.assertFalse(value)
            else:
                self.assertEqual(value, 0)


if __name__ == "__main__":
    unittest.main()
