from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.operational_readiness_closeout import (  # noqa: E402
    CloseoutError,
    FACTORY_RUNNER_SHA256,
    apply_stage_reconciliation,
    evaluate_closeout,
)


class FactoryV1OperationalReadinessCloseoutTests(unittest.TestCase):
    def test_runner_pin_unchanged(self) -> None:
        digest = hashlib.sha256(
            (ROOT / "src/solana_alpha_lab/factory/runner.py").read_bytes()
        ).hexdigest()
        self.assertEqual(digest, FACTORY_RUNNER_SHA256)

    def test_live_closeout_is_replan_with_named_gaps(self) -> None:
        gate = evaluate_closeout(ROOT)
        self.assertEqual(gate["terminal"], "FACTORY_PRODUCTIZATION_REPLAN")
        self.assertFalse(gate["factory_v1_operational_ready"])
        self.assertEqual(gate["foundation_freeze"], "INACTIVE")
        self.assertGreaterEqual(len(gate["named_gaps"]), 1)
        gap_ids = {item.split(":", 1)[0] for item in gate["named_gaps"]}
        self.assertNotIn("RUNTIME_LIVE_DEPLOY_ROLLBACK", gap_ids)
        self.assertNotIn("MONITORING_PROVIDER_FAILURE_ALERT", gap_ids)
        self.assertNotIn("SECURITY_FINANCIAL_GATED", gap_ids)
        self.assertNotIn("DATA_FACTORY_PIT_LINEAGE_RECEIPT", gap_ids)
        self.assertNotIn("DATA_EXPLICIT_MISSINGNESS", gap_ids)
        self.assertNotIn("TIME_TO_EVIDENCE_FIRST_BYTE", gap_ids)
        self.assertEqual(gap_ids, {"ENTRY_GATE_RESOLVES_READINESS_CONTRACT"})
        self.assertEqual(
            gate["next_safe_action"],
            "A6_READINESS_RECERTIFICATION_AND_FREEZE",
        )
        # Must still pass known slice predicates (positive fields, not proxies).
        by_id = {item["id"]: item for item in gate["predicates"]}
        self.assertEqual(by_id["COMMISSIONING_GOLDEN_REPLAY"]["verdict"], "PASS")
        self.assertEqual(by_id["RUNTIME_LIVE_HOST_AND_SHADOW_WORKER"]["verdict"], "PASS")
        self.assertEqual(by_id["DATA_LIVE_BACKUP_ISOLATED_RESTORE"]["verdict"], "PASS")
        self.assertEqual(by_id["SECURITY_LOCALHOST_UI"]["verdict"], "PASS")
        self.assertEqual(by_id["MONITORING_HEALTH_VIEW"]["verdict"], "PASS")
        self.assertEqual(by_id["MONITORING_DEDUP_TESTED"]["verdict"], "PASS")
        self.assertEqual(by_id["DATA_FACTORY_PIT_LINEAGE_RECEIPT"]["verdict"], "PASS")
        self.assertEqual(by_id["DATA_EXPLICIT_MISSINGNESS"]["verdict"], "PASS")
        self.assertEqual(by_id["TIME_TO_EVIDENCE_FIRST_BYTE"]["verdict"], "PASS")
        self.assertEqual(by_id["RUNTIME_LIVE_DEPLOY_ROLLBACK"]["verdict"], "PASS")
        self.assertEqual(by_id["RUNTIME_LIVE_CLEAN_REHOST"]["verdict"], "PASS")
        self.assertEqual(by_id["MONITORING_PROVIDER_FAILURE_ALERT"]["verdict"], "PASS")
        self.assertEqual(by_id["MONITORING_LIVE_STALE_DATA_ALERT"]["verdict"], "PASS")
        self.assertEqual(by_id["MONITORING_LIVE_BOT_STALL_ALERT"]["verdict"], "PASS")
        self.assertEqual(by_id["DATA_PROVIDER_HEALTH_VISIBLE"]["verdict"], "PASS")
        self.assertEqual(by_id["SECURITY_FINANCIAL_GATED"]["verdict"], "PASS")

    def test_all_pass_fixture_emits_ready_and_freeze(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Minimal tree: copy config + runner bytes + synthetic evidence.
            (root / "configs").mkdir()
            (root / "src/solana_alpha_lab/factory").mkdir(parents=True)
            (root / "src/solana_alpha_lab/factory/runner.py").write_bytes(
                (ROOT / "src/solana_alpha_lab/factory/runner.py").read_bytes()
            )
            for relative in (
                "docs/evidence/early_structural_backing_pit_commissioning/a1_window_a_runtime_receipt_v1.json",
                "docs/evidence/early_structural_backing_pit_commissioning/a1_acceptance_v1.json",
                "docs/tasks/EARLY_STRUCTURAL_BACKING_PIT_COMMISSIONING_V1.md",
            ):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
            cfg = json.loads(
                json.dumps(
                    __import__("yaml").safe_load(
                        (ROOT / "configs/factory_v1_operational_readiness_closeout_v1.yaml").read_text(
                            encoding="utf-8"
                        )
                    )
                )
            )
            # Replace every evidence with a synthetic PASS object.
            for pred in cfg["predicates"]:
                rel = pred["evidence_path"]
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                if "schema_path" in pred:
                    source_path = ROOT / rel
                    payload = json.loads(source_path.read_text(encoding="utf-8"))
                    schema_rel = pred["schema_path"]
                    schema_path = root / schema_rel
                    schema_path.parent.mkdir(parents=True, exist_ok=True)
                    schema_path.write_bytes((ROOT / schema_rel).read_bytes())
                    pred["schema_sha256"] = hashlib.sha256(
                        schema_path.read_bytes()
                    ).hexdigest()
                elif path.is_file():
                    if "require_yaml" in pred:
                        payload = __import__("yaml").safe_load(path.read_text(encoding="utf-8")) or {}
                    else:
                        payload = json.loads(path.read_text(encoding="utf-8"))
                else:
                    payload = {}
                if not isinstance(payload, dict):
                    payload = {}
                source = pred.get("require_yaml") if "require_yaml" in pred else pred["require"]
                for key, value in source.items():
                    cur = payload
                    parts = str(key).split(".")
                    for part in parts[:-1]:
                        nxt = cur.get(part)
                        if not isinstance(nxt, dict):
                            nxt = {}
                            cur[part] = nxt
                        cur = nxt
                    cur[parts[-1]] = value
                if "require_yaml" in pred:
                    path.write_text(
                        __import__("yaml").safe_dump(payload, sort_keys=True),
                        encoding="utf-8",
                    )
                else:
                    path.write_text(
                        json.dumps(payload, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    if "schema_path" in pred:
                        pred["evidence_sha256"] = hashlib.sha256(
                            path.read_bytes()
                        ).hexdigest()
            (root / "configs/factory_v1_operational_readiness_closeout_v1.yaml").write_text(
                __import__("yaml").safe_dump(cfg, sort_keys=False),
                encoding="utf-8",
            )
            # readiness yaml doubles as ENTRY_GATE evidence + reconcile target
            readiness = (
                "status: ACCEPTED_DIRECTION_NOT_IMPLEMENTED\n"
                "implementation: NOT_IMPLEMENTED\n"
                "mode: DESIGN_ONLY\n"
                "milestone:\n"
                "  status: TRIGGERED\n"
                "domain_policy_integration:\n"
                "  entry_gate_resolves_this_file: true\n"
                "current_product_stage:\n"
                "  generic_hypothesis_runner: NOT_OPERATIONAL_AS_PRODUCT\n"
                "  owner_cockpit: NOT_IMPLEMENTED\n"
                "  production_lite_runtime: NOT_IMPLEMENTED\n"
                "  unattended_monitoring: NOT_IMPLEMENTED\n"
                "  paper_shadow_position_operations: NOT_OPERATIONAL\n"
                "capability_radar:\n"
                "  now: NONE\n"
            )
            readiness_path = root / "configs/factory_v1_operational_readiness_v1.yaml"
            # Preserve ENTRY_GATE synthetic file if already written, merge required fields.
            if readiness_path.is_file():
                existing = __import__("yaml").safe_load(readiness_path.read_text(encoding="utf-8"))
            else:
                existing = {}
            if not isinstance(existing, dict):
                existing = {}
            merged = __import__("yaml").safe_load(readiness)
            # Keep require_yaml satisfaction from synthetic writer.
            dpi = existing.get("domain_policy_integration")
            if isinstance(dpi, dict):
                merged.setdefault("domain_policy_integration", {}).update(dpi)
            readiness_path.write_text(
                __import__("yaml").safe_dump(merged, sort_keys=False),
                encoding="utf-8",
            )
            gate = evaluate_closeout(root)
            self.assertEqual(gate["terminal"], "FACTORY_V1_OPERATIONAL_READY")
            self.assertTrue(gate["factory_v1_operational_ready"])
            self.assertEqual(gate["foundation_freeze"], "ACTIVE")
            self.assertEqual(gate["named_gaps"], [])
            apply_stage_reconciliation(root, gate)
            text = (root / "configs/factory_v1_operational_readiness_v1.yaml").read_text(
                encoding="utf-8"
            )
            self.assertIn("status: IMPLEMENTED_VALIDATED", text)
            self.assertIn("foundation_freeze: ACTIVE", text)
            self.assertIn("factory_v1_operational_ready: true", text)

    def test_missing_evidence_is_named_gap_not_exception(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "configs").mkdir()
            (root / "src/solana_alpha_lab/factory").mkdir(parents=True)
            (root / "src/solana_alpha_lab/factory/runner.py").write_bytes(
                (ROOT / "src/solana_alpha_lab/factory/runner.py").read_bytes()
            )
            cfg = {
                "task_id": "T",
                "as_of": "2026-08-23",
                "runner_path": "src/solana_alpha_lab/factory/runner.py",
                "runner_pin_sha256": FACTORY_RUNNER_SHA256,
                "foundation_freeze_on_ready": True,
                "reconciled_product_stage_on_any_closeout": {
                    "owner_cockpit": "X"
                },
                "non_claims": ["NO_ALPHA"],
                "predicates": [
                    {
                        "id": "MISSING_ONE",
                        "dimension": "runtime",
                        "evidence_path": "docs/missing.json",
                        "require": {"terminal": "PASS"},
                    }
                ],
            }
            (root / "configs/factory_v1_operational_readiness_closeout_v1.yaml").write_text(
                __import__("yaml").safe_dump(cfg, sort_keys=False),
                encoding="utf-8",
            )
            gate = evaluate_closeout(root)
            self.assertEqual(gate["terminal"], "FACTORY_PRODUCTIZATION_REPLAN")
            self.assertTrue(gate["named_gaps"][0].startswith("MISSING_ONE:MISSING_EVIDENCE:"))

    def test_a4_data_gap_routes_to_data_replan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "configs").mkdir()
            (root / "src/solana_alpha_lab/factory").mkdir(parents=True)
            (root / "src/solana_alpha_lab/factory/runner.py").write_bytes(
                (ROOT / "src/solana_alpha_lab/factory/runner.py").read_bytes()
            )
            cfg = {
                "task_id": "T",
                "as_of": "2026-08-23",
                "runner_path": "src/solana_alpha_lab/factory/runner.py",
                "runner_pin_sha256": FACTORY_RUNNER_SHA256,
                "foundation_freeze_on_ready": True,
                "reconciled_product_stage_on_any_closeout": {"owner_cockpit": "X"},
                "non_claims": ["NO_ALPHA"],
                "predicates": [
                    {
                        "id": "DATA_EXPLICIT_MISSINGNESS",
                        "dimension": "data",
                        "evidence_path": "docs/missing.json",
                        "require": {"terminal": "PASS"},
                    }
                ],
            }
            (root / "configs/factory_v1_operational_readiness_closeout_v1.yaml").write_text(
                __import__("yaml").safe_dump(cfg, sort_keys=False),
                encoding="utf-8",
            )

            gate = evaluate_closeout(root)

            self.assertEqual(
                gate["next_safe_action"],
                "PIT_CANONICALIZATION_EVIDENCE_INSUFFICIENT",
            )

    def test_a4_receipt_hash_and_schema_binding_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "configs/factory_v1_operational_readiness_closeout_v1.yaml"
            config_path.parent.mkdir(parents=True)
            config_path.write_bytes(
                (ROOT / "configs/factory_v1_operational_readiness_closeout_v1.yaml").read_bytes()
            )
            runner_path = root / "src/solana_alpha_lab/factory/runner.py"
            runner_path.parent.mkdir(parents=True)
            runner_path.write_bytes((ROOT / "src/solana_alpha_lab/factory/runner.py").read_bytes())
            acceptance_path = root / "docs/evidence/factory_v1_pit_data_truth_canonicalization/a1_acceptance_v1.json"
            acceptance_path.parent.mkdir(parents=True)
            acceptance_path.write_bytes(
                (ROOT / "docs/evidence/factory_v1_pit_data_truth_canonicalization/a1_acceptance_v1.json").read_bytes()
            )
            schema_path = root / "catalog/schemas/factory_v1_pit_data_truth_canonicalization.schema.json"
            schema_path.parent.mkdir(parents=True)
            schema_path.write_bytes(
                (ROOT / "catalog/schemas/factory_v1_pit_data_truth_canonicalization.schema.json").read_bytes()
            )
            acceptance_path.write_bytes(
                acceptance_path.read_bytes().replace(
                    b'"pit_lineage_ready": true',
                    b'"pit_lineage_ready": false',
                )
            )

            gate = evaluate_closeout(root)
            a4_gap = next(
                item for item in gate["named_gaps"]
                if item.startswith("DATA_FACTORY_PIT_LINEAGE_RECEIPT:")
            )
            self.assertTrue(a4_gap.endswith("EVIDENCE_HASH_MISMATCH"))

    def test_a4_schema_valid_forgery_fails_replay_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "configs/factory_v1_operational_readiness_closeout_v1.yaml"
            config_path.parent.mkdir(parents=True)
            config = __import__("yaml").safe_load(
                (ROOT / "configs/factory_v1_operational_readiness_closeout_v1.yaml").read_text(
                    encoding="utf-8"
                )
            )
            config_path.write_text(
                __import__("yaml").safe_dump(config, sort_keys=False),
                encoding="utf-8",
            )
            runner_path = root / "src/solana_alpha_lab/factory/runner.py"
            runner_path.parent.mkdir(parents=True)
            runner_path.write_bytes((ROOT / "src/solana_alpha_lab/factory/runner.py").read_bytes())
            for relative in (
                "docs/evidence/early_structural_backing_pit_commissioning/a1_window_a_runtime_receipt_v1.json",
                "docs/evidence/early_structural_backing_pit_commissioning/a1_acceptance_v1.json",
                "docs/tasks/EARLY_STRUCTURAL_BACKING_PIT_COMMISSIONING_V1.md",
            ):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
            acceptance_path = root / "docs/evidence/factory_v1_pit_data_truth_canonicalization/a1_acceptance_v1.json"
            acceptance_path.parent.mkdir(parents=True)
            acceptance = json.loads(
                (ROOT / "docs/evidence/factory_v1_pit_data_truth_canonicalization/a1_acceptance_v1.json").read_text(
                    encoding="utf-8"
                )
            )
            acceptance["projection"]["rows"][1]["mint"] = acceptance["projection"]["rows"][0]["mint"]
            acceptance["projection"]["rows"][1]["source_row_mint"] = acceptance["projection"]["rows"][0]["source_row_mint"]
            acceptance_path.write_text(
                json.dumps(acceptance, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            schema_path = root / "catalog/schemas/factory_v1_pit_data_truth_canonicalization.schema.json"
            schema_path.parent.mkdir(parents=True)
            shutil.copyfile(
                ROOT / "catalog/schemas/factory_v1_pit_data_truth_canonicalization.schema.json",
                schema_path,
            )
            acceptance_sha = hashlib.sha256(acceptance_path.read_bytes()).hexdigest()
            schema_sha = hashlib.sha256(schema_path.read_bytes()).hexdigest()
            for predicate in config["predicates"]:
                if predicate["evidence_path"] == "docs/evidence/factory_v1_pit_data_truth_canonicalization/a1_acceptance_v1.json":
                    predicate["evidence_sha256"] = acceptance_sha
                    predicate["schema_sha256"] = schema_sha
            config_path.write_text(
                __import__("yaml").safe_dump(config, sort_keys=False),
                encoding="utf-8",
            )

            gate = evaluate_closeout(root)
            a4_gaps = [
                item
                for item in gate["named_gaps"]
                if item.split(":", 1)[0]
                in {
                    "DATA_FACTORY_PIT_LINEAGE_RECEIPT",
                    "DATA_EXPLICIT_MISSINGNESS",
                    "TIME_TO_EVIDENCE_FIRST_BYTE",
                }
            ]
            self.assertEqual(len(a4_gaps), 3)
            self.assertTrue(
                all(item.endswith("EVIDENCE_REPLAY_MISMATCH") for item in a4_gaps),
                a4_gaps,
            )


if __name__ == "__main__":
    unittest.main()
