"""Deterministic redaction and raw-envelope preparation for TASK-06."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TypeAlias

from solana_alpha_lab.contracts.schema_v1 import RawApiEvent, RawResponseStatus

JsonScalar: TypeAlias = None | bool | int | float | str
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
PayloadValue: TypeAlias = bytes | str | JsonValue

REDACTION_MARKER = "[REDACTED]"
USER_PATH_MARKER = "[REDACTED_USER_PATH]"
PRIVATE_KEY_MARKER = "[REDACTED_PRIVATE_KEY]"


class EnvelopeContractError(ValueError):
    """The caller supplied an incoherent public envelope claim."""


class RedactionError(EnvelopeContractError):
    """The payload cannot safely cross the redaction boundary."""


class EnvelopeIntegrityError(EnvelopeContractError):
    """A prepared event no longer matches its deterministic identity."""


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


DEFAULT_SENSITIVE_KEYS = frozenset(
    _normalize_key(value)
    for value in (
        "authorization",
        "proxy_authorization",
        "x_api_key",
        "api_key",
        "apikey",
        "access_token",
        "auth_token",
        "refresh_token",
        "token",
        "password",
        "passwd",
        "secret",
        "client_secret",
        "cookie",
        "set_cookie",
        "private_key",
        "seed",
        "seed_phrase",
        "mnemonic",
    )
)


@dataclass(frozen=True, slots=True)
class RedactionPolicy:
    """Versioned deterministic rules applied before hashing or storage."""

    version: str = "1.0"
    sensitive_keys: frozenset[str] = DEFAULT_SENSITIVE_KEYS
    replacement: str = REDACTION_MARKER

    def __post_init__(self) -> None:
        if re.fullmatch(r"[1-9][0-9]*[.][0-9]+", self.version) is None:
            raise RedactionError("invalid_redaction_policy_version")
        if self.replacement != REDACTION_MARKER:
            raise RedactionError("unsupported_redaction_marker")
        normalized = frozenset(_normalize_key(value) for value in self.sensitive_keys)
        if not normalized or "" in normalized:
            raise RedactionError("invalid_sensitive_key_set")
        if not DEFAULT_SENSITIVE_KEYS.issubset(normalized):
            raise RedactionError("default_sensitive_keys_cannot_be_removed")
        object.__setattr__(self, "sensitive_keys", normalized)


DEFAULT_REDACTION_POLICY = RedactionPolicy()

_SENSITIVE_ALIAS = (
    r"(?:authorization|proxy[_-]?authorization|x[_-]?api[_-]?key|"
    r"api[_-]?key|apikey|access[_-]?token|auth[_-]?token|"
    r"refresh[_-]?token|token|password|passwd|secret|client[_-]?secret|"
    r"cookie|set[_-]?cookie|private[_-]?key|seed[_-]?phrase|mnemonic)"
)
_HEADER_RE = re.compile(
    rf"(?im)\b({_SENSITIVE_ALIAS})([ \t]*:[ \t]*)([^\r\n]+)"
)
_ASSIGNMENT_RE = re.compile(
    rf"(?i)\b({_SENSITIVE_ALIAS})([ \t]*[:=][ \t]*)"
    r"(?:\"[^\"]*\"|'[^']*'|[^&\s,;}\]]+)"
)
_RESIDUAL_ASSIGNMENT_RE = re.compile(
    rf"(?i)\b{_SENSITIVE_ALIAS}[ \t]*[:=][ \t]*[\"']?"
    r"[A-Za-z0-9+/=_-]{12,}"
)
_AUTH_SCHEME_RE = re.compile(
    r"(?i)\b(Bearer|Basic)[ \t]+[A-Za-z0-9._~+/=-]+"
)
_CREDENTIAL_URL_RE = re.compile(
    r"(?i)\b(https?://)[^/\s:@]+:[^/\s@]+@"
)
_PRIVATE_KEY_LABEL = "PRIVATE" + " KEY"
_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN [A-Z0-9 ]*"
    + _PRIVATE_KEY_LABEL
    + r"-----.*?-----END [A-Z0-9 ]*"
    + _PRIVATE_KEY_LABEL
    + r"-----",
    flags=re.DOTALL,
)
_PRIVATE_KEY_HEADER_RE = re.compile(
    r"-----BEGIN [A-Z0-9 ]*" + _PRIVATE_KEY_LABEL + r"-----"
)
_WINDOWS_USER_PATH_RE = re.compile(
    r"(?i)\b[A-Z]:\\Users\\[^\\/\s]+"
)
_POSIX_USER_PATH_RE = re.compile(r"(?i)(?<![A-Za-z0-9_])/(?:home|Users)/[^/\s]+")
_PUBLIC_IDENTIFIER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}")


def _prepare_explicit_secrets(
    values: Iterable[str | bytes],
) -> tuple[str, ...]:
    prepared: set[str] = set()
    for value in values:
        if isinstance(value, bytes):
            try:
                text = value.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise RedactionError(
                    "explicit_secret_must_be_utf8"
                ) from exc
        elif isinstance(value, str):
            text = value
        else:
            raise RedactionError("explicit_secret_must_be_text")
        if len(text) < 4:
            raise RedactionError("explicit_secret_too_short")
        prepared.add(text)
    return tuple(sorted(prepared, key=lambda item: (-len(item), item)))


def _assert_text_payload(text: str) -> None:
    if any(ord(character) < 32 and character not in "\t\r\n" for character in text):
        raise RedactionError("control_character_requires_typed_adapter")


def _assert_no_residual_secret(
    text: str,
    explicit_secrets: Sequence[str],
) -> None:
    if any(secret in text for secret in explicit_secrets):
        raise RedactionError("explicit_secret_survived_redaction")
    residual_patterns = (
        _PRIVATE_KEY_RE,
        _PRIVATE_KEY_HEADER_RE,
        _CREDENTIAL_URL_RE,
        _AUTH_SCHEME_RE,
        _RESIDUAL_ASSIGNMENT_RE,
    )
    if any(pattern.search(text) for pattern in residual_patterns):
        raise RedactionError("high_confidence_secret_survived_redaction")


def _redact_text(
    text: str,
    policy: RedactionPolicy,
    explicit_secrets: Sequence[str],
) -> str:
    _assert_text_payload(text)
    result = text
    for secret in explicit_secrets:
        result = result.replace(secret, policy.replacement)
    result = _PRIVATE_KEY_RE.sub(PRIVATE_KEY_MARKER, result)
    if _PRIVATE_KEY_HEADER_RE.search(result):
        raise RedactionError("incomplete_private_key_block")
    result = _CREDENTIAL_URL_RE.sub(
        lambda match: f"{match.group(1)}{policy.replacement}@",
        result,
    )
    result = _HEADER_RE.sub(
        lambda match: (
            f"{match.group(1)}{match.group(2)}{policy.replacement}"
        ),
        result,
    )
    result = _AUTH_SCHEME_RE.sub(
        lambda match: f"{match.group(1)} {policy.replacement}",
        result,
    )
    result = _ASSIGNMENT_RE.sub(
        lambda match: (
            f"{match.group(1)}{match.group(2)}{policy.replacement}"
        ),
        result,
    )
    result = _WINDOWS_USER_PATH_RE.sub(USER_PATH_MARKER, result)
    result = _POSIX_USER_PATH_RE.sub(USER_PATH_MARKER, result)
    _assert_no_residual_secret(result, explicit_secrets)
    return result


def _redact_json(
    value: object,
    policy: RedactionPolicy,
    explicit_secrets: Sequence[str],
) -> JsonValue:
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise RedactionError("non_finite_json_number")
        return value
    if isinstance(value, str):
        return _redact_text(value, policy, explicit_secrets)
    if isinstance(value, Mapping):
        result: dict[str, JsonValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise RedactionError("json_object_key_must_be_text")
            if _redact_text(key, policy, explicit_secrets) != key:
                raise RedactionError("json_object_key_contains_sensitive_data")
            if _normalize_key(key) in policy.sensitive_keys:
                result[key] = policy.replacement
            else:
                result[key] = _redact_json(
                    item,
                    policy,
                    explicit_secrets,
                )
        return result
    if isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        return [
            _redact_json(item, policy, explicit_secrets)
            for item in value
        ]
    raise RedactionError("unsupported_json_value")


def _canonical_json_bytes(value: JsonValue) -> bytes:
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise RedactionError("json_canonicalization_failed") from exc
    return text.encode("utf-8")


def _reject_duplicate_json_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise RedactionError("duplicate_json_key")
        result[key] = value
    return result


def canonical_redacted_bytes(
    value: PayloadValue,
    *,
    policy: RedactionPolicy = DEFAULT_REDACTION_POLICY,
    explicit_secret_values: Iterable[str | bytes] = (),
) -> bytes:
    """Return deterministic UTF-8 bytes safe for hashing and future storage."""

    secrets = _prepare_explicit_secrets(explicit_secret_values)
    if isinstance(value, bytes):
        try:
            text = value.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RedactionError(
                "non_utf8_payload_requires_typed_adapter"
            ) from exc
        stripped = text.lstrip()
        if stripped.startswith(("{", "[")):
            try:
                parsed = json.loads(
                    text,
                    object_pairs_hook=_reject_duplicate_json_keys,
                )
            except json.JSONDecodeError:
                pass
            else:
                redacted = _redact_json(parsed, policy, secrets)
                return _canonical_json_bytes(redacted)
        return _redact_text(text, policy, secrets).encode("utf-8")
    if isinstance(value, str):
        return canonical_redacted_bytes(
            value.encode("utf-8"),
            policy=policy,
            explicit_secret_values=secrets,
        )
    redacted = _redact_json(value, policy, secrets)
    return _canonical_json_bytes(redacted)


def _as_utc(name: str, value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, datetime):
        raise EnvelopeContractError(f"{name}_must_be_datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise EnvelopeContractError(f"{name}_must_be_timezone_aware")
    return value.astimezone(timezone.utc)


def _timestamp_text(value: datetime | None) -> str | None:
    if value is None:
        return None
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _public_identifier(name: str, value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or _PUBLIC_IDENTIFIER_RE.fullmatch(value) is None:
        raise EnvelopeContractError(f"{name}_must_be_public_identifier")
    return value


def _sanitized_metadata(
    name: str,
    value: str | None,
    policy: RedactionPolicy,
    explicit_secrets: Sequence[str],
    *,
    allow_redaction: bool,
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise EnvelopeContractError(f"{name}_must_be_nonempty_text")
    redacted = _redact_text(value, policy, explicit_secrets)
    if not allow_redaction and redacted != value:
        raise EnvelopeContractError(f"{name}_contained_sensitive_data")
    return redacted


def _identity_claim(
    *,
    source: str,
    source_version: str,
    endpoint_or_method: str,
    request_hash: str,
    response_status: str,
    error_class: str | None,
    content_sha256: str,
    redaction_version: str,
    event_time: datetime | None,
    observed_at: datetime,
    available_to_strategy_at: datetime,
    ingested_at: datetime,
    first_reliable_available_at: datetime,
    provider_version: str | None,
    schema_version: str,
    protocol_version: str | None,
    revision_number: int,
    revision_of: str | None,
    quality_flags: str | None,
) -> dict[str, JsonValue]:
    return {
        "available_to_strategy_at": _timestamp_text(
            available_to_strategy_at
        ),
        "content_sha256": content_sha256,
        "endpoint_or_method": endpoint_or_method,
        "error_class": error_class,
        "event_time": _timestamp_text(event_time),
        "first_reliable_available_at": _timestamp_text(
            first_reliable_available_at
        ),
        "ingested_at": _timestamp_text(ingested_at),
        "observed_at": _timestamp_text(observed_at),
        "protocol_version": protocol_version,
        "provider_version": provider_version,
        "quality_flags": quality_flags,
        "redaction_version": redaction_version,
        "request_hash": request_hash,
        "response_status": response_status,
        "revision_number": revision_number,
        "revision_of": revision_of,
        "schema_version": schema_version,
        "source": source,
        "source_version": source_version,
    }


def _identity_digest(claim: dict[str, JsonValue]) -> str:
    return hashlib.sha256(_canonical_json_bytes(claim)).hexdigest()


def build_raw_api_event(
    *,
    source: str,
    source_version: str,
    endpoint_or_method: str,
    request_identity: PayloadValue,
    response_body: PayloadValue,
    response_status: RawResponseStatus | str,
    error_class: str | None,
    observed_at: datetime,
    available_to_strategy_at: datetime,
    ingested_at: datetime,
    first_reliable_available_at: datetime,
    event_time: datetime | None = None,
    provider_version: str | None = None,
    schema_version: str = "1.0",
    protocol_version: str | None = None,
    revision_number: int = 1,
    revision_of: str | None = None,
    quality_flags: str | None = None,
    policy: RedactionPolicy = DEFAULT_REDACTION_POLICY,
    explicit_secret_values: Iterable[str | bytes] = (),
) -> RawApiEvent:
    """Build one strict deterministic event without performing I/O."""

    secrets = _prepare_explicit_secrets(explicit_secret_values)
    safe_source = _public_identifier("source", source)
    safe_source_version = _public_identifier(
        "source_version",
        source_version,
    )
    safe_provider_version = _public_identifier(
        "provider_version",
        provider_version,
    )
    safe_schema_version = _public_identifier(
        "schema_version",
        schema_version,
    )
    safe_protocol_version = _public_identifier(
        "protocol_version",
        protocol_version,
    )
    safe_revision_of = _public_identifier("revision_of", revision_of)
    if isinstance(revision_number, bool) or not isinstance(revision_number, int):
        raise EnvelopeContractError("revision_number_must_be_integer")
    if revision_number < 1:
        raise EnvelopeContractError("revision_number_must_be_positive")
    if revision_number == 1 and safe_revision_of is not None:
        raise EnvelopeContractError("first_revision_cannot_link_predecessor")
    if revision_number > 1 and safe_revision_of is None:
        raise EnvelopeContractError("later_revision_requires_predecessor")

    safe_endpoint = _sanitized_metadata(
        "endpoint_or_method",
        endpoint_or_method,
        policy,
        secrets,
        allow_redaction=True,
    )
    safe_error_class = _sanitized_metadata(
        "error_class",
        error_class,
        policy,
        secrets,
        allow_redaction=False,
    )
    safe_quality_flags = _sanitized_metadata(
        "quality_flags",
        quality_flags,
        policy,
        secrets,
        allow_redaction=False,
    )
    request_bytes = canonical_redacted_bytes(
        request_identity,
        policy=policy,
        explicit_secret_values=secrets,
    )
    body_bytes = canonical_redacted_bytes(
        response_body,
        policy=policy,
        explicit_secret_values=secrets,
    )
    request_hash = hashlib.sha256(request_bytes).hexdigest()
    content_sha256 = hashlib.sha256(body_bytes).hexdigest()

    utc_event = _as_utc("event_time", event_time)
    utc_observed = _as_utc("observed_at", observed_at)
    utc_available = _as_utc(
        "available_to_strategy_at",
        available_to_strategy_at,
    )
    utc_ingested = _as_utc("ingested_at", ingested_at)
    utc_reliable = _as_utc(
        "first_reliable_available_at",
        first_reliable_available_at,
    )
    assert utc_observed is not None
    assert utc_available is not None
    assert utc_ingested is not None
    assert utc_reliable is not None

    try:
        status = RawResponseStatus(response_status)
    except ValueError as exc:
        raise EnvelopeContractError("unknown_response_status") from exc

    claim = _identity_claim(
        source=safe_source,
        source_version=safe_source_version,
        endpoint_or_method=safe_endpoint,
        request_hash=request_hash,
        response_status=status.value,
        error_class=safe_error_class,
        content_sha256=content_sha256,
        redaction_version=policy.version,
        event_time=utc_event,
        observed_at=utc_observed,
        available_to_strategy_at=utc_available,
        ingested_at=utc_ingested,
        first_reliable_available_at=utc_reliable,
        provider_version=safe_provider_version,
        schema_version=safe_schema_version,
        protocol_version=safe_protocol_version,
        revision_number=revision_number,
        revision_of=safe_revision_of,
        quality_flags=safe_quality_flags,
    )
    idempotency_key = _identity_digest(claim)
    event = RawApiEvent(
        raw_event_id=f"raw-{idempotency_key}",
        idempotency_key=idempotency_key,
        source=safe_source,
        source_version=safe_source_version,
        endpoint_or_method=safe_endpoint,
        request_hash=request_hash,
        response_status=status,
        error_class=safe_error_class,
        redacted_body=body_bytes,
        content_sha256=content_sha256,
        redaction_version=policy.version,
        event_time=utc_event,
        observed_at=utc_observed,
        available_to_strategy_at=utc_available,
        ingested_at=utc_ingested,
        first_reliable_available_at=utc_reliable,
        provider_version=safe_provider_version,
        schema_version=safe_schema_version,
        protocol_version=safe_protocol_version,
        revision_number=revision_number,
        revision_of=safe_revision_of,
        quality_flags=safe_quality_flags,
    )
    verify_raw_api_event(event, policy=policy)
    return event


def verify_raw_api_event(
    event: RawApiEvent,
    *,
    policy: RedactionPolicy = DEFAULT_REDACTION_POLICY,
) -> None:
    """Fail if bytes, policy or deterministic identity no longer agree."""

    if event.redaction_version != policy.version:
        raise EnvelopeIntegrityError("redaction_policy_version_mismatch")
    actual_content_hash = hashlib.sha256(event.redacted_body).hexdigest()
    if actual_content_hash != event.content_sha256:
        raise EnvelopeIntegrityError("redacted_body_hash_mismatch")
    try:
        body_text = event.redacted_body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise EnvelopeIntegrityError("redacted_body_is_not_utf8") from exc
    try:
        _assert_no_residual_secret(body_text, ())
        _assert_no_residual_secret(event.endpoint_or_method, ())
    except RedactionError as exc:
        raise EnvelopeIntegrityError(
            "residual_sensitive_data"
        ) from exc

    claim = _identity_claim(
        source=event.source,
        source_version=event.source_version,
        endpoint_or_method=event.endpoint_or_method,
        request_hash=event.request_hash,
        response_status=str(event.response_status),
        error_class=event.error_class,
        content_sha256=event.content_sha256,
        redaction_version=event.redaction_version,
        event_time=event.event_time,
        observed_at=event.observed_at,
        available_to_strategy_at=event.available_to_strategy_at,
        ingested_at=event.ingested_at,
        first_reliable_available_at=event.first_reliable_available_at,
        provider_version=event.provider_version,
        schema_version=event.schema_version,
        protocol_version=event.protocol_version,
        revision_number=event.revision_number,
        revision_of=event.revision_of,
        quality_flags=event.quality_flags,
    )
    expected = _identity_digest(claim)
    if event.idempotency_key != expected:
        raise EnvelopeIntegrityError("idempotency_key_mismatch")
    if event.raw_event_id != f"raw-{expected}":
        raise EnvelopeIntegrityError("raw_event_id_mismatch")
