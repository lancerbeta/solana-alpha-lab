"""Append-only provider-route registry successor after Tokens V2 discovery."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from solana_alpha_lab.provider_route_capability_registry import ProviderRouteRegistryError
from solana_alpha_lab.provider_route_capability_registry_v7 import (
    validate_provider_route_capability_registry_v7,
)


V7_SHA256 = "cfbd2b34fdecd387d14b89b81ec8d6b814f819ec2b5c7e032ccb54734ff7be6a"
V7_PATH = "configs/provider_route_capability_registry_v7.yaml"
RUNTIME_RECEIPT_PATH = (
    "docs/evidence/quote_native_live_variation_campaign"
    "/a1_quote_native_live_variation_campaign_runtime_receipt_v1.json"
)
RUNTIME_RECEIPT_SHA256 = "d672ddfe764278468cf2e38dc07cf8076dc81abd5e3e5d40450942b20a0497c6"
RECENT_ROUTE_ID = "JUPITER-SOLANA-TOKENS-V2-RECENT-001"
TRADED_ROUTE_ID = "JUPITER-SOLANA-TOKENS-V2-TOPTRADED-001"
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


def _require_token_route(
    route: Mapping[str, Any],
    *,
    route_id: str,
    endpoint_family: str,
    operation: str,
    observed_at: str,
    response_bytes: int,
    response_sha256: str,
) -> None:
    _require(route.get("route_id") == route_id, "TOKEN_ROUTE_ID_DRIFT")
    _require(route.get("provider") == "JUPITER", "TOKEN_PROVIDER_DRIFT")
    _require(route.get("endpoint_family") == endpoint_family, "TOKEN_ENDPOINT_DRIFT")
    _require(route.get("access_class") == "KEYLESS", "TOKEN_ACCESS_DRIFT")
    _require(route.get("operation") == operation, "TOKEN_OPERATION_DRIFT")
    _require(route.get("protocol") == "HTTPS_GET", "TOKEN_PROTOCOL_DRIFT")
    success = _mapping(route.get("last_success"), "TOKEN_SUCCESS_INVALID")
    observation = _mapping(route.get("last_observation"), "TOKEN_OBSERVATION_INVALID")
    _require(success.get("http_status") == 200, "TOKEN_SUCCESS_STATUS_DRIFT")
    _require(success.get("observed_at") == observed_at, "TOKEN_SUCCESS_TIME_DRIFT")
    _require(success.get("response_bytes") == response_bytes, "TOKEN_SUCCESS_BYTES_DRIFT")
    _require(success.get("response_sha256") == response_sha256, "TOKEN_SUCCESS_SHA_DRIFT")
    _require(observation.get("terminal_class") == "TOKEN_LIST_OBSERVED", "TOKEN_TERMINAL_DRIFT")
    _require(observation.get("http_status") == 200, "TOKEN_OBSERVATION_STATUS_DRIFT")
    _require(observation.get("observed_at") == observed_at, "TOKEN_OBSERVATION_TIME_DRIFT")
    _require(observation.get("response_bytes") == response_bytes, "TOKEN_OBSERVATION_BYTES_DRIFT")
    _require(observation.get("response_sha256") == response_sha256, "TOKEN_OBSERVATION_SHA_DRIFT")
    evidence = _mapping(route.get("evidence"), "TOKEN_EVIDENCE_INVALID")
    _require(evidence.get("last_observation_receipt") == RUNTIME_RECEIPT_PATH, "TOKEN_RECEIPT_PATH_DRIFT")
    _require(
        evidence.get("last_observation_receipt_sha256") == RUNTIME_RECEIPT_SHA256,
        "TOKEN_RECEIPT_SHA_DRIFT",
    )
    policy = _mapping(route.get("execution_policy"), "TOKEN_POLICY_INVALID")
    _require(policy.get("retry") is False, "TOKEN_RETRY_DRIFT")
    _require(policy.get("fallback") is False, "TOKEN_FALLBACK_DRIFT")
    _require(policy.get("automatic_selection") is False, "TOKEN_AUTOMATIC_DRIFT")
    _require(policy.get("authority_granted") is False, "TOKEN_AUTHORITY_DRIFT")


def validate_provider_route_capability_registry_v8(
    registry: Mapping[str, Any],
    *,
    predecessor: Mapping[str, Any],
    predecessor_sha256: str,
    v6_registry: Mapping[str, Any],
    v6_sha256: str,
) -> tuple[Mapping[str, Any], ...]:
    _require(set(registry) == ROOT_FIELDS, "REGISTRY_ROOT_DRIFT")
    _require(registry.get("schema") == "smial.provider-route-capability-registry", "SCHEMA_DRIFT")
    _require(registry.get("schema_version") == "8.0", "SCHEMA_VERSION_DRIFT")
    _require(
        registry.get("registry_id") == "PROVIDER-ROUTE-CAPABILITY-REGISTRY-008",
        "REGISTRY_ID_DRIFT",
    )
    _require(predecessor_sha256 == V7_SHA256, "V7_BYTES_DRIFT")
    v7_routes = validate_provider_route_capability_registry_v7(
        predecessor,
        predecessor=v6_registry,
        predecessor_sha256=v6_sha256,
    )
    supersedes = _mapping(registry.get("supersedes"), "SUPERSEDES_INVALID")
    _require(supersedes.get("registry_id") == "PROVIDER-ROUTE-CAPABILITY-REGISTRY-007", "SUPERSEDES_ID_DRIFT")
    _require(supersedes.get("path") == V7_PATH, "SUPERSEDES_PATH_DRIFT")
    _require(supersedes.get("sha256") == V7_SHA256, "SUPERSEDES_SHA_DRIFT")
    preserved = _mapping(supersedes.get("preserved_route_semantic_sha256"), "PRESERVED_HASHES_INVALID")
    routes = registry.get("routes")
    _require(isinstance(routes, list) and len(routes) == 9, "ROUTE_COUNT_DRIFT")
    for index, prior in enumerate(v7_routes):
        current = _mapping(routes[index], "ROUTE_INVALID")
        _require(current.get("route_id") == prior.get("route_id"), "PRESERVED_ROUTE_ORDER_DRIFT")
        digest = _semantic_sha256(current)
        _require(digest == _semantic_sha256(prior), "PRESERVED_ROUTE_DRIFT")
        _require(preserved.get(str(prior["route_id"])) == digest, "PRESERVED_HASH_TABLE_DRIFT")
    _require_token_route(
        _mapping(routes[7], "RECENT_ROUTE_INVALID"),
        route_id=RECENT_ROUTE_ID,
        endpoint_family="tokens/v2/recent",
        operation="KEYLESS_RECENT_TOKEN_LIST",
        observed_at="2026-08-18T09:35:50Z",
        response_bytes=46234,
        response_sha256="f0d611d0ba4be83dbf4d6f4e17d6a50361722b1b5953c661efd5f21a6e1812aa",
    )
    _require_token_route(
        _mapping(routes[8], "TRADED_ROUTE_INVALID"),
        route_id=TRADED_ROUTE_ID,
        endpoint_family="tokens/v2/toptraded/1h",
        operation="KEYLESS_TOPTRADED_1H_TOKEN_LIST",
        observed_at="2026-08-18T09:35:52Z",
        response_bytes=125056,
        response_sha256="b0aac757015eb1dbedc3fbb2caa491bd13653c2164f77960c7c52d991799f007",
    )
    return tuple(_mapping(item, "ROUTE_INVALID") for item in routes)


def resolve_provider_route_v8(
    registry: Mapping[str, Any],
    route_id: str,
    *,
    predecessor: Mapping[str, Any],
    predecessor_sha256: str,
    v6_registry: Mapping[str, Any],
    v6_sha256: str,
) -> Mapping[str, Any]:
    _require(type(route_id) is str and bool(route_id), "ROUTE_ID_REQUIRED")
    for route in validate_provider_route_capability_registry_v8(
        registry,
        predecessor=predecessor,
        predecessor_sha256=predecessor_sha256,
        v6_registry=v6_registry,
        v6_sha256=v6_sha256,
    ):
        if route["route_id"] == route_id:
            return route
    raise ProviderRouteRegistryError(f"REGISTRY_GAP:{route_id}")
