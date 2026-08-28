"""Load and resolve the V1 observation primitive registry."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import jsonschema
import yaml

REGISTRY_RELATIVE = "configs/observation_primitive_registry_v1.yaml"
DESCRIPTOR_SCHEMA_RELATIVE = (
    "catalog/schemas/observation_primitive_descriptor_v1.schema.json"
)
REGISTRY_SCHEMA_RELATIVE = (
    "catalog/schemas/observation_primitive_registry_v1.schema.json"
)
IMPLEMENTATION_RELATIVE = (
    "src/solana_alpha_lab/factory/observation_primitives.py"
)


class PrimitiveRegistryError(ValueError):
    """Typed primitive registry failure."""


def _load_json(root: Path, relative: str) -> dict[str, Any]:
    loaded = json.loads((root / relative).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise PrimitiveRegistryError("PRIMITIVE_REGISTRY_SCHEMA_INVALID")
    return loaded


class ObservationPrimitiveRegistry:
    def __init__(self, root: Path) -> None:
        self.root = root
        path = root / REGISTRY_RELATIVE
        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise PrimitiveRegistryError("PRIMITIVE_REGISTRY_MISSING") from exc
        if not isinstance(loaded, Mapping):
            raise PrimitiveRegistryError("PRIMITIVE_REGISTRY_INVALID")
        jsonschema.validate(dict(loaded), _load_json(root, REGISTRY_SCHEMA_RELATIVE))
        descriptor_schema = _load_json(root, DESCRIPTOR_SCHEMA_RELATIVE)
        self.document = dict(loaded)
        self.fields = {str(item["field_id"]): dict(item) for item in loaded["fields"]}
        self.query_profiles = {
            str(item["query_profile_id"]): dict(item) for item in loaded["query_profiles"]
        }
        self.bundles = {str(item["bundle_id"]): dict(item) for item in loaded["bundles"]}
        primitives: dict[str, dict[str, Any]] = {}
        for item in loaded["primitives"]:
            if not isinstance(item, Mapping):
                raise PrimitiveRegistryError("PRIMITIVE_DESCRIPTOR_INVALID")
            if item.get("retry") is not False or item.get("fallback") is not False:
                raise PrimitiveRegistryError("PRIMITIVE_RETRY_OR_FALLBACK_FORBIDDEN")
            try:
                jsonschema.validate(dict(item), descriptor_schema)
            except jsonschema.ValidationError as exc:
                raise PrimitiveRegistryError("PRIMITIVE_DESCRIPTOR_INVALID") from exc
            primitive_id = str(item["primitive_id"])
            if primitive_id in primitives:
                raise PrimitiveRegistryError("PRIMITIVE_ID_DUPLICATE")
            primitives[primitive_id] = dict(item)
        self.primitives = primitives
        self.authority_profiles = {
            str(item["profile_id"]): dict(item) for item in loaded["authority_profiles"]
        }
        self.registry_sha256 = __import__("hashlib").sha256(path.read_bytes()).hexdigest()

    def require_parser(self, parser_asset_id: str) -> None:
        if parser_asset_id != "MODULE-OBSERVATION-PRIMITIVES-001":
            raise PrimitiveRegistryError("CHANGE_LANE_PRIMITIVE_GAP")

    def require_field(self, field_id: str) -> dict[str, Any]:
        field = self.fields.get(field_id)
        if field is None:
            raise PrimitiveRegistryError("CHANGE_LANE_PRIMITIVE_GAP")
        parser_id = field.get("parser_asset_id")
        if not isinstance(parser_id, str) or not parser_id:
            raise PrimitiveRegistryError("CHANGE_LANE_PRIMITIVE_GAP")
        self.require_parser(parser_id)
        return field

    def require_primitive(self, primitive_id: str) -> dict[str, Any]:
        primitive = self.primitives.get(primitive_id)
        if primitive is None or primitive["status"] != "ACCEPTED":
            raise PrimitiveRegistryError("CHANGE_LANE_PRIMITIVE_GAP")
        return primitive

    def require_bundle(self, bundle_id: str) -> dict[str, Any]:
        bundle = self.bundles.get(bundle_id)
        if bundle is None:
            raise PrimitiveRegistryError("CHANGE_LANE_PRIMITIVE_GAP")
        self.require_primitive(str(bundle["primitive_id"]))
        for field_id in bundle["field_ids"]:
            self.require_field(str(field_id))
        return bundle

    def require_query_profile(self, query_profile_id: str, primitive_id: str) -> dict[str, Any]:
        profile = self.query_profiles.get(query_profile_id)
        if profile is None or profile["primitive_id"] != primitive_id:
            raise PrimitiveRegistryError("CHANGE_LANE_PRIMITIVE_GAP")
        return profile

    def require_authority_profile(self, profile_id: str) -> dict[str, Any]:
        profile = self.authority_profiles.get(profile_id)
        if profile is None:
            raise PrimitiveRegistryError("BLOCKED_AUTHORITY")
        return profile

    def descriptor_sha256(self, primitive_id: str) -> str:
        from solana_alpha_lab.factory.observation_schedule import canonical_sha256

        return canonical_sha256(self.require_primitive(primitive_id))


def load_observation_primitive_registry(root: Path) -> ObservationPrimitiveRegistry:
    return ObservationPrimitiveRegistry(root)


__all__ = [
    "IMPLEMENTATION_RELATIVE",
    "ObservationPrimitiveRegistry",
    "PrimitiveRegistryError",
    "REGISTRY_RELATIVE",
    "load_observation_primitive_registry",
]
