from __future__ import annotations

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

from solana_alpha_lab.factory.application import FactoryApplication
from solana_alpha_lab.factory.cockpit import load_cockpit_config, project_cockpit
from solana_alpha_lab.factory.operational_store import OperationalStore
from solana_alpha_lab.factory.runtime import copy_rehost_allowlist, load_runtime_config
from solana_alpha_lab.factory.workbench import serve


COCKPIT_SCHEMA = ROOT / "catalog/schemas/factory_v1_owner_cockpit.schema.json"
COCKPIT_CONFIG = ROOT / "configs/factory_v1_owner_cockpit_v1.yaml"
PYPROJECT = ROOT / "pyproject.toml"
ACCEPTANCE_RELATIVE = (
    "docs/evidence/factory_v1_commissioning/a2_factory_v1_commissioning_acceptance_v1.json"
)
RUNTIME_RECEIPT_RELATIVE = (
    "docs/evidence/factory_v1_commissioning/a2_factory_v1_commissioning_runtime_receipt_v1.json"
)
PACKET_FIELDS = (
    "QUESTION",
    "ESTIMAND",
    "POPULATION",
    "DATA",
    "RESULT",
    "UNCERTAINTY",
    "ROBUSTNESS",
    "FAILURE",
    "DECISION",
    "NEXT",
)


def isolated_factory_root(tmp: Path) -> Path:
    config = load_runtime_config(ROOT)
    copy_rehost_allowlist(
        src_root=ROOT,
        dst_root=tmp,
        relatives=list(config["rehost_relative_paths"]),
    )
    return tmp


def _get(app: FactoryApplication, path: str) -> str:
    server = serve(app, host="127.0.0.1", port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        conn = HTTPConnection(host, port, timeout=2)
        conn.request("GET", path)
        response = conn.getresponse()
        body = response.read().decode("utf-8")
        conn.close()
        assert response.status == 200, body
        return body
    finally:
        server.shutdown()
        server.server_close()


class FactoryV1OwnerCockpitLiteTests(unittest.TestCase):
    def test_config_is_cockpit_lite_without_ui_package_or_vps(self) -> None:
        config = load_cockpit_config(ROOT)
        jsonschema.validate(config, json.loads(COCKPIT_SCHEMA.read_text(encoding="utf-8")))
        self.assertEqual(config["implementation"], "WORKBENCH_WRAP_NO_NEW_UI_PACKAGE")
        self.assertEqual(config["visible_nav"], ["HOME", "RESEARCH", "OPERATIONS", "ECONOMICS", "SYSTEM"])
        self.assertEqual(config["hidden_nav"], ["MARKET"])
        self.assertEqual(list(config["packet_fields"]), list(PACKET_FIELDS))
        self.assertTrue(config["health"]["empty_enterprise_screens_forbidden"])
        self.assertFalse(config["authority"]["ui_package_adoption"])
        self.assertFalse(config["authority"]["deployment"])
        self.assertFalse(config["authority"]["provider_calls"])
        dumped = yaml.safe_dump(config)
        self.assertNotIn("FACTORY_V1_OPERATIONAL_READY", dumped)
        self.assertNotIn("NiceGUI", dumped)
        self.assertNotIn("Streamlit", dumped)
        self.assertNotIn("FastAPI", dumped)
        self.assertNotIn("React", dumped)

    def test_pyproject_does_not_adopt_a_ui_package(self) -> None:
        text = PYPROJECT.read_text(encoding="utf-8")
        for token in ("nicegui", "streamlit", "fastapi", "react", "nextjs"):
            self.assertNotIn(token, text.lower())

    def test_result_prefers_scientific_terminal_over_product_pass(self) -> None:
        cockpit = project_cockpit(
            {
                "question": "q",
                "estimand": "e",
                "population": "p",
                "terminal_result": "FACTORY_COMMISSIONING_LIVE_CYCLE_PASS",
                "result": "FACTORY_COMMISSIONING_LIVE_CYCLE_PASS",
                "decision": "product",
                "next_safe_action": "park",
            },
            acceptance={
                "scientific_terminal": "DIRECTIONAL_HINT_NOT_CONFIRMATION",
                "terminal": "DIRECTIONAL_HINT_NOT_CONFIRMATION",
                "product_terminal": "FACTORY_COMMISSIONING_LIVE_CYCLE_PASS",
                "owner_decision": "COMMISSIONING_PACKET_SCIENTIFIC_HINT_NOT_ALPHA",
                "limitations": ["SCREENING_HINT_NOT_OOS_CONFIRMATION"],
                "criteria": {"h3600_role": "PREDECLARED_ROBUSTNESS_NOT_SEARCHABLE_Y"},
                "cohort": {"sample_class": "LIVE_OUTCOME_BLIND"},
                "next_boundary": "LATER",
            },
        )
        self.assertEqual(cockpit["packet"]["RESULT"], "DIRECTIONAL_HINT_NOT_CONFIRMATION")
        self.assertNotEqual(cockpit["packet"]["RESULT"], "FACTORY_COMMISSIONING_LIVE_CYCLE_PASS")

    def _close_app(self, app: FactoryApplication, store: OperationalStore) -> None:
        paper = getattr(app, "_paper_plane_store", None)
        if paper is not None:
            paper.close()
        store.close()

    def test_packet_and_attention_are_visible_without_git_archaeology(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp) / "src")
            store = OperationalStore((root / "ops.sqlite").resolve())
            app = FactoryApplication(root=root, store=store)
            try:
                model = app.read_model()
                self.assertFalse(model["git_archaeology_required"])
                cockpit = model["cockpit"]
                self.assertFalse(cockpit["git_archaeology_required"])
                self.assertFalse(cockpit["operational_ready"])
                self.assertEqual(cockpit["terminal"], "OWNER_COCKPIT_LITE_OPERABILITY_PASS")
                for field in PACKET_FIELDS:
                    self.assertTrue(str(cockpit["packet"][field]).strip(), field)
                self.assertEqual(cockpit["packet"]["RESULT"], "DIRECTIONAL_HINT_NOT_CONFIRMATION")
                self.assertNotEqual(cockpit["packet"]["RESULT"], "FACTORY_COMMISSIONING_LIVE_CYCLE_PASS")
                self.assertIn("SCREENING_HINT_NOT_OOS_CONFIRMATION", cockpit["packet"]["UNCERTAINTY"])
                self.assertIn("PREDECLARED_ROBUSTNESS", cockpit["packet"]["ROBUSTNESS"])
                self.assertEqual(
                    cockpit["packet"]["DECISION"],
                    "COMMISSIONING_PACKET_SCIENTIFIC_HINT_NOT_ALPHA",
                )
                home = _get(app, "/")
                research = _get(app, "/research")
                system = _get(app, "/system")
                self.assertIn("COMMISSIONING_PACKET_SCIENTIFIC_HINT_NOT_ALPHA", home)
                self.assertIn("WHY_NOW", home)
                self.assertIn("NEXT_SAFE_ACTION", home)
                self.assertIn("factory-v1-runtime-v1.0", home)
                self.assertIn("EXPLICIT_UNKNOWN", home)
                self.assertIn("DEGRADED_PROCESS_ALIVE_BACKUP_UNKNOWN", home)
                self.assertNotIn(">MARKET<", home)
                self.assertIn(">OPERATIONS<", home)
                self.assertIn(">ECONOMICS<", home)
                operations = _get(app, "/operations")
                economics = _get(app, "/economics")
                ops_model = app.read_model(surface="OPERATIONS")
                self.assertEqual(ops_model["cockpit"]["terminal"], "OWNER_OPERATIONS_COCKPIT_PASS")
                self.assertIn("Operator commands", operations)
                self.assertIn("NO_REALIZED_LIVE_PNL", economics)
                self.assertNotIn(">MARKET<", operations)
                self.assertNotIn(">MARKET<", economics)
                self.assertNotEqual(model["runtime"]["verdict"], "HEALTHY")
                self.assertIn("COMMISSIONING_PACKET_SCIENTIFIC_HINT_NOT_ALPHA", research)
                self.assertIn("QUESTION", research)
                self.assertIn("factory-v1-runtime-v1.0", system)
            finally:
                self._close_app(app, store)

    def test_missing_acceptance_requires_git_archaeology(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp) / "src")
            (root / ACCEPTANCE_RELATIVE).unlink()
            store = OperationalStore((root / "ops.sqlite").resolve())
            app = FactoryApplication(root=root, store=store)
            try:
                model = app.read_model()
                self.assertTrue(model["git_archaeology_required"])
                self.assertTrue(model["cockpit"]["git_archaeology_required"])
                self.assertEqual(model["cockpit"]["terminal"], "OWNER_COCKPIT_LITE_BLOCKED")
                self.assertEqual(model["cockpit"]["attention"][0]["id"], "GIT_ARCHAEOLOGY_REQUIRED")
                home = _get(app, "/")
                self.assertIn("GIT_ARCHAEOLOGY_REQUIRED", home)
                self.assertIn("git_archaeology_required=true", home)
                self.assertNotEqual(model.get("runtime", {}).get("verdict"), "HEALTHY")
            finally:
                self._close_app(app, store)

    def test_missing_runtime_receipt_requires_git_archaeology(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp) / "src")
            (root / RUNTIME_RECEIPT_RELATIVE).unlink()
            store = OperationalStore((root / "ops.sqlite").resolve())
            app = FactoryApplication(root=root, store=store)
            try:
                model = app.read_model()
                self.assertTrue(model["git_archaeology_required"])
                self.assertIn("RUNTIME_RECEIPT", model["cockpit"]["attention"][0]["EVIDENCE"])
                self.assertEqual(model["cockpit"]["terminal"], "OWNER_COCKPIT_LITE_BLOCKED")
            finally:
                self._close_app(app, store)

    def test_missing_both_produced_receipts_requires_git_archaeology(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp) / "src")
            (root / ACCEPTANCE_RELATIVE).unlink()
            (root / RUNTIME_RECEIPT_RELATIVE).unlink()
            store = OperationalStore((root / "ops.sqlite").resolve())
            app = FactoryApplication(root=root, store=store)
            try:
                model = app.read_model()
                self.assertTrue(model["git_archaeology_required"])
                evidence = model["cockpit"]["attention"][0]["EVIDENCE"]
                self.assertIn("ACCEPTANCE", evidence)
                self.assertIn("RUNTIME_RECEIPT", evidence)
                self.assertEqual(model["cockpit"]["terminal"], "OWNER_COCKPIT_LITE_BLOCKED")
            finally:
                self._close_app(app, store)

    def test_kernel_authority_and_existing_copy_blocks_remain(self) -> None:
        kernel = yaml.safe_load(
            (ROOT / "configs/factory_v1_product_kernel_v1.yaml").read_text(encoding="utf-8")
        )
        self.assertFalse(kernel["authority"]["provider_calls"])
        self.assertFalse(kernel["ui_gate"]["package_adoption"])
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            store = OperationalStore(Path(tmp) / "ops.sqlite")
            app = FactoryApplication(root=ROOT, store=store)
            try:
                home = _get(app, "/")
                self.assertIn("copy-block", home)
                self.assertIn("Копировать", home)
                self.assertIn("QUOTE_SURFACE_RETENTION_CONFIRMATORY_V1", home)
            finally:
                self._close_app(app, store)


if __name__ == "__main__":
    unittest.main()
