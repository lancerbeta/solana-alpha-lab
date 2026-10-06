"""Append-only provider-route registry successor recording the Jupiter core qualification."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from solana_alpha_lab.provider_route_capability_registry import ProviderRouteRegistryError


V10_SHA256 = "b56dbc70819d52281cd5cd62e86c5b759ef3c3dd3bff8787faf2a605b496c2dc"
V10_PATH = "configs/provider_route_capability_registry_v10.yaml"
SEARCH_ROUTE_ID = "JUPITER-SOLANA-TOKENS-V2-SEARCH-FREE-API-KEY-001"
CATEGORY_ROUTE_SPECS = (
    (
        "JUPITER-SOLANA-TOKENS-V2-TOPORGANICSCORE-5M-FREE-API-KEY-001",
        "tokens/v2/toporganicscore/5m",
        "FREE_API_KEY_TOPORGANICSCORE_5M_TOKEN_LIST",
    ),
    (
        "JUPITER-SOLANA-TOKENS-V2-TOPTRADED-5M-FREE-API-KEY-001",
        "tokens/v2/toptraded/5m",
        "FREE_API_KEY_TOPTRADED_5M_TOKEN_LIST",
    ),
    (
        "JUPITER-SOLANA-TOKENS-V2-TOPTRENDING-5M-FREE-API-KEY-001",
        "tokens/v2/toptrending/5m",
        "FREE_API_KEY_TOPTRENDING_5M_TOKEN_LIST",
    ),
)
EVIDENCE_DIR = "docs/evidence/opportunity_episodes_jupiter_commissioning_v1"
RECEIPT_PATH = f"{EVIDENCE_DIR}/jupiter_qualification_receipt_v1.json"
RECEIPT_SHA256 = "880b2ce75e383444733753e36f1015ad7395d6fabaeefe7f710a07430d13c381"
LIMITS_PATH = f"{EVIDENCE_DIR}/route_qualification_limits_v1.json"
LIMITS_SHA256 = "f3aa0f38400003ab004c93844b78f85891fb43be25d6e608b0fe11dbdcb6b569"
EVIDENCE_ID = "EVIDENCE-JUPITER-CORE-COMMISSIONING-ROUTE-QUALIFICATION-20261006"
PACE_DISCIPLINE = "UNPROVEN_FAILED_OVERLAP_WITH_LEGACY"
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


def _validate_observed_route(
    route: Mapping[str, Any],
    *,
    route_id: str,
    endpoint_family: str,
    operation: str,
    terminal_class: str,
) -> None:
    _require(route.get("route_id") == route_id, "OBSERVED_ROUTE_ID_DRIFT")
    _require(route.get("provider") == "JUPITER", "OBSERVED_PROVIDER_DRIFT")
    _require(route.get("endpoint_family") == endpoint_family, "OBSERVED_ENDPOINT_DRIFT")
    _require(route.get("network") == "solana", "OBSERVED_NETWORK_DRIFT")
    _require(route.get("access_class") == "LOCAL_ENV_CREDENTIAL", "OBSERVED_ACCESS_DRIFT")
    _require(route.get("operation") == operation, "OBSERVED_OPERATION_DRIFT")
    _require(route.get("protocol") == "HTTPS_GET", "OBSERVED_PROTOCOL_DRIFT")
    runtime = _mapping(route.get("runtime"), "OBSERVED_RUNTIME_INVALID")
    _require(runtime.get("observed_result") == "HTTP_200_FREE_KEY_OBSERVED", "OBSERVED_RESULT_DRIFT")
    _require(runtime.get("client_recorded_in_receipt") is False, "OBSERVED_CLIENT_CLAIM_DRIFT")
    preflight = _mapping(route.get("preflight"), "OBSERVED_PREFLIGHT_INVALID")
    _require(preflight.get("steps") == ["DNS", "TCP_443", "TLS_HANDSHAKE"], "OBSERVED_PREFLIGHT_STEPS_DRIFT")
    _require(preflight.get("consumes_credential") is False, "OBSERVED_PREFLIGHT_CREDENTIAL_DRIFT")
    _require(preflight.get("consumes_attempt") is False, "OBSERVED_PREFLIGHT_ATTEMPT_DRIFT")
    last_success = _mapping(route.get("last_success"), "OBSERVED_SUCCESS_INVALID")
    _require(route.get("last_observation") == last_success, "OBSERVED_OBSERVATION_DRIFT")
    _require(last_success.get("terminal_class") == terminal_class, "OBSERVED_TERMINAL_DRIFT")
    _require(last_success.get("layer") == "DISCOVERY", "OBSERVED_LAYER_DRIFT")
    _require(last_success.get("http_status") == 200, "OBSERVED_HTTP_STATUS_DRIFT")
    _require(last_success.get("parser_compatible") is True, "OBSERVED_PARSER_DRIFT")
    _require(last_success.get("error_fingerprint") is None, "OBSERVED_ERROR_DRIFT")
    _require(last_success.get("evidence_id") == EVIDENCE_ID, "OBSERVED_EVIDENCE_ID_DRIFT")
    _require(
        last_success.get("response_bytes_semantics") == "CANONICAL_RESPONSE_JSON",
        "OBSERVED_BYTES_SEMANTICS_DRIFT",
    )
    rows = last_success.get("rows")
    _require(type(rows) is int and rows >= 1, "OBSERVED_ROWS_DRIFT")
    _require(last_success.get("rows_with_valid_identity") == rows, "OBSERVED_IDENTITY_ROWS_DRIFT")
    _require(last_success.get("rows_core_fields_typed") == rows, "OBSERVED_TYPED_ROWS_DRIFT")
    _require(route.get("known_failures") == [], "OBSERVED_FAILURES_DRIFT")
    execution = _mapping(route.get("execution_policy"), "OBSERVED_POLICY_INVALID")
    _require(execution.get("retry") is False, "OBSERVED_RETRY_DRIFT")
    _require(execution.get("fallback") is False, "OBSERVED_FALLBACK_DRIFT")
    _require(execution.get("automatic_selection") is False, "OBSERVED_AUTOMATIC_SELECTION_DRIFT")
    _require(execution.get("authority_granted") is False, "OBSERVED_AUTHORITY_DRIFT")
    evidence = _mapping(route.get("evidence"), "OBSERVED_EVIDENCE_INVALID")
    _require(evidence.get("last_observation_receipt") == RECEIPT_PATH, "OBSERVED_RECEIPT_PATH_DRIFT")
    _require(evidence.get("last_observation_receipt_sha256") == RECEIPT_SHA256, "OBSERVED_RECEIPT_SHA_DRIFT")
    _require(evidence.get("qualification_limits") == LIMITS_PATH, "OBSERVED_LIMITS_PATH_DRIFT")
    _require(evidence.get("qualification_limits_sha256") == LIMITS_SHA256, "OBSERVED_LIMITS_SHA_DRIFT")
    _require(evidence.get("account_pace_discipline") == PACE_DISCIPLINE, "OBSERVED_PACE_CLAIM_DRIFT")
    _require(evidence.get("parser_route_qualification") == "PASS", "OBSERVED_PARSER_QUALIFICATION_DRIFT")
    _require(evidence.get("raw_retention") == "A4_OUTSIDE_GIT", "OBSERVED_RETENTION_DRIFT")
    _require(evidence.get("observed_request_count") == 1, "OBSERVED_REQUEST_COUNT_DRIFT")
    non_claims = _mapping(route.get("non_claims"), "OBSERVED_NON_CLAIMS_INVALID")
    _require(non_claims.get("alpha") is False, "OBSERVED_ALPHA_CLAIM")
    _require(non_claims.get("numeric_netreturn") is False, "OBSERVED_NETRETURN_CLAIM")
    _require(non_claims.get("data_completeness") is False, "OBSERVED_COMPLETENESS_CLAIM")


def validate_provider_route_capability_registry_v11(
    registry: Mapping[str, Any],
    *,
    predecessor: Mapping[str, Any],
    predecessor_sha256: str,
) -> tuple[Mapping[str, Any], ...]:
    _require(set(registry) == ROOT_FIELDS, "REGISTRY_ROOT_DRIFT")
    _require(registry.get("schema") == "smial.provider-route-capability-registry", "SCHEMA_DRIFT")
    _require(registry.get("schema_version") == "11.0", "SCHEMA_VERSION_DRIFT")
    _require(registry.get("registry_id") == "PROVIDER-ROUTE-CAPABILITY-REGISTRY-011", "REGISTRY_ID_DRIFT")
    _require(registry.get("as_of") == "2026-10-06", "AS_OF_DRIFT")
    _require(predecessor_sha256 == V10_SHA256, "V10_BYTES_DRIFT")
    _require(predecessor.get("registry_id") == "PROVIDER-ROUTE-CAPABILITY-REGISTRY-010", "PREDECESSOR_ID_DRIFT")
    supersedes = _mapping(registry.get("supersedes"), "SUPERSEDES_INVALID")
    _require(supersedes.get("registry_id") == "PROVIDER-ROUTE-CAPABILITY-REGISTRY-010", "SUPERSEDES_ID_DRIFT")
    _require(supersedes.get("path") == V10_PATH, "SUPERSEDES_PATH_DRIFT")
    _require(supersedes.get("sha256") == V10_SHA256, "SUPERSEDES_SHA_DRIFT")
    _require(registry.get("update_policy") == predecessor.get("update_policy"), "UPDATE_POLICY_DRIFT")
    predecessor_routes = predecessor.get("routes")
    routes = registry.get("routes")
    _require(isinstance(predecessor_routes, list) and len(predecessor_routes) == 13, "PREDECESSOR_ROUTE_COUNT_DRIFT")
    _require(isinstance(routes, list) and len(routes) == 16, "ROUTE_COUNT_DRIFT")
    preserved = _mapping(supersedes.get("preserved_route_semantic_sha256"), "PRESERVED_HASHES_INVALID")
    _require(len(preserved) == 12, "PRESERVED_HASH_COUNT_DRIFT")
    for index, prior in enumerate(predecessor_routes[:12]):
        current = _mapping(routes[index], "ROUTE_INVALID")
        _require(current == prior, "PRESERVED_ROUTE_DRIFT")
        _require(preserved.get(str(prior.get("route_id"))) == _semantic_sha256(prior), "PRESERVED_ROUTE_HASH_DRIFT")
    # The one transition: the v10 placeholder search route gains its first observation.
    placeholder = _mapping(predecessor_routes[12], "TRANSITION_PREDECESSOR_INVALID")
    _require(placeholder.get("route_id") == SEARCH_ROUTE_ID, "TRANSITION_PREDECESSOR_ID_DRIFT")
    _require(
        _mapping(placeholder.get("runtime"), "TRANSITION_PREDECESSOR_INVALID").get("observed_result")
        == "AUTHORIZED_UNOBSERVED",
        "TRANSITION_PREDECESSOR_STATE_DRIFT",
    )
    transitioned = _mapping(supersedes.get("transitioned_route_semantic_sha256"), "TRANSITIONED_HASHES_INVALID")
    _require(
        dict(transitioned) == {SEARCH_ROUTE_ID: _semantic_sha256(placeholder)},
        "TRANSITIONED_HASH_DRIFT",
    )
    _validate_observed_route(
        _mapping(routes[12], "SEARCH_ROUTE_INVALID"),
        route_id=SEARCH_ROUTE_ID,
        endpoint_family="tokens/v2/search",
        operation="FREE_API_KEY_BULK_TOKEN_SEARCH",
        terminal_class="TOKEN_SEARCH_OBSERVED",
    )
    search_evidence = _mapping(routes[12].get("evidence"), "SEARCH_EVIDENCE_INVALID")
    _require(
        search_evidence.get("search_shape_coverage") == "SINGLE_OBJECT_USDC_PUBLIC_MINT_ONLY",
        "SEARCH_SHAPE_CLAIM_DRIFT",
    )
    _require(routes[12]["last_success"].get("rows") == 1, "SEARCH_ROWS_DRIFT")
    for index, (route_id, endpoint_family, operation) in enumerate(CATEGORY_ROUTE_SPECS, start=13):
        _validate_observed_route(
            _mapping(routes[index], "CATEGORY_ROUTE_INVALID"),
            route_id=route_id,
            endpoint_family=endpoint_family,
            operation=operation,
            terminal_class="TOKEN_LIST_OBSERVED",
        )
    ids = [route["route_id"] for route in routes]
    _require(len(set(ids)) == len(ids), "ROUTE_ID_DUPLICATE")
    return tuple(_mapping(route, "ROUTE_INVALID") for route in routes)


def resolve_provider_route_v11(
    registry: Mapping[str, Any],
    route_id: str,
    *,
    predecessor: Mapping[str, Any],
    predecessor_sha256: str,
) -> Mapping[str, Any]:
    _require(type(route_id) is str and bool(route_id), "ROUTE_ID_REQUIRED")
    for route in validate_provider_route_capability_registry_v11(
        registry,
        predecessor=predecessor,
        predecessor_sha256=predecessor_sha256,
    ):
        if route["route_id"] == route_id:
            return route
    raise ProviderRouteRegistryError(f"REGISTRY_GAP:{route_id}")
