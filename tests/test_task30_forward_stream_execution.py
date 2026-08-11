from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
import sys
import unittest
from collections.abc import Iterator, Mapping
from contextlib import redirect_stderr, redirect_stdout
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task30_forward_stream_execution import (  # noqa: E402
    ForwardStreamExecutionError,
    classify_task08_capture,
    execute_forward_stream_attempt,
    find_unresolved_attempts,
    prepare_forward_stream_attempt,
    validate_forward_stream_preflight,
)
from solana_alpha_lab.lifecycle_discovery_transport import WssCapture  # noqa: E402
from solana_alpha_lab.task30_forward_stream_runtime import (  # noqa: E402
    OWNER_EXECUTION_PHRASE,
)
CONFIG_PATH = ROOT / "configs/task30_forward_stream_execution_adapter_v1.yaml"
SCHEMA_PATH = (
    ROOT / "catalog/schemas/task30_forward_stream_execution_adapter.schema.json"
)
FIXTURE_PATH = (
    ROOT / "tests/fixtures/task30/forward_stream_execution_adapter_v1.json"
)
RUNTIME_CONFIG_PATH = ROOT / "configs/task30_forward_stream_runtime_harness_v1.yaml"
CLI_PATH = ROOT / "scripts/run_task30_forward_stream_capture.py"
TASK_PATH = ROOT / "docs/tasks/TASK-30-forward-stream-execution-adapter.md"
CONTRACT_PATH = (
    ROOT / "docs/contracts/task30_forward_stream_execution_adapter_contract_v1.md"
)
MODULE_PATH = ROOT / "src/solana_alpha_lab/task30_forward_stream_execution.py"
DESIGN_PATH = (
    ROOT
    / "docs/superpowers/specs/2026-08-11-task30-forward-stream-execution-adapter-design.md"
)
PLAN_PATH = (
    ROOT
    / "docs/superpowers/plans/2026-08-11-task30-forward-stream-execution-adapter.md"
)
ACCEPTANCE_PATH = (
    ROOT
    / "docs/evidence/task30/a14p_forward_stream_execution_adapter_acceptance_v1.json"
)
FACTORY_FIT_PATH = (
    ROOT
    / "docs/evidence/task30/a14p_forward_stream_execution_adapter_factory_fit_v1.json"
)
CORE_CATALOG_PATH = ROOT / "catalog/assets/core.yaml"
EXPECTED_A14P_ASSET_IDS = {
    "CONTRACT-T30-FORWARD-STREAM-EXECUTION-ADAPTER-001",
    "CONFIG-T30-FORWARD-STREAM-EXECUTION-ADAPTER-001",
    "SCHEMA-T30-FORWARD-STREAM-EXECUTION-ADAPTER-001",
    "FIXTURE-T30-FORWARD-STREAM-EXECUTION-ADAPTER-001",
    "MODULE-T30-FORWARD-STREAM-EXECUTION-ADAPTER-001",
    "SCRIPT-T30-FORWARD-STREAM-CAPTURE-001",
    "TEST-T30-FORWARD-STREAM-EXECUTION-ADAPTER-001",
    "EVIDENCE-T30-A14P-FORWARD-STREAM-EXECUTION-ADAPTER-001",
    "EVIDENCE-T30-A14P-FORWARD-STREAM-EXECUTION-FACTORY-FIT-001",
}
FROZEN_NOW = datetime(2026, 8, 11, 12, 0, 0, tzinfo=UTC)
SECOND_FRAME_AT = datetime(2026, 8, 11, 12, 0, 1, tzinfo=UTC)
FAKE_CREDENTIAL = "synthetic-" + "credential-value"


def expected_policy() -> dict[str, object]:
    return {
        "schema": "smial.task30.forward-stream-execution-adapter.policy",
        "schema_version": "1.0",
        "task_id": "TASK-30",
        "atom_id": "T30-A14P_FORWARD_STREAM_EXECUTION_ADAPTER_V1",
        "consumer": "EXACT_OWNER_FORWARD_STREAM_EXTERNAL_GATE",
        "runtime_policy": "configs/task30_forward_stream_runtime_harness_v1.yaml",
        "retention": {
            "class": "A4",
            "logical_root": "local/task30_forward_stream",
            "started_receipt": "attempt_started.json",
            "manifest": "raw_manifest.json",
            "terminal_receipt": "terminal_receipt.json",
            "create_only": True,
        },
        "credential": {
            "environment_variable": "HELIUS_API_KEY",
            "read_after_started_receipt": True,
        },
        "execution": {
            "max_attempts": 1,
            "retry": False,
            "reconnect": False,
            "fallback": False,
            "scheduler": False,
        },
        "authority": {
            "provider_api_rpc_wss_calls": 0,
            "credential_read": False,
            "raw_external_data_write": False,
        },
        "decision": "OFFLINE_EXECUTION_ADAPTER_PENDING_IMPLEMENTATION",
        "project_sources_disposition": "NO_CHANGE",
    }


def acknowledgement(
    subscription_id: int = 7, *, subscription_error: bool = False
) -> bytes:
    result: dict[str, object] = {
        "jsonrpc": "2.0",
        "id": "task30-a14-transaction-subscribe",
    }
    if subscription_error:
        result["error"] = {"code": -32000, "message": "synthetic rejection"}
    else:
        result["result"] = subscription_id
    return json.dumps(result, separators=(",", ":")).encode("utf-8")


def notification(subscription_id: int = 7, slot: int = 123) -> bytes:
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "method": "transactionNotification",
            "params": {
                "subscription": subscription_id,
                "result": {
                    "context": {"slot": slot},
                    "value": {"signature": f"sig-{slot}", "transaction": {}},
                },
            },
        },
        separators=(",", ":"),
    ).encode("utf-8")


def bounded_capture(*notifications: bytes, ack: bytes | None = None) -> WssCapture:
    return WssCapture(
        acknowledgement=ack if ack is not None else acknowledgement(),
        notifications=tuple(notifications),
        acknowledgement_observed_at=FROZEN_NOW,
        notification_observed_at=tuple(SECOND_FRAME_AT for _ in notifications),
        terminal_class="BOUND_REACHED",
        error_class=None,
        stop_reason="ELAPSED_CAP",
    )


def load_cli():
    spec = importlib.util.spec_from_file_location(
        "run_task30_forward_stream_capture", CLI_PATH
    )
    if spec is None or spec.loader is None:
        raise AssertionError("CLI module spec unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ExplodingMapping(Mapping[str, str]):
    def __getitem__(self, key: str) -> str:
        raise AssertionError("environment must not be read")

    def __iter__(self) -> Iterator[str]:
        raise AssertionError("environment must not be iterated")

    def __len__(self) -> int:
        raise AssertionError("environment length must not be read")


class RecordingMapping(Mapping[str, str]):
    def __init__(self, value: str, marker_exists) -> None:
        self.value = value
        self.marker_exists = marker_exists
        self.read_keys: list[str] = []
        self.marker_before_read = False

    def __getitem__(self, key: str) -> str:
        self.read_keys.append(key)
        self.marker_before_read = self.marker_exists()
        if key != "HELIUS_API_KEY":
            raise KeyError(key)
        return self.value

    def __iter__(self) -> Iterator[str]:
        yield "HELIUS_API_KEY"

    def __len__(self) -> int:
        return 1


class Task30ForwardStreamExecutionPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        self.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        self.validator = Draft202012Validator(self.schema)

    def assert_rejected(self, candidate: dict[str, object]) -> None:
        self.assertNotEqual(list(self.validator.iter_errors(candidate)), [])

    def test_policy_schema_and_fixture_freeze_exact_offline_contract(self) -> None:
        self.assertEqual(self.policy, expected_policy())
        self.assertEqual(self.fixture, expected_policy())
        self.assertEqual(list(self.validator.iter_errors(self.policy)), [])

    def test_schema_closes_every_object_layer(self) -> None:
        stack = [self.schema]
        object_nodes = []
        while stack:
            node = stack.pop()
            if not isinstance(node, dict):
                continue
            if node.get("type") == "object":
                object_nodes.append(node)
            stack.extend(node.values())
        self.assertGreaterEqual(len(object_nodes), 5)
        self.assertTrue(
            all(node.get("additionalProperties") is False for node in object_nodes)
        )

    def test_schema_rejects_extra_keys_and_alternate_local_bindings(self) -> None:
        mutations = []

        extra = copy.deepcopy(self.policy)
        extra["notes"] = "not allowed"
        mutations.append(extra)

        alternate_root = copy.deepcopy(self.policy)
        alternate_root["retention"]["logical_root"] = "local/elsewhere"  # type: ignore[index]
        mutations.append(alternate_root)

        alternate_environment = copy.deepcopy(self.policy)
        alternate_environment["credential"]["environment_variable"] = "OTHER_KEY"  # type: ignore[index]
        mutations.append(alternate_environment)

        for candidate in mutations:
            with self.subTest(candidate=candidate):
                self.assert_rejected(candidate)

    def test_schema_rejects_type_confusion_and_any_offline_authority(self) -> None:
        mutations = []

        boolean_attempts = copy.deepcopy(self.policy)
        boolean_attempts["execution"]["max_attempts"] = True  # type: ignore[index]
        mutations.append(boolean_attempts)

        for key, value in (
            ("provider_api_rpc_wss_calls", 1),
            ("credential_read", True),
            ("raw_external_data_write", True),
        ):
            candidate = copy.deepcopy(self.policy)
            candidate["authority"][key] = value  # type: ignore[index]
            mutations.append(candidate)

        for candidate in mutations:
            with self.subTest(candidate=candidate):
                self.assert_rejected(candidate)


class Task30ForwardStreamExecutionPreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        (self.root / ".gitignore").write_text("local/\n", encoding="utf-8")
        self.raw_root = self.root / "local/task30_forward_stream"
        self.execution_config = expected_policy()
        self.runtime_config = yaml.safe_load(
            RUNTIME_CONFIG_PATH.read_text(encoding="utf-8")
        )

    @staticmethod
    def _never_called(calls: dict[str, int], key: str):
        def fail(*args: object, **kwargs: object) -> object:
            calls[key] += 1
            raise AssertionError(f"{key} must not be called")

        return fail

    def test_wrong_authority_fails_before_credential_transport_or_write(self) -> None:
        calls = {"credential": 0, "transport": 0}
        with self.assertRaisesRegex(
            ForwardStreamExecutionError, "PILOT_NOT_AUTHORIZED"
        ):
            execute_forward_stream_attempt(
                self.execution_config,
                self.runtime_config,
                authority_phrase="WRONG",
                repository_root=self.root,
                raw_root=self.raw_root,
                credential_loader=self._never_called(calls, "credential"),
                wss_exchange=self._never_called(calls, "transport"),
                clock=lambda: FROZEN_NOW,
                nonce_factory=lambda: "a1b2c3d4",
            )
        self.assertEqual(calls, {"credential": 0, "transport": 0})
        self.assertFalse(self.raw_root.exists())

    def test_preflight_is_pure_and_returns_only_safe_bindings(self) -> None:
        receipt = validate_forward_stream_preflight(
            self.execution_config,
            self.runtime_config,
            authority_phrase=OWNER_EXECUTION_PHRASE,
            repository_root=self.root,
            raw_root=self.raw_root,
        )
        self.assertEqual(receipt["result"], "PREFLIGHT_PASS")
        self.assertEqual(receipt["credential_read"], False)
        self.assertEqual(receipt["network_calls"], 0)
        self.assertEqual(receipt["logical_root"], "local/task30_forward_stream")
        self.assertFalse(self.raw_root.exists())

    def test_unresolved_attempt_blocks_next_attempt(self) -> None:
        first = prepare_forward_stream_attempt(
            self.execution_config,
            self.runtime_config,
            authority_phrase=OWNER_EXECUTION_PHRASE,
            repository_root=self.root,
            raw_root=self.raw_root,
            now=FROZEN_NOW,
            nonce="a1b2c3d4",
        )
        self.assertEqual(find_unresolved_attempts(self.raw_root), (first.run_id,))
        marker = json.loads(
            (first.run_root / "attempt_started.json").read_text(encoding="utf-8")
        )
        self.assertEqual(marker["state"], "UNRESOLVED_EXTERNAL_ATTEMPT")
        self.assertEqual(marker["run_id"], first.run_id)
        self.assertNotIn("api-key", json.dumps(marker).casefold())

        with self.assertRaisesRegex(
            ForwardStreamExecutionError, "UNRESOLVED_PRIOR_ATTEMPT"
        ):
            prepare_forward_stream_attempt(
                self.execution_config,
                self.runtime_config,
                authority_phrase=OWNER_EXECUTION_PHRASE,
                repository_root=self.root,
                raw_root=self.raw_root,
                now=FROZEN_NOW,
                nonce="e5f6a7b8",
            )

    def test_preflight_rejects_path_and_policy_widening(self) -> None:
        cases: list[tuple[str, Path, Path, dict[str, object]]] = []

        relative_root = Path("relative-repository")
        cases.append(
            (
                "REPOSITORY_ROOT_ABSOLUTE_REQUIRED",
                relative_root,
                relative_root / "local/task30_forward_stream",
                self.execution_config,
            )
        )

        cases.append(
            (
                "RAW_ROOT_IDENTITY_DRIFT",
                self.root,
                self.root / "local/other",
                self.execution_config,
            )
        )

        confused = copy.deepcopy(self.execution_config)
        confused["execution"]["max_attempts"] = True  # type: ignore[index]
        cases.append(
            (
                "EXECUTION_POLICY_DRIFT",
                self.root,
                self.raw_root,
                confused,
            )
        )

        for code, repository_root, raw_root, config in cases:
            with self.subTest(code=code):
                with self.assertRaisesRegex(ForwardStreamExecutionError, code):
                    validate_forward_stream_preflight(
                        config,
                        self.runtime_config,
                        authority_phrase=OWNER_EXECUTION_PHRASE,
                        repository_root=repository_root,
                        raw_root=raw_root,
                    )

    def test_attempt_rejects_naive_time_unsafe_nonce_and_forged_terminal(self) -> None:
        for now, nonce, code in (
            (datetime(2026, 8, 11, 12, 0, 0), "a1b2c3d4", "START_TIME_UTC_REQUIRED"),
            (FROZEN_NOW, "../unsafe", "NONCE_INVALID"),
        ):
            with self.subTest(code=code):
                with self.assertRaisesRegex(ForwardStreamExecutionError, code):
                    prepare_forward_stream_attempt(
                        self.execution_config,
                        self.runtime_config,
                        authority_phrase=OWNER_EXECUTION_PHRASE,
                        repository_root=self.root,
                        raw_root=self.raw_root,
                        now=now,
                        nonce=nonce,
                    )
                self.assertFalse(self.raw_root.exists())

        first = prepare_forward_stream_attempt(
            self.execution_config,
            self.runtime_config,
            authority_phrase=OWNER_EXECUTION_PHRASE,
            repository_root=self.root,
            raw_root=self.raw_root,
            now=FROZEN_NOW,
            nonce="a1b2c3d4",
        )
        terminal = {
            "schema": "smial.task30.forward-stream-terminal-receipt",
            "schema_version": "1.0",
            "run_id": first.run_id,
            "logical_run_root": first.logical_run_root,
            "state": "TERMINAL",
            "terminal_state": "RETENTION_FAILED_STOP",
        }
        (first.run_root / "terminal_receipt.json").write_text(
            json.dumps(terminal), encoding="utf-8"
        )
        self.assertEqual(find_unresolved_attempts(self.raw_root), (first.run_id,))
        with self.assertRaisesRegex(
            ForwardStreamExecutionError, "UNRESOLVED_PRIOR_ATTEMPT"
        ):
            prepare_forward_stream_attempt(
                self.execution_config,
                self.runtime_config,
                authority_phrase=OWNER_EXECUTION_PHRASE,
                repository_root=self.root,
                raw_root=self.raw_root,
                now=FROZEN_NOW,
                nonce="a1b2c3d4",
            )

    def test_preflight_rejects_symlink_component(self) -> None:
        local_component = self.root / "local"
        original_is_symlink = Path.is_symlink

        def synthetic_symlink(path: Path) -> bool:
            if path == local_component:
                return True
            return original_is_symlink(path)

        with patch.object(Path, "is_symlink", synthetic_symlink):
            with self.assertRaisesRegex(
                ForwardStreamExecutionError, "RAW_ROOT_SYMLINK_FORBIDDEN"
            ):
                validate_forward_stream_preflight(
                    self.execution_config,
                    self.runtime_config,
                    authority_phrase=OWNER_EXECUTION_PHRASE,
                    repository_root=self.root,
                    raw_root=self.raw_root,
                )


class Task30ForwardStreamExecutionRetentionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        (self.root / ".gitignore").write_text("local/\n", encoding="utf-8")
        self.raw_root = self.root / "local/task30_forward_stream"
        self.execution_config = expected_policy()
        self.runtime_config = yaml.safe_load(
            RUNTIME_CONFIG_PATH.read_text(encoding="utf-8")
        )

    def execute(self, exchange, *, credential_loader=None) -> dict[str, object]:
        return execute_forward_stream_attempt(
            self.execution_config,
            self.runtime_config,
            authority_phrase=OWNER_EXECUTION_PHRASE,
            repository_root=self.root,
            raw_root=self.raw_root,
            credential_loader=(
                credential_loader
                if credential_loader is not None
                else lambda name: FAKE_CREDENTIAL
            ),
            wss_exchange=exchange,
            clock=lambda: FROZEN_NOW,
            nonce_factory=lambda: "a1b2c3d4",
        )

    def test_success_retains_exact_bytes_timestamps_hashes_and_safe_receipt(self) -> None:
        calls: list[dict[str, object]] = []
        capture = bounded_capture(notification())

        def exchange(request, **limits):
            calls.append({"request": request.safe_receipt(), **limits})
            return capture

        receipt = self.execute(exchange)
        self.assertEqual(
            receipt["terminal_state"], "OBSERVATION_RETAINED_TECHNICAL_ONLY"
        )
        self.assertEqual(receipt["notifications"], 1)
        self.assertEqual(
            receipt["logical_run_root"],
            f"local/task30_forward_stream/run={receipt['run_id']}",
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["max_open_seconds"], 540)
        self.assertEqual(calls[0]["max_stream_bytes"], 1_000_000)
        self.assertEqual(calls[0]["max_notifications"], 500)

        run_root = self.raw_root / f"run={receipt['run_id']}"
        manifest = json.loads(
            (run_root / "raw_manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            [item["observed_at"] for item in manifest["raw_objects"]],
            ["2026-08-11T12:00:00Z", "2026-08-11T12:00:01Z"],
        )
        for item in manifest["raw_objects"]:
            body = (run_root / item["path"]).read_bytes()
            self.assertEqual(item["bytes"], len(body))
            self.assertEqual(item["sha256"], hashlib.sha256(body).hexdigest())

        all_local_bytes = b"".join(
            path.read_bytes() for path in run_root.rglob("*") if path.is_file()
        )
        self.assertNotIn(FAKE_CREDENTIAL.encode(), all_local_bytes)
        self.assertNotIn(FAKE_CREDENTIAL, json.dumps(receipt))
        self.assertNotIn(FAKE_CREDENTIAL, repr(receipt))

    def test_valid_terminal_consumes_gate_and_forged_variants_are_unresolved(
        self,
    ) -> None:
        receipt = self.execute(
            lambda request, **limits: bounded_capture(notification())
        )
        run_id = str(receipt["run_id"])
        run_root = self.raw_root / f"run={run_id}"
        terminal_path = run_root / "terminal_receipt.json"
        original = json.loads(terminal_path.read_text(encoding="utf-8"))
        self.assertEqual(find_unresolved_attempts(self.raw_root), ())

        with self.assertRaisesRegex(
            ForwardStreamExecutionError, "PRIOR_ATTEMPT_REQUIRES_NEW_GATE"
        ):
            prepare_forward_stream_attempt(
                self.execution_config,
                self.runtime_config,
                authority_phrase=OWNER_EXECUTION_PHRASE,
                repository_root=self.root,
                raw_root=self.raw_root,
                now=FROZEN_NOW,
                nonce="deadbeef",
            )

        forged_variants = []
        type_confused = copy.deepcopy(original)
        type_confused["notifications"] = True
        forged_variants.append(type_confused)
        widened = copy.deepcopy(original)
        widened["notes"] = "synthetic extra field"
        forged_variants.append(widened)
        reversed_time = copy.deepcopy(original)
        reversed_time["terminal_at"] = "2026-08-11T11:59:59Z"
        forged_variants.append(reversed_time)
        malformed_manifest = copy.deepcopy(original)
        malformed_manifest["raw_manifest"]["sha256"] = "not-a-sha256"
        forged_variants.append(malformed_manifest)

        for forged in forged_variants:
            with self.subTest(forged=forged):
                terminal_path.write_text(json.dumps(forged), encoding="utf-8")
                self.assertEqual(find_unresolved_attempts(self.raw_root), (run_id,))

        terminal_path.write_text(json.dumps(original), encoding="utf-8")
        self.assertEqual(find_unresolved_attempts(self.raw_root), ())

        raw_object_path = run_root / "notifications/000001.json"
        raw_object = raw_object_path.read_bytes()
        raw_object_path.write_bytes(b'{"synthetic":"tampered"}')
        self.assertEqual(find_unresolved_attempts(self.raw_root), (run_id,))
        raw_object_path.write_bytes(raw_object)
        self.assertEqual(find_unresolved_attempts(self.raw_root), ())

    def test_credential_is_read_only_after_started_marker(self) -> None:
        observed = {"reads": 0, "marker_before_read": False}

        def credential_loader(name: str) -> str:
            observed["reads"] += 1
            observed["marker_before_read"] = bool(
                tuple(self.raw_root.glob("run=*/attempt_started.json"))
            )
            self.assertEqual(name, "HELIUS_API_KEY")
            return FAKE_CREDENTIAL

        receipt = self.execute(
            lambda request, **limits: bounded_capture(),
            credential_loader=credential_loader,
        )
        self.assertEqual(receipt["terminal_state"], "NO_OBSERVED_TX_NO_EMPTY_CLAIM")
        self.assertEqual(observed, {"reads": 1, "marker_before_read": True})

    def test_missing_credential_closes_attempt_without_transport(self) -> None:
        transport_calls = 0

        def missing(name: str) -> str:
            raise KeyError(name)

        def exchange(*args, **kwargs):
            nonlocal transport_calls
            transport_calls += 1
            raise AssertionError("transport must not run")

        receipt = self.execute(exchange, credential_loader=missing)
        self.assertEqual(receipt["terminal_state"], "CONNECTION_OR_AUTH_REJECTED")
        self.assertEqual(transport_calls, 0)
        self.assertEqual(find_unresolved_attempts(self.raw_root), ())

    def test_unexpected_credential_loader_failure_stays_unresolved_and_sanitized(
        self,
    ) -> None:
        transport_calls = 0

        def unexpected(name: str) -> str:
            raise RuntimeError(f"synthetic loader bug {FAKE_CREDENTIAL}")

        def exchange(*args, **kwargs):
            nonlocal transport_calls
            transport_calls += 1
            raise AssertionError("transport must not run")

        with self.assertRaisesRegex(
            ForwardStreamExecutionError, "UNCLASSIFIED_LOCAL_FAILURE"
        ) as caught:
            self.execute(exchange, credential_loader=unexpected)
        self.assertEqual(transport_calls, 0)
        self.assertNotIn(FAKE_CREDENTIAL, str(caught.exception))
        self.assertNotIn(FAKE_CREDENTIAL, repr(caught.exception))
        self.assertEqual(len(find_unresolved_attempts(self.raw_root)), 1)
        run_root = next(self.raw_root.glob("run=*"))
        self.assertTrue((run_root / "attempt_started.json").is_file())
        self.assertFalse((run_root / "terminal_receipt.json").exists())

    def test_nonbounded_transport_is_unknown_after_cap_enforcement(self) -> None:
        capture = WssCapture(
            acknowledgement=acknowledgement(),
            notifications=(notification(),),
            acknowledgement_observed_at=FROZEN_NOW,
            notification_observed_at=(SECOND_FRAME_AT,),
            terminal_class="REMOTE_CLOSED",
            error_class="wss_remote_closed",
            stop_reason="REMOTE_CLOSED",
        )
        classification = classify_task08_capture(self.runtime_config, capture)
        self.assertEqual(classification["terminal_state"], "TRANSPORT_LOST_UNKNOWN")
        self.assertTrue(classification["unknown"])
        self.assertFalse(classification["retry"])
        self.assertFalse(classification["reconnect"])

        receipt = self.execute(lambda request, **limits: capture)
        self.assertEqual(receipt["terminal_state"], "TRANSPORT_LOST_UNKNOWN")
        self.assertTrue(receipt["unknown"])
        self.assertEqual(find_unresolved_attempts(self.raw_root), ())

    def test_caps_reject_oversized_capture_before_classification(self) -> None:
        oversized = WssCapture(
            acknowledgement=b"x" * 100_001,
            notifications=(),
            acknowledgement_observed_at=FROZEN_NOW,
            notification_observed_at=(),
            terminal_class="RESPONSE_TOO_LARGE",
            error_class="wss_frame_too_large",
            stop_reason="FRAME_LIMIT",
        )
        with self.assertRaisesRegex(
            ForwardStreamExecutionError, "ACK_FRAME_CAP_EXCEEDED"
        ):
            classify_task08_capture(self.runtime_config, oversized)

    def test_execute_rejects_oversized_capture_before_raw_publication(self) -> None:
        oversized = WssCapture(
            acknowledgement=b"x" * 100_001,
            notifications=(),
            acknowledgement_observed_at=FROZEN_NOW,
            notification_observed_at=(),
            terminal_class="RESPONSE_TOO_LARGE",
            error_class="wss_frame_too_large",
            stop_reason="FRAME_LIMIT",
        )
        with self.assertRaisesRegex(
            ForwardStreamExecutionError, "ACK_FRAME_CAP_EXCEEDED"
        ):
            self.execute(lambda request, **limits: oversized)

        run_root = next(self.raw_root.glob("run=*"))
        self.assertTrue((run_root / "attempt_started.json").is_file())
        self.assertFalse((run_root / "acknowledgement.json").exists())
        self.assertFalse((run_root / "raw_manifest.json").exists())
        self.assertFalse((run_root / "terminal_receipt.json").exists())
        self.assertEqual(len(find_unresolved_attempts(self.raw_root)), 1)

    def test_subscription_error_is_closed_but_identity_drift_stays_unresolved(self) -> None:
        rejected = self.execute(
            lambda request, **limits: bounded_capture(
                ack=acknowledgement(subscription_error=True)
            )
        )
        self.assertEqual(rejected["terminal_state"], "SUBSCRIPTION_REJECTED")
        self.assertEqual(find_unresolved_attempts(self.raw_root), ())

        second_root = Path(self.temporary.name).resolve() / "second"
        second_root.mkdir()
        (second_root / ".gitignore").write_text("local/\n", encoding="utf-8")
        self.root = second_root
        self.raw_root = second_root / "local/task30_forward_stream"
        with self.assertRaisesRegex(
            ForwardStreamExecutionError, "NOTIFICATION_SUBSCRIPTION_DRIFT"
        ):
            self.execute(
                lambda request, **limits: bounded_capture(notification(8))
            )
        self.assertEqual(len(find_unresolved_attempts(self.raw_root)), 1)
        run_root = next(self.raw_root.glob("run=*"))
        self.assertTrue((run_root / "raw_manifest.json").is_file())
        self.assertFalse((run_root / "terminal_receipt.json").exists())

    def test_raw_publication_failure_closes_only_when_terminal_receipt_is_writable(
        self,
    ) -> None:
        from solana_alpha_lab import task30_forward_stream_execution as execution

        original_publish = execution._publish_new

        def fail_ack(path: Path, body: bytes) -> None:
            if path.name == "acknowledgement.json":
                raise ForwardStreamExecutionError("CREATE_ONLY_PUBLICATION_FAILED")
            original_publish(path, body)

        with patch.object(execution, "_publish_new", fail_ack):
            receipt = self.execute(
                lambda request, **limits: bounded_capture(notification())
            )
        self.assertEqual(receipt["terminal_state"], "RETENTION_FAILED_STOP")
        self.assertEqual(find_unresolved_attempts(self.raw_root), ())

        other_root = Path(self.temporary.name).resolve() / "other"
        other_root.mkdir()
        (other_root / ".gitignore").write_text("local/\n", encoding="utf-8")
        self.root = other_root
        self.raw_root = other_root / "local/task30_forward_stream"

        def fail_raw_and_terminal(path: Path, body: bytes) -> None:
            if path.name in {"acknowledgement.json", "terminal_receipt.json"}:
                raise ForwardStreamExecutionError("CREATE_ONLY_PUBLICATION_FAILED")
            original_publish(path, body)

        with patch.object(execution, "_publish_new", fail_raw_and_terminal):
            with self.assertRaisesRegex(
                ForwardStreamExecutionError, "UNRESOLVED_EXTERNAL_ATTEMPT"
            ):
                self.execute(
                    lambda request, **limits: bounded_capture(notification())
                )
        self.assertEqual(len(find_unresolved_attempts(self.raw_root)), 1)

    def test_transport_exception_is_sanitized_unknown_and_secret_never_escapes(self) -> None:
        def fail_transport(request, **limits):
            raise RuntimeError(f"synthetic transport detail {FAKE_CREDENTIAL}")

        receipt = self.execute(fail_transport)
        rendered = json.dumps(receipt)
        self.assertEqual(receipt["terminal_state"], "TRANSPORT_LOST_UNKNOWN")
        self.assertNotIn(FAKE_CREDENTIAL, rendered)
        run_root = next(self.raw_root.glob("run=*"))
        self.assertNotIn(
            FAKE_CREDENTIAL.encode(),
            (run_root / "terminal_receipt.json").read_bytes(),
        )


class Task30ForwardStreamExecutionCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        (self.root / ".gitignore").write_text("local/\n", encoding="utf-8")
        self.raw_root = self.root / "local/task30_forward_stream"

    def invoke(self, argv, *, environ, exchange, repository_root=None):
        cli = load_cli()
        cli.ROOT = self.root if repository_root is None else repository_root
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = cli.main(argv, environ=environ, wss_exchange=exchange)
        return result, stdout.getvalue(), stderr.getvalue()

    def test_dry_run_does_not_read_key_write_or_call_transport(self) -> None:
        def fail_if_called(*args, **kwargs):
            raise AssertionError("transport must not be called")

        result, stdout, stderr = self.invoke(
            [
                "--dry-run",
                "--authority",
                OWNER_EXECUTION_PHRASE,
                "--raw-root",
                str(self.raw_root),
            ],
            environ=ExplodingMapping(),
            exchange=fail_if_called,
        )
        self.assertEqual(result, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(
            json.loads(stdout),
            {
                "credential_read": False,
                "network_calls": 0,
                "output_created": False,
                "result": "DRY_RUN_PASS",
            },
        )
        self.assertFalse(self.raw_root.exists())

    def test_execute_reads_only_named_key_after_started_marker(self) -> None:
        environment = RecordingMapping(
            FAKE_CREDENTIAL,
            lambda: bool(tuple(self.raw_root.glob("run=*/attempt_started.json"))),
        )
        result, stdout, stderr = self.invoke(
            [
                "--execute",
                "--authority",
                OWNER_EXECUTION_PHRASE,
                "--raw-root",
                str(self.raw_root),
            ],
            environ=environment,
            exchange=lambda request, **limits: bounded_capture(notification()),
        )
        self.assertEqual(result, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(environment.read_keys, ["HELIUS_API_KEY"])
        self.assertTrue(environment.marker_before_read)
        output = json.loads(stdout)
        self.assertEqual(
            output["terminal_state"], "OBSERVATION_RETAINED_TECHNICAL_ONLY"
        )
        self.assertNotIn(FAKE_CREDENTIAL, stdout)
        self.assertNotIn(notification().decode("utf-8"), stdout)

    def test_cli_rejects_ambiguous_modes_and_unknown_clock_override(self) -> None:
        cli = load_cli()
        cases = (
            [],
            ["--dry-run", "--execute"],
            ["--execute", "--clock", "2026-08-11T12:00:00Z"],
        )
        for argv in cases:
            with self.subTest(argv=argv):
                with redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as context:
                        cli.main(
                            argv,
                            environ=ExplodingMapping(),
                            wss_exchange=lambda *args, **kwargs: None,
                        )
                self.assertEqual(context.exception.code, 2)

    def test_cli_rejects_relative_root_or_wrong_authority_before_environment(self) -> None:
        cases = (
            (
                [
                    "--dry-run",
                    "--authority",
                    OWNER_EXECUTION_PHRASE,
                    "--raw-root",
                    "relative/local/task30_forward_stream",
                ],
                "REPOSITORY_ROOT_ABSOLUTE_REQUIRED",
            ),
            (
                [
                    "--execute",
                    "--authority",
                    "WRONG",
                    "--raw-root",
                    str(self.raw_root),
                ],
                "PILOT_NOT_AUTHORIZED",
            ),
        )
        for argv, code in cases:
            with self.subTest(code=code):
                result, stdout, stderr = self.invoke(
                    argv,
                    environ=ExplodingMapping(),
                    exchange=lambda *args, **kwargs: None,
                    repository_root=(
                        Path("relative")
                        if code == "REPOSITORY_ROOT_ABSOLUTE_REQUIRED"
                        else self.root
                    ),
                )
                self.assertEqual(result, 2)
                self.assertEqual(stderr, "")
                self.assertEqual(json.loads(stdout)["error"], code)
                self.assertFalse(self.raw_root.exists())


class Task30ForwardStreamExecutionAcceptanceTests(unittest.TestCase):
    def test_acceptance_binds_exact_artifacts_and_zero_external_authority(self) -> None:
        acceptance = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(acceptance["validation_status"], "PASS_WITH_LIMITATIONS")
        self.assertEqual(acceptance["state_change"], "NONE")
        self.assertEqual(
            acceptance["decision"],
            {
                "value": "READY_FOR_EXACT_OWNER_EXTERNAL_GATE_WITH_LIMITATIONS",
                "external_capture_authorized": False,
                "raw_external_data_collected": False,
                "task30_trial_admissible": False,
            },
        )
        self.assertEqual(
            acceptance["project_sources_disposition"], {"kind": "NO_CHANGE"}
        )
        self.assertTrue(
            all(value == 0 for value in acceptance["authority"].values())
        )
        self.assertTrue(
            all(value == 0 for value in acceptance["side_effect_counters"].values())
        )

        expected_paths = {
            "task": TASK_PATH,
            "contract": CONTRACT_PATH,
            "configuration": CONFIG_PATH,
            "schema": SCHEMA_PATH,
            "fixture": FIXTURE_PATH,
            "module": MODULE_PATH,
            "runner": CLI_PATH,
            "test": Path(__file__),
            "design": DESIGN_PATH,
            "plan": PLAN_PATH,
            "factory_fit": FACTORY_FIT_PATH,
        }
        self.assertEqual(set(acceptance["artifact_bindings"]), set(expected_paths))
        for role, path in expected_paths.items():
            with self.subTest(role=role):
                binding = acceptance["artifact_bindings"][role]
                self.assertEqual(binding["path"], path.relative_to(ROOT).as_posix())
                self.assertEqual(
                    binding["sha256"], hashlib.sha256(path.read_bytes()).hexdigest()
                )

    def test_factory_fit_is_full_and_preserves_external_stop_boundary(self) -> None:
        review = json.loads(FACTORY_FIT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(review["review_scope"], "FULL_REVIEW")
        self.assertEqual(review["verdict"], "PASS_WITH_LIMITATIONS")
        self.assertEqual(review["state_change"], "NONE")
        for dimension in (
            "mission",
            "flexibility",
            "compatibility_history",
            "efficiency",
            "research_truth",
            "secret_handling",
            "owner_operability",
            "monitoring_recovery",
            "reuse_first",
            "red_team",
        ):
            with self.subTest(dimension=dimension):
                self.assertIn(
                    review[dimension]["result"], {"PASS", "PASS_WITH_LIMITATIONS"}
                )
        self.assertEqual(
            review["execution_to_cashflow"]["result"], "NOT_APPLICABLE_YET"
        )
        self.assertEqual(
            review["product_horizon"]["now"]["candidate"],
            "ONE_EXACT_OWNER_FORWARD_STREAM_EXTERNAL_GATE",
        )

    def test_catalog_registers_only_nine_durable_a14p_assets_with_exact_hashes(
        self,
    ) -> None:
        catalog = yaml.safe_load(CORE_CATALOG_PATH.read_text(encoding="utf-8"))
        records = {
            record["asset_id"]: record
            for record in catalog["records"]
            if record["asset_id"] in EXPECTED_A14P_ASSET_IDS
        }
        self.assertEqual(set(records), EXPECTED_A14P_ASSET_IDS)
        for asset_id, record in records.items():
            with self.subTest(asset_id=asset_id):
                self.assertEqual(record["consumers"], ["TASK-30", "FACTORY-001"])
                path = ROOT / record["location"]["repository_path"]
                self.assertEqual(
                    record["integrity"],
                    {"kind": "sha256", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()},
                )

if __name__ == "__main__":
    unittest.main()
