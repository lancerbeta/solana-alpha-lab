from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.ordinary_market_pit_local_raw_envelope import (
    PRODUCT_TERMINAL,
    LocalRawEnvelopeBindError,
    bind_local_raw_envelopes,
    load_local_raw_config,
)
from solana_alpha_lab.ordinary_market_pit_primary_x import (
    FACTORY_RUNNER,
    FACTORY_RUNNER_SHA256,
    PRIMARY_X_UNKNOWN,
    bind_git_retained_cells,
    load_bind_config,
)

SCRIPT = ROOT / "scripts/run_ordinary_market_pit_local_raw_envelope_bind.py"
FEATURE_CATALOG = ROOT / "registries/feature_catalog.yaml"
HYPOTHESES = ROOT / "registries/hypotheses.yaml"
RESEARCH_CYCLES = ROOT / "registries/research_cycles.yaml"
LOCAL_RAW_ROOT = ROOT / "local/quote_native_evidence_channel_qualification"
RECEIPT_PATH = (
    ROOT / "docs/evidence/ordinary_market_pit_local_raw_envelope_bind/a1_runtime_receipt_v1.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def _fixture_root() -> tempfile.TemporaryDirectory[str]:
    return tempfile.TemporaryDirectory()


class OrdinaryMarketPitLocalRawEnvelopeBindTests(unittest.TestCase):
    def test_git_frozen_cells_still_lack_mcap(self) -> None:
        config = load_bind_config(ROOT)
        result = bind_git_retained_cells(ROOT, config)
        self.assertEqual(result["mcap_key_count"], 0)
        self.assertEqual(result["primary_x_bound_count"], 0)

    def test_factory_runner_unchanged(self) -> None:
        self.assertEqual(sha256(ROOT / FACTORY_RUNNER), FACTORY_RUNNER_SHA256)

    def test_task28_skeletons_stay_empty(self) -> None:
        import yaml

        for path in (FEATURE_CATALOG, HYPOTHESES, RESEARCH_CYCLES):
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["records"], [])

    def test_fixture_envelopes_bind_without_leaking_raw_fields(self) -> None:
        with _fixture_root() as tmp:
            root = Path(tmp)
            recent = [
                {"id": "MintRecent111111111111111111111111111111111", "liquidity": 2000.0, "mcap": 10000.0, "fdv": 99999.0, "twitter": "x"}
            ]
            traded = [
                {"id": "MintTraded111111111111111111111111111111111", "liquidity": 4000.0, "mcap": 8000.0, "usdPrice": 1.2}
            ]
            recent_bytes = json.dumps(recent).encode("utf-8")
            traded_bytes = json.dumps(traded).encode("utf-8")
            recent_sha = hashlib.sha256(recent_bytes).hexdigest()
            traded_sha = hashlib.sha256(traded_bytes).hexdigest()
            run_dir = root / "local/quote_native_evidence_channel_qualification/run=fixture"
            run_dir.mkdir(parents=True)
            (run_dir / "DISCOVERY_RECENT.json").write_bytes(recent_bytes)
            (run_dir / "DISCOVERY_TRADED.json").write_bytes(traded_bytes)
            qualification = {
                "frozen_cells": [
                    {
                        "identity_id": "RECENT_1",
                        "mint": "MintRecent111111111111111111111111111111111",
                        "stratum": "RECENT",
                        "liquidity": 2000.0,
                    },
                    {
                        "identity_id": "TRADED_1",
                        "mint": "MintTraded111111111111111111111111111111111",
                        "stratum": "TRADED",
                        "liquidity": 4000.0,
                    },
                ],
                "raw_retention": {
                    "manifests": [
                        {
                            "observation_id": "DISCOVERY:RECENT",
                            "path": "run=fixture/DISCOVERY_RECENT.json",
                            "sha256": recent_sha,
                        },
                        {
                            "observation_id": "DISCOVERY:TRADED",
                            "path": "run=fixture/DISCOVERY_TRADED.json",
                            "sha256": traded_sha,
                        },
                    ]
                },
            }
            qual_path = root / "docs/evidence/qual.json"
            _write_json(qual_path, qualification)
            config = {
                "hypothesis_version": "HYP-ORDINARY-LIQUIDITY-COVERAGE-PIT-V1",
                "primary_x": {
                    "numerator_field": "liquidity",
                    "denominator_field": "mcap",
                    "forbidden_substitutes": ["fdv", "usdPrice", "circSupply", "totalSupply"],
                },
                "availability_class": "FORWARD_SNAPSHOT_NOT_PIT_READY",
                "raw_retention": "A4_OUTSIDE_GIT",
                "evidence_budget": {"provider_api_rpc_wss_calls": 0},
                "qualification_receipt": {
                    "path": "docs/evidence/qual.json",
                    "sha256": sha256(qual_path),
                },
                "local_raw_root": "local/quote_native_evidence_channel_qualification",
                "next_safe_action": "OFFLINE_N12_ASSOCIATION_OR_FRESH_SAMPLE_OWNER_CHOICE",
                "envelopes": [
                    {"observation_id": "DISCOVERY:RECENT", "stratum": "RECENT", "expected_sha256": recent_sha},
                    {"observation_id": "DISCOVERY:TRADED", "stratum": "TRADED", "expected_sha256": traded_sha},
                ],
            }
            (root / "src/solana_alpha_lab/factory").mkdir(parents=True)
            (root / FACTORY_RUNNER).write_bytes((ROOT / FACTORY_RUNNER).read_bytes())
            result = bind_local_raw_envelopes(root, config)
            self.assertEqual(result["product_terminal"], PRODUCT_TERMINAL)
            self.assertEqual(result["primary_x_bound_count"], 2)
            self.assertEqual(result["primary_x_unknown_count"], 0)
            self.assertEqual(result["git_frozen_cell_mcap_key_count"], 0)
            self.assertEqual(result["pit_ready_count"], 0)
            self.assertEqual(result["provider_api_rpc_wss_calls"], 0)
            self.assertAlmostEqual(result["rows"][0]["value"], 0.2)
            self.assertAlmostEqual(result["rows"][1]["value"], 0.5)
            for row in result["rows"]:
                self.assertNotIn("fdv", row)
                self.assertNotIn("twitter", row)
                self.assertNotIn("usdPrice", row)
                self.assertFalse(row["pit_ready"])

    def test_hash_mismatch_is_fail_closed(self) -> None:
        with _fixture_root() as tmp:
            root = Path(tmp)
            recent = [{"id": "MintA", "liquidity": 1.0, "mcap": 2.0}]
            traded = [{"id": "MintB", "liquidity": 3.0, "mcap": 4.0}]
            recent_bytes = json.dumps(recent).encode("utf-8")
            traded_bytes = json.dumps(traded).encode("utf-8")
            recent_sha = hashlib.sha256(recent_bytes).hexdigest()
            traded_sha = hashlib.sha256(traded_bytes).hexdigest()
            run_dir = root / "local/quote_native_evidence_channel_qualification/run=fixture"
            run_dir.mkdir(parents=True)
            (run_dir / "DISCOVERY_RECENT.json").write_bytes(b"[]")
            (run_dir / "DISCOVERY_TRADED.json").write_bytes(traded_bytes)
            qualification = {
                "frozen_cells": [
                    {"identity_id": "RECENT_1", "mint": "MintA", "stratum": "RECENT", "liquidity": 1.0},
                    {"identity_id": "TRADED_1", "mint": "MintB", "stratum": "TRADED", "liquidity": 3.0},
                ],
                "raw_retention": {
                    "manifests": [
                        {"observation_id": "DISCOVERY:RECENT", "path": "run=fixture/DISCOVERY_RECENT.json", "sha256": recent_sha},
                        {"observation_id": "DISCOVERY:TRADED", "path": "run=fixture/DISCOVERY_TRADED.json", "sha256": traded_sha},
                    ]
                },
            }
            qual_path = root / "docs/evidence/qual.json"
            _write_json(qual_path, qualification)
            config = {
                "hypothesis_version": "HYP-ORDINARY-LIQUIDITY-COVERAGE-PIT-V1",
                "primary_x": {
                    "numerator_field": "liquidity",
                    "denominator_field": "mcap",
                    "forbidden_substitutes": ["fdv", "usdPrice", "circSupply", "totalSupply"],
                },
                "availability_class": "FORWARD_SNAPSHOT_NOT_PIT_READY",
                "raw_retention": "A4_OUTSIDE_GIT",
                "evidence_budget": {"provider_api_rpc_wss_calls": 0},
                "qualification_receipt": {"path": "docs/evidence/qual.json", "sha256": sha256(qual_path)},
                "local_raw_root": "local/quote_native_evidence_channel_qualification",
                "envelopes": [
                    {"observation_id": "DISCOVERY:RECENT", "stratum": "RECENT", "expected_sha256": recent_sha},
                    {"observation_id": "DISCOVERY:TRADED", "stratum": "TRADED", "expected_sha256": traded_sha},
                ],
            }
            (root / "src/solana_alpha_lab/factory").mkdir(parents=True)
            (root / FACTORY_RUNNER).write_bytes((ROOT / FACTORY_RUNNER).read_bytes())
            with self.assertRaises(LocalRawEnvelopeBindError) as raised:
                bind_local_raw_envelopes(root, config)
            self.assertEqual(str(raised.exception), "LOCAL_RAW_HASH_MISMATCH")

    def test_fdv_only_item_stays_unknown(self) -> None:
        with _fixture_root() as tmp:
            root = Path(tmp)
            recent = [{"id": "MintA", "liquidity": 2000.0, "fdv": 50000.0}]
            traded = [{"id": "MintB", "liquidity": 4000.0, "mcap": 8000.0}]
            recent_bytes = json.dumps(recent).encode("utf-8")
            traded_bytes = json.dumps(traded).encode("utf-8")
            recent_sha = hashlib.sha256(recent_bytes).hexdigest()
            traded_sha = hashlib.sha256(traded_bytes).hexdigest()
            run_dir = root / "local/quote_native_evidence_channel_qualification/run=fixture"
            run_dir.mkdir(parents=True)
            (run_dir / "DISCOVERY_RECENT.json").write_bytes(recent_bytes)
            (run_dir / "DISCOVERY_TRADED.json").write_bytes(traded_bytes)
            qualification = {
                "frozen_cells": [
                    {"identity_id": "RECENT_1", "mint": "MintA", "stratum": "RECENT", "liquidity": 2000.0},
                    {"identity_id": "TRADED_1", "mint": "MintB", "stratum": "TRADED", "liquidity": 4000.0},
                ],
                "raw_retention": {
                    "manifests": [
                        {"observation_id": "DISCOVERY:RECENT", "path": "run=fixture/DISCOVERY_RECENT.json", "sha256": recent_sha},
                        {"observation_id": "DISCOVERY:TRADED", "path": "run=fixture/DISCOVERY_TRADED.json", "sha256": traded_sha},
                    ]
                },
            }
            qual_path = root / "docs/evidence/qual.json"
            _write_json(qual_path, qualification)
            config = {
                "hypothesis_version": "HYP-ORDINARY-LIQUIDITY-COVERAGE-PIT-V1",
                "primary_x": {
                    "numerator_field": "liquidity",
                    "denominator_field": "mcap",
                    "forbidden_substitutes": ["fdv", "usdPrice", "circSupply", "totalSupply"],
                },
                "availability_class": "FORWARD_SNAPSHOT_NOT_PIT_READY",
                "raw_retention": "A4_OUTSIDE_GIT",
                "evidence_budget": {"provider_api_rpc_wss_calls": 0},
                "qualification_receipt": {"path": "docs/evidence/qual.json", "sha256": sha256(qual_path)},
                "local_raw_root": "local/quote_native_evidence_channel_qualification",
                "next_safe_action": "OFFLINE_N12_ASSOCIATION_OR_FRESH_SAMPLE_OWNER_CHOICE",
                "envelopes": [
                    {"observation_id": "DISCOVERY:RECENT", "stratum": "RECENT", "expected_sha256": recent_sha},
                    {"observation_id": "DISCOVERY:TRADED", "stratum": "TRADED", "expected_sha256": traded_sha},
                ],
            }
            (root / "src/solana_alpha_lab/factory").mkdir(parents=True)
            (root / FACTORY_RUNNER).write_bytes((ROOT / FACTORY_RUNNER).read_bytes())
            result = bind_local_raw_envelopes(root, config)
            self.assertEqual(result["product_terminal"], "LOCAL_RAW_ENVELOPES_INCOMPLETE")
            self.assertEqual(result["rows"][0]["status"], PRIMARY_X_UNKNOWN)
            self.assertIsNone(result["rows"][0]["value"])
            self.assertTrue(result["rows"][0]["substitute_rejected"])
            self.assertEqual(result["primary_x_bound_count"], 1)

    def test_local_a4_recompute_matches_committed_receipt(self) -> None:
        if not LOCAL_RAW_ROOT.is_dir():
            self.skipTest("LOCAL_A4_ABSENT")
        config = load_local_raw_config(ROOT)
        result = bind_local_raw_envelopes(ROOT, config)
        committed = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(result["product_terminal"], PRODUCT_TERMINAL)
        self.assertEqual(result["primary_x_bound_count"], 12)
        self.assertEqual(result["primary_x_unknown_count"], 0)
        self.assertEqual(result["git_frozen_cell_mcap_key_count"], 0)
        self.assertEqual(committed["primary_x_bound_count"], 12)
        self.assertEqual(
            [(row["identity_id"], row["value"], row["mcap"]) for row in result["rows"]],
            [(row["identity_id"], row["value"], row["mcap"]) for row in committed["rows"]],
        )

    def test_cli_binds_local_envelopes_without_network(self) -> None:
        if not LOCAL_RAW_ROOT.is_dir():
            self.skipTest("LOCAL_A4_ABSENT")
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(ROOT)],
            check=False,
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["product_terminal"], PRODUCT_TERMINAL)
        self.assertEqual(payload["provider_api_rpc_wss_calls"], 0)
        self.assertEqual(payload["pit_ready_count"], 0)
        self.assertEqual(payload["primary_x_bound_count"], 12)


if __name__ == "__main__":
    unittest.main()
