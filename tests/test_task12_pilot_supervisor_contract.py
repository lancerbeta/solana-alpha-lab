from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task12"
    / "pilot_supervisor_contract_v1.json"
)
CONTRACT_PATH = (
    ROOT / "docs" / "contracts" / "pilot_supervisor_contract_v1.md"
)
EXPECTED_FIXTURE_SHA256 = (
    "dad8c95b2e81fe918a04fa651cb55e8556ee91cdeb0074161b7315d69821df2c"
)
EXPECTED_MANAGED_FILES = [
    "docs/contracts/pilot_supervisor_contract_v1.md",
    "tests/fixtures/task12/pilot_supervisor_contract_v1.json",
    "tests/test_task12_pilot_supervisor_contract.py",
    "catalog/assets/core.yaml",
]
EXPECTED_TERMINAL_STATES = {
    "SUCCEEDED",
    "FAILED",
    "TIMED_OUT",
    "STOPPED",
    "BLOCKED_DUPLICATE",
    "BLOCKED_DISK",
}


class Task12PilotSupervisorContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture_bytes = FIXTURE_PATH.read_bytes()
        cls.document = json.loads(cls.fixture_bytes)
        cls.contract = CONTRACT_PATH.read_text(encoding="utf-8")

    def test_frozen_identity_and_managed_inventory_are_exact(self) -> None:
        self.assertEqual(
            hashlib.sha256(self.fixture_bytes).hexdigest(),
            EXPECTED_FIXTURE_SHA256,
        )
        self.assertEqual(
            self.document["schema"],
            "solana_alpha_lab.pilot_supervisor_contract",
        )
        self.assertEqual(
            self.document["contract_id"],
            "CONTRACT-T12-PILOT-SUPERVISOR-001",
        )
        self.assertEqual(self.document["task_id"], "TASK-12")
        self.assertEqual(
            self.document["atom_id"],
            "T12-A2_OFFLINE_SUPERVISOR_CONTRACT_V1",
        )
        self.assertEqual(self.document["entry_verdict"], "START_WITH_PATCH")
        self.assertEqual(
            self.document["accepted_claim"],
            "OFFLINE_SUPERVISOR_CONTRACT_FROZEN",
        )
        self.assertFalse(self.document["implementation_claim"])
        self.assertFalse(self.document["unattended_pilot_claim"])
        self.assertEqual(
            self.document["authority"]["managed_files"],
            EXPECTED_MANAGED_FILES,
        )

    def test_one_offline_consumer_has_no_execution_surface(self) -> None:
        consumer = self.document["selected_consumer"]
        self.assertEqual(
            consumer["asset_id"],
            "SCRIPT-T11-ENTITY-INPUT-PROBE-001",
        )
        self.assertEqual(consumer["mode"], "OFFLINE_PREFLIGHT_ONLY")
        self.assertFalse(consumer["network_required"])
        self.assertFalse(consumer["raw_write_required"])
        self.assertNotIn("--execute", consumer["argv_template"])
        self.assertNotIn("--replay-run", consumer["argv_template"])
        self.assertEqual(
            set(consumer["forbidden_arguments"]),
            {"--execute", "--replay-run"},
        )
        self.assertEqual(
            consumer["expected_success_marker"],
            "TASK11_ENTITY_PROBE_PREFLIGHT: PASS",
        )

    def test_reuse_keeps_first_slice_stdlib_thin_and_dependency_free(self) -> None:
        reuse = self.document["reuse"]
        self.assertIn("REUSE-T04-LOGGING-001", reuse["adopt"])
        self.assertEqual(reuse["build"], ["REUSE-T04-COORDINATOR-001"])
        self.assertEqual(reuse["wrap"], [])
        self.assertEqual(reuse["fork"], [])
        self.assertIn("REUSE-T04-COMPOSE-001", reuse["deferred"])
        self.assertIn("REUSE-T04-APSCHEDULER-001", reuse["deferred"])
        self.assertEqual(reuse["rejected"], ["REUSE-T04-CELERY-001"])
        self.assertEqual(reuse["new_dependency_count"], 0)

    def test_run_identity_separates_monotonic_duration_from_utc_evidence(
        self,
    ) -> None:
        identity = self.document["run_identity"]
        self.assertEqual(identity["hash_algorithm"], "SHA256")
        self.assertEqual(identity["duration_clock"], "MONOTONIC")
        self.assertEqual(identity["evidence_timestamp_clock"], "UTC_RFC3339")
        self.assertIn("attempt_sequence", identity["inputs"])
        self.assertTrue(identity["restart_creates_new_attempt_sequence"])
        self.assertFalse(identity["restart_backdates_availability"])

    def test_duplicate_guard_is_atomic_and_cannot_steal_by_age(self) -> None:
        guard = self.document["duplicate_guard"]
        self.assertEqual(guard["acquisition"], "ATOMIC_CREATE_EXCLUSIVE")
        self.assertEqual(guard["max_active_processes_per_key"], 1)
        self.assertFalse(guard["age_alone_proves_stale"])
        self.assertEqual(
            set(guard["stale_reconciliation_requires"]),
            {
                "recorded_process_identity",
                "recorded_process_start_token",
                "lock_owner_run_id",
            },
        )
        self.assertEqual(guard["duplicate_state"], "BLOCKED_DUPLICATE")
        self.assertFalse(guard["duplicate_spawns_child"])
        self.assertTrue(guard["release_only_owned_lock"])

    def test_state_machine_is_finite_and_terminal_states_never_transition(
        self,
    ) -> None:
        machine = self.document["state_machine"]
        states = set(machine["states"])
        transitions = machine["allowed_transitions"]
        self.assertEqual(states, set(transitions))
        self.assertEqual(
            set(machine["terminal_states"]),
            EXPECTED_TERMINAL_STATES,
        )
        for terminal in EXPECTED_TERMINAL_STATES:
            with self.subTest(terminal=terminal):
                self.assertEqual(transitions[terminal], [])
        for source, targets in transitions.items():
            with self.subTest(source=source):
                self.assertTrue(set(targets).issubset(states))
        self.assertFalse(machine["zero_exit_alone_is_success"])
        self.assertIn(
            "exact_success_marker_observed",
            machine["success_requires"],
        )

    def test_terminal_reasons_preserve_distinct_failure_classes(self) -> None:
        reasons = self.document["terminal_reasons"]
        self.assertEqual(reasons["CHILD_WALL_TIMEOUT"], "TIMED_OUT")
        self.assertEqual(reasons["ACTIVE_DUPLICATE"], "BLOCKED_DUPLICATE")
        self.assertEqual(
            reasons["INSUFFICIENT_DISK_BEFORE_START"],
            "BLOCKED_DISK",
        )
        self.assertEqual(reasons["DISK_GUARD_BREACHED"], "BLOCKED_DISK")
        self.assertEqual(reasons["EXPECTED_MARKER_MISSING"], "FAILED")
        self.assertEqual(reasons["CHILD_EXIT_NONZERO"], "FAILED")

    def test_health_retry_and_stop_are_bounded(self) -> None:
        health = self.document["health"]
        self.assertEqual(health["spawn_grace_seconds"], 5)
        self.assertEqual(health["silence_seconds_max"], 30)
        self.assertEqual(health["child_wall_seconds_max"], 60)
        self.assertGreaterEqual(health["poll_interval_milliseconds_min"], 200)
        self.assertFalse(health["exit_without_terminal_marker_is_healthy"])
        stop = self.document["retry_and_stop"]
        self.assertEqual(stop["concurrency"], 1)
        self.assertEqual(stop["retry_count_max"], 0)
        self.assertFalse(stop["automatic_restart"])
        self.assertEqual(stop["graceful_stop_seconds"], 5)
        self.assertFalse(stop["delete_child_artifacts_on_stop"])
        self.assertFalse(stop["delete_other_run_lock"])

    def test_structured_event_and_output_caps_are_finite(self) -> None:
        events = self.document["structured_events"]
        self.assertEqual(events["encoding"], "NDJSON_CANONICAL_JSON")
        self.assertIn("SUPERVISOR_STARTED", events["required_event_types"])
        self.assertIn("SUPERVISOR_FINISHED", events["required_event_types"])
        for field in (
            "run_id",
            "state",
            "observed_at",
            "monotonic_elapsed_ms",
            "disk_free_bytes",
            "provider_calls",
            "cash_spend_usd_cents",
        ):
            with self.subTest(field=field):
                self.assertIn(field, events["required_fields"])
        self.assertEqual(events["line_bytes_max"], 16_384)
        self.assertEqual(
            events["child_stdout_stderr_bytes_max"],
            262_144,
        )
        self.assertEqual(events["sanitized_run_log_bytes_max"], 1_048_576)
        self.assertEqual(events["local_retention_days_max"], 7)
        self.assertTrue(events["environment_dump_forbidden"])
        self.assertTrue(events["provider_body_forbidden"])

    def test_disk_guard_blocks_before_spawn_and_fails_closed_at_runtime(
        self,
    ) -> None:
        guard = self.document["disk_guard"]
        self.assertTrue(guard["telemetry_required"])
        self.assertEqual(guard["missing_telemetry_disposition"], "FAIL_CLOSED")
        predicted = guard["offline_predicted_child_write_bytes_max"]
        start_required = (
            guard["start_reserve_multiplier"] * predicted
            + guard["start_reserve_fixed_bytes"]
        )
        self.assertEqual(start_required, 536_870_912)
        self.assertEqual(guard["runtime_reserve_fixed_bytes"], 268_435_456)
        self.assertEqual(guard["insufficient_start_state"], "BLOCKED_DISK")
        self.assertEqual(guard["runtime_breach_state"], "BLOCKED_DISK")
        self.assertFalse(guard["sustained_pilot_forecast_claim"])

    def test_lineage_and_pit_meanings_cannot_be_rewritten(self) -> None:
        lineage = self.document["lineage_and_pit"]
        self.assertFalse(lineage["child_artifacts_rewritten"])
        self.assertTrue(lineage["task06_raw_identity_preserved"])
        self.assertTrue(lineage["task06_revision_links_preserved"])
        self.assertTrue(lineage["task06_manifest_hashes_preserved"])
        self.assertTrue(
            lineage["event_observed_available_ingested_meanings_preserved"]
        )
        self.assertFalse(lineage["restart_backdates_availability"])
        self.assertFalse(lineage["missing_output_is_zero"])
        self.assertFalse(lineage["provider_failure_is_no_route"])
        self.assertFalse(lineage["provider_failure_is_success"])

    def test_synthetic_vectors_cover_all_decision_relevant_failures(self) -> None:
        vectors = {
            row["vector_id"]: row
            for row in self.document["synthetic_vectors"]
        }
        expected = {
            "OFFLINE_PREFLIGHT_SUCCESS": ("SUCCEEDED", None, 1),
            "ZERO_EXIT_WITHOUT_MARKER_FAILS": (
                "FAILED",
                "EXPECTED_MARKER_MISSING",
                1,
            ),
            "NONZERO_EXIT_RETAINED": ("FAILED", "CHILD_EXIT_NONZERO", 1),
            "ACTIVE_DUPLICATE_BLOCKED": (
                "BLOCKED_DUPLICATE",
                "ACTIVE_DUPLICATE",
                0,
            ),
            "INSUFFICIENT_DISK_BLOCKS_SPAWN": (
                "BLOCKED_DISK",
                "INSUFFICIENT_DISK_BEFORE_START",
                0,
            ),
            "WALL_TIMEOUT_STOPS_CHILD": (
                "TIMED_OUT",
                "CHILD_WALL_TIMEOUT",
                1,
            ),
            "RUNTIME_DISK_BREACH_STOPS_CHILD": (
                "BLOCKED_DISK",
                "DISK_GUARD_BREACHED",
                1,
            ),
        }
        self.assertEqual(set(vectors), set(expected))
        for vector_id, outcome in expected.items():
            with self.subTest(vector_id=vector_id):
                row = vectors[vector_id]
                self.assertEqual(
                    (
                        row["expected_state"],
                        row["expected_reason"],
                        row["child_spawn_count"],
                    ),
                    outcome,
                )

    def test_atom2_authority_has_zero_external_or_git_actions(self) -> None:
        authority = self.document["authority"]
        self.assertEqual(authority["class"], "LOCAL_WRITE_ONLY")
        self.assertEqual(authority["source"], "EXPLICIT_USER")
        for field in (
            "network_calls",
            "provider_api_rpc_wss_calls",
            "credential_use",
            "collector_executions",
            "raw_data_writes",
            "cash_spend_usd_cents",
            "provider_credits",
            "dependency_changes",
        ):
            with self.subTest(field=field):
                self.assertEqual(authority[field], 0)
        for field in (
            "commit",
            "push",
            "pull_request",
            "merge",
            "ui_changes",
            "destructive_actions",
        ):
            with self.subTest(field=field):
                self.assertFalse(authority[field])
        self.assertFalse(
            self.document["next_atom"]["production_code_authorized"]
        )
        self.assertFalse(
            self.document["next_atom"]["external_calls_authorized"]
        )

    def test_catalog_deferral_is_explicit_and_blocks_only_task_done(self) -> None:
        catalog = self.document["catalog"]
        self.assertFalse(catalog["registered_in_atom2"])
        self.assertEqual(
            catalog["status"],
            "CATALOG_TRANSACTION_PENDING_TASK12_FINAL_RECONCILIATION",
        )
        self.assertTrue(catalog["blocks_task12_done"])
        self.assertFalse(catalog["blocks_contract_freeze"])
        self.assertEqual(
            set(catalog["planned_asset_ids"]),
            {
                "CONTRACT-T12-PILOT-SUPERVISOR-001",
                "FIXTURE-T12-PILOT-SUPERVISOR-001",
                "TEST-T12-PILOT-SUPERVISOR-CONTRACT-001",
            },
        )

    def test_contract_records_required_boundaries_and_stable_ids(self) -> None:
        for marker in (
            "OFFLINE_SUPERVISOR_CONTRACT_FROZEN",
            "SCRIPT-T11-ENTITY-INPUT-PROBE-001",
            "REUSE-T04-COORDINATOR-001",
            "`BLOCKED_DUPLICATE`",
            "`BLOCKED_DISK`",
            "`TIMED_OUT`",
            "missing output is not zero",
            "Provider failure is not",
            "CATALOG_TRANSACTION_PENDING_TASK12_FINAL_RECONCILIATION",
            "USD 0",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.contract)

    def test_tracked_contract_artifacts_have_no_secret_or_machine_path(
        self,
    ) -> None:
        texts = {
            "contract": self.contract,
            "fixture": self.fixture_bytes.decode("utf-8"),
            "test": Path(__file__).read_text(encoding="utf-8"),
        }
        prohibited = {
            "windows_absolute_path": re.compile(r"(?i)\b[a-z]:[\\/]"),
            "user_home_path": re.compile(r"(?i)/(?:users|home)/[^/\s]+"),
            "private_key_block": re.compile(
                r"-----BEGIN [A-Z ]*PRIVATE KEY-----"
            ),
            "credential_assignment": re.compile(
                r"(?i)\b(?:api[_-]?key|access[_-]?token|password|secret)"
                r"\s*[:=]\s*[\"'][^\"']+[\"']"
            ),
        }
        for label, text in texts.items():
            for pattern_name, pattern in prohibited.items():
                with self.subTest(file=label, pattern=pattern_name):
                    self.assertIsNone(pattern.search(text))


if __name__ == "__main__":
    unittest.main()
