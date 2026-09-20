#!/usr/bin/env python
"""Zero-network Discovery Evidence Release CLI (seal / verify / import)."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.discovery_evidence_release import (
    DiscoveryReleaseError,
    import_discovery_release,
    load_source_inventory,
    seal_discovery_release,
    verify_discovery_release,
)
from solana_alpha_lab.factory.live_cohort_discovery_release import (
    LiveCohortReleaseError,
    build_live_observation_source_from_rdp,
    import_live_cohort,
    live_cohort_status,
    repair_live_corpus_manifests,
    seal_live_cohort,
    verify_live_cohort,
)
from solana_alpha_lab.factory.bounded_cohort_materialization import (
    UNBOUNDED_PLAN,
    plan_is_unbounded,
)
from solana_alpha_lab.factory.live_cohort_source_bundle import (
    SOURCE_BUILD_WORKER_ENV,
    apply_source_build_address_limit,
    source_build_child_was_resource_killed,
)
from solana_alpha_lab.factory.live_cohort_to_forge import (
    LiveCohortToForgeError,
    assert_closure_ready,
    assert_source_matches_receipt,
    build_closure_receipt,
    forge_control_ready,
    list_live_cohorts,
    publish_live_cohort,
    resolve_operator_path,
)
from solana_alpha_lab.factory.cohort_import_readback import (
    PASS_ALREADY_PRESENT_EXACT,
    STOP_IDENTITY_CONFLICT,
    build_cohort_import_readback,
    owner_import_terminal,
)
from solana_alpha_lab.factory.data_root import DataRootError, resolve_data_root

FAIL_OWNER_NEXT = {
    "NOT_MATURE": "WAIT_UNTIL_COHORT_MATURE",
    "COHORT_DUE_OPEN": "WAIT_UNTIL_COHORT_DUES_CLOSED",
    "PUBLICATION_OPEN": "WAIT_UNTIL_PUBLICATION_JOBS_CLOSED",
    "IDENTITY_CONFLICT": "STOP_DO_NOT_RESEAL",
    "COVERAGE_CONFIRMED_BROKEN": "STOP_DO_NOT_SEAL",
    "LOW_YIELD": "WAIT_UNTIL_YIELD_ELIGIBLE",
    "IMPORT_CONFLICT": "STOP_DO_NOT_REIMPORT",
    "COHORT_ALREADY_IMPORTED": "STOP_DO_NOT_REIMPORT",
    "CLOSED_RECEIPT_INCOMPLETE": "STOP_MISSING_CLOSURE_EVIDENCE",
    "CLOSED_RECEIPT_MISSING": "STOP_MISSING_CLOSURE_EVIDENCE",
    "CLOSED_RECEIPT_STORE_MISSING": "STOP_MISSING_CLOSURE_EVIDENCE",
    "RELEASE_BLOCKED_BUDGET": "WAIT_UNTIL_BUDGET_UNBLOCKED",
    "CURRENT_CORPUS_MISSING": "IMPORT_VERIFIED_RELEASE_FIRST",
    "TRANSPORT_HASH_MISMATCH": "STOP_DO_NOT_IMPORT",
    "SOURCE_BUILD_RESOURCE_LIMIT": "STOP_RETRY_BOUNDED_SOURCE_BUILD",
    "UNBOUNDED_MATERIALIZATION_PLAN": "STOP_FIX_BOUNDED_PLAN_BEFORE_BUILD",
    "BUILD_ALREADY_RUNNING": "STOP_WAIT_OR_RECOVER_DEAD_LOCK",
    "MATERIALIZATION_WALL_BUDGET_EXCEEDED": "STOP_NO_PARTIAL_CANONICAL_PUBLISH",
    "OBSERVATION_LINEAGE_INCOMPLETE": "STOP_RESTORE_OBSERVATION_LINEAGE",
    "CURRENT_CORPUS_LEGACY_METADATA_REQUIRES_REPAIR": "REPAIR_LIVE_CORPUS_METADATA_FIRST",
    "CORPUS_LINEAGE_INCOMPLETE": "STOP_RESTORE_LINEAGE_THEN_RETRY_REPAIR",
    "DATASET_TERMINAL_MISSING": "STOP_RESTORE_LABELS_THEN_RETRY_REPAIR",
    "CORPUS_PARQUET_SHA_MISMATCH": "STOP_DO_NOT_REPAIR_PARQUET_DRIFT",
    "LIVE_CORPUS_LOGICAL_CONTENT_NOT_RECONSTRUCTIBLE": "STOP_DO_NOT_REPAIR_PARQUET_UNREADABLE",
    "CANONICAL_TARGET_CONFLICT": "STOP_DO_NOT_OVERWRITE_CANONICAL_TARGET",
    "DATASET_PUBLICATION_INCOMPLETE": "REPAIR_LIVE_CORPUS_METADATA_FIRST",
    "LIVE_CORPUS_PARQUET_SYMLINK": "STOP_DO_NOT_FOLLOW_PARQUET_SYMLINK",
    "SEAL_SCHEDULE_DOCUMENT_MISSING": "STOP_SCHEDULE_DOCUMENT_REQUIRED",
    "SCHEDULE_DOCUMENT_CONFLICT": "STOP_DO_NOT_SEAL",
    "SCHEDULE_ARTIFACT_MISSING": "STOP_DO_NOT_IMPORT",
    "SCHEDULE_ARTIFACT_HASH_MISMATCH": "STOP_DO_NOT_IMPORT",
    "SCHEDULE_SEMANTIC_SHA_MISMATCH": "STOP_DO_NOT_IMPORT",
    "SCHEDULE_PARSER_INVALID": "STOP_DO_NOT_IMPORT",
    "SCHEDULE_PRODUCER_UNBOUND": "STOP_SCHEDULE_PRODUCER_REQUIRED",
    "DATA_ROOT_NON_GIT_CONTEXT": "STOP_USE_GIT_CHECKOUT_OR_EXPLICIT_DATA_ROOT",
}


def _parse_utc(value: str | None) -> datetime | None:
    if value is None:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


def _path(value: Path) -> Path:
    return resolve_operator_path(ROOT, value)


def _resolved_data_root(value: Path | None) -> Path:
    if value is None:
        return resolve_data_root(ROOT)
    return _path(value)


def _print_import_success(result: object, data_root: Path) -> None:
    payload: dict[str, object] = {"result": result}
    status = "PASS"
    inner_status = None
    if isinstance(result, dict):
        inner_status = result.get("status")
        imported = result.get("import")
        if inner_status is None and isinstance(imported, dict):
            inner_status = imported.get("status")
    if isinstance(inner_status, str):
        terminal = owner_import_terminal(inner_status)
        if terminal == PASS_ALREADY_PRESENT_EXACT:
            status = PASS_ALREADY_PRESENT_EXACT
    payload["status"] = status
    payload["readback"] = build_cohort_import_readback(data_root)
    print(json.dumps(payload, sort_keys=True, default=str))


def _spawn_source_build_worker(argv: list[str]) -> int:
    env = os.environ.copy()
    env[SOURCE_BUILD_WORKER_ENV] = "1"
    capture = not sys.stdout.isatty()
    proc = subprocess.run(
        [sys.executable, "-B", str(Path(__file__).resolve()), *argv],
        env=env,
        capture_output=capture,
        text=True if capture else None,
    )
    if source_build_child_was_resource_killed(proc.returncode):
        payload = {
            "status": "FAIL",
            "code": "SOURCE_BUILD_RESOURCE_LIMIT",
            "next": FAIL_OWNER_NEXT["SOURCE_BUILD_RESOURCE_LIMIT"],
        }
        print(json.dumps(payload, sort_keys=True))
        return 2
    if capture:
        if proc.stdout:
            sys.stdout.write(proc.stdout)
            if not proc.stdout.endswith("\n"):
                sys.stdout.write("\n")
        if proc.stderr:
            sys.stderr.write(proc.stderr)
            if not proc.stderr.endswith("\n"):
                sys.stderr.write("\n")
    return int(proc.returncode)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    seal = sub.add_parser("seal", help="Seal a compact discovery release")
    seal.add_argument("--body", type=Path, required=True)
    seal.add_argument("--envelope", type=Path, required=True)
    seal.add_argument("--source-receipt", type=Path, default=None)
    seal.add_argument("--release-root", type=Path, required=True)
    seal.add_argument("--sealed-at", type=str, default=None)

    verify = sub.add_parser("verify", help="Verify a sealed release")
    verify.add_argument("--release-root", type=Path, required=True)

    imp = sub.add_parser("import", help="Import a verified release into an RDP root")
    imp.add_argument("--release-root", type=Path, required=True)
    imp.add_argument("--data-root", type=Path, required=True)
    imp.add_argument("--import-at", type=str, default=None)

    build_live = sub.add_parser(
        "build-live-source",
        help="Rebuild cohort-scoped live source bundle from Observation RDP",
    )
    build_live.add_argument("--observation-rdp", type=Path, required=True)
    build_live.add_argument("--ops-store", type=Path, required=True)
    build_live.add_argument("--schedule-sha256", required=True)
    build_live.add_argument("--activation-id", required=True)
    build_live.add_argument("--cohort-id", required=True)
    build_live.add_argument("--as-of", type=str, default=None)
    build_live.add_argument("--discovery-coverage-class", default=None)
    build_live.add_argument(
        "--plan-only",
        action="store_true",
        help="Emit the bounded work plan and stop before payload replay",
    )

    live_status = sub.add_parser(
        "live-status", help="Cohort readiness from immutable Observation RDP"
    )
    live_status.add_argument("--observation-rdp", type=Path, required=True)
    live_status.add_argument("--cohort-id", required=True)
    live_status.add_argument("--as-of", type=str, default=None)

    seal_live = sub.add_parser("seal-live-cohort", help="Seal a ready live cohort")
    seal_live.add_argument("--observation-rdp", type=Path, required=True)
    seal_live.add_argument("--cohort-id", required=True)
    seal_live.add_argument("--release-root", type=Path, required=True)
    seal_live.add_argument("--sealed-at", type=str, default=None)
    seal_live.add_argument("--as-of", type=str, default=None)
    seal_live.add_argument("--release-builder-git-sha", default=None)

    verify_live = sub.add_parser("verify-live", help="Verify a sealed live cohort")
    verify_live.add_argument("--release-root", type=Path, required=True)

    import_live = sub.add_parser(
        "import-live", help="Import a verified live cohort into the LIVE CORPUS"
    )
    import_live.add_argument("--release-root", type=Path, required=True)
    import_live.add_argument(
        "--data-root",
        type=Path,
        default=None,
        help="LIVE CORPUS root; omit to use the Git principal checkout local/factory_v1/data_plane",
    )
    import_live.add_argument("--import-at", type=str, default=None)

    repair_live = sub.add_parser(
        "repair-live-corpus-manifests",
        help="Metadata-only TASK-06 repair of the current LIVE CORPUS root",
    )
    repair_live.add_argument("--data-root", type=Path, required=True)
    repair_live.add_argument("--published-at", type=str, default=None)

    publish = sub.add_parser(
        "publish-live-cohort",
        help="One-shot: closure → source → seal → verify → transport → import → Forge CONTROL",
    )
    publish.add_argument("--observation-rdp", type=Path, required=True)
    publish.add_argument("--ops-store", type=Path, required=True)
    publish.add_argument("--schedule-sha256", required=True)
    publish.add_argument("--activation-id", required=True)
    publish.add_argument("--cohort-id", default=None)
    publish.add_argument(
        "--data-root",
        type=Path,
        default=None,
        help="LIVE CORPUS root; omit to use the Git principal checkout local/factory_v1/data_plane",
    )
    publish.add_argument("--release-root", type=Path, default=None)
    publish.add_argument("--as-of", type=str, default=None)
    publish.add_argument("--release-builder-git-sha", default=None)
    publish.add_argument("--discovery-coverage-class", default=None)

    listed = sub.add_parser(
        "list-live-cohorts",
        help="List campaign cohorts and the next mature unimported cohort",
    )
    listed.add_argument("--observation-rdp", type=Path, required=True)
    listed.add_argument("--ops-store", type=Path, required=True)
    listed.add_argument("--schedule-sha256", required=True)
    listed.add_argument("--activation-id", required=True)
    listed.add_argument("--data-root", type=Path, default=None)
    listed.add_argument("--as-of", type=str, default=None)

    forge_ready = sub.add_parser(
        "forge-control-ready",
        help="Read-only Forge CONTROL readiness (does not run /hypothesis-forge)",
    )
    forge_ready.add_argument("--data-root", type=Path, required=True)
    forge_ready.add_argument("--imported-cohort-id", default=None)

    args = parser.parse_args(argv)
    if args.command in {
        "build-live-source",
        "publish-live-cohort",
        "list-live-cohorts",
        "seal-live-cohort",
        "verify-live",
        "live-status",
    }:
        argv = argv if argv is not None else sys.argv[1:]
        skip_worker = args.command == "build-live-source" and "--plan-only" in argv
        if os.environ.get(SOURCE_BUILD_WORKER_ENV) != "1" and not skip_worker:
            return _spawn_source_build_worker(list(argv))
        if not skip_worker:
            apply_source_build_address_limit()
    try:
        if args.command == "seal":
            inventory = load_source_inventory(
                body_path=_path(args.body),
                envelope_path=_path(args.envelope),
                source_receipt_path=(
                    None if args.source_receipt is None else _path(args.source_receipt)
                ),
            )
            result = seal_discovery_release(
                inventory=inventory,
                release_root=_path(args.release_root),
                sealed_at=_parse_utc(args.sealed_at),
            )
        elif args.command == "verify":
            result = verify_discovery_release(_path(args.release_root))
        elif args.command == "import":
            result = import_discovery_release(
                release_root=_path(args.release_root),
                data_root=_path(args.data_root),
                import_time=_parse_utc(args.import_at),
            )
        elif args.command == "build-live-source":
            observation_rdp = _path(args.observation_rdp)
            as_of = _parse_utc(args.as_of) or datetime.now().astimezone()
            receipt = build_closure_receipt(
                ops_store=_path(args.ops_store),
                observation_rdp=observation_rdp,
                schedule_sha256=args.schedule_sha256,
                activation_id=args.activation_id,
                cohort_id=args.cohort_id,
                as_of=as_of,
            )
            assert_closure_ready(receipt)
            result = build_live_observation_source_from_rdp(
                observation_rdp_root=observation_rdp,
                schedule_sha256=args.schedule_sha256,
                activation_id=args.activation_id,
                cohort_id=args.cohort_id,
                as_of=as_of,
                closure_receipt=receipt,
                discovery_coverage_class=args.discovery_coverage_class,
                ops_store=_path(args.ops_store),
                plan_only=bool(args.plan_only),
            )
            if args.plan_only:
                if plan_is_unbounded(result):
                    payload = {
                        "status": "FAIL",
                        "code": UNBOUNDED_PLAN,
                        "next": FAIL_OWNER_NEXT[UNBOUNDED_PLAN],
                        "plan": result,
                    }
                    print(json.dumps(payload, sort_keys=True))
                    return 2
            else:
                assert_source_matches_receipt(result, receipt)
        elif args.command == "live-status":
            result = live_cohort_status(
                observation_rdp_root=_path(args.observation_rdp),
                cohort_id=args.cohort_id,
                as_of=_parse_utc(args.as_of),
            )
        elif args.command == "seal-live-cohort":
            result = seal_live_cohort(
                observation_rdp_root=_path(args.observation_rdp),
                cohort_id=args.cohort_id,
                release_root=_path(args.release_root),
                sealed_at=_parse_utc(args.sealed_at),
                as_of=_parse_utc(args.as_of),
                release_builder_git_sha=args.release_builder_git_sha,
            )
        elif args.command == "verify-live":
            result = verify_live_cohort(_path(args.release_root))
        elif args.command == "import-live":
            data_root = _resolved_data_root(args.data_root)
            result = import_live_cohort(
                release_root=_path(args.release_root),
                data_root=data_root,
                import_time=_parse_utc(args.import_at),
            )
            _print_import_success(result, data_root)
            return 0
        elif args.command == "repair-live-corpus-manifests":
            result = repair_live_corpus_manifests(
                data_root=_path(args.data_root),
                published_at=_parse_utc(args.published_at),
            )
        elif args.command == "publish-live-cohort":
            data_root = _resolved_data_root(args.data_root)
            result = publish_live_cohort(
                repo_root=ROOT,
                observation_rdp=_path(args.observation_rdp),
                ops_store=_path(args.ops_store),
                schedule_sha256=args.schedule_sha256,
                activation_id=args.activation_id,
                cohort_id=args.cohort_id,
                data_root=data_root,
                release_root=None if args.release_root is None else _path(args.release_root),
                as_of=_parse_utc(args.as_of),
                release_builder_git_sha=args.release_builder_git_sha,
                discovery_coverage_class=args.discovery_coverage_class,
            )
            _print_import_success(result, data_root)
            return 0
        elif args.command == "list-live-cohorts":
            result = list_live_cohorts(
                observation_rdp=_path(args.observation_rdp),
                ops_store=_path(args.ops_store),
                schedule_sha256=args.schedule_sha256,
                activation_id=args.activation_id,
                data_root=None if args.data_root is None else _path(args.data_root),
                as_of=_parse_utc(args.as_of),
            )
        else:
            result = forge_control_ready(
                data_root=_path(args.data_root),
                repo_root=ROOT,
                imported_cohort_id=args.imported_cohort_id,
            )
    except MemoryError:
        if os.environ.get(SOURCE_BUILD_WORKER_ENV) != "1":
            raise
        payload = {
            "status": "FAIL",
            "code": "SOURCE_BUILD_RESOURCE_LIMIT",
            "next": FAIL_OWNER_NEXT["SOURCE_BUILD_RESOURCE_LIMIT"],
        }
        print(json.dumps(payload, sort_keys=True))
        return 2
    except (DiscoveryReleaseError, LiveCohortReleaseError, LiveCohortToForgeError, DataRootError) as exc:
        code = str(exc)
        next_action = FAIL_OWNER_NEXT.get(code, "STOP_INSPECT_FAIL_CODE")
        if args.command in {"import-live", "publish-live-cohort"}:
            terminal = owner_import_terminal(code)
            if terminal == STOP_IDENTITY_CONFLICT:
                next_action = STOP_IDENTITY_CONFLICT
        payload = {
            "status": "FAIL",
            "code": code,
            "next": next_action,
        }
        print(json.dumps(payload, sort_keys=True))
        return 2
    print(json.dumps({"status": "PASS", "result": result}, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
