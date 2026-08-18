from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.quote_native_admissible_friction_audition import (  # noqa: E402
    AUTHORITY_PHRASE,
    attempt_reservation_document,
    capture_envelope,
    classify_audition_terminal,
    evaluate_capture,
    family_closed,
    validate_policy,
)


ACCEPTANCE_PATH = (
    ROOT
    / "docs/evidence/quote_native_admissible_friction_audition"
    / "a1_quote_native_admissible_friction_audition_acceptance_v1.json"
)
RUNTIME_PATH = (
    ROOT
    / "docs/evidence/quote_native_admissible_friction_audition"
    / "a1_quote_native_admissible_friction_audition_runtime_receipt_v1.json"
)
CONFIG_PATH = ROOT / "configs/quote_native_admissible_friction_audition_v1.yaml"


class _Response:
    def __init__(self, body: bytes, *, status: int, headers: dict[str, str]) -> None:
        self._body = io.BytesIO(body)
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
        self.started = start
        self.current = start
        self.sleeps: list[float] = []

    def __call__(self) -> datetime:
        return self.current

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.current += timedelta(seconds=seconds)


def _token_rows(prefix: str) -> bytes:
    payload = [
        {
            "id": f"{prefix}{index:02d}111111111111111111111111111111111",
            "liquidity": 2_000,
            "firstPool": {"createdAt": f"2026-08-18T00:{index:02d}:00Z"},
        }
        for index in range(1, 7)
    ]
    return json.dumps(payload).encode("utf-8")


def _quote_body(amount: str, *, out_amount: str) -> bytes:
    return json.dumps(
        {
            "transaction": None,
            "requestId": "request-1",
            "inAmount": amount,
            "outAmount": out_amount,
            "router": "metis",
            "mode": "manual",
            "priceImpactPct": "0.01",
            "platformFee": None,
            "feeBps": "1",
            "routePlan": [],
        }
    ).encode("utf-8")


def _policy() -> dict[str, Any]:
    loaded = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _quote_sequence(*, reverse_out: list[str], sell_out: list[str], h3600_out: list[str]) -> list[_Response]:
    buy_out = "10000000"
    responses = [
        _Response(_token_rows("Recent"), status=200, headers={}),
        _Response(_token_rows("Traded"), status=200, headers={}),
    ]
    for index in range(12):
        responses.append(_Response(_quote_body("10000000", out_amount=buy_out), status=200, headers={}))
        responses.append(
            _Response(_quote_body(buy_out, out_amount=reverse_out[index]), status=200, headers={})
        )
    for index in range(12):
        responses.append(_Response(_quote_body(buy_out, out_amount=sell_out[index]), status=200, headers={}))
    for index in range(12):
        responses.append(_Response(_quote_body(buy_out, out_amount=h3600_out[index]), status=200, headers={}))
    return responses


def _run_capture(responses: list[_Response], *, directory: Path) -> dict[str, Any]:
    from scripts.run_quote_native_admissible_friction_audition import run_capture

    clock = _Clock(datetime(2026, 8, 18, 12, 0, tzinfo=UTC))
    return run_capture(
        authority_phrase=AUTHORITY_PHRASE,
        policy=_policy(),
        raw_root=directory / "raw",
        receipt_path=directory / "runtime.json",
        environ={"JUPITER_API_KEY": "test-key-not-a-secret"},
        preflight_fn=lambda *_args, **_kwargs: {"credential_reads": 0},
        opener=_SequenceOpener(responses),
        clock=clock,
        sleeper=clock.sleep,
    )


class CaptureEnvelopeTests(unittest.TestCase):
    def test_envelope_binds_observed_at_and_body_hash(self) -> None:
        envelope = capture_envelope(
            observation_id="RECENT_1:10000000:BUY_T0",
            observed_at="2026-08-18T12:00:03Z",
            body_sha256="a" * 64,
        )
        self.assertEqual(envelope["schema"], "smial.quote-native-admissible-friction-audition.capture-envelope")
        tampered = capture_envelope(
            observation_id="RECENT_1:10000000:BUY_T0",
            observed_at="2026-08-18T12:00:04Z",
            body_sha256="a" * 64,
        )
        self.assertNotEqual(envelope["envelope_sha256"], tampered["envelope_sha256"])

    def test_reservation_is_hashed_before_credential_read(self) -> None:
        reservation = attempt_reservation_document(
            started_at="2026-08-18T12:00:00Z",
            policy_sha256="b" * 64,
        )
        self.assertEqual(reservation["credential_reads"], 0)
        capture = evaluate_capture(
            reservation=reservation,
            consumed_rows=[
                {
                    "observation_id": "DISCOVERY:RECENT",
                    "observed_at": "2026-08-18T12:00:03Z",
                    "consumed_call": True,
                    "transport": {"response_sha256": "c" * 64},
                    "capture_envelope_sha256": capture_envelope(
                        observation_id="DISCOVERY:RECENT",
                        observed_at="2026-08-18T12:00:03Z",
                        body_sha256="c" * 64,
                    )["envelope_sha256"],
                }
            ],
        )
        self.assertTrue(capture["accepted"])

    def test_missing_envelope_fails_capture(self) -> None:
        reservation = attempt_reservation_document(
            started_at="2026-08-18T12:00:00Z",
            policy_sha256="b" * 64,
        )
        capture = evaluate_capture(
            reservation=reservation,
            consumed_rows=[
                {
                    "observation_id": "DISCOVERY:RECENT",
                    "observed_at": "2026-08-18T12:00:03Z",
                    "consumed_call": True,
                    "transport": {"response_sha256": "c" * 64},
                }
            ],
        )
        self.assertFalse(capture["accepted"])
        self.assertIn("CAPTURE_TIME_NOT_HASH_BOUND_AT_WRITE", capture["blockers"])


class TerminalClassificationTests(unittest.TestCase):
    def test_invalid_capture_pauses_and_does_not_close_family(self) -> None:
        terminal = classify_audition_terminal(
            capture={"accepted": False, "blockers": ["CAPTURE_TIME_NOT_HASH_BOUND_AT_WRITE"]},
            campaign={"campaign_verdict": "VARIATION_PRESENT_NOT_MECHANISM"},
            mechanism={"verdict": "DIRECTIONAL_HINT_NOT_CONFIRMATION"},
        )
        self.assertEqual(terminal, "PAUSE_CLOSE_QUOTE_NATIVE_CURRENT_ALPHA_ROUTE")
        self.assertFalse(family_closed(terminal))

    def test_sample_invalid_does_not_close_family(self) -> None:
        terminal = classify_audition_terminal(
            capture={"accepted": True},
            campaign={"campaign_verdict": "SAMPLE_INVALID_INSUFFICIENT_COMPLETE_XY"},
            mechanism={"verdict": "SAMPLE_INVALID_INSUFFICIENT_COMPLETE_XY"},
        )
        self.assertEqual(terminal, "SAMPLE_INVALID_INSUFFICIENT_COMPLETE_XY")
        self.assertFalse(family_closed(terminal))

    def test_traded_control_kill_does_not_close_family(self) -> None:
        terminal = classify_audition_terminal(
            capture={"accepted": True},
            campaign={"campaign_verdict": "VARIATION_ABSENT_ON_TRADED_CONTROL"},
            mechanism={"verdict": "MECHANISM_NOT_SUPPORTED_ON_THIS_SAMPLE"},
        )
        self.assertEqual(terminal, "SAMPLE_INVALID_TRADED_CONTROL_KILL")
        self.assertFalse(family_closed(terminal))

    def test_no_direction_closes_exact_mechanism(self) -> None:
        terminal = classify_audition_terminal(
            capture={"accepted": True},
            campaign={"campaign_verdict": "VARIATION_PRESENT_NOT_MECHANISM"},
            mechanism={"verdict": "MECHANISM_NOT_SUPPORTED_ON_THIS_SAMPLE"},
        )
        self.assertEqual(terminal, "CLOSE_EXACT_QUOTE_FRICTION_MECHANISM")
        self.assertTrue(family_closed(terminal))

    def test_directional_hint_does_not_start_move_2(self) -> None:
        terminal = classify_audition_terminal(
            capture={"accepted": True},
            campaign={"campaign_verdict": "VARIATION_PRESENT_NOT_MECHANISM"},
            mechanism={"verdict": "DIRECTIONAL_HINT_NOT_CONFIRMATION"},
        )
        self.assertEqual(terminal, "DIRECTIONAL_HINT_NOT_CONFIRMATION")
        self.assertFalse(family_closed(terminal))


class CampaignCaptureTests(unittest.TestCase):
    def test_policy_matches_owner_phrase_and_h3600_role(self) -> None:
        policy = _policy()
        validate_policy(policy, root=ROOT)
        self.assertEqual(policy["external_authority"]["owner_phrase"], AUTHORITY_PHRASE)
        self.assertEqual(policy["searchable_y_horizon_seconds"], 900)
        self.assertEqual(policy["h3600_role"], "PREDECLARED_ROBUSTNESS_NOT_SEARCHABLE_Y")

    def test_fresh_campaign_writes_hash_bound_reservation_and_envelopes(self) -> None:
        reverse = [str(9_900_000 - index * 10_000) for index in range(12)]
        sell = [str(9_800_000 - index * 10_000) for index in range(12)]
        h3600 = [str(9_700_000 - index * 5_000) for index in range(12)]
        with tempfile.TemporaryDirectory() as directory:
            receipt = _run_capture(
                _quote_sequence(reverse_out=reverse, sell_out=sell, h3600_out=h3600),
                directory=Path(directory),
            )
            self.assertTrue(receipt["capture"]["accepted"])
            self.assertEqual(receipt["attempt_reservation"]["credential_reads"], 0)
            self.assertTrue(receipt["attempt_reservation"]["before_credential_read"])
            self.assertEqual(receipt["credential_reads"], 1)
            self.assertEqual(receipt["searchable_y_kind"], "SELL_H900")
            self.assertEqual(receipt["h3600_role"], "PREDECLARED_ROBUSTNESS_NOT_SEARCHABLE_Y")
            self.assertTrue(receipt["mechanism"]["scored"])
            self.assertEqual(receipt["mechanism"]["searchable_y_kind"], "SELL_H900")
            self.assertNotIn("non_claims", receipt["campaign"])
            self.assertNotIn("non_claims", receipt["mechanism"])
            self.assertNotIn("family_close", receipt["campaign"])
            self.assertNotIn("family_close", receipt["mechanism"])
            for cell in receipt["mechanism"]["cells"]:
                self.assertIn("h900_terminal", cell)
                self.assertNotIn("h3600_terminal", cell)
            consumed = [
                row
                for row in receipt["discovery_observations"] + receipt["observations"]
                if row.get("consumed_call") is True
            ]
            self.assertGreaterEqual(len(consumed), 14)
            for row in consumed:
                expected = capture_envelope(
                    observation_id=str(row["observation_id"]),
                    observed_at=str(row["observed_at"]),
                    body_sha256=str(row["transport"]["response_sha256"]),
                )
                self.assertEqual(row["capture_envelope_sha256"], expected["envelope_sha256"])
            self.assertNotIn("test-key-not-a-secret", json.dumps(receipt))
            self.assertEqual(
                receipt["terminal_outcome"],
                "DIRECTIONAL_HINT_NOT_CONFIRMATION",
            )
            self.assertFalse(receipt["family_close"])
            self.assertGreaterEqual(receipt["campaign"]["h3600_moved_count"], 1)
            self.assertNotIn("MOVE_2", receipt["terminal_outcome"])


class AcceptanceEvidenceTests(unittest.TestCase):
    def test_acceptance_is_hash_bound_to_runtime_and_keeps_four_way_semantics(self) -> None:
        runtime = json.loads(RUNTIME_PATH.read_text(encoding="utf-8"))
        acceptance = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        self.assertTrue(runtime["capture"]["accepted"])
        self.assertEqual(runtime["terminal_outcome"], "DIRECTIONAL_HINT_NOT_CONFIRMATION")
        self.assertEqual(acceptance["terminal"], "DIRECTIONAL_HINT_NOT_CONFIRMATION")
        self.assertEqual(acceptance["capture_contract"], "VALID_CAPTURE_CONTRACT")
        self.assertFalse(acceptance["family_close"])
        self.assertFalse(acceptance["move_2_executed"])
        self.assertEqual(
            acceptance["source_runtime_receipt_sha256"],
            hashlib.sha256(RUNTIME_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            acceptance["criteria"]["observed_complete_xy"],
            runtime["campaign"]["complete_xy_count"],
        )
        self.assertEqual(
            acceptance["criteria"]["observed_time_separated"],
            runtime["campaign"]["time_separated_complete_xy_count"],
        )
        self.assertEqual(
            acceptance["criteria"]["concordant_pairs"],
            runtime["mechanism"]["concordant_pairs"],
        )
        self.assertEqual(
            acceptance["criteria"]["h3600_role"],
            "PREDECLARED_ROBUSTNESS_NOT_SEARCHABLE_Y",
        )
        self.assertEqual(
            sum(acceptance["provider_observations"]["all_http_status_counts"].values()),
            acceptance["provider_observations"]["provider_requests"],
        )
        self.assertIn("NO_MOVE_2_EXECUTED", acceptance["non_claims"])
        self.assertIn("NO_H3600_SEARCHABLE_Y", acceptance["non_claims"])
        self.assertEqual(
            acceptance["next_boundary"],
            "OWNER_DECISION_MOVE_2_FRESH_OOS_CONTRACT_OR_LEAVE_HINT_UNEXTENDED",
        )

    def test_y_equals_x_sample_invalid_does_not_close_family(self) -> None:
        same = [str(9_900_000 - index * 10_000) for index in range(12)]
        h3600 = [str(9_500_000 - index * 1_000) for index in range(12)]
        with tempfile.TemporaryDirectory() as directory:
            receipt = _run_capture(
                _quote_sequence(reverse_out=same, sell_out=same, h3600_out=h3600),
                directory=Path(directory),
            )
            self.assertTrue(receipt["capture"]["accepted"])
            self.assertIn(
                receipt["terminal_outcome"],
                {
                    "SAMPLE_INVALID_INSUFFICIENT_COMPLETE_XY",
                    "SAMPLE_INVALID_TRADED_CONTROL_KILL",
                },
            )
            self.assertFalse(receipt["family_close"])

    def test_discordant_ranks_close_exact_mechanism(self) -> None:
        reverse = [str(9_900_000 - index * 10_000) for index in range(12)]
        sell = [str(9_800_000 + index * 10_000) for index in range(12)]
        h3600 = [str(9_700_000) for _ in range(12)]
        with tempfile.TemporaryDirectory() as directory:
            receipt = _run_capture(
                _quote_sequence(reverse_out=reverse, sell_out=sell, h3600_out=h3600),
                directory=Path(directory),
            )
            self.assertTrue(receipt["capture"]["accepted"])
            self.assertEqual(receipt["campaign"]["campaign_verdict"], "VARIATION_PRESENT_NOT_MECHANISM")
            self.assertEqual(receipt["terminal_outcome"], "CLOSE_EXACT_QUOTE_FRICTION_MECHANISM")
            self.assertTrue(receipt["family_close"])


    def test_tampered_envelope_does_not_score_mechanism_or_campaign(self) -> None:
        reverse = [str(9_900_000 - index * 10_000) for index in range(12)]
        sell = [str(9_800_000 - index * 10_000) for index in range(12)]
        h3600 = [str(9_700_000 - index * 5_000) for index in range(12)]
        from solana_alpha_lab import quote_native_admissible_friction_audition as audition

        original = audition._attach_envelopes

        def corrupt(
            rows: list[dict[str, object]],
            envelopes: dict[str, str],
        ) -> list[dict[str, object]]:
            attached = original(rows, envelopes)
            for row in attached:
                if row.get("capture_envelope_sha256"):
                    row["capture_envelope_sha256"] = "0" * 64
            return attached

        audition._attach_envelopes = corrupt  # type: ignore[method-assign]
        try:
            with tempfile.TemporaryDirectory() as directory:
                receipt = _run_capture(
                    _quote_sequence(reverse_out=reverse, sell_out=sell, h3600_out=h3600),
                    directory=Path(directory),
                )
        finally:
            audition._attach_envelopes = original  # type: ignore[method-assign]
        self.assertFalse(receipt["capture"]["accepted"])
        self.assertEqual(
            receipt["terminal_outcome"],
            "PAUSE_CLOSE_QUOTE_NATIVE_CURRENT_ALPHA_ROUTE",
        )
        self.assertFalse(receipt["family_close"])
        self.assertEqual(receipt["mechanism"]["verdict"], "NOT_SCORED_INVALID_CAPTURE")
        self.assertFalse(receipt["mechanism"]["scored"])
        self.assertNotIn("concordant_pairs", receipt["mechanism"])
        self.assertNotIn("cells", receipt["mechanism"])
        self.assertEqual(
            receipt["campaign"]["campaign_verdict"],
            "NOT_SCORED_INVALID_CAPTURE",
        )
        self.assertNotIn("complete_xy_count", receipt["campaign"])
        self.assertNotIn("non_claims", receipt["campaign"])
        self.assertNotIn("non_claims", receipt["mechanism"])


    def test_searchable_y_observations_drop_h3600(self) -> None:
        from solana_alpha_lab.quote_native_admissible_friction_audition import (
            searchable_y_observations,
        )

        rows = [
            {"kind": "BUY_T0"},
            {"kind": "REVERSE_T0"},
            {"kind": "SELL_H900"},
            {"kind": "SELL_H3600"},
            {"kind": "DISCOVERY_RECENT"},
        ]
        kinds = [str(row["kind"]) for row in searchable_y_observations(rows)]
        self.assertEqual(kinds, ["BUY_T0", "REVERSE_T0", "SELL_H900"])
        self.assertNotIn("SELL_H3600", kinds)

    def test_typed_stop_does_not_publish_complete_xy_count(self) -> None:
        from scripts.run_quote_native_admissible_friction_audition import run_capture

        clock = _Clock(datetime(2026, 8, 18, 12, 0, tzinfo=UTC))
        with tempfile.TemporaryDirectory() as directory:
            receipt = run_capture(
                authority_phrase=AUTHORITY_PHRASE,
                policy=_policy(),
                raw_root=Path(directory) / "raw",
                receipt_path=Path(directory) / "runtime.json",
                environ={},
                preflight_fn=lambda *_args, **_kwargs: {"credential_reads": 0},
                opener=_SequenceOpener([]),
                clock=clock,
                sleeper=clock.sleep,
            )
        self.assertFalse(receipt["capture"]["accepted"])
        self.assertEqual(receipt["campaign"]["campaign_verdict"], "NOT_SCORED_TYPED_STOP")
        self.assertNotIn("complete_xy_count", receipt["campaign"])
        self.assertEqual(receipt["mechanism"]["verdict"], "NOT_SCORED_TYPED_STOP")
        self.assertFalse(receipt["mechanism"]["scored"])
        self.assertNotIn("concordant_pairs", receipt["mechanism"])

    def test_rate_limit_after_valid_capture_does_not_score_mechanism(self) -> None:
        responses = [
            _Response(_token_rows("Recent"), status=200, headers={}),
            _Response(_token_rows("Traded"), status=200, headers={}),
            _Response(b'{"error":"rate limited"}', status=429, headers={}),
        ]
        with tempfile.TemporaryDirectory() as directory:
            receipt = _run_capture(responses, directory=Path(directory))
        self.assertTrue(receipt["capture"]["accepted"])
        self.assertEqual(
            receipt["terminal_outcome"],
            "PAUSE_CLOSE_QUOTE_NATIVE_CURRENT_ALPHA_ROUTE",
        )
        self.assertEqual(
            receipt["campaign"]["campaign_verdict"],
            "NOT_SCORED_INCOMPLETE_TRANSPORT",
        )
        self.assertNotIn("complete_xy_count", receipt["campaign"])
        self.assertEqual(
            receipt["mechanism"]["verdict"],
            "NOT_SCORED_INCOMPLETE_TRANSPORT",
        )
        self.assertFalse(receipt["mechanism"]["scored"])
        self.assertNotIn("concordant_pairs", receipt["mechanism"])
        self.assertFalse(receipt["family_close"])


if __name__ == "__main__":
    unittest.main()
