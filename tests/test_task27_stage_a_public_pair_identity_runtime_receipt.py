from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "docs/contracts/task27_two_stage_identity_and_history_route_contract_v1.md"
CONFIG_PATH = ROOT / "configs/task27_two_stage_identity_and_history_route_contract_v1.yaml"
SOURCE_SMOKE_RECEIPT_PATH = ROOT / "docs/evidence/task27/a0a5r1_project_sources_activation_receipt_v1.json"
RECEIPT_PATH = ROOT / "docs/evidence/task27/a1_stage_a_public_pair_identity_runtime_receipt_v1.json"

EXPECTED_POOL_ADDRESS = "URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S"
EXPECTED_BASE_MINT = "DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK"
EXPECTED_QUOTE_MINT = "So11111111111111111111111111111111111111112"
EXPECTED_RAW_SHA256 = "327c332eedec6238cb1446c5d3b21189cb402892aec597bda86cb352496af11a"
EXPECTED_RAW_MANIFEST_SHA256 = "b98930a5efe653d77552778303e05a66e98ebc2314d5aafd1252e5038eb01475"
EXPECTED_PROJECTION_SHA256 = "2b8e3bd68d38f3c35c183a370816bdfb100e330adb599c00e94393f9fffb2f0a"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


class StageAPublicPairIdentityRuntimeReceiptTests(unittest.TestCase):
    def test_retained_identity_is_bound_to_one_allowed_get_without_raw_exposure(self) -> None:
        receipt = load_json(RECEIPT_PATH)

        self.assertEqual(receipt["schema"], "smial.task27.stage-a-public-pair-identity.runtime-receipt")
        self.assertEqual(receipt["task_id"], "TASK-27")
        self.assertEqual(receipt["atom_id"], "T27-A1_STAGE_A_PUBLIC_PAIR_IDENTITY_READ_V1")

        bindings = receipt["artifact_bindings"]
        self.assertEqual(bindings["contract"]["path"], CONTRACT_PATH.relative_to(ROOT).as_posix())
        self.assertEqual(bindings["contract"]["sha256"], sha256(CONTRACT_PATH))
        self.assertEqual(bindings["config"]["path"], CONFIG_PATH.relative_to(ROOT).as_posix())
        self.assertEqual(bindings["config"]["sha256"], sha256(CONFIG_PATH))
        self.assertEqual(
            bindings["source_smoke_receipt"]["path"],
            SOURCE_SMOKE_RECEIPT_PATH.relative_to(ROOT).as_posix(),
        )
        self.assertEqual(bindings["source_smoke_receipt"]["sha256"], sha256(SOURCE_SMOKE_RECEIPT_PATH))

        request = receipt["request"]
        self.assertEqual(request["provider"], "DEXSCREENER_PUBLIC_PAIR_IDENTITY")
        self.assertEqual(request["request_id"], "T27-A1R1-STAGE-A-IDENTITY-001")
        self.assertEqual(request["method"], "GET")
        self.assertEqual(
            request["url"],
            "https://api.dexscreener.com/latest/dex/pairs/solana/URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S",
        )
        self.assertEqual(request["request_count"], 1)
        self.assertEqual(request["retries"], 0)
        self.assertFalse(request["redirect_followed"])
        self.assertEqual(request["http_status"], 200)

        identity = receipt["identity"]
        self.assertEqual(
            identity,
            {
                "network": "solana",
                "pool_address": EXPECTED_POOL_ADDRESS,
                "base_mint": EXPECTED_BASE_MINT,
                "quote_mint": EXPECTED_QUOTE_MINT,
                "dex_id": "pumpswap",
            },
        )

        raw_evidence = receipt["raw_evidence"]
        self.assertTrue(raw_evidence["outside_git"])
        self.assertEqual(raw_evidence["raw_sha256"], EXPECTED_RAW_SHA256)
        self.assertEqual(raw_evidence["raw_manifest_sha256"], EXPECTED_RAW_MANIFEST_SHA256)
        self.assertEqual(raw_evidence["identity_projection_sha256"], EXPECTED_PROJECTION_SHA256)
        self.assertEqual(raw_evidence["retention"], "RETAIN_WITH_DEPENDENT_RESEARCH_AND_HASHES")

        authority = receipt["authority"]
        self.assertEqual(authority["provider_api_rpc_wss_calls"], 1)
        self.assertFalse(authority["credential_use"])
        self.assertEqual(authority["r2_value_reads"], 0)
        self.assertEqual(authority["r3_value_or_path_reads"], 0)
        self.assertEqual(authority["wallet_signer_transaction_actions"], 0)
        self.assertEqual(authority["cash_spend_usd_cents"], 0)
        self.assertFalse(authority["stage_b_authorized"])
        self.assertFalse(authority["task27_acceptance"])

        self.assertEqual(receipt["decision"]["stage_a_state"], "FROZEN_BASE_MINT_AND_POOL_IDENTITY")
        self.assertEqual(receipt["decision"]["history_grade"], "NO_HISTORY_COLLECTED")
        self.assertEqual(receipt["decision"]["state_change"], "NONE")

        serialized = json.dumps(receipt, sort_keys=True).lower()
        for forbidden_marker in ("raw_json", "private_key", "seed", "api-key", "api_key", "authorization"):
            with self.subTest(forbidden_marker=forbidden_marker):
                self.assertNotIn(forbidden_marker, serialized)


if __name__ == "__main__":
    unittest.main()
