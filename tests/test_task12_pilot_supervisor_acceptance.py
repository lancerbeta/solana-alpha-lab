from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.pilot_supervisor import (  # noqa: E402
    AtomicDuplicateLock,
    ChildSpec,
    PilotSupervisor,
    SupervisorLimits,
    build_run_identity,
    canonical_json_bytes,
    make_task11_offline_spec,
)

FIXTURE_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task12"
    / "pilot_supervisor_offline_acceptance_v1.json"
)
RECEIPT_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task12"
    / "pilot_supervisor_offline_acceptance_receipt_v1.json"
)
SUMMARY_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task12"
    / "pilot_supervisor_offline_acceptance_summary_v1.md"
)
DISK_OK = 4_000_000_000
FIXTURE_SHA256 = (
    "f798ab8fc40f141b95dce84393971002"
    "5bc8958f094d62e07c0c51c9a00a1d5b"
)
REQUIRED_EVENT_FIELDS = {
    "schema_version",
    "event_type",
    "run_id",
    "consumer_asset_id",
    "attempt_sequence",
    "state",
    "observed_at",
    "monotonic_elapsed_ms",
    "reason",
    "child_exit_code",
    "stdout_bytes",
    "stderr_bytes",
    "disk_free_bytes",
    "provider_calls",
    "cash_spend_usd_cents",
}


def _synthetic_factory(source: str) -> Callable[
    [ChildSpec, Path, Mapping[str, str]],
    subprocess.Popen[bytes],
]:
    def factory(
        _spec: ChildSpec,
        repo_root: Path,
        environment: Mapping[str, str],
    ) -> subprocess.Popen[bytes]:
        return subprocess.Popen(
            (sys.executable, "-B", "-c", source),
            cwd=repo_root,
            env=dict(environment),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )

    return factory


def _limits(**overrides: object) -> SupervisorLimits:
    values: dict[str, object] = {
        "spawn_grace_seconds": 1.0,
        "silence_seconds_max": 1.0,
        "child_wall_seconds_max": 10.0,
        "poll_interval_seconds": 0.2,
        "graceful_stop_seconds": 1.0,
        "line_bytes_max": 16_384,
        "child_output_bytes_max": 262_144,
        "predicted_child_write_bytes_max": 0,
        "start_reserve_fixed_bytes": 536_870_912,
        "runtime_reserve_fixed_bytes": 268_435_456,
    }
    values.update(overrides)
    return SupervisorLimits(**values)  # type: ignore[arg-type]


def _exit_code_class(value: int | None) -> str:
    if value is None:
        return "NONE"
    if value == 0:
        return "ZERO"
    return "NONZERO"


def _parse_utc(value: str) -> datetime:
    if not value.endswith("Z"):
        raise AssertionError(f"timestamp_not_utc_z:{value}")
    return datetime.fromisoformat(value[:-1] + "+00:00")


class Task12PilotSupervisorAcceptanceTests(unittest.TestCase):
    fixture: dict[str, object]
    vectors: list[dict[str, object]]
    results: dict[str, object]

    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.vectors = list(cls.fixture["vectors"])  # type: ignore[arg-type]
        cls.spec = make_task11_offline_spec(
            ROOT,
            python_executable=Path(sys.executable),
        )
        cls.results = {
            str(vector["vector_id"]): cls._execute_vector(vector)
            for vector in cls.vectors
        }

    @classmethod
    def _execute_vector(cls, vector: Mapping[str, object]) -> object:
        vector_id = str(vector["vector_id"])
        window_start = str(vector["window_start"])
        with tempfile.TemporaryDirectory() as directory:
            lock_root = Path(directory) / "locks"
            disk_free: Callable[[Path], int] = lambda _path: DISK_OK
            process_factory = None
            limits = _limits()
            held_lock: AtomicDuplicateLock | None = None

            if vector_id == "ZERO_EXIT_WITHOUT_MARKER_FAILS":
                process_factory = _synthetic_factory(
                    "print('synthetic-complete')"
                )
            elif vector_id == "NONZERO_EXIT_RETAINED":
                process_factory = _synthetic_factory(
                    "import sys; print('typed-failure'); sys.exit(2)"
                )
            elif vector_id == "ACTIVE_DUPLICATE_BLOCKED":
                identity = build_run_identity(
                    cls.spec,
                    utc_window_start=window_start,
                    attempt_sequence=1,
                )
                held_lock = AtomicDuplicateLock(
                    lock_root,
                    duplicate_key=identity.duplicate_key,
                    run_id=identity.run_id,
                    process_start_token="b" * 64,
                )
                if not held_lock.acquire():
                    raise AssertionError("acceptance_lock_not_acquired")

                def must_not_spawn(
                    _spec: ChildSpec,
                    _root: Path,
                    _environment: Mapping[str, str],
                ) -> subprocess.Popen[bytes]:
                    raise AssertionError("duplicate_spawned_child")

                process_factory = must_not_spawn
            elif vector_id == "INSUFFICIENT_DISK_BLOCKS_SPAWN":
                disk_free = lambda _path: 100

                def must_not_spawn_for_disk(
                    _spec: ChildSpec,
                    _root: Path,
                    _environment: Mapping[str, str],
                ) -> subprocess.Popen[bytes]:
                    raise AssertionError("disk_block_spawned_child")

                process_factory = must_not_spawn_for_disk
            elif vector_id == "WALL_TIMEOUT_STOPS_CHILD":
                process_factory = _synthetic_factory(
                    "import time; time.sleep(5)"
                )
                limits = _limits(
                    silence_seconds_max=0.2,
                    child_wall_seconds_max=0.4,
                )
            elif vector_id == "RUNTIME_DISK_BREACH_STOPS_CHILD":
                readings = iter((DISK_OK, 0, 0))
                disk_free = lambda _path: next(readings, 0)
                process_factory = _synthetic_factory(
                    "import time; time.sleep(5)"
                )
            elif vector_id != "OFFLINE_PREFLIGHT_SUCCESS":
                raise AssertionError(f"unknown_acceptance_vector:{vector_id}")

            try:
                supervisor = PilotSupervisor(
                    repo_root=ROOT,
                    lock_root=lock_root,
                    limits=limits,
                    disk_free_bytes=disk_free,
                    process_factory=process_factory,
                )
                return supervisor.run(
                    cls.spec,
                    utc_window_start=window_start,
                    attempt_sequence=1,
                )
            finally:
                if held_lock is not None and not held_lock.release():
                    raise AssertionError("acceptance_lock_not_released")

    def test_fixture_identity_and_source_fingerprints(self) -> None:
        self.assertEqual(
            hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest(),
            FIXTURE_SHA256,
        )
        self.assertEqual(self.fixture["schema_version"], "1.0")
        self.assertEqual(self.fixture["task_id"], "TASK-12")
        self.assertEqual(
            self.fixture["atom_id"],
            "T12-A4_DETERMINISTIC_OFFLINE_ACCEPTANCE_V1",
        )
        self.assertEqual(len(self.vectors), 7)
        consumer = self.fixture["consumer"]
        self.assertEqual(
            consumer["child_plan_sha256"],  # type: ignore[index]
            self.spec.plan_sha256,
        )
        for fingerprint in self.fixture["source_fingerprints"]:
            relative = str(fingerprint["path"])
            target = (ROOT / relative).resolve()
            self.assertTrue(target.is_relative_to(ROOT))
            self.assertTrue(target.is_file())
            self.assertEqual(
                hashlib.sha256(target.read_bytes()).hexdigest(),
                fingerprint["sha256"],
            )

    def test_all_frozen_vectors_match_stable_projection(self) -> None:
        for vector in self.vectors:
            vector_id = str(vector["vector_id"])
            expected = vector["expected"]
            result = self.results[vector_id]
            with self.subTest(vector_id=vector_id):
                self.assertEqual(result.run_id, vector["run_id"])
                self.assertEqual(
                    result.duplicate_key,
                    vector["duplicate_key"],
                )
                self.assertEqual(result.state, expected["state"])
                self.assertEqual(result.reason, expected["reason"])
                self.assertEqual(
                    _exit_code_class(result.child_exit_code),
                    expected["child_exit_code_class"],
                )
                self.assertEqual(
                    result.child_spawn_count,
                    expected["child_spawn_count"],
                )
                self.assertEqual(
                    result.success_marker_observed,
                    expected["success_marker_observed"],
                )
                self.assertEqual(
                    result.to_receipt()["retry_count"],
                    expected["retry_count"],
                )

    def test_events_and_lineage_preserve_time_and_identity(self) -> None:
        for vector in self.vectors:
            vector_id = str(vector["vector_id"])
            result = self.results[vector_id]
            receipt = result.to_receipt()
            lineage = receipt["lineage"]
            event_types = {
                str(event["event_type"]) for event in receipt["events"]
            }
            with self.subTest(vector_id=vector_id):
                self.assertTrue(
                    set(vector["required_event_types"]).issubset(event_types)
                )
                self.assertTrue(
                    set(vector["forbidden_event_types"]).isdisjoint(
                        event_types
                    )
                )
                elapsed = []
                observed = []
                for event in receipt["events"]:
                    self.assertTrue(REQUIRED_EVENT_FIELDS.issubset(event))
                    elapsed.append(event["monotonic_elapsed_ms"])
                    observed.append(_parse_utc(str(event["observed_at"])))
                    self.assertLessEqual(
                        len(canonical_json_bytes(event)),
                        16_384,
                    )
                self.assertEqual(elapsed, sorted(elapsed))
                self.assertEqual(
                    lineage["parent_run_id"],
                    result.run_id,
                )
                self.assertEqual(
                    lineage["child_plan_sha256"],
                    self.spec.plan_sha256,
                )
                self.assertEqual(
                    lineage["sanitized_argv"],
                    list(self.spec.sanitized_argv),
                )
                self.assertIsNone(
                    lineage["accepted_child_receipt_sha256"]
                )
                self.assertIsNone(
                    lineage["accepted_child_manifest_sha256"]
                )
                self.assertFalse(
                    lineage["restart_backdates_availability"]
                )
                availability = _parse_utc(
                    str(lineage["child_availability_timestamp"])
                )
                self.assertGreaterEqual(availability, observed[-1])
                if result.child_spawn_count == 1:
                    self.assertTrue(
                        str(lineage["child_run_id"]).startswith(
                            "t12-child-"
                        )
                    )
                    started = _parse_utc(
                        str(lineage["child_start_timestamp"])
                    )
                    observed_child = _parse_utc(
                        str(lineage["child_observation_timestamp"])
                    )
                    self.assertLessEqual(started, observed_child)
                    self.assertLessEqual(observed_child, availability)
                else:
                    self.assertIsNone(lineage["child_run_id"])
                    self.assertIsNone(lineage["child_start_timestamp"])
                    self.assertIsNone(
                        lineage["child_observation_timestamp"]
                    )

    def test_duplicate_and_disk_preflight_never_spawn(self) -> None:
        blocked = (
            self.results["ACTIVE_DUPLICATE_BLOCKED"],
            self.results["INSUFFICIENT_DISK_BLOCKS_SPAWN"],
        )
        for result in blocked:
            self.assertEqual(result.child_spawn_count, 0)
            self.assertIsNone(result.child_exit_code)
            self.assertNotIn(
                "CHILD_STARTED",
                {event["event_type"] for event in result.events},
            )

    def test_receipts_have_zero_external_effects_and_no_raw_body(self) -> None:
        forbidden_key_fragments = (
            "stdout_body",
            "stderr_body",
            "provider_body",
            "request_header",
            "environment_dump",
        )
        for vector_id, result in self.results.items():
            receipt = result.to_receipt()
            encoded = json.dumps(
                receipt,
                ensure_ascii=False,
                sort_keys=True,
            )
            with self.subTest(vector_id=vector_id):
                self.assertEqual(receipt["provider_calls"], 0)
                self.assertEqual(receipt["raw_data_writes"], 0)
                self.assertEqual(receipt["cash_spend_usd_cents"], 0)
                self.assertEqual(receipt["retry_count"], 0)
                self.assertNotIn(str(ROOT), encoded)
                self.assertIsNone(re.search(r"[A-Za-z]:[\\/]", encoded))
                for forbidden in forbidden_key_fragments:
                    self.assertNotIn(forbidden, encoded.lower())

    def test_tracked_receipt_and_summary_bind_the_fixture(self) -> None:
        receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        summary = SUMMARY_PATH.read_text(encoding="utf-8")
        self.assertEqual(
            receipt["fixture"]["sha256"],
            FIXTURE_SHA256,
        )
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(
            receipt["accepted_result"]["accepted_claim"],
            self.fixture["accepted_claim"],
        )
        self.assertEqual(receipt["accepted_result"]["vector_count"], 7)
        self.assertIn(FIXTURE_SHA256, summary)
        self.assertIn(
            "THIN_OFFLINE_SUPERVISOR_DETERMINISTIC_CONTROL_ACCEPTANCE",
            summary,
        )
        self.assertNotRegex(summary, r"[A-Za-z]:[\\/]")

    def test_nonclaims_and_catalog_deferral_are_explicit(self) -> None:
        nonclaims = self.fixture["nonclaims"]
        self.assertTrue(nonclaims)
        self.assertFalse(any(nonclaims.values()))
        authority = self.fixture["authority"]
        zero_fields = (
            "network_calls",
            "provider_api_rpc_wss_calls",
            "credential_use",
            "collector_executions",
            "raw_data_writes",
            "cash_spend_usd_cents",
            "provider_credits",
            "dependency_changes",
            "wallet_signer_transaction_actions",
        )
        self.assertTrue(all(authority[field] == 0 for field in zero_fields))
        catalog = self.fixture["catalog"]
        self.assertFalse(catalog["changed_in_atom4"])
        self.assertTrue(catalog["blocks_task12_done"])
        self.assertFalse(catalog["blocks_atom4_acceptance"])

    def test_atom5_catalog_registration_is_exact(self) -> None:
        manifest = yaml.safe_load(
            (ROOT / "catalog" / "catalog_manifest.yaml").read_text(
                encoding="utf-8"
            )
        )
        asset_documents = [
            yaml.safe_load((ROOT / relative).read_text(encoding="utf-8"))
            for relative in manifest["root_resolver"]["asset_registries"]
        ]
        records = {
            record["asset_id"]: record
            for document in asset_documents
            for record in document["records"]
        }
        expected = {
            "CONTRACT-T12-PILOT-SUPERVISOR-001",
            "FIXTURE-T12-PILOT-SUPERVISOR-CONTRACT-001",
            "TEST-T12-PILOT-SUPERVISOR-CONTRACT-001",
            "MODULE-T12-PILOT-SUPERVISOR-001",
            "SCRIPT-T12-PILOT-SUPERVISOR-001",
            "TEST-T12-PILOT-SUPERVISOR-001",
            "FIXTURE-T12-PILOT-SUPERVISOR-OFFLINE-ACCEPTANCE-001",
            "EVIDENCE-T12-PILOT-SUPERVISOR-OFFLINE-ACCEPTANCE-001",
            "EVIDENCE-T12-PILOT-SUPERVISOR-OFFLINE-SUMMARY-001",
            "TEST-T12-PILOT-SUPERVISOR-ACCEPTANCE-001",
        }
        self.assertEqual(
            len(records),
            manifest["current_checkpoint"]["assets"],
        )
        self.assertTrue(expected.issubset(records))
        self.assertTrue(
            expected.issubset(set(manifest["mandatory_asset_ids"]))
        )
        receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            receipt["catalog"]["status"],
            "REGISTERED_IN_TASK12_CATALOG_TRANSACTION",
        )
        self.assertTrue(receipt["catalog"]["changed_in_atom5"])


if __name__ == "__main__":
    unittest.main()
