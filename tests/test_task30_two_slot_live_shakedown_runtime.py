from __future__ import annotations

import sys
import tempfile
import unittest
import hashlib
import json
import subprocess
import copy
from pathlib import Path

import yaml
import jsonschema


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
POLICY_PATH = ROOT / "configs" / "task30_two_slot_live_shakedown_runtime_v1.yaml"
SCRIPT_PATH = ROOT / "scripts" / "run_task30_two_slot_live_shakedown.py"
CONTRACT_PATH = ROOT / "docs" / "contracts" / "task30_two_slot_live_shakedown_runtime_contract_v1.md"
SCHEMA_PATH = ROOT / "catalog" / "schemas" / "task30_two_slot_live_shakedown_runtime.schema.json"
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "task30" / "two_slot_live_shakedown_runtime_v1.json"
ACCEPTANCE_PATH = ROOT / "docs" / "evidence" / "task30" / "a11c_two_slot_live_shakedown_runtime_offline_acceptance_v1.json"
CATALOG_CORE_PATH = ROOT / "catalog" / "assets" / "core.yaml"
DESIGN_PATH = ROOT / "docs" / "superpowers" / "specs" / "2026-08-11-t30-a11c-two-slot-shakedown-runtime-harness-design.md"
PLAN_PATH = ROOT / "docs" / "superpowers" / "plans" / "2026-08-11-t30-a11c-two-slot-shakedown-runtime-harness.md"

ARTIFACT_PATHS = {
    "contract": CONTRACT_PATH,
    "configuration": POLICY_PATH,
    "schema": SCHEMA_PATH,
    "fixture": FIXTURE_PATH,
    "module": ROOT / "src" / "solana_alpha_lab" / "task30_two_slot_live_shakedown_runtime.py",
    "script": SCRIPT_PATH,
    "test": Path(__file__),
    "design": DESIGN_PATH,
    "plan": PLAN_PATH,
}
EXPECTED_A11C_ASSET_IDS = {
    "CONTRACT-T30-TWO-SLOT-LIVE-SHAKEDOWN-RUNTIME-001",
    "CONFIG-T30-TWO-SLOT-LIVE-SHAKEDOWN-RUNTIME-001",
    "SCHEMA-T30-TWO-SLOT-LIVE-SHAKEDOWN-RUNTIME-001",
    "FIXTURE-T30-TWO-SLOT-LIVE-SHAKEDOWN-RUNTIME-001",
    "MODULE-T30-TWO-SLOT-LIVE-SHAKEDOWN-RUNTIME-001",
    "SCRIPT-T30-TWO-SLOT-LIVE-SHAKEDOWN-RUNTIME-001",
    "TEST-T30-TWO-SLOT-LIVE-SHAKEDOWN-RUNTIME-001",
    "EVIDENCE-T30-A11C-TWO-SLOT-LIVE-SHAKEDOWN-RUNTIME-001",
}

from solana_alpha_lab.task30_two_slot_live_shakedown_runtime import (  # noqa: E402
    TwoSlotShakedownRuntimeError,
    build_slot_plan,
    parse_execution_authority,
    run_slot,
)


def load_yaml(path: Path) -> dict[str, object]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


AUTHORITY_TEXT = (
    "T30-A11C_TWO_SLOT_SHAKEDOWN_EXECUTION_V1;"
    "pool=URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S;"
    "slot_starts_utc=2026-08-12T10:00:00Z,2026-08-12T10:15:00Z;"
    "monitoring_owner=LOCAL_WORK_CODEX_FOREGROUND;max_gets=8;"
    "retention=A4;retry=false;fallback=false"
)
HEALTHY_RESPONSE_BYTES = (
    b'{"data":{"attributes":{"ohlcv_list":[[1786528800,"1.00","1.10","0.90","1.05","100"]]}}}'
)


class FakeClock:
    def __init__(self, epoch: int) -> None:
        self.epoch = epoch

    def now(self) -> int:
        return self.epoch

    def sleep(self, seconds: float) -> None:
        self.epoch += int(seconds)


class FakeTransport:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.calls = 0

    def __call__(self, _request: object) -> dict[str, object]:
        self.calls += 1
        return {"http_status": 200, "safe_response_headers": {}, "body": self.body}


class FailIfCalledTransport:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, _request: object) -> dict[str, object]:
        self.calls += 1
        raise AssertionError("transport must not be called")


class RuntimeErrorTransport:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, _request: object) -> dict[str, object]:
        self.calls += 1
        raise RuntimeError("synthetic transport failure")


class Task30TwoSlotLiveShakedownRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temporary_directory.name)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def policy(self) -> dict[str, object]:
        return load_yaml(POLICY_PATH)

    def authority(self) -> dict[str, object]:
        return parse_execution_authority(AUTHORITY_TEXT)

    def test_exact_authority_and_first_slot_plan_have_four_gets_and_zero_io(self) -> None:
        policy = self.policy()
        authority = self.authority()

        plan = build_slot_plan(policy, authority, slot_index=1, now_epoch=1786529670)

        self.assertEqual([item["offset_seconds"] for item in plan], [0, 15, 30, 60])
        self.assertTrue(all(item["method"] == "GET" for item in plan))
        self.assertTrue(all(item["before_timestamp"] == 1786529700 for item in plan))

    def test_healthy_fake_first_slot_writes_four_immutable_checkpoints(self) -> None:
        clock = FakeClock(1786529700)
        result = run_slot(
            self.policy(), self.authority(), slot_index=1, raw_root=self.temp_root,
            transport=FakeTransport(HEALTHY_RESPONSE_BYTES), now=clock.now, sleep=clock.sleep,
        )

        self.assertEqual(result["terminal_state"], "SLOT_TECHNICAL_HEALTHY")
        self.assertEqual(len(list((self.temp_root / "raw").glob("*.json"))), 4)
        self.assertEqual(len(list(self.temp_root.glob("raw_manifest_*.json"))), 4)
        self.assertEqual(len(list(self.temp_root.glob("health_receipt_*.json"))), 4)
        self.assertTrue((self.temp_root / "slot_receipt_v1.json").is_file())

    def test_second_slot_rejects_altered_first_receipt_before_transport(self) -> None:
        first_root = self.temp_root / "first"
        clock = FakeClock(1786529700)
        run_slot(
            self.policy(), self.authority(), slot_index=1, raw_root=first_root,
            transport=FakeTransport(HEALTHY_RESPONSE_BYTES), now=clock.now, sleep=clock.sleep,
        )
        receipt_path = first_root / "slot_receipt_v1.json"
        receipt_path.write_text('{"terminal_state":"SLOT_TECHNICAL_HEALTHY"}', encoding="utf-8")
        transport = FailIfCalledTransport()
        second_clock = FakeClock(1786530600)

        with self.assertRaisesRegex(TwoSlotShakedownRuntimeError, "PRIOR_RECEIPT"):
            run_slot(
                self.policy(), self.authority(), slot_index=2, raw_root=self.temp_root / "second",
                transport=transport, now=second_clock.now, sleep=second_clock.sleep,
                prior_receipt=receipt_path,
            )
        self.assertEqual(transport.calls, 0)

    def test_second_slot_rejects_manifest_with_forged_contents_before_transport(self) -> None:
        first_root = self.temp_root / "first"
        clock = FakeClock(1786529700)
        run_slot(
            self.policy(), self.authority(), slot_index=1, raw_root=first_root,
            transport=FakeTransport(HEALTHY_RESPONSE_BYTES), now=clock.now, sleep=clock.sleep,
        )
        manifest_path = first_root / "raw_manifest_02.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["raw_files"] = []
        manifest_bytes = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
        manifest_path.write_bytes(manifest_bytes)
        manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
        health_path = first_root / "health_receipt_02.json"
        health = json.loads(health_path.read_text(encoding="utf-8"))
        health["raw_manifest_sha256"] = manifest_hash
        health_bytes = (json.dumps(health, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        health_path.write_bytes(health_bytes)
        receipt_path = first_root / "slot_receipt_v1.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["checkpoint_artifacts"][1]["manifest_sha256"] = manifest_hash
        receipt["checkpoint_artifacts"][1]["health_sha256"] = hashlib.sha256(health_bytes).hexdigest()
        receipt_path.write_text(json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        transport = FailIfCalledTransport()
        second_clock = FakeClock(1786530600)

        with self.assertRaisesRegex(TwoSlotShakedownRuntimeError, "PRIOR_RECEIPT"):
            run_slot(
                self.policy(), self.authority(), slot_index=2, raw_root=self.temp_root / "second",
                transport=transport, now=second_clock.now, sleep=second_clock.sleep,
                prior_receipt=receipt_path,
            )
        self.assertEqual(transport.calls, 0)

    def test_second_slot_rejects_rewritten_health_receipt_before_transport(self) -> None:
        first_root = self.temp_root / "first"
        clock = FakeClock(1786529700)
        run_slot(
            self.policy(), self.authority(), slot_index=1, raw_root=first_root,
            transport=FakeTransport(HEALTHY_RESPONSE_BYTES), now=clock.now, sleep=clock.sleep,
        )
        health_path = first_root / "health_receipt_03.json"
        health = json.loads(health_path.read_text(encoding="utf-8"))
        health["classification"] = "TYPED_GAP"
        health_path.write_text(json.dumps(health, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        transport = FailIfCalledTransport()
        second_clock = FakeClock(1786530600)

        with self.assertRaisesRegex(TwoSlotShakedownRuntimeError, "PRIOR_RECEIPT"):
            run_slot(
                self.policy(), self.authority(), slot_index=2, raw_root=self.temp_root / "second",
                transport=transport, now=second_clock.now, sleep=second_clock.sleep,
                prior_receipt=first_root / "slot_receipt_v1.json",
            )
        self.assertEqual(transport.calls, 0)

    def test_late_offset_stops_before_any_request(self) -> None:
        transport = FailIfCalledTransport()
        result = run_slot(
            self.policy(), self.authority(), slot_index=1, raw_root=self.temp_root,
            transport=transport, now=FakeClock(1786529716).now, sleep=FakeClock(1786529716).sleep,
        )

        self.assertEqual(result["terminal_state"], "STOP_RUN")
        self.assertEqual(result["stop_reason"], "LATE_OFFSET")
        self.assertEqual(transport.calls, 0)

    def test_invalid_interval_start_is_typed_gap_not_research_evidence(self) -> None:
        wrong_interval = HEALTHY_RESPONSE_BYTES.replace(b"1786528800", b"1786527900")
        clock = FakeClock(1786529700)
        result = run_slot(
            self.policy(), self.authority(), slot_index=1, raw_root=self.temp_root,
            transport=FakeTransport(wrong_interval), now=clock.now, sleep=clock.sleep,
        )

        self.assertEqual(result["terminal_state"], "SLOT_TECHNICAL_INCONCLUSIVE")
        self.assertFalse(result["claims"]["pit_admissible"])
        self.assertFalse(result["claims"]["h07_h01_evidence"])

    def test_transport_runtime_error_stops_without_a_second_request(self) -> None:
        transport = RuntimeErrorTransport()
        result = run_slot(
            self.policy(), self.authority(), slot_index=1, raw_root=self.temp_root,
            transport=transport, now=FakeClock(1786529700).now, sleep=FakeClock(1786529700).sleep,
        )

        self.assertEqual(result["terminal_state"], "STOP_RUN")
        self.assertEqual(transport.calls, 1)

    def test_cli_dry_run_emits_four_requests_and_creates_no_output(self) -> None:
        completed = subprocess.run(
            [
                sys.executable, "-B", str(SCRIPT_PATH), "--dry-run", "--slot-index", "1",
                "--authority", AUTHORITY_TEXT, "--now-epoch", "1786529670",
            ],
            cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["network_calls"], 0)
        self.assertFalse(payload["output_created"])
        self.assertEqual(len(payload["plan"]), 4)

    def test_cli_execute_without_exact_authority_fails_before_network_io(self) -> None:
        completed = subprocess.run(
            [
                sys.executable, "-B", str(SCRIPT_PATH), "--execute", "--slot-index", "1",
                "--authority", "not-an-authority", "--raw-root", str(self.temp_root),
            ],
            cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("AUTHORITY", completed.stderr)

    def test_policy_schema_is_closed_and_binds_the_zero_authority_default(self) -> None:
        policy = self.policy()
        jsonschema.validate(policy, json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))
        self.assertEqual(policy["authority"]["provider_api_rpc_wss_calls"], 0)
        self.assertFalse(policy["non_claims"]["external_capture_authorized"])

    def test_policy_validator_rejects_omitted_zero_authority_prohibition(self) -> None:
        unsafe = copy.deepcopy(self.policy())
        del unsafe["authority"]["provider_api_rpc_wss_calls"]

        with self.assertRaisesRegex(TwoSlotShakedownRuntimeError, "AUTHORITY"):
            run_slot(
                unsafe, self.authority(), slot_index=1, raw_root=self.temp_root,
                transport=FailIfCalledTransport(), now=FakeClock(1786529700).now, sleep=FakeClock(1786529700).sleep,
            )

    def test_offline_acceptance_binds_runtime_artifacts_and_zero_side_effects(self) -> None:
        receipt = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(receipt["validation_status"], "PASS_WITH_LIMITATIONS")
        self.assertEqual(receipt["factory_fit_review"], "FULL_REVIEW")
        self.assertEqual(receipt["state_change"], "NONE")
        self.assertEqual(receipt["project_sources_disposition"], "NO_CHANGE")
        self.assertEqual(receipt["side_effect_counters"]["provider_api_rpc_wss_calls"], 0)
        self.assertFalse(receipt["non_claims"]["twenty_four_hour_capture_authorized"])
        for name, path in ARTIFACT_PATHS.items():
            self.assertEqual(receipt["artifact_bindings"][name]["path"], path.relative_to(ROOT).as_posix())
            self.assertEqual(receipt["artifact_bindings"][name]["sha256"], sha256(path))

    def test_catalog_registers_all_eight_runtime_assets(self) -> None:
        catalog = load_yaml(CATALOG_CORE_PATH)
        records = catalog["records"]
        assert isinstance(records, list)
        asset_ids = {record["asset_id"] for record in records if isinstance(record, dict)}
        self.assertTrue(EXPECTED_A11C_ASSET_IDS.issubset(asset_ids))


if __name__ == "__main__":
    unittest.main()
