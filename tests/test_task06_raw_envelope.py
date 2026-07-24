from __future__ import annotations

import hashlib
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.storage import (  # noqa: E402
    DEFAULT_REDACTION_POLICY,
    EnvelopeContractError,
    EnvelopeIntegrityError,
    RedactionError,
    RedactionPolicy,
    build_raw_api_event,
    canonical_redacted_bytes,
    verify_raw_api_event,
)

FIXTURE_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task06"
    / "raw_envelope_v1.json"
)


class Task06RawEnvelopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.times = {
            name: datetime.fromisoformat(value.replace("Z", "+00:00"))
            for name, value in cls.fixture["timestamps"].items()
        }

    def event_kwargs(self) -> dict[str, object]:
        return {
            "source": "synthetic.provider",
            "source_version": "fixture-1",
            "endpoint_or_method": "GET /v1/items",
            "request_identity": self.fixture["request_identity"],
            "response_body": self.fixture["success_body"],
            "response_status": "SUCCESS",
            "error_class": None,
            "event_time": self.times["event_time"],
            "observed_at": self.times["observed_at"],
            "ingested_at": self.times["ingested_at"],
            "first_reliable_available_at": self.times[
                "first_reliable_available_at"
            ],
            "available_to_strategy_at": self.times[
                "available_to_strategy_at"
            ],
            "provider_version": "fixture-1",
            "schema_version": "1.0",
            "protocol_version": "fixture-1",
            "quality_flags": "synthetic_fixture",
        }

    def test_policy_cannot_remove_default_sensitive_keys(self) -> None:
        with self.assertRaisesRegex(
            RedactionError,
            "default_sensitive_keys_cannot_be_removed",
        ):
            RedactionPolicy(sensitive_keys=frozenset({"authorization"}))

    def test_recursive_json_redaction_is_canonical_and_deterministic(self) -> None:
        actual = canonical_redacted_bytes(self.fixture["request_identity"])
        expected = json.dumps(
            self.fixture["expected_redacted_request"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self.assertEqual(actual, expected)

        reordered = {
            "headers": self.fixture["request_identity"]["headers"],
            "url": self.fixture["request_identity"]["url"],
            "method": self.fixture["request_identity"]["method"],
        }
        self.assertEqual(canonical_redacted_bytes(reordered), expected)

    def test_response_json_redacts_nested_sensitive_key(self) -> None:
        actual = canonical_redacted_bytes(self.fixture["success_body"])
        expected = json.dumps(
            self.fixture["expected_redacted_success_body"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self.assertEqual(actual, expected)

    def test_plain_text_redacts_header_query_userinfo_and_explicit_value(
        self,
    ) -> None:
        fake_value = "F" * 24
        credential_url = (
            "https://"
            + "user:"
            + fake_value
            + "@provider.invalid/path"
        )
        payload = (
            f"Authorization: Bearer {fake_value}\n"
            f"url={credential_url}"
            f"?api_key={fake_value}\n"
            f"note={fake_value}"
        )
        redacted = canonical_redacted_bytes(
            payload,
            explicit_secret_values=(fake_value,),
        ).decode("utf-8")
        self.assertNotIn(fake_value, redacted)
        self.assertIn("[REDACTED]", redacted)
        self.assertIn("https://[REDACTED]@provider.invalid", redacted)

    def test_quoted_assignment_with_spaces_is_fully_redacted(self) -> None:
        fake_value = ("P" * 16) + " with spaces"
        payload = "password = " + '"' + fake_value + '"'
        redacted = canonical_redacted_bytes(payload).decode("utf-8")
        self.assertEqual(redacted, "password = [REDACTED]")
        self.assertNotIn(fake_value, redacted)

    def test_duplicate_json_keys_fail_closed(self) -> None:
        payload = b'{"token":"FAKE","token":"SAFE"}'
        with self.assertRaisesRegex(RedactionError, "duplicate_json_key"):
            canonical_redacted_bytes(payload)

    def test_sensitive_json_key_and_incomplete_private_key_fail_closed(
        self,
    ) -> None:
        fake_value = "Q" * 24
        with self.assertRaisesRegex(
            RedactionError,
            "json_object_key_contains_sensitive_data",
        ):
            canonical_redacted_bytes(
                {f"field-{fake_value}": "value"},
                explicit_secret_values=(fake_value,),
            )

        key_header = (
            "-----BEGIN "
            + ("PRIVATE" + " KEY")
            + "-----\nsynthetic-incomplete-block"
        )
        with self.assertRaisesRegex(
            RedactionError,
            "incomplete_private_key_block",
        ):
            canonical_redacted_bytes(key_header)

    def test_non_utf8_and_short_explicit_secret_fail_closed(self) -> None:
        with self.assertRaisesRegex(
            RedactionError,
            "non_utf8_payload_requires_typed_adapter",
        ):
            canonical_redacted_bytes(b"\xff\xfe")
        with self.assertRaisesRegex(
            RedactionError,
            "explicit_secret_too_short",
        ):
            canonical_redacted_bytes("text", explicit_secret_values=("x",))

    def test_build_is_deterministic_and_hashes_redacted_bytes(self) -> None:
        first = build_raw_api_event(**self.event_kwargs())
        second = build_raw_api_event(**self.event_kwargs())
        self.assertEqual(first, second)
        self.assertEqual(first.raw_event_id, f"raw-{first.idempotency_key}")
        self.assertEqual(
            first.content_sha256,
            hashlib.sha256(first.redacted_body).hexdigest(),
        )
        self.assertNotIn(b"FAKE", first.redacted_body)
        verify_raw_api_event(first)

    def test_equivalent_timezone_instants_have_same_identity(self) -> None:
        base = self.event_kwargs()
        shifted = dict(base)
        offset = timezone(timedelta(hours=3))
        for name in (
            "event_time",
            "observed_at",
            "ingested_at",
            "first_reliable_available_at",
            "available_to_strategy_at",
        ):
            shifted[name] = base[name].astimezone(offset)
        self.assertEqual(
            build_raw_api_event(**base),
            build_raw_api_event(**shifted),
        )

    def test_changed_content_and_revision_create_new_identity(self) -> None:
        first = build_raw_api_event(**self.event_kwargs())
        changed = self.event_kwargs()
        changed["response_body"] = {"result": {"slot": 124}}
        changed["revision_number"] = 2
        changed["revision_of"] = first.raw_event_id
        second = build_raw_api_event(**changed)
        self.assertNotEqual(first.content_sha256, second.content_sha256)
        self.assertNotEqual(first.idempotency_key, second.idempotency_key)
        self.assertNotEqual(first.raw_event_id, second.raw_event_id)
        self.assertEqual(second.revision_of, first.raw_event_id)

    def test_revision_chain_is_fail_closed(self) -> None:
        invalid_first = self.event_kwargs()
        invalid_first["revision_of"] = "raw-" + ("a" * 64)
        with self.assertRaisesRegex(
            EnvelopeContractError,
            "first_revision_cannot_link_predecessor",
        ):
            build_raw_api_event(**invalid_first)

        invalid_later = self.event_kwargs()
        invalid_later["revision_number"] = 2
        with self.assertRaisesRegex(
            EnvelopeContractError,
            "later_revision_requires_predecessor",
        ):
            build_raw_api_event(**invalid_later)

    def test_every_failure_status_is_retained_including_empty_body(self) -> None:
        for case in self.fixture["error_cases"]:
            with self.subTest(status=case["status"]):
                kwargs = self.event_kwargs()
                kwargs["response_status"] = case["status"]
                kwargs["error_class"] = case["error_class"]
                kwargs["response_body"] = case["body"]
                event = build_raw_api_event(**kwargs)
                self.assertEqual(event.response_status, case["status"])
                self.assertEqual(event.error_class, case["error_class"])
                if case["status"] == "TIMEOUT":
                    self.assertEqual(event.redacted_body, b"")

    def test_success_and_error_coherence_uses_task05_model(self) -> None:
        invalid = self.event_kwargs()
        invalid["error_class"] = "UNEXPECTED_ERROR"
        with self.assertRaises(ValidationError):
            build_raw_api_event(**invalid)

        invalid = self.event_kwargs()
        invalid["response_status"] = "HTTP_ERROR"
        with self.assertRaises(ValidationError):
            build_raw_api_event(**invalid)

    def test_naive_timestamps_and_backdated_availability_fail(self) -> None:
        naive = self.event_kwargs()
        naive["observed_at"] = datetime(2026, 7, 24, 10, 0, 0)
        with self.assertRaisesRegex(
            EnvelopeContractError,
            "observed_at_must_be_timezone_aware",
        ):
            build_raw_api_event(**naive)

        backdated = self.event_kwargs()
        backdated["first_reliable_available_at"] = (
            self.times["available_to_strategy_at"] + timedelta(seconds=1)
        )
        with self.assertRaisesRegex(
            ValidationError,
            "first_reliable_availability_after_strategy_availability",
        ):
            build_raw_api_event(**backdated)

    def test_endpoint_is_redacted_but_identity_fields_reject_secrets(self) -> None:
        fake_value = "K" * 24
        kwargs = self.event_kwargs()
        kwargs["endpoint_or_method"] = (
            f"https://provider.invalid/v1?api_key={fake_value}"
        )
        kwargs["explicit_secret_values"] = (fake_value,)
        event = build_raw_api_event(**kwargs)
        self.assertNotIn(fake_value, event.endpoint_or_method)
        self.assertIn("[REDACTED]", event.endpoint_or_method)

        kwargs = self.event_kwargs()
        kwargs["source"] = f"api_key={fake_value}"
        kwargs["explicit_secret_values"] = (fake_value,)
        with self.assertRaisesRegex(
            EnvelopeContractError,
            "source_must_be_public_identifier",
        ):
            build_raw_api_event(**kwargs)

    def test_tampered_body_and_identity_are_rejected(self) -> None:
        event = build_raw_api_event(**self.event_kwargs())
        with self.assertRaisesRegex(
            EnvelopeIntegrityError,
            "redacted_body_hash_mismatch",
        ):
            verify_raw_api_event(
                event.model_copy(update={"redacted_body": b"tampered"})
            )
        with self.assertRaisesRegex(
            EnvelopeIntegrityError,
            "idempotency_key_mismatch",
        ):
            verify_raw_api_event(
                event.model_copy(update={"idempotency_key": "0" * 64})
            )

    def test_default_policy_version_is_bound_to_event(self) -> None:
        event = build_raw_api_event(**self.event_kwargs())
        self.assertEqual(
            event.redaction_version,
            DEFAULT_REDACTION_POLICY.version,
        )
        with self.assertRaisesRegex(
            EnvelopeIntegrityError,
            "redaction_policy_version_mismatch",
        ):
            verify_raw_api_event(
                event,
                policy=RedactionPolicy(version="1.1"),
            )


if __name__ == "__main__":
    unittest.main()
