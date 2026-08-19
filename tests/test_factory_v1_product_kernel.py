from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.application import ApplicationError, FactoryApplication
from solana_alpha_lab.factory.experiment_spec import load_experiment_spec
from solana_alpha_lab.factory.operational_store import OperationalStore
from solana_alpha_lab.factory.runner import ExperimentRunner
from solana_alpha_lab.factory.workbench import serve
from solana_alpha_lab.quote_native_admissible_friction_audition import (
    classify_audition_terminal,
)


SPEC_RELATIVE = (
    "configs/experiment_specs/quote_native_admissible_friction_audition_offline_v1.yaml"
)
KERNEL_CONFIG = ROOT / "configs/factory_v1_product_kernel_v1.yaml"
KERNEL_SCHEMA = ROOT / "catalog/schemas/factory_v1_product_kernel.schema.json"
SPEC_SCHEMA = ROOT / "catalog/schemas/experiment_spec.schema.json"
RUNTIME = (
    ROOT
    / "docs/evidence/quote_native_admissible_friction_audition"
    / "a1_quote_native_admissible_friction_audition_runtime_receipt_v1.json"
)
ACCEPTANCE = (
    ROOT
    / "docs/evidence/quote_native_admissible_friction_audition"
    / "a1_quote_native_admissible_friction_audition_acceptance_v1.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def isolated_spec_root(
    tmp: Path,
    *,
    mutate_hash: bool = False,
    include_receipts: bool = True,
) -> Path:
    schema_dst = tmp / "catalog/schemas/experiment_spec.schema.json"
    schema_dst.parent.mkdir(parents=True, exist_ok=True)
    schema_dst.write_bytes(SPEC_SCHEMA.read_bytes())
    spec = yaml.safe_load((ROOT / SPEC_RELATIVE).read_text(encoding="utf-8"))
    if mutate_hash:
        spec["data_requirements"][0]["sha256"] = "0" * 64
    spec_dst = tmp / SPEC_RELATIVE
    spec_dst.parent.mkdir(parents=True, exist_ok=True)
    spec_dst.write_text(yaml.safe_dump(spec, sort_keys=False), encoding="utf-8")
    if include_receipts:
        for req in spec["data_requirements"]:
            dst = tmp / req["path"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes((ROOT / req["path"]).read_bytes())
    for relative in ("registries/hypotheses.yaml", "registries/research_cycles.yaml"):
        dst = tmp / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes((ROOT / relative).read_bytes())
    return tmp


class FactoryV1ProductKernelTests(unittest.TestCase):
    def test_kernel_config_and_spec_validate(self) -> None:
        config = yaml.safe_load(KERNEL_CONFIG.read_text(encoding="utf-8"))
        spec = yaml.safe_load((ROOT / SPEC_RELATIVE).read_text(encoding="utf-8"))
        jsonschema.validate(config, json.loads(KERNEL_SCHEMA.read_text(encoding="utf-8")))
        jsonschema.validate(spec, json.loads(SPEC_SCHEMA.read_text(encoding="utf-8")))
        self.assertEqual(config["ui_gate"]["verdict"], "BUILD")
        self.assertFalse(config["ui_gate"]["package_adoption"])
        self.assertFalse(config["authority"]["provider_calls"])
        self.assertEqual(spec["evidence_budget"]["provider_api_rpc_wss_calls"], 0)
        self.assertNotIn("docs/tasks/", json.dumps(spec))

    def test_golden_receipt_hashes_match_spec(self) -> None:
        spec = load_experiment_spec(ROOT, SPEC_RELATIVE)
        requirements = {item["requirement_id"]: item for item in spec["data_requirements"]}
        self.assertEqual(requirements["RUNTIME_RECEIPT"]["sha256"], sha256(RUNTIME))
        self.assertEqual(requirements["ACCEPTANCE"]["sha256"], sha256(ACCEPTANCE))

    def test_offline_runner_replays_admissible_audition_without_provider(self) -> None:
        runtime = json.loads(RUNTIME.read_text(encoding="utf-8"))
        derived = classify_audition_terminal(
            capture=runtime["capture"],
            campaign=runtime["campaign"],
            mechanism=runtime["mechanism"],
        )
        self.assertEqual(derived, "DIRECTIONAL_HINT_NOT_CONFIRMATION")
        with tempfile.TemporaryDirectory() as tmp:
            store = OperationalStore(Path(tmp) / "ops.sqlite")
            runner = ExperimentRunner(root=ROOT, store=store)
            first = runner.start(SPEC_RELATIVE)
            self.assertEqual(first["status"], "COMPLETE")
            self.assertEqual(first["terminal"], "DIRECTIONAL_HINT_NOT_CONFIRMATION")
            self.assertEqual(first["evidence"]["provider_api_rpc_wss_calls"], 0)
            store.close()
            restarted = OperationalStore(Path(tmp) / "ops.sqlite")
            job = restarted.latest_job()
            assert job is not None
            self.assertEqual(job["status"], "COMPLETE")
            model = FactoryApplication(root=ROOT, store=restarted).read_model()
            self.assertEqual(model["terminal_result"], "DIRECTIONAL_HINT_NOT_CONFIRMATION")
            self.assertFalse(model["missing_data"])
            restarted.close()

    def test_missing_receipt_is_explicit_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = isolated_spec_root(Path(tmp), mutate_hash=True)
            store = OperationalStore(root / "ops.sqlite")
            runner = ExperimentRunner(root=root, store=store)
            result = runner.start(SPEC_RELATIVE)
            self.assertEqual(result["status"], "BLOCKED_DATA")
            self.assertEqual(result["blocker"], "MISSING_OR_MISMATCHED_EVIDENCE")
            model = FactoryApplication(root=root, store=store).read_model()
            self.assertTrue(model["missing_data"])
            self.assertEqual(model["next_safe_action"], "RESOLVE_MISSING_EVIDENCE")
            store.close()

    def test_read_model_reports_live_git_coverage_before_start(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = isolated_spec_root(Path(tmp), include_receipts=False)
            store = OperationalStore(root / "ops.sqlite")
            before = FactoryApplication(root=root, store=store).read_model()
            self.assertEqual(before["status"], "NOT_STARTED")
            self.assertTrue(before["missing_data"])
            self.assertEqual(before["next_safe_action"], "RESOLVE_MISSING_EVIDENCE")
            self.assertFalse(before["available_data"])
            store.close()

    def test_freeze_does_not_rewrite_hypothesis_registry(self) -> None:
        hypotheses = ROOT / "registries/hypotheses.yaml"
        before = hypotheses.read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            store = OperationalStore(Path(tmp) / "ops.sqlite")
            app = FactoryApplication(root=ROOT, store=store)
            with self.assertRaises(ApplicationError):
                app.freeze_hypothesis()
            store.close()
        self.assertEqual(hypotheses.read_bytes(), before)

    def test_application_read_model_and_workbench_are_projections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = OperationalStore(Path(tmp) / "ops.sqlite")
            app = FactoryApplication(root=ROOT, store=store)
            before = app.read_model()
            self.assertEqual(before["hypothesis"], "HYP-QUOTE-NATIVE-FRICTION-H900-V1")
            self.assertEqual(before["hypothesis_status"], "UNKNOWN")
            self.assertFalse(before["git_archaeology_required"])
            self.assertEqual(before["status"], "NOT_STARTED")
            after = app.start()
            self.assertEqual(after["status"], "COMPLETE")
            self.assertEqual(after["terminal_result"], "DIRECTIONAL_HINT_NOT_CONFIRMATION")
            self.assertEqual(after["blocker"], "NONE")
            self.assertFalse(after["missing_data"])
            self.assertIn("PARK_FAMILY", after["next_safe_action"])
            server = serve(app, host="127.0.0.1", port=0)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address[:2]
                conn = HTTPConnection(host, port, timeout=2)
                conn.request("GET", "/")
                response = conn.getresponse()
                body = response.read().decode("utf-8")
                self.assertEqual(response.status, 200)
                self.assertIn("DIRECTIONAL_HINT_NOT_CONFIRMATION", body)
                self.assertIn("Factory v1", body)
                conn.close()
            finally:
                server.shutdown()
                server.server_close()
                store.close()

    def test_src_runner_has_no_hypothesis_business_logic(self) -> None:
        runner = (SRC / "solana_alpha_lab/factory/runner.py").read_text(encoding="utf-8")
        self.assertNotIn("classify_audition_terminal", runner)
        self.assertNotIn("QuotedRoundTripFriction", runner)
        self.assertNotIn("JUPITER", runner)

    def test_catalog_and_workbench_have_no_scientific_authority(self) -> None:
        config = yaml.safe_load(KERNEL_CONFIG.read_text(encoding="utf-8"))
        self.assertFalse(config["operational_store"]["owns_scientific_truth"])
        self.assertFalse(config["ui_gate"]["package_adoption"])
        core = (ROOT / "catalog/assets/core.yaml").read_text(encoding="utf-8")
        for asset_id in (
            "CTRL-FACTORY-V1-PRODUCT-KERNEL-001",
            "MODULE-FACTORY-V1-RUNNER-001",
            "EVIDENCE-FACTORY-V1-PRODUCT-KERNEL-ACCEPTANCE-001",
        ):
            self.assertIn(asset_id, core)
            self.assertIn(asset_id, (ROOT / "docs/PROJECT_MAP.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
