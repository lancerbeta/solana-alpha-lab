#!/usr/bin/env python
"""Bounded native retention: read-only plans and exact approved mutations."""
from __future__ import annotations
import argparse
import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / 'src') not in sys.path:
    sys.path.insert(0, str(ROOT / 'src'))
from solana_alpha_lab.factory.observation_schedule import parse_utc
from solana_alpha_lab.factory.observation_schedule_retention import (
    ObservationScheduleRetentionError, apply_retirement_plan, apply_physical_reclaim,
    build_retirement_plan, build_reclaim_plan, create_cold_archive, evaluate_retention,
    install_maintenance_policy, install_retirement, recover_physical_reclaim,
    register_checkpoint_retirement_archive,
    run_maintenance_step, retention_status,
    validate_retention_operation_mode,
)
from solana_alpha_lab.factory.observation_schedule_runtime import load_runtime_config
from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore, ObservationScheduleStoreError


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding='utf-8'))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('status','dry-run','plan','archive','retire','policy','apply','maintenance-step','reclaim-plan','reclaim-apply','reclaim-resume','reclaim-rollback','commission-store','register-checkpoint-archive'))
    parser.add_argument('--store')
    parser.add_argument('--runtime-config', default='configs/observation_schedule_runtime_v1.yaml')
    parser.add_argument('--raw-retention-days', type=int, default=31)
    parser.add_argument('--now')
    parser.add_argument('--input')
    parser.add_argument('--policy')
    parser.add_argument('--plan')
    parser.add_argument('--approved-sha256')
    parser.add_argument('--output')
    parser.add_argument('--archive-path')
    parser.add_argument('--restored-path')
    parser.add_argument('--routine-root', action='append', default=[])
    parser.add_argument('--data-root')
    parser.add_argument('--factory-root')
    parser.add_argument('--isolated-root')
    parser.add_argument('--operation-mode', choices=('ISOLATED_REHEARSAL','OPERATE'), default='ISOLATED_REHEARSAL')
    parser.add_argument('--after')
    parser.add_argument('--pressure-input')
    parser.add_argument('--max-rows', type=int, default=256)
    parser.add_argument('--max-bytes', type=int, default=8 * 1024 * 1024)
    parser.add_argument('--max-wall-seconds', type=float, default=1)
    parser.add_argument('--writers-quiesced', action='store_true')
    parser.add_argument('--i-understand-apply', action='store_true')
    args = parser.parse_args(argv)
    readonly = args.command in {'status','dry-run','plan','archive','reclaim-plan'}
    if not readonly and not args.i_understand_apply:
        print('APPLY_REQUIRES_FLAG: --i-understand-apply', file=sys.stderr)
        return 2
    store = None
    try:
        if args.output and Path(args.output).exists():
            raise ObservationScheduleRetentionError('OUTPUT_ARTIFACT_EXISTS')
        if args.command=='register-checkpoint-archive' and not all((args.store,args.factory_root,args.isolated_root,args.input,args.output)):
            raise ObservationScheduleRetentionError('EXACT_STORE_FACTORY_ISOLATED_PROOF_OUTPUT_REQUIRED')
        if args.store:
            path = Path(args.store).resolve()
        else:
            runtime = load_runtime_config(ROOT, args.runtime_config)
            path = (ROOT / str(runtime['ops_store_relative'])).resolve()
        now = parse_utc(args.now) if args.now else datetime.now(UTC)
        data_root = Path(args.data_root).resolve() if args.data_root else path.parent
        factory_root = Path(args.factory_root).resolve() if args.factory_root else (path.parent if args.store else ROOT)
        if args.command=='register-checkpoint-archive' and not path.is_file():
            raise ObservationScheduleRetentionError('SOURCE_NOT_PRESENT')
        if args.command=='archive' and args.operation_mode!='ISOLATED_REHEARSAL':
            raise ObservationScheduleRetentionError('ARCHIVE_ISOLATED_REHEARSAL_ONLY')
        # Reject mode/proof disagreements before opening a writable native owner:
        # even startup commissioning must not alter a denied source.
        if args.command in {'retire','policy','apply','maintenance-step','reclaim-apply'}:
            if args.command in {'retire','policy'} and (not args.input or not args.approved_sha256):
                raise ObservationScheduleRetentionError('EXACT_APPROVED_INPUT_REQUIRED')
            if args.command=='apply' and (not args.plan or not args.approved_sha256):
                raise ObservationScheduleRetentionError('EXACT_APPROVED_PLAN_REQUIRED')
            if args.command=='reclaim-apply' and (not args.plan or not args.input or not args.approved_sha256):
                raise ObservationScheduleRetentionError('RECLAIM_PLAN_AND_RECOVERY_PROOF_REQUIRED')
            probe=ObservationScheduleStore(path,readonly=True,immutable=False)
            try:
                if args.command=='retire':
                    validate_retention_operation_mode(probe,operation_mode=args.operation_mode,retirement=_load(args.input))
                elif args.command=='policy':
                    validate_retention_operation_mode(probe,operation_mode=args.operation_mode,policy=_load(args.input),commissioning=True)
                elif args.command=='reclaim-apply':
                    plan=_load(args.plan)
                    if plan.get('operation_mode')!=args.operation_mode:
                        raise ObservationScheduleRetentionError('OPERATION_MODE_MISMATCH')
                    if args.operation_mode=='OPERATE':
                        proof=_load(args.input)
                        if proof.get('proof_class')!='REMOTE_CHECKPOINT_RESTORE_VERIFIED':
                            raise ObservationScheduleRetentionError('RECLAIM_INDEPENDENT_OPERATE_PROOF_REQUIRED')
                        row=probe._conn.execute("SELECT payload_json FROM retention_control WHERE control_key='checkpoint_archive'").fetchone()
                        if row is None or json.loads(row[0])!=proof:
                            raise ObservationScheduleRetentionError('RECLAIM_REGISTERED_OPERATE_PROOF_REQUIRED')
                else:
                    row=probe._conn.execute("SELECT payload_json FROM retention_control WHERE control_key='policy'").fetchone()
                    policy=json.loads(row[0])['policy'] if row else None
                    if args.command=='apply':
                        plan=_load(args.plan)
                    else:
                        row=probe._conn.execute("SELECT payload_json FROM retention_control WHERE control_key='active_plan'").fetchone()
                        plan=json.loads(row[0]) if row else None
                    validate_retention_operation_mode(probe,operation_mode=args.operation_mode,policy=policy,plan=plan,now=now)
            finally:
                probe.close()
        if args.command in {'reclaim-resume','reclaim-rollback'}:
            result = recover_physical_reclaim(path, data_root=data_root,
                action='resume' if args.command == 'reclaim-resume' else 'rollback',
                approved_plan_sha256=args.approved_sha256 or '',
                plan=_load(args.plan) if args.plan else None,operation_mode=args.operation_mode)
        else:
            store = ObservationScheduleStore(path, readonly=readonly, immutable=False)
            if args.command in {'status','dry-run'}:
                result = evaluate_retention(store, now=now, raw_retention_days=args.raw_retention_days,
                    max_rows=args.max_rows, max_bytes=args.max_bytes, max_wall_seconds=args.max_wall_seconds,
                    after=json.loads(args.after) if args.after else None)
                result['mode'] = args.command
            elif args.command == 'commission-store':
                result = {'status':'STORE_METADATA_COMMISSIONED', **retention_status(store)}
            elif args.command == 'register-checkpoint-archive':
                register_checkpoint_retirement_archive(store,proof=_load(args.input),
                    isolated_root=Path(args.isolated_root).resolve(),source_root=factory_root,now=now)
                # Export the actual source-owned record, never a hand-authored
                # conversion from the off-host terminal proof.
                row=store._conn.execute("SELECT payload_json FROM retention_control WHERE control_key='checkpoint_archive'").fetchone()
                result=json.loads(row[0])
            elif args.command == 'archive':
                if not args.archive_path or not args.restored_path or not args.routine_root:
                    raise ObservationScheduleRetentionError('ARCHIVE_PATHS_AND_ROUTINE_ROOTS_REQUIRED')
                result = create_cold_archive(store, archive_path=Path(args.archive_path).resolve(),
                    restored_path=Path(args.restored_path).resolve(), routine_roots=[Path(p).resolve() for p in args.routine_root])
            elif args.command in {'retire','policy'}:
                if not args.input or not args.approved_sha256:
                    raise ObservationScheduleRetentionError('EXACT_APPROVED_INPUT_REQUIRED')
                operation = install_retirement if args.command == 'retire' else install_maintenance_policy
                keyword = {'retirement' if args.command == 'retire' else 'policy':_load(args.input)}
                result = operation(store, **keyword, approved_sha256=args.approved_sha256, now=now,operation_mode=args.operation_mode)
            elif args.command == 'plan':
                if args.policy:
                    policy = _load(args.policy)
                else:
                    row = store._conn.execute("SELECT payload_json FROM retention_control WHERE control_key='policy'").fetchone()
                    if row is None:
                        raise ObservationScheduleRetentionError('APPROVED_POLICY_REQUIRED')
                    policy = json.loads(row[0])['policy']
                result = build_retirement_plan(store, now=now, policy=policy,
                    after=json.loads(args.after) if args.after else None,operation_mode=args.operation_mode)
            elif args.command == 'apply':
                if not args.plan or not args.approved_sha256:
                    raise ObservationScheduleRetentionError('EXACT_APPROVED_PLAN_REQUIRED')
                result = apply_retirement_plan(store, plan=_load(args.plan), approved_plan_sha256=args.approved_sha256, now=now,operation_mode=args.operation_mode)
            elif args.command == 'maintenance-step':
                result = run_maintenance_step(store, now=now, pressure=_load(args.pressure_input) if args.pressure_input else None,operation_mode=args.operation_mode)
            elif args.command == 'reclaim-plan':
                result = build_reclaim_plan(store, data_root=data_root, max_wall_seconds=args.max_wall_seconds,
                    backup_root=factory_root, operation_mode=args.operation_mode)
            elif args.command == 'reclaim-apply':
                if not args.plan or not args.input or not args.approved_sha256:
                    raise ObservationScheduleRetentionError('RECLAIM_PLAN_AND_RECOVERY_PROOF_REQUIRED')
                result = apply_physical_reclaim(store, plan=_load(args.plan), approved_plan_sha256=args.approved_sha256,
                    data_root=data_root, writers_quiesced=args.writers_quiesced, independent_recovery_proof=_load(args.input), now=now, backup_root=factory_root,operation_mode=args.operation_mode)
            else:
                raise ObservationScheduleRetentionError('COMMAND_NOT_IMPLEMENTED')
        if args.output:
            with Path(args.output).open('x', encoding='utf-8') as output:
                json.dump(result, output, sort_keys=True, indent=2)
                output.write('\n')
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except (ObservationScheduleRetentionError, ObservationScheduleStoreError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error):
        print('RETENTION_INPUT_OR_SOURCE_UNAVAILABLE', file=sys.stderr)
        return 2
    finally:
        if store is not None:
            try:
                store.close()
            except sqlite3.ProgrammingError:
                pass

if __name__ == '__main__':
    raise SystemExit(main())
