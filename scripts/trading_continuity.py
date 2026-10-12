"""Ordinary synthetic offline PAPER/SHADOW continuity entry; no external execution."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path, PureWindowsPath
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from solana_alpha_lab.factory.trading_runner import TradingContinuityRunner, OFFLINE_MARKER
from solana_alpha_lab.factory.strategy_runtime import PaperPlaneError
from solana_alpha_lab.factory.research_store import ResearchStoreError
from solana_alpha_lab.factory.trading_coordinator import TradingCoordinator, exact_child, normalize_profile, restore_native_backup, check_execution_inputs
from solana_alpha_lab.factory.observation_schedule import parse_utc


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("init", "load", "activate", "episode", "attempt", "result", "exit", "operator", "readback",
        "init-operating", "check", "operating-activate", "switch", "tick", "run", "status", "backup", "restore", "reconcile", "ack-restore",
        "pause", "resume", "drain", "close", "envelope", "seal-cut", "export-cut"))
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--strategy", help="Repository-relative, exact materialized StrategyVersion")
    parser.add_argument("--mode", choices=("PAPER", "SHADOW", "LIVE"), default="PAPER")
    parser.add_argument("--epoch")
    parser.add_argument("--as-of")
    parser.add_argument("--episode-id")
    parser.add_argument("--source", default="source/observation_schedule_state.sqlite")
    parser.add_argument("--position-id")
    parser.add_argument("--side", choices=("ENTRY", "EXIT"))
    parser.add_argument("--attempt-key")
    parser.add_argument("--input", help="Offline-root-relative result or operator command JSON")
    parser.add_argument("--profile", help="Runtime-relative operating profile; required only for explicit activation")
    parser.add_argument("--scope-root", type=Path, help="Explicit existing scope containing a marked operating root")
    parser.add_argument("--switch-key")
    parser.add_argument("--expected-current-epoch")
    parser.add_argument("--ticks", type=int)
    parser.add_argument("--clock-file", help="Synthetic-only runtime-relative clock; never a production clock")
    parser.add_argument("--destination", help="Runtime-relative new backup path")
    parser.add_argument("--backup", type=Path, help="Exact retained native backup for a fresh marked root")
    parser.add_argument("--inventory-sha256")
    parser.add_argument("--external-cut-id")
    parser.add_argument("--complete-after-backup",action="store_true",help="Explicit independent-ledger completeness assertion for export-cut")
    parser.add_argument("--quote-grant", help="Runtime-relative exact external quote authority; software task grants none")
    parser.add_argument("--credential-env", help="Explicit existing credential variable name; never a value")
    parser.add_argument("--format", choices=("json", "human"), default="json")
    parser.add_argument("--evidence-class", choices=("SYNTHETIC_OFFLINE", "OBSERVED"))
    parser.add_argument("--bot-instance-id")
    parser.add_argument("--idempotency-key")
    args = parser.parse_args(argv)
    try:
        if args.mode == "LIVE":
            raise PaperPlaneError("LIVE_ROUTE_FORBIDDEN")
        if args.command in {"init", "init-operating"}:
            if args.command == "init-operating" and (args.scope_root is None or args.evidence_class is None):
                raise PaperPlaneError("EXACT_OPERATING_SCOPE_AND_EVIDENCE_CLASS_REQUIRED")
            local_arg = args.scope_root if args.command == "init-operating" else args.repository_root / "local"
            local = local_arg.resolve(strict=True)
            if local != local_arg.absolute():
                raise PaperPlaneError("OFFLINE_ROOT_LINK_FORBIDDEN")
            target = args.data_root.resolve(strict=False)
            if target == local or not target.is_relative_to(local) or target != args.data_root.absolute():
                raise PaperPlaneError("OFFLINE_ROOT_UNSAFE")
            for item in (args.data_root, *args.data_root.parents):
                if item.is_symlink() or (hasattr(item, "is_junction") and item.is_junction()):
                    raise PaperPlaneError("OFFLINE_ROOT_LINK_FORBIDDEN")
                if item == local:
                    break
            if target.exists() and any(target.iterdir()):
                raise PaperPlaneError("OFFLINE_INIT_REQUIRES_EMPTY_ROOT")
            target.mkdir(parents=True, exist_ok=True)
            marker = OFFLINE_MARKER if args.command == "init" else {"schema":"smial.operating-runtime", "schema_version":"1.0", "evidence_class":args.evidence_class}
            name = "offline_runtime.json" if args.command == "init" else "operating_runtime.json"
            (target / name).write_text(json.dumps(marker) + "\n", encoding="utf-8")
            result = {"status": "INITIALIZED", "evidence_class": marker["evidence_class"], "activation_created": False}
        else:
            runner = TradingContinuityRunner(args.repository_root, data_root=args.data_root,
                strategy_relative=args.strategy, scope_root=args.scope_root)
            def read_input(relative):
                if not relative:
                    raise PaperPlaneError("EXACT_INPUT_REQUIRED")
                return json.loads(exact_child(runner.data_root, relative).read_text(encoding="utf-8"))
            clock = None
            if (runner.evidence_class == "OBSERVED" and args.command in {"status", "check", "tick", "run"}
                and (args.as_of or args.clock_file)):
                raise PaperPlaneError("OBSERVED_RUNTIME_REQUIRES_PHYSICAL_CLOCK")
            if args.clock_file:
                if runner.evidence_class != "SYNTHETIC_OFFLINE" or not (runner.data_root / "offline_runtime.json").is_file():
                    raise PaperPlaneError("SYNTHETIC_CLOCK_FORBIDDEN")
                clock = lambda: parse_utc(read_input(args.clock_file)["as_of"])
            elif args.as_of and runner.evidence_class != "OBSERVED":
                # OBSERVED activation/cut timestamps remain original metadata;
                # current input freshness always uses the physical owner clock.
                clock = lambda: parse_utc(args.as_of)
            quote_adapter = None
            if args.quote_grant:
                if args.command not in {"run", "tick"} or args.mode != "SHADOW" or runner.evidence_class != "OBSERVED":
                    raise PaperPlaneError("QUOTE_EXTERNAL_AUTHORITY_REQUIRED")
                if not args.credential_env or not re.fullmatch(r"[A-Z][A-Z0-9_]{2,80}", args.credential_env):
                    raise PaperPlaneError("QUOTE_CREDENTIAL_CONFIGURATION_REQUIRED")
                from solana_alpha_lab.factory.trading_adapters import verified_quote_grant, JupiterQuoteAdapter
                grant = verified_quote_grant(args.repository_root, read_input(args.quote_grant))
                import os
                def credential_supplier():
                    value = os.environ.get(args.credential_env)
                    if not value:
                        raise PaperPlaneError("QUOTE_CREDENTIAL_CONFIGURATION_REQUIRED")
                    return value
                # Read bounds from the committed profile, never an implicit default.
                store = runner._store(readonly=True)
                try:
                    row = store._conn.execute("SELECT epoch_id FROM ordinary_state WHERE mode=?", (args.mode,)).fetchone()
                    if row is None:
                        raise PaperPlaneError("ORDINARY_ACTIVATION_REQUIRED")
                    cfg = TradingCoordinator(runner, mode=args.mode)._profile(store, row[0])["quote"]
                finally:
                    store.close()
                quote_adapter = JupiterQuoteAdapter(timeout_seconds=cfg["timeout_seconds"], max_response_bytes=cfg["max_response_bytes"],
                    grant=grant, credential_supplier=credential_supplier)
            ordinary = TradingCoordinator(runner, mode=args.mode, clock=clock, quote_adapter=quote_adapter)
            if args.command == "load":
                if runner.strategy is None:
                    raise PaperPlaneError("EXACT_STRATEGY_PATH_REQUIRED")
                result = {"status": "LOADED_VERIFIED", "strategy_sha256": runner.strategy["spec_sha256"], "activation_created": False}
            elif args.command == "check":
                if runner.strategy is None:
                    raise PaperPlaneError("EXACT_STRATEGY_PATH_REQUIRED")
                profile = normalize_profile(read_input(args.profile), recipe=runner.recipe, mode=args.mode)
                result = {"status": "PROFILE_VERIFIED", "mode": profile["mode"], "activation_created": False,
                    **check_execution_inputs(profile,as_of=ordinary.clock().isoformat().replace("+00:00","Z")),
                    "network_authorized": False, "financial_authority": False}
            elif args.command in {"operating-activate", "switch"}:
                if not args.strategy or not args.epoch or not args.as_of or not args.switch_key:
                    raise PaperPlaneError("EXACT_ACTIVATION_INPUT_REQUIRED")
                result = ordinary.activate(epoch_id=args.epoch, at=args.as_of, profile=read_input(args.profile),
                    switch_key=args.switch_key, expected_current_epoch=args.expected_current_epoch)
            elif args.command == "tick":
                result = ordinary.tick()
            elif args.command == "run":
                import signal
                if args.ticks is not None and args.ticks <= 0:
                    raise PaperPlaneError("RUN_TICK_LIMIT_INVALID")
                stopping = [False]
                for name in ("SIGINT", "SIGTERM", "SIGBREAK"):
                    if hasattr(signal, name):
                        signal.signal(getattr(signal, name), lambda *_: stopping.__setitem__(0, True))
                result = ordinary.run(ticks=args.ticks, stop=lambda: stopping[0])
            elif args.command == "status":
                result = ordinary.status()
            elif args.command=="export-cut":
                if not args.complete_after_backup or not args.external_cut_id or not args.as_of or not args.destination:
                    raise PaperPlaneError("RESTORE_COMPLETE_EXTERNAL_CUT_REQUIRED")
                cut=ordinary.export_recovery_cut(backup_path=Path(args.backup),effects=read_input(args.input),
                    external_cut_id=args.external_cut_id,as_of=args.as_of)
                destination=exact_child(runner.data_root,args.destination,exists=False)
                if destination.exists():
                    raise PaperPlaneError("RECOVERY_CUT_DESTINATION_MUST_BE_NEW")
                destination.write_text(json.dumps(cut,sort_keys=True,allow_nan=False)+"\n",encoding="utf-8")
                result={"status":"RECOVERY_CUT_EXPORTED","completeness":"CALLER_ASSERTED_COMPLETE_CUT", "send_permitted":False}
            elif args.command == "backup":
                result = ordinary.backup(destination_relative=args.destination)
            elif args.command == "restore":
                if args.backup is None:
                    raise PaperPlaneError("EXACT_BACKUP_REQUIRED")
                scope = args.scope_root or (args.repository_root / "local").resolve(strict=True)
                backup = exact_child(scope, args.backup.absolute().relative_to(scope))
                exact_child(scope, backup.relative_to(scope).as_posix() + ".json")
                result = restore_native_backup(backup_path=backup, destination_runner=runner)
            elif args.command == "reconcile":
                body=read_input(args.input)
                result = ordinary.reconcile_cut(body) if body.get("schema")=="smial.operating-external-recovery-cut" else ordinary.reconcile_restored_effect(body)
            elif args.command == "seal-cut":
                from solana_alpha_lab.factory.hfic_research_scope import sha256_of
                body=read_input(args.input)
                if "cut_sha256" in body:
                    raise PaperPlaneError("CUT_INPUT_MUST_BE_UNSIGNED")
                body["cut_sha256"]=sha256_of(body)
                ordinary._validate_cut(body)
                target=exact_child(runner.data_root,args.destination,exists=False)
                if target.exists():
                    raise PaperPlaneError("CUT_DESTINATION_MUST_BE_NEW")
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_text(json.dumps(body,sort_keys=True)+"\n",encoding="utf-8")
                result={"status":"CUT_VERIFIED_AND_SEALED","cut_sha256":body["cut_sha256"],"destination":args.destination,"external_completeness_claim":"CALLER_ASSERTED_COMPLETE_CUT","authority_granted":False}
            elif args.command == "ack-restore":
                result = ordinary.acknowledge_restore(expected_inventory_sha256=args.inventory_sha256, as_of=args.as_of,cut=read_input(args.input))
            elif args.command in {"pause", "resume", "drain", "close"}:
                if not args.idempotency_key:
                    raise PaperPlaneError("EXACT_COMMAND_IDENTITY_REQUIRED")
                names={"pause":"PAUSE_NEW_ENTRIES", "resume":"RESUME_NEW_ENTRIES", "drain":"STOP_BOT", "close":"REQUEST_CLOSE_POSITION"}
                payload={"command_type":names[args.command], "idempotency_key":args.idempotency_key}
                if args.command == "close":
                    if not args.position_id:
                        raise PaperPlaneError("EXACT_POSITION_REQUIRED")
                    payload["position_id"]=args.position_id
                else:
                    if not args.bot_instance_id:
                        raise PaperPlaneError("EXACT_BOT_SCOPE_REQUIRED")
                    payload["bot_instance_id"]=args.bot_instance_id
                result=runner.command(payload)
            elif args.command == "envelope":
                from solana_alpha_lab.factory.trading_runtime_policy import configure_operating_envelope
                payload=read_input(args.input)
                if payload.get("owner_authorization_phrase") != "AUTHORIZE PAPER SHADOW OPERATING ENVELOPE APPLY":
                    raise PaperPlaneError("OPERATING_ENVELOPE_OWNER_AUTHORITY_REQUIRED")
                store=runner._store()
                try:
                    result=configure_operating_envelope(store, mode=args.mode, candidate_raw=payload["candidate"],
                        expected_current_sha256=payload["expected_current_sha256"],idempotency_key=payload["idempotency_key"],as_of=payload["as_of"])
                finally:
                    store.close()
            elif args.command == "activate":
                result = runner.activate(epoch_id=args.epoch, mode=args.mode, at=args.as_of)
            elif args.command == "episode":
                result = runner.episode(source_relative=args.source, episode_id=args.episode_id, epoch_id=args.epoch, mode=args.mode, as_of=args.as_of)
            elif args.command == "attempt":
                result = runner.attempt(position_id=args.position_id, side=args.side, attempt_key=args.attempt_key, as_of=args.as_of)
            elif args.command == "exit":
                result = runner.exit(position_id=args.position_id, source_relative=args.source, as_of=args.as_of)
            elif args.command == "readback":
                result = runner.readback()
            else:
                payload = read_input(args.input)
                result = runner.result(payload) if args.command == "result" else runner.command(payload)
        if args.format == "human" and args.command == "status":
            inventory = result["inventory"]
            print(f"{result['mode']} · {result['status']} · epoch {result['activation_epoch_id']}\n"
                f"На {result['as_of']} · последний tick: {result['last_tick_at'] or 'NONE'}\n"
                f"Процесс: {result['process_alive']} · источник: {result['input_reason']} ({result['source_latest_at'] or 'NONE'}) · прогресс: {result['progress_moving']}\n"
                f"Конфигурация: {result['operating_configuration_status']} · входы исполнения: {result['execution_input_status']}\n"
                f"Политика входов: {result['runtime_policy_status']} · revision: {result['runtime_policy_revision'] if result['runtime_policy_revision'] is not None else 'NONE'} · SHA256: {result['runtime_policy_sha256']}\n"
                f"Обязательства: {inventory['position_count']} · стоимость: {inventory['outstanding_cost_basis_usd'] if inventory['outstanding_cost_basis_usd'] is not None else 'UNKNOWN'} USD · pending attempts: {result['pending_attempts']}\n"
                f"Целостность: {result['integrity_verified']} · restore fence: {result['restore_guard']} · earliest overdue: {result['earliest_overdue'] or 'NONE'}\n"
                f"Inventory SHA256: {result['inventory_sha256']}")
            for bot in result["instances"]:
                print(f"Bot {bot['bot_instance_id']} · {bot['status']} · entries paused: {bool(bot['entries_paused'])}")
            for position in inventory["positions"]:
                print(f"Position {position['position_id']} · {position['state']} · remaining: {position.get('remaining_quantity','UNKNOWN')}")
            for incident in result["incidents"]:
                if incident["active"]:
                    print(f"Incident {incident['incident_key']} · {incident['reason']} · с {incident['first_at']} · {incident['occurrences']} наблюдений")
            print("Далее: CLI "+result["next_safe_command"]+" (с теми же repository/data/scope flags)")
        else:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
        return 0
    except (ValueError, OSError, sqlite3.DatabaseError, TypeError, KeyError, ResearchStoreError) as exc:
        # Typed domain errors are safe codes; native exceptions never expose paths.
        code, next_action = "OFFLINE_INPUT_SHAPE_INVALID", "CHECK_REQUIRED_INPUT_FIELDS"
        if isinstance(exc, FileNotFoundError):
            code, next_action = "OFFLINE_SOURCE_NOT_PRESENT", "RESTORE_EXACT_SOURCE_DO_NOT_BOOTSTRAP_READBACK"
        elif isinstance(exc, PermissionError):
            code, next_action = "OFFLINE_SOURCE_ACCESS_DENIED", "RESOLVE_LOCAL_ACCESS_WITHOUT_RECREATING_STATE"
        elif isinstance(exc, json.JSONDecodeError):
            code, next_action = "OFFLINE_INPUT_JSON_INVALID", "CORRECT_JSON_WITHOUT_REUSING_CONFLICTING_CONTENT_ID"
        elif isinstance(exc, sqlite3.DatabaseError):
            corrupt = getattr(exc, "sqlite_errorcode", None) in {sqlite3.SQLITE_CORRUPT, sqlite3.SQLITE_NOTADB}
            code = "OFFLINE_DATABASE_CORRUPT" if corrupt else "OFFLINE_DATABASE_READ_OR_LOCK_UNAVAILABLE"
            next_action = "RESTORE_EXACT_NATIVE_BACKUP" if corrupt else "CHECK_OWNED_HANDLES_AND_SOURCE_ACCESS"
        elif isinstance(exc, ResearchStoreError):
            code, next_action = "OFFLINE_BOUND_RESEARCH_UNAVAILABLE", "RESTORE_EXACT_BOUND_RESEARCH_INPUT"
        elif isinstance(exc, ValueError) and re.fullmatch(r"[A-Z][A-Z0-9_]{1,119}", str(exc)):
            code, next_action = str(exc), "RESOLVE_REASON_AT_FROZEN_SOURCE_OWNER"
            next_action = {"SOURCE_NOT_PRESENT": "RESTORE_EXACT_SOURCE_DO_NOT_BOOTSTRAP_READBACK",
                "AUTOMATIC_EXIT_INACTIVE_EPOCH_UNRESOLVED_USE_OPERATOR": "REQUEST_CLOSE_POSITION_THEN_RECONCILE",
                "ATTEMPT_RECONCILIATION_REQUIRED": "RECONCILE_SAME_ATTEMPT_BEFORE_RETRY"}.get(code, next_action)
        if args.format=="human":
            guidance={"EXECUTION_QUOTE_INPUT_NOT_PRESENT":"Подготовь указанный в quote profile файл funding observation внутри source.root и повтори check.",
                "CONFIGURATION_REQUIRED":"Укажи явно разрешённые max_outstanding_positions и max_outstanding_cost_basis_usd в envelope профиля; затем повтори check.",
                "OPERATING_ENVELOPE_INVALID":"Проверь структуру и версию envelope профиля; затем повтори check. Общий лимит не становится unlimited.",
                "EXECUTION_OBSERVATION_STALE_OR_FUTURE":"Обнови своевременное наблюдение в exact source; затем повтори check. UNKNOWN не освобождает обязательства.",
                "RESTORE_COMPLETE_EXTERNAL_CUT_REQUIRED":"Получи полный независимый cut, проверь seal-cut и выполни reconcile; fence остаётся.",
                "QUOTE_EXTERNAL_AUTHORITY_REQUIRED":"Quote provider не разрешён; для внешнего вызова нужен отдельный exact grant.",
                "QUOTE_CALL_CAP_EXHAUSTED":"Лимит grant исчерпан. Чтение, pause и выяснение прежней попытки доступны; новый вызов требует отдельной authority."}
            print("Действие заблокировано · "+code+"\nДалее: "+guidance.get(code,"Проверь exact вход и его владельца; reason "+code+", следующий шаг "+next_action+"."))
        else:
            print(json.dumps({"status": "BLOCKED", "reason_code": code, "next_safe_action": next_action,
                              "evidence_class": "SYNTHETIC_OFFLINE"}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
