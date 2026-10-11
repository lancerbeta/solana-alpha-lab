"""Ordinary offline PAPER/SHADOW runner over the existing truth owners.

Definition loading and explicit activation are separate. External observation
and result bytes are inputs; this module has no provider, wallet or live route.
"""
from __future__ import annotations

import json
import re
from itertools import islice
from pathlib import Path, PureWindowsPath
from typing import Any

from solana_alpha_lab.factory.episode_decision import produce_episode_decision, load_bound_recipe, produce_originating_exit
from solana_alpha_lab.factory.observation_schedule import parse_utc
from solana_alpha_lab.factory.paper_plane import (PaperPlaneStore, accept_signal_decision,
    accept_exit_decision, begin_modeled_attempt, accept_modeled_result)
from solana_alpha_lab.factory.paper_shadow_commands import apply_operator_command, maybe_finish_drain
from solana_alpha_lab.factory.paper_shadow_operations import build_operations_projection
from solana_alpha_lab.factory.promotion_handoff import compose_science_to_strategy_handoff
from solana_alpha_lab.factory.research_store import ResearchStore
from solana_alpha_lab.factory.strategy_runtime import PaperPlaneError, load_strategy_version
from solana_alpha_lab.factory.hfic_research_scope import sha256_of

OFFLINE_MARKER = {"schema": "smial.offline-runtime", "schema_version": "1.0", "evidence_class": "SYNTHETIC_OFFLINE"}


def offline_root(root: Path, data_root: Path) -> Path:
    """Fail before opening any writable store. Exact local marker, no links."""
    local = (root / "local").resolve(strict=True)
    path = data_root.resolve(strict=True)
    if path == local or not path.is_relative_to(local) or path != data_root.absolute():
        raise PaperPlaneError("OFFLINE_ROOT_UNSAFE")
    for item in (path, *path.parents):
        if item.is_symlink() or (hasattr(item, "is_junction") and item.is_junction()):
            raise PaperPlaneError("OFFLINE_ROOT_LINK_FORBIDDEN")
        if item == local:
            break
    try:
        marker = json.loads((path / "offline_runtime.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise PaperPlaneError("OFFLINE_ROOT_MARKER_REQUIRED") from None
    if marker != OFFLINE_MARKER:
        raise PaperPlaneError("OFFLINE_ROOT_MARKER_INVALID")
    return path


class TradingContinuityRunner:
    def __init__(self, root: Path, *, data_root: Path, strategy_relative: str):
        self.root = root
        self.data_root = offline_root(root, data_root)
        self.store_path = self.data_root / "paper_plane.sqlite"
        self._validate_store_paths()
        self._safe_path(self.data_root / "research-data", strict=True)
        self.strategy = load_strategy_version(root, strategy_relative)
        if self.strategy["schema_version"] != "1.1":
            raise PaperPlaneError("CONTINUITY_REQUIRES_V1_1")
        records = tuple(islice(ResearchStore(self.data_root / "research-data", create_if_missing=False).iter_committed_records(), 10001))
        if len(records) > 10000:
            raise PaperPlaneError("OFFLINE_RESEARCH_INPUT_TOO_WIDE")
        selected = [record for record in records if record.record_id == self.strategy["source_decision_asset_id"]]
        if len(selected) != 1:
            raise PaperPlaneError("BOUND_PROMOTE_RECORD_REQUIRED")
        payload = json.loads(selected[0].payload_json)
        if payload.get("decision_kind") != "PROMOTE":
            raise PaperPlaneError("BOUND_PROMOTE_RECORD_REQUIRED")
        self.manifest = payload.get("promotion_handoff_manifest")
        self.binding = payload.get("execution_evidence_binding")
        if not isinstance(self.manifest, dict) or not isinstance(self.binding, dict):
            raise PaperPlaneError("LEGACY_PROVENANCE_GAP")
        exact_records = [record for record in records if record.record_kind != "DECISION_EVENT" or record.record_id == selected[0].record_id]
        check = compose_science_to_strategy_handoff(root=root, experiment_id=self.manifest["experiment_id"],
            records=exact_records, records_status="AVAILABLE", execution_inputs={
                "max_age_seconds": self.strategy["signal_input"]["max_age_seconds"],
                **self.strategy["notional_policy"], **self.strategy["risk_policy"],
                "shadow": self.strategy["mode_eligibility"]["shadow"],
            })
        if check["state"]["blocker_codes"]:
            raise PaperPlaneError(check["state"]["blocker_codes"][0])
        load_bound_recipe(root, strategy=self.strategy, manifest=self.manifest, execution_binding=self.binding)

    def _safe_path(self, path: Path, *, strict=False):
        resolved = path.resolve(strict=strict)
        if resolved != path.absolute() or not resolved.is_relative_to(self.data_root):
            raise PaperPlaneError("OFFLINE_CHILD_PATH_UNSAFE")
        for item in (path, *path.parents):
            if item.is_symlink() or item.is_junction():
                raise PaperPlaneError("OFFLINE_CHILD_LINK_FORBIDDEN")
            if item == self.data_root:
                break
        return path

    def _validate_store_paths(self):
        for suffix in ("", "-wal", "-shm", "-journal"):
            path = self._safe_path(Path(str(self.store_path) + suffix))
            if path.exists() and (not path.is_file() or path.stat().st_nlink != 1):
                raise PaperPlaneError("OFFLINE_STORE_ALIAS_FORBIDDEN")

    def _store(self, *, readonly=False):
        self._validate_store_paths()
        return PaperPlaneStore(self.store_path, readonly=readonly)

    def activate(self, *, epoch_id: str, mode: str, at: str) -> dict[str, Any]:
        if mode not in {"PAPER", "SHADOW"} or not re.fullmatch(r"ACTIVATION-EPOCH-[A-Z0-9]+(?:-[A-Z0-9]+)*", epoch_id):
            raise PaperPlaneError("OFFLINE_ACTIVATION_SCOPE_INVALID")
        if self.strategy["mode_eligibility"].get(mode.lower()) is not True or self.strategy["mode_eligibility"].get("micro_live") is not False:
            raise PaperPlaneError("MODE_NOT_ELIGIBLE")
        if parse_utc(at) < parse_utc(self.manifest["decision_effective_at"]):
            raise PaperPlaneError("ACTIVATION_BEFORE_PROMOTE")
        binding = {"epoch_id": epoch_id, "mode": mode, "at": at,
                   "strategy_id": self.strategy["strategy_id"], "strategy_version": self.strategy["strategy_version"],
                   "strategy_sha256": self.strategy["spec_sha256"], "evidence_class": "SYNTHETIC_OFFLINE"}
        store = self._store()
        try:
            with store.immediate_write():
                prior = store.get_execution_event(epoch_id)
                if prior is not None:
                    if prior["payload"] != binding:
                        raise PaperPlaneError("ACTIVATION_BINDING_CONFLICT")
                    return {**binding, "idempotent": True}
                bot = store.start_bot(self.strategy, mode=mode, activation_epoch_id=epoch_id)
                store.append_execution_event(event_type="OFFLINE_ACTIVATION_CREATED", event_id=epoch_id,
                    bot_instance_id=bot["bot_instance_id"], position_id=None, payload=binding, created_at=at)
                return {**binding, "idempotent": False}
        finally:
            store.close()

    def _epoch(self, store, epoch_id, mode):
        record = store.get_execution_event(epoch_id)
        if record is None or record["event_type"] != "OFFLINE_ACTIVATION_CREATED":
            raise PaperPlaneError("EXPLICIT_OFFLINE_ACTIVATION_REQUIRED")
        bound = record["payload"]
        if (bound["mode"], bound["strategy_sha256"]) != (mode, self.strategy["spec_sha256"]):
            raise PaperPlaneError("ACTIVATION_BINDING_CONFLICT")
        return {epoch_id: bound}

    def _origin(self, store, position):
        record = store.get_execution_event("SRC-" + position["signal_decision_id"])
        if record is None or record["event_type"] != "SOURCE_DECISION_PRODUCED":
            raise PaperPlaneError("SOURCE_DECISION_PROVENANCE_MISSING")
        packet = record["payload"]
        provenance = packet.get("provenance") or {}
        decision = packet.get("decision") or {}
        digest = sha256_of(provenance)
        if (packet.get("provenance_sha256") != digest
            or decision.get("evidence_refs") != ["execution-event:SRC-" + position["signal_decision_id"] + ":sha256:" + digest]
            or (decision.get("signal_decision_id"), decision.get("strategy_id"), decision.get("strategy_version"),
                decision.get("activation_epoch_id"), decision.get("mint")) !=
               (position["signal_decision_id"], self.strategy["strategy_id"], self.strategy["strategy_version"],
                position["activation_epoch_id"], position["mint"])
            or provenance.get("strategy_sha256") != self.strategy["spec_sha256"]
            or provenance.get("promotion_handoff_manifest_sha256") != self.manifest["manifest_sha256"]):
            raise PaperPlaneError("SOURCE_DECISION_PROVENANCE_CONFLICT")
        return packet

    def episode(self, *, source_relative: str, episode_id: str, epoch_id: str, mode: str, as_of: str):
        source = Path(source_relative)
        if source.anchor or PureWindowsPath(source_relative).anchor or ".." in source.parts:
            raise PaperPlaneError("OFFLINE_SOURCE_PATH_UNSAFE")
        source_path = self.data_root / source
        self._safe_path(source_path, strict=True)
        store = self._store()
        try:
            known = self._epoch(store, epoch_id, mode)
            if parse_utc(as_of) < parse_utc(known[epoch_id]["at"]):
                raise PaperPlaneError("DECISION_BEFORE_ACTIVATION")
            packet = produce_episode_decision(self.root, source_path=source_path, strategy=self.strategy,
                manifest=self.manifest, execution_binding=self.binding, epoch_id=epoch_id,
                episode_id=episode_id, as_of=as_of)
            with store.immediate_write():
                sid = "SRC-" + packet["decision"]["signal_decision_id"]
                previous = store.get_execution_event(sid)
                if previous is not None and previous["payload"] != packet:
                    raise PaperPlaneError("SOURCE_DECISION_CONTENT_CONFLICT")
                if previous is None:
                    store.append_execution_event(event_type="SOURCE_DECISION_PRODUCED", event_id=sid,
                        bot_instance_id=None, position_id=None, payload=packet, created_at=as_of)
                admitted = accept_signal_decision(self.root, store, strategy=self.strategy,
                    signal_decision=packet["decision"], known_activation_epochs=known,
                    mode=mode, as_of=as_of, skip_fill=True)
            return {**packet, "admission": admitted}
        finally:
            store.close()

    def attempt(self, *, position_id: str, side: str, attempt_key: str, as_of: str):
        store = self._store()
        try:
            position = store.get_position(position_id)
            if position is None:
                raise PaperPlaneError("POSITION_NOT_FOUND")
            bot = store.get_bot(position["bot_instance_id"])
            self._epoch(store, position["activation_epoch_id"], bot["mode"])
            packet = self._origin(store, position)
            decision_at = packet["decision"]["decision_at"]
            if side == "EXIT" and position.get("exit_decision_id"):
                exit_packet = store.get_execution_event("SRC-" + position["exit_decision_id"])
                if exit_packet is None:
                    raise PaperPlaneError("SOURCE_EXIT_PROVENANCE_MISSING")
                decision_at = exit_packet["payload"]["decision"]["decision_at"]
            return begin_modeled_attempt(store, position_id=position_id, side=side, mode=bot["mode"],
                attempt_key=attempt_key, decision_at=decision_at,
                max_age_seconds=self.strategy["signal_input"]["max_age_seconds"], as_of=as_of)
        finally:
            store.close()

    def result(self, result):
        if not isinstance(result, dict):
            raise PaperPlaneError("MODELED_RESULT_OBJECT_REQUIRED")
        store = self._store()
        try:
            attempt = store.get_execution_event(result.get("attempt_id") or "")
            if attempt is None or attempt["event_type"] != "MODELED_ATTEMPT_STARTED":
                raise PaperPlaneError("MODELED_ATTEMPT_MISSING")
            position = store.get_position(attempt["position_id"])
            if position is None:
                raise PaperPlaneError("POSITION_NOT_FOUND")
            bot = store.get_bot(position["bot_instance_id"])
            self._epoch(store, position["activation_epoch_id"], bot["mode"])
            self._origin(store, position)
            accepted = accept_modeled_result(store, result=result)
            accepted["drain"] = maybe_finish_drain(store, accepted["position"]["bot_instance_id"])
            return accepted
        finally:
            store.close()

    def exit(self, *, position_id: str, source_relative: str, as_of: str):
        source = Path(source_relative)
        if source.anchor or PureWindowsPath(source_relative).anchor or ".." in source.parts:
            raise PaperPlaneError("OFFLINE_SOURCE_PATH_UNSAFE")
        source_path = self.data_root / source
        self._safe_path(source_path, strict=True)
        store = self._store()
        try:
            position = store.get_position(position_id)
            if position is None:
                raise PaperPlaneError("POSITION_NOT_FOUND")
            bot = store.get_bot(position["bot_instance_id"])
            if bot["status"] != "RUNNING":
                raise PaperPlaneError("AUTOMATIC_EXIT_INACTIVE_EPOCH_UNRESOLVED_USE_OPERATOR")
            known = self._epoch(store, position["activation_epoch_id"], bot["mode"])
            origin = self._origin(store, position)
            packet = produce_originating_exit(self.root, source_path=source_path, strategy=self.strategy,
                manifest=self.manifest, execution_binding=self.binding, position=position,
                origin_packet=origin, as_of=as_of)
            with store.immediate_write():
                sid = "SRC-" + packet["decision"]["exit_decision_id"]
                previous = store.get_execution_event(sid)
                if previous is not None and previous["payload"] != packet:
                    raise PaperPlaneError("SOURCE_EXIT_CONTENT_CONFLICT")
                if previous is None:
                    store.append_execution_event(event_type="SOURCE_EXIT_PRODUCED", event_id=sid,
                        bot_instance_id=bot["bot_instance_id"], position_id=position_id, payload=packet, created_at=as_of)
                applied = accept_exit_decision(self.root, store, strategy=self.strategy,
                                              exit_decision=packet["decision"], known_activation_epochs=known)
            return {**packet, "exit": applied}
        finally:
            store.close()

    def command(self, command):
        store = self._store()
        try:
            return apply_operator_command(store, command)
        finally:
            store.close()

    def readback(self):
        store = self._store(readonly=True)
        try:
            with store.read_snapshot():
                view = build_operations_projection(store)
                view["evidence_class"] = "SYNTHETIC_OFFLINE"
                view["positions"] = store.positions()
                view["modeled_attempts"] = [event for event in store.execution_events() if event["event_type"] == "MODELED_ATTEMPT_STARTED"]
                view["modeled_results"] = [event for event in store.execution_events() if event["event_type"] == "MODELED_RESULT_ACCEPTED"]
                return view
        finally:
            store.close()
