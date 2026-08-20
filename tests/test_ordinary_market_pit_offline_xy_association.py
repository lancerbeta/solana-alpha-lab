from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.ordinary_market_pit_offline_xy_association import (
    FAMILY_DECISION,
    MIN_STRATUM_N,
    PRODUCT_TERMINAL,
    Y_FIELD,
    OfflineXyAssociationError,
    associate_offline_xy,
    kendall_comparable,
    load_association_config,
)
from solana_alpha_lab.ordinary_market_pit_primary_x import (
    FACTORY_RUNNER,
    FACTORY_RUNNER_SHA256,
)

FEATURE_CATALOG = ROOT / "registries/feature_catalog.yaml"
HYPOTHESES = ROOT / "registries/hypotheses.yaml"
RESEARCH_CYCLES = ROOT / "registries/research_cycles.yaml"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def _write_yaml(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _bind_row(identity: str, stratum: str, value: float, status: str = "PRIMARY_X_BOUND") -> dict[str, object]:
    return {
        "identity_id": identity,
        "mint": f"Mint{identity}",
        "stratum": stratum,
        "status": status,
        "value": value,
    }


def _cell(
    identity: str,
    y_status: str,
    y_value: object,
    friction: object = "-0.01",
    y_equals_x: object = False,
) -> dict[str, object]:
    return {
        "identity_id": identity,
        "x_quoted_roundtrip_friction": friction,
        "x_status": "OBSERVED" if friction is not None else "MISSING",
        "y_quoted_liquidation_recovery": y_value,
        "y_status": y_status,
        "y_equals_x": y_equals_x,
    }


def _config_text(x_sha: str, y_sha: str) -> str:
    return (
        "schema: smial.ordinary-market-pit-offline-xy-association\n"
        "schema_version: '1.0'\n"
        "association_id: ORDINARY-MARKET-PIT-OFFLINE-XY-ASSOCIATION-001\n"
        "as_of: '2026-08-20'\n"
        "hypothesis_version: HYP-ORDINARY-LIQUIDITY-COVERAGE-PIT-V1\n"
        "y_field: y_quoted_liquidation_recovery\n"
        "forbidden_y_fields: [x_quoted_roundtrip_friction]\n"
        "y_source_atom_id: QUOTE_NATIVE_EVIDENCE_CHANNEL_QUALIFICATION_V1\n"
        "y_horizon_seconds: 900\n"
        "min_stratum_n: 6\n"
        "availability_class: FORWARD_SNAPSHOT_NOT_PIT_READY\n"
        "family_decision: DEFER_FRESH_PIT_CAPTURE\n"
        "product_terminal: EXPLORATORY_ASSOCIATION_NOT_PIT\n"
        "x_receipt:\n"
        "  path: x.json\n"
        f"  sha256: {x_sha}\n"
        "y_receipt:\n"
        "  path: y.json\n"
        f"  sha256: {y_sha}\n"
        "next_safe_action: OWNER_BOUNDED_FRESH_PIT_CAPTURE\n"
    )


class OrdinaryMarketPitOfflineXyAssociationTests(unittest.TestCase):
    def test_factory_runner_unchanged(self) -> None:
        self.assertEqual(sha256(ROOT / FACTORY_RUNNER), FACTORY_RUNNER_SHA256)

    def test_task28_skeletons_stay_empty(self) -> None:
        import yaml

        for path in (FEATURE_CATALOG, HYPOTHESES, RESEARCH_CYCLES):
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["records"], [])

    def test_kendall_perfect_positive(self) -> None:
        rank = kendall_comparable(
            [Decimal("1"), Decimal("2"), Decimal("3")],
            [Decimal("10"), Decimal("20"), Decimal("30")],
        )
        self.assertEqual(rank["hint"], "EXPLORATORY_POSITIVE")
        self.assertEqual(rank["tau"], "1")

    def test_missing_y_is_not_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bind = {
                "product_terminal": "LOCAL_RAW_ENVELOPES_BIND_PRIMARY_X",
                "rows": [
                    _bind_row("RECENT_1", "RECENT", 0.9),
                    _bind_row("RECENT_2", "RECENT", 0.8),
                    _bind_row("TRADED_1", "TRADED", 0.7),
                    _bind_row("TRADED_2", "TRADED", 0.6),
                    _bind_row("TRADED_3", "TRADED", 0.5),
                    _bind_row("TRADED_4", "TRADED", 0.4),
                    _bind_row("TRADED_5", "TRADED", 0.3),
                    _bind_row("TRADED_6", "TRADED", 0.2),
                ],
            }
            qual = {
                "atom_id": "QUOTE_NATIVE_EVIDENCE_CHANNEL_QUALIFICATION_V1",
                "panel_started_at": "2026-08-18T12:43:07Z",
                "campaign": {
                    "cells": [
                        _cell("RECENT_1", "MISSING", None, y_equals_x=None),
                        _cell("RECENT_2", "OBSERVED", "-0.03"),
                        _cell("TRADED_1", "OBSERVED", "-0.01"),
                        _cell("TRADED_2", "OBSERVED", "-0.02"),
                        _cell("TRADED_3", "OBSERVED", "-0.03"),
                        _cell("TRADED_4", "OBSERVED", "-0.04"),
                        _cell("TRADED_5", "OBSERVED", "-0.05"),
                        _cell("TRADED_6", "OBSERVED", "-0.06"),
                    ]
                }
            }
            x_path = root / "x.json"
            y_path = root / "y.json"
            _write_json(x_path, bind)
            _write_json(y_path, qual)
            _write_yaml(
                root / "configs/ordinary_market_pit_offline_xy_association_v1.yaml",
                _config_text(sha256(x_path), sha256(y_path)),
            )
            result = associate_offline_xy(root)
            recent_1 = next(row for row in result["rows"] if row["identity_id"] == "RECENT_1")
            self.assertEqual(recent_1["join_status"], "X_BOUND_Y_MISSING")
            self.assertIsNone(recent_1["y_value"])
            self.assertNotEqual(recent_1["y_value"], "0")
            self.assertEqual(result["complete_xy_count"], 7)
            self.assertEqual(result["strata"]["RECENT"]["status"], "INCONCLUSIVE_STRATUM")
            self.assertEqual(result["strata"]["TRADED"]["status"], "EXPLORATORY_RANK_COMPUTED")
            self.assertEqual(result["family_decision"], FAMILY_DECISION)
            self.assertFalse(any(row["pit_ready"] for row in result["rows"]))
            self.assertNotEqual(result["rows"][0]["y_field"], "x_quoted_roundtrip_friction")
            self.assertEqual(result["y_field"], Y_FIELD)

    def test_wrong_y_field_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = root / "configs/ordinary_market_pit_offline_xy_association_v1.yaml"
            _write_yaml(
                cfg,
                _config_text("0" * 64, "0" * 64).replace(
                    "y_field: y_quoted_liquidation_recovery",
                    "y_field: x_quoted_roundtrip_friction",
                ),
            )
            with self.assertRaises(OfflineXyAssociationError):
                load_association_config(root)

    def test_git_receipts_join_quoted_subset_not_n12_panel(self) -> None:
        config = load_association_config(ROOT)
        result = associate_offline_xy(ROOT, config)
        self.assertEqual(result["product_terminal"], PRODUCT_TERMINAL)
        self.assertEqual(result["family_decision"], FAMILY_DECISION)
        self.assertEqual(result["cell_count"], 12)
        self.assertEqual(result["complete_xy_count"], 10)
        self.assertEqual(result["y_missing_identities"], ["RECENT_1", "RECENT_4"])
        self.assertEqual(result["strata"]["RECENT"]["n_complete"], 4)
        self.assertLess(result["strata"]["RECENT"]["n_complete"], MIN_STRATUM_N)
        self.assertEqual(result["strata"]["RECENT"]["status"], "INCONCLUSIVE_STRATUM")
        self.assertEqual(result["strata"]["TRADED"]["n_complete"], 6)
        self.assertEqual(result["strata"]["TRADED"]["n_rankable"], 6)
        self.assertEqual(result["strata"]["TRADED"]["n_y_equals_x_excluded"], 0)
        self.assertEqual(result["strata"]["TRADED"]["status"], "EXPLORATORY_RANK_COMPUTED")
        self.assertEqual(result["strata"]["TRADED"]["concordant_pairs"], 5)
        self.assertEqual(result["strata"]["TRADED"]["discordant_pairs"], 10)
        self.assertEqual(result["strata"]["TRADED"]["hint"], "EXPLORATORY_NEGATIVE")
        self.assertEqual(result["combined"]["n_complete"], 10)
        self.assertEqual(result["combined"]["n_rankable"], 8)
        self.assertEqual(result["combined"]["n_y_equals_x_excluded"], 2)
        self.assertEqual(result["y_equals_x_count"], 2)
        self.assertEqual(result["y_source_atom_id"], "QUOTE_NATIVE_EVIDENCE_CHANNEL_QUALIFICATION_V1")
        self.assertEqual(result["clock_alignment"], "SAME_CAPTURE_WINDOW_NOT_INDEPENDENT_PIT")
        equals = [row["identity_id"] for row in result["rows"] if row.get("y_equals_x") is True]
        self.assertEqual(equals, ["RECENT_5", "RECENT_6"])
        self.assertEqual(result["combined"]["status"], "EXPLORATORY_COMBINED_NOT_FAMILY_DECISION")
        self.assertEqual(result["pit_ready_count"], 0)
        self.assertEqual(result["provider_api_rpc_wss_calls"], 0)
        self.assertNotIn("EARN_REPLICATION", result["family_decision"])
        self.assertNotIn("CLOSE", result["family_decision"])
        traded_complete = [
            row for row in result["rows"] if row["stratum"] == "TRADED" and row["join_status"] == "COMPLETE_XY"
        ]
        self.assertEqual(len(traded_complete), 6)
        for row in result["rows"]:
            self.assertFalse(row["pit_ready"])
            if row["y_status"] != "OBSERVED":
                self.assertIsNone(row["y_value"])


if __name__ == "__main__":
    unittest.main()
