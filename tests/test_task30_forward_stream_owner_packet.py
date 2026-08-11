from __future__ import annotations

import json
import copy
import subprocess
import sys
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task30_forward_stream_owner_packet import (
    ForwardStreamOwnerPacketError,
    evaluate_forward_stream_owner_packet,
    render_forward_stream_owner_packet,
)


CONFIG_PATH = ROOT / "configs/task30_forward_stream_owner_packet_v1.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/task30_forward_stream_owner_packet.schema.json"
FIXTURE_PATH = ROOT / "tests/fixtures/task30/forward_stream_owner_packet_v1.json"
SCRIPT_PATH = ROOT / "scripts/show_task30_forward_stream_owner_packet.py"
READOUT_PATH = ROOT / "docs/reports/task30/forward_stream_owner_packet_readout_v1.md"


def replace_pointer(
    record: dict[str, object], pointer: str, replacement: object
) -> None:
    target: dict[str, object] = record
    parts = pointer.split(".")
    for part in parts[:-1]:
        target = target[part]  # type: ignore[assignment,index]
    target[parts[-1]] = replacement


class Task30ForwardStreamOwnerPacketTests(unittest.TestCase):
    def test_policy_is_schema_valid_and_only_proposes_one_pilot(self) -> None:
        """The valid offline packet remains proposal-only and zero-authority."""
        config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

        self.assertFalse(list(Draft202012Validator(schema).iter_errors(config)))
        self.assertEqual(
            evaluate_forward_stream_owner_packet(config),
            fixture["expected_result"],
        )

    def test_policy_rejects_authority_and_truth_shortcuts(self) -> None:
        """Any attempt to widen the offline packet fails closed."""
        config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        cases = (
            (
                "provider.provider_selection",
                "SELECTED",
                "PROVIDER_SELECTION_NOT_PROPOSED",
            ),
            ("pilot_limits.connections", 2, "PILOT_LIMIT_DRIFT"),
            ("pilot_limits.subscriptions", 2, "PILOT_LIMIT_DRIFT"),
            ("pilot_limits.open_duration_seconds", 1201, "PILOT_LIMIT_DRIFT"),
            ("pilot_limits.notifications", 501, "PILOT_LIMIT_DRIFT"),
            ("execution_controls.retry", True, "RETRY_RECONNECT_FALLBACK_FORBIDDEN"),
            (
                "execution_controls.reconnect",
                True,
                "RETRY_RECONNECT_FALLBACK_FORBIDDEN",
            ),
            (
                "execution_controls.fallback",
                True,
                "RETRY_RECONNECT_FALLBACK_FORBIDDEN",
            ),
            (
                "execution_controls.monitoring_owner",
                "BACKGROUND_SCHEDULER",
                "MONITORING_OWNER_DRIFT",
            ),
            (
                "execution_controls.retention_class",
                "A3",
                "RETENTION_CLASS_DRIFT",
            ),
            (
                "execution_controls.absolute_raw_root",
                "C:/real/raw",
                "RAW_ROOT_DISCLOSURE_FORBIDDEN",
            ),
            (
                "authority.provider_api_rpc_wss_calls",
                1,
                "ZERO_AUTHORITY_REQUIRED",
            ),
            ("authority.credential_read", True, "ZERO_AUTHORITY_REQUIRED"),
            ("authority.raw_data_write", True, "ZERO_AUTHORITY_REQUIRED"),
            ("authority.cash_spend_usd", 1, "ZERO_AUTHORITY_REQUIRED"),
            (
                "target.dex_program_or_route",
                "INVENTED_PROGRAM",
                "ROUTE_INFERENCE_FORBIDDEN",
            ),
            (
                "terminal_truth.no_observation_disposition",
                "EMPTY_INTERVAL",
                "NO_OBSERVATION_PROMOTION_FORBIDDEN",
            ),
            (
                "terminal_truth.unknown_recovery.retry_before_reconciliation",
                True,
                "UNKNOWN_RECOVERY_DRIFT",
            ),
            (
                "terminal_truth.unknown_recovery.interval_projection",
                True,
                "UNKNOWN_RECOVERY_DRIFT",
            ),
            ("non_claims.empty_interval_claim", True, "PROMOTION_CLAIM_FORBIDDEN"),
            ("non_claims.complete_coverage_claim", True, "PROMOTION_CLAIM_FORBIDDEN"),
            ("non_claims.h07_h01_evidence_claim", True, "PROMOTION_CLAIM_FORBIDDEN"),
            ("non_claims.task30_trial_claim", True, "PROMOTION_CLAIM_FORBIDDEN"),
            ("non_claims.execution_claim", True, "PROMOTION_CLAIM_FORBIDDEN"),
            ("non_claims.settlement_claim", True, "PROMOTION_CLAIM_FORBIDDEN"),
            ("non_claims.pnl_claim", True, "PROMOTION_CLAIM_FORBIDDEN"),
            (
                "non_claims.numeric_netreturn_claim",
                True,
                "PROMOTION_CLAIM_FORBIDDEN",
            ),
        )
        for pointer, replacement, expected_error in cases:
            with self.subTest(pointer=pointer):
                candidate = copy.deepcopy(config)
                replace_pointer(candidate, pointer, replacement)
                with self.assertRaisesRegex(
                    ForwardStreamOwnerPacketError, expected_error
                ):
                    evaluate_forward_stream_owner_packet(candidate)

    def test_policy_rejects_secret_route_and_recovery_widening(self) -> None:
        """An owner packet cannot hide a credential, route or automatic repair."""
        config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        cases = (
            (
                lambda packet: packet["provider"].update({"api_key": "not-a-key"}),
                "CREDENTIAL_OR_ENDPOINT_DISCLOSURE_FORBIDDEN",
            ),
            (
                lambda packet: packet["provider"].update({"endpoint": "not-an-endpoint"}),
                "CREDENTIAL_OR_ENDPOINT_DISCLOSURE_FORBIDDEN",
            ),
            (
                lambda packet: packet["terminal_truth"]["unknown_recovery"].update(
                    {"automatic_reconciliation": True}
                ),
                "UNKNOWN_RECOVERY_DRIFT",
            ),
            (
                lambda packet: packet["owner_authority"].update(
                    {"future_pilot_phrase": ""}
                ),
                "OWNER_PHRASE_DRIFT",
            ),
            (
                lambda packet: packet["target"].update(
                    {"pool_address": "WRONG_POOL"}
                ),
                "TARGET_IDENTITY_DRIFT",
            ),
        )
        for mutate, expected_error in cases:
            with self.subTest(expected_error=expected_error):
                candidate = copy.deepcopy(config)
                mutate(candidate)
                with self.assertRaisesRegex(
                    ForwardStreamOwnerPacketError, expected_error
                ):
                    evaluate_forward_stream_owner_packet(candidate)

    def test_renderer_is_russian_and_never_grants_external_authority(self) -> None:
        """The human packet explains a future gate without leaking an execution path."""
        config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        rendered = render_forward_stream_owner_packet(config)

        self.assertIn("не является сделкой", rendered)
        self.assertIn("1 200", rendered)
        self.assertIn("500", rendered)
        self.assertIn("UNKNOWN", rendered)
        self.assertIn("T30-A13P_FORWARD_STREAM_PILOT_V1", rendered)
        self.assertNotIn("ws://", rendered.lower())
        self.assertNotIn("http://", rendered.lower())
        self.assertNotIn("https://", rendered.lower())

    def test_cli_readout_matches_the_tracked_owner_packet(self) -> None:
        """The reviewed Markdown packet cannot drift from the pure renderer."""
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            check=True,
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            completed.stdout,
            READOUT_PATH.read_text(encoding="utf-8"),
        )
