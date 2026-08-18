"""Append-only provider-route registry successor for Free-key qualification."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from solana_alpha_lab.provider_route_capability_registry import ProviderRouteRegistryError
from solana_alpha_lab.provider_route_capability_registry_v8 import (
    validate_provider_route_capability_registry_v8,
)


V8_SHA256 = "2a4483ee2ab3c7b657644044b35317fe9f60cd66c7287ac7303170e78ae67609"
V8_PATH = "configs/provider_route_capability_registry_v8.yaml"
FREE_KEY_ROUTE_IDS = (
    "JUPITER-SOLANA-TOKENS-V2-RECENT-FREE-API-KEY-001",
    "JUPITER-SOLANA-TOKENS-V2-TOPTRADED-FREE-API-KEY-001",
    "JUPITER-SOLANA-SWAP-V2-ORDER-FREE-API-KEY-001",
)
FREE_KEY_ROUTE_SPECS = (
    (
        "tokens/v2/recent",
        "FREE_API_KEY_RECENT_TOKEN_LIST",
    ),
    (
        "tokens/v2/toptraded/1h",
        "FREE_API_KEY_TOPTRADED_1H_TOKEN_LIST",
    ),
    (
        "swap/v2/order",
        "FREE_API_KEY_QUOTE_ONLY_ORDER_WITHOUT_TAKER",
    ),
)
QUALIFICATION_RUNTIME_RECEIPT_PATH = (
    "docs/evidence/quote_native_evidence_channel_qualification/"
    "a1_quote_native_evidence_channel_qualification_runtime_receipt_v1.json"
)
QUALIFICATION_RUNTIME_RECEIPT_SHA256 = (
    "d10e0d74de9d175dfcf5e3fd2408e3736d0fa8b94f52d804a34dce590a89e56f"
)
TIMING_RECOVERY_RECEIPT_PATH = (
    "docs/evidence/quote_native_evidence_channel_qualification/"
    "a1_quote_native_evidence_channel_qualification_timing_recovery_v1.json"
)
TIMING_RECOVERY_RECEIPT_SHA256 = (
    "b7a5c5cd11730d8d5faf3e4f998729bb9edf37e6342343c1d73f441ea73891f5"
)
QUALIFICATION_EVIDENCE_ID = (
    "EVIDENCE-QUOTE-NATIVE-EVIDENCE-CHANNEL-QUALIFICATION-001"
)
FREE_KEY_OBSERVED_SPECS = {
    "JUPITER-SOLANA-TOKENS-V2-RECENT-FREE-API-KEY-001": {
        "observed_result": "HTTP_200_FREE_KEY_OBSERVED",
        "terminal_class": "TOKEN_LIST_OBSERVED",
        "layer": "DISCOVERY",
        "observed_at": "2026-08-18T12:43:04Z",
        "response_bytes": 40179,
        "response_sha256": "bbb7db19f08d8bace5b138ab61dbe8cd60f6dbda856a18fc2c277a0778018ad0",
        "request_count": 1,
        "http_status_counts": {"200": 1},
    },
    "JUPITER-SOLANA-TOKENS-V2-TOPTRADED-FREE-API-KEY-001": {
        "observed_result": "HTTP_200_FREE_KEY_OBSERVED",
        "terminal_class": "TOKEN_LIST_OBSERVED",
        "layer": "DISCOVERY",
        "observed_at": "2026-08-18T12:43:07Z",
        "response_bytes": 127795,
        "response_sha256": "6baa4a05e3dc9597116f7e65e36772fe43ddeedf7fc349bead6dd0196bde31e5",
        "request_count": 1,
        "http_status_counts": {"200": 1},
    },
    "JUPITER-SOLANA-SWAP-V2-ORDER-FREE-API-KEY-001": {
        "observed_result": "HTTP_200_FREE_KEY_OBSERVED_WITH_PROVIDER_TYPED_FAILURES",
        "terminal_class": "QUOTE_OBSERVED",
        "layer": "QUOTE",
        "observed_at": "2026-08-18T13:43:44Z",
        "response_bytes": 1871,
        "response_sha256": "39fddf7d2fe5e04f2792d8c72fdc8938fc8fc953211d5699cf73c407d6ec52b1",
        "request_count": 48,
        "http_status_counts": {"200": 42, "400": 6},
    },
}
ROOT_FIELDS = frozenset(
    {
        "schema",
        "schema_version",
        "registry_id",
        "as_of",
        "supersedes",
        "update_policy",
        "routes",
        "non_claims",
    }
)


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ProviderRouteRegistryError("REGISTRY_VALUE_INVALID") from exc


def _semantic_sha256(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ProviderRouteRegistryError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def _validate_observed_record(
    record: Mapping[str, Any],
    *,
    expected: Mapping[str, Any],
) -> None:
    _require(
        record.get("observed_at") == expected["observed_at"],
        "FREE_KEY_OBSERVED_AT_DRIFT",
    )
    _require(
        record.get("observed_at_semantics")
        == "LOCAL_RAW_WRITE_COMPLETE_UPPER_BOUND",
        "FREE_KEY_TIMESTAMP_SEMANTICS_DRIFT",
    )
    _require(
        record.get("terminal_class") == expected["terminal_class"],
        "FREE_KEY_TERMINAL_DRIFT",
    )
    _require(record.get("layer") == expected["layer"], "FREE_KEY_LAYER_DRIFT")
    _require(record.get("http_status") == 200, "FREE_KEY_STATUS_DRIFT")
    _require(
        record.get("response_bytes") == expected["response_bytes"],
        "FREE_KEY_RESPONSE_BYTES_DRIFT",
    )
    _require(
        record.get("response_sha256") == expected["response_sha256"],
        "FREE_KEY_RESPONSE_SHA_DRIFT",
    )
    _require(record.get("error_fingerprint") is None, "FREE_KEY_ERROR_DRIFT")
    _require(
        record.get("evidence_id") == QUALIFICATION_EVIDENCE_ID,
        "FREE_KEY_EVIDENCE_ID_DRIFT",
    )


def _validate_free_key_route(
    route: Mapping[str, Any],
    *,
    route_id: str,
    endpoint_family: str,
    operation: str,
) -> None:
    _require(route.get("route_id") == route_id, "FREE_KEY_ROUTE_ID_DRIFT")
    _require(route.get("provider") == "JUPITER", "FREE_KEY_PROVIDER_DRIFT")
    _require(
        route.get("endpoint_family") == endpoint_family,
        "FREE_KEY_ENDPOINT_DRIFT",
    )
    _require(route.get("network") == "solana", "FREE_KEY_NETWORK_DRIFT")
    _require(
        route.get("access_class") == "LOCAL_ENV_CREDENTIAL",
        "FREE_KEY_ACCESS_DRIFT",
    )
    _require(route.get("operation") == operation, "FREE_KEY_OPERATION_DRIFT")
    _require(route.get("protocol") == "HTTPS_GET", "FREE_KEY_PROTOCOL_DRIFT")
    runtime = _mapping(route.get("runtime"), "FREE_KEY_RUNTIME_INVALID")
    _require(
        runtime.get("client") == "PYTHON_STDLIB_URLLIB",
        "FREE_KEY_CLIENT_DRIFT",
    )
    observed_result = runtime.get("observed_result")
    preflight = _mapping(route.get("preflight"), "FREE_KEY_PREFLIGHT_INVALID")
    _require(
        preflight.get("steps") == ["DNS", "TCP_443", "TLS_HANDSHAKE"],
        "FREE_KEY_PREFLIGHT_STEPS_DRIFT",
    )
    _require(
        preflight.get("consumes_credential") is False,
        "FREE_KEY_PREFLIGHT_CREDENTIAL_DRIFT",
    )
    _require(
        preflight.get("consumes_attempt") is False,
        "FREE_KEY_PREFLIGHT_ATTEMPT_DRIFT",
    )
    policy = _mapping(route.get("execution_policy"), "FREE_KEY_POLICY_INVALID")
    _require(policy.get("retry") is False, "FREE_KEY_RETRY_DRIFT")
    _require(policy.get("fallback") is False, "FREE_KEY_FALLBACK_DRIFT")
    _require(
        policy.get("automatic_selection") is False,
        "FREE_KEY_AUTOMATIC_SELECTION_DRIFT",
    )
    _require(
        policy.get("authority_granted") is False,
        "FREE_KEY_AUTHORITY_DRIFT",
    )
    evidence = _mapping(route.get("evidence"), "FREE_KEY_EVIDENCE_INVALID")
    expected_observed = FREE_KEY_OBSERVED_SPECS[route_id]
    if observed_result == "AUTHORIZED_UNOBSERVED":
        _require(route.get("last_success") is None, "FREE_KEY_SUCCESS_NOT_NULL")
        _require(
            route.get("last_observation") is None,
            "FREE_KEY_OBSERVATION_NOT_NULL",
        )
        _require(
            evidence.get("raw_retention") == "PENDING_FIRST_OBSERVATION",
            "FREE_KEY_RETENTION_DRIFT",
        )
    else:
        _require(
            observed_result == expected_observed["observed_result"],
            "FREE_KEY_OBSERVATION_STATE_DRIFT",
        )
        _validate_observed_record(
            _mapping(route.get("last_success"), "FREE_KEY_SUCCESS_INVALID"),
            expected=expected_observed,
        )
        _validate_observed_record(
            _mapping(route.get("last_observation"), "FREE_KEY_OBSERVATION_INVALID"),
            expected=expected_observed,
        )
        _require(
            evidence.get("last_observation_receipt")
            == QUALIFICATION_RUNTIME_RECEIPT_PATH,
            "FREE_KEY_RECEIPT_PATH_DRIFT",
        )
        _require(
            evidence.get("last_observation_receipt_sha256")
            == QUALIFICATION_RUNTIME_RECEIPT_SHA256,
            "FREE_KEY_RECEIPT_SHA_DRIFT",
        )
        _require(
            evidence.get("timing_recovery_receipt") == TIMING_RECOVERY_RECEIPT_PATH,
            "FREE_KEY_TIMING_PATH_DRIFT",
        )
        _require(
            evidence.get("timing_recovery_receipt_sha256")
            == TIMING_RECOVERY_RECEIPT_SHA256,
            "FREE_KEY_TIMING_SHA_DRIFT",
        )
        _require(
            evidence.get("raw_retention") == "A4_OUTSIDE_GIT",
            "FREE_KEY_RETENTION_DRIFT",
        )
        _require(
            evidence.get("observed_request_count")
            == expected_observed["request_count"],
            "FREE_KEY_REQUEST_COUNT_DRIFT",
        )
        _require(
            evidence.get("http_status_counts")
            == expected_observed["http_status_counts"],
            "FREE_KEY_STATUS_COUNTS_DRIFT",
        )
        if route_id == FREE_KEY_ROUTE_IDS[2]:
            failures = route.get("known_failures")
            _require(
                isinstance(failures, list) and len(failures) == 1,
                "FREE_KEY_FAILURES_DRIFT",
            )
            failure = _mapping(failures[0], "FREE_KEY_FAILURE_INVALID")
            _require(
                failure.get("fingerprint") == "HTTP_400_PROVIDER_TYPED_FAILURE",
                "FREE_KEY_FAILURES_DRIFT",
            )
        else:
            _require(route.get("known_failures") == [], "FREE_KEY_FAILURES_DRIFT")
    non_claims = _mapping(route.get("non_claims"), "FREE_KEY_NON_CLAIMS_INVALID")
    _require(non_claims.get("alpha") is False, "FREE_KEY_ALPHA_CLAIM")
    _require(
        non_claims.get("numeric_netreturn") is False,
        "FREE_KEY_NETRETURN_CLAIM",
    )


def validate_provider_route_capability_registry_v9(
    registry: Mapping[str, Any],
    *,
    predecessor: Mapping[str, Any],
    predecessor_sha256: str,
    v7_registry: Mapping[str, Any],
    v7_sha256: str,
    v6_registry: Mapping[str, Any],
    v6_sha256: str,
) -> tuple[Mapping[str, Any], ...]:
    _require(set(registry) == ROOT_FIELDS, "REGISTRY_ROOT_DRIFT")
    _require(
        registry.get("schema") == "smial.provider-route-capability-registry",
        "SCHEMA_DRIFT",
    )
    _require(registry.get("schema_version") == "9.0", "SCHEMA_VERSION_DRIFT")
    _require(
        registry.get("registry_id") == "PROVIDER-ROUTE-CAPABILITY-REGISTRY-009",
        "REGISTRY_ID_DRIFT",
    )
    _require(predecessor_sha256 == V8_SHA256, "V8_BYTES_DRIFT")
    v8_routes = validate_provider_route_capability_registry_v8(
        predecessor,
        predecessor=v7_registry,
        predecessor_sha256=v7_sha256,
        v6_registry=v6_registry,
        v6_sha256=v6_sha256,
    )
    supersedes = _mapping(registry.get("supersedes"), "SUPERSEDES_INVALID")
    _require(
        supersedes.get("registry_id") == "PROVIDER-ROUTE-CAPABILITY-REGISTRY-008",
        "SUPERSEDES_ID_DRIFT",
    )
    _require(supersedes.get("path") == V8_PATH, "SUPERSEDES_PATH_DRIFT")
    _require(supersedes.get("sha256") == V8_SHA256, "SUPERSEDES_SHA_DRIFT")
    preserved = _mapping(
        supersedes.get("preserved_route_semantic_sha256"),
        "PRESERVED_HASHES_INVALID",
    )
    routes = registry.get("routes")
    _require(isinstance(routes, list) and len(routes) == 12, "ROUTE_COUNT_DRIFT")
    for index, prior in enumerate(v8_routes):
        current = _mapping(routes[index], "ROUTE_INVALID")
        digest = _semantic_sha256(current)
        _require(
            current.get("route_id") == prior.get("route_id"),
            "PRESERVED_ROUTE_ORDER_DRIFT",
        )
        _require(
            digest == _semantic_sha256(prior),
            "PRESERVED_ROUTE_DRIFT",
        )
        _require(
            preserved.get(str(prior["route_id"])) == digest,
            "PRESERVED_HASH_TABLE_DRIFT",
        )
    for index, (route_id, spec) in enumerate(
        zip(FREE_KEY_ROUTE_IDS, FREE_KEY_ROUTE_SPECS, strict=True),
        start=9,
    ):
        _validate_free_key_route(
            _mapping(routes[index], "FREE_KEY_ROUTE_INVALID"),
            route_id=route_id,
            endpoint_family=spec[0],
            operation=spec[1],
        )
    return tuple(_mapping(route, "ROUTE_INVALID") for route in routes)


def resolve_provider_route_v9(
    registry: Mapping[str, Any],
    route_id: str,
    *,
    predecessor: Mapping[str, Any],
    predecessor_sha256: str,
    v7_registry: Mapping[str, Any],
    v7_sha256: str,
    v6_registry: Mapping[str, Any],
    v6_sha256: str,
) -> Mapping[str, Any]:
    _require(type(route_id) is str and bool(route_id), "ROUTE_ID_REQUIRED")
    for route in validate_provider_route_capability_registry_v9(
        registry,
        predecessor=predecessor,
        predecessor_sha256=predecessor_sha256,
        v7_registry=v7_registry,
        v7_sha256=v7_sha256,
        v6_registry=v6_registry,
        v6_sha256=v6_sha256,
    ):
        if route["route_id"] == route_id:
            return route
    raise ProviderRouteRegistryError(f"REGISTRY_GAP:{route_id}")
