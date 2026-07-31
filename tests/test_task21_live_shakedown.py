from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.jupiter_quote_transport import HttpCapture  # noqa: E402
from solana_alpha_lab.task21_forward_collector import (  # noqa: E402
    _synthetic_observation,
)
from solana_alpha_lab.task21_live_shakedown import (  # noqa: E402
    ATOM_ID,
    EXTERNAL_AUTHORITY_PHRASE,
    MIN_FREE_SPACE_AFTER_WRITE,
    Task21ExternalAuthorityRequired,
    Task21LiveExecutionGate,
    Task21LiveShakedownError,
    run_live_shakedown,
    validate_contract,
    validate_recovery_freshness,
)

CONFIG = ROOT / "configs/task21_live_shakedown_v1.yaml"
RECOVERY = ROOT / "docs/evidence/task21/runtime_recovery_gate_receipt_v1.json"
ACCEPTANCE = (
    ROOT / "docs/evidence/task21/live_shakedown_acceptance_receipt_v1.json"
)
FIXED_NOW = datetime(2026, 7, 30, 10, 0, tzinfo=UTC)


class FakeTransport:
    def __init__(self) -> None:
        self._attempts = 0
        self._received_bytes = 0

    @property
    def attempts(self) -> int:
        return self._attempts

    @property
    def received_bytes(self) -> int:
        return self._received_bytes

    def execute(self, request):
        self._attempts += 1
        observation = _synthetic_observation(
            request,
            requested_at=FIXED_NOW
            + timedelta(milliseconds=self._attempts * 20),
            sequence=self._attempts,
            late=False,
        )
        received = len(
            json.dumps(
                observation.response_body,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        self._received_bytes += received
        return HttpCapture(
            observation=observation,
            received_bytes=received,
            transport_stop_reason=None,
        )


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Task21LiveShakedownTests(unittest.TestCase):
    def test_contract_resolves_frozen_inputs_and_exact_caps(self) -> None:
        config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
        validate_contract(config, ROOT)
        self.assertEqual(config["atom_id"], ATOM_ID)
        for item in config["frozen_inputs"]:
            self.assertEqual(digest(ROOT / item["path"]), item["sha256"])
        self.assertEqual(config["run"]["provider_calls_max"], 8)
        self.assertEqual(config["run"]["modeled_provider_credits_max"], 8)
        self.assertEqual(config["run"]["cash_spend_usd_cents"], 0)
        self.assertEqual(config["run"]["credentials"], 0)

    def test_current_provider_readback_is_keyless_but_superseded(self) -> None:
        config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
        provider = config["official_provider_readback"]
        self.assertEqual(provider["base_url"], "https://api.jup.ag")
        self.assertEqual(provider["path"], "/swap/v1/quote")
        self.assertTrue(provider["keyless_allowed"])
        self.assertEqual(provider["keyless_rate_limit_rps"], 0.5)
        self.assertEqual(
            provider["current_status"],
            "AVAILABLE_SUPERSEDED_NOT_ACTIVELY_MAINTAINED",
        )

    def test_external_gate_is_exact(self) -> None:
        with self.assertRaisesRegex(
            Task21ExternalAuthorityRequired, "phrase_mismatch"
        ):
            Task21LiveExecutionGate("WRONG")
        self.assertEqual(
            Task21LiveExecutionGate(
                EXTERNAL_AUTHORITY_PHRASE
            ).authority_phrase,
            EXTERNAL_AUTHORITY_PHRASE,
        )

    def test_recovery_freshness_passes_and_stale_values_fail(self) -> None:
        receipt = json.loads(RECOVERY.read_text(encoding="utf-8"))
        validate_recovery_freshness(receipt, now=FIXED_NOW)
        stale = copy.deepcopy(receipt)
        stale["health"]["last_successful_backup_at"] = (
            FIXED_NOW - timedelta(hours=25)
        ).isoformat().replace("+00:00", "Z")
        with self.assertRaisesRegex(Task21LiveShakedownError, "backup_stale"):
            validate_recovery_freshness(stale, now=FIXED_NOW)
        unhealthy = copy.deepcopy(receipt)
        unhealthy["health"]["health_state"] = "DEGRADED"
        with self.assertRaisesRegex(Task21LiveShakedownError, "unhealthy"):
            validate_recovery_freshness(unhealthy, now=FIXED_NOW)

    def test_offline_fake_transport_completes_one_isolated_window(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            for item in yaml.safe_load(
                CONFIG.read_text(encoding="utf-8")
            )["frozen_inputs"]:
                target = repo / item["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / item["path"]).read_bytes())
            config_target = repo / "configs/task21_live_shakedown_v1.yaml"
            config_target.parent.mkdir(parents=True, exist_ok=True)
            config_target.write_bytes(CONFIG.read_bytes())
            recovery_target = (
                repo / "docs/evidence/task21/runtime_recovery_gate_receipt_v1.json"
            )
            receipt = run_live_shakedown(
                gate=Task21LiveExecutionGate(EXTERNAL_AUTHORITY_PHRASE),
                repo_root=repo,
                config_path=config_target,
                recovery_receipt_path=recovery_target,
                transport_factory=FakeTransport,
                now=lambda: FIXED_NOW,
                available_disk_bytes=10 * 1024 * 1024 * 1024,
            )
            self.assertEqual(receipt["status"], "COMPLETE")
            self.assertEqual(receipt["provider_api_rpc_wss_calls"], 8)
            self.assertEqual(receipt["modeled_provider_credits"], 8)
            self.assertTrue(receipt["technical_probe_only"])
            self.assertEqual(receipt["task21_watchlist_members_created"], 0)
            self.assertEqual(receipt["real_candidate_admissions"], 0)
            self.assertEqual(receipt["forward_dataset_rows"], 0)
            self.assertEqual(receipt["cash_spend_usd_cents"], 0)
            self.assertTrue(
                (
                    repo
                    / "local/task21_collector/live_shakedown"
                    / "task21_live_shakedown_v1"
                    / "window=T21-A5-WINDOW-01"
                    / "manifest.json"
                ).is_file()
            )

    def test_disk_pressure_and_existing_output_block_before_transport(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
            for item in config["frozen_inputs"]:
                target = repo / item["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / item["path"]).read_bytes())
            config_target = repo / "configs/task21_live_shakedown_v1.yaml"
            config_target.parent.mkdir(parents=True, exist_ok=True)
            config_target.write_bytes(CONFIG.read_bytes())
            recovery_target = (
                repo / "docs/evidence/task21/runtime_recovery_gate_receipt_v1.json"
            )
            with self.assertRaisesRegex(
                Task21LiveShakedownError, "disk_pressure"
            ):
                run_live_shakedown(
                    gate=Task21LiveExecutionGate(EXTERNAL_AUTHORITY_PHRASE),
                    repo_root=repo,
                    config_path=config_target,
                    recovery_receipt_path=recovery_target,
                    transport_factory=FakeTransport,
                    now=lambda: FIXED_NOW,
                    available_disk_bytes=MIN_FREE_SPACE_AFTER_WRITE,
                )
            existing = (
                repo
                / "local/task21_collector/live_shakedown"
                / "task21_live_shakedown_v1"
                / "window=T21-A5-WINDOW-01"
            )
            existing.mkdir(parents=True)
            with self.assertRaisesRegex(
                Task21LiveShakedownError, "output_already_exists"
            ):
                run_live_shakedown(
                    gate=Task21LiveExecutionGate(EXTERNAL_AUTHORITY_PHRASE),
                    repo_root=repo,
                    config_path=config_target,
                    recovery_receipt_path=recovery_target,
                    transport_factory=FakeTransport,
                    now=lambda: FIXED_NOW,
                    available_disk_bytes=10 * 1024 * 1024 * 1024,
                )

    def test_future_atom_and_external_actions_remain_separate(self) -> None:
        config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
        external = config["external_authority_required"]
        self.assertFalse(external["authorized"])
        self.assertEqual(external["proposed_caps"]["drive_reads"], 0)
        self.assertEqual(external["proposed_caps"]["drive_writes"], 0)
        self.assertEqual(external["proposed_caps"]["credential_use"], 0)
        self.assertEqual(
            external["proposed_caps"]["real_candidate_admissions"], 0
        )
        self.assertEqual(
            external["proposed_caps"]["forward_dataset_writes"], 0
        )
        self.assertEqual(
            config["next_atom"]["atom_id"],
            "T21-A6_SUSTAINED_FORWARD_COLLECTION_AND_MONITORING_V1",
        )
        self.assertFalse(config["next_atom"]["authorized_by_atom5"])

    def test_tracked_acceptance_receipt_matches_exact_live_evidence(self) -> None:
        receipt = json.loads(ACCEPTANCE.read_text(encoding="utf-8"))
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(
            receipt["verdict"],
            "LIVE_TRANSPORT_AND_CREATE_ONLY_DURABILITY_COMPATIBLE",
        )
        for artifact in receipt["frozen_artifacts"].values():
            self.assertEqual(digest(ROOT / artifact["path"]), artifact["sha256"])
        runtime = receipt["runtime"]
        self.assertEqual(runtime["execution_count"], 1)
        self.assertEqual(runtime["provider_api_rpc_wss_calls"], 8)
        self.assertEqual(runtime["modeled_provider_credits"], 8)
        self.assertEqual(runtime["raw_rows"], 8)
        self.assertEqual(runtime["terminal_counts"], {"QUOTE_AVAILABLE": 8})
        self.assertEqual(runtime["cash_spend_usd_cents"], 0)
        self.assertEqual(runtime["credentials_used"], 0)
        self.assertEqual(runtime["drive_reads"], 0)
        self.assertEqual(runtime["drive_writes"], 0)
        self.assertEqual(runtime["wallet_signer_transaction_actions"], 0)
        self.assertFalse(runtime["auto_escalated_to_atom6"])
        probe = receipt["technical_probe"]
        self.assertEqual(probe["task21_watchlist_members_created"], 0)
        self.assertEqual(probe["real_candidate_admissions"], 0)
        self.assertEqual(probe["forward_dataset_rows"], 0)
        self.assertFalse(
            receipt["next_atom"]["authorized_by_atom5"]
        )


if __name__ == "__main__":
    unittest.main()
