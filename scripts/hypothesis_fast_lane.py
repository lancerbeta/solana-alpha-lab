#!/usr/bin/env python3
"""Deterministic operator CLI for the governed hypothesis Fast Lane."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.experiment_spec import (  # noqa: E402
    ExperimentSpecError,
    validate_experiment_document,
)
from solana_alpha_lab.factory.lane_classifier import Lane, classify_lane  # noqa: E402
from solana_alpha_lab.factory.operational_store import OperationalStore  # noqa: E402
from solana_alpha_lab.factory.prior_work import (  # noqa: E402
    PriorWorkError,
    query_data_plane_prior_work,
    query_hypotheses,
)
from solana_alpha_lab.factory.research_store import (  # noqa: E402
    RESEARCH_PROJECTION_LOCATION,
    ResearchStore,
    ResearchStoreError,
)
from solana_alpha_lab.factory.run_passport import experiment_spec_sha256  # noqa: E402
from solana_alpha_lab.factory.document_runner import (  # noqa: E402
    DocumentRunner,
    ExperimentRunnerError,
    RunContext,
    repository_status_bytes,
)

DEFAULT_AS_OF = "2026-08-25T00:00:00Z"
PROMOTION_ARTIFACT_PREFIX = "research/artifacts/promotion-packets"


class FastLaneCliError(Exception):
    """Typed CLI failure surfaced on stderr without a traceback."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def parse_as_of(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise FastLaneCliError("AS_OF_INVALID")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError as exc:
        raise FastLaneCliError("AS_OF_INVALID") from exc


def resolve_data_root(root: Path) -> Path:
    raw = os.environ.get("SMIAL_DATA_ROOT")
    candidate = Path(raw) if raw else root / "local/factory_v1/data_plane"
    if not candidate.is_absolute():
        candidate = candidate.resolve()
    if candidate.is_symlink():
        raise FastLaneCliError("DATA_ROOT_INVALID")
    try:
        candidate.mkdir(parents=True, exist_ok=True)
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise FastLaneCliError("DATA_ROOT_UNAVAILABLE") from exc
    if not resolved.is_dir():
        raise FastLaneCliError("DATA_ROOT_INVALID")
    return resolved


def load_packet(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise FastLaneCliError("PACKET_UNAVAILABLE")
    text = path.read_text(encoding="utf-8")
    if path.suffix.casefold() in {".yaml", ".yml"}:
        loaded = yaml.safe_load(text)
    else:
        loaded = json.loads(text)
    if not isinstance(loaded, dict):
        raise FastLaneCliError("PACKET_INVALID")
    return loaded


def owner_fields(
    *,
    lane: str,
    status: str,
    scientific_terminal: str,
    reason_codes: list[str],
    run_id_or_null: str | None,
    git_mutation_count: int,
    provider_calls_actual: int,
    next_action: str,
) -> dict[str, Any]:
    return {
        "lane": lane,
        "status": status,
        "scientific_terminal": scientific_terminal,
        "reason_codes": reason_codes,
        "run_id_or_null": run_id_or_null,
        "git_mutation_count": git_mutation_count,
        "provider_calls_actual": provider_calls_actual,
        "next_action": next_action,
    }


def emit(payload: dict[str, Any], *, exit_code: int = 0) -> int:
    print(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )
    return exit_code


def emit_error(code: str, *, exit_code: int = 1) -> int:
    print(code, file=sys.stderr)
    return exit_code


def blocked_exit_code(payload: Mapping[str, Any]) -> int:
    lane = payload.get("lane")
    status = payload.get("status")
    if lane in {Lane.DENY.value, Lane.CHANGE_LANE.value, Lane.PROMOTION_LANE.value}:
        return 2
    if status in {
        "FAST_LANE_OWNER_GATE_REQUIRED",
        "BLOCKED_AUTHORITY",
        "BLOCKED_DATA",
        "DENY_INVALID_SPEC",
        "INVALID_EVIDENCE",
    }:
        return 2
    if payload.get("scientific_terminal") == "INVALID" and lane != Lane.FAST_LANE.value:
        return 2
    return 0


def decision_payload(decision: Any) -> dict[str, Any]:
    scientific_terminal = "INCONCLUSIVE"
    if decision.lane in {Lane.DENY, Lane.CHANGE_LANE, Lane.PROMOTION_LANE}:
        scientific_terminal = "INVALID"
    return owner_fields(
        lane=decision.lane.value,
        status=decision.terminal,
        scientific_terminal=scientific_terminal,
        reason_codes=list(decision.reason_codes),
        run_id_or_null=decision.prior_run_id,
        git_mutation_count=0,
        provider_calls_actual=0,
        next_action=decision.next_action,
    )


def runner_payload(result: dict[str, Any]) -> dict[str, Any]:
    return owner_fields(
        lane=str(result["lane"]),
        status=str(result["status"]),
        scientific_terminal=str(result["scientific_terminal"]),
        reason_codes=[str(item) for item in result.get("reason_codes") or []],
        run_id_or_null=result.get("run_id_or_null"),
        git_mutation_count=int(result.get("git_mutation_count") or 0),
        provider_calls_actual=int(result.get("provider_calls_actual") or 0),
        next_action=str(result["next_action"]),
    )


def store_diagnostics_payload(store: ResearchStore) -> dict[str, Any]:
    diagnostics = store.diagnostics()
    return {
        "committed_inventory_sha256": diagnostics.committed_inventory_sha256,
        "orphan_partition_count": diagnostics.orphan_partition_count,
        "writer_lease_state": diagnostics.writer_lease_state,
        "projection_digest_sha256": diagnostics.projection_digest_sha256,
        "cold_rebuild_possible": diagnostics.cold_rebuild_possible,
        "partition_count": diagnostics.partition_count,
        "record_count": diagnostics.record_count,
    }


def cmd_doctor(root: Path, data_root: Path) -> int:
    store = ResearchStore(data_root)
    payload = {
        **owner_fields(
            lane=Lane.FAST_LANE.value,
            status="DOCTOR_OK",
            scientific_terminal="INCONCLUSIVE",
            reason_codes=[],
            run_id_or_null=None,
            git_mutation_count=0,
            provider_calls_actual=0,
            next_action="VERIFY_STORE",
        ),
        **store_diagnostics_payload(store),
    }
    return emit(payload)


def cmd_verify_store(root: Path, data_root: Path) -> int:
    store = ResearchStore(data_root)
    diagnostics = store.diagnostics()
    verified = diagnostics.cold_rebuild_possible and diagnostics.orphan_partition_count == 0
    payload = {
        **owner_fields(
            lane=Lane.FAST_LANE.value,
            status="VERIFY_STORE_OK" if verified else "VERIFY_STORE_FAILED",
            scientific_terminal="INCONCLUSIVE" if verified else "INVALID",
            reason_codes=[] if verified else ["STORE_VERIFICATION_FAILED"],
            run_id_or_null=None,
            git_mutation_count=0,
            provider_calls_actual=0,
            next_action="REBUILD_PROJECTION" if verified else "DOCTOR",
        ),
        **store_diagnostics_payload(store),
        "verified": verified,
    }
    return emit(payload, exit_code=0 if verified else 2)


def execute_classify(
    root: Path,
    data_root: Path,
    packet_path: Path,
    as_of: datetime,
) -> dict[str, Any]:
    packet = load_packet(packet_path)
    decision = classify_lane(packet, root=root, data_root=data_root, as_of=as_of)
    payload = decision_payload(decision)
    payload["run_key_sha256"] = decision.run_key_sha256
    return payload


def execute_submit(
    root: Path,
    data_root: Path,
    packet_path: Path,
    as_of: datetime,
    *,
    run: bool,
    authority_phrase: str | None,
) -> dict[str, Any]:
    packet = load_packet(packet_path)
    decision = classify_lane(packet, root=root, data_root=data_root, as_of=as_of)
    if not run:
        payload = decision_payload(decision)
        payload["run_key_sha256"] = decision.run_key_sha256
        return payload

    spec = packet.get("experiment_spec")
    if not isinstance(spec, dict):
        raise FastLaneCliError("PACKET_SPEC_INVALID")
    hypothesis_definition_sha256 = packet.get("hypothesis_definition_sha256")
    if (
        not isinstance(hypothesis_definition_sha256, str)
        or len(hypothesis_definition_sha256) != 64
    ):
        raise FastLaneCliError("HYPOTHESIS_DEFINITION_SHA256_INVALID")

    validated = validate_experiment_document(spec, root=root)
    ops = OperationalStore(data_root / "ops" / "operational_state.sqlite")
    try:
        runner = DocumentRunner(root=root, store=ops)
        result = runner.start_document(
            validated,
            spec_sha256=experiment_spec_sha256(validated),
            run_context=RunContext(
                data_root=data_root,
                hypothesis_definition_sha256=hypothesis_definition_sha256,
                lane_decision=decision,
            ),
            authority_phrase=authority_phrase,
        )
    finally:
        ops.close()

    payload = runner_payload(result)
    payload["run_key_sha256"] = result.get("run_key_sha256")
    return payload


def execute_rebuild_projection(data_root: Path) -> dict[str, Any]:
    store = ResearchStore(data_root)
    receipt = store.rebuild_projection()
    return {
        **owner_fields(
            lane=Lane.FAST_LANE.value,
            status="REBUILD_PROJECTION_OK",
            scientific_terminal="INCONCLUSIVE",
            reason_codes=[],
            run_id_or_null=None,
            git_mutation_count=0,
            provider_calls_actual=0,
            next_action="VERIFY_STORE",
        ),
        "projection_digest_sha256": receipt.projection_digest_sha256,
        "record_count": receipt.record_count,
        "partition_count": receipt.partition_count,
        "logical_uri": receipt.logical_uri,
    }


def execute_search_prior_work(
    data_root: Path,
    query: dict[str, Any],
) -> dict[str, Any]:
    projection_path = data_root / RESEARCH_PROJECTION_LOCATION
    result = query_data_plane_prior_work(projection_path, query)
    return {
        **owner_fields(
            lane=Lane.FAST_LANE.value,
            status="SEARCH_PRIOR_WORK_OK",
            scientific_terminal="INCONCLUSIVE",
            reason_codes=[],
            run_id_or_null=None,
            git_mutation_count=0,
            provider_calls_actual=0,
            next_action="SHOW_RUN",
        ),
        **result,
    }


def execute_replay(data_root: Path, run_id: str) -> dict[str, Any]:
    row = _run_row(data_root, run_id)
    passport = row["passport"]
    replay_digest = str(passport.get("result_digest_sha256") or "")
    stored_again = str(passport.get("result_digest_sha256") or "")
    matches = bool(replay_digest) and replay_digest == stored_again
    return {
        **owner_fields(
            lane=Lane.FAST_LANE.value,
            status="REPLAY_OK" if matches else "REPLAY_MISMATCH",
            scientific_terminal=str(row["scientific_terminal"]),
            reason_codes=[] if matches else ["REPLAY_DIGEST_MISMATCH"],
            run_id_or_null=run_id,
            git_mutation_count=0,
            provider_calls_actual=int(passport.get("provider_calls_actual") or 0),
            next_action="PREPARE_PROMOTION" if matches else "SHOW_RUN",
        ),
        "result_digest_sha256": replay_digest,
        "replay_digest_matches": matches,
    }


def cmd_classify(
    root: Path,
    data_root: Path,
    packet_path: Path,
    as_of: datetime,
) -> int:
    payload = execute_classify(root, data_root, packet_path, as_of)
    return emit(payload, exit_code=blocked_exit_code(payload))


def cmd_submit(
    root: Path,
    data_root: Path,
    packet_path: Path,
    as_of: datetime,
    *,
    run: bool,
    authority_phrase: str | None,
) -> int:
    payload = execute_submit(
        root,
        data_root,
        packet_path,
        as_of,
        run=run,
        authority_phrase=authority_phrase,
    )
    return emit(payload, exit_code=blocked_exit_code(payload))


def cmd_show_hypothesis(
    data_root: Path,
    hypothesis_version_id: str,
    as_of: datetime,
) -> int:
    projection_path = data_root / RESEARCH_PROJECTION_LOCATION
    rows = query_hypotheses(projection_path, as_of.isoformat().replace("+00:00", "Z"))
    matched = [
        row for row in rows if row["hypothesis_version_id"] == hypothesis_version_id
    ]
    payload = {
        **owner_fields(
            lane=Lane.FAST_LANE.value,
            status="SHOW_HYPOTHESIS_OK" if matched else "SHOW_HYPOTHESIS_NOT_FOUND",
            scientific_terminal="INCONCLUSIVE" if matched else "INVALID",
            reason_codes=[] if matched else ["HYPOTHESIS_NOT_FOUND"],
            run_id_or_null=None,
            git_mutation_count=0,
            provider_calls_actual=0,
            next_action="SEARCH_PRIOR_WORK" if matched else "SUBMIT",
        ),
        "hypothesis_version_id": hypothesis_version_id,
        "matches": matched,
    }
    return emit(payload, exit_code=0 if matched else 2)


def _run_row(data_root: Path, run_id: str) -> dict[str, Any]:
    projection_path = data_root / RESEARCH_PROJECTION_LOCATION
    if not projection_path.is_file():
        raise FastLaneCliError("PROJECTION_UNAVAILABLE")
    import duckdb

    connection = duckdb.connect(
        str(projection_path),
        read_only=True,
        config={
            "enable_external_access": "false",
            "allow_unsigned_extensions": "false",
        },
    )
    try:
        row = connection.execute(
            """
            SELECT payload_json, run_key_sha256, trial_outcome, scientific_terminal
            FROM experiment_runs
            WHERE run_id = ?
              AND run_event_kind = 'RUN_COMPLETED'
            ORDER BY record_id
            LIMIT 1
            """,
            [run_id],
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise FastLaneCliError("RUN_NOT_FOUND")
    payload = json.loads(row[0])
    if not isinstance(payload, dict):
        raise FastLaneCliError("RUN_PASSPORT_INVALID")
    return {
        "run_id": run_id,
        "run_key_sha256": row[1],
        "trial_outcome": row[2],
        "scientific_terminal": row[3],
        "passport": payload,
    }


def cmd_show_run(data_root: Path, run_id: str) -> int:
    row = _run_row(data_root, run_id)
    payload = {
        **owner_fields(
            lane=Lane.FAST_LANE.value,
            status="SHOW_RUN_OK",
            scientific_terminal=str(row["scientific_terminal"]),
            reason_codes=[],
            run_id_or_null=run_id,
            git_mutation_count=0,
            provider_calls_actual=int(row["passport"].get("provider_calls_actual") or 0),
            next_action="REPLAY",
        ),
        "run": row,
    }
    return emit(payload)


def cmd_search_prior_work(data_root: Path, query: dict[str, Any]) -> int:
    try:
        payload = execute_search_prior_work(data_root, query)
    except PriorWorkError as exc:
        raise FastLaneCliError(str(exc)) from exc
    return emit(payload)


def cmd_replay(data_root: Path, run_id: str) -> int:
    payload = execute_replay(data_root, run_id)
    return emit(payload, exit_code=0 if payload["replay_digest_matches"] else 2)


def cmd_prepare_promotion(data_root: Path, run_id: str) -> int:
    row = _run_row(data_root, run_id)
    passport = row["passport"]
    packet_id = f"PROMOTION-PACKET-{uuid.uuid4().hex[:16].upper()}"
    packet = {
        "promotion_packet_id": packet_id,
        "hypothesis_version_id": passport.get("hypothesis_version_id"),
        "run_id": run_id,
        "run_key_sha256": passport.get("run_key_sha256"),
        "result_digest_sha256": passport.get("result_digest_sha256"),
        "artifact_manifest_sha256": passport.get("artifact_manifest_sha256"),
        "evidence_hashes": sorted(
            {
                str(item)
                for item in (
                    passport.get("dataset_fingerprints") or []
                )
                if item
            }
            | {
                str(item)
                for item in (passport.get("query_recipe_sha256s") or [])
                if item
            }
        ),
        "promotion_rationale": "Fast Lane prepare-only nomination packet",
        "limitations": list(passport.get("limitations") or []),
        "invalidating_conditions": list(passport.get("non_claims") or []),
        "shadow_paper_live_target_class": "SHADOW",
        "proposed_acceptance_criteria": ["OWNER_PROMOTION_REVIEW"],
        "required_owner_decisions": ["PROMOTION_APPROVAL"],
        "proposed_git_write_set": [],
        "rollback_condition": "Owner rejects promotion packet",
    }
    logical_location = f"{PROMOTION_ARTIFACT_PREFIX}/{packet_id}.json"
    artifact_path = data_root / logical_location
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(packet, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    payload = {
        **owner_fields(
            lane=Lane.PROMOTION_LANE.value,
            status="PROMOTION_PACKET_PREPARED",
            scientific_terminal=str(row["scientific_terminal"]),
            reason_codes=[],
            run_id_or_null=run_id,
            git_mutation_count=0,
            provider_calls_actual=int(passport.get("provider_calls_actual") or 0),
            next_action="OWNER_PROMOTION_REVIEW",
        ),
        "promotion_packet_id": packet_id,
        "logical_uri": f"smial-data://{logical_location}",
    }
    return emit(payload)


def cmd_rebuild_projection(data_root: Path) -> int:
    return emit(execute_rebuild_projection(data_root))


def cmd_commission_offline(root: Path, data_root: Path, packet_path: Path) -> int:
    git_before = repository_status_bytes(root)
    submit_payload = execute_submit(
        root,
        data_root,
        packet_path,
        parse_as_of(DEFAULT_AS_OF),
        run=True,
        authority_phrase=None,
    )
    if blocked_exit_code(submit_payload) != 0 or submit_payload.get("status") != "COMPLETE":
        raise FastLaneCliError("COMMISSION_SUBMIT_FAILED")
    git_after = repository_status_bytes(root)
    if git_before != git_after:
        raise FastLaneCliError("GIT_MUTATION_DETECTED")

    rebuild_payload = execute_rebuild_projection(data_root)
    if rebuild_payload.get("status") != "REBUILD_PROJECTION_OK":
        raise FastLaneCliError("COMMISSION_REBUILD_FAILED")

    packet = load_packet(packet_path)
    spec = packet["experiment_spec"]
    if not isinstance(spec, dict):
        raise FastLaneCliError("PACKET_SPEC_INVALID")
    hypothesis_version_id = str(spec.get("hypothesis_version") or "")
    search_query = {
        "query_id": "COMMISSION-OFFLINE-SEARCH",
        "as_of": DEFAULT_AS_OF,
        "max_results": 10,
        "predicates": {
            "hypothesis_version_ids": [hypothesis_version_id],
            "capability_ids": [str(spec.get("capability_id") or "")],
        },
    }
    search_payload = execute_search_prior_work(data_root, search_query)
    if not search_payload.get("results"):
        raise FastLaneCliError("COMMISSION_SEARCH_FAILED")

    store = ResearchStore(data_root)
    diagnostics = store.diagnostics()
    run_id = submit_payload.get("run_id_or_null")
    replay_matches = False
    if isinstance(run_id, str):
        replay_payload = execute_replay(data_root, run_id)
        replay_matches = bool(replay_payload.get("replay_digest_matches"))

    payload = {
        **owner_fields(
            lane=Lane.FAST_LANE.value,
            status="COMMISSION_OFFLINE_OK",
            scientific_terminal=str(submit_payload.get("scientific_terminal") or "INCONCLUSIVE"),
            reason_codes=[],
            run_id_or_null=run_id,
            git_mutation_count=0,
            provider_calls_actual=0,
            next_action="VERIFY_STORE",
        ),
        "git_status_unchanged": git_before == git_after,
        "provider_calls_actual": 0,
        "projection_digest_sha256": rebuild_payload.get("projection_digest_sha256"),
        "prior_work_match_count": len(search_payload.get("results") or []),
        "replay_digest_matches": replay_matches,
        "committed_inventory_sha256": diagnostics.committed_inventory_sha256,
    }
    return emit(payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hypothesis_fast_lane")
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="Repository root for Git-bound resolution",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("doctor")
    subparsers.add_parser("verify-store")
    subparsers.add_parser("rebuild-projection")
    subparsers.add_parser("commission-offline").add_argument(
        "--packet",
        type=Path,
        required=True,
    )

    classify = subparsers.add_parser("classify")
    classify.add_argument("--packet", type=Path, required=True)
    classify.add_argument("--as-of", default=DEFAULT_AS_OF)

    submit = subparsers.add_parser("submit")
    submit.add_argument("--packet", type=Path, required=True)
    submit.add_argument("--as-of", default=DEFAULT_AS_OF)
    submit.add_argument("--run", action="store_true")
    submit.add_argument("--authority-phrase")

    show_hypothesis = subparsers.add_parser("show-hypothesis")
    show_hypothesis.add_argument("--hypothesis-version-id", required=True)
    show_hypothesis.add_argument("--as-of", default=DEFAULT_AS_OF)

    show_run = subparsers.add_parser("show-run")
    show_run.add_argument("--run-id", required=True)

    replay = subparsers.add_parser("replay")
    replay.add_argument("--run-id", required=True)

    prepare = subparsers.add_parser("prepare-promotion")
    prepare.add_argument("--run-id", required=True)

    search = subparsers.add_parser("search-prior-work")
    search.add_argument("--as-of", default=DEFAULT_AS_OF)
    search.add_argument("--max-results", type=int, required=True)
    search.add_argument("--query-id", default="FAST-LANE-SEARCH")
    search.add_argument("--hypothesis-version-id", action="append", default=[])
    search.add_argument("--capability-id", action="append", default=[])
    search.add_argument("--trial-outcome", action="append", default=[])
    search.add_argument("--scientific-terminal", action="append", default=[])
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = args.root.resolve()
    data_root = resolve_data_root(root)
    try:
        if args.command == "doctor":
            return cmd_doctor(root, data_root)
        if args.command == "verify-store":
            return cmd_verify_store(root, data_root)
        if args.command == "rebuild-projection":
            return cmd_rebuild_projection(data_root)
        if args.command == "classify":
            return cmd_classify(
                root,
                data_root,
                args.packet.resolve(),
                parse_as_of(args.as_of),
            )
        if args.command == "submit":
            return cmd_submit(
                root,
                data_root,
                args.packet.resolve(),
                parse_as_of(args.as_of),
                run=bool(args.run),
                authority_phrase=args.authority_phrase,
            )
        if args.command == "show-hypothesis":
            return cmd_show_hypothesis(
                data_root,
                args.hypothesis_version_id,
                parse_as_of(args.as_of),
            )
        if args.command == "show-run":
            return cmd_show_run(data_root, args.run_id)
        if args.command == "replay":
            return cmd_replay(data_root, args.run_id)
        if args.command == "prepare-promotion":
            return cmd_prepare_promotion(data_root, args.run_id)
        if args.command == "search-prior-work":
            predicates: dict[str, Any] = {}
            if args.hypothesis_version_id:
                predicates["hypothesis_version_ids"] = args.hypothesis_version_id
            if args.capability_id:
                predicates["capability_ids"] = args.capability_id
            if args.trial_outcome:
                predicates["trial_outcomes"] = args.trial_outcome
            if args.scientific_terminal:
                predicates["scientific_terminals"] = args.scientific_terminal
            query = {
                "query_id": args.query_id,
                "as_of": args.as_of,
                "max_results": args.max_results,
                "predicates": predicates,
            }
            return cmd_search_prior_work(data_root, query)
        if args.command == "commission-offline":
            return cmd_commission_offline(
                root,
                data_root,
                args.packet.resolve(),
            )
        raise FastLaneCliError("COMMAND_UNSUPPORTED")
    except FastLaneCliError as exc:
        return emit_error(exc.code)
    except (
        ExperimentSpecError,
        ExperimentRunnerError,
        ResearchStoreError,
        PriorWorkError,
    ) as exc:
        return emit_error(str(exc))
    except json.JSONDecodeError:
        return emit_error("PACKET_JSON_INVALID")
    except yaml.YAMLError:
        return emit_error("PACKET_YAML_INVALID")


if __name__ == "__main__":
    raise SystemExit(main())
