#!/usr/bin/env python3
"""Thin network-free CLI for Hypothesis Forge operational sessions."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

HFIC_REQUIRED_PYTHON = "3.13.14"
HFIC_RUNTIME_PYTHON_VERSION_INCOMPATIBLE = "HFIC_RUNTIME_PYTHON_VERSION_INCOMPATIBLE"


def running_python_release(version_info: Any = None) -> str:
    info = sys.version_info if version_info is None else version_info
    return "{}.{}.{}".format(info.major, info.minor, info.micro)


def hfic_runtime_python_terminal(version_info: Any = None) -> str | None:
    if running_python_release(version_info) != HFIC_REQUIRED_PYTHON:
        return HFIC_RUNTIME_PYTHON_VERSION_INCOMPATIBLE
    return None


def enforce_hfic_runtime_python(version_info: Any = None) -> None:
    terminal = hfic_runtime_python_terminal(version_info)
    if terminal is None:
        return
    print(terminal, file=sys.stderr)
    raise SystemExit(1)


enforce_hfic_runtime_python()

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.data_root import (  # noqa: E402
    DataRootError,
    resolve_active_data_root,
)
from solana_alpha_lab.factory.document_runner import (  # noqa: E402
    repository_git_snapshot,
)
from solana_alpha_lab.factory.hfic_preflight import (  # noqa: E402
    HficPreflightError,
    build_offline_commission_packet,
    is_fast_lane_commissioned,
    run_preflight,
    store_inventory_digest,
)
from solana_alpha_lab.factory.hfic_prospects import (  # noqa: E402
    HficProspectError,
)
from solana_alpha_lab.factory.hfic_session import (  # noqa: E402
    HficSessionError,
    PENDING_STATES,
    apply_classification,
    apply_revision,
    backfill_legacy,
    canonical_preflight_receipt_sha256,
    find_session_by_search_key,
    freeze_draft,
    list_hfic_sessions,
    lookup_prior,
    prove_runtime,
    show_session,
)
from solana_alpha_lab.factory.hfic_provenance import (  # noqa: E402
    apply_provenance_correction,
    inventory_placeholder_hfic_records,
)
from solana_alpha_lab.factory.research_store import (  # noqa: E402
    ResearchStore,
    ResearchStoreError,
)


MAX_JSON_BYTES = 262144
_DRIVE_RE = re.compile(r"[A-Za-z]:\\")


class HficCliError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def emit(payload: dict[str, Any], *, exit_code: int = 0) -> int:
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    print(rendered)
    return exit_code


def emit_error(code: str, *, exit_code: int = 1) -> int:
    print(code, file=sys.stderr)
    return exit_code


def _assert_no_path_leak(payload: dict[str, Any], *forbidden: str) -> None:
    rendered = json.dumps(payload, ensure_ascii=False)
    if _DRIVE_RE.search(rendered) or "SMIAL_DATA_ROOT" in rendered:
        raise HficCliError("PHYSICAL_PATH_LEAK")
    for item in forbidden:
        if item and item in rendered:
            raise HficCliError("PHYSICAL_PATH_LEAK")


def _load_json_file(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise HficCliError("HFIC_PROTOCOL_INVALID")
    data = path.read_bytes()
    if len(data) > MAX_JSON_BYTES:
        raise HficCliError("HFIC_PROTOCOL_INVALID")
    loaded = json.loads(data.decode("utf-8"))
    if not isinstance(loaded, dict):
        raise HficCliError("HFIC_PROTOCOL_INVALID")
    return loaded


def _load_fast_lane():
    path = ROOT / "scripts" / "hypothesis_fast_lane.py"
    spec = importlib.util.spec_from_file_location("hfic_fast_lane_helper", path)
    if spec is None or spec.loader is None:
        raise HficCliError("FAST_LANE_NOT_COMMISSIONABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _commission_offline(repo_root: Path, data_root: Path) -> dict[str, Any]:
    module = _load_fast_lane()
    packet = build_offline_commission_packet(repo_root)
    with tempfile.TemporaryDirectory() as tmp:
        packet_path = Path(tmp) / "offline_commission.json"
        packet_path.write_text(
            json.dumps(packet, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        git_before = repository_git_snapshot(repo_root)
        try:
            payload = module.execute_commission_offline(repo_root, data_root, packet_path)
        except Exception as exc:
            code = getattr(exc, "code", None)
            if isinstance(code, str) and code:
                raise HficCliError(code) from exc
            raise HficCliError("FAST_LANE_NOT_COMMISSIONABLE") from exc
        git_after = repository_git_snapshot(repo_root)
        if not git_before.unchanged(git_after):
            raise HficCliError("GIT_MUTATION_DETECTED")
    if payload.get("provider_calls_actual") not in {0, None}:
        raise HficCliError("PROVIDER_CALLS_FORBIDDEN")
    return payload


def _active_root(repo_root: Path, explicit_data_root: Path | None):
    return resolve_active_data_root(
        repo_root,
        explicit_data_root=explicit_data_root,
        is_commissioned=is_fast_lane_commissioned,
        inventory_digest=store_inventory_digest,
    )


def cmd_preflight(
    repo_root: Path,
    *,
    owner_focus: str,
    auto_commission: bool,
    explicit_data_root: Path | None,
) -> int:
    try:
        active = _active_root(repo_root, explicit_data_root)
        data_root = active.root
    except DataRootError as exc:
        payload = {
            "action": "STOP",
            "terminal": str(exc),
            "owner_focus": owner_focus,
            "data_root_instance_fingerprint": None,
        }
        _assert_no_path_leak(payload, str(repo_root))
        return emit(payload, exit_code=2)
    snap = repository_git_snapshot(repo_root)
    try:
        receipt = run_preflight(
            repo_root,
            data_root,
            owner_focus=owner_focus,
            auto_commission=auto_commission,
            commission_fn=_commission_offline if auto_commission else None,
            git_snapshot={
                "head_sha": snap.head_sha,
                "composite_sha256": snap.composite_sha256,
            },
        )
    except HficPreflightError as exc:
        payload = {
            "action": "STOP",
            "terminal": str(exc),
            "owner_focus": owner_focus,
            **active.redacted_receipt(),
        }
        _assert_no_path_leak(payload, str(data_root), str(repo_root))
        return emit(payload, exit_code=2)
    payload = {
        **active.redacted_receipt(),
        **receipt,
    }
    payload["preflight_receipt_sha256"] = canonical_preflight_receipt_sha256(payload)
    _assert_no_path_leak(payload, str(data_root), str(repo_root))
    exit_code = 0 if receipt["action"] != "STOP" else 2
    return emit(payload, exit_code=exit_code)


def _store_root(repo_root: Path, explicit_data_root: Path | None) -> Path:
    return _active_root(repo_root, explicit_data_root).root


def cmd_freeze(
    repo_root: Path,
    draft_path: Path,
    preflight_path: Path | None,
    explicit_data_root: Path | None,
    next_action_path: Path | None = None,
) -> int:
    git_before = repository_git_snapshot(repo_root)
    draft = _load_json_file(draft_path)
    if preflight_path is None:
        raise HficCliError("PREFLIGHT_RECEIPT_REQUIRED")
    receipt = _load_json_file(preflight_path)
    next_action_draft = None
    if next_action_path is not None:
        next_action_draft = _load_json_file(next_action_path)
    data_root = _store_root(repo_root, explicit_data_root)
    store = ResearchStore(data_root)
    frozen = freeze_draft(
        draft,
        preflight_receipt=receipt,
        store=store,
        repo_root=repo_root,
        next_action_draft=next_action_draft,
    )
    git_after = repository_git_snapshot(repo_root)
    if not git_before.unchanged(git_after):
        raise HficCliError("GIT_MUTATION_DETECTED")
    frozen["authority"] = {
        "git_mutation": 0,
        "experiment_execution": 0,
        "provider_api_rpc_wss_calls": 0,
    }
    _assert_no_path_leak(frozen, str(data_root), str(repo_root))
    return emit(frozen)


def cmd_prospects(
    repo_root: Path,
    *,
    trigger: str,
    max_results: int,
) -> int:
    from solana_alpha_lab.factory.hfic_prospects import query_prospects

    git_before = repository_git_snapshot(repo_root)
    payload = query_prospects(
        repo_root,
        trigger=trigger,
        max_results=max_results,
    )
    git_after = repository_git_snapshot(repo_root)
    if not git_before.unchanged(git_after):
        raise HficCliError("GIT_MUTATION_DETECTED")
    _assert_no_path_leak(payload, str(repo_root))
    return emit(payload)


def cmd_finalize(
    repo_root: Path,
    session_id: str,
    critic_path: Path,
    explicit_data_root: Path | None,
) -> int:
    from solana_alpha_lab.factory.hfic_session import finalize_session, load_session_bundle

    git_before = repository_git_snapshot(repo_root)
    critic_result = _load_json_file(critic_path)
    data_root = _store_root(repo_root, explicit_data_root)
    store = ResearchStore(data_root)
    frozen = load_session_bundle(store, session_id)
    if frozen is None:
        raise HficCliError("SESSION_NOT_FOUND")
    receipt = finalize_session(
        frozen,
        critic_result,
        store=store,
        repo_root=repo_root,
        data_root=data_root,
    )
    git_after = repository_git_snapshot(repo_root)
    if not git_before.unchanged(git_after):
        raise HficCliError("GIT_MUTATION_DETECTED")
    _assert_no_path_leak(receipt, str(data_root), str(repo_root))
    return emit(receipt)


def cmd_revise(
    repo_root: Path,
    session_id: str,
    draft_path: Path,
    explicit_data_root: Path | None,
) -> int:
    from solana_alpha_lab.factory.hfic_session import load_session_bundle

    git_before = repository_git_snapshot(repo_root)
    draft = _load_json_file(draft_path)
    data_root = _store_root(repo_root, explicit_data_root)
    store = ResearchStore(data_root)
    frozen = load_session_bundle(store, session_id)
    if frozen is None:
        raise HficCliError("SESSION_NOT_FOUND")
    payload = apply_revision(
        frozen,
        draft,
        store=store,
        repo_root=repo_root,
    )
    git_after = repository_git_snapshot(repo_root)
    if not git_before.unchanged(git_after):
        raise HficCliError("GIT_MUTATION_DETECTED")
    _assert_no_path_leak(payload, str(data_root), str(repo_root))
    return emit(payload)


def cmd_classify(
    repo_root: Path,
    session_id: str,
    spec_path: Path,
    explicit_data_root: Path | None,
) -> int:
    from solana_alpha_lab.factory.hfic_session import load_session_bundle

    git_before = repository_git_snapshot(repo_root)
    packet = _load_json_file(spec_path)
    data_root = _store_root(repo_root, explicit_data_root)
    store = ResearchStore(data_root)
    frozen = load_session_bundle(store, session_id)
    if frozen is None:
        raise HficCliError("SESSION_NOT_FOUND")
    payload = apply_classification(
        frozen,
        packet,
        store=store,
        repo_root=repo_root,
        data_root=data_root,
    )
    git_after = repository_git_snapshot(repo_root)
    if not git_before.unchanged(git_after):
        raise HficCliError("GIT_MUTATION_DETECTED")
    _assert_no_path_leak(payload, str(data_root), str(repo_root))
    return emit(payload)


def cmd_show_session(
    repo_root: Path,
    *,
    session_id: str | None,
    search_key: str | None,
    explicit_data_root: Path | None,
) -> int:
    if bool(session_id) == bool(search_key):
        raise HficCliError("HFIC_PROTOCOL_INVALID")
    data_root = _store_root(repo_root, explicit_data_root)
    store = ResearchStore(data_root)
    if search_key:
        bundle = find_session_by_search_key(store, search_key)
        if bundle is None:
            raise HficCliError("SESSION_NOT_FOUND")
        session_id = str(bundle["session_id"])
    payload = show_session(store, str(session_id), repo_root=repo_root)
    _assert_no_path_leak(payload, str(data_root), str(repo_root))
    return emit(payload)


def cmd_pending(
    repo_root: Path,
    *,
    search_key: str,
    explicit_data_root: Path | None,
) -> int:
    data_root = _store_root(repo_root, explicit_data_root)
    store = ResearchStore(data_root)
    pending = [
        {
            "session_id": item.get("session_id"),
            "session_state": item.get("session_state"),
            "search_key_sha256": item.get("search_key_sha256"),
            "evidence_epoch_sha256": item.get("evidence_epoch_sha256"),
            "focus_key_sha256": item.get("focus_key_sha256"),
        }
        for item in list_hfic_sessions(store)
        if item.get("search_key_sha256") == search_key
        and item.get("session_state") in PENDING_STATES
    ]
    payload = {
        "match_count": len(pending),
        "sessions": pending,
        "authority": {
            "git_mutation": 0,
            "experiment_execution": 0,
            "provider_api_rpc_wss_calls": 0,
        },
    }
    _assert_no_path_leak(payload, str(data_root), str(repo_root))
    return emit(payload)


def cmd_prior(
    repo_root: Path,
    *,
    candidate_raw: str | None,
    query: str | None,
    explicit_data_root: Path | None,
) -> int:
    if not candidate_raw and not query:
        raise HficCliError("HFIC_PROTOCOL_INVALID")
    candidate = None
    if candidate_raw:
        loaded = json.loads(candidate_raw)
        if not isinstance(loaded, dict):
            raise HficCliError("HFIC_PROTOCOL_INVALID")
        candidate = loaded
    data_root = _store_root(repo_root, explicit_data_root)
    store = ResearchStore(data_root)
    payload = lookup_prior(store, candidate=candidate, query=query)
    _assert_no_path_leak(payload, str(data_root), str(repo_root))
    return emit(payload)


def cmd_prove_runtime(
    repo_root: Path,
    session_id: str,
    explicit_data_root: Path | None,
) -> int:
    data_root = _store_root(repo_root, explicit_data_root)
    store = ResearchStore(data_root)
    payload = prove_runtime(store, session_id, repo_root=repo_root)
    _assert_no_path_leak(payload, str(data_root), str(repo_root))
    return emit(payload)


def cmd_inventory_placeholder_times(
    repo_root: Path,
    explicit_data_root: Path | None,
) -> int:
    data_root = _store_root(repo_root, explicit_data_root)
    store = ResearchStore(data_root)
    payload = inventory_placeholder_hfic_records(store)
    public = {
        "record_count": payload["record_count"],
        "counts_by_session_id": payload["counts_by_session_id"],
        "counts_by_record_kind": payload["counts_by_record_kind"],
        "counts_by_artifact_kind": payload["counts_by_artifact_kind"],
        "counts_by_affected_field": payload["counts_by_affected_field"],
        "inventory_sha256": payload["inventory_sha256"],
        "original_placeholder_value": payload["original_placeholder_value"],
        "original_exact_time_status": "UNKNOWN",
        "chronological_use_forbidden": True,
        "records": [
            {
                "record_id": item["record_id"],
                "payload_sha256": item["payload_sha256"],
                "record_kind": item["record_kind"],
                "artifact_kind": item.get("artifact_kind"),
                "session_id": item.get("session_id"),
                "affected_fields": item["affected_fields"],
            }
            for item in payload["records"]
        ],
        "authority": payload["authority"],
    }
    _assert_no_path_leak(public, str(data_root), str(repo_root))
    return emit(public)


def cmd_apply_provenance_correction(
    repo_root: Path,
    explicit_data_root: Path | None,
    *,
    confirm_append_only: bool,
) -> int:
    if not confirm_append_only:
        raise HficCliError("PROVENANCE_CORRECTION_CONFIRM_REQUIRED")
    data_root = _store_root(repo_root, explicit_data_root)
    store = ResearchStore(data_root)
    payload = apply_provenance_correction(store, repo_root=repo_root)
    _assert_no_path_leak(payload, str(data_root), str(repo_root))
    return emit(payload)


def cmd_backfill(
    packet_path: Path,
    *,
    persist: bool,
    repo_root: Path,
    explicit_data_root: Path | None,
) -> int:
    packet = _load_json_file(packet_path)
    store = None
    if persist:
        data_root = _store_root(repo_root, explicit_data_root)
        store = ResearchStore(data_root)
        result = backfill_legacy(
            packet,
            persist=True,
            store=store,
            repo_root=repo_root,
        )
        _assert_no_path_leak(result, str(data_root), str(repo_root))
        return emit(result)
    result = backfill_legacy(packet, persist=False)
    return emit(result)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hypothesis_forge")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--data-root", type=Path, default=None)
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight = subparsers.add_parser("preflight")
    preflight.add_argument("--owner-focus", default="AUTO")
    preflight.add_argument("--format", choices=("json",), default="json")
    preflight.add_argument("--no-auto-commission", action="store_true")

    freeze = subparsers.add_parser("freeze")
    freeze.add_argument("--draft", type=Path, required=True)
    freeze.add_argument("--preflight-receipt", type=Path, required=True)
    freeze.add_argument("--next-action", type=Path, default=None)
    freeze.add_argument("--format", choices=("json",), default="json")

    prospects = subparsers.add_parser("prospects")
    prospects.add_argument("--trigger", required=True)
    prospects.add_argument("--max-results", type=int, default=3)
    prospects.add_argument("--format", choices=("json",), default="json")

    finalize = subparsers.add_parser("finalize")
    finalize.add_argument("--session-id", required=True)
    finalize.add_argument("--critic-result", type=Path, required=True)
    finalize.add_argument("--format", choices=("json",), default="json")

    revise = subparsers.add_parser("revise")
    revise.add_argument("--session-id", required=True)
    revise.add_argument("--draft", type=Path, required=True)
    revise.add_argument("--format", choices=("json",), default="json")

    classify_cmd = subparsers.add_parser("classify")
    classify_cmd.add_argument("--session-id", required=True)
    classify_cmd.add_argument("--experiment-spec", type=Path, required=True)
    classify_cmd.add_argument("--format", choices=("json",), default="json")

    show_session_cmd = subparsers.add_parser("show-session")
    show_session_cmd.add_argument("--session-id", default=None)
    show_session_cmd.add_argument("--search-key", default=None)
    show_session_cmd.add_argument("--format", choices=("json",), default="json")

    pending = subparsers.add_parser("pending")
    pending.add_argument("--search-key", required=True)
    pending.add_argument("--format", choices=("json",), default="json")

    prior = subparsers.add_parser("prior")
    prior.add_argument("--candidate", default=None)
    prior.add_argument("--query", default=None)
    prior.add_argument("--format", choices=("json",), default="json")

    backfill = subparsers.add_parser("backfill-legacy")
    backfill.add_argument("--packet", type=Path, required=True)
    backfill.add_argument("--persist", action="store_true")
    backfill.add_argument("--format", choices=("json",), default="json")

    prove = subparsers.add_parser("prove-runtime")
    prove.add_argument("--session-id", required=True)
    prove.add_argument("--format", choices=("json",), default="json")

    inventory = subparsers.add_parser(
        "inventory-placeholder-times",
        help="read-only counts of HFIC records with placeholder provenance times",
    )
    inventory.add_argument("--format", choices=("json",), default="json")

    correction = subparsers.add_parser(
        "apply-provenance-correction",
        help="append-only HFIC provenance-time correction; requires --confirm-append-only after merge phrase",
    )
    correction.add_argument("--format", choices=("json",), default="json")
    correction.add_argument(
        "--confirm-append-only",
        action="store_true",
        help="required; does not rewrite RDP bytes or recover an exact original time",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    repo_root = args.root.resolve()
    try:
        if args.command == "preflight":
            return cmd_preflight(
                repo_root,
                owner_focus=args.owner_focus,
                auto_commission=not args.no_auto_commission,
                explicit_data_root=args.data_root,
            )
        if args.command == "freeze":
            return cmd_freeze(
                repo_root,
                args.draft,
                args.preflight_receipt,
                args.data_root,
                next_action_path=getattr(args, "next_action", None),
            )
        if args.command == "prospects":
            return cmd_prospects(
                repo_root,
                trigger=args.trigger,
                max_results=args.max_results,
            )
        if args.command == "backfill-legacy":
            return cmd_backfill(
                args.packet,
                persist=bool(args.persist),
                repo_root=repo_root,
                explicit_data_root=args.data_root,
            )
        if args.command == "finalize":
            return cmd_finalize(
                repo_root,
                args.session_id,
                args.critic_result,
                args.data_root,
            )
        if args.command == "revise":
            return cmd_revise(
                repo_root,
                args.session_id,
                args.draft,
                args.data_root,
            )
        if args.command == "classify":
            return cmd_classify(
                repo_root,
                args.session_id,
                args.experiment_spec,
                args.data_root,
            )
        if args.command == "show-session":
            return cmd_show_session(
                repo_root,
                session_id=args.session_id,
                search_key=getattr(args, "search_key", None),
                explicit_data_root=args.data_root,
            )
        if args.command == "pending":
            return cmd_pending(
                repo_root,
                search_key=args.search_key,
                explicit_data_root=args.data_root,
            )
        if args.command == "prior":
            return cmd_prior(
                repo_root,
                candidate_raw=args.candidate,
                query=args.query,
                explicit_data_root=args.data_root,
            )
        if args.command == "prove-runtime":
            return cmd_prove_runtime(repo_root, args.session_id, args.data_root)
        if args.command == "inventory-placeholder-times":
            return cmd_inventory_placeholder_times(repo_root, args.data_root)
        if args.command == "apply-provenance-correction":
            return cmd_apply_provenance_correction(
                repo_root,
                args.data_root,
                confirm_append_only=bool(args.confirm_append_only),
            )
        raise HficCliError(f"HFIC_COMMAND_NOT_READY:{args.command}")
    except (HficCliError, HficSessionError, HficPreflightError, HficProspectError, DataRootError, ResearchStoreError) as exc:
        return emit_error(str(exc))
    except (OSError, ValueError, json.JSONDecodeError):
        return emit_error("HFIC_PROTOCOL_INVALID")


if __name__ == "__main__":
    sys.exit(main())
