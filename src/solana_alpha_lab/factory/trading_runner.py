"""Ordinary offline PAPER/SHADOW runner over the existing truth owners.

Definition loading and explicit activation are separate. External observation
and result bytes are inputs; this module has no provider, wallet or live route.
"""
from __future__ import annotations

import json
import re
from pathlib import Path, PureWindowsPath
from typing import Any

from solana_alpha_lab.factory.episode_decision import produce_episode_decision, load_bound_recipe, produce_originating_exit, produce_frozen_time_exit
from solana_alpha_lab.factory.observation_schedule import parse_utc
from solana_alpha_lab.factory.paper_plane import (PaperPlaneStore, accept_signal_decision_outcome,
    accept_exit_decision, begin_modeled_attempt, accept_modeled_result)
from solana_alpha_lab.factory.paper_shadow_commands import apply_operator_command, maybe_finish_drain
from solana_alpha_lab.factory.paper_shadow_operations import build_operations_projection
from solana_alpha_lab.factory.promotion_handoff import compose_science_to_strategy_handoff
from solana_alpha_lab.factory.research_store import ResearchStore
from solana_alpha_lab.factory.strategy_runtime import PaperPlaneError, canonical_spec_sha256, load_strategy_version, validate_and_hash_strategy
from solana_alpha_lab.factory.hfic_research_scope import sha256_of

OFFLINE_MARKER = {"schema": "smial.offline-runtime", "schema_version": "1.0", "evidence_class": "SYNTHETIC_OFFLINE"}


def operating_root(scope_root: Path, data_root: Path) -> Path:
    """Future explicit operator root; independent of synthetic local protection.

    Selecting this boundary grants no external authority. All paths are exact,
    existing non-linked children of an operator-provided scope.
    """
    scope = scope_root.resolve(strict=True)
    if scope != scope_root.absolute():
        raise PaperPlaneError("OPERATING_ROOT_LINK_FORBIDDEN")
    path = data_root.resolve(strict=True)
    if path == scope or not path.is_relative_to(scope) or path != data_root.absolute():
        raise PaperPlaneError("OPERATING_ROOT_UNSAFE")
    for item in (data_root, *data_root.parents):
        if item.is_symlink() or (hasattr(item, "is_junction") and item.is_junction()):
            raise PaperPlaneError("OPERATING_ROOT_LINK_FORBIDDEN")
        if item == scope:
            break
    try:
        marker_path = path / "operating_runtime.json"
        if marker_path.resolve(strict=True) != marker_path or marker_path.stat().st_nlink != 1:
            raise PaperPlaneError("OPERATING_ROOT_MARKER_INVALID")
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise PaperPlaneError("OPERATING_ROOT_MARKER_REQUIRED") from None
    if marker not in [{"schema": "smial.operating-runtime", "schema_version": "1.0", "evidence_class": kind}
                      for kind in ("SYNTHETIC_OFFLINE", "OBSERVED")]:
        raise PaperPlaneError("OPERATING_ROOT_MARKER_INVALID")
    return path


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
        marker_path = path / "offline_runtime.json"
        if marker_path.resolve(strict=True) != marker_path or marker_path.stat().st_nlink != 1:
            raise PaperPlaneError("OFFLINE_ROOT_MARKER_INVALID")
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise PaperPlaneError("OFFLINE_ROOT_MARKER_REQUIRED") from None
    if marker != OFFLINE_MARKER:
        raise PaperPlaneError("OFFLINE_ROOT_MARKER_INVALID")
    return path


class TradingContinuityRunner:
    def __init__(self, root: Path, *, data_root: Path, strategy_relative: str | None = None,
                 resume_epoch: str | None = None, scope_root: Path | None = None):
        self.root = root
        self.data_root = offline_root(root, data_root) if scope_root is None else operating_root(scope_root, data_root)
        self.store_path = self.data_root / "paper_plane.sqlite"
        self._validate_store_paths()
        self.strategy_relative = strategy_relative
        self.strategy = self.manifest = self.binding = self.recipe = None
        self.science_verified = False
        self.scope_root = scope_root
        marker_name = "offline_runtime.json" if scope_root is None else "operating_runtime.json"
        self.evidence_class = json.loads((self.data_root / marker_name).read_text(encoding="utf-8"))["evidence_class"]
        if resume_epoch is not None:
            store = self._store(readonly=True)
            try:
                event = store.get_execution_event("OPERATING-" + resume_epoch)
                if event is None:
                    raise PaperPlaneError("OPERATING_BINDING_MISSING")
                self._set_frozen(event)
            finally:
                store.close()
            return
        if strategy_relative is None:
            return
        self.strategy = load_strategy_version(root, strategy_relative)
        if self.store_path.exists():
            store = self._store(readonly=True)
            try:
                rows = store._conn.execute("SELECT event_id FROM execution_events WHERE event_type='OPERATING_BINDING_COMMITTED'").fetchall()
                for row in rows:
                    event = store.get_execution_event(row[0])
                    if event["payload"].get("strategy", {}).get("spec_sha256") == self.strategy["spec_sha256"]:
                        self._set_frozen(event)
                        # An explicit new loading request cannot hide mutable
                        # spec corruption; cold controls use resume_epoch and
                        # the retained binding instead of the research store.
                        from solana_alpha_lab.factory.experiment_spec import spec_sha256
                        if spec_sha256(self.root, self.manifest["experiment_spec_source_value"]) != self.manifest["experiment_spec_sha256"]:
                            raise PaperPlaneError("EXPERIMENT_SPEC_HASH_CONFLICT")
                        return
            finally:
                store.close()
        self._verify_science()

    def _verify_science(self):
        if self.strategy is None:
            raise PaperPlaneError("EXACT_STRATEGY_PATH_REQUIRED")
        self._safe_path(self.data_root / "research-data", strict=True)
        if self.strategy["schema_version"] != "1.1":
            raise PaperPlaneError("CONTINUITY_REQUIRES_V1_1")
        research = ResearchStore(self.data_root / "research-data", create_if_missing=False)
        selected = research.find_record(self.strategy["source_decision_asset_id"])
        if selected is None:
            raise PaperPlaneError("BOUND_PROMOTE_RECORD_REQUIRED")
        payload = json.loads(selected.payload_json)
        if payload.get("decision_kind") != "PROMOTE":
            raise PaperPlaneError("BOUND_PROMOTE_RECORD_REQUIRED")
        self.manifest = payload.get("promotion_handoff_manifest")
        self.binding = payload.get("execution_evidence_binding")
        if not isinstance(self.manifest, dict) or not isinstance(self.binding, dict):
            raise PaperPlaneError("LEGACY_PROVENANCE_GAP")
        refs = {item["record_id"] for item in self.manifest.get("direct_evidence", [])}
        refs.update(item["record_id"] for item in self.binding.get("direct_evidence_refs", []))
        exact_records = [selected]
        for record_id in sorted(refs - {selected.record_id}):
            record = research.find_record(record_id)
            if record is None:
                raise PaperPlaneError("BOUND_DIRECT_EVIDENCE_REQUIRED")
            exact_records.append(record)
        check = compose_science_to_strategy_handoff(root=self.root, experiment_id=self.manifest["experiment_id"],
            records=exact_records, records_status="AVAILABLE", execution_inputs={
                "max_age_seconds": self.strategy["signal_input"]["max_age_seconds"],
                **self.strategy["notional_policy"], **self.strategy["risk_policy"],
                "shadow": self.strategy["mode_eligibility"]["shadow"],
            })
        if check["state"]["blocker_codes"]:
            raise PaperPlaneError(check["state"]["blocker_codes"][0])
        self.recipe = load_bound_recipe(self.root, strategy=self.strategy, manifest=self.manifest, execution_binding=self.binding)
        self.promote_ref = {"record_id": selected.record_id, "payload_sha256": selected.payload_sha256,
                            "producer_git_sha": selected.producer_git_sha}
        self.science_verified = True

    def _set_frozen(self, event):
        import base64
        import hashlib
        import yaml
        from solana_alpha_lab.factory.episode_decision import bound_recipe_body
        from solana_alpha_lab.factory.promotion_handoff import verify_strategy_version
        payload = event["payload"]
        if not isinstance(payload, dict):
            raise PaperPlaneError("OPERATING_BINDING_INTEGRITY_CONFLICT")
        unsigned = {key: value for key, value in payload.items() if key != "binding_sha256"}
        if event["event_type"] != "OPERATING_BINDING_COMMITTED" or sha256_of(unsigned) != payload.get("binding_sha256"):
            raise PaperPlaneError("OPERATING_BINDING_INTEGRITY_CONFLICT")
        strategy = validate_and_hash_strategy(self.root, payload["strategy"])
        verify_strategy_version(self.root, strategy, manifest=payload["manifest"],
            decision_event_id=payload["promote_ref"]["record_id"],
            execution_evidence_binding=payload["execution_binding"])
        try:
            raw_spec = base64.b64decode(payload["experiment_spec_bytes_b64"], validate=True)
            document = yaml.safe_load(raw_spec.decode("utf-8"))
        except (ValueError, TypeError, KeyError, yaml.YAMLError):
            raise PaperPlaneError("OPERATING_SPEC_INTEGRITY_CONFLICT") from None
        if (hashlib.sha256(raw_spec).hexdigest() != payload["manifest"]["experiment_spec_sha256"]
            or bound_recipe_body(document, strategy=strategy) != payload["recipe"]
            or document["experiment_id"] != payload["manifest"]["experiment_id"]):
            raise PaperPlaneError("OPERATING_SPEC_INTEGRITY_CONFLICT")
        if strategy["strategy_version"] != "V1" or strategy["source_decision_asset_id"] != payload["promote_ref"]["record_id"]:
            raise PaperPlaneError("OPERATING_BINDING_INTEGRITY_CONFLICT")
        activation = payload["activation"]
        if (activation["strategy_sha256"], event["event_id"]) != (strategy["spec_sha256"], "OPERATING-" + activation["epoch_id"]):
            raise PaperPlaneError("OPERATING_BINDING_INTEGRITY_CONFLICT")
        self.strategy, self.manifest, self.binding, self.recipe = strategy, payload["manifest"], payload["execution_binding"], payload["recipe"]
        self.promote_ref = payload["promote_ref"]

    def for_epoch(self, epoch_id):
        return TradingContinuityRunner(self.root, data_root=self.data_root, resume_epoch=epoch_id, scope_root=self.scope_root)

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

    def _store(self, *, readonly=False, bootstrap=False):
        self._validate_store_paths()
        if not bootstrap and not self.store_path.is_file():
            raise PaperPlaneError("SOURCE_NOT_PRESENT")
        return PaperPlaneStore(self.store_path, readonly=readonly)

    def activate(self, *, epoch_id: str, mode: str, at: str, transaction_store=None) -> dict[str, Any]:
        if self.strategy is None:
            raise PaperPlaneError("EXACT_STRATEGY_PATH_REQUIRED")
        if mode not in {"PAPER", "SHADOW"} or not re.fullmatch(r"ACTIVATION-EPOCH-[A-Z0-9]+(?:-[A-Z0-9]+)*", epoch_id):
            raise PaperPlaneError("OFFLINE_ACTIVATION_SCOPE_INVALID")
        if self.strategy["mode_eligibility"].get(mode.lower()) is not True or self.strategy["mode_eligibility"].get("micro_live") is not False:
            raise PaperPlaneError("MODE_NOT_ELIGIBLE")
        if parse_utc(at) < parse_utc(self.manifest["decision_effective_at"]):
            raise PaperPlaneError("ACTIVATION_BEFORE_PROMOTE")
        binding = {"epoch_id": epoch_id, "mode": mode, "at": at,
                   "strategy_id": self.strategy["strategy_id"], "strategy_version": self.strategy["strategy_version"],
                   "strategy_sha256": self.strategy["spec_sha256"], "evidence_class": self.evidence_class}
        # A new epoch requires verifiable original science. An exact replay
        # below does not re-bootstrap or fabricate legacy bindings.
        if not self.science_verified:
            if self.store_path.exists():
                probe = self._store(readonly=True)
                try:
                    prior = probe.get_execution_event(epoch_id)
                finally:
                    probe.close()
                if prior is not None and prior["payload"] == binding:
                    return {**binding, "idempotent": True}
            self._verify_science()
        store = transaction_store or self._store(bootstrap=True)
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
                frozen = {"schema": "smial.operating-binding", "schema_version": "1.0", "activation": binding,
                          "strategy": self.strategy, "manifest": self.manifest, "execution_binding": self.binding,
                          "recipe": self.recipe, "promote_ref": self.promote_ref}
                import base64
                frozen["experiment_spec_bytes_b64"] = base64.b64encode(
                    (self.root / self.manifest["experiment_spec_source_value"]).read_bytes()).decode("ascii")
                frozen["binding_sha256"] = sha256_of(frozen)
                self._set_frozen({"event_type": "OPERATING_BINDING_COMMITTED", "event_id": "OPERATING-" + epoch_id, "payload": frozen})
                store.append_execution_event(event_type="OPERATING_BINDING_COMMITTED", event_id="OPERATING-" + epoch_id,
                    bot_instance_id=bot["bot_instance_id"], position_id=None, payload=frozen, created_at=at)
                return {**binding, "idempotent": False}
        finally:
            if transaction_store is None:
                store.close()

    def _epoch(self, store, epoch_id, mode):
        record = store.get_execution_event(epoch_id)
        if record is None or record["event_type"] != "OFFLINE_ACTIVATION_CREATED":
            raise PaperPlaneError("EXPLICIT_OFFLINE_ACTIVATION_REQUIRED")
        bound = record["payload"]
        frozen = store.get_execution_event("OPERATING-" + epoch_id)
        if frozen is not None:
            self._set_frozen(frozen)
            if frozen["payload"]["activation"] != bound:
                raise PaperPlaneError("OPERATING_BINDING_INTEGRITY_CONFLICT")
        if (bound["mode"], bound["strategy_sha256"]) != (mode, self.strategy["spec_sha256"]):
            raise PaperPlaneError("ACTIVATION_BINDING_CONFLICT")
        return {epoch_id: bound}

    def _origin(self, store, position):
        record = store.get_execution_event("SRC-" + position["signal_decision_id"])
        if record is None or record["event_type"] != "SOURCE_DECISION_PRODUCED":
            raise PaperPlaneError("SOURCE_DECISION_PROVENANCE_MISSING")
        packet = record["payload"]
        if (not isinstance(packet, dict) or not isinstance(packet.get("provenance"), dict)
            or not isinstance(packet.get("decision"), dict)):
            raise PaperPlaneError("SOURCE_DECISION_PROVENANCE_CONFLICT")
        provenance = packet["provenance"]
        decision = packet["decision"]
        digest = sha256_of(provenance)
        if (packet.get("provenance_sha256") != digest
            or canonical_spec_sha256(decision) != position.get("signal_decision_sha256")
            or decision.get("evidence_refs") != ["execution-event:SRC-" + position["signal_decision_id"] + ":sha256:" + digest]
            or (decision.get("signal_decision_id"), decision.get("strategy_id"), decision.get("strategy_version"),
                decision.get("activation_epoch_id"), decision.get("mint")) !=
               (position["signal_decision_id"], self.strategy["strategy_id"], self.strategy["strategy_version"],
                position["activation_epoch_id"], position["mint"])
            or provenance.get("strategy_sha256") != self.strategy["spec_sha256"]
            or provenance.get("promotion_handoff_manifest_sha256") != self.manifest["manifest_sha256"]):
            raise PaperPlaneError("SOURCE_DECISION_PROVENANCE_CONFLICT")
        return packet

    def _exit_origin(self, store, position):
        eid = position["exit_decision_id"]
        record = store.get_execution_event("SRC-" + eid)
        binding = store.get_execution_event("EXITBIND-" + eid)
        if record is None or binding is None:
            raise PaperPlaneError("SOURCE_EXIT_PROVENANCE_MISSING")
        packet = record["payload"]
        if not isinstance(packet, dict):
            raise PaperPlaneError("SOURCE_EXIT_PROVENANCE_CONFLICT")
        expected = {"source_event_id": "SRC-" + eid, "exit_decision_id": eid,
                    "position_id": position["position_id"],
                    "signal_decision_sha256": position["signal_decision_sha256"],
                    "packet_sha256": canonical_spec_sha256(packet)}
        if (record["event_type"] != "SOURCE_EXIT_PRODUCED"
            or binding["event_type"] != "SOURCE_EXIT_ADMISSION_BOUND"
            or record["position_id"] != position["position_id"]
            or binding["position_id"] != position["position_id"]
            or record["bot_instance_id"] != position["bot_instance_id"]
            or binding["bot_instance_id"] != position["bot_instance_id"]
            or binding["payload"] != expected):
            raise PaperPlaneError("SOURCE_EXIT_PROVENANCE_CONFLICT")
        return packet

    def episode(self, *, source_relative: str, episode_id: str, epoch_id: str, mode: str, as_of: str,
                ordinary_operating=False, source_path: Path | None = None):
        source = Path(source_relative)
        if source.anchor or PureWindowsPath(source_relative).anchor or ".." in source.parts:
            raise PaperPlaneError("OFFLINE_SOURCE_PATH_UNSAFE")
        source_path = source_path or self.data_root / source
        if source_path.is_relative_to(self.data_root):
            self._safe_path(source_path, strict=True)
        store = self._store()
        try:
            known = self._epoch(store, epoch_id, mode)
            if parse_utc(as_of) < parse_utc(known[epoch_id]["at"]):
                raise PaperPlaneError("DECISION_BEFORE_ACTIVATION")
            packet = produce_episode_decision(self.root, source_path=source_path, strategy=self.strategy,
                manifest=self.manifest, execution_binding=self.binding, epoch_id=epoch_id,
                episode_id=episode_id, as_of=as_of, frozen_recipe=self.recipe)
            with store.immediate_write():
                sid = "SRC-" + packet["decision"]["signal_decision_id"]
                previous = store.get_execution_event(sid)
                if previous is not None and previous["payload"] != packet:
                    raise PaperPlaneError("SOURCE_DECISION_CONTENT_CONFLICT")
                if previous is None:
                    store.append_execution_event(event_type="SOURCE_DECISION_PRODUCED", event_id=sid,
                        bot_instance_id=None, position_id=None, payload=packet, created_at=as_of)
                extra = {"ordinary_operating": True} if ordinary_operating else {}
                admitted = accept_signal_decision_outcome(self.root, store, strategy=self.strategy,
                    signal_decision=packet["decision"], known_activation_epochs=known,
                    mode=mode, as_of=as_of, skip_fill=True, **extra)
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
                decision_at = self._exit_origin(store, position)["decision"]["decision_at"]
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
            if self.strategy is None or self.strategy["spec_sha256"] != position["strategy_spec_sha256"]:
                return self.for_epoch(position["activation_epoch_id"]).result(result)
            self._epoch(store, position["activation_epoch_id"], bot["mode"])
            self._origin(store, position)
            if attempt["payload"]["side"] == "EXIT" and position.get("exit_decision_id"):
                self._exit_origin(store, position)
            accepted = accept_modeled_result(store, result=result)
            accepted["drain"] = maybe_finish_drain(store, accepted["position"]["bot_instance_id"])
            return accepted
        finally:
            store.close()

    def exit(self, *, position_id: str, source_relative: str, as_of: str, ordinary_operating=False):
        source = Path(source_relative)
        if source.anchor or PureWindowsPath(source_relative).anchor or ".." in source.parts:
            raise PaperPlaneError("OFFLINE_SOURCE_PATH_UNSAFE")
        source_path = self.data_root / source
        if not ordinary_operating:
            self._safe_path(source_path, strict=True)
        store = self._store()
        try:
            position = store.get_position(position_id)
            if position is None:
                raise PaperPlaneError("POSITION_NOT_FOUND")
            bot = store.get_bot(position["bot_instance_id"])
            if bot["status"] != "RUNNING" and not ordinary_operating:
                raise PaperPlaneError("AUTOMATIC_EXIT_INACTIVE_EPOCH_UNRESOLVED_USE_OPERATOR")
            known = self._epoch(store, position["activation_epoch_id"], bot["mode"])
            origin = self._origin(store, position)
            if ordinary_operating:
                packet = produce_frozen_time_exit(self.root, strategy=self.strategy, position=position,
                    origin_packet=origin, frozen_recipe=self.recipe, as_of=as_of)
            else:
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
                if applied["applied"]:
                    binding = {"source_event_id": sid,
                               "exit_decision_id": packet["decision"]["exit_decision_id"],
                               "position_id": position_id,
                               "signal_decision_sha256": position["signal_decision_sha256"],
                               "packet_sha256": canonical_spec_sha256(packet)}
                    binding_id = "EXITBIND-" + packet["decision"]["exit_decision_id"]
                    prior_binding = store.get_execution_event(binding_id)
                    if prior_binding is not None and (
                        prior_binding["payload"] != binding
                        or prior_binding["event_type"] != "SOURCE_EXIT_ADMISSION_BOUND"
                        or prior_binding["position_id"] != position_id
                        or prior_binding["bot_instance_id"] != bot["bot_instance_id"]):
                        raise PaperPlaneError("SOURCE_EXIT_PROVENANCE_CONFLICT")
                    if prior_binding is None:
                        store.append_execution_event(event_type="SOURCE_EXIT_ADMISSION_BOUND", event_id=binding_id,
                            bot_instance_id=bot["bot_instance_id"], position_id=position_id,
                            payload=binding, created_at=as_of)
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
                view["evidence_class"] = self.evidence_class
                view["positions"] = store.positions()
                view["admission_refusals"] = [event for event in store.execution_events()
                    if event["event_type"] == "SIGNAL_ADMISSION_DENIED"]
                view["modeled_attempts"] = [event for event in store.execution_events() if event["event_type"] == "MODELED_ATTEMPT_STARTED"]
                view["modeled_results"] = [event for event in store.execution_events() if event["event_type"] == "MODELED_RESULT_ACCEPTED"]
                return view
        finally:
            store.close()
