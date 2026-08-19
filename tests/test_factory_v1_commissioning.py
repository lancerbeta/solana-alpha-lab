from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread
from typing import Any

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.application import FactoryApplication
from solana_alpha_lab.factory.experiment_spec import load_experiment_spec
from solana_alpha_lab.factory.operational_store import OperationalStore
from solana_alpha_lab.factory.workbench import owner_copy_blocks, serve
from solana_alpha_lab.quote_native_admissible_friction_audition import (
    FACTORY_COMMISSIONING_ATOM_ID,
    FACTORY_V1_COMMISSIONING_AUTHORITY_PHRASE,
    validate_policy,
)


SPEC_RELATIVE = (
    "configs/experiment_specs/factory_v1_commissioning_quote_native_free_key_v1.yaml"
)
COMMISSIONING_CONFIG = ROOT / "configs/factory_v1_commissioning_v1.yaml"
COMMISSIONING_SCHEMA = ROOT / "catalog/schemas/factory_v1_commissioning.schema.json"
SPEC_SCHEMA = ROOT / "catalog/schemas/experiment_spec.schema.json"
POLICY_RELATIVE = "configs/quote_native_factory_commissioning_audition_v1.yaml"
GOLDEN_SPEC = (
    "configs/experiment_specs/quote_native_admissible_friction_audition_offline_v1.yaml"
)


def _copy(root: Path, relative: str) -> None:
    src = ROOT / relative
    dst = root / relative
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(src.read_bytes())


def isolated_commissioning_root(tmp: Path) -> Path:
    _copy(tmp, "catalog/schemas/experiment_spec.schema.json")
    _copy(tmp, SPEC_RELATIVE)
    _copy(tmp, POLICY_RELATIVE)
    spec = yaml.safe_load((ROOT / SPEC_RELATIVE).read_text(encoding="utf-8"))
    for item in spec["data_requirements"]:
        if item["kind"] == "PROVIDER_BOUNDED_CAPTURE":
            continue
        _copy(tmp, item["path"])
    for relative in (
        "registries/hypotheses.yaml",
        "registries/research_cycles.yaml",
        "configs/provider_route_capability_registry_v6.yaml",
        "configs/provider_route_capability_registry_v7.yaml",
        "configs/provider_route_capability_registry_v8.yaml",
        "configs/provider_route_capability_registry_v9.yaml",
    ):
        _copy(tmp, relative)
    return tmp


def isolated_commissioning_root_with_bound_receipts(tmp: Path) -> Path:
    root = isolated_commissioning_root(tmp)
    spec = yaml.safe_load((ROOT / SPEC_RELATIVE).read_text(encoding="utf-8"))
    for item in spec["data_requirements"]:
        if item["kind"] == "PROVIDER_BOUNDED_CAPTURE":
            _copy(root, item["path"])
    return root


class _Response:
    def __init__(self, body: bytes, *, status: int, headers: dict[str, str]) -> None:
        self._body = __import__("io").BytesIO(body)
        self._status = status
        self.headers = headers

    def getcode(self) -> int:
        return self._status

    def read(self, size: int = -1) -> bytes:
        return self._body.read(size)

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


class _SequenceOpener:
    def __init__(self, responses: list[_Response]) -> None:
        self.responses = list(responses)
        self.requests: list[object] = []

    def open(self, request: object, timeout: float = 0) -> _Response:
        self.requests.append(request)
        if not self.responses:
            raise AssertionError("unexpected provider request")
        return self.responses.pop(0)


class _Clock:
    def __init__(self, start: datetime) -> None:
        self.current = start

    def __call__(self) -> datetime:
        return self.current

    def sleep(self, seconds: float) -> None:
        self.current += timedelta(seconds=seconds)


class FactoryV1CommissioningTests(unittest.TestCase):
    def test_commissioning_config_and_spec_validate(self) -> None:
        config = yaml.safe_load(COMMISSIONING_CONFIG.read_text(encoding="utf-8"))
        spec = yaml.safe_load((ROOT / SPEC_RELATIVE).read_text(encoding="utf-8"))
        jsonschema.validate(config, json.loads(COMMISSIONING_SCHEMA.read_text(encoding="utf-8")))
        jsonschema.validate(spec, json.loads(SPEC_SCHEMA.read_text(encoding="utf-8")))
        self.assertEqual(config["atom_id"], FACTORY_COMMISSIONING_ATOM_ID)
        self.assertEqual(spec["evidence_budget"]["provider_api_rpc_wss_calls"], 60)
        self.assertEqual(spec["hypothesis_version"], "HYP-FACTORY-V1-COMMISSIONING-QUOTE-NATIVE-FREE-KEY-V1")
        golden = yaml.safe_load((ROOT / GOLDEN_SPEC).read_text(encoding="utf-8"))
        self.assertEqual(golden["evidence_budget"]["provider_api_rpc_wss_calls"], 0)

    def test_commissioning_policy_accepts_factory_phrase_not_a1(self) -> None:
        policy = yaml.safe_load((ROOT / POLICY_RELATIVE).read_text(encoding="utf-8"))
        validate_policy(policy, root=ROOT)
        self.assertEqual(policy["atom_id"], FACTORY_COMMISSIONING_ATOM_ID)
        self.assertEqual(
            policy["external_authority"]["owner_phrase"],
            FACTORY_V1_COMMISSIONING_AUTHORITY_PHRASE,
        )

    def test_start_without_phrase_is_blocked_authority_zero_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = isolated_commissioning_root(Path(tmp))
            store = OperationalStore(root / "ops.sqlite")
            app = FactoryApplication(root=root, store=store, spec_relative=SPEC_RELATIVE)
            before = app.read_model()
            self.assertEqual(before["hypothesis"], "HYP-FACTORY-V1-COMMISSIONING-QUOTE-NATIVE-FREE-KEY-V1")
            self.assertEqual(before["status"], "NOT_STARTED")
            self.assertEqual(before["next_safe_action"], "WAIT_EXACT_OWNER_PHRASE")
            self.assertEqual(before["next"], "WAIT_EXACT_OWNER_PHRASE")
            self.assertTrue(before["produced_missing"])
            after = app.start()
            self.assertEqual(after["status"], "BLOCKED_AUTHORITY")
            self.assertEqual(after["blocker"], "OWNER_PHRASE_MISSING")
            self.assertEqual(after["result"], "BLOCKED_AUTHORITY")
            job = store.get_job("JOB-EXP-FACTORY-V1-COMMISSIONING-QUOTE-NATIVE-FREE-KEY-001")
            assert job is not None
            self.assertEqual(job["evidence"]["provider_api_rpc_wss_calls"], 0)
            self.assertEqual(job["evidence"]["credential_reads"], 0)
            store.close()

    def test_wrong_phrase_does_not_read_credential(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = isolated_commissioning_root(Path(tmp))
            store = OperationalStore(root / "ops.sqlite")
            app = FactoryApplication(root=root, store=store, spec_relative=SPEC_RELATIVE)
            after = app.start(authority_phrase="not-the-factory-phrase")
            self.assertEqual(after["status"], "BLOCKED_AUTHORITY")
            self.assertEqual(after["blocker"], "AUTHORITY_PHRASE_INVALID")
            job = store.get_job("JOB-EXP-FACTORY-V1-COMMISSIONING-QUOTE-NATIVE-FREE-KEY-001")
            assert job is not None
            self.assertEqual(job["evidence"]["provider_api_rpc_wss_calls"], 0)
            self.assertEqual(job["evidence"]["credential_reads"], 0)
            store.close()

    def test_mocked_wrap_excludes_prior_mints_and_does_not_use_real_network(self) -> None:
        from tests.test_quote_native_admissible_friction_audition import (
            _quote_sequence,
        )

        reverse = [str(9_900_000 - index * 10_000) for index in range(12)]
        sell = [str(9_800_000 - index * 10_000) for index in range(12)]
        h3600 = [str(9_700_000 - index * 5_000) for index in range(12)]
        opener = _SequenceOpener(
            _quote_sequence(reverse_out=reverse, sell_out=sell, h3600_out=h3600)
        )
        clock = _Clock(datetime(2026, 8, 19, 12, 0, tzinfo=UTC))
        with tempfile.TemporaryDirectory() as tmp:
            root = isolated_commissioning_root(Path(tmp))
            store = OperationalStore(root / "ops.sqlite")
            app = FactoryApplication(root=root, store=store, spec_relative=SPEC_RELATIVE)
            after = app.start(
                authority_phrase=FACTORY_V1_COMMISSIONING_AUTHORITY_PHRASE,
                capture_hooks={
                    "environ": {"JUPITER_API_KEY": "test-key-not-a-secret"},
                    "opener": opener,
                    "clock": clock,
                    "sleeper": clock.sleep,
                    "preflight_fn": lambda *_args, **_kwargs: {"credential_reads": 0},
                },
            )
            self.assertIn(after["status"], {"COMPLETE", "FAILED"})
            self.assertGreaterEqual(len(opener.requests), 2)
            runtime_path = (
                root
                / "docs/evidence/factory_v1_commissioning"
                / "a2_factory_v1_commissioning_runtime_receipt_v1.json"
            )
            self.assertTrue(runtime_path.is_file())
            receipt = json.loads(runtime_path.read_text(encoding="utf-8"))
            self.assertEqual(receipt["atom_id"], FACTORY_COMMISSIONING_ATOM_ID)
            self.assertIn("NO_MOVE_3", receipt["non_claims"])
            excluded = set(receipt["excluded_prior_mints"])
            for cell in receipt.get("frozen_cells") or []:
                self.assertNotIn(cell["mint"], excluded)
            first_requests = len(opener.requests)
            runtime_bytes = runtime_path.read_bytes()
            job = store.get_job("JOB-EXP-FACTORY-V1-COMMISSIONING-QUOTE-NATIVE-FREE-KEY-001")
            assert job is not None
            first_terminal = job["terminal"]
            second = app.start(
                authority_phrase=FACTORY_V1_COMMISSIONING_AUTHORITY_PHRASE,
                capture_hooks={
                    "environ": {"JUPITER_API_KEY": "test-key-not-a-secret"},
                    "opener": opener,
                    "clock": clock,
                    "sleeper": clock.sleep,
                    "preflight_fn": lambda *_args, **_kwargs: {"credential_reads": 0},
                },
            )
            self.assertEqual(second["status"], "COMPLETE")
            self.assertEqual(second["terminal_result"], first_terminal)
            self.assertEqual(len(opener.requests), first_requests)
            self.assertEqual(runtime_path.read_bytes(), runtime_bytes)
            store.close()

    def test_live_receipts_are_hash_bound_and_exclude_prior_mints(self) -> None:
        spec = load_experiment_spec(ROOT, SPEC_RELATIVE)
        requirements = {item["requirement_id"]: item for item in spec["data_requirements"]}
        runtime_path = ROOT / requirements["RUNTIME_RECEIPT"]["path"]
        acceptance_path = ROOT / requirements["ACCEPTANCE"]["path"]
        self.assertEqual(
            requirements["RUNTIME_RECEIPT"]["sha256"],
            hashlib.sha256(runtime_path.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            requirements["ACCEPTANCE"]["sha256"],
            hashlib.sha256(acceptance_path.read_bytes()).hexdigest(),
        )
        runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
        acceptance = json.loads(acceptance_path.read_text(encoding="utf-8"))
        self.assertEqual(runtime["atom_id"], FACTORY_COMMISSIONING_ATOM_ID)
        self.assertEqual(runtime["terminal_outcome"], "DIRECTIONAL_HINT_NOT_CONFIRMATION")
        self.assertEqual(acceptance["product_terminal"], "FACTORY_COMMISSIONING_LIVE_CYCLE_PASS")
        self.assertFalse(acceptance["factory_v1_operational_ready"])
        self.assertFalse(acceptance["move_3"])
        self.assertEqual(acceptance["project_sources_disposition"]["kind"], "NO_CHANGE")
        excluded = set(runtime["excluded_prior_mints"])
        self.assertGreaterEqual(len(excluded), 12)
        for cell in runtime["frozen_cells"]:
            self.assertNotIn(cell["mint"], excluded)
        blob = runtime_path.read_bytes().decode("utf-8").lower()
        self.assertNotIn("jupiter_api_key", blob)
        self.assertNotIn("x-api-key", blob)

    def test_hash_bound_receipt_projects_without_network_or_phrase(self) -> None:
        runtime = json.loads(
            (
                ROOT
                / "docs/evidence/factory_v1_commissioning"
                / "a2_factory_v1_commissioning_runtime_receipt_v1.json"
            ).read_text(encoding="utf-8")
        )
        opener = _SequenceOpener([])
        with tempfile.TemporaryDirectory() as tmp:
            root = isolated_commissioning_root_with_bound_receipts(Path(tmp))
            store = OperationalStore(root / "ops.sqlite")
            app = FactoryApplication(root=root, store=store, spec_relative=SPEC_RELATIVE)
            after = app.start(
                authority_phrase=FACTORY_V1_COMMISSIONING_AUTHORITY_PHRASE,
                capture_hooks={
                    "environ": {},
                    "opener": opener,
                },
            )
            self.assertEqual(after["status"], "COMPLETE")
            self.assertEqual(after["terminal_result"], runtime["terminal_outcome"])
            self.assertEqual(after["result"], runtime["terminal_outcome"])
            self.assertEqual(len(opener.requests), 0)
            job = store.get_job("JOB-EXP-FACTORY-V1-COMMISSIONING-QUOTE-NATIVE-FREE-KEY-001")
            assert job is not None
            self.assertEqual(job["evidence"]["provider_api_rpc_wss_calls"], runtime["provider_requests"])
            self.assertEqual(job["evidence"]["credential_reads"], runtime["credential_reads"])
            without_phrase = FactoryApplication(
                root=root, store=store, spec_relative=SPEC_RELATIVE
            ).start()
            self.assertEqual(without_phrase["status"], "COMPLETE")
            self.assertEqual(without_phrase["terminal_result"], runtime["terminal_outcome"])
            self.assertEqual(len(opener.requests), 0)
            store.close()

    def test_workbench_start_after_complete_does_not_clobber_git(self) -> None:
        runtime = json.loads(
            (
                ROOT
                / "docs/evidence/factory_v1_commissioning"
                / "a2_factory_v1_commissioning_runtime_receipt_v1.json"
            ).read_text(encoding="utf-8")
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = isolated_commissioning_root_with_bound_receipts(Path(tmp))
            store = OperationalStore(root / "ops.sqlite")
            app = FactoryApplication(root=root, store=store, spec_relative=SPEC_RELATIVE)
            first = app.start()
            self.assertEqual(first["status"], "COMPLETE")
            server = serve(app, host="127.0.0.1", port=0)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address[:2]
                conn = HTTPConnection(host, port, timeout=2)
                conn.request(
                    "POST",
                    "/",
                    body="command=START",
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                response = conn.getresponse()
                body = response.read().decode("utf-8")
                self.assertEqual(response.status, 200)
                self.assertIn("COMPLETE", body)
                self.assertIn(runtime["terminal_outcome"], body)
                conn.close()
            finally:
                server.shutdown()
                server.server_close()
            job = store.get_job("JOB-EXP-FACTORY-V1-COMMISSIONING-QUOTE-NATIVE-FREE-KEY-001")
            assert job is not None
            self.assertEqual(job["status"], "COMPLETE")
            self.assertEqual(job["terminal"], runtime["terminal_outcome"])
            store.close()

    def test_commissioning_spec_remains_selectable(self) -> None:
        spec = load_experiment_spec(ROOT, SPEC_RELATIVE)
        self.assertEqual(
            spec["capabilities"],
            ["CAP-JUPITER-FREE-KEY-QUOTE-NATIVE-BOUNDED-CAPTURE-001"],
        )
        with tempfile.TemporaryDirectory() as tmp:
            store = OperationalStore(Path(tmp) / "ops.sqlite")
            try:
                app = FactoryApplication(root=ROOT, store=store, spec_relative=SPEC_RELATIVE)
                self.assertEqual(app.spec_relative, SPEC_RELATIVE)
                model = app.read_model()
                self.assertEqual(
                    model["hypothesis"],
                    "HYP-FACTORY-V1-COMMISSIONING-QUOTE-NATIVE-FREE-KEY-V1",
                )
                self.assertIn("question", model)
                self.assertEqual(model["result"], None)
            finally:
                store.close()

    def test_workbench_exposes_hover_copy_blocks_for_exact_phrase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = OperationalStore(Path(tmp) / "ops.sqlite")
            try:
                app = FactoryApplication(root=ROOT, store=store, spec_relative=SPEC_RELATIVE)
                blocks = owner_copy_blocks(app)
                self.assertEqual(blocks[0]["id"], "exact-owner-phrase")
                self.assertEqual(blocks[0]["text"], FACTORY_V1_COMMISSIONING_AUTHORITY_PHRASE)
                self.assertIn("--authority-phrase", blocks[1]["text"])
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
                    self.assertIn("copy-block", body)
                    self.assertIn("copy-btn", body)
                    self.assertIn("Копировать", body)
                    self.assertIn("FACTORY_V1_COMMISSIONING_HYPOTHESIS_V1", body)
                    self.assertIn("pace &gt;=3s", body)
                    self.assertIn(":hover .copy-btn", body)
                    conn.close()
                finally:
                    server.shutdown()
                    server.server_close()
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
