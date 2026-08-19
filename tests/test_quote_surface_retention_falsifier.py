from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.application import FactoryApplication
from solana_alpha_lab.factory.capabilities import (
    drop_excluded_rows,
    excluded_mints_from_spec,
    execute_capability,
)
from solana_alpha_lab.factory.experiment_spec import load_experiment_spec
from solana_alpha_lab.factory.operational_store import OperationalStore
from solana_alpha_lab.factory.quote_surface_retention import (
    INCONCLUSIVE_TERMINAL,
    PASS_TERMINAL,
    FAIL_TERMINAL,
    classify_quote_surface_retention,
    load_quote_surface_retention_rule,
    score_retention_observations,
)
from solana_alpha_lab.quote_native_admissible_friction_audition import (
    RETENTION_ATOM_ID,
    RETENTION_AUTHORITY_PHRASE,
    canonical_json,
    validate_policy,
)
from solana_alpha_lab.quote_native_evidence_channel_qualification import _execute_schedule
from solana_alpha_lab.quote_native_live_variation_campaign import (
    RETENTION_OBSERVATION_SCHEDULE,
    build_schedule,
)


SPEC_RELATIVE = "configs/experiment_specs/quote_surface_retention_falsifier_v1.yaml"
POLICY_RELATIVE = "configs/quote_native_quote_surface_retention_audition_v1.yaml"
RULE_RELATIVE = "configs/quote_surface_retention_rule_v1.yaml"
SELECTOR = ROOT / "configs/factory_v1_quote_surface_retention_falsifier_v1.yaml"
SELECTOR_SCHEMA = ROOT / "catalog/schemas/factory_v1_quote_surface_retention_falsifier.schema.json"
SPEC_SCHEMA = ROOT / "catalog/schemas/experiment_spec.schema.json"
RUNNER = ROOT / "src/solana_alpha_lab/factory/runner.py"


def _copy(root: Path, relative: str) -> None:
    src = ROOT / relative
    dst = root / relative
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(src.read_bytes())


def isolated_retention_root(tmp: Path) -> Path:
    _copy(tmp, "catalog/schemas/experiment_spec.schema.json")
    _copy(tmp, SPEC_RELATIVE)
    _copy(tmp, POLICY_RELATIVE)
    spec_text = yaml.safe_load((ROOT / SPEC_RELATIVE).read_text(encoding="utf-8"))
    for item in spec_text["data_requirements"]:
        if item["kind"] == "PROVIDER_BOUNDED_CAPTURE":
            item.pop("sha256", None)
            continue
        _copy(tmp, item["path"])
    spec_dst = tmp / SPEC_RELATIVE
    spec_dst.parent.mkdir(parents=True, exist_ok=True)
    spec_dst.write_text(yaml.safe_dump(spec_text, sort_keys=False), encoding="utf-8")
    for relative in (
        "registries/hypotheses.yaml",
        "registries/research_cycles.yaml",
        "configs/provider_route_capability_registry_v6.yaml",
        "configs/provider_route_capability_registry_v7.yaml",
        "configs/provider_route_capability_registry_v8.yaml",
        "configs/provider_route_capability_registry_v9.yaml",
        "configs/factory_v1_quote_surface_retention_falsifier_v1.yaml",
        "configs/factory_v1_product_kernel_v1.yaml",
    ):
        _copy(tmp, relative)
    return tmp


def _cell(
    identity: str,
    *,
    decision: str,
    y: str,
    stratum: str,
    time_separated: bool = True,
) -> dict[str, object]:
    return {
        "identity_id": identity,
        "stratum": stratum,
        "decision": decision,
        "y_status": "OBSERVED",
        "time_separated": time_separated,
        "forward_quoted_return_h900_h3600": y,
        "retention_delta": "0.01" if decision == "KEEP" else "-0.01",
    }


def _frozen(identity: str, stratum: str) -> dict[str, str]:
    return {"identity_id": identity, "stratum": stratum, "mint": identity}


def _pass_cells() -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    cells: list[dict[str, object]] = []
    frozen: list[dict[str, str]] = []
    for index in range(4):
        keep_id = f"r-keep-{index}"
        veto_id = f"r-veto-{index}"
        cells.append(_cell(keep_id, decision="KEEP", y="0.10", stratum="RECENT"))
        cells.append(_cell(veto_id, decision="VETO", y="-0.10", stratum="RECENT"))
        frozen.extend([_frozen(keep_id, "RECENT"), _frozen(veto_id, "RECENT")])
        keep_t = f"t-keep-{index}"
        veto_t = f"t-veto-{index}"
        cells.append(_cell(keep_t, decision="KEEP", y="0.10", stratum="TRADED"))
        cells.append(_cell(veto_t, decision="VETO", y="-0.10", stratum="TRADED"))
        frozen.extend([_frozen(keep_t, "TRADED"), _frozen(veto_t, "TRADED")])
    return cells, frozen


class QuoteSurfaceRetentionFalsifierTests(unittest.TestCase):
    def test_frozen_configs_are_composition_not_vps(self) -> None:
        selector = yaml.safe_load(SELECTOR.read_text(encoding="utf-8"))
        jsonschema.validate(
            selector, json.loads(SELECTOR_SCHEMA.read_text(encoding="utf-8"))
        )
        spec = yaml.safe_load((ROOT / SPEC_RELATIVE).read_text(encoding="utf-8"))
        jsonschema.validate(spec, json.loads(SPEC_SCHEMA.read_text(encoding="utf-8")))
        policy = yaml.safe_load((ROOT / POLICY_RELATIVE).read_text(encoding="utf-8"))
        validate_policy(policy, root=ROOT)
        self.assertEqual(policy["atom_id"], RETENTION_ATOM_ID)
        self.assertEqual(
            policy["external_authority"]["owner_phrase"],
            RETENTION_AUTHORITY_PHRASE,
        )
        self.assertEqual(
            spec["parameters"]["required_owner_phrase"],
            RETENTION_AUTHORITY_PHRASE,
        )
        self.assertEqual(spec["method"], "classify_quote_surface_retention")
        self.assertEqual(spec["evidence_budget"]["provider_api_rpc_wss_calls"], 62)
        ids = [item["requirement_id"] for item in spec["data_requirements"]]
        self.assertIn("EXCLUSION_ATOM5", ids)
        self.assertIn("EXCLUSION_ATOM6", ids)
        dumped = yaml.safe_dump(selector) + yaml.safe_dump(spec)
        self.assertNotIn("FACTORY_V1_OPERATIONAL_READY", dumped)
        self.assertNotIn("RC-004", dumped)
        self.assertNotIn("VPS", spec["question"])

    def test_generic_runner_file_is_untouched(self) -> None:
        text = RUNNER.read_text(encoding="utf-8")
        self.assertIn("Contains no hypothesis business logic", text)
        self.assertNotIn("quote_surface_retention", text)
        self.assertNotIn("RETENTION_DELTA", text)

    def test_retention_schedule_buys_at_h900_and_sells_that_buy_at_h3600(self) -> None:
        cells = [
            {"identity_id": "RECENT_0", "mint": "Mint111111111111111111111111111111111111111", "stratum": "RECENT"}
            for _ in range(6)
        ] + [
            {"identity_id": "TRADED_0", "mint": "Mint222222222222222222222222222222222222222", "stratum": "TRADED"}
            for _ in range(6)
        ]
        for index, cell in enumerate(cells[:6]):
            cell["identity_id"] = f"RECENT_{index}"
            cell["mint"] = f"RMint{index:0>38}"
        for index, cell in enumerate(cells[6:]):
            cell["identity_id"] = f"TRADED_{index}"
            cell["mint"] = f"TMint{index:0>38}"
        rows = build_schedule(
            cells,
            panel_started_at=datetime(2026, 8, 19, 12, 0, tzinfo=UTC),
            schedule_kind=RETENTION_OBSERVATION_SCHEDULE,
        )
        self.assertEqual(len(rows), 60)
        kinds = {str(row["kind"]) for row in rows}
        self.assertEqual(
            kinds,
            {"BUY_T0", "REVERSE_T0", "BUY_H900", "REVERSE_H900", "SELL_H3600"},
        )
        self.assertNotIn("SELL_H900", kinds)
        buy_h900 = next(row for row in rows if row["kind"] == "BUY_H900")
        self.assertEqual(buy_h900["amount"], "10000000")
        self.assertIsNone(buy_h900["parent_id"])
        sell = next(
            row
            for row in rows
            if row["kind"] == "SELL_H3600" and row["identity_id"] == buy_h900["identity_id"]
        )
        self.assertEqual(sell["parent_id"], buy_h900["observation_id"])

    def test_execute_schedule_uses_explicit_h900_buy_notional(self) -> None:
        started = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
        buy_h900_id = "RECENT_0:10000000:BUY_H900"
        schedule = [
            {
                "observation_id": buy_h900_id,
                "identity_id": "RECENT_0",
                "mint": "MintKeep111111111111111111111111111111111",
                "stratum": "RECENT",
                "kind": "BUY_H900",
                "wave": "horizon",
                "input_mint": "So11111111111111111111111111111111111111112",
                "output_mint": "MintKeep111111111111111111111111111111111",
                "amount": "10000000",
                "parent_id": None,
                "due_at": "2026-08-19T12:15:00Z",
                "horizon_seconds": 900,
                "lateness_slack_seconds": 120,
            }
        ]
        seen: list[str] = []

        def call(url: str, observation_id: str) -> dict[str, object]:
            seen.append(url)
            return {
                "observed_at": "2026-08-19T12:15:01Z",
                "url_has_api_key": False,
                "response_sha256": "ab",
                "http_status": 200,
                "body": b"{}",
            }

        results = _execute_schedule(
            schedule=schedule,
            policy={"slippage_bps": "100"},
            call=call,
            clock=lambda: started,
            sleeper=lambda _: None,
            panel_started_at=started,
            panel_started_monotonic=0.0,
            monotonic_clock=lambda: 900.0,
            retain_order_raw=lambda *_args: None,
        )
        self.assertEqual(len(seen), 1)
        self.assertIn("amount=10000000", seen[0])
        self.assertEqual(results[0]["amount"], "10000000")

    def test_missing_phrase_is_blocked_authority_with_zero_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = isolated_retention_root(Path(tmp) / "src")
            spec = load_experiment_spec(root, SPEC_RELATIVE)
            derived = execute_capability(spec, root=root, authority_phrase=None)
            self.assertEqual(derived["status"], "BLOCKED_AUTHORITY")
            self.assertEqual(derived["blocker"], "OWNER_PHRASE_MISSING")
            self.assertEqual(derived["provider_api_rpc_wss_calls"], 0)
            self.assertEqual(derived["credential_reads"], 0)

    def test_wrong_phrase_including_go_is_blocked_authority(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = isolated_retention_root(Path(tmp) / "src")
            spec = load_experiment_spec(root, SPEC_RELATIVE)
            derived = execute_capability(spec, root=root, authority_phrase="го")
            self.assertEqual(derived["status"], "BLOCKED_AUTHORITY")
            self.assertEqual(derived["blocker"], "AUTHORITY_PHRASE_INVALID")
            self.assertEqual(derived["provider_api_rpc_wss_calls"], 0)
            self.assertEqual(derived["credential_reads"], 0)

    def test_keep_improves_both_strata(self) -> None:
        cells, frozen = _pass_cells()
        result = classify_quote_surface_retention(
            mechanism={"cells": cells},
            frozen_cells=frozen,
        )
        self.assertEqual(result["terminal"], PASS_TERMINAL)
        self.assertFalse(result["stratum_unstable"])
        self.assertTrue(result["same_direction"])

    def test_closes_family_without_uplift(self) -> None:
        cells, frozen = _pass_cells()
        for cell in cells:
            if cell["decision"] == "KEEP":
                cell["forward_quoted_return_h900_h3600"] = "-0.20"
            else:
                cell["forward_quoted_return_h900_h3600"] = "0.05"
        result = classify_quote_surface_retention(
            mechanism={"cells": cells},
            frozen_cells=frozen,
        )
        self.assertEqual(result["terminal"], FAIL_TERMINAL)
        self.assertEqual(result["reason"], "NO_MEDIAN_OR_TAIL_UPLIFT")

    def test_one_stratum_kept_is_unstable_fail(self) -> None:
        cells, frozen = _pass_cells()
        for cell in cells:
            if cell["stratum"] == "RECENT" and cell["decision"] == "KEEP":
                cell["decision"] = "VETO"
                cell["forward_quoted_return_h900_h3600"] = "-0.10"
        result = classify_quote_surface_retention(
            mechanism={"cells": cells},
            frozen_cells=frozen,
        )
        self.assertEqual(result["terminal"], FAIL_TERMINAL)
        self.assertEqual(result["reason"], "STRATUM_UNSTABLE")

    def test_insufficient_cells_are_inconclusive_not_family_close(self) -> None:
        result = classify_quote_surface_retention(
            mechanism={
                "cells": [
                    _cell("r1", decision="KEEP", y="0.1", stratum="RECENT"),
                    _cell("t1", decision="VETO", y="-0.1", stratum="TRADED"),
                ]
            },
            frozen_cells=[_frozen("r1", "RECENT"), _frozen("t1", "TRADED")],
        )
        self.assertEqual(result["terminal"], INCONCLUSIVE_TERMINAL)
        self.assertEqual(result["reason"], "INSUFFICIENT_VALID_CELLS_PER_STRATUM")

    def test_yaml_rule_binds_the_executed_projector(self) -> None:
        rule = load_quote_surface_retention_rule(ROOT, RULE_RELATIVE)
        cells, frozen = _pass_cells()
        result = classify_quote_surface_retention(
            mechanism={"cells": cells},
            frozen_cells=frozen,
            rule=rule,
        )
        self.assertEqual(result["terminal"], PASS_TERMINAL)

    def test_h3600_no_route_is_path_risk_not_zero(self) -> None:
        observations = [
            {
                "identity_id": "RECENT_0",
                "kind": "BUY_T0",
                "terminal": "QUOTE_OBSERVED",
                "amount": "10000000",
                "quote": {"out_amount": "200"},
            },
            {
                "identity_id": "RECENT_0",
                "kind": "REVERSE_T0",
                "terminal": "QUOTE_OBSERVED",
                "quote": {"out_amount": "9900000"},
            },
            {
                "identity_id": "RECENT_0",
                "kind": "BUY_H900",
                "terminal": "QUOTE_OBSERVED",
                "amount": "10000000",
                "quote": {"out_amount": "210"},
            },
            {
                "identity_id": "RECENT_0",
                "kind": "REVERSE_H900",
                "terminal": "QUOTE_OBSERVED",
                "quote": {"out_amount": "9950000"},
            },
            {
                "identity_id": "RECENT_0",
                "kind": "SELL_H3600",
                "terminal": "NO_ROUTE",
            },
        ]
        scored = score_retention_observations(
            observations,
            frozen_cells=[_frozen("RECENT_0", "RECENT")],
        )
        cell = scored["cells"][0]
        self.assertEqual(cell["decision"], "KEEP")
        self.assertEqual(cell["y_status"], "PATH_RISK")
        self.assertTrue(cell["y_path_risk"])
        self.assertIsNone(cell["forward_quoted_return_h900_h3600"])

    def test_spec_exclusions_cover_prior_consumed_cohorts(self) -> None:
        spec = load_experiment_spec(ROOT, SPEC_RELATIVE)
        excluded = excluded_mints_from_spec(spec, root=ROOT)
        self.assertGreaterEqual(len(excluded), 48)
        for item in spec["data_requirements"]:
            if item["kind"] != "GIT_CANONICAL_RECEIPT":
                continue
            receipt = json.loads((ROOT / item["path"]).read_text(encoding="utf-8"))
            mints = {
                str(cell["mint"])
                for cell in receipt.get("frozen_cells") or []
                if isinstance(cell, dict) and cell.get("mint")
            }
            self.assertTrue(mints)
            self.assertTrue(mints.issubset(excluded), item["requirement_id"])
        kept = drop_excluded_rows(
            [{"id": sorted(excluded)[0]}, {"id": "fresh-mint-not-in-prior-receipts"}],
            excluded,
        )
        self.assertEqual([row["id"] for row in kept], ["fresh-mint-not-in-prior-receipts"])

    def test_application_default_spec_is_the_retention_falsifier(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = OperationalStore(Path(tmp) / "ops.sqlite")
            try:
                app = FactoryApplication(root=ROOT, store=store)
                self.assertEqual(app.spec_relative, SPEC_RELATIVE)
            finally:
                store.close()
            root = isolated_retention_root(Path(tmp) / "src")
            store = OperationalStore(Path(tmp) / "ops-isolated.sqlite")
            try:
                app = FactoryApplication(root=root, store=store)
                self.assertEqual(app.spec_relative, SPEC_RELATIVE)
                after = app.start()
                self.assertEqual(after["status"], "BLOCKED_AUTHORITY")
                self.assertEqual(after["blocker"], "OWNER_PHRASE_MISSING")
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
