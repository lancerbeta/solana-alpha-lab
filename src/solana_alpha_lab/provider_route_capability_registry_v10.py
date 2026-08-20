"""Append-only provider-route registry successor naming the bulk search route."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from solana_alpha_lab.provider_route_capability_registry import ProviderRouteRegistryError


V9_SHA256 = "dc5cdd4c78a8a907f4bb6de16629c4ee2ef7535c437b33ae9bd8b18eb1847aa1"
V9_PATH = "configs/provider_route_capability_registry_v9.yaml"
SEARCH_ROUTE_ID = "JUPITER-SOLANA-TOKENS-V2-SEARCH-FREE-API-KEY-001"
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


def _validate_search_route(route: Mapping[str, Any]) -> None:
    _require(route.get("route_id") == SEARCH_ROUTE_ID, "SEARCH_ROUTE_ID_DRIFT")
    _require(route.get("provider") == "JUPITER", "SEARCH_PROVIDER_DRIFT")
    _require(route.get("endpoint_family") == "tokens/v2/search", "SEARCH_ENDPOINT_DRIFT")
    _require(route.get("network") == "solana", "SEARCH_NETWORK_DRIFT")
    _require(route.get("access_class") == "LOCAL_ENV_CREDENTIAL", "SEARCH_ACCESS_DRIFT")
    _require(route.get("operation") == "FREE_API_KEY_BULK_TOKEN_SEARCH", "SEARCH_OPERATION_DRIFT")
    _require(route.get("protocol") == "HTTPS_GET", "SEARCH_PROTOCOL_DRIFT")
    runtime = _mapping(route.get("runtime"), "SEARCH_RUNTIME_INVALID")
    _require(runtime.get("client") == "PYTHON_STDLIB_URLLIB", "SEARCH_CLIENT_DRIFT")
    _require(runtime.get("observed_result") == "AUTHORIZED_UNOBSERVED", "SEARCH_OBSERVATION_STATE_DRIFT")
    preflight = _mapping(route.get("preflight"), "SEARCH_PREFLIGHT_INVALID")
    _require(preflight.get("steps") == ["DNS", "TCP_443", "TLS_HANDSHAKE"], "SEARCH_PREFLIGHT_STEPS_DRIFT")
    _require(preflight.get("consumes_credential") is False, "SEARCH_PREFLIGHT_CREDENTIAL_DRIFT")
    _require(preflight.get("consumes_attempt") is False, "SEARCH_PREFLIGHT_ATTEMPT_DRIFT")
    _require(route.get("last_success") is None, "SEARCH_SUCCESS_NOT_NULL")
    _require(route.get("last_observation") is None, "SEARCH_OBSERVATION_NOT_NULL")
    _require(route.get("known_failures") == [], "SEARCH_FAILURES_DRIFT")
    execution = _mapping(route.get("execution_policy"), "SEARCH_POLICY_INVALID")
    _require(execution.get("retry") is False, "SEARCH_RETRY_DRIFT")
    _require(execution.get("fallback") is False, "SEARCH_FALLBACK_DRIFT")
    _require(execution.get("automatic_selection") is False, "SEARCH_AUTOMATIC_SELECTION_DRIFT")
    _require(execution.get("authority_granted") is False, "SEARCH_AUTHORITY_DRIFT")
    evidence = _mapping(route.get("evidence"), "SEARCH_EVIDENCE_INVALID")
    _require(evidence.get("raw_retention") == "PENDING_FIRST_OBSERVATION", "SEARCH_RETENTION_DRIFT")
    non_claims = _mapping(route.get("non_claims"), "SEARCH_NON_CLAIMS_INVALID")
    _require(non_claims.get("alpha") is False, "SEARCH_ALPHA_CLAIM")
    _require(non_claims.get("numeric_netreturn") is False, "SEARCH_NETRETURN_CLAIM")


def validate_provider_route_capability_registry_v10(
    registry: Mapping[str, Any],
    *,
    predecessor: Mapping[str, Any],
    predecessor_sha256: str,
) -> tuple[Mapping[str, Any], ...]:
    _require(set(registry) == ROOT_FIELDS, "REGISTRY_ROOT_DRIFT")
    _require(registry.get("schema") == "smial.provider-route-capability-registry", "SCHEMA_DRIFT")
    _require(registry.get("schema_version") == "10.0", "SCHEMA_VERSION_DRIFT")
    _require(registry.get("registry_id") == "PROVIDER-ROUTE-CAPABILITY-REGISTRY-010", "REGISTRY_ID_DRIFT")
    _require(registry.get("as_of") == "2026-08-20", "AS_OF_DRIFT")
    _require(predecessor_sha256 == V9_SHA256, "V9_BYTES_DRIFT")
    _require(predecessor.get("registry_id") == "PROVIDER-ROUTE-CAPABILITY-REGISTRY-009", "PREDECESSOR_ID_DRIFT")
    supersedes = _mapping(registry.get("supersedes"), "SUPERSEDES_INVALID")
    _require(supersedes.get("registry_id") == "PROVIDER-ROUTE-CAPABILITY-REGISTRY-009", "SUPERSEDES_ID_DRIFT")
    _require(supersedes.get("path") == V9_PATH, "SUPERSEDES_PATH_DRIFT")
    _require(supersedes.get("sha256") == V9_SHA256, "SUPERSEDES_SHA_DRIFT")
    predecessor_routes = predecessor.get("routes")
    routes = registry.get("routes")
    _require(isinstance(predecessor_routes, list) and len(predecessor_routes) == 12, "PREDECESSOR_ROUTE_COUNT_DRIFT")
    _require(isinstance(routes, list) and len(routes) == 13, "ROUTE_COUNT_DRIFT")
    preserved = _mapping(supersedes.get("preserved_route_semantic_sha256"), "PRESERVED_HASHES_INVALID")
    _require(len(preserved) == 12, "PRESERVED_HASH_COUNT_DRIFT")
    for index, prior in enumerate(predecessor_routes):
        current = _mapping(routes[index], "ROUTE_INVALID")
        _require(current == prior, "PRESERVED_ROUTE_DRIFT")
        route_id = str(prior.get("route_id"))
        _require(preserved.get(route_id) == _semantic_sha256(prior), "PRESERVED_ROUTE_HASH_DRIFT")
    search = _mapping(routes[12], "SEARCH_ROUTE_INVALID")
    _validate_search_route(search)
    return tuple(_mapping(route, "ROUTE_INVALID") for route in routes)


def resolve_provider_route_v10(
    registry: Mapping[str, Any],
    route_id: str,
    *,
    predecessor: Mapping[str, Any],
    predecessor_sha256: str,
) -> Mapping[str, Any]:
    _require(type(route_id) is str and bool(route_id), "ROUTE_ID_REQUIRED")
    for route in validate_provider_route_capability_registry_v10(
        registry,
        predecessor=predecessor,
        predecessor_sha256=predecessor_sha256,
    ):
        if route["route_id"] == route_id:
            return route
    raise ProviderRouteRegistryError(f"REGISTRY_GAP:{route_id}")
