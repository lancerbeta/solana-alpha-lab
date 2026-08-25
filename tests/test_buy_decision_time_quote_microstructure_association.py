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

from solana_alpha_lab.buy_decision_time_quote_microstructure_association import (
    DIRECTIONAL_WATCH,
    LOCAL_ONLY_NONREPRODUCIBLE,
    NULL_CLOSE,
    REPLICATION_WORTHY,
    SEMANTICS_BLOCKED,
    AssociationError,
    apply_drop_downgrade,
    associate_from_capsule,
    classify_family_signs,
    load_association_config,
    outcome_group,
    rescale_invariant,
    run_association,
    weaker_terminal,
    write_outputs,
)


FLOOR = 9_727_186
TOL = 20


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, (bytes, bytearray)):
        path.write_bytes(payload)
        return
    path.write_bytes((json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def _quote_body(*, impact: str, hops: int = 1, percent: int = 100, error: bool = False) -> dict[str, object]:
    if error:
        return {"error": "quote failed"}
    legs = [{"bps": 10000, "percent": percent, "swapInfo": {"label": "Pump.fun"}} for _ in range(hops)]
    return {
        "inAmount": "10000000",
        "outAmount": "100",
        "priceImpactPct": impact,
        "routePlan": legs,
    }


def _receipt(*, mints: list[str], outputs: dict[str, int], y_values: dict[str, float], bodies: dict[str, bytes], run: str = "run=test") -> dict[str, object]:
    observations = []
    manifests = []
    for mint in mints:
        amount = outputs[mint]
        y = y_values[mint]
        terminal = "QUOTE_OBSERVED" if y is not None else "MARKET_EXECUTION_UNAVAILABLE"
        observations.append(
            {
                "mint": mint,
                "h900_terminal": terminal,
                "y": y,
                "h900": {"output_amount": str(amount)} if amount is not None else {},
            }
        )
        rel = f"{run}/{mint}_BUY_T0.body"
        body = bodies[mint]
        manifests.append(
            {
                "path": rel,
                "sha256": sha256(body),
                "retention": "A4_OUTSIDE_GIT",
            }
        )
    return {"observations": observations, "raw_retention": {"manifests": manifests}}


def _base_config(windows: list[dict[str, object]]) -> dict[str, object]:
    return {
        "atom_id": "BUY_DECISION_TIME_QUOTE_MICROSTRUCTURE_ASSOCIATION_V1",
        "association_predictors": ["X_PRICE_IMPACT"],
        "routeplan_eligibility_gates": ["RP_ROUTE_COUNT", "RP_FIRST_LEG_PERCENT"],
        "unit_assumption": "WORKING_ASSUMPTION_FRACTION",
        "floor": {"lamports": FLOOR, "tolerance_lamports": TOL, "notional_atomic": 10_000_000},
        "informative_window": {"min_analysis_rows": 8, "min_floor_n": 3, "min_family_n": 3},
        "terminal_thresholds": {
            "min_informative_windows": 4,
            "majority_min": 4,
            "drop_may_upgrade": False,
            "overall_rule": "WEAKER_OF_FAMILY_TERMINALS",
            "combined_not_floor_forbidden": True,
            "absolute_x_threshold_forbidden": True,
        },
        "primary_windows": windows,
        "next_by_terminal": {
            SEMANTICS_BLOCKED: "STOP",
            LOCAL_ONLY_NONREPRODUCIBLE: "STOP",
            NULL_CLOSE: "PARK_BUY_IMPACT_AS_SELECTOR_X",
            DIRECTIONAL_WATCH: "STOP",
            REPLICATION_WORTHY: "WRITE_REPLICATION_CONTRACT_ONLY",
        },
        "non_claims": ["NO_PRODUCTION_SELECTOR"],
        "outputs": {
            "capsule_jsonl": "docs/evidence/buy_decision_time_quote_microstructure_association/a1_derived_capsule_v1.jsonl",
            "association_input": "docs/evidence/buy_decision_time_quote_microstructure_association/a1_association_input_v1.json",
            "runtime_receipt": "docs/evidence/buy_decision_time_quote_microstructure_association/a1_runtime_receipt_v1.json",
        },
    }


def _analysis_row(window_id: str, mint: str, x: str, group: str) -> dict[str, object]:
    amount = FLOOR if group == "FLOOR" else FLOOR + TOL + 5 if group == "BETTER" else FLOOR - TOL - 5
    return {
        "window_id": window_id,
        "mint": mint,
        "decision_time_label": "BUY_T0",
        "x_price_impact_decimal": x,
        "x_price_impact_raw_json_type": "str",
        "rp_route_count": 1,
        "rp_first_leg_percent": 100,
        "h900_output_amount": amount,
        "outcome_group": group,
        "exclusion_reason": None,
        "in_primary_analysis": True,
        "extractor_id": "BUY_DT_QUOTE_MS_EXTRACTOR_V1",
        "raw_body_sha256": "a" * 64,
        "git_receipt_sha256": "b" * 64,
    }


def _filled_window(window_id: str, *, better_x: str, worse_x: str, floor_x: str) -> list[dict[str, object]]:
    rows = []
    for i in range(4):
        rows.append(_analysis_row(window_id, f"{window_id}F{i}", floor_x, "FLOOR"))
    for i in range(3):
        rows.append(_analysis_row(window_id, f"{window_id}B{i}", better_x, "BETTER"))
    for i in range(3):
        rows.append(_analysis_row(window_id, f"{window_id}W{i}", worse_x, "WORSE"))
    return rows


class OutcomeAndMutexTests(unittest.TestCase):
    def test_floor_split_is_three_way(self) -> None:
        self.assertEqual(outcome_group(FLOOR, FLOOR, TOL), "FLOOR")
        self.assertEqual(outcome_group(FLOOR - TOL - 1, FLOOR, TOL), "WORSE")
        self.assertEqual(outcome_group(FLOOR + TOL + 1, FLOOR, TOL), "BETTER")

    def test_drop_cannot_upgrade_null(self) -> None:
        full = [1, -1, 1, -1]
        remaining = [1, 1, 1]
        self.assertEqual(classify_family_signs(full, min_w=4, majority_min=4), NULL_CLOSE)
        self.assertEqual(apply_drop_downgrade(NULL_CLOSE, remaining, full), NULL_CLOSE)

    def test_drop_cannot_upgrade_directional_to_replication(self) -> None:
        full = [1, 1, 1, 1, -1]
        remaining = [1, 1, 1, 1]
        self.assertEqual(classify_family_signs(full, min_w=4, majority_min=4), DIRECTIONAL_WATCH)
        self.assertEqual(apply_drop_downgrade(DIRECTIONAL_WATCH, remaining, full), DIRECTIONAL_WATCH)
        self.assertNotEqual(apply_drop_downgrade(DIRECTIONAL_WATCH, remaining, full), REPLICATION_WORTHY)

    def test_weaker_of_families(self) -> None:
        self.assertEqual(weaker_terminal(REPLICATION_WORTHY, NULL_CLOSE), NULL_CLOSE)
        self.assertEqual(weaker_terminal(REPLICATION_WORTHY, DIRECTIONAL_WATCH), DIRECTIONAL_WATCH)

    def test_replication_survives_unanimous_drop(self) -> None:
        full = [1, 1, 1, 1]
        remaining = [1, 1, 1]
        self.assertEqual(apply_drop_downgrade(REPLICATION_WORTHY, remaining, full), REPLICATION_WORTHY)


class CapsuleAssociationTests(unittest.TestCase):
    def test_w_vl_cannot_enter_primary(self) -> None:
        config = _base_config([{"window_id": "W-EP"}])
        rows = _filled_window("W-EP", better_x="0.2", worse_x="0.3", floor_x="0.1")
        baseline = associate_from_capsule(rows, config)["terminal"]
        poisoned = rows + [{**_analysis_row("W-VL", "vl1", "0.9", "BETTER"), "in_primary_analysis": True}]
        result = associate_from_capsule(poisoned, config)
        self.assertEqual(result["terminal"], baseline)

    def test_capsule_reapplies_semantics_gates(self) -> None:
        config = _base_config(
            [{"window_id": wid} for wid in ("W-EP", "W-SB", "W-HC-A", "W-HC-B")]
        )
        rows: list[dict[str, object]] = []
        for wid in ("W-EP", "W-SB", "W-HC-A", "W-HC-B"):
            rows.extend(_filled_window(wid, better_x="0.20", worse_x="0.20", floor_x="0.10"))
        rows[0]["x_price_impact_raw_json_type"] = "float"
        result = associate_from_capsule(rows, config)
        self.assertEqual(result["terminal"], SEMANTICS_BLOCKED)

    def test_not_floor_is_not_used_for_terminal(self) -> None:
        config = _base_config(
            [{"window_id": wid} for wid in ("W-EP", "W-SB", "W-HC-A", "W-HC-B")]
        )
        rows: list[dict[str, object]] = []
        for wid in ("W-EP", "W-SB", "W-HC-A", "W-HC-B"):
            rows.extend(_filled_window(wid, better_x="0.40", worse_x="0.01", floor_x="0.10"))
        result = associate_from_capsule(rows, config)
        better_sign = result["families"]["BETTER"]["per_window"][0]["sign"]
        worse_sign = result["families"]["WORSE"]["per_window"][0]["sign"]
        self.assertEqual(better_sign, 1)
        self.assertEqual(worse_sign, -1)
        self.assertNotEqual(better_sign, worse_sign)

    def test_rescale_invariance(self) -> None:
        config = _base_config(
            [{"window_id": wid} for wid in ("W-EP", "W-SB", "W-HC-A", "W-HC-B")]
        )
        rows: list[dict[str, object]] = []
        for wid in ("W-EP", "W-SB", "W-HC-A", "W-HC-B"):
            rows.extend(_filled_window(wid, better_x="0.20", worse_x="0.20", floor_x="0.10"))
        self.assertTrue(rescale_invariant(rows, config, 100))

    def test_mutex_one_terminal(self) -> None:
        config = _base_config(
            [{"window_id": wid} for wid in ("W-EP", "W-SB", "W-HC-A", "W-HC-B")]
        )
        rows: list[dict[str, object]] = []
        for wid in ("W-EP", "W-SB", "W-HC-A", "W-HC-B"):
            rows.extend(_filled_window(wid, better_x="0.20", worse_x="0.20", floor_x="0.10"))
        result = associate_from_capsule(rows, config)
        self.assertIn(result["terminal"], {NULL_CLOSE, DIRECTIONAL_WATCH, REPLICATION_WORTHY})
        self.assertFalse(result["production_selector_authorized"])
        self.assertNotIn("p_value", json.dumps(result))

    def test_e3_counts_present(self) -> None:
        config = _base_config([{"window_id": "W-EP"}])
        rows = _filled_window("W-EP", better_x="0.2", worse_x="0.3", floor_x="0.1")
        result = associate_from_capsule(rows, config)
        stats = result["families"]["BETTER"]["per_window"][0]
        self.assertEqual(stats["n_better"], 3)
        self.assertEqual(stats["n_worse"], 3)
        self.assertEqual(stats["n_floor"], 4)

    def test_routeplan_not_listed_as_predictor(self) -> None:
        config = load_association_config(ROOT)
        self.assertEqual(config["association_predictors"], ["X_PRICE_IMPACT"])
        self.assertIn("RP_ROUTE_COUNT", config["routeplan_eligibility_gates"])
        self.assertNotIn("RP_ROUTE_COUNT", config["association_predictors"])


class ExtractorFixtureTests(unittest.TestCase):
    def _window(self, tmp: Path, window_id: str, impact: str, *, native_float: bool = False, hops: int = 1) -> dict[str, object]:
        mints = [f"{window_id}{i}" for i in range(10)]
        outputs = {}
        y_values = {}
        bodies = {}
        for i, mint in enumerate(mints):
            if i < 4:
                outputs[mint] = FLOOR
            elif i < 7:
                outputs[mint] = FLOOR + TOL + 5
            else:
                outputs[mint] = FLOOR - TOL - 5
            y_values[mint] = -0.01 if i >= 4 else -0.027
            body_obj = _quote_body(impact=impact, hops=hops)
            if native_float:
                body_obj["priceImpactPct"] = float(impact)
            raw = (json.dumps(body_obj, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
            bodies[mint] = raw
        receipt = _receipt(mints=mints, outputs=outputs, y_values=y_values, bodies=bodies)
        rec_path = tmp / "docs" / "evidence" / f"{window_id}.json"
        a4_root = tmp / "local" / window_id
        _write(rec_path, receipt)
        for mint, raw in bodies.items():
            (a4_root / "run=test" / f"{mint}_BUY_T0.body").parent.mkdir(parents=True, exist_ok=True)
            (a4_root / "run=test" / f"{mint}_BUY_T0.body").write_bytes(raw)
        return {
            "window_id": window_id,
            "git_receipt_path": f"docs/evidence/{window_id}.json",
            "git_receipt_sha256": sha256(rec_path.read_bytes()),
            "a4_root": f"local/{window_id}",
        }

    def test_native_float_blocks_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            window = self._window(tmp, "W-EP", "0.10", native_float=True)
            config = _base_config([window])
            config.pop("sensitivity_window", None)
            bundle = run_association(tmp, config)
            self.assertEqual(bundle["result"]["terminal"], SEMANTICS_BLOCKED)
            self.assertIsNone(bundle["result"]["family_terminals"]["BETTER"])

    def test_hop_mix_blocks_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            window = self._window(tmp, "W-EP", "0.10", hops=2)
            config = _base_config([window])
            bundle = run_association(tmp, config)
            self.assertEqual(bundle["result"]["terminal"], SEMANTICS_BLOCKED)

    def test_abs_x_ge_1_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            window = self._window(tmp, "W-EP", "1.00")
            config = _base_config([window])
            bundle = run_association(tmp, config)
            self.assertEqual(bundle["result"]["terminal"], SEMANTICS_BLOCKED)

    def test_missing_run_dir_is_local_only(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            window = self._window(tmp, "W-EP", "0.10")
            import shutil
            shutil.rmtree(tmp / "local" / "W-EP")
            config = _base_config([window])
            bundle = run_association(tmp, config)
            self.assertEqual(bundle["result"]["terminal"], LOCAL_ONLY_NONREPRODUCIBLE)

    def test_y_copied_not_relabeled(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            window = self._window(tmp, "W-EP", "0.10")
            config = _base_config([window])
            bundle = run_association(tmp, config)
            row = next(item for item in bundle["rows"] if item["in_primary_analysis"])
            self.assertIsInstance(row["y_h900"], float)
            self.assertNotIn("y_escape", row)
            self.assertIn(row["outcome_group"], {"FLOOR", "WORSE", "BETTER"})

    def test_missing_output_amount_not_synthesized(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            window = self._window(tmp, "W-EP", "0.10")
            rec_path = tmp / window["git_receipt_path"]
            receipt = json.loads(rec_path.read_text(encoding="utf-8"))
            receipt["observations"][0]["h900"] = {}
            receipt["observations"][0]["y"] = -0.01
            receipt["observations"][0]["h900_terminal"] = "QUOTE_OBSERVED"
            _write(rec_path, receipt)
            window["git_receipt_sha256"] = sha256(rec_path.read_bytes())
            config = _base_config([window])
            bundle = run_association(tmp, config)
            row = next(item for item in bundle["rows"] if item["mint"] == receipt["observations"][0]["mint"])
            self.assertEqual(row["exclusion_reason"], "OUTPUT_AMOUNT_MISSING")
            self.assertIsNone(row["h900_output_amount"])

    def test_sell_filename_is_not_x_source(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            window = self._window(tmp, "W-EP", "0.10")
            sell = tmp / "local" / "W-EP" / "run=test" / "W-EP0_SELL_H900.body"
            sell.write_bytes(b'{"priceImpactPct":"9.9","routePlan":[]}')
            config = _base_config([window])
            bundle = run_association(tmp, config)
            self.assertTrue(all(row["decision_time_label"] == "BUY_T0" for row in bundle["rows"]))
            self.assertTrue(all(row.get("x_price_impact_decimal") != "9.9" for row in bundle["rows"]))

    def test_capsule_omits_taker_transaction_and_price_impact_float_key(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            window = self._window(tmp, "W-EP", "0.10")
            config = _base_config([window])
            bundle = run_association(tmp, config)
            write_outputs(tmp, bundle, config)
            text = (tmp / config["outputs"]["capsule_jsonl"]).read_text(encoding="utf-8")
            self.assertNotIn('"taker"', text)
            self.assertNotIn('"transaction"', text)
            self.assertNotIn('"priceImpact"', text)
            self.assertNotIn('"p_value"', text)
            self.assertNotIn('"routePlan"', text)

    def test_w_vl_rows_do_not_alter_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            windows = [self._window(tmp, wid, "0.10") for wid in ("W-EP", "W-SB", "W-HC-A", "W-HC-B")]
            config = _base_config(windows)
            without = run_association(tmp, config)["result"]["terminal"]
            vl_receipt = {"observations": [{"mint": "vlmint", "h900_terminal": "QUOTE_OBSERVED", "y": 0.08, "h900": {"output_amount": "20000000"}}], "raw_retention": {"manifests": []}}
            rec = tmp / "docs/evidence/wvl.json"
            _write(rec, vl_receipt)
            a4 = tmp / "local/wvl"
            a4.mkdir(parents=True)
            config["sensitivity_window"] = {
                "window_id": "W-VL",
                "quote_tag": "BUY_T1",
                "git_receipt_path": "docs/evidence/wvl.json",
                "git_receipt_sha256": sha256(rec.read_bytes()),
                "a4_root": "local/wvl",
                "may_change_primary_terminal": False,
            }
            with_vl = run_association(tmp, config)
            self.assertEqual(with_vl["result"]["terminal"], without)
            self.assertEqual(with_vl["receipt"]["w_vl_appendix"]["in_primary_analysis_count"], 0)

    def test_hash_mismatch_is_local_only(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            window = self._window(tmp, "W-EP", "0.10")
            rec_path = tmp / window["git_receipt_path"]
            receipt = json.loads(rec_path.read_text(encoding="utf-8"))
            receipt["raw_retention"]["manifests"][0]["sha256"] = "0" * 64
            _write(rec_path, receipt)
            window["git_receipt_sha256"] = sha256(rec_path.read_bytes())
            config = _base_config([window])
            bundle = run_association(tmp, config)
            self.assertEqual(bundle["result"]["terminal"], LOCAL_ONLY_NONREPRODUCIBLE)

    def test_error_quote_excluded_not_semantics_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            window = self._window(tmp, "W-EP", "0.10")
            rec_path = tmp / window["git_receipt_path"]
            receipt = json.loads(rec_path.read_text(encoding="utf-8"))
            mint = receipt["observations"][0]["mint"]
            err = (json.dumps({"error": "no quote"}) + "\n").encode("utf-8")
            body_path = tmp / window["a4_root"] / "run=test" / f"{mint}_BUY_T0.body"
            body_path.write_bytes(err)
            for item in receipt["raw_retention"]["manifests"]:
                if item["path"].endswith(f"{mint}_BUY_T0.body"):
                    item["sha256"] = sha256(err)
            _write(rec_path, receipt)
            window["git_receipt_sha256"] = sha256(rec_path.read_bytes())
            config = _base_config([window])
            bundle = run_association(tmp, config)
            self.assertNotEqual(bundle["result"]["terminal"], SEMANTICS_BLOCKED)
            row = next(item for item in bundle["rows"] if item["mint"] == mint)
            self.assertEqual(row["exclusion_reason"], "BUY_QUOTE_ERROR")

    def test_buy_t1_filename_is_not_x_source(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            window = self._window(tmp, "W-EP", "0.10")
            t1 = tmp / "local" / "W-EP" / "run=test" / "W-EP0_BUY_T1.body"
            t1.write_bytes(b'{"priceImpactPct":"0.99","routePlan":[{"percent":100}]}')
            config = _base_config([window])
            bundle = run_association(tmp, config)
            self.assertTrue(all(row["decision_time_label"] == "BUY_T0" for row in bundle["rows"]))
            self.assertTrue(all(row.get("x_price_impact_decimal") != "0.99" for row in bundle["rows"]))

    def test_written_capsule_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            windows = [self._window(tmp, wid, "0.10") for wid in ("W-EP", "W-SB", "W-HC-A", "W-HC-B")]
            config = _base_config(windows)
            bundle = run_association(tmp, config)
            write_outputs(tmp, bundle, config)
            from solana_alpha_lab.buy_decision_time_quote_microstructure_association import (
                associate_from_capsule,
                load_capsule_jsonl,
            )
            rows = load_capsule_jsonl(tmp / config["outputs"]["capsule_jsonl"])
            replay = associate_from_capsule(rows, config)
            self.assertEqual(replay["terminal"], bundle["result"]["terminal"])
            self.assertEqual(replay["family_terminals"], bundle["result"]["family_terminals"])


class RepoConfigLockTests(unittest.TestCase):
    def test_repo_config_pins(self) -> None:
        config = load_association_config(ROOT)
        self.assertFalse(config["unit_assumption_is_fact"])
        self.assertEqual(config["decision_time_label"], "BUY_T0")
        ids = [item["window_id"] for item in config["primary_windows"]]
        self.assertNotIn("W-VL", ids)
        self.assertEqual(len(ids), 5)


if __name__ == "__main__":
    unittest.main()
