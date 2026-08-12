from __future__ import annotations

import json
import hashlib
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

from solana_alpha_lab.lifecycle_discovery_transport import HttpCapture


CONFIG_PATH = ROOT / "configs/task30_pool_activity_discriminator_v1.yaml"
MODULE_PATH = ROOT / "src/solana_alpha_lab/task30_pool_activity_discriminator_runtime.py"
SCRIPT_PATH = ROOT / "scripts/run_task30_pool_activity_discriminator.py"
TEST_PATH = ROOT / "tests/test_task30_pool_activity_discriminator_runtime.py"
RECEIPT_PATH_V1 = ROOT / "docs/evidence/task30/a16p_pool_activity_discriminator_runtime_receipt_v1.json"
RECEIPT_PATH_V2 = ROOT / "docs/evidence/task30/a16p_pool_activity_discriminator_runtime_receipt_v2.json"
CATALOG_PATH = ROOT / "catalog/assets/core.yaml"
AUTHORITY = (
    "T30-A16P_POOL_ACTIVITY_DISCRIMINATOR_RUNTIME_V1; "
    "pool=URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S; "
    "provider=HELIUS_STANDARD_RPC; method=getSignaturesForAddress; "
    "capture_started_at=2026-08-12T09:27:52.749910Z; "
    "capture_terminal_at=2026-08-12T09:37:53.059095Z; "
    "max_requests=1; limit=1000; commitment=confirmed; "
    "estimated_credit_cap=1; retention=A4; retry=false; fallback=false; "
    "transaction_followups=0"
)
AUTHORITY_V2 = AUTHORITY.replace("RUNTIME_V1", "RUNTIME_V2")


class PoolActivityDiscriminatorRuntimeTests(unittest.TestCase):
    def test_second_owner_gate_uses_distinct_immutable_root(self) -> None:
        from solana_alpha_lab.task30_pool_activity_discriminator_runtime import (
            execute_pool_activity_attempt,
        )

        config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        response = {
            "jsonrpc": "2.0",
            "id": "task30-a16-pool-activity-discriminator",
            "result": [],
        }
        with tempfile.TemporaryDirectory() as temporary:
            repository_root = Path(temporary).resolve()
            receipt = execute_pool_activity_attempt(
                config,
                authority_phrase=AUTHORITY_V2,
                execution_profile="v2",
                repository_root=repository_root,
                raw_root=repository_root / "local/task30_pool_activity_discriminator_v2",
                route_preflight=lambda: {"dns_resolved": True, "tcp_443": True},
                credential_loader=lambda name: "test-helius-secret",
                http_exchange=lambda request, max_response_bytes: HttpCapture(
                    status_code=200,
                    body=json.dumps(response, separators=(",", ":")).encode(),
                    response_url="https://mainnet.helius-rpc.com/?api-key=<redacted>",
                ),
                clock=lambda: datetime(2026, 8, 12, 20, 30, tzinfo=UTC),
                nonce_factory=lambda: "fedcba98",
            )
        self.assertTrue(
            receipt["logical_run_root"].startswith(
                "local/task30_pool_activity_discriminator_v2/run="
            )
        )

    def test_runtime_receipt_is_hash_bound_and_catalogued(self) -> None:
        receipt = json.loads(RECEIPT_PATH_V1.read_text(encoding="utf-8"))
        self.assertEqual(
            receipt["decision"]["value"],
            "ATTEMPT_NOT_DECISION_USABLE_NETWORK_FAILURE",
        )
        self.assertEqual(receipt["run"]["request_count"], 1)
        self.assertEqual(receipt["run"]["transport_terminal_class"], "DNS_OR_TLS")
        self.assertTrue(receipt["post_failure_route_preflight"]["dns_resolved"])
        self.assertTrue(receipt["post_failure_route_preflight"]["tcp_443"])
        self.assertFalse(receipt["non_claims"]["pool_inactive"])
        self.assertFalse(receipt["non_claims"]["pool_activity"])
        self.assertEqual(receipt["factory_fit_review"]["scope"], "FULL_REVIEW")
        self.assertEqual(receipt["project_sources_disposition"]["kind"], "NO_CHANGE")
        success = json.loads(RECEIPT_PATH_V2.read_text(encoding="utf-8"))
        self.assertEqual(success["decision"]["value"], "NO_DIRECT_POOL_ACTIVITY_SUPPORTED")
        self.assertEqual(success["run"]["request_count"], 1)
        self.assertEqual(success["run"]["http_status"], 200)
        self.assertEqual(success["coverage"]["result_count"], 1000)
        self.assertTrue(success["coverage"]["page_brackets_acknowledgement_floor"])
        self.assertEqual(success["coverage"]["interior_signature_count"], 0)
        self.assertTrue(success["decision"]["a15p_no_notification_explained"])
        self.assertFalse(success["non_claims"]["pool_inactive"])
        self.assertFalse(success["non_claims"]["no_trades"])
        self.assertEqual(success["project_sources_disposition"]["kind"], "NO_CHANGE")
        for key, path in {
            "module": MODULE_PATH,
            "script": SCRIPT_PATH,
            "test": TEST_PATH,
        }.items():
            self.assertEqual(
                receipt["artifact_bindings"][key]["sha256"],
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        catalog = yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8"))
        ids = {item["asset_id"] for item in catalog["records"]}
        self.assertTrue(
            {
                "MODULE-T30-POOL-ACTIVITY-DISCRIMINATOR-RUNTIME-001",
                "SCRIPT-T30-POOL-ACTIVITY-DISCRIMINATOR-RUNTIME-001",
                "TEST-T30-POOL-ACTIVITY-DISCRIMINATOR-RUNTIME-001",
                "EVIDENCE-T30-A16P-POOL-ACTIVITY-DISCRIMINATOR-RUNTIME-001",
                "EVIDENCE-T30-A16P-POOL-ACTIVITY-DISCRIMINATOR-RUNTIME-002",
            }.issubset(ids)
        )

    def test_one_bound_request_is_retained_and_classified(self) -> None:
        try:
            from solana_alpha_lab.task30_pool_activity_discriminator_runtime import (
                execute_pool_activity_attempt,
            )
        except ModuleNotFoundError:
            self.fail("runtime adapter is missing")

        config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        calls: list[object] = []
        retention_sentinel = "unit-test-marker"
        response = {
            "jsonrpc": "2.0",
            "id": "task30-a16-pool-activity-discriminator",
            "result": [
                {
                    "signature": "1" * 64,
                    "slot": 10,
                    "err": None,
                    "memo": None,
                    "blockTime": 1786527000,
                    "confirmationStatus": "confirmed",
                }
            ],
        }

        def exchange(request: object, *, max_response_bytes: int) -> HttpCapture:
            calls.append(request)
            self.assertEqual(max_response_bytes, 2_000_000)
            return HttpCapture(
                status_code=200,
                body=json.dumps(response, separators=(",", ":")).encode("utf-8"),
                response_url="https://mainnet.helius-rpc.com/?api-key=<redacted>",
            )

        with tempfile.TemporaryDirectory() as temporary:
            repository_root = Path(temporary).resolve()
            raw_root = repository_root / "local/task30_pool_activity_discriminator"
            receipt = execute_pool_activity_attempt(
                config,
                authority_phrase=AUTHORITY,
                repository_root=repository_root,
                raw_root=raw_root,
                route_preflight=lambda: {"dns_resolved": True, "tcp_443": True},
                credential_loader=lambda name: retention_sentinel,
                http_exchange=exchange,
                clock=lambda: datetime(2026, 8, 12, 20, 0, tzinfo=UTC),
                nonce_factory=lambda: "01234567",
            )

            self.assertEqual(len(calls), 1)
            self.assertEqual(receipt["request_count"], 1)
            self.assertEqual(
                receipt["terminal_state"],
                "POOL_ADDRESS_ACTIVITY_OBSERVED_ROUTE_REVIEW_REQUIRED",
            )
            self.assertEqual(receipt["raw_retention"], "A4_EXACT_RETAINED")
            run_root = repository_root / receipt["logical_run_root"]
            self.assertTrue((run_root / "raw_response.json").is_file())
            self.assertTrue((run_root / "raw_manifest.json").is_file())
            self.assertTrue((run_root / "terminal_receipt.json").is_file())
            retained = b"".join(path.read_bytes() for path in run_root.iterdir())
            self.assertNotIn(retention_sentinel.encode("utf-8"), retained)

    def test_transport_failure_cannot_promote_plausible_body(self) -> None:
        from solana_alpha_lab.task30_pool_activity_discriminator_runtime import (
            execute_pool_activity_attempt,
        )

        config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        plausible = {
            "jsonrpc": "2.0",
            "id": "task30-a16-pool-activity-discriminator",
            "result": [
                {
                    "signature": "1" * 64,
                    "slot": 10,
                    "err": None,
                    "memo": None,
                    "blockTime": 1786527000,
                    "confirmationStatus": "confirmed",
                }
            ],
        }

        def failed_exchange(request: object, *, max_response_bytes: int) -> HttpCapture:
            return HttpCapture(
                status_code=None,
                body=json.dumps(plausible, separators=(",", ":")).encode("utf-8"),
                response_url="https://mainnet.helius-rpc.com/?api-key=<redacted>",
                terminal_class="DNS_OR_TLS",
                error_class="http_connection_failed",
            )

        with tempfile.TemporaryDirectory() as temporary:
            repository_root = Path(temporary).resolve()
            receipt = execute_pool_activity_attempt(
                config,
                authority_phrase=AUTHORITY,
                repository_root=repository_root,
                raw_root=repository_root / "local/task30_pool_activity_discriminator",
                route_preflight=lambda: {"dns_resolved": True, "tcp_443": True},
                credential_loader=lambda name: "test-helius-secret",
                http_exchange=failed_exchange,
                clock=lambda: datetime(2026, 8, 12, 20, 0, tzinfo=UTC),
                nonce_factory=lambda: "89abcdef",
            )

        self.assertEqual(receipt["terminal_state"], "MALFORMED_OR_RPC_ERROR_UNKNOWN")
        self.assertFalse(receipt["pool_address_activity_observed"])

    def test_failed_keyless_preflight_does_not_consume_owner_gate(self) -> None:
        from solana_alpha_lab.task30_pool_activity_discriminator_runtime import (
            PoolActivityRuntimeError,
            execute_pool_activity_attempt,
        )

        config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        credential_reads = 0
        network_calls = 0

        def credential_loader(name: str) -> str:
            nonlocal credential_reads
            credential_reads += 1
            return "test-helius-secret"

        def exchange(request: object, *, max_response_bytes: int) -> HttpCapture:
            nonlocal network_calls
            network_calls += 1
            raise AssertionError("RPC must not run after failed preflight")

        with tempfile.TemporaryDirectory() as temporary:
            repository_root = Path(temporary).resolve()
            raw_root = repository_root / "local/task30_pool_activity_discriminator"
            with self.assertRaisesRegex(
                PoolActivityRuntimeError, "ROUTE_PREFLIGHT_FAILED_NO_ATTEMPT"
            ):
                execute_pool_activity_attempt(
                    config,
                    authority_phrase=AUTHORITY,
                    repository_root=repository_root,
                    raw_root=raw_root,
                    route_preflight=lambda: {"dns_resolved": False, "tcp_443": False},
                    credential_loader=credential_loader,
                    http_exchange=exchange,
                    clock=lambda: datetime(2026, 8, 12, 20, 0, tzinfo=UTC),
                    nonce_factory=lambda: "01234567",
                )
            self.assertFalse(raw_root.exists())
        self.assertEqual(credential_reads, 0)
        self.assertEqual(network_calls, 0)


if __name__ == "__main__":
    unittest.main()
