"""Operational capacity for self-contained HFIC packets, never research budgets."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from solana_alpha_lab.factory.run_passport import canonical_json_bytes

CONFIG_RELATIVE = "configs/hypothesis_forge_independent_critic_v1.yaml"
ENV_PREFIX = "SMIAL_HFIC_"


class PacketCapacityError(ValueError):
    def __init__(self, code: str, **detail: Any) -> None:
        self.code = code
        self.detail = detail
        super().__init__(code)


@dataclass(frozen=True)
class PacketCapacity:
    working_records: int = 8
    working_bytes: int = 65536
    packet_bytes: int = 8 * 1024 * 1024
    json_bytes: int = 64 * 1024 * 1024
    resource_records: int = 10000

    def snapshot(self) -> dict[str, Any]:
        return {"version": "1.0", **asdict(self)}


DEFAULT_CAPACITY = PacketCapacity()


def resolve_packet_capacity(
    repo_root: Path | str | None = None, *, frozen: Mapping[str, Any] | None = None,
) -> PacketCapacity:
    """Preserve frozen selection; explicit local resource overrides remain usable."""
    names = tuple(asdict(DEFAULT_CAPACITY))
    values = asdict(DEFAULT_CAPACITY)
    if frozen is not None:
        if not isinstance(frozen, Mapping) or set(frozen) != {"version", *names} or frozen.get("version") != "1.0":
            raise PacketCapacityError("HFIC_CAPACITY_CONFIG_INVALID", source="FROZEN_SETTINGS")
        values.update({name: frozen[name] for name in names})
    else:
        if repo_root is None:
            repo_root = Path(__file__).resolve().parents[3]
        path = Path(repo_root) / CONFIG_RELATIVE
        if path.is_file():
            try:
                loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
                if loaded is None:
                    loaded = {}
                if not isinstance(loaded, Mapping):
                    raise PacketCapacityError("HFIC_CAPACITY_CONFIG_INVALID", source="REPOSITORY_CONFIG")
                block = loaded.get("packet_capacity", {})
            except (OSError, ValueError, yaml.YAMLError) as exc:
                raise PacketCapacityError("HFIC_CAPACITY_CONFIG_INVALID", source="REPOSITORY_CONFIG") from exc
            if not isinstance(block, Mapping) or set(block) - set(names):
                raise PacketCapacityError("HFIC_CAPACITY_CONFIG_INVALID", source="REPOSITORY_CONFIG")
            values.update(block)
    # Explicit local resource overrides can unblock an action on saved inputs.
    # Frozen selection recommendations never follow today's config/defaults.
    override_names = names if frozen is None else ("packet_bytes", "json_bytes", "resource_records")
    for name in override_names:
        raw = os.environ.get(ENV_PREFIX + name.upper())
        if raw is not None:
            try:
                values[name] = int(raw)
            except ValueError as exc:
                raise PacketCapacityError("HFIC_CAPACITY_CONFIG_INVALID", setting=name) from exc
    for name, value in values.items():
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value < sys.maxsize:
            raise PacketCapacityError("HFIC_CAPACITY_CONFIG_INVALID", setting=name)
    return PacketCapacity(**values)


def packet_capacity(packet: Mapping[str, Any], repo_root: Path | str | None = None) -> PacketCapacity:
    frozen = packet.get("operational_capacity")
    if frozen is None:
        memory = packet.get("prior_memory") or packet.get("prior_memory_working_view") or {}
        frozen = memory.get("operational_capacity") if isinstance(memory, Mapping) else None
        if frozen is None and isinstance(memory, Mapping) and memory.get("schema_version") == "1.1":
            # Before capacity snapshots existed, working views saved these
            # selection knobs directly. Do not reselect with today's defaults.
            frozen = {**DEFAULT_CAPACITY.snapshot(),
                      "working_records": memory.get("max_records"),
                      "working_bytes": memory.get("max_bytes")}
    return resolve_packet_capacity(repo_root, frozen=frozen)


def check_packet_resource(
    packet: Mapping[str, Any], *, capacity: PacketCapacity | None = None, stage: str = "PACKET",
) -> int:
    capacity = capacity or packet_capacity(packet)
    memory = packet.get("prior_memory") or packet.get("prior_memory_working_view") or {}
    records = len(memory.get("capsules") or []) if isinstance(memory, Mapping) else 0
    if records > capacity.resource_records:
        raise PacketCapacityError("HFIC_MEMORY_RESOURCE_LIMIT_EXCEEDED", stage=stage,
                                  actual_records=records, limit_records=capacity.resource_records,
                                  setting="SMIAL_HFIC_RESOURCE_RECORDS")
    size = len(canonical_json_bytes(packet))
    if size > capacity.packet_bytes:
        raise PacketCapacityError(
            "HFIC_PACKET_RESOURCE_LIMIT_EXCEEDED", stage=stage,
            actual_bytes=size, limit_bytes=capacity.packet_bytes,
            setting="SMIAL_HFIC_PACKET_BYTES",
        )
    return size


def load_bounded_bytes(path: Path, *, repo_root: Path | str | None = None) -> bytes:
    """Read at most the operational allowance plus one sentinel byte."""
    capacity = resolve_packet_capacity(repo_root)
    if path.is_symlink() or not path.is_file():
        raise PacketCapacityError("HFIC_JSON_INPUT_UNAVAILABLE", stage="FILE_READ")
    try:
        with path.open("rb") as stream:
            data = stream.read(capacity.json_bytes + 1)
    except OSError as exc:
        raise PacketCapacityError("HFIC_JSON_INPUT_UNAVAILABLE", stage="FILE_READ") from exc
    if len(data) > capacity.json_bytes:
        raise PacketCapacityError(
            "HFIC_JSON_RESOURCE_LIMIT_EXCEEDED", stage="FILE_READ",
            actual_bytes_at_least=len(data), limit_bytes=capacity.json_bytes,
            setting="SMIAL_HFIC_JSON_BYTES",
        )
    return data


def load_json_document(path: Path, *, repo_root: Path | str | None = None) -> dict[str, Any]:
    data = load_bounded_bytes(path, repo_root=repo_root)
    try:
        loaded = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise PacketCapacityError("HFIC_JSON_INPUT_INVALID", stage="JSON_DECODE") from exc
    if not isinstance(loaded, dict):
        raise PacketCapacityError("HFIC_JSON_INPUT_INVALID", stage="JSON_OBJECT_REQUIRED")
    return loaded
