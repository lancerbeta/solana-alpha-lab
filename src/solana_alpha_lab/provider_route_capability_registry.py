"""Deterministic lookup boundary for observed provider route capabilities."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qsl, urlsplit


ROOT_FIELDS = frozenset(
    {
        "schema",
        "schema_version",
        "registry_id",
        "as_of",
        "update_policy",
        "routes",
        "non_claims",
    }
)
ROUTE_FIELDS = frozenset(
    {
        "route_id",
        "provider",
        "endpoint_family",
        "network",
        "access_class",
        "operation",
        "protocol",
        "runtime",
        "preflight",
        "last_success",
        "last_observation",
        "known_failures",
        "execution_policy",
        "evidence",
        "non_claims",
    }
)
UPDATE_POLICY_FIELDS = frozenset(
    {
        "observed_receipt_required",
        "preserve_receipt_history",
        "separate_last_success",
        "registry_gap_is_unavailability",
        "automatic_routing",
        "authority_granted",
    }
)
NON_CLAIM_FIELDS = frozenset(
    {
        "provider_reliability",
        "data_completeness",
        "market_activity",
        "task30_trial",
        "alpha",
        "numeric_netreturn",
    }
)
RUNTIME_FIELDS = frozenset(
    {"client", "version_source", "tls_engine", "observed_result"}
)
PREFLIGHT_FIELDS = frozenset(
    {"kind", "steps", "consumes_credential", "consumes_attempt"}
)
SUCCESS_FIELDS = frozenset(
    {"observed_at", "http_status", "response_bytes", "response_sha256", "evidence_id"}
)
OBSERVATION_FIELDS = frozenset(
    {
        "observed_at",
        "terminal_class",
        "layer",
        "http_status",
        "response_bytes",
        "response_sha256",
        "error_fingerprint",
        "evidence_id",
    }
)
FAILURE_FIELDS = frozenset({"fingerprint", "layer", "interpretation"})
EXECUTION_POLICY_FIELDS = frozenset(
    {"retry", "fallback", "automatic_selection", "authority_granted"}
)
EVIDENCE_FIELDS = frozenset({"last_observation_receipt", "raw_retention"})
ALLOWED_LAYERS = frozenset({"LOCAL_TLS", "TRANSPORT", "HTTP", "RPC", "DATA"})
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
ROUTE_ID_PATTERN = re.compile(r"^[A-Z0-9-]+$")
ABSOLUTE_WINDOWS_PATH = re.compile(r"^[A-Za-z]:[\\/]")
SECRET_QUERY_KEYS = frozenset(
    {
        "api" + "-key",
        "api_key",
        "apikey",
        "token",
        "secret",
        "password",
        "authorization",
    }
)


class ProviderRouteRegistryError(ValueError):
    """The registry is malformed, widened or semantically unsafe."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ProviderRouteRegistryError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    _require(all(type(key) is str for key in value), code)
    return value


def _exact_keys(
    value: Mapping[str, Any], expected: frozenset[str], code: str
) -> None:
    _require(frozenset(value) == expected, code)


def _exact(value: object, expected: object, code: str) -> None:
    _require(type(value) is type(expected) and value == expected, code)


def _string(value: object, code: str) -> str:
    _require(type(value) is str and bool(value), code)
    return value


def _timestamp(value: object) -> datetime:
    text = _string(value, "TIMESTAMP_INVALID")
    _require(text.endswith("Z") and "T" in text, "TIMESTAMP_INVALID")
    try:
        parsed = datetime.fromisoformat(f"{text[:-1]}+00:00")
    except ValueError as exc:
        raise ProviderRouteRegistryError("TIMESTAMP_INVALID") from exc
    _require(parsed.tzinfo is not None and parsed.astimezone(UTC) == parsed, "TIMESTAMP_INVALID")
    return parsed


def _sha256(value: object) -> str:
    text = _string(value, "SHA256_INVALID")
    _require(SHA256_PATTERN.fullmatch(text) is not None, "SHA256_INVALID")
    return text


def _inspect_unsafe_values(value: object) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized = str(key).lower().replace("-", "_")
            _require(
                normalized
                not in {
                    "api_key",
                    "apikey",
                    "token",
                    "secret",
                    "password",
                    "authorization",
                    "private_key",
                    "seed_phrase",
                },
                "SECRET_KEY_FORBIDDEN",
            )
            _inspect_unsafe_values(nested)
        return
    if type(value) is list:
        for nested in value:
            _inspect_unsafe_values(nested)
        return
    if type(value) is not str:
        return
    _require(ABSOLUTE_WINDOWS_PATH.match(value) is None, "ABSOLUTE_PATH_FORBIDDEN")
    lowered = value.lower()
    assignments = tuple(f"{key}=" for key in SECRET_QUERY_KEYS)
    _require(not any(marker in lowered for marker in assignments), "SECRET_VALUE_FORBIDDEN")
    parsed = urlsplit(value)
    if parsed.scheme in {"http", "https", "wss"}:
        _require(parsed.username is None and parsed.password is None, "SECRET_VALUE_FORBIDDEN")
        query_keys = {key.lower() for key, _ in parse_qsl(parsed.query, keep_blank_values=True)}
        _require(query_keys.isdisjoint(SECRET_QUERY_KEYS), "SECRET_VALUE_FORBIDDEN")


def _validate_non_claims(value: object) -> None:
    claims = _mapping(value, "NON_CLAIMS_REQUIRED")
    _exact_keys(claims, NON_CLAIM_FIELDS, "NON_CLAIM_FIELDS_DRIFT")
    for field in NON_CLAIM_FIELDS:
        _exact(claims.get(field), False, "NON_CLAIM_PROMOTION")


def _validate_success(value: object) -> tuple[datetime, str]:
    success = _mapping(value, "LAST_SUCCESS_REQUIRED")
    _exact_keys(success, SUCCESS_FIELDS, "LAST_SUCCESS_FIELDS_DRIFT")
    observed_at = _timestamp(success.get("observed_at"))
    status = success.get("http_status")
    response_bytes = success.get("response_bytes")
    _require(type(status) is int and 100 <= status <= 599, "TYPE_INVALID")
    _require(type(response_bytes) is int and response_bytes > 0, "TYPE_INVALID")
    response_sha256 = _sha256(success.get("response_sha256"))
    _string(success.get("evidence_id"), "EVIDENCE_ID_REQUIRED")
    return observed_at, response_sha256


def _validate_observation(value: object) -> datetime:
    observation = _mapping(value, "LAST_OBSERVATION_REQUIRED")
    _exact_keys(observation, OBSERVATION_FIELDS, "LAST_OBSERVATION_FIELDS_DRIFT")
    observed_at = _timestamp(observation.get("observed_at"))
    terminal_class = _string(observation.get("terminal_class"), "TERMINAL_CLASS_REQUIRED")
    layer = observation.get("layer")
    _require(layer in ALLOWED_LAYERS, "FAILURE_LAYER_CONFLATION")
    status = observation.get("http_status")
    _require(status is None or (type(status) is int and 100 <= status <= 599), "TYPE_INVALID")
    response_bytes = observation.get("response_bytes")
    _require(type(response_bytes) is int and response_bytes >= 0, "TYPE_INVALID")
    response_sha256 = observation.get("response_sha256")
    if response_bytes == 0:
        _require(response_sha256 is None, "RESPONSE_HASH_WITHOUT_BYTES")
    else:
        _sha256(response_sha256)
    error = observation.get("error_fingerprint")
    _require(error is None or (type(error) is str and bool(error)), "TYPE_INVALID")
    if terminal_class == "HTTP_SUCCESS":
        _require(status == 200 and response_bytes > 0 and error is None, "SUCCESS_STATE_INVALID")
    else:
        _require(type(error) is str and bool(error), "FAILED_OBSERVATION_NEEDS_ERROR")
    _string(observation.get("evidence_id"), "EVIDENCE_ID_REQUIRED")
    return observed_at


def _validate_route(route: Mapping[str, Any]) -> None:
    _exact_keys(route, ROUTE_FIELDS, "ROUTE_FIELDS_DRIFT")
    route_id = _string(route.get("route_id"), "ROUTE_ID_REQUIRED")
    _require(ROUTE_ID_PATTERN.fullmatch(route_id) is not None, "ROUTE_ID_INVALID")
    _string(route.get("provider"), "PROVIDER_REQUIRED")
    _string(route.get("endpoint_family"), "ENDPOINT_FAMILY_REQUIRED")
    _exact(route.get("network"), "solana", "NETWORK_DRIFT")
    _require(route.get("access_class") in {"KEYLESS", "LOCAL_ENV_CREDENTIAL"}, "ACCESS_CLASS_INVALID")
    _string(route.get("operation"), "OPERATION_REQUIRED")
    _string(route.get("protocol"), "PROTOCOL_REQUIRED")

    runtime = _mapping(route.get("runtime"), "RUNTIME_REQUIRED")
    _exact_keys(runtime, RUNTIME_FIELDS, "RUNTIME_FIELDS_DRIFT")
    for field in RUNTIME_FIELDS:
        _string(runtime.get(field), "RUNTIME_VALUE_REQUIRED")

    preflight = _mapping(route.get("preflight"), "PREFLIGHT_REQUIRED")
    _exact_keys(preflight, PREFLIGHT_FIELDS, "PREFLIGHT_FIELDS_DRIFT")
    _string(preflight.get("kind"), "PREFLIGHT_KIND_REQUIRED")
    steps = preflight.get("steps")
    _require(
        type(steps) is list and bool(steps) and all(type(item) is str and bool(item) for item in steps),
        "PREFLIGHT_STEPS_INVALID",
    )
    _exact(preflight.get("consumes_credential"), False, "PREFLIGHT_CREDENTIAL_PROMOTION")
    _exact(preflight.get("consumes_attempt"), False, "PREFLIGHT_ATTEMPT_PROMOTION")

    success_at, _ = _validate_success(route.get("last_success"))
    observation_at = _validate_observation(route.get("last_observation"))
    _require(observation_at >= success_at, "LAST_OBSERVATION_BEFORE_SUCCESS")

    known_failures = route.get("known_failures")
    _require(type(known_failures) is list, "KNOWN_FAILURES_REQUIRED")
    for raw_failure in known_failures:
        failure = _mapping(raw_failure, "FAILURE_RECORD_REQUIRED")
        _exact_keys(failure, FAILURE_FIELDS, "FAILURE_FIELDS_DRIFT")
        _string(failure.get("fingerprint"), "FAILURE_FINGERPRINT_REQUIRED")
        _require(failure.get("layer") in ALLOWED_LAYERS, "FAILURE_LAYER_CONFLATION")
        _string(failure.get("interpretation"), "FAILURE_INTERPRETATION_REQUIRED")

    policy = _mapping(route.get("execution_policy"), "EXECUTION_POLICY_REQUIRED")
    _exact_keys(policy, EXECUTION_POLICY_FIELDS, "EXECUTION_POLICY_FIELDS_DRIFT")
    _exact(policy.get("retry"), False, "RETRY_PROMOTION")
    _exact(policy.get("fallback"), False, "FALLBACK_PROMOTION")
    _exact(policy.get("automatic_selection"), False, "AUTOMATIC_SELECTION_PROMOTION")
    _exact(policy.get("authority_granted"), False, "AUTHORITY_PROMOTION")

    evidence = _mapping(route.get("evidence"), "EVIDENCE_REQUIRED")
    _exact_keys(evidence, EVIDENCE_FIELDS, "EVIDENCE_FIELDS_DRIFT")
    receipt = _string(evidence.get("last_observation_receipt"), "EVIDENCE_RECEIPT_REQUIRED")
    _require(receipt.startswith("a4://") and "\\" not in receipt, "EVIDENCE_RECEIPT_INVALID")
    retention = _string(evidence.get("raw_retention"), "RAW_RETENTION_REQUIRED")
    _require(retention.startswith("A4_"), "RAW_RETENTION_INVALID")
    _validate_non_claims(route.get("non_claims"))


def validate_provider_route_capability_registry(
    registry: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    """Validate a registry document without I/O or provider authority."""

    root = _mapping(registry, "REGISTRY_ROOT_REQUIRED")
    _inspect_unsafe_values(root)
    _require(frozenset(root) == ROOT_FIELDS, "REGISTRY_ROOT_FIELDS_DRIFT")
    _require(
        root.get("schema") == "smial.provider-route-capability-registry",
        "REGISTRY_SCHEMA_DRIFT",
    )
    _require(root.get("schema_version") == "1.0", "REGISTRY_VERSION_DRIFT")
    _exact(root.get("registry_id"), "PROVIDER-ROUTE-CAPABILITY-REGISTRY-001", "REGISTRY_ID_DRIFT")
    as_of = _string(root.get("as_of"), "AS_OF_INVALID")
    try:
        datetime.strptime(as_of, "%Y-%m-%d")
    except ValueError as exc:
        raise ProviderRouteRegistryError("AS_OF_INVALID") from exc

    update_policy = _mapping(root.get("update_policy"), "UPDATE_POLICY_REQUIRED")
    _exact_keys(update_policy, UPDATE_POLICY_FIELDS, "UPDATE_POLICY_FIELDS_DRIFT")
    for field in {
        "observed_receipt_required",
        "preserve_receipt_history",
        "separate_last_success",
    }:
        _exact(update_policy.get(field), True, "UPDATE_POLICY_WEAKENED")
    for field in {
        "registry_gap_is_unavailability",
        "automatic_routing",
        "authority_granted",
    }:
        _exact(update_policy.get(field), False, "UPDATE_POLICY_PROMOTION")
    raw_routes = root.get("routes")
    _require(type(raw_routes) is list and bool(raw_routes), "ROUTES_REQUIRED")
    routes = tuple(_mapping(item, "ROUTE_RECORD_REQUIRED") for item in raw_routes)
    route_ids = [route.get("route_id") for route in routes]
    _require(len(route_ids) == len(set(route_ids)), "DUPLICATE_ROUTE_ID")
    for route in routes:
        _validate_route(route)
    _validate_non_claims(root.get("non_claims"))
    return routes


def resolve_provider_route(
    registry: Mapping[str, Any], route_id: str
) -> Mapping[str, Any]:
    """Resolve one stable route ID or retain absence as a registry gap."""

    _require(type(route_id) is str and bool(route_id), "ROUTE_ID_REQUIRED")
    for route in validate_provider_route_capability_registry(registry):
        if route["route_id"] == route_id:
            return route
    raise ProviderRouteRegistryError(f"REGISTRY_GAP:{route_id}")
