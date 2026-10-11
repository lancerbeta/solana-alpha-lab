"""One ordinary bounded tick, same tick in run, over the PaperPlane owners."""
from __future__ import annotations

import json
import os
import sqlite3
import time
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from solana_alpha_lab.factory.trading_runner import TradingContinuityRunner
from solana_alpha_lab.factory.trading_adapters import PaperModelAdapter, JupiterQuoteAdapter, raw_amount, checked_observation
from solana_alpha_lab.factory.paper_plane import PRE_ATTEMPT_STATES, accept_exit_decision
from solana_alpha_lab.factory.paper_shadow_commands import maybe_finish_drain, apply_operator_command
from solana_alpha_lab.factory.observation_schedule import parse_utc, render_utc
from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
from solana_alpha_lab.factory.opportunity_episodes import admission_content_sha256, resolve_point, schedule_binding, object_sha256
from solana_alpha_lab.factory.episode_decision import _Prefix
from solana_alpha_lab.factory.hfic_temporal_discovery import episode_decision_price
from solana_alpha_lab.factory.strategy_runtime import PaperPlaneError
from solana_alpha_lab.factory.hfic_research_scope import sha256_of


def exact_child(root, relative, *, exists=True):
    path = root / Path(relative)
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise PaperPlaneError("OPERATING_CHILD_PATH_UNSAFE")
    resolved = path.resolve(strict=exists)
    if resolved != path.absolute() or not resolved.is_relative_to(root.resolve()):
        raise PaperPlaneError("OPERATING_CHILD_ALIAS_FORBIDDEN")
    for item in (path, *path.parents):
        if item.is_symlink() or (hasattr(item, "is_junction") and item.is_junction()):
            raise PaperPlaneError("OPERATING_CHILD_ALIAS_FORBIDDEN")
        if item == root:
            break
    if path.is_file() and path.stat().st_nlink != 1:
        raise PaperPlaneError("OPERATING_CHILD_ALIAS_FORBIDDEN")
    return path


def normalize_profile(profile, *, recipe, mode):
    required = {"schema_version", "mode", "source", "batch_size", "poll_seconds", "source_max_age_seconds",
                "progress_max_age_seconds", "observation_max_age_seconds", "envelope", "model", "quote", "network_authorized"}
    if set(profile) != required or profile["schema_version"] != "1.0" or profile["mode"] != mode or mode not in {"PAPER", "SHADOW"}:
        raise PaperPlaneError("OPERATING_PROFILE_INVALID")
    if profile["network_authorized"] is not False:
        raise PaperPlaneError("PROFILE_CANNOT_GRANT_NETWORK_AUTHORITY")
    for field in ("batch_size", "source_max_age_seconds", "progress_max_age_seconds", "observation_max_age_seconds"):
        if type(profile[field]) is not int or not 0 < profile[field] <= 1000000:
            raise PaperPlaneError("OPERATING_PROFILE_LIMIT_INVALID")
    if type(profile["poll_seconds"]) not in {int, float} or not 0 < profile["poll_seconds"] <= 3600:
        raise PaperPlaneError("OPERATING_PROFILE_LIMIT_INVALID")
    source = profile["source"]
    if set(source) != {"root", "file", "schedule_sha256", "activation_id"}:
        raise PaperPlaneError("OPERATING_SOURCE_BINDING_INVALID")
    source_root = Path(source["root"])
    if not source_root.is_absolute() or source_root.resolve(strict=True) != source_root:
        raise PaperPlaneError("OPERATING_SOURCE_BINDING_INVALID")
    exact_child(source_root, source["file"])
    rule = recipe.get("executable_exit")
    if rule != {"kind": "FROZEN_TIME_EXIT", "exit_point": recipe["target"]["exit_point"]}:
        raise PaperPlaneError("EXECUTABLE_EXIT_BINDING_REQUIRED")
    PaperModelAdapter(profile["model"])
    quote = profile["quote"]
    if set(quote) != {"timeout_seconds", "max_response_bytes", "funding_mint", "asset_metadata_file", "funding_observation_file", "max_exit_input_raw"}:
        raise PaperPlaneError("QUOTE_PROFILE_INVALID")
    cap = quote["max_exit_input_raw"]
    if cap is not None and (not isinstance(cap, str) or not cap.isdigit() or not 0 < int(cap) < 10 ** 30):
        raise PaperPlaneError("QUOTE_EXIT_LEG_LIMIT_INVALID")
    JupiterQuoteAdapter(timeout_seconds=quote["timeout_seconds"], max_response_bytes=quote["max_response_bytes"])
    for key in ("asset_metadata_file","funding_observation_file"):
        if quote[key] is None and key=="asset_metadata_file":
            continue
        if not isinstance(quote[key],str) or not quote[key] or Path(quote[key]).is_absolute() or ".." in Path(quote[key]).parts:
            raise PaperPlaneError("QUOTE_INPUT_PATH_INVALID")
    return json.loads(json.dumps(profile, allow_nan=False))


def check_execution_inputs(profile, *, as_of):
    """Read-only quote input preflight, independent of external authority."""
    if profile["mode"]!="SHADOW":
        return {"execution_input_status":"PAPER_NATIVE_PREFIX"}
    cfg=profile["quote"]
    root=Path(profile["source"]["root"])
    try:
        checked_observation(json.loads(exact_child(root,cfg["funding_observation_file"]).read_text(encoding="utf-8")),
            mint=cfg["funding_mint"],as_of=as_of,max_age_seconds=profile["observation_max_age_seconds"])
        if cfg["asset_metadata_file"] is not None:
            metadata=json.loads(exact_child(root,cfg["asset_metadata_file"]).read_text(encoding="utf-8"))
            if not isinstance(metadata,dict) or not metadata:
                raise PaperPlaneError("EXECUTION_ASSET_METADATA_REQUIRED")
            for mint,asset in metadata.items():
                if asset.get("mint")!=mint or type(asset.get("decimals")) is not int or not 0<=asset["decimals"]<=18:
                    raise PaperPlaneError("EXECUTION_ASSET_IDENTITY_INVALID")
                if not parse_utc(asset["observed_at"])<=parse_utc(asset["available_at"])<=parse_utc(as_of):
                    raise PaperPlaneError("EXECUTION_OBSERVATION_STALE_OR_FUTURE")
    except FileNotFoundError:
        raise PaperPlaneError("EXECUTION_QUOTE_INPUT_NOT_PRESENT") from None
    return {"execution_input_status":"QUOTE_INPUTS_VERIFIED","asset_metadata_source":"NATIVE_WITNESS" if cfg["asset_metadata_file"] is None else "BOUND_SOURCE_FILE"}


def ensure_schema(store):
    # Only explicit initialization/activation invokes this additive migration.
    for sql in (
        "CREATE TABLE IF NOT EXISTS ordinary_state(mode TEXT PRIMARY KEY, epoch_id TEXT NOT NULL, generation INTEGER NOT NULL, discovery_rowid INTEGER NOT NULL DEFAULT 0, rescan_rowid INTEGER NOT NULL DEFAULT 0, last_tick_at TEXT, last_progress_at TEXT, last_work_id TEXT, source_status TEXT, source_latest_at TEXT, restore_guard INTEGER NOT NULL DEFAULT 0)",
        "CREATE TABLE IF NOT EXISTS ordinary_work(epoch_id TEXT NOT NULL, episode_id TEXT NOT NULL, source_sha256 TEXT NOT NULL, cutoff TEXT NOT NULL, status TEXT NOT NULL, position_id TEXT, evaluation_revision TEXT, PRIMARY KEY(epoch_id,episode_id))",
        "CREATE INDEX IF NOT EXISTS ordinary_work_due ON ordinary_work(epoch_id,status,cutoff)",
        "CREATE TABLE IF NOT EXISTS ordinary_incidents(incident_key TEXT PRIMARY KEY, reason TEXT NOT NULL, first_at TEXT NOT NULL, last_changed_at TEXT NOT NULL, active INTEGER NOT NULL, occurrences INTEGER NOT NULL)",
    ):
        store._conn.execute(sql)
    columns = {row[1] for row in store._conn.execute("PRAGMA table_info(ordinary_state)")}
    if "source_latest_at" not in columns:
        store._conn.execute("ALTER TABLE ordinary_state ADD COLUMN source_latest_at TEXT")
    if "rescan_rowid" not in columns:
        store._conn.execute("ALTER TABLE ordinary_state ADD COLUMN rescan_rowid INTEGER NOT NULL DEFAULT 0")


@contextmanager
def single_writer(runner):
    path = exact_child(runner.data_root, ".ordinary-writer.lock", exists=False)
    with path.open("a+b") as handle:
        handle.seek(0)
        if path.stat().st_size == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise PaperPlaneError("ORDINARY_WRITER_ALREADY_OWNED") from None
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


class TradingCoordinator:
    def __init__(self, runner, *, mode, clock=None, quote_adapter=None, fault=None):
        if mode not in {"PAPER", "SHADOW"}:
            raise PaperPlaneError("LIVE_ROUTE_FORBIDDEN")
        self.runner, self.mode = runner, mode
        self.clock = clock or (lambda: datetime.now(UTC))
        self.quote_adapter, self.fault = quote_adapter, fault or (lambda _point: None)

    def activate(self, *, epoch_id, at, profile, switch_key, expected_current_epoch=None):
        from solana_alpha_lab.factory.trading_runtime_policy import configure_operating_envelope, read_operating_envelope
        candidate = normalize_profile(profile, recipe=self.runner.recipe, mode=self.mode)
        check_execution_inputs(candidate,as_of=render_utc(self.clock()))
        # Verify source schedule before disabling any old entries.
        source = self._source(candidate)
        try:
            schedule = source.get_registered_schedule(candidate["source"]["schedule_sha256"])
            if schedule is None:
                raise PaperPlaneError("EPISODE_SCHEDULE_BINDING_MISSING")
            resolve_point(schedule_binding(schedule["document"]), parse_utc(at), self.runner.recipe["decision_point"])
            resolve_point(schedule_binding(schedule["document"]), parse_utc(at), self.runner.recipe["target"]["exit_point"])
        finally:
            source.close()
        body = {"epoch_id": epoch_id, "at": at, "mode": self.mode, "profile": candidate,
                "strategy_sha256": self.runner.strategy["spec_sha256"], "expected_current_epoch": expected_current_epoch}
        event_id = "SWITCH-" + sha256_of({"key": switch_key})
        store = self.runner._store(bootstrap=True)
        try:
            with store.immediate_write():
                ensure_schema(store)
                prior = store.get_execution_event(event_id)
                if prior is not None:
                    if prior["payload"] != body:
                        raise PaperPlaneError("OPERATING_SWITCH_CONTENT_CONFLICT")
                    return {"idempotent": True, "epoch_id": epoch_id}
                current = store._conn.execute("SELECT * FROM ordinary_state WHERE mode=?", (self.mode,)).fetchone()
                current_epoch = current["epoch_id"] if current else None
                if current_epoch != expected_current_epoch:
                    raise PaperPlaneError("OPERATING_SWITCH_STALE_CURRENT")
                legacy = [bot for bot in store.bots() if bot["mode"] == self.mode and bot["status"] == "RUNNING"
                          and not bot["entries_paused"] and bot.get("activation_epoch_id") not in {current_epoch, epoch_id}]
                if legacy:
                    raise PaperPlaneError("LEGACY_ENTRY_ENABLED_CONFLICT")
                envelope = read_operating_envelope(store, self.mode)
                normalized = candidate["envelope"]
                if envelope.get("status") == "VALID":
                    from solana_alpha_lab.factory.trading_runtime_policy import normalize_operating_envelope
                    if envelope.get("policy", envelope.get("envelope")) != normalize_operating_envelope(normalized, mode=self.mode):
                        raise PaperPlaneError("SWITCH_CANNOT_CHANGE_OPERATING_ENVELOPE")
                else:
                    configure_operating_envelope(store, mode=self.mode, candidate_raw=normalized,
                        expected_current_sha256=envelope.get("envelope_sha256") or "0" * 64,
                        idempotency_key="ENVELOPE-" + switch_key, as_of=at)
                activated = self.runner.activate(epoch_id=epoch_id, mode=self.mode, at=at, transaction_store=store)
                if current_epoch and current_epoch != epoch_id:
                    old = next(bot for bot in store.bots() if bot.get("activation_epoch_id") == current_epoch and bot["mode"] == self.mode)
                    apply_operator_command(store, {"command_type": "STOP_BOT", "idempotency_key": "DRAIN-" + switch_key,
                                                   "bot_instance_id": old["bot_instance_id"]})
                profile_id = "PROFILE-" + epoch_id
                frozen = {"profile": candidate, "profile_sha256": sha256_of(candidate)}
                prior_profile = store.get_execution_event(profile_id)
                if prior_profile and prior_profile["payload"] != frozen:
                    raise PaperPlaneError("OPERATING_PROFILE_CONTENT_CONFLICT")
                if prior_profile is None:
                    store.append_execution_event(event_type="OPERATING_PROFILE_COMMITTED", event_id=profile_id,
                        bot_instance_id=None, position_id=None, payload=frozen, created_at=at)
                generation = int(current["generation"]) + 1 if current else 1
                store._conn.execute("INSERT INTO ordinary_state(mode,epoch_id,generation) VALUES(?,?,?) ON CONFLICT(mode) DO UPDATE SET epoch_id=excluded.epoch_id,generation=excluded.generation,discovery_rowid=0,rescan_rowid=0",
                                    (self.mode, epoch_id, generation))
                store.append_execution_event(event_type="OPERATING_SWITCH_COMMITTED", event_id=event_id,
                    bot_instance_id=None, position_id=None, payload=body, created_at=at)
                return {**activated, "generation": generation}
        finally:
            store.close()

    def _profile(self, store, epoch):
        event = store.get_execution_event("PROFILE-" + epoch)
        if event is None:
            raise PaperPlaneError("OPERATING_PROFILE_REQUIRED")
        payload = event["payload"]
        if (not isinstance(payload,dict) or set(payload)!={"profile","profile_sha256"} or not isinstance(payload["profile"],dict)
            or payload["profile_sha256"] != sha256_of(payload["profile"])):
            raise PaperPlaneError("OPERATING_PROFILE_INTEGRITY_CONFLICT")
        return payload["profile"]

    def _source(self, profile):
        cfg = profile["source"]
        source = exact_child(Path(cfg["root"]), cfg["file"])
        for suffix in ("-wal", "-shm", "-journal"):
            exact_child(Path(cfg["root"]), cfg["file"] + suffix, exists=False)
        return ObservationScheduleStore(source, readonly=True, immutable=False)

    @staticmethod
    def _source_latest(source, profile):
        cfg = profile["source"]
        stamps = [source._conn.execute(f"SELECT MAX(created_at) FROM {table} WHERE schedule_sha256=? AND activation_id=?",
                  (cfg["schedule_sha256"], cfg["activation_id"])).fetchone()[0]
                  for table in ("episode_rounds", "episode_outbox", "episode_publications")]
        return max((stamp for stamp in stamps if stamp is not None), default=None)

    def _incident(self, store, key, reason, at):
        with store.immediate_write():
            old = store._conn.execute("SELECT * FROM ordinary_incidents WHERE incident_key=?", (key,)).fetchone()
            if old and old["reason"] == reason and old["active"]:
                # Count occurrence in place, no event storm or notification fanout.
                store._conn.execute("UPDATE ordinary_incidents SET occurrences=occurrences+1 WHERE incident_key=?", (key,))
            else:
                store._conn.execute("INSERT INTO ordinary_incidents VALUES(?,?,?,?,1,1) ON CONFLICT(incident_key) DO UPDATE SET reason=excluded.reason,last_changed_at=excluded.last_changed_at,active=1,occurrences=ordinary_incidents.occurrences+1", (key, reason, at, at))

    def _inputs(self, bound, store, position, profile, side, at):
        origin = bound._origin(store, position)
        admission = origin["provenance"]["origin_admission"]
        point = bound.recipe["decision_point"] if side == "ENTRY" else bound.recipe["target"]["exit_point"]
        schedule = origin["provenance"]["schedule_binding"]
        resolved = resolve_point(schedule, parse_utc(admission["t0"]), point)
        price = None
        try:
            source = self._source(profile)
            try:
                with source.read_snapshot():
                    current = source.get_episode_admission(admission["episode_id"])
                    if current is None or admission_content_sha256(current["record"]) != origin["provenance"]["admission_content_sha256"]:
                        raise PaperPlaneError("EXIT_ORIGIN_SOURCE_CONFLICT")
                    prefix = _Prefix(source, admission, schedule, resolved.availability_deadline, Path(profile["source"]["root"]))
                    cell = episode_decision_price(prefix, cohort=admission["cohort_id"], release="TIMELY_PREFIX",
                        episode_id=admission["episode_id"], decision_point=point,
                        decision_deadline=resolved.availability_deadline, snapshot_policy=bound.recipe["observation_clock_policy"],
                        decision_due_at=resolved.request_not_before)
                    if cell.get("status") == "OBSERVED" and (parse_utc(at) - resolved.request_not_before).total_seconds() <= profile["observation_max_age_seconds"]:
                        price = str(cell["value"])
            finally:
                source.close()
        except (OSError, sqlite3.Error):
            pass  # Missing execution input becomes UNKNOWN; origin errors do not.
        request = {"activation_epoch_id": position["activation_epoch_id"], "strategy_sha256": position["strategy_spec_sha256"],
                   "unit_price_usd": price, "admitted_notional_usd": position["admitted_entry_notional_usd_dec"],
                   "observation_valid_until": render_utc(resolved.request_not_before+timedelta(seconds=profile["observation_max_age_seconds"])),
                   "result_at": render_utc(parse_utc(at) + timedelta(seconds=profile["model"]["latency_seconds"]))}
        if self.mode == "SHADOW":
            cfg = profile["quote"]
            root = Path(profile["source"]["root"])
            funding = checked_observation(json.loads(exact_child(root, cfg["funding_observation_file"]).read_text(encoding="utf-8")),
                mint=cfg["funding_mint"], as_of=at, max_age_seconds=profile["observation_max_age_seconds"])
            request["funding_valid_until"] = render_utc(parse_utc(funding["observed_at"])+timedelta(seconds=profile["observation_max_age_seconds"]))
            entries=store.filtered_execution_events(event_type="ADAPTER_REQUEST_BOUND",position_ids=[position["position_id"]]) if side=="EXIT" else []
            retained=next((event["payload"] for event in entries if event["payload"].get("asset_metadata") and event["payload"].get("outputMint")==position["mint"]),None)
            if retained:
                asset=retained["asset_metadata"]
                if sha256_of(asset)!=retained["asset_metadata_sha256"] or retained["request_sha256"]!=sha256_of({k:v for k,v in retained.items() if k!="request_sha256"}):
                    raise PaperPlaneError("EXECUTION_ASSET_METADATA_INTEGRITY_CONFLICT")
            elif cfg["asset_metadata_file"] is None:
                import hashlib
                raw=exact_child(root,admission["witness_raw_body_rel"]).read_bytes()
                witness=json.loads(raw)
                if (hashlib.sha256(raw).hexdigest()!=Path(admission["witness_raw_body_rel"]).stem
                    or witness.get("schema")!="smial.opportunity-episode-witness-extract" or witness.get("schema_version")!="1.0"
                    or witness.get("source_response_sha256")!=admission["witness_response_sha256"]
                    or witness.get("object_sha256")!=admission["witness_object_sha256"]):
                    raise PaperPlaneError("EXECUTION_ASSET_WITNESS_INTEGRITY_CONFLICT")
                row=witness.get("object")
                if not isinstance(row,dict) or object_sha256(row)!=admission["witness_object_sha256"] or row.get("id")!=position["mint"] or witness.get("mint")!=position["mint"]:
                    raise PaperPlaneError("EXECUTION_ASSET_WITNESS_IDENTITY_CONFLICT")
                asset={"mint":position["mint"],"decimals":row.get("decimals"),
                    "observed_at":admission["witness_response_received_at"],"available_at":admission["witness_first_reliable_available_at"],
                    "witness_response_sha256":admission["witness_response_sha256"],"witness_object_sha256":admission["witness_object_sha256"]}
            else:
                asset=json.loads(exact_child(root,cfg["asset_metadata_file"]).read_text(encoding="utf-8"))[position["mint"]]
            token_decimals = asset["decimals"]
            if asset.get("mint") != position["mint"] or type(token_decimals) is not int or not 0 <= token_decimals <= 18:
                raise PaperPlaneError("EXECUTION_ASSET_IDENTITY_INVALID")
            if not parse_utc(asset["observed_at"]) <= parse_utc(asset["available_at"]) <= parse_utc(at):
                raise PaperPlaneError("EXECUTION_OBSERVATION_STALE_OR_FUTURE")
            request.update(funding_price_usd=funding["unit_price_usd"], funding_observation_sha256=sha256_of(funding),
                           asset_metadata_sha256=sha256_of(asset),asset_metadata=asset)
            if side == "ENTRY":
                units = Decimal(request["admitted_notional_usd"]) / Decimal(funding["unit_price_usd"])
                request.update(inputMint=cfg["funding_mint"], outputMint=position["mint"], amount=raw_amount(units, funding["decimals"]),
                               input_decimals=funding["decimals"], output_decimals=token_decimals)
            else:
                quantity = position.get("remaining_qty_dec") or position["qty_dec"]
                request.update(inputMint=position["mint"], outputMint=cfg["funding_mint"], amount=raw_amount(quantity, token_decimals),
                               input_decimals=token_decimals, output_decimals=funding["decimals"], remaining_quantity=quantity)
                if cfg["max_exit_input_raw"] is not None:
                    request["amount"] = str(min(int(request["amount"]), int(cfg["max_exit_input_raw"])))
        request["request_sha256"] = sha256_of(request)
        return request

    def _dispatch(self, store, bound, position, profile, side, at):
        from solana_alpha_lab.factory.trading_runtime_policy import enforce_operating_envelope
        guarded = store._conn.execute("SELECT restore_guard FROM ordinary_state WHERE mode=?", (self.mode,)).fetchone()
        if guarded and guarded[0]:
            raise PaperPlaneError("RESTORE_RECONCILIATION_REQUIRED")
        # Request is prepared without a write transaction or HTTP; it is frozen
        # with attempt before effect, not re-created on restart from latest data.
        request = self._inputs(bound, store, position, profile, side, at)
        # I/O or a prior quote may consume an entry's TTL. The atomic claim
        # uses the current clock, never the tick's cached start time.
        at = render_utc(self.clock())
        if parse_utc(at) > parse_utc(request["observation_valid_until"]):
            request["unit_price_usd"] = None
        if self.mode == "SHADOW" and parse_utc(at) > parse_utc(request["funding_valid_until"]):
            raise PaperPlaneError("EXECUTION_OBSERVATION_STALE_OR_FUTURE")
        request["result_at"] = render_utc(parse_utc(at)+timedelta(seconds=profile["model"]["latency_seconds"]))
        request["request_sha256"] = sha256_of({k:v for k,v in request.items() if k!="request_sha256"})
        prior = store._conn.execute("SELECT COUNT(*) FROM execution_events WHERE event_type='MODELED_ATTEMPT_STARTED' AND position_id=?", (position["position_id"],)).fetchone()[0]
        key = "ORDINARY-" + side + "-" + str(prior + 1)
        with store.immediate_write():
            if side == "ENTRY":
                check = enforce_operating_envelope(store, mode=self.mode, admitted_notional_usd=position["admitted_entry_notional_usd_dec"], exclude_position_id=position["position_id"])
                if check.get("decision") != "ALLOW":
                    store.cancel_entry_intent(position["position_id"], reason_code="OPERATING_SAFETY_VETO")
                    return False
            # Runner normally opens its own connection; use same connection for
            # admission/control recheck and durable claim by passing a temporary
            # store factory only for this synchronous atomic call.
            origin = bound._origin(store, position)
            decision_at = origin["decision"]["decision_at"]
            if side == "EXIT" and position.get("exit_decision_id"):
                decision_at = bound._exit_origin(store, position)["decision"]["decision_at"]
            at = render_utc(self.clock())
            request["result_at"] = render_utc(parse_utc(at)+timedelta(seconds=profile["model"]["latency_seconds"]))
            request["entry_send_valid_until"] = render_utc(parse_utc(decision_at)+timedelta(seconds=bound.strategy["signal_input"]["max_age_seconds"])) if side=="ENTRY" else None
            if parse_utc(at)>parse_utc(request["observation_valid_until"]):
                request["unit_price_usd"]=None
            from solana_alpha_lab.factory.paper_plane import begin_modeled_attempt
            attempt = begin_modeled_attempt(store, position_id=position["position_id"], side=side, mode=self.mode,
                attempt_key=key, decision_at=decision_at, max_age_seconds=bound.strategy["signal_input"]["max_age_seconds"], as_of=at)
            if not attempt.get("send_permitted"):
                return False
            if self.mode=="SHADOW" and parse_utc(at)>parse_utc(request["funding_valid_until"]):
                raise PaperPlaneError("EXECUTION_OBSERVATION_STALE_OR_FUTURE")
            request["request_sha256"]=sha256_of({k:v for k,v in request.items() if k!="request_sha256"})
            store.append_execution_event(event_type="ADAPTER_REQUEST_BOUND", event_id="REQUEST-" + attempt["attempt_id"],
                bot_instance_id=position["bot_instance_id"], position_id=position["position_id"], payload=request, created_at=at)
            attempt = store.get_execution_event(attempt["attempt_id"])["payload"]
            # Independent effect receipts retain the accepted origin even when
            # the restored DB cut precedes the reservation or activation.
            closure = {"position":store.get_position(position["position_id"]),
                "origin":origin,
                "binding":store.get_execution_event("OPERATING-"+position["activation_epoch_id"]),
                "activation":store.get_execution_event(position["activation_epoch_id"]),
                "profile":store.get_execution_event("PROFILE-"+position["activation_epoch_id"])}
            if side=="EXIT" and position.get("exit_decision_id"):
                closure["exit_events"]=[store.get_execution_event("SRC-"+position["exit_decision_id"]),
                    store.get_execution_event("EXITBIND-"+position["exit_decision_id"])]
            closure["closure_sha256"] = sha256_of(closure)
            request["recovery_closure"] = closure
            request["request_sha256"] = sha256_of({k:v for k,v in request.items() if k!="request_sha256"})
            # Replace before commit: no effect has consumed the initial request.
            store._conn.execute("UPDATE execution_events SET payload_json=? WHERE event_id=?",
                (json.dumps(request,sort_keys=True),"REQUEST-"+attempt["attempt_id"]))
        self.fault("AFTER_ATTEMPT_COMMIT")
        if self.mode == "PAPER":
            result = PaperModelAdapter(profile["model"]).reconcile(attempt, request, as_of=at)
            if result is not None:
                bound.result(result)
        else:
            cfg = profile["quote"]
            adapter = self.quote_adapter or JupiterQuoteAdapter(timeout_seconds=cfg["timeout_seconds"], max_response_bytes=cfg["max_response_bytes"])
            if adapter.transport is None:
                grant = adapter.grant or {}
                grant_id = grant.get("grant_sha256")
                if not grant_id:
                    raise PaperPlaneError("QUOTE_EXTERNAL_AUTHORITY_REQUIRED")
                with store.immediate_write():
                    # A committed claim consumes quota even if the process dies
                    # before HTTP. Restart never resets the bounded call grant.
                    used = store._conn.execute("SELECT COUNT(*) FROM execution_events WHERE event_type='QUOTE_CALL_CLAIMED' AND json_extract(payload_json,'$.grant_sha256')=?", (grant_id,)).fetchone()[0]
                    if type(grant.get("calls_max")) is not int or used >= grant["calls_max"]:
                        raise PaperPlaneError("QUOTE_CALL_CAP_EXHAUSTED")
                    store.append_execution_event(event_type="QUOTE_CALL_CLAIMED", event_id="QUOTE-CALL-" + attempt["attempt_id"],
                        bot_instance_id=position["bot_instance_id"], position_id=position["position_id"],
                        payload={"grant_sha256": grant_id, "attempt_id": attempt["attempt_id"]}, created_at=at)
            adapter.result_clock = lambda:render_utc(self.clock())
            result, proof = adapter.dispatch(attempt, request, as_of=at)
            self.fault("AFTER_ADAPTER_EFFECT")
            captured = {"result": result, "provenance": proof}
            captured["capture_sha256"] = sha256_of(captured)
            with store.immediate_write():
                store.append_execution_event(event_type="ADAPTER_RESULT_CAPTURED", event_id="CAPTURE-" + attempt["attempt_id"],
                    bot_instance_id=position["bot_instance_id"], position_id=position["position_id"], payload=captured, created_at=at)
            self.fault("AFTER_RESULT_CAPTURE")
            bound.result(result)
        self.fault("AFTER_RESULT_COMMIT")
        return True

    def _recover(self, store, at):
        pending = store._conn.execute("SELECT e.event_id FROM execution_events e JOIN bot_instances b ON b.bot_instance_id=e.bot_instance_id WHERE e.event_type='MODELED_ATTEMPT_STARTED' AND b.mode=? AND NOT EXISTS(SELECT 1 FROM execution_events f WHERE f.event_id='FINAL-'||e.event_id)", (self.mode,)).fetchall()
        healthy = True
        for row in pending:
            try:
                healthy = self._recover_attempt(store, row[0], at) and healthy
            except (PaperPlaneError, KeyError, ValueError, OSError, sqlite3.Error) as error:
                reason = str(error) if isinstance(error, PaperPlaneError) else "ATTEMPT_RECOVERY_INPUT_UNAVAILABLE"
                self._incident(store, row[0], reason, at)
                healthy = False
        return healthy

    def _recover_attempt(self, store, attempt_id, at):
        row = (attempt_id,)
        # One damaged obligation cannot starve unrelated proven old exits.
        event = store.get_execution_event(row[0])
        attempt = event["payload"]
        position = store.get_position(event["position_id"])
        bound = self.runner.for_epoch(position["activation_epoch_id"])
        bound._origin(store, position)
        if attempt["side"] == "EXIT" and position.get("exit_decision_id"):
            bound._exit_origin(store, position)
        captured = store.get_execution_event("CAPTURE-" + row[0])
        inbox = exact_child(self.runner.data_root, "result-inbox", exists=False)
        callback = exact_child(inbox, row[0] + ".json", exists=False)
        if callback.is_file():
            result = json.loads(callback.read_text(encoding="utf-8"))
        elif captured:
            body = captured["payload"]
            if sha256_of({key: value for key, value in body.items() if key != "capture_sha256"}) != body.get("capture_sha256"):
                raise PaperPlaneError("ADAPTER_CAPTURE_INTEGRITY_CONFLICT")
            result = captured["payload"]["result"]
        elif self.mode == "PAPER":
            request = store.get_execution_event("REQUEST-" + row[0])
            if request is None:
                raise PaperPlaneError("ADAPTER_REQUEST_BINDING_MISSING")
            result = PaperModelAdapter(self._profile(store, position["activation_epoch_id"])["model"]).reconcile(attempt, request["payload"], as_of=at)
        else:
            # A callback ledger can supply the original uncertain identity.
            # No HTTP resend. The same inbox API is available after restore.
            result = None
        if result is not None:
            bound.result(result)
        if store.get_execution_event("FINAL-" + row[0]) is None:
            self._incident(store, row[0], "ATTEMPT_RECONCILIATION_REQUIRED", at)
            return False
        else:
            store._conn.execute("UPDATE ordinary_incidents SET active=0,last_changed_at=? WHERE incident_key=? AND active=1", (at, row[0]))
            return True

    def tick(self):
        with single_writer(self.runner):
            return self._tick_owned()

    def _tick_owned(self):
        at = render_utc(self.clock())
        store = self.runner._store()
        counts = {"discovered": 0, "decisions": 0, "attempts": 0, "exits": 0}
        try:
            state = store._conn.execute("SELECT * FROM ordinary_state WHERE mode=?", (self.mode,)).fetchone()
            if state is None:
                raise PaperPlaneError("ORDINARY_ACTIVATION_REQUIRED")
            if state["last_tick_at"] and parse_utc(at) < parse_utc(state["last_tick_at"]):
                raise PaperPlaneError("OPERATING_CLOCK_REGRESSION")
            recovery_healthy = self._recover(store, at)
            rows = store.obligation_positions(self.mode)
            # Entire outstanding inventory, independent of entry-active pointer.
            for position in rows:
                at = render_utc(self.clock())
                bot = store.get_bot(position["bot_instance_id"])
                if bot is None or bot.get("mode") not in {"PAPER","SHADOW"}:
                    self._incident(store,position["position_id"],"OPERATING_BOT_IDENTITY_UNKNOWN",at)
                    recovery_healthy=False
                    continue
                if bot["mode"] != self.mode:
                    continue
                if position["state"] in {"OPEN", "PARTIAL"}:
                    try:
                        bound = self.runner.for_epoch(position["activation_epoch_id"])
                        bound.exit(position_id=position["position_id"], source_relative="unused", as_of=at, ordinary_operating=True)
                        counts["exits"] += 1
                    except (PaperPlaneError,KeyError,ValueError,TypeError,OSError,sqlite3.Error) as error:
                        if str(error) != "EPISODE_EXIT_NOT_DUE":
                            self._incident(store, position["position_id"], str(error) if isinstance(error,PaperPlaneError) else "OPERATING_BINDING_INTEGRITY_CONFLICT", at)
                            recovery_healthy = False
                    position = store.get_position(position["position_id"])
                if position["state"] in {"EXIT_REQUIRED", "UNRESOLVED"}:
                    if position["state"] == "UNRESOLVED":
                        # Recovery above owns the already claimed identity.
                        # An uncertain attempt is never a second send slot.
                        pending_attempt = store._conn.execute("SELECT 1 FROM execution_events e WHERE e.position_id=? AND e.event_type='MODELED_ATTEMPT_STARTED' AND NOT EXISTS(SELECT 1 FROM execution_events f WHERE f.event_id='FINAL-'||e.event_id) LIMIT 1", (position["position_id"],)).fetchone()
                        if pending_attempt is not None:
                            recovery_healthy = False
                            continue
                    try:
                        bound = self.runner.for_epoch(position["activation_epoch_id"])
                        counts["attempts"] += int(self._dispatch(store, bound, position, self._profile(store, position["activation_epoch_id"]), "EXIT", at))
                    except (PaperPlaneError,KeyError,ValueError,TypeError,OSError,sqlite3.Error) as error:
                        self._incident(store, position["position_id"], str(error) if isinstance(error,PaperPlaneError) else "OPERATING_BINDING_INTEGRITY_CONFLICT", at)
                        recovery_healthy = False
            for bot in store.bots():
                if bot["mode"] == self.mode and bot["status"] == "DRAINING":
                    maybe_finish_drain(store, bot["bot_instance_id"])
            # Current entry configuration is not the owner of older exits.
            # Consume it only after independently bound recovery/exit work.
            try:
                profile=self._profile(store,state["epoch_id"])
                bound=self.runner.for_epoch(state["epoch_id"])
                store._conn.execute("UPDATE ordinary_incidents SET active=0,last_changed_at=? WHERE incident_key=? AND active=1",(at,"PROFILE-"+self.mode))
            except (PaperPlaneError,KeyError,ValueError,TypeError):
                at=render_utc(self.clock())
                self._incident(store,"PROFILE-"+self.mode,"OPERATING_PROFILE_UNAVAILABLE_OR_CORRUPT",at)
                with store.immediate_write():
                    store._conn.execute("UPDATE ordinary_state SET last_tick_at=?,source_status=?,source_latest_at=NULL WHERE mode=?",(at,"ACTIVE_PROFILE_UNAVAILABLE",self.mode))
                    if counts["attempts"] or counts["exits"]:
                        store._conn.execute("UPDATE ordinary_state SET last_progress_at=? WHERE mode=?",(at,self.mode))
                return {"status":"TICK_COMPLETE","mode":self.mode,"epoch_id":state["epoch_id"],"as_of":at,
                    "source_status":"ACTIVE_PROFILE_UNAVAILABLE","reconciliation_healthy":recovery_healthy,"entries_enabled":False,**counts}
            source_status, latest = "AVAILABLE", None
            at = render_utc(self.clock())
            source = None
            try:
                source = self._source(profile)
                with source.read_snapshot():
                    cfg = profile["source"]
                    # Stable source-native rowid paging plus cyclic anti-join.
                    # Queue owns delayed due slots; cursor never owns effects.
                    records = source._conn.execute("SELECT rowid,* FROM episode_admissions WHERE rowid>? AND schedule_sha256=? AND activation_id=? ORDER BY rowid LIMIT ?", (state["discovery_rowid"], cfg["schedule_sha256"], cfg["activation_id"], profile["batch_size"])).fetchall()
                    append_page = bool(records)
                    if not records:
                        # New append work always wins over cyclic retention
                        # checking; a large known history cannot starve it.
                        records = source._conn.execute("SELECT rowid,* FROM episode_admissions WHERE rowid>? AND schedule_sha256=? AND activation_id=? ORDER BY rowid LIMIT ?", (state["rescan_rowid"], cfg["schedule_sha256"], cfg["activation_id"], profile["batch_size"])).fetchall()
                    latest = self._source_latest(source, profile)
                    if latest is None or not 0 <= (parse_utc(at) - parse_utc(latest)).total_seconds() <= profile["source_max_age_seconds"]:
                        source_status = "SOURCE_STALE"
                    with store.immediate_write():
                        for raw in records:
                            record = source._decode_episode_admission(raw)
                            admission = record["record"]
                            digest = admission_content_sha256(admission)
                            if digest != record["content_sha256"]:
                                raise PaperPlaneError("EPISODE_ADMISSION_HASH_CONFLICT")
                            schedule = source.get_registered_schedule(admission["schedule_sha256"])
                            cutoff = resolve_point(schedule_binding(schedule["document"]), parse_utc(admission["t0"]), bound.recipe["decision_point"]).availability_deadline
                            existing = store._conn.execute("SELECT source_sha256 FROM ordinary_work WHERE epoch_id=? AND episode_id=?", (state["epoch_id"], admission["episode_id"])).fetchone()
                            if existing and existing[0] != digest:
                                raise PaperPlaneError("ORDINARY_SOURCE_IDENTITY_CONFLICT")
                            store._conn.execute("INSERT OR IGNORE INTO ordinary_work(epoch_id,episode_id,source_sha256,cutoff,status) VALUES(?,?,?,?, 'PENDING')", (state["epoch_id"], admission["episode_id"], digest, render_utc(cutoff)))
                            counts["discovered"] += int(existing is None)
                        if append_page:
                            store._conn.execute("UPDATE ordinary_state SET discovery_rowid=? WHERE mode=?", (records[-1]["rowid"], self.mode))
                        else:
                            cursor = records[-1]["rowid"] if records else 0
                            store._conn.execute("UPDATE ordinary_state SET rescan_rowid=? WHERE mode=?", (cursor, self.mode))
            except (OSError, sqlite3.Error):
                source_status = "SOURCE_UNAVAILABLE"
            finally:
                if source is not None:
                    source.close()
            if source_status != "AVAILABLE":
                self._incident(store, "SOURCE-" + self.mode, source_status, at)
            else:
                store._conn.execute("UPDATE ordinary_incidents SET active=0,last_changed_at=? WHERE incident_key=? AND active=1", (at, "SOURCE-" + self.mode))
            bot = next(bot for bot in store.bots() if bot.get("activation_epoch_id") == state["epoch_id"] and bot["mode"] == self.mode)
            allows_entries = source_status == "AVAILABLE" and recovery_healthy and bot["status"] == "RUNNING" and not bot["entries_paused"] and not state["restore_guard"]
            if allows_entries:
                from solana_alpha_lab.factory.trading_runtime_policy import read_operating_envelope, show_policy, obligation_summary
                revision = sha256_of({"policy": show_policy(store, self.mode).get("policy_sha256"),
                                      "envelope": read_operating_envelope(store, self.mode).get("envelope_sha256"),
                                      "obligations": obligation_summary(store, mode=self.mode)})
                store._conn.execute("UPDATE ordinary_work SET status='PENDING' WHERE epoch_id=? AND status='DENIED' AND evaluation_revision!=? AND cutoff>=?", (state["epoch_id"], revision,
                    render_utc(parse_utc(at) - timedelta(seconds=bound.strategy["signal_input"]["max_age_seconds"]))))
                pending = store._conn.execute("SELECT * FROM ordinary_work WHERE epoch_id=? AND status='PENDING' AND cutoff<=? ORDER BY cutoff,episode_id LIMIT ?", (state["epoch_id"], at, profile["batch_size"])).fetchall()
                for work in pending:
                    at = render_utc(self.clock())
                    packet = bound.episode(source_relative="unused", source_path=exact_child(Path(profile["source"]["root"]), profile["source"]["file"]),
                        episode_id=work["episode_id"], epoch_id=state["epoch_id"], mode=self.mode, as_of=at, ordinary_operating=True)
                    self.fault("AFTER_DECISION_COMMIT")
                    admission = packet["admission"]
                    status = admission.get("outcome") or packet["decision"]["action"]
                    if (parse_utc(at) - parse_utc(work["cutoff"])).total_seconds() > bound.strategy["signal_input"]["max_age_seconds"]:
                        status = "SKIPPED_STALE"
                    with store.immediate_write():
                        store._conn.execute("UPDATE ordinary_work SET status=?,position_id=?,evaluation_revision=? WHERE epoch_id=? AND episode_id=?", (status, admission.get("position_id"), revision, state["epoch_id"], work["episode_id"]))
                        store._conn.execute("UPDATE ordinary_state SET last_progress_at=?,last_work_id=? WHERE mode=?", (at, packet["decision"]["signal_decision_id"], self.mode))
                    counts["decisions"] += 1
            # Admission and effect may be separated by pause/switch/crash.
            for position in store.obligation_positions(self.mode):
                if position["state"] not in PRE_ATTEMPT_STATES or position["activation_epoch_id"] != state["epoch_id"]:
                    continue
                if not allows_entries:
                    if bot["entries_paused"] or bot["status"] != "RUNNING":
                        store.cancel_entry_intent(position["position_id"], reason_code="ENTRIES_PAUSED" if bot["entries_paused"] else "BOT_DRAINING" if bot["status"] == "DRAINING" else "BOT_STOPPED")
                    continue
                counts["attempts"] += int(self._dispatch(store, bound, position, profile, "ENTRY", at))
            with store.immediate_write():
                at = render_utc(self.clock())
                store._conn.execute("UPDATE ordinary_state SET last_tick_at=?,source_status=?,source_latest_at=? WHERE mode=?", (at, source_status, latest, self.mode))
                if counts["attempts"] or counts["exits"]:
                    store._conn.execute("UPDATE ordinary_state SET last_progress_at=? WHERE mode=?", (at, self.mode))
            return {"status": "TICK_COMPLETE", "mode": self.mode, "epoch_id": state["epoch_id"], "as_of": at,
                    "source_status": source_status, "reconciliation_healthy": recovery_healthy, **counts}
        finally:
            store.close()

    def status(self):
        """Independent observer: no schema creation, source mutation or network."""
        from solana_alpha_lab.factory.trading_runtime_policy import obligation_summary, read_operating_envelope
        at = render_utc(self.clock())
        store = self.runner._store(readonly=True)
        try:
            with store.read_snapshot():
                state = store._conn.execute("SELECT * FROM ordinary_state WHERE mode=?", (self.mode,)).fetchone()
                if state is None:
                    raise PaperPlaneError("ORDINARY_ACTIVATION_REQUIRED")
                try:
                    profile = self._profile(store, state["epoch_id"])
                except (PaperPlaneError,KeyError,ValueError,TypeError):
                    profile = None
                inventory = obligation_summary(store, mode=self.mode)
                unresolved = store._conn.execute("SELECT COUNT(*) FROM execution_events e JOIN bot_instances b ON b.bot_instance_id=e.bot_instance_id WHERE b.mode=? AND e.event_type='MODELED_ATTEMPT_STARTED' AND NOT EXISTS(SELECT 1 FROM execution_events f WHERE f.event_id='FINAL-'||e.event_id)", (self.mode,)).fetchone()[0]
                pending = store._conn.execute("SELECT COUNT(*),MIN(cutoff) FROM ordinary_work WHERE epoch_id=? AND status='PENDING' AND cutoff<=?", (state["epoch_id"], at)).fetchone()
                tick = state["last_tick_at"]
                age = None if tick is None else (parse_utc(at) - parse_utc(tick)).total_seconds()
                expected = pending[0] > 0 or unresolved > 0
                alive = None if profile is None else tick is not None and 0 <= age <= profile["progress_max_age_seconds"]
                progress_age = None if state["last_progress_at"] is None else (parse_utc(at) - parse_utc(state["last_progress_at"])).total_seconds()
                moving = None if profile is None else not expected or progress_age is not None and 0 <= progress_age <= profile["progress_max_age_seconds"]
                bots = [bot for bot in store.bots() if bot["mode"] == self.mode]
                integrity = []
                if profile is None:
                    integrity.append({"epoch_id":state["epoch_id"],"status":"OPERATING_PROFILE_UNAVAILABLE_OR_CORRUPT"})
                for bot in bots:
                    try:
                        self.runner.for_epoch(bot["activation_epoch_id"])
                    except (PaperPlaneError, KeyError, ValueError, TypeError):
                        integrity.append({"epoch_id": bot["activation_epoch_id"], "status": "INTEGRITY_CONFLICT"})
                for position in store.obligation_positions(self.mode):
                    try:
                        bound = self.runner.for_epoch(position["activation_epoch_id"])
                        bound._origin(store, position)
                        if position.get("exit_decision_id"):
                            bound._exit_origin(store, position)
                            expected = True
                        else:
                            origin = bound._origin(store, position)
                            due = resolve_point(origin["provenance"]["schedule_binding"],
                                parse_utc(origin["provenance"]["origin_admission"]["t0"]),
                                bound.recipe["target"]["exit_point"]).availability_deadline
                            expected = expected or parse_utc(at) >= due
                    except (PaperPlaneError, KeyError, ValueError, TypeError):
                        integrity.append({"position_id": position["position_id"], "epoch_id": position["activation_epoch_id"],
                            "status": "ORIGIN_INTEGRITY_CONFLICT", "inventory_status": "UNKNOWN"})
                moving = None if profile is None else not expected or progress_age is not None and 0 <= progress_age <= profile["progress_max_age_seconds"]
                incidents = [dict(row) for row in store._conn.execute("SELECT * FROM ordinary_incidents ORDER BY incident_key")]
                for incident in incidents:
                    if incident["active"] and any(tag in incident["reason"] for tag in ("INTEGRITY", "CONFLICT", "CORRUPT")):
                        integrity.append({"incident_key":incident["incident_key"],"status":incident["reason"]})
                if integrity and inventory["position_count"]:
                    inventory = {**inventory, "inventory_status": "UNKNOWN", "outstanding_cost_basis_usd": None}
                source_available, observed_source_latest = False, None
                source = None
                try:
                    if profile is not None:
                        source = self._source(profile)
                        with source.read_snapshot():
                            source_available = source.get_registered_schedule(profile["source"]["schedule_sha256"]) is not None
                            observed_source_latest = self._source_latest(source, profile)
                except (OSError, sqlite3.Error, KeyError, ValueError):
                    source_available = False
                finally:
                    if source is not None:
                        source.close()
                source_age = None if observed_source_latest is None else (parse_utc(at) - parse_utc(observed_source_latest)).total_seconds()
                fresh = profile is not None and source_available and source_age is not None and 0 <= source_age <= profile["source_max_age_seconds"]
                input_reason = "OPERATING_PROFILE_UNAVAILABLE_OR_CORRUPT" if profile is None else "SOURCE_UNAVAILABLE" if not source_available else "SOURCE_CLOCK_FROM_FUTURE" if source_age is not None and source_age < 0 else "SOURCE_STALE" if not fresh else "SOURCE_FRESH"
                exit_blocked = any(row["active"] and not row["incident_key"].startswith("SOURCE-") for row in incidents)
                healthy = not integrity and not exit_blocked and alive and moving and fresh and not unresolved and inventory["inventory_status"] == "KNOWN" and not state["restore_guard"]
                restored_cut = store._conn.execute("SELECT event_id FROM execution_events WHERE event_type='RESTORE_EXTERNAL_CUT_RECONCILED' AND json_extract(payload_json,'$.mode')=? ORDER BY rowid DESC LIMIT 1", (self.mode,)).fetchone()
                restore_next = "ack-restore --mode "+self.mode+" --input complete-external-cut.json --inventory-sha256 "+sha256_of(inventory)+" --as-of "+at if restored_cut and not unresolved and not integrity and inventory["inventory_status"]=="KNOWN" else "reconcile --mode "+self.mode+" --input complete-external-cut.json"
                from solana_alpha_lab.factory.paper_shadow_operations import position_pnl_view, _modeled_attempt_costs
                recent = [dict(row) for row in store._conn.execute("SELECT p.* FROM positions p JOIN bot_instances b USING(bot_instance_id) WHERE b.mode=? ORDER BY p.rowid DESC LIMIT 100", (self.mode,))]
                by_position = {}
                for event in store.filtered_execution_events(position_ids=[position["position_id"] for position in recent]):
                    by_position.setdefault(event["position_id"], []).append(event)
                class EventWindow:
                    def __init__(self, events):
                        self.events = events
                    def execution_events(self):
                        return self.events
                economics = [{"position_id": position["position_id"], "activation_epoch_id": position["activation_epoch_id"],
                    "strategy_sha256": position["strategy_spec_sha256"], "state": position["state"],
                    **position_pnl_view(position), "additional_costs": _modeled_attempt_costs(
                        EventWindow(by_position.get(position["position_id"], [])), {position["bot_instance_id"]})} for position in recent]
                return {"status": "READY" if healthy else "ACTION_REQUIRED", "mode": self.mode,
                    "as_of": at, "store": "paper_plane.sqlite", "activation_epoch_id": state["epoch_id"],
                    "generation":state["generation"],"inventory_sha256":sha256_of(inventory),
                    "profile_sha256": None if profile is None else sha256_of(profile), "process_alive": alive,
                    "input_fresh": fresh, "input_reason":input_reason,"source_available": source_available, "source_latest_at": observed_source_latest, "last_tick_at":tick,"progress_moving": moving,
                    "integrity_verified": not integrity, "exit_reconciliation_healthy": not exit_blocked and unresolved == 0 and inventory["inventory_status"] == "KNOWN",
                    "restore_guard": bool(state["restore_guard"]), "inventory": inventory,
                    "envelope": read_operating_envelope(store, self.mode), "instances": bots,
                    "pending_attempts": unresolved, "due_work": pending[0], "earliest_overdue": pending[1],
                    "last_completed_work": state["last_work_id"], "incidents": incidents, "integrity_gaps": integrity,
                    "economics": economics, "economics_coverage": "RECENT_100_POSITION_ROWS_PER_MODE",
                    "complete_execution_readback": "trading_continuity.py readback", "netreturn_status": "NOT_ESTABLISHED", "owner_fcf_status": "NOT_AVAILABLE",
                    "scientific_monitoring_thresholds": "NOT_CONFIGURED",
                    "next_safe_action": "RECONCILE_SAME_ATTEMPT_OR_RESTORE_EXACT_BINDING" if unresolved or integrity or state["restore_guard"] else "CHECK_PROCESS_SOURCE_AND_PROFILE" if not healthy else "NONE",
                    "next_safe_command": restore_next if state["restore_guard"] else "readback --mode "+self.mode if unresolved or integrity or exit_blocked else "run --mode "+self.mode+" --ticks 1" if not fresh else "run --mode "+self.mode if not alive else "status --mode "+self.mode+" --format human",
                    "live_authority": False, "financial_authority": False}
        finally:
            store.close()

    def backup(self, *, destination_relative):
        target = exact_child(self.runner.data_root, destination_relative, exists=False)
        if target.exists():
            raise PaperPlaneError("BACKUP_DESTINATION_MUST_BE_NEW")
        target.parent.mkdir(parents=True, exist_ok=True)
        store = self.runner._store(readonly=True)
        try:
            replica = sqlite3.connect(target)
            try:
                store._conn.backup(replica)
                if replica.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise PaperPlaneError("BACKUP_INTEGRITY_FAILED")
            finally:
                replica.close()
        finally:
            store.close()
        import hashlib
        manifest = {"schema_version": "1.0", "database_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                    "mode": self.mode, "schema": "smial.operating-native-backup",
                    "restore_policy": "RECONCILIATION_BEFORE_NEW_EFFECTS", "frozen_bindings_in_database": True}
        target.with_suffix(target.suffix + ".json").write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
        return manifest

    def export_recovery_cut(self, *, backup_path, effects, external_cut_id, as_of):
        """Export coherent local evidence; external completeness remains explicit."""
        import hashlib
        parse_utc(as_of)
        if not isinstance(effects,list) or not isinstance(external_cut_id,str) or not external_cut_id:
            raise PaperPlaneError("RESTORE_COMPLETE_EXTERNAL_CUT_REQUIRED")
        effects_ids={row["attempt"]["attempt_id"] for row in effects}
        effects_by_id={row["attempt"]["attempt_id"]:row for row in effects}
        if len(effects_by_id)!=len(effects):
            raise PaperPlaneError("RESTORE_EXTERNAL_CUT_CONTENT_INVALID")
        backup=sqlite3.connect(backup_path.resolve(strict=True).as_uri()+"?mode=ro",uri=True)
        try:
            backup.execute("PRAGMA query_only=ON")
            backup_results={row[0]:json.loads(row[1]) for row in backup.execute("SELECT event_id,payload_json FROM execution_events WHERE event_type='MODELED_RESULT_ACCEPTED'")}
        finally:
            backup.close()
        store=self.runner._store(readonly=True)
        try:
            with store.read_snapshot():
                state=store._conn.execute("SELECT * FROM ordinary_state WHERE mode=?",(self.mode,)).fetchone()
                bots=[bot for bot in store.bots() if bot["mode"]==self.mode]
                bot_ids={bot["bot_instance_id"] for bot in bots}
                latest_results={}
                result_observations=[]
                for event in store.filtered_execution_events(event_type="MODELED_RESULT_ACCEPTED"):
                    if event["bot_instance_id"] in bot_ids:
                        latest_results[event["payload"]["result"]["attempt_id"]]=event
                        if backup_results.get(event["event_id"])!=event["payload"]:
                            result_observations.append(event)
                for attempt_id,event in latest_results.items():
                    if backup_results.get(event["event_id"])==event["payload"]:
                        continue
                    receipt=effects_by_id.get(attempt_id)
                    if (receipt is None or receipt["result"]!=event["payload"]["result"]
                        or receipt["attempt"]!=store.get_execution_event(attempt_id)["payload"]
                        or receipt["request"]!=store.get_execution_event("REQUEST-"+attempt_id)["payload"]):
                        # Independently asserted completeness cannot contradict
                        # accepted native results already visible to this reader.
                        raise PaperPlaneError("RECOVERY_KNOWN_RESULT_OMITTED_OR_CONFLICTING")
                return {"schema":"smial.operating-external-recovery-cut","schema_version":"1.0","mode":self.mode,
                    "backup_sha256":hashlib.sha256(backup_path.read_bytes()).hexdigest(),"external_cut_id":external_cut_id,
                    "as_of":as_of,"completeness":"COMPLETE_AFTER_BACKUP","effects":effects,
                    "result_observations":result_observations,
                    "current_entry":{"epoch_id":state["epoch_id"],"generation":state["generation"]},
                    "operating_bindings":[{"activation":store.get_execution_event(bot["activation_epoch_id"]),
                        "binding":store.get_execution_event("OPERATING-"+bot["activation_epoch_id"]),
                        "profile":store.get_execution_event("PROFILE-"+bot["activation_epoch_id"])} for bot in bots],
                    "quote_claims":[event for event in store.filtered_execution_events(event_type="QUOTE_CALL_CLAIMED") if event["bot_instance_id"] in bot_ids],
                    "pending_attempts":[{"attempt":event["payload"],"request":store.get_execution_event("REQUEST-"+event["event_id"])["payload"]}
                        for event in store.filtered_execution_events(event_type="MODELED_ATTEMPT_STARTED")
                        if event["bot_instance_id"] in bot_ids and store.get_execution_event("FINAL-"+event["event_id"]) is None and event["event_id"] not in effects_ids],
                    "controls":[{"bot_instance_id":bot["bot_instance_id"],"status":bot["status"],"entries_paused":bool(bot["entries_paused"])} for bot in bots]}
        finally:
            store.close()

    def reconcile_restored_effect(self, receipt, *, pending_only=False, result_observations=()):
        """Import a retained original effect receipt, never authorize a send.

        This handles a snapshot before the original committed attempt. The
        independent ledger is an explicit recovery input, not a new outcome.
        """
        from solana_alpha_lab.factory.strategy_runtime import canonical_spec_sha256
        attempt, request, result = receipt["attempt"], receipt["request"], receipt["result"]
        if sha256_of({k: v for k, v in receipt.items() if k != "receipt_sha256"}) != receipt.get("receipt_sha256"):
            raise PaperPlaneError("RECOVERY_RECEIPT_INTEGRITY_CONFLICT")
        identity = {key: attempt[key] for key in ("position_id", "side", "mode", "attempt_key")}
        if (attempt["attempt_id"] != "ATTEMPT-" + canonical_spec_sha256(identity).upper() or attempt["mode"] != self.mode
            or (result is None and not pending_only) or (result is not None and result["attempt_id"] != attempt["attempt_id"])):
            raise PaperPlaneError("RECOVERY_ATTEMPT_IDENTITY_CONFLICT")
        if sha256_of({k: v for k, v in request.items() if k != "request_sha256"}) != request.get("request_sha256"):
            raise PaperPlaneError("ADAPTER_REQUEST_INTEGRITY_CONFLICT")
        store = self.runner._store()
        try:
            with store.immediate_write():
                position = store.get_position(attempt["position_id"])
                if position is None:
                    from solana_alpha_lab.factory.strategy_runtime import validate_signal_decision,position_id_for_signal_decision
                    from solana_alpha_lab.factory.trading_adapters import decimal_value
                    closure=request.get("recovery_closure") or {}
                    if closure.get("closure_sha256") != sha256_of({k:v for k,v in closure.items() if k!="closure_sha256"}):
                        raise PaperPlaneError("RECOVERY_ORIGIN_CLOSURE_REQUIRED")
                    if attempt["side"] != "ENTRY":
                        raise PaperPlaneError("RECOVERY_ENTRY_RECEIPT_REQUIRED_FIRST")
                    retained=closure["position"]
                    if retained["state"]!="ATTEMPTING" or retained["qty_dec"] is not None or retained["entry_price_dec"] is not None:
                        raise PaperPlaneError("RECOVERY_RESERVATION_STATE_CONFLICT")
                    self.runner._set_frozen(closure["binding"])
                    bound=self.runner
                    epoch=request["activation_epoch_id"]
                    if closure["activation"]["payload"]!=closure["binding"]["payload"]["activation"]:
                        raise PaperPlaneError("RECOVERY_ACTIVATION_CONFLICT")
                    for event in (closure["activation"],closure["binding"],closure["profile"]):
                        existing=store.get_execution_event(event["event_id"])
                        if existing and (existing["payload"]!=event["payload"] or existing["event_type"]!=event["event_type"]):
                            raise PaperPlaneError("RECOVERY_BINDING_CONTENT_CONFLICT")
                        if not existing:
                            store.append_execution_event(event_type=event["event_type"],event_id=event["event_id"],
                                bot_instance_id=event["bot_instance_id"],position_id=event["position_id"],payload=event["payload"],created_at=event["created_at"])
                    self._profile(store,epoch)
                    bot=store.start_bot(bound.strategy,mode=self.mode,activation_epoch_id=epoch)
                    store._conn.execute("UPDATE bot_instances SET entries_paused=1 WHERE bot_instance_id=?",(bot["bot_instance_id"],))
                    decision=validate_signal_decision(self.runner.root,closure["origin"]["decision"])
                    if (decision["action"]!="ENTER" or position_id_for_signal_decision(decision["signal_decision_id"])!=attempt["position_id"]
                        or retained["position_id"]!=attempt["position_id"] or retained["bot_instance_id"]!=bot["bot_instance_id"]
                        or retained["admitted_entry_notional_usd_dec"]!=request["admitted_notional_usd"]
                        or retained["ordinary_operating"]!=1
                        or decimal_value(request["admitted_notional_usd"])>decimal_value(bound.strategy["notional_policy"]["notional_usd"])):
                        raise PaperPlaneError("RECOVERY_RESERVATION_IDENTITY_CONFLICT")
                    store.append_execution_event(event_type="SOURCE_DECISION_PRODUCED",event_id="SRC-"+decision["signal_decision_id"],
                        bot_instance_id=None,position_id=None,payload=closure["origin"],created_at=decision["decision_at"])
                    store.open_position_from_signal(bot_instance_id=bot["bot_instance_id"],signal_decision=decision,
                        signal_decision_sha256=canonical_spec_sha256(decision),strategy_spec_sha256=bound.strategy["spec_sha256"])
                    if type(retained["admitted_fee_bps"]) is not int or not 0<=retained["admitted_fee_bps"]<=10000:
                        raise PaperPlaneError("RECOVERY_ADMISSION_FEE_CONFLICT")
                    store._freeze_admission_binding_locked(attempt["position_id"],
                        admitted_entry_notional_usd_dec=retained["admitted_entry_notional_usd_dec"],
                        strategy_requested_notional_usd_dec=retained["strategy_requested_notional_usd_dec"],
                        runtime_policy_mode=retained["runtime_policy_mode"],runtime_policy_revision=retained["runtime_policy_revision"],
                        runtime_policy_sha256=retained["runtime_policy_sha256"],admitted_fee_bps=retained["admitted_fee_bps"])
                    store._conn.execute("UPDATE positions SET ordinary_operating=1 WHERE position_id=?",(attempt["position_id"],))
                    store.append_execution_event(event_type="RECOVERY_RESERVATION_RETAINED",event_id="RECOVERY-RESERVATION-"+attempt["position_id"],
                        bot_instance_id=bot["bot_instance_id"],position_id=attempt["position_id"],
                        payload={"closure_sha256":closure["closure_sha256"],"reservation":retained},created_at=attempt["as_of"])
                    position=store.get_position(attempt["position_id"])
                if position is None or (position["activation_epoch_id"], position["strategy_spec_sha256"]) != (request["activation_epoch_id"], request["strategy_sha256"]):
                    raise PaperPlaneError("RECOVERY_ORIGIN_IDENTITY_CONFLICT")
                bound = self.runner.for_epoch(position["activation_epoch_id"])
                bound._origin(store, position)
                if attempt["side"]=="EXIT":
                    closure=request.get("recovery_closure") or {}
                    if closure.get("closure_sha256")!=sha256_of({k:v for k,v in closure.items() if k!="closure_sha256"}):
                        raise PaperPlaneError("RECOVERY_ORIGIN_CLOSURE_REQUIRED")
                    if position["state"] in {"OPEN","PARTIAL"}:
                        events=closure.get("exit_events")
                        if not isinstance(events,list) or len(events)!=2:
                            raise PaperPlaneError("RECOVERY_EXIT_CLOSURE_REQUIRED")
                        for event in events:
                            prior=store.get_execution_event(event["event_id"])
                            if prior and prior["payload"]!=event["payload"]:
                                raise PaperPlaneError("RECOVERY_EXIT_CONTENT_CONFLICT")
                            if not prior:
                                store.append_execution_event(event_type=event["event_type"],event_id=event["event_id"],
                                    bot_instance_id=event["bot_instance_id"],position_id=event["position_id"],payload=event["payload"],created_at=event["created_at"])
                        accept_exit_decision(self.runner.root,store,strategy=bound.strategy,exit_decision=events[0]["payload"]["decision"],
                            known_activation_epochs=bound._epoch(store,position["activation_epoch_id"],self.mode))
                        position=store.get_position(position["position_id"])
                    if position.get("exit_decision_id"):
                        bound._exit_origin(store,position)
                existing = store.get_execution_event(attempt["attempt_id"])
                if existing and existing["payload"] != attempt:
                    raise PaperPlaneError("RECOVERY_ATTEMPT_CONTENT_CONFLICT")
                if existing is None:
                    if attempt["side"] == "ENTRY":
                        if position["state"] not in PRE_ATTEMPT_STATES:
                            raise PaperPlaneError("RECOVERY_ENTRY_STATE_CONFLICT")
                        states = ("WATCHED", "SIGNALLED", "INTENT_CREATED", "ATTEMPTING")
                        for state in states[states.index(position["state"]) + 1:]:
                            store.transition(position["position_id"], state)
                    elif position["state"] not in {"EXIT_REQUIRED", "EXITING", "UNRESOLVED"}:
                        raise PaperPlaneError("RECOVERY_EXIT_STATE_CONFLICT")
                    store.append_execution_event(event_type="MODELED_ATTEMPT_STARTED", event_id=attempt["attempt_id"],
                        bot_instance_id=position["bot_instance_id"], position_id=position["position_id"], payload=attempt, created_at=attempt["as_of"])
                    store.append_execution_event(event_type="ADAPTER_REQUEST_BOUND", event_id="REQUEST-" + attempt["attempt_id"],
                        bot_instance_id=position["bot_instance_id"], position_id=position["position_id"], payload=request, created_at=attempt["as_of"])
                # Result acceptance uses this same transaction; its public
                # runner validates origin above, and the engine stays owner.
                if pending_only:
                    # A claim is known; its external outcome is not. Retain the
                    # original attempt without inventing a physical result clock.
                    return {"status":"PENDING_ATTEMPT_RESTORED","send_permitted":False}
                from solana_alpha_lab.factory.paper_plane import accept_modeled_result
                # A later UNKNOWN cumulative total cannot erase an earlier
                # accepted cost. Replay the original observations and clocks
                # through the accounting owner before accepting the last receipt.
                for event in result_observations:
                    observed=event["payload"]["result"]
                    expected_payload={"result":observed,"evidence_class":attempt["evidence_class"],
                        "chargeable_cost_status":"KNOWN" if observed.get("chargeable_cost_usd") is not None else "UNKNOWN"}
                    if (event["event_type"]!="MODELED_RESULT_ACCEPTED"
                        or event["event_id"]!="RESULT-"+canonical_spec_sha256({"result_id":observed["result_id"]}).upper()
                        or observed["attempt_id"]!=attempt["attempt_id"]
                        or event["position_id"]!=attempt["position_id"]
                        or event["bot_instance_id"]!=position["bot_instance_id"]
                        or event["created_at"]!=observed["observed_at"] or event["payload"]!=expected_payload
                        or parse_utc(observed["observed_at"])>parse_utc(result["observed_at"])):
                        raise PaperPlaneError("RECOVERY_RESULT_OBSERVATION_CONFLICT")
                    accept_modeled_result(store,result=observed)
                accepted = accept_modeled_result(store, result=result)
                maybe_finish_drain(store, position["bot_instance_id"])
                return {**accepted, "send_permitted": False}
        finally:
            store.close()

    def reconcile_cut(self,cut):
        self._validate_cut(cut)
        probe=self.runner._store(readonly=True)
        try:
            prior=probe.get_execution_event("RECOVERY-CUT-"+cut["cut_sha256"])
            if prior is not None:
                return {"status":"EXTERNAL_CUT_RECONCILED","idempotent":True,"send_permitted":False}
        finally:
            probe.close()
        store=self.runner._store()
        try:
            with store.immediate_write():
                for bundle in cut["operating_bindings"]:
                    if set(bundle)!={"activation","binding","profile"}:
                        raise PaperPlaneError("RECOVERY_OPERATING_BINDING_INVALID")
                    self.runner._set_frozen(bundle["binding"])
                    epoch=bundle["binding"]["payload"]["activation"]["epoch_id"]
                    for key,event_type,event_id in (("activation","OFFLINE_ACTIVATION_CREATED",epoch),
                        ("binding","OPERATING_BINDING_COMMITTED","OPERATING-"+epoch),("profile","OPERATING_PROFILE_COMMITTED","PROFILE-"+epoch)):
                        event=bundle[key]
                        if event["event_type"]!=event_type or event["event_id"]!=event_id or event["position_id"] is not None:
                            raise PaperPlaneError("RECOVERY_OPERATING_BINDING_INVALID")
                        prior=store.get_execution_event(event_id)
                        if prior and (prior["payload"]!=event["payload"] or prior["event_type"]!=event_type):
                            raise PaperPlaneError("RECOVERY_BINDING_CONTENT_CONFLICT")
                        if not prior:
                            store.append_execution_event(event_type=event_type,event_id=event_id,bot_instance_id=event["bot_instance_id"],
                                position_id=None,payload=event["payload"],created_at=event["created_at"])
                    if bundle["activation"]["payload"]!=bundle["binding"]["payload"]["activation"] or bundle["activation"]["payload"]["mode"]!=self.mode:
                        raise PaperPlaneError("RECOVERY_ACTIVATION_CONFLICT")
                    if self._profile(store,epoch)["mode"]!=self.mode:
                        raise PaperPlaneError("RECOVERY_PROFILE_MODE_CONFLICT")
                    bot=store.start_bot(self.runner.strategy,mode=self.mode,activation_epoch_id=epoch)
                    if bundle["activation"]["bot_instance_id"]!=bot["bot_instance_id"] or bundle["binding"]["bot_instance_id"]!=bot["bot_instance_id"]:
                        raise PaperPlaneError("RECOVERY_BOT_IDENTITY_CONFLICT")
                    store._conn.execute("UPDATE bot_instances SET entries_paused=1 WHERE bot_instance_id=?",(bot["bot_instance_id"],))
        finally:
            store.close()
        for receipt in cut["effects"]:
            observations=[event for event in cut["result_observations"]
                if event["payload"]["result"]["attempt_id"]==receipt["attempt"]["attempt_id"]]
            self.reconcile_restored_effect(receipt,result_observations=observations)
        for pending in cut["pending_attempts"]:
            receipt={"attempt":pending["attempt"],"request":pending["request"],"result":None}
            receipt["receipt_sha256"]=sha256_of(receipt)
            self.reconcile_restored_effect(receipt,pending_only=True)
        store=self.runner._store()
        try:
            with store.immediate_write():
                for claim in cut["quote_claims"]:
                    attempt=store.get_execution_event(claim["payload"]["attempt_id"])
                    if (claim["event_type"]!="QUOTE_CALL_CLAIMED" or claim["event_id"]!="QUOTE-CALL-"+claim["payload"]["attempt_id"]
                        or set(claim["payload"])!={"grant_sha256","attempt_id"} or len(claim["payload"]["grant_sha256"])!=64
                        or attempt is None or attempt["payload"]["mode"]!=self.mode
                        or claim["bot_instance_id"]!=attempt["bot_instance_id"] or claim["position_id"]!=attempt["position_id"]
                        or parse_utc(claim["created_at"])>parse_utc(cut["as_of"])):
                        raise PaperPlaneError("RECOVERY_QUOTE_CLAIM_IDENTITY_INVALID")
                    prior=store.get_execution_event(claim["event_id"])
                    if prior and (prior["payload"]!=claim["payload"] or prior["event_type"]!=claim["event_type"]):
                        raise PaperPlaneError("RECOVERY_QUOTE_CLAIM_CONTENT_CONFLICT")
                    if not prior:
                        store.append_execution_event(event_type=claim["event_type"],event_id=claim["event_id"],
                            bot_instance_id=claim["bot_instance_id"],position_id=claim["position_id"],payload=claim["payload"],created_at=claim["created_at"])
                state=store._conn.execute("SELECT * FROM ordinary_state WHERE mode=?",(self.mode,)).fetchone()
                current=cut["current_entry"]
                self.runner.for_epoch(current["epoch_id"])
                self._profile(store,current["epoch_id"])
                if type(current["generation"]) is not int or current["generation"]<state["generation"]:
                    raise PaperPlaneError("RECOVERY_CONTROL_GENERATION_CONFLICT")
                store._conn.execute("UPDATE ordinary_state SET epoch_id=?,generation=?,discovery_rowid=0,rescan_rowid=0 WHERE mode=?",
                    (current["epoch_id"],current["generation"],self.mode))
                bots={bot["bot_instance_id"]:bot for bot in store.bots() if bot["mode"]==self.mode}
                if set(bots)!={control["bot_instance_id"] for control in cut["controls"]}:
                    raise PaperPlaneError("RECOVERY_CONTROL_SET_CONFLICT")
                for control in cut["controls"]:
                    if control["status"] not in {"RUNNING","DRAINING","STOPPED"} or type(control["entries_paused"]) is not bool:
                        raise PaperPlaneError("RECOVERY_CONTROL_CONTENT_INVALID")
                    # A later local safety command dominates the older cut.
                    store._conn.execute("UPDATE bot_instances SET status=CASE WHEN status='STOPPED' THEN 'STOPPED' WHEN status='DRAINING' AND ?='RUNNING' THEN 'DRAINING' ELSE ? END,entries_paused=1 WHERE bot_instance_id=?",
                        (control["status"],control["status"],control["bot_instance_id"]))
                store.append_execution_event(event_type="RESTORE_EXTERNAL_CUT_RECONCILED",event_id="RECOVERY-CUT-"+cut["cut_sha256"],
                    bot_instance_id=None,position_id=None,payload={"mode":self.mode,"cut_sha256":cut["cut_sha256"],
                    "effects_n":len(cut["effects"]),"entries_paused":True},created_at=cut["as_of"])
            return {"status":"EXTERNAL_CUT_RECONCILED","effects_n":len(cut["effects"]),"entries_paused":True,"send_permitted":False}
        finally:
            store.close()

    def _validate_cut(self,cut):
        if (set(cut)!={"schema","schema_version","mode","backup_sha256","external_cut_id","as_of","effects","result_observations","current_entry","controls","operating_bindings","quote_claims","pending_attempts","completeness","cut_sha256"}
            or cut["schema"]!="smial.operating-external-recovery-cut" or cut["schema_version"]!="1.0"
            or cut["mode"]!=self.mode or cut["completeness"]!="COMPLETE_AFTER_BACKUP"
            or not isinstance(cut["external_cut_id"],str) or not cut["external_cut_id"]
            or not all(isinstance(cut[key],list) for key in ("effects","result_observations","controls","operating_bindings","quote_claims","pending_attempts"))
            or cut["cut_sha256"]!=sha256_of({k:v for k,v in cut.items() if k!="cut_sha256"})):
            raise PaperPlaneError("RESTORE_COMPLETE_EXTERNAL_CUT_REQUIRED")
        parse_utc(cut["as_of"])
        if (set(cut["current_entry"])!={"epoch_id","generation"}
            or len({row["bot_instance_id"] for row in cut["controls"]})!=len(cut["controls"])
            or any(set(row)!={"bot_instance_id","status","entries_paused"} for row in cut["controls"])
            or len({row["attempt"]["attempt_id"] for row in cut["effects"]})!=len(cut["effects"])
            or len({row["event_id"] for row in cut["quote_claims"]})!=len(cut["quote_claims"])
            or len({row["event_id"] for row in cut["result_observations"]})!=len(cut["result_observations"])
            or any(row["payload"]["result"]["attempt_id"] not in {effect["attempt"]["attempt_id"] for effect in cut["effects"]}
                or parse_utc(row["created_at"])>parse_utc(cut["as_of"]) for row in cut["result_observations"])
            or any(set(row)!={"attempt","request"} for row in cut["pending_attempts"])
            or len({row["attempt"]["attempt_id"] for row in cut["pending_attempts"]})!=len(cut["pending_attempts"])
            or {row["attempt"]["attempt_id"] for row in cut["pending_attempts"]}&{row["attempt"]["attempt_id"] for row in cut["effects"]}
            or any(parse_utc(row["result"]["observed_at"])>parse_utc(cut["as_of"]) for row in cut["effects"])):
            raise PaperPlaneError("RESTORE_EXTERNAL_CUT_CONTENT_INVALID")
        probe=self.runner._store(readonly=True)
        try:
            restored=probe.get_execution_event("RESTORE-SNAPSHOT")
            if restored is None or restored["payload"]["database_sha256"]!=cut["backup_sha256"]:
                raise PaperPlaneError("RESTORE_EXTERNAL_CUT_BACKUP_CONFLICT")
        finally:
            probe.close()

    def acknowledge_restore(self, *, expected_inventory_sha256, as_of,cut=None):
        from solana_alpha_lab.factory.trading_runtime_policy import obligation_summary
        if cut is None:
            raise PaperPlaneError("RESTORE_COMPLETE_EXTERNAL_CUT_REQUIRED")
        self._validate_cut(cut)
        parse_utc(as_of)
        store = self.runner._store()
        try:
            with store.immediate_write():
                if store.get_execution_event("RECOVERY-CUT-"+cut["cut_sha256"]) is None:
                    raise PaperPlaneError("RESTORE_EXTERNAL_CUT_NOT_RECONCILED")
                summary = obligation_summary(store, mode=self.mode)
                if sha256_of(summary) != expected_inventory_sha256:
                    raise PaperPlaneError("RESTORE_INVENTORY_CHANGED")
                if summary["inventory_status"] != "KNOWN" or summary["pending_attempt_count"]:
                    raise PaperPlaneError("RESTORE_RECONCILIATION_REQUIRED")
                # Acknowledging the independent ledger does not unpause a bot
                # or change any policy, envelope or activation pointer.
                for bot in store.bots():
                    if bot["mode"] == self.mode:
                        self.runner.for_epoch(bot["activation_epoch_id"])
                ack_id="RESTORE-ACK-" + sha256_of({"mode": self.mode, "inventory": expected_inventory_sha256, "at": as_of})
                if store.get_execution_event(ack_id) is not None:
                    return {"status":"RESTORE_RECONCILED","idempotent":True,"controls_preserved":True}
                store._conn.execute("UPDATE ordinary_state SET restore_guard=0 WHERE mode=?", (self.mode,))
                store.append_execution_event(event_type="RESTORE_RECONCILIATION_ACKNOWLEDGED",
                    event_id=ack_id,
                    bot_instance_id=None, position_id=None, payload={"mode": self.mode,
                    "inventory_sha256": expected_inventory_sha256, "as_of": as_of}, created_at=as_of)
                return {"status": "RESTORE_RECONCILED", "controls_preserved": True}
        finally:
            store.close()

    def run(self, *, ticks=None, stop=None):
        stop = stop or (lambda: False)
        count = 0
        with single_writer(self.runner):
            while not stop() and (ticks is None or count < ticks):
                self._tick_owned()
                count += 1
                if stop() or ticks is not None and count>=ticks:
                    break
                store = self.runner._store(readonly=True)
                try:
                    state = store._conn.execute("SELECT epoch_id FROM ordinary_state WHERE mode=?", (self.mode,)).fetchone()
                    try:
                        delay = self._profile(store, state[0])["poll_seconds"]
                    except (PaperPlaneError,KeyError,ValueError,TypeError):
                        retained=[]
                        for bot in store.bots():
                            if bot["mode"]!=self.mode:
                                continue
                            try:
                                retained.append(self._profile(store,bot["activation_epoch_id"])["poll_seconds"])
                            except (PaperPlaneError,KeyError,ValueError,TypeError):
                                continue
                        if not retained:
                            raise PaperPlaneError("OPERATING_POLL_PROFILE_UNAVAILABLE")
                        delay=min(retained)
                finally:
                    store.close()
                if ticks is None or count < ticks:
                    time.sleep(delay)
        return {"status": "GRACEFUL_SHUTDOWN", "ticks": count, "activation_created": False}


def restore_native_backup(*, backup_path, destination_runner):
    import hashlib
    manifest = json.loads(backup_path.with_suffix(backup_path.suffix + ".json").read_text(encoding="utf-8"))
    if manifest.get("database_sha256") != hashlib.sha256(backup_path.read_bytes()).hexdigest():
        raise PaperPlaneError("BACKUP_CONTENT_CONFLICT")
    destination_runner._validate_store_paths()
    if destination_runner.store_path.exists():
        raise PaperPlaneError("RESTORE_REQUIRES_FRESH_ROOT")
    source = sqlite3.connect(backup_path.resolve().as_uri() + "?mode=ro", uri=True)
    target = sqlite3.connect(destination_runner.store_path)
    try:
        source.backup(target)
        if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise PaperPlaneError("RESTORE_INTEGRITY_FAILED")
        target.execute("UPDATE ordinary_state SET restore_guard=1")
        target.commit()
    finally:
        target.close()
        source.close()
    restored=destination_runner._store()
    try:
        with restored.immediate_write():
            restored._conn.execute("UPDATE bot_instances SET entries_paused=1")
            restored.append_execution_event(event_type="RESTORE_SNAPSHOT_BOUND",event_id="RESTORE-SNAPSHOT",
                bot_instance_id=None,position_id=None,payload={"database_sha256":manifest["database_sha256"]},
                created_at=render_utc(datetime.now(UTC)))
    finally:
        restored.close()
    return {"status": "RESTORED_RECONCILIATION_REQUIRED", "new_effects_enabled": False, "database_integrity": "ok"}
