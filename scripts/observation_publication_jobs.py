#!/usr/bin/env python
"""Publication-job journal status / dry-run / apply / fat-ARTIFACTS resume.

Zero provider calls. APPLY and fat-ARTIFACTS resume refuse live ACTIVE/DRAINING
collectors. APPLY writes no RDP/Parquet/manifests. Fat resume continues an
already-proven ARTIFACTS job without materializing members[].
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.observation_panel_publisher import (  # noqa: E402
    ObservationPanelPublisherError,
    inspect_legacy_fat_open_artifacts,
    resume_legacy_fat_open_artifacts,
)
from solana_alpha_lab.factory.observation_publication_jobs import (  # noqa: E402
    AMBIGUOUS_BLOCKS_APPLY,
    COLLECTOR_NOT_PAUSED,
    COLLECTOR_STORE_MISSING,
    COMPACT_RECEIPT_UNCONSTRUCTABLE,
    COMPLETED_RECEIPT_CONFLICT,
    CONTENT_IDENTITY_COLLISION,
    CONTENT_SHA256_INVALID,
    FAT_ARTIFACTS_RESUME_ARTIFACT_MISSING,
    FAT_ARTIFACTS_RESUME_CONFLICT,
    FAT_ARTIFACTS_RESUME_CONTENT_REQUIRED,
    FAT_ARTIFACTS_RESUME_HASH_MISMATCH,
    FAT_ARTIFACTS_RESUME_IDENTITY_MISMATCH,
    FAT_ARTIFACTS_RESUME_NOT_LEGACY_FAT,
    FAT_ARTIFACTS_RESUME_OBSERVATION_INVALID,
    FAT_ARTIFACTS_RESUME_PAYLOAD_INVALID,
    FAT_ARTIFACTS_RESUME_PAYLOAD_TOO_LARGE,
    FAT_ARTIFACTS_RESUME_PRODUCER_SHA_REQUIRED,
    FAT_ARTIFACTS_RESUME_REQUIRES_FLAG,
    FAT_ARTIFACTS_RESUME_SCHEDULE_MISSING,
    FAT_ARTIFACTS_RESUME_SOURCE_NOT_REGULAR_OPEN,
    FAT_ARTIFACTS_RESUME_UNSUPPORTED_STAGE,
    LEGACY_FULL_BYTE_MISMATCH,
    OPEN_JOB_CONFLICT,
    SOURCE_CHANGED_AFTER_PLAN,
    PublicationJobError,
    apply_migration,
    collector_blocks_apply,
    collector_pause_proven,
    completed_job_path,
    dry_run_migration,
    is_compact_receipt,
    journal_stats,
    open_job_path,
    prove_legacy_fat_open_artifacts_source,
)
from solana_alpha_lab.factory.observation_schedule_runtime import (  # noqa: E402
    DEFAULT_RUNTIME_RELATIVE,
    ObservationRuntimeError,
    git_sha,
    load_runtime_config,
    resolve_data_root,
)
from solana_alpha_lab.factory.observation_schedule_store import (  # noqa: E402
    ObservationScheduleStore,
)

FAT_RESUME_TERMINALS = {
    COLLECTOR_NOT_PAUSED,
    COLLECTOR_STORE_MISSING,
    CONTENT_SHA256_INVALID,
    FAT_ARTIFACTS_RESUME_ARTIFACT_MISSING,
    FAT_ARTIFACTS_RESUME_CONFLICT,
    FAT_ARTIFACTS_RESUME_CONTENT_REQUIRED,
    FAT_ARTIFACTS_RESUME_HASH_MISMATCH,
    FAT_ARTIFACTS_RESUME_IDENTITY_MISMATCH,
    FAT_ARTIFACTS_RESUME_NOT_LEGACY_FAT,
    FAT_ARTIFACTS_RESUME_OBSERVATION_INVALID,
    FAT_ARTIFACTS_RESUME_PAYLOAD_INVALID,
    FAT_ARTIFACTS_RESUME_PAYLOAD_TOO_LARGE,
    FAT_ARTIFACTS_RESUME_PRODUCER_SHA_REQUIRED,
    FAT_ARTIFACTS_RESUME_REQUIRES_FLAG,
    FAT_ARTIFACTS_RESUME_SCHEDULE_MISSING,
    FAT_ARTIFACTS_RESUME_SOURCE_NOT_REGULAR_OPEN,
    FAT_ARTIFACTS_RESUME_UNSUPPORTED_STAGE,
    SOURCE_CHANGED_AFTER_PLAN,
}


def _emit(payload: dict, code: int) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    return code


def _producer_git_sha(configured: str | None) -> str:
    try:
        return git_sha(ROOT, configured)
    except ObservationRuntimeError as exc:
        raise PublicationJobError(FAT_ARTIFACTS_RESUME_PRODUCER_SHA_REQUIRED) from exc


def _load_store(store_path: Path) -> tuple[list[dict], ObservationScheduleStore]:
    if not store_path.is_file():
        raise PublicationJobError(COLLECTOR_STORE_MISSING)
    store = ObservationScheduleStore(store_path)
    try:
        activations = store.list_activations()
    except Exception:
        store.close()
        raise
    return activations, store


def _fat_error_payload(exc: BaseException) -> dict:
    text = str(exc)
    terminal = text if text in FAT_RESUME_TERMINALS else "PUBLICATION_JOB_ERROR"
    if isinstance(exc, ObservationPanelPublisherError) and text not in FAT_RESUME_TERMINALS:
        terminal = text
    return {
        "terminal": terminal,
        "reason": text,
        "provider_calls": 0,
        "scientific_writes": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "status",
            "dry-run",
            "apply",
            "inspect-fat-open",
            "resume-fat-artifacts",
        ),
    )
    parser.add_argument("--runtime-config", default=DEFAULT_RUNTIME_RELATIVE)
    parser.add_argument("--data-root")
    parser.add_argument("--ops-store")
    parser.add_argument("--content", help="Exact open job content_sha256 (64 hex)")
    parser.add_argument("--producer-git-sha", help="Exact producer git SHA for resume")
    parser.add_argument(
        "--i-understand-apply",
        action="store_true",
        help="Required exact flag for apply mode",
    )
    parser.add_argument(
        "--i-understand-resume",
        action="store_true",
        help="Required exact flag for fat ARTIFACTS resume",
    )
    args = parser.parse_args(argv)

    runtime = load_runtime_config(ROOT, args.runtime_config)
    data_root = (
        Path(args.data_root).resolve()
        if args.data_root
        else resolve_data_root(ROOT, str(runtime["data_root"]))
    )
    store_path = (
        Path(args.ops_store).resolve()
        if args.ops_store
        else (ROOT / str(runtime["ops_store_relative"])).resolve()
    )

    if args.command in {"status", "dry-run"}:
        report = dry_run_migration(data_root) if args.command == "dry-run" else journal_stats(data_root)
        if args.command == "status":
            report = dict(report)
            report.update(dry_run_migration(data_root))
        report["provider_calls"] = 0
        report["scientific_writes"] = 0
        report["legacy_full_deleted"] = False
        return _emit(report, 0)

    if args.command in {"inspect-fat-open", "resume-fat-artifacts"}:
        content = str(args.content or "")
        if not content:
            return _emit(
                {
                    "terminal": FAT_ARTIFACTS_RESUME_CONTENT_REQUIRED,
                    "reason": "--content",
                    "provider_calls": 0,
                    "scientific_writes": 0,
                },
                2,
            )
        if args.command == "resume-fat-artifacts" and not args.i_understand_resume:
            return _emit(
                {
                    "terminal": FAT_ARTIFACTS_RESUME_REQUIRES_FLAG,
                    "reason": "--i-understand-resume",
                    "provider_calls": 0,
                    "scientific_writes": 0,
                },
                2,
            )
        try:
            activations, store = _load_store(store_path)
        except PublicationJobError as exc:
            return _emit(_fat_error_payload(exc), 2)
        if collector_pause_proven(activations) is False:
            store.close()
            return _emit(
                {
                    "terminal": COLLECTOR_NOT_PAUSED,
                    "provider_calls": 0,
                    "scientific_writes": 0,
                    "activation_states": [
                        str(item.get("state") or "") for item in activations
                    ],
                },
                2,
            )
        try:
            open_path = open_job_path(data_root, content)
            completed = completed_job_path(data_root, content)
            if open_path.is_file():
                proven = prove_legacy_fat_open_artifacts_source(data_root, content)
                digest = str(proven["job"]["schedule_sha256"])
            elif completed.is_file():
                existing = json.loads(completed.read_text(encoding="utf-8"))
                if not isinstance(existing, dict) or not is_compact_receipt(existing):
                    raise PublicationJobError(FAT_ARTIFACTS_RESUME_CONFLICT)
                digest = str(existing.get("schedule_sha256") or "")
            else:
                raise PublicationJobError(FAT_ARTIFACTS_RESUME_SOURCE_NOT_REGULAR_OPEN)
            registered = store.get_registered_schedule(digest)
            if registered is None or not isinstance(registered.get("document"), dict):
                raise PublicationJobError(FAT_ARTIFACTS_RESUME_SCHEDULE_MISSING)
            schedule = dict(registered["document"])
            if args.command == "inspect-fat-open":
                report = inspect_legacy_fat_open_artifacts(
                    data_root=data_root,
                    root=ROOT,
                    content_sha256=content,
                    activations=activations,
                    schedule=schedule,
                )
                return _emit(report, 0)
            configured = str(args.producer_git_sha or "").strip() or None
            producer = _producer_git_sha(configured)
            report = resume_legacy_fat_open_artifacts(
                data_root=data_root,
                root=ROOT,
                content_sha256=content,
                activations=activations,
                schedule=schedule,
                producer_git_sha=producer,
                now=datetime.now(UTC),
            )
            return _emit(report, 0)
        except (PublicationJobError, ObservationPanelPublisherError) as exc:
            return _emit(_fat_error_payload(exc), 2)
        finally:
            store.close()

    if not args.i_understand_apply:
        return _emit(
            {
                "terminal": "APPLY_REQUIRES_FLAG",
                "reason": "--i-understand-apply",
                "provider_calls": 0,
                "scientific_writes": 0,
            },
            2,
        )
    if not store_path.is_file():
        return _emit(
            {
                "terminal": COLLECTOR_STORE_MISSING,
                "provider_calls": 0,
                "scientific_writes": 0,
            },
            2,
        )
    store = ObservationScheduleStore(store_path)
    try:
        activations = store.list_activations()
    finally:
        store.close()
    if collector_blocks_apply(activations):
        return _emit(
            {
                "terminal": COLLECTOR_NOT_PAUSED,
                "provider_calls": 0,
                "scientific_writes": 0,
                "activation_states": [
                    str(item.get("state") or "") for item in activations
                ],
            },
            2,
        )
    try:
        report = apply_migration(data_root)
    except PublicationJobError as exc:
        text = str(exc)
        known = {
            AMBIGUOUS_BLOCKS_APPLY,
            OPEN_JOB_CONFLICT,
            COMPLETED_RECEIPT_CONFLICT,
            LEGACY_FULL_BYTE_MISMATCH,
            COMPACT_RECEIPT_UNCONSTRUCTABLE,
            CONTENT_IDENTITY_COLLISION,
            CONTENT_SHA256_INVALID,
            SOURCE_CHANGED_AFTER_PLAN,
        }
        terminal = text if text in known else "PUBLICATION_JOB_ERROR"
        return _emit(
            {
                "terminal": terminal,
                "reason": text,
                "provider_calls": 0,
                "scientific_writes": 0,
                "legacy_full_deleted": False,
            },
            2,
        )
    report["terminal"] = "PUBLICATION_JOB_MIGRATION_APPLIED"
    report["provider_calls"] = 0
    report["scientific_writes"] = 0
    return _emit(report, 0)


if __name__ == "__main__":
    raise SystemExit(main())
