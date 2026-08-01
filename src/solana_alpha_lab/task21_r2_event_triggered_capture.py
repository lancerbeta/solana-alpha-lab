"""Bounded event-triggered R2 source and P0 capture for TASK-21."""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

import yaml

from solana_alpha_lab.jupiter_quote_logger import (
    DEFAULT_SLIPPAGE_BPS,
    PROVIDER,
    PROVIDER_VERSION,
    QuoteProjection,
    build_buy_panel_requests,
    decide_dependent_sell,
    project_quote_observation,
)
from solana_alpha_lab.jupiter_quote_transport import (
    EXTERNAL_AUTHORITY_PHRASE as JUPITER_AUTHORITY,
    BoundedQuoteTransport,
    ExternalExecutionGate as JupiterExecutionGate,
    HttpCapture,
)
from solana_alpha_lab.task21_event_triggered_final_cohort import (
    Task21FinalCohortError,
    evaluate_nomination_observation,
    evaluate_panel_trigger,
    initial_runtime_state,
    validate_protected_inputs as validate_final_cohort_inputs,
)
from solana_alpha_lab.task21_live_shakedown import (
    Task21LiveShakedownError,
    validate_recovery_freshness,
)
from solana_alpha_lab.task21_multi_horizon_capture import (
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
)
from solana_alpha_lab.task21_real_nomination_source import (
    DEXSCREENER_URL,
    SOLANA_RPC_URL,
    StructuralCandidate,
    select_profile_mints,
    validate_rpc_mints,
)


TASK_ID = "TASK-21"
ATOM_ID = "T21-A6S_R2_EVENT_TRIGGERED_SOURCE_AND_P0_CAPTURE_V1"
SCHEMA_VERSION = "1.0"
OUTPUT_RELATIVE_ROOT = "local/task21_forward/final_cohort/r2"
SOURCE_CALLS_MAX = 2
JUPITER_CALLS_MAX = 24
EXTERNAL_CALLS_MAX = 26
MEMBERS_MAX = 3
DURABLE_BYTES_MAX = 16_777_216
MIN_FREE_SPACE_AFTER_WRITE = 2_147_483_648
WALL_SECONDS_MAX = 300
MINIMUM_INTERVAL_SECONDS = 2.2
JUPITER_RECEIVED_BYTES_PER_PANEL_MAX = 3_145_728
HYPOTHESIS_ID = "HYP-VERSION-EXECUTION-CAPACITY-CURVATURE-V1"


class Task21R2Error(RuntimeError):
    """R2 cannot proceed without violating its frozen boundary."""


class Task21R2AuthorityRequired(Task21R2Error):
    """The exact R2 external authority phrase is absent."""


@dataclass(frozen=True, slots=True)
class Task21R2ExecutionGate:
    authority_phrase: str

    def __post_init__(self) -> None:
        if self.authority_phrase != ATOM_ID:
            raise Task21R2AuthorityRequired("task21_r2_authority_phrase_mismatch")


@dataclass(frozen=True, slots=True)
class SourceHttpCapture:
    request_kind: str
    method: str
    url: str
    request_body: bytes
    status: int | None
    response_body: bytes
    requested_at: datetime
    response_at: datetime
    error_class: str | None
    stop_reason: str | None

    def raw_envelope(self) -> dict[str, Any]:
        return {
            "request_kind": self.request_kind,
            "method": self.method,
            "url": self.url,
            "request_bytes": len(self.request_body),
            "request_sha256": sha256_bytes(self.request_body),
            "request_body_base64": base64.b64encode(self.request_body).decode("ascii"),
            "status": self.status,
            "response_bytes": len(self.response_body),
            "response_sha256": sha256_bytes(self.response_body),
            "response_body_base64": base64.b64encode(self.response_body).decode("ascii"),
            "requested_at": _utc_text(self.requested_at),
            "response_at": _utc_text(self.response_at),
            "error_class": self.error_class,
            "stop_reason": self.stop_reason,
        }


class SourceTransport(Protocol):
    @property
    def attempts(self) -> int: ...

    @property
    def received_bytes(self) -> int: ...

    def execute(
        self,
        *,
        request_kind: str,
        method: str,
        url: str,
        request_body: bytes,
        response_bytes_max: int,
    ) -> SourceHttpCapture: ...


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        raise Task21R2Error("source_redirect_forbidden")


class BoundedSourceTransport:
    """Sequential, zero-retry transport for the two exact public source calls."""

    def __init__(
        self,
        *,
        opener: Any | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._opener = opener or urllib.request.build_opener(_NoRedirectHandler())
        self._now = now
        self._attempts = 0
        self._received_bytes = 0

    @property
    def attempts(self) -> int:
        return self._attempts

    @property
    def received_bytes(self) -> int:
        return self._received_bytes

    def execute(
        self,
        *,
        request_kind: str,
        method: str,
        url: str,
        request_body: bytes,
        response_bytes_max: int,
    ) -> SourceHttpCapture:
        if self._attempts >= SOURCE_CALLS_MAX:
            raise Task21R2Error("source_call_cap_exhausted")
        parsed = urllib.parse.urlsplit(url)
        allowed = {
            ("api.dexscreener.com", "/token-profiles/latest/v1", "GET"),
            ("api.mainnet-beta.solana.com", "", "POST"),
        }
        if (
            parsed.scheme != "https"
            or parsed.port is not None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or (parsed.hostname, parsed.path, method) not in allowed
        ):
            raise Task21R2Error("source_request_scope_drift")
        if response_bytes_max <= 0:
            raise Task21R2Error("source_response_cap_invalid")
        self._attempts += 1
        requested_at = self._now()
        outgoing = urllib.request.Request(
            url,
            data=request_body if method == "POST" else None,
            method=method,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "solana-alpha-lab-task21-r2/1.0",
            },
        )
        status: int | None = None
        response_body = b""
        error_class: str | None = None
        stop_reason: str | None = None
        try:
            with self._opener.open(outgoing, timeout=20) as response:
                status = int(response.status)
                response_body = response.read(response_bytes_max + 1)
        except urllib.error.HTTPError as exc:
            status = int(exc.code)
            response_body = exc.read(response_bytes_max + 1)
            error_class = "HTTP_ERROR"
        except Task21R2Error:
            raise
        except (TimeoutError, socket.timeout):
            error_class = "TIMEOUT"
            stop_reason = "SOURCE_TIMEOUT"
        except (
            urllib.error.URLError,
            ssl.SSLError,
            socket.gaierror,
            ConnectionError,
            OSError,
        ):
            error_class = "DNS_TLS_OR_TRANSPORT_FAILURE"
            stop_reason = "SOURCE_TRANSPORT_FAILURE"
        response_at = self._now()
        self._received_bytes += len(response_body)
        if len(response_body) > response_bytes_max:
            stop_reason = "SOURCE_RESPONSE_BYTE_CAP_EXHAUSTED"
        elif status != 200:
            stop_reason = "SOURCE_HTTP_STATUS_NOT_200"
        return SourceHttpCapture(
            request_kind=request_kind,
            method=method,
            url=url,
            request_body=request_body,
            status=status,
            response_body=response_body,
            requested_at=requested_at,
            response_at=response_at,
            error_class=error_class,
            stop_reason=stop_reason,
        )


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Task21R2Error("config_root_invalid")
    return value


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Task21R2Error("json_root_invalid")
    return value


def _utc(name: str, value: object) -> datetime:
    if not isinstance(value, str):
        raise Task21R2Error(f"{name}_must_be_text")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Task21R2Error(f"{name}_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise Task21R2Error(f"{name}_must_be_timezone_aware")
    return parsed.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise Task21R2Error("datetime_must_be_timezone_aware")
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _write_new(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise Task21R2Error("r2_create_only_collision") from exc


def _json_document(name: str, payload: bytes) -> object:
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Task21R2Error(f"{name}_invalid_json") from exc


def _rpc_request_bytes(mints: Sequence[str]) -> bytes:
    return canonical_json_bytes(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getMultipleAccounts",
            "params": [
                list(mints),
                {
                    "commitment": "finalized",
                    "encoding": "base64",
                    "dataSlice": {"offset": 0, "length": 82},
                },
            ],
        }
    )


def _directory_bytes(root: Path) -> int:
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def _inventory(root: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]


def validate_config(config: Mapping[str, Any], repo_root: Path) -> None:
    if (
        config.get("schema") != "smial.task21_r2_event_triggered_source_p0"
        or config.get("schema_version") != SCHEMA_VERSION
        or config.get("task_id") != TASK_ID
        or config.get("atom_id") != ATOM_ID
        or config.get("status")
        != "FROZEN_FOR_EXACT_USER_AUTHORIZED_R2_EXECUTION"
    ):
        raise Task21R2Error("r2_config_identity_drift")
    protected = config.get("protected_inputs")
    if not isinstance(protected, list) or len(protected) != 4:
        raise Task21R2Error("r2_protected_inputs_drift")
    root = repo_root.resolve()
    for item in protected:
        relative = item.get("path") if isinstance(item, Mapping) else None
        expected = item.get("sha256") if isinstance(item, Mapping) else None
        if (
            not isinstance(relative, str)
            or not isinstance(expected, str)
            or re.fullmatch(r"[0-9a-f]{64}", expected) is None
        ):
            raise Task21R2Error("r2_protected_input_identity_invalid")
        path = (root / relative).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise Task21R2Error("r2_protected_input_outside_repo") from exc
        if not path.is_file() or sha256_file(path) != expected:
            raise Task21R2Error(f"r2_protected_input_hash_drift:{item.get('role')}")
    source = config.get("source", {})
    profile = source.get("profile_endpoint", {})
    rpc = source.get("mint_validation_rpc", {})
    selection = source.get("selection", {})
    if (
        source.get("authentication") != "NONE"
        or profile.get("url") != DEXSCREENER_URL
        or profile.get("method") != "GET"
        or profile.get("response_rows_max") != 200
        or profile.get("response_bytes_max") != 2_097_152
        or rpc.get("url") != SOLANA_RPC_URL
        or rpc.get("method") != "getMultipleAccounts"
        or rpc.get("data_slice") != {"offset": 0, "length": 82}
        or rpc.get("account_count_max") != 100
        or rpc.get("response_bytes_max") != 6_291_456
        or selection.get("rpc_candidate_mints_max") != 100
        or selection.get("structural_candidates_max") != 100
        or selection.get("outcome_or_route_inputs_allowed") is not False
    ):
        raise Task21R2Error("r2_source_contract_drift")
    cohort = config.get("cohort", {})
    if (
        cohort.get("batch_id") != "T21-R2"
        or cohort.get("nomination_cap") != MEMBERS_MAX
        or cohort.get("admission_cap") != MEMBERS_MAX
        or len(cohort.get("prior_seen_mints", [])) != 3
    ):
        raise Task21R2Error("r2_cohort_contract_drift")
    p0 = config.get("p0", {})
    if (
        p0.get("horizon_id") != "P0"
        or p0.get("notionals_usd") != [10, 25, 50, 100]
        or p0.get("provider_calls_per_panel_max") != 8
        or p0.get("provider_calls_total_max") != JUPITER_CALLS_MAX
        or p0.get("endpoint") != "https://api.jup.ag/swap/v1/quote"
        or p0.get("authentication") != "NONE"
        or p0.get("retries") != 0
        or p0.get("concurrency") != 1
    ):
        raise Task21R2Error("r2_p0_contract_drift")
    budget = config.get("budget", {})
    caps = budget.get("whole_task_caps", {})
    used = budget.get("used_before_r2", {})
    atom_caps = budget.get("this_atom_caps", {})
    if (
        caps.get("external_requests") != 192
        or caps.get("source_requests") != 8
        or caps.get("quote_requests") != 184
        or used.get("external_requests") != 60
        or used.get("source_requests") != 4
        or used.get("quote_requests") != 56
        or atom_caps
        != {
            "external_requests": 26,
            "source_requests": 2,
            "quote_requests": 24,
            "durable_local_bytes": DURABLE_BYTES_MAX,
        }
        or used["external_requests"] + atom_caps["external_requests"]
        > caps["external_requests"]
    ):
        raise Task21R2Error("r2_budget_contract_drift")
    authority = config.get("authority", {})
    expected = {
        "exact_phrase": ATOM_ID,
        "provider_api_rpc_wss_calls_max": EXTERNAL_CALLS_MAX,
        "dexscreener_calls_max": 1,
        "solana_public_rpc_calls_max": 1,
        "jupiter_calls_max": JUPITER_CALLS_MAX,
        "nominations_max": MEMBERS_MAX,
        "admissions_max": MEMBERS_MAX,
        "durable_local_bytes_max": DURABLE_BYTES_MAX,
        "retries": 0,
        "concurrency": 1,
        "drive_reads": 0,
        "drive_writes": 0,
        "credentials": 0,
        "cash_spend_usd_cents": 0,
        "scheduler_or_background_process": False,
        "deploy": False,
        "catalog_mutation": False,
        "source_mutation": False,
        "wallet_signer_transaction_actions": 0,
        "destructive_actions": False,
        "merge": False,
    }
    if any(authority.get(key) != value for key, value in expected.items()):
        raise Task21R2Error("r2_authority_boundary_drift")


def _source_helper_config(config: Mapping[str, Any]) -> dict[str, Any]:
    source = config["source"]
    return {
        "source": {
            "profile_endpoint": source["profile_endpoint"],
        },
        "selection": {
            "rpc_candidate_mints_max": source["selection"]["rpc_candidate_mints_max"],
            "target_nomination_count": source["selection"]["structural_candidates_max"],
            "allowed_token_programs": source["selection"]["allowed_token_programs"],
        },
    }


def _candidate_event(
    *, candidate: StructuralCandidate, source_hash: str, observed_at: str
) -> dict[str, Any]:
    identity = sha256_bytes(
        canonical_json_bytes({"mint": candidate.mint, "source": source_hash})
    )[:20]
    return {
        "nomination_event_id": f"T21-R2-NOM-{identity}",
        "mint": candidate.mint,
        "mint_decimals": candidate.mint_decimals,
        "eligible": True,
        "observed_at": observed_at,
        "first_reliable_available_at": observed_at,
        "exact_rule_input_values": {
            "source_class": "PREDECLARED_CONTROL_COHORT",
            "structural_mint_initialized": True,
            "token_program": candidate.token_program,
            "prior_relevant_quote_outcome_exposure": False,
            "uses_task21_quote_route_or_price_outcome": False,
        },
    }


def _projection_envelope(
    projection: QuoteProjection,
    *,
    member: Mapping[str, Any],
    window_id: str,
    ordinal: int,
) -> dict[str, Any]:
    quote = projection.quote_attempt
    raw = projection.raw_event
    enum = lambda value: getattr(value, "value", str(value))
    return {
        "schema": "smial.task21.forward-quote-panel-raw",
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "hypothesis_version_id": HYPOTHESIS_ID,
        "batch_id": "T21-R2",
        "member_id": member["member_id"],
        "nomination_event_id": member["nomination_event_id"],
        "horizon_id": "P0",
        "window_id": window_id,
        "call_ordinal": ordinal,
        "provider": PROVIDER,
        "provider_version": PROVIDER_VERSION,
        "request_hash": quote.request_hash,
        "idempotency_key": quote.idempotency_key,
        "raw_content_sha256": raw.content_sha256,
        "requested_at": _utc_text(quote.requested_at),
        "response_at": None if quote.response_at is None else _utc_text(quote.response_at),
        "first_reliable_available_at": _utc_text(quote.first_reliable_available_at),
        "available_to_strategy_at": _utc_text(quote.available_to_strategy_at),
        "ingested_at": _utc_text(quote.ingested_at),
        "latency_ms": quote.provider_latency_ms,
        "response_status": enum(raw.response_status),
        "terminal_class": enum(quote.status),
        "error_class": quote.error_class,
        "route_id": quote.route_id,
        "route_count": quote.route_count,
        "context_slot": quote.context_slot,
        "stop_reason": projection.stop_reason,
        "raw_event": raw.model_dump(mode="json"),
        "quote_attempt": quote.model_dump(mode="json"),
    }


def _capture_member_p0(
    *,
    run_root: Path,
    config_hash: str,
    member: Mapping[str, Any],
    transport: Any,
    now: Callable[[], datetime],
    clock: Callable[[], float],
) -> dict[str, Any]:
    started = clock()
    triggered_at = _utc_text(now())
    projections: list[QuoteProjection] = []
    terminal_counts: Counter[str] = Counter()
    buy_attempts = 0
    sell_attempts = 0
    sell_not_attempted = 0
    stop_reason: str | None = None
    for index, buy_request in enumerate(
        build_buy_panel_requests(
            selected_output_mint=member["mint"],
            output_decimals=member["mint_decimals"],
            slippage_bps=DEFAULT_SLIPPAGE_BPS,
        )
    ):
        if clock() - started >= WALL_SECONDS_MAX:
            stop_reason = "WALL_TIME_CAP_EXHAUSTED"
            break
        buy_capture: HttpCapture = transport.execute(buy_request)
        buy_attempts += 1
        buy_projection = project_quote_observation(buy_request, buy_capture.observation)
        projections.append(buy_projection)
        terminal_counts[getattr(buy_projection.quote_attempt.status, "value", str(buy_projection.quote_attempt.status))] += 1
        stop_reason = buy_capture.transport_stop_reason or buy_projection.stop_reason
        if stop_reason is not None:
            break
        sell = decide_dependent_sell(buy_projection, attempt_ordinal=5 + index)
        if sell.request is None:
            sell_not_attempted += 1
            continue
        sell_capture: HttpCapture = transport.execute(sell.request)
        sell_attempts += 1
        sell_projection = project_quote_observation(sell.request, sell_capture.observation)
        projections.append(sell_projection)
        terminal_counts[getattr(sell_projection.quote_attempt.status, "value", str(sell_projection.quote_attempt.status))] += 1
        stop_reason = sell_capture.transport_stop_reason or sell_projection.stop_reason
        if stop_reason is not None:
            break
    if transport.attempts > 8:
        raise Task21R2Error("r2_p0_panel_call_cap_exceeded")
    if not projections:
        raise Task21R2Error("r2_p0_panel_has_no_evidence")
    member_id = member["member_id"]
    window_id = f"{member_id}-P0"
    window_root = run_root / f"member={member_id}" / "horizon=P0"
    envelopes = [
        _projection_envelope(
            projection,
            member=member,
            window_id=window_id,
            ordinal=ordinal,
        )
        for ordinal, projection in enumerate(projections, start=1)
    ]
    raw_bytes = b"".join(canonical_json_bytes(item) + b"\n" for item in envelopes)
    manifest = {
        "schema": "smial.task21.forward-quote-panel-manifest",
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "batch_id": "T21-R2",
        "horizon_id": "P0",
        "config_sha256": config_hash,
        "member_id": member_id,
        "nomination_event_id": member["nomination_event_id"],
        "provider": PROVIDER,
        "provider_version": PROVIDER_VERSION,
        "triggered_at": triggered_at,
        "files": [{"logical_path": "raw_events.jsonl", "bytes": len(raw_bytes), "sha256": sha256_bytes(raw_bytes)}],
    }
    manifest_bytes = canonical_json_bytes(manifest) + b"\n"
    completed_at = _utc_text(now())
    receipt = {
        "schema": "smial.task21.forward-quote-panel-receipt",
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "batch_id": "T21-R2",
        "horizon_id": "P0",
        "window_id": window_id,
        "member_id": member_id,
        "nomination_event_id": member["nomination_event_id"],
        "status": "COMPLETE" if stop_reason is None else "STOPPED",
        "stop_reason": stop_reason,
        "triggered_at": triggered_at,
        "completed_at": completed_at,
        "provider_calls": transport.attempts,
        "modeled_provider_credits": transport.attempts,
        "provider_billed_credit_claim": "NOT_AVAILABLE_KEYLESS_NO_ACCOUNT",
        "received_bytes": transport.received_bytes,
        "buy_attempts": buy_attempts,
        "sell_attempts": sell_attempts,
        "sell_not_attempted": sell_not_attempted,
        "terminal_counts": dict(sorted(terminal_counts.items())),
        "raw_events_sha256": sha256_bytes(raw_bytes),
        "manifest_sha256": sha256_bytes(manifest_bytes),
        "cash_spend_usd_cents": 0,
        "credentials_used": 0,
        "wallet_signer_transaction_actions": 0,
    }
    receipt_bytes = canonical_json_bytes(receipt) + b"\n"
    if (
        _directory_bytes(run_root)
        + len(raw_bytes)
        + len(manifest_bytes)
        + len(receipt_bytes)
        > DURABLE_BYTES_MAX
    ):
        raise Task21R2Error("r2_durable_byte_cap_would_be_exceeded")
    raw_path = window_root / "raw_events.jsonl"
    manifest_path = window_root / "manifest.json"
    _write_new(raw_path, raw_bytes)
    _write_new(manifest_path, manifest_bytes)
    receipt_path = window_root / "receipt.json"
    _write_new(receipt_path, receipt_bytes)
    return {
        **receipt,
        "stored_bytes": _directory_bytes(window_root),
        "receipt_sha256": sha256_file(receipt_path),
    }


def _finalize_local_receipt(
    *, run_root: Path, receipt: dict[str, Any], output_override: bool
) -> dict[str, Any]:
    receipt_path = run_root / "runtime_receipt.json"
    receipt_bytes = canonical_json_bytes(receipt) + b"\n"
    if _directory_bytes(run_root) + len(receipt_bytes) > DURABLE_BYTES_MAX:
        raise Task21R2Error("r2_durable_byte_cap_would_be_exceeded")
    _write_new(receipt_path, receipt_bytes)
    stored = _directory_bytes(run_root)
    if stored > DURABLE_BYTES_MAX:
        raise Task21R2Error("r2_durable_byte_cap_exceeded")
    result = dict(receipt)
    result["local_evidence"] = {
        "root": (
            f"TEST_OUTPUT_ROOT/{run_root.name}"
            if output_override
            else run_root.relative_to(run_root.parents[4]).as_posix()
        ),
        "stored_bytes": stored,
        "runtime_receipt_sha256": sha256_file(receipt_path),
        "files": _inventory(run_root),
        "tracked_in_git": False,
        "create_only": True,
    }
    return result


def run_r2_source_p0_capture(
    *,
    gate: Task21R2ExecutionGate | None,
    repo_root: Path,
    config_path: Path,
    source_transport: SourceTransport | None = None,
    quote_transport_factory: Callable[[Mapping[str, Any]], Any] | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
    available_disk_bytes: int | None = None,
    output_root_override: Path | None = None,
) -> dict[str, Any]:
    """Execute the exact R2 source sequence and immediate P0 panels."""

    if not isinstance(gate, Task21R2ExecutionGate):
        raise Task21R2AuthorityRequired("task21_r2_execution_gate_required")
    config = _load_yaml(config_path)
    validate_config(config, repo_root)
    event_config_path = repo_root / config["protected_inputs"][0]["path"]
    event_config = _load_yaml(event_config_path)
    try:
        validate_final_cohort_inputs(repo_root=repo_root, config=event_config)
    except Task21FinalCohortError as exc:
        raise Task21R2Error(str(exc)) from exc
    started_at = now()
    if started_at.tzinfo is None or started_at.utcoffset() is None:
        raise Task21R2Error("runtime_now_must_be_timezone_aware")
    started_at = started_at.astimezone(UTC)
    recovery_path = repo_root / config["protected_inputs"][3]["path"]
    recovery = _load_json(recovery_path)
    try:
        validate_recovery_freshness(recovery, now=started_at)
    except Task21LiveShakedownError as exc:
        raise Task21R2Error(str(exc)) from exc
    free_bytes = available_disk_bytes or shutil.disk_usage(repo_root).free
    if free_bytes - DURABLE_BYTES_MAX < MIN_FREE_SPACE_AFTER_WRITE:
        raise Task21R2Error("r2_disk_pressure")
    if output_root_override is not None and (
        source_transport is None or quote_transport_factory is None
    ):
        raise Task21R2Error("output_override_requires_injected_transports")
    output_root = (
        output_root_override.resolve()
        if output_root_override is not None
        else (repo_root / OUTPUT_RELATIVE_ROOT).resolve()
    )
    claim = {
        "atom_id": ATOM_ID,
        "config_sha256": sha256_file(config_path),
        "started_at": _utc_text(started_at),
    }
    run_id = "r2-" + started_at.strftime("%Y%m%dT%H%M%S%fZ") + "-" + sha256_bytes(canonical_json_bytes(claim))[:12]
    run_root = output_root / f"run={run_id}"
    if run_root.exists():
        raise Task21R2Error("r2_run_output_already_exists")
    transport = source_transport or BoundedSourceTransport(now=now)
    profile_cfg = config["source"]["profile_endpoint"]
    profile_capture = transport.execute(
        request_kind="DEXSCREENER_LATEST_TOKEN_PROFILES",
        method="GET",
        url=profile_cfg["url"],
        request_body=b"",
        response_bytes_max=profile_cfg["response_bytes_max"],
    )
    captures = [profile_capture]
    requested_mints: list[str] = []
    structural: list[StructuralCandidate] = []
    rpc_slot: int | None = None
    if profile_capture.stop_reason is None:
        profiles = _json_document("dexscreener_response", profile_capture.response_body)
        helper_config = _source_helper_config(config)
        requested_mints = select_profile_mints(
            profile_document=profiles,
            config=helper_config,
        )
        if requested_mints:
            rpc_cfg = config["source"]["mint_validation_rpc"]
            rpc_capture = transport.execute(
                request_kind="SOLANA_GET_MULTIPLE_ACCOUNTS",
                method="POST",
                url=rpc_cfg["url"],
                request_body=_rpc_request_bytes(requested_mints),
                response_bytes_max=rpc_cfg["response_bytes_max"],
            )
            captures.append(rpc_capture)
            if rpc_capture.stop_reason is None:
                structural, rpc_slot = validate_rpc_mints(
                    rpc_document=_json_document("solana_rpc_response", rpc_capture.response_body),
                    requested_mints=requested_mints,
                    config=helper_config,
                )
    observed_at = _utc_text(max(item.response_at for item in captures))
    content_identity = {
        "source_version": config["source"]["source_version"],
        "captures": [
            {
                "request_kind": item.request_kind,
                "request_sha256": sha256_bytes(item.request_body),
                "status": item.status,
                "response_sha256": sha256_bytes(item.response_body),
            }
            for item in captures
        ],
        "requested_mints": requested_mints,
        "rpc_context_slot": rpc_slot,
    }
    source_hash = sha256_bytes(canonical_json_bytes(content_identity))
    source_id = "T21-R2-SOURCE-" + sha256_bytes(
        canonical_json_bytes({"content": source_hash, "observed_at": observed_at})
    )[:20]
    source_partition = {
        "schema": "smial.task21.r2-source-partition",
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "run_id": run_id,
        "batch_id": "T21-R2",
        "source_observation_id": source_id,
        "source_content_identity": content_identity,
        "source_content_sha256": source_hash,
        "observed_at": observed_at,
        "captures": [item.raw_envelope() for item in captures],
        "contains_secrets": False,
    }
    source_path = run_root / "source" / "source_partition.json"
    source_bytes = canonical_json_bytes(source_partition) + b"\n"
    if len(source_bytes) > DURABLE_BYTES_MAX:
        raise Task21R2Error("r2_source_partition_would_exceed_durable_cap")
    _write_new(source_path, source_bytes)
    base_actions = {
        "provider_api_rpc_wss_calls": transport.attempts,
        "dexscreener_calls": sum(item.request_kind.startswith("DEXSCREENER") for item in captures),
        "solana_public_rpc_calls": sum(item.request_kind.startswith("SOLANA") for item in captures),
        "jupiter_calls": 0,
        "modeled_provider_credits": 0,
        "received_bytes": transport.received_bytes,
        "nominations": 0,
        "admissions": 0,
        "cash_spend_usd_cents": 0,
        "credentials_used": 0,
        "drive_reads": 0,
        "drive_writes": 0,
        "scheduler_or_background_process": False,
        "wallet_signer_transaction_actions": 0,
    }
    source_stop = next((item.stop_reason for item in captures if item.stop_reason), None)
    unseen = [
        item for item in structural
        if item.mint not in set(config["cohort"]["prior_seen_mints"])
    ][:MEMBERS_MAX]
    if source_stop is not None or not requested_mints or not unseen:
        reason = source_stop or (
            "NO_SOURCE_MINT_IDENTITIES" if not requested_mints
            else "NO_PREVIOUSLY_UNSEEN_ELIGIBLE_MINT"
        )
        receipt = {
            "schema": "smial.task21.r2-source-p0-runtime-receipt",
            "schema_version": SCHEMA_VERSION,
            "task_id": TASK_ID,
            "atom_id": ATOM_ID,
            "run_id": run_id,
            "status": "STOPPED_NO_ADMISSION",
            "stop_reason": reason,
            "started_at": _utc_text(started_at),
            "source": {
                "source_observation_id": source_id,
                "source_content_sha256": source_hash,
                "observed_at": observed_at,
                "rpc_context_slot": rpc_slot,
                "requested_mints": len(requested_mints),
                "structurally_valid_mints": len(structural),
                "unseen_eligible_mints": len(unseen),
                "partition_sha256": sha256_file(source_path),
            },
            "admission": {"candidate_states": [], "members": []},
            "p0": {"panels_complete": 0, "panels_stopped": 0, "windows": []},
            "actual_actions": base_actions,
            "next_boundary": {"status": "R2_REVIEW_REQUIRED", "external_authority_granted": False},
            "non_claims": ["NO_TRADE_OR_SWAP", "NO_ALPHA_PNL_OR_MARKET_WIDE_CLAIM", "NO_CATALOG_OR_SOURCE_MUTATION"],
        }
        return _finalize_local_receipt(
            run_root=run_root,
            receipt=receipt,
            output_override=output_root_override is not None,
        )
    candidates = [
        _candidate_event(candidate=item, source_hash=source_hash, observed_at=observed_at)
        for item in unseen
    ]
    candidates.sort(
        key=lambda item: (
            _utc("candidate_available", item["first_reliable_available_at"]),
            _utc("candidate_observed", item["observed_at"]),
            item["nomination_event_id"],
            item["mint"],
        )
    )
    observation = {
        "batch_id": "T21-R2",
        "source_calls": transport.attempts,
        "source_observation_id": source_id,
        "source_content_sha256": source_hash,
        "observed_at": observed_at,
        "candidates": candidates,
    }
    admitted_at = _utc_text(now())
    try:
        admission = evaluate_nomination_observation(
            config=event_config,
            state=initial_runtime_state(event_config),
            observation=observation,
            admitted_at=admitted_at,
        )
    except Task21FinalCohortError as exc:
        raise Task21R2Error(str(exc)) from exc
    members = [dict(item, hypothesis_version_id=HYPOTHESIS_ID) for item in admission["members"]]
    nomination_path = run_root / "admission" / "nomination_events.jsonl"
    admission_path = run_root / "admission" / "admission_events.jsonl"
    nomination_bytes = b"".join(canonical_json_bytes(item) + b"\n" for item in candidates)
    admission_bytes = b"".join(canonical_json_bytes(item) + b"\n" for item in members)
    if _directory_bytes(run_root) + len(nomination_bytes) + len(admission_bytes) > DURABLE_BYTES_MAX:
        raise Task21R2Error("r2_admission_evidence_would_exceed_durable_cap")
    _write_new(nomination_path, nomination_bytes)
    _write_new(admission_path, admission_bytes)
    admission_receipt = {
        "schema": "smial.task21.r2-admission-receipt",
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "batch_id": "T21-R2",
        "status": admission["status"],
        "admitted_at": admitted_at,
        "source_observation_id": source_id,
        "source_content_sha256": source_hash,
        "candidate_states": admission["candidate_states"],
        "member_ids": [item["member_id"] for item in members],
        "nomination_events_sha256": sha256_file(nomination_path),
        "admission_events_sha256": sha256_file(admission_path),
        "provider_calls_before_admission_persisted": transport.attempts,
        "jupiter_calls_before_admission_persisted": 0,
        "outcome_or_route_input_used": False,
    }
    admission_receipt_path = run_root / "admission" / "receipt.json"
    admission_receipt_bytes = canonical_json_bytes(admission_receipt) + b"\n"
    if _directory_bytes(run_root) + len(admission_receipt_bytes) > DURABLE_BYTES_MAX:
        raise Task21R2Error("r2_admission_receipt_would_exceed_durable_cap")
    _write_new(admission_receipt_path, admission_receipt_bytes)
    base_actions["nominations"] = len(candidates)
    base_actions["admissions"] = len(members)
    windows: list[dict[str, Any]] = []
    started_clock = clock()
    for index, member in enumerate(members):
        if index:
            sleeper(MINIMUM_INTERVAL_SECONDS)
        if clock() - started_clock >= WALL_SECONDS_MAX:
            break
        if (
            config["budget"]["used_before_r2"]["response_bytes"]
            + base_actions["received_bytes"]
            + JUPITER_RECEIVED_BYTES_PER_PANEL_MAX
            > config["budget"]["whole_task_caps"]["response_bytes"]
        ):
            break
        current_stored = _directory_bytes(repo_root / "local/task21_forward")
        trigger = evaluate_panel_trigger(
            config=event_config,
            member=member,
            panel_history=[],
            requested_panel="P0",
            now=_utc_text(now()),
            recovery_health="HEALTHY",
            response_bytes_used=config["budget"]["used_before_r2"]["response_bytes"] + base_actions["received_bytes"],
            stored_bytes_used=current_stored,
            dataset_bytes_used=config["budget"]["used_before_r2"]["dataset_bytes"] + _directory_bytes(run_root),
            free_disk_bytes=free_bytes,
            remaining_reserved_provider_calls=len(members) * 24,
        )
        if trigger["status"] != "READY_FOR_SEPARATE_EXTERNAL_AUTHORITY":
            break
        quote_transport = (
            quote_transport_factory(member)
            if quote_transport_factory is not None
            else BoundedQuoteTransport(gate=JupiterExecutionGate(JUPITER_AUTHORITY))
        )
        window = _capture_member_p0(
            run_root=run_root,
            config_hash=sha256_file(config_path),
            member=member,
            transport=quote_transport,
            now=now,
            clock=clock,
        )
        windows.append(window)
        base_actions["jupiter_calls"] += int(window["provider_calls"])
        base_actions["modeled_provider_credits"] += int(window["provider_calls"])
        base_actions["received_bytes"] += int(window["received_bytes"])
        if window["status"] != "COMPLETE":
            break
    base_actions["provider_api_rpc_wss_calls"] = transport.attempts + base_actions["jupiter_calls"]
    if base_actions["provider_api_rpc_wss_calls"] > EXTERNAL_CALLS_MAX:
        raise Task21R2Error("r2_external_call_cap_exceeded")
    if base_actions["jupiter_calls"] > JUPITER_CALLS_MAX:
        raise Task21R2Error("r2_jupiter_call_cap_exceeded")
    complete = len(windows) == len(members) and all(item["status"] == "COMPLETE" for item in windows)
    stop_reason = None
    if not complete:
        stop_reason = (
            next((item["stop_reason"] for item in windows if item["stop_reason"]), None)
            or "P0_POPULATION_INCOMPLETE"
        )
    receipt = {
        "schema": "smial.task21.r2-source-p0-runtime-receipt",
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "run_id": run_id,
        "status": "PASS" if complete else "STOPPED",
        "stop_reason": stop_reason,
        "started_at": _utc_text(started_at),
        "source": {
            "source_observation_id": source_id,
            "source_content_sha256": source_hash,
            "observed_at": observed_at,
            "rpc_context_slot": rpc_slot,
            "requested_mints": len(requested_mints),
            "structurally_valid_mints": len(structural),
            "unseen_eligible_mints": len(unseen),
            "partition_sha256": sha256_file(source_path),
        },
        "admission": {
            "candidate_states": admission["candidate_states"],
            "member_ids": [item["member_id"] for item in members],
            "receipt_sha256": sha256_file(admission_receipt_path),
            "persisted_before_first_jupiter_call": True,
            "outcome_or_route_input_used": False,
        },
        "p0": {
            "panels_complete": sum(item["status"] == "COMPLETE" for item in windows),
            "panels_stopped": sum(item["status"] != "COMPLETE" for item in windows),
            "windows": windows,
        },
        "actual_actions": base_actions,
        "budget_after_r2": {
            "external_requests": config["budget"]["used_before_r2"]["external_requests"] + base_actions["provider_api_rpc_wss_calls"],
            "source_requests": config["budget"]["used_before_r2"]["source_requests"] + transport.attempts,
            "quote_requests": config["budget"]["used_before_r2"]["quote_requests"] + base_actions["jupiter_calls"],
            "response_bytes": config["budget"]["used_before_r2"]["response_bytes"] + base_actions["received_bytes"],
        },
        "next_boundary": {
            "status": "P1_EVENT_TRIGGER_READY_AFTER_MINIMUM_SEPARATION" if complete else "R2_REVIEW_REQUIRED",
            "atom_id": "T21-A6S_R2_P1_EVENT_TRIGGERED_FOREGROUND_CAPTURE_V1" if complete else None,
            "member_not_before": [
                {
                    "member_id": item["member_id"],
                    "not_before_at": _utc_text(_utc("completed_at", item["completed_at"]) + timedelta(seconds=1801)),
                }
                for item in windows if item["status"] == "COMPLETE"
            ],
            "external_authority_granted": False,
        },
        "non_claims": [
            "NO_TRADE_OR_SWAP_EXECUTED",
            "NO_FILL_POSITION_PNL_OR_ALPHA_CLAIM",
            "NO_MARKET_WIDE_OR_CROSS_REGIME_CLAIM",
            "NO_DRIVE_CATALOG_SOURCE_OR_DEPLOY_ACTION",
            "NO_TASK22_OR_A7_AUTHORITY",
        ],
    }
    return _finalize_local_receipt(
        run_root=run_root,
        receipt=receipt,
        output_override=output_root_override is not None,
    )
