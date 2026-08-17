"""Append-only provider-route registry successor after the PMF quote observation."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from solana_alpha_lab.provider_route_capability_registry import ProviderRouteRegistryError
from solana_alpha_lab.provider_route_capability_registry_v6 import (
    validate_provider_route_capability_registry_v6,
)


V6_SHA256 = "b9642b77c300c81aedebc4aa464284fe244a7553bb3a37bdbb344d68594df580"
V6_PATH = "configs/provider_route_capability_registry_v6.yaml"
RUNTIME_RECEIPT_PATH = (
    "docs/evidence/pmf_quote_slice/a1_pmf_quote_slice_one_shot_runtime_receipt_v1.json"
)
RUNTIME_RECEIPT_SHA256 = (
    "2ee2b71115b67b5129e44d08f7c29becefefd8979ad130c3174614ba7f64ba2c"
)
JUPITER_ROUTE_ID = "JUPITER-SOLANA-SWAP-V2-ORDER-001"
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


def validate_provider_route_capability_registry_v7(
    registry: Mapping[str, Any],
    *,
    predecessor: Mapping[str, Any],
    predecessor_sha256: str,
) -> tuple[Mapping[str, Any], ...]:
    _require(set(registry) == ROOT_FIELDS, "REGISTRY_ROOT_DRIFT")
    _require(registry.get("schema") == "smial.provider-route-capability-registry", "SCHEMA_DRIFT")
    _require(registry.get("schema_version") == "7.0", "SCHEMA_VERSION_DRIFT")
    _require(
        registry.get("registry_id") == "PROVIDER-ROUTE-CAPABILITY-REGISTRY-007",
        "REGISTRY_ID_DRIFT",
    )
    _require(predecessor_sha256 == V6_SHA256, "V6_BYTES_DRIFT")
    v6_routes = validate_provider_route_capability_registry_v6(predecessor)
    supersedes = _mapping(registry.get("supersedes"), "SUPERSEDES_INVALID")
    _require(supersedes.get("registry_id") == "PROVIDER-ROUTE-CAPABILITY-REGISTRY-006", "SUPERSEDES_ID_DRIFT")
    _require(supersedes.get("path") == V6_PATH, "SUPERSEDES_PATH_DRIFT")
    _require(supersedes.get("sha256") == V6_SHA256, "SUPERSEDES_SHA_DRIFT")
    preserved = _mapping(supersedes.get("preserved_route_semantic_sha256"), "PRESERVED_HASHES_INVALID")
    routes = registry.get("routes")
    _require(isinstance(routes, list) and len(routes) == 7, "ROUTE_COUNT_DRIFT")
    for index, prior in enumerate(v6_routes):
        current = _mapping(routes[index], "ROUTE_INVALID")
        _require(current.get("route_id") == prior.get("route_id"), "PRESERVED_ROUTE_ORDER_DRIFT")
        digest = _semantic_sha256(current)
        _require(digest == _semantic_sha256(prior), "PRESERVED_ROUTE_DRIFT")
        _require(preserved.get(str(prior["route_id"])) == digest, "PRESERVED_HASH_TABLE_DRIFT")
    jupiter = _mapping(routes[6], "JUPITER_ROUTE_INVALID")
    _require(jupiter.get("route_id") == JUPITER_ROUTE_ID, "JUPITER_ROUTE_ID_DRIFT")
    _require(jupiter.get("provider") == "JUPITER", "JUPITER_PROVIDER_DRIFT")
    _require(jupiter.get("endpoint_family") == "swap/v2/order", "JUPITER_ENDPOINT_DRIFT")
    _require(jupiter.get("access_class") == "KEYLESS", "JUPITER_ACCESS_DRIFT")
    _require(jupiter.get("operation") == "QUOTE_ONLY_ORDER_WITHOUT_TAKER", "JUPITER_OPERATION_DRIFT")
    _require(jupiter.get("protocol") == "HTTPS_GET", "JUPITER_PROTOCOL_DRIFT")
    success = _mapping(jupiter.get("last_success"), "JUPITER_SUCCESS_INVALID")
    observation = _mapping(jupiter.get("last_observation"), "JUPITER_OBSERVATION_INVALID")
    _require(success.get("http_status") == 200, "JUPITER_SUCCESS_STATUS_DRIFT")
    _require(observation.get("terminal_class") == "QUOTE_OBSERVED", "JUPITER_TERMINAL_DRIFT")
    _require(observation.get("http_status") == 200, "JUPITER_OBSERVATION_STATUS_DRIFT")
    evidence = _mapping(jupiter.get("evidence"), "JUPITER_EVIDENCE_INVALID")
    _require(evidence.get("last_observation_receipt") == RUNTIME_RECEIPT_PATH, "JUPITER_RECEIPT_PATH_DRIFT")
    _require(
        evidence.get("last_observation_receipt_sha256") == RUNTIME_RECEIPT_SHA256,
        "JUPITER_RECEIPT_SHA_DRIFT",
    )
    return tuple(_mapping(item, "ROUTE_INVALID") for item in routes)


def resolve_provider_route_v7(
    registry: Mapping[str, Any],
    route_id: str,
    *,
    predecessor: Mapping[str, Any],
    predecessor_sha256: str,
) -> Mapping[str, Any]:
    _require(type(route_id) is str and bool(route_id), "ROUTE_ID_REQUIRED")
    for route in validate_provider_route_capability_registry_v7(
        registry, predecessor=predecessor, predecessor_sha256=predecessor_sha256
    ):
        if route["route_id"] == route_id:
            return route
    raise ProviderRouteRegistryError(f"REGISTRY_GAP:{route_id}")
