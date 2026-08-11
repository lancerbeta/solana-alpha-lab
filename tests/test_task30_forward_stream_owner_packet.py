from __future__ import annotations

import json
import copy
import hashlib
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
ACCEPTANCE_PATH = (
    ROOT / "docs/evidence/task30/a13_forward_stream_owner_packet_acceptance_v1.json"
)
FACTORY_FIT_PATH = (
    ROOT / "docs/evidence/task30/a13_forward_stream_owner_packet_factory_fit_v1.json"
)
CATALOG_CORE_PATH = ROOT / "catalog/assets/core.yaml"


def replace_pointer(
    record: dict[str, object], pointer: str, replacement: object
) -> None:
    target: dict[str, object] = record
    parts = pointer.split(".")
    for part in parts[:-1]:
        target = target[part]  # type: ignore[assignment,index]
    target[parts[-1]] = replacement


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_acceptance(receipt: dict[str, object]) -> None:
    decision = receipt["decision"]  # type: ignore[index]
    authority = receipt["authority"]  # type: ignore[index]
    side_effects = receipt["side_effect_counters"]  # type: ignore[index]
    non_claims = receipt["non_claims"]  # type: ignore[index]
    assert isinstance(decision, dict)
    assert isinstance(authority, dict)
    assert isinstance(side_effects, dict)
    assert isinstance(non_claims, dict)
    assert decision["provider_selected"] is False
    assert decision["external_capture_authorized"] is False
    assert decision["trial_admissible"] is False
    assert all(value == 0 for value in authority.values())
    assert all(value == 0 for value in side_effects.values())
    assert all(value is False for value in non_claims.values())


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

    def test_policy_rejects_unknown_fields_and_disclosure_values(self) -> None:
        """Unknown authority/claim fields and secret-bearing strings fail closed."""
        config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        cases = (
            (
                lambda packet: packet.update(
                    {"notes": "https://provider.invalid/path?api_key=not-a-key"}
                ),
                "CREDENTIAL_OR_ENDPOINT_DISCLOSURE_FORBIDDEN",
            ),
            (
                lambda packet: packet["authority"].update({"external_calls": 1}),
                "AUTHORITY_FIELDS_DRIFT",
            ),
            (
                lambda packet: packet["non_claims"].update({"complete": True}),
                "NON_CLAIM_FIELDS_DRIFT",
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

    def test_candidate_subscription_filter_is_bound_to_the_frozen_pool(self) -> None:
        """A later request cannot widen the subscription away from the target pool."""
        config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        pool = "URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S"
        self.assertEqual(
            config["candidate_subscription"]["account_include"], [pool]
        )

        candidate = copy.deepcopy(config)
        candidate["candidate_subscription"]["account_include"] = [
            "DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK"
        ]
        with self.assertRaisesRegex(
            ForwardStreamOwnerPacketError, "SUBSCRIPTION_FILTER_DRIFT"
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

    def test_acceptance_factory_fit_and_catalog_bind_the_offline_boundary(self) -> None:
        """A13 cannot ship without hashes, FULL review, zero authority and discovery."""
        self.assertTrue(
            ACCEPTANCE_PATH.exists(),
            "T30-A13 must include a hash-bound acceptance receipt",
        )
        self.assertTrue(
            FACTORY_FIT_PATH.exists(),
            "T30-A13 must include a FULL_REVIEW Factory Fit receipt",
        )
        if not ACCEPTANCE_PATH.exists() or not FACTORY_FIT_PATH.exists():
            return

        acceptance = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        factory_fit = json.loads(FACTORY_FIT_PATH.read_text(encoding="utf-8"))
        catalog = yaml.safe_load(CATALOG_CORE_PATH.read_text(encoding="utf-8"))

        for binding in acceptance["artifact_bindings"].values():
            path = ROOT / binding["path"]
            self.assertEqual(binding["sha256"], sha256(path))
        assert_acceptance(acceptance)
        self.assertEqual(
            acceptance["decision"]["value"],
            "OFFLINE_FORWARD_STREAM_OWNER_PACKET_VALIDATED",
        )
        self.assertEqual(
            acceptance["project_sources_disposition"]["kind"], "NO_CHANGE"
        )
        self.assertEqual(
            acceptance["reuse_research"]["decision"], "WRAP_CANDIDATE"
        )
        self.assertEqual(factory_fit["review_scope"], "FULL_REVIEW")
        self.assertEqual(factory_fit["verdict"], "PASS_WITH_LIMITATIONS")
        self.assertEqual(
            factory_fit["reuse_first"]["outcome"], "WRAP_CANDIDATE"
        )
        self.assertEqual(
            factory_fit["product_horizon"]["now"]["candidate"],
            "ONE_EXACT_OWNER_EXTERNAL_READ_GATE",
        )

        assets = {asset["asset_id"] for asset in catalog["records"]}
        self.assertTrue(
            {
                "CONTRACT-T30-FORWARD-STREAM-OWNER-PACKET-001",
                "CONFIG-T30-FORWARD-STREAM-OWNER-PACKET-001",
                "SCHEMA-T30-FORWARD-STREAM-OWNER-PACKET-001",
                "FIXTURE-T30-FORWARD-STREAM-OWNER-PACKET-001",
                "MODULE-T30-FORWARD-STREAM-OWNER-PACKET-001",
                "SCRIPT-T30-FORWARD-STREAM-OWNER-PACKET-001",
                "REPORT-T30-FORWARD-STREAM-OWNER-PACKET-001",
                "TEST-T30-FORWARD-STREAM-OWNER-PACKET-001",
                "EVIDENCE-T30-A13-FORWARD-STREAM-OWNER-PACKET-001",
                "EVIDENCE-T30-A13-FORWARD-STREAM-OWNER-PACKET-FACTORY-FIT-001",
            }.issubset(assets)
        )

        invalid = copy.deepcopy(acceptance)
        invalid["side_effect_counters"]["provider_api_rpc_wss_calls"] = 1
        with self.assertRaises(AssertionError):
            assert_acceptance(invalid)
