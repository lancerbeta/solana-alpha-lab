"""Run the exact two-call, keyless TASK-30 A10 technical discriminator."""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import ssl
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from solana_alpha_lab.task30_gecko_interval_semantics import (  # noqa: E402
    INTERVAL_SECONDS,
    IntervalSemanticsError,
    build_request_plan,
    evaluate_interval_semantics,
)


CONFIG_PATH = ROOT / "configs" / "task30_gecko_interval_semantics_v1.yaml"
LOCAL_ROOT = ROOT / "local" / "task30_gecko_interval_semantics"
RESPONSE_BYTES_MAX = 4_194_304
SAFE_HEADERS = frozenset(
    {
        "content-length",
        "content-type",
        "date",
        "retry-after",
        "x-ratelimit-limit",
        "x-ratelimit-remaining",
        "x-ratelimit-reset",
    }
)


class RunnerError(RuntimeError):
    """The one-shot runner cannot operate inside its frozen envelope."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_: object, **__: object) -> urllib.request.Request:
        raise RunnerError("REDIRECT_FORBIDDEN")


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _load_policy(path: Path) -> dict[str, Any]:
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise RunnerError("POLICY_INVALID")
    return parsed


def _closed_boundary(now_epoch: int) -> int:
    if isinstance(now_epoch, bool) or not isinstance(now_epoch, int) or now_epoch <= INTERVAL_SECONDS:
        raise RunnerError("RUN_TIME_INVALID")
    boundary = now_epoch - (now_epoch % INTERVAL_SECONDS)
    if boundary <= INTERVAL_SECONDS:
        raise RunnerError("CLOSED_BOUNDARY_INVALID")
    return boundary


def dry_run(policy: Mapping[str, Any], *, now_epoch: int) -> dict[str, Any]:
    """Return the complete request plan without external I/O or output files."""

    before_timestamp = _closed_boundary(now_epoch)
    return {
        "atom_id": "T30-A10_GECKO_INTERVAL_SEMANTICS_DISCRIMINATOR_V1",
        "before_timestamp": before_timestamp,
        "network_calls": 0,
        "output_created": False,
        "plan": build_request_plan(policy, before_timestamp=before_timestamp),
    }


def _safe_headers(headers: object) -> dict[str, str]:
    if not hasattr(headers, "items"):
        return {}
    return {
        str(key).lower(): str(value)
        for key, value in headers.items()
        if str(key).lower() in SAFE_HEADERS
    }


class BoundedGeckoTransport:
    """One-use transport that can send only the two prevalidated GETs once."""

    def __init__(
        self,
        *,
        opener: Any | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._opener = opener or urllib.request.build_opener(_NoRedirect())
        self._now = now
        self._attempts = 0

    @property
    def attempts(self) -> int:
        return self._attempts

    def execute(self, plan: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        if len(plan) != 2 or self._attempts != 0:
            raise RunnerError("REQUEST_PLAN_CAP_INVALID")
        captures: list[dict[str, Any]] = []
        for request in plan:
            if request.get("method") != "GET" or request.get("host") != "api.geckoterminal.com":
                raise RunnerError("REQUEST_SCOPE_INVALID")
            url = request.get("url")
            if not isinstance(url, str) or not url.startswith("https://api.geckoterminal.com/api/v2/"):
                raise RunnerError("REQUEST_SCOPE_INVALID")
            self._attempts += 1
            sent_at = self._now()
            body = b""
            status: int | None = None
            headers: dict[str, str] = {}
            error_class: str | None = None
            stop_reason: str | None = None
            outgoing = urllib.request.Request(
                url,
                method="GET",
                headers={
                    "Accept": "application/json",
                    "User-Agent": "solana-alpha-lab-task30-a10/1.0",
                },
            )
            try:
                with self._opener.open(outgoing, timeout=20) as response:
                    status = int(response.status)
                    headers = _safe_headers(response.headers)
                    body = response.read(RESPONSE_BYTES_MAX + 1)
            except urllib.error.HTTPError as exc:
                status = int(exc.code)
                headers = _safe_headers(exc.headers)
                body = exc.read(RESPONSE_BYTES_MAX + 1)
                error_class = "HTTP_ERROR"
            except RunnerError:
                error_class = "REDIRECT_FORBIDDEN"
                stop_reason = "NO_REDIRECT"
            except (TimeoutError, socket.timeout):
                error_class = "TIMEOUT"
                stop_reason = "TRANSPORT_TIMEOUT"
            except (urllib.error.URLError, ssl.SSLError, socket.gaierror, ConnectionError, OSError):
                error_class = "DNS_TLS_OR_TRANSPORT_FAILURE"
                stop_reason = "TRANSPORT_FAILURE"
            received_at = self._now()
            if len(body) > RESPONSE_BYTES_MAX:
                stop_reason = "RESPONSE_BYTE_CAP_EXCEEDED"
            elif status != 200 and stop_reason is None:
                stop_reason = "HTTP_STATUS_NOT_200"
            captures.append(
                {
                    "request_id": request.get("request_id"),
                    "method": "GET",
                    "host": request.get("host"),
                    "path": request.get("path"),
                    "query": request.get("query"),
                    "requested_at": _utc_text(sent_at),
                    "received_at": _utc_text(received_at),
                    "http_status": status,
                    "body": body,
                    "response_bytes": len(body),
                    "raw_sha256": _sha256(body),
                    "safe_response_headers": headers,
                    "error_class": error_class,
                    "stop_reason": stop_reason,
                }
            )
        return captures


def _raw_root(path: Path) -> Path:
    candidate = path.resolve()
    permitted = (ROOT / "local").resolve()
    if not candidate.is_relative_to(permitted):
        raise RunnerError("RAW_ROOT_OUTSIDE_LOCAL_FORBIDDEN")
    return candidate


def _write_local_run(
    *,
    raw_root: Path,
    run_id: str,
    policy: Mapping[str, Any],
    before_timestamp: int,
    captures: Sequence[Mapping[str, Any]],
    result: Mapping[str, Any],
) -> Path:
    safe_run_id = run_id.replace(":", "").replace("+", "").replace(".", "")
    if not safe_run_id or "/" in safe_run_id or "\\" in safe_run_id:
        raise RunnerError("RUN_ID_INVALID")
    run_directory = _raw_root(raw_root) / f"run={safe_run_id}"
    run_directory.mkdir(parents=True, exist_ok=False)
    raw_directory = run_directory / "raw"
    raw_directory.mkdir()
    raw_files: list[dict[str, Any]] = []
    sanitized_reads: list[dict[str, Any]] = []
    for capture in captures:
        request_id = capture["request_id"]
        if not isinstance(request_id, str):
            raise RunnerError("REQUEST_ID_INVALID")
        filename = request_id.casefold() + ".json"
        body = capture["body"]
        if not isinstance(body, bytes):
            raise RunnerError("RESPONSE_BODY_INVALID")
        target = raw_directory / filename
        with target.open("xb") as handle:
            handle.write(body)
        raw_files.append(
            {
                "request_id": request_id,
                "relative_path": f"raw/{filename}",
                "sha256": _sha256(body),
                "bytes": len(body),
            }
        )
        sanitized_reads.append({key: value for key, value in capture.items() if key != "body"})
    manifest = {
        "schema": "smial.task30.gecko-interval-semantics.raw-manifest",
        "schema_version": "1.0",
        "run_id": safe_run_id,
        "before_timestamp": before_timestamp,
        "files": raw_files,
    }
    manifest_bytes = _canonical_json(manifest) + b"\n"
    with (run_directory / "raw_manifest_v1.json").open("xb") as handle:
        handle.write(manifest_bytes)
    local_receipt = {
        "schema": "smial.task30.gecko-interval-semantics.local-runtime-receipt",
        "schema_version": "1.0",
        "run_id": safe_run_id,
        "policy_sha256": _sha256(yaml.safe_dump(dict(policy), sort_keys=True).encode("utf-8")),
        "before_timestamp": before_timestamp,
        "provider_calls_attempted": len(captures),
        "reads": sanitized_reads,
        "raw_manifest": {
            "relative_path": "raw_manifest_v1.json",
            "sha256": _sha256(manifest_bytes),
            "bytes": len(manifest_bytes),
        },
        "result": dict(result),
        "side_effects": {
            "provider_api_calls": len(captures),
            "credentials": 0,
            "raw_artifacts_outside_git": len(raw_files) + 2,
            "scheduler_or_background_processes": 0,
            "r2_r3_reads": 0,
            "wallet_signer_transaction_actions": 0,
            "cash_spend_usd_cents": 0,
            "task30_trial_or_acceptance_actions": 0,
        },
    }
    with (run_directory / "local_runtime_receipt_v1.json").open("xb") as handle:
        handle.write(_canonical_json(local_receipt) + b"\n")
    return run_directory


def _decode_payload(capture: Mapping[str, Any]) -> Mapping[str, Any] | None:
    if capture.get("http_status") != 200 or capture.get("stop_reason") is not None:
        return None
    body = capture.get("body")
    if not isinstance(body, bytes):
        return None
    try:
        decoded = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return decoded if isinstance(decoded, Mapping) else None


def _result_from_captures(policy: Mapping[str, Any], captures: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_id = {capture.get("request_id"): capture for capture in captures}
    ohlcv = _decode_payload(by_id.get("OHLCV_15M", {}))
    trades = _decode_payload(by_id.get("POOL_TRADES", {}))
    if ohlcv is None or trades is None:
        return {
            "decision": "INCONCLUSIVE_EXTERNAL_RESPONSE_UNAVAILABLE",
            "selected_model": None,
            "claims": {
                "interval_label_semantics_only": False,
                "continuous_panel": False,
                "empty_interval_semantics": False,
                "historical_panel": False,
                "pit_admissible": False,
                "h07_h01_evidence": False,
                "task30_trial": False,
                "execution": False,
                "numeric_netreturn": False,
            },
        }
    try:
        return evaluate_interval_semantics(policy, ohlcv, trades)
    except IntervalSemanticsError as exc:
        return {
            "decision": "INCONCLUSIVE_INVALID_RUNTIME_EVIDENCE",
            "selected_model": None,
            "error_code": str(exc),
            "claims": {
                "interval_label_semantics_only": False,
                "continuous_panel": False,
                "empty_interval_semantics": False,
                "historical_panel": False,
                "pit_admissible": False,
                "h07_h01_evidence": False,
                "task30_trial": False,
                "execution": False,
                "numeric_netreturn": False,
            },
        }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="send the two bounded GET requests")
    parser.add_argument("--dry-run", action="store_true", help="print the zero-I/O request plan")
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--raw-root", type=Path, default=LOCAL_ROOT)
    args = parser.parse_args(argv)
    if args.execute == args.dry_run:
        parser.error("choose exactly one of --dry-run or --execute")
    policy = _load_policy(args.config)
    now = datetime.now(UTC)
    plan_result = dry_run(policy, now_epoch=int(now.timestamp()))
    if args.dry_run:
        print(json.dumps(plan_result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    transport = BoundedGeckoTransport()
    captures = transport.execute(plan_result["plan"])
    result = _result_from_captures(policy, captures)
    run_directory = _write_local_run(
        raw_root=args.raw_root,
        run_id=now.strftime("t30a10-%Y%m%dT%H%M%SZ"),
        policy=policy,
        before_timestamp=plan_result["before_timestamp"],
        captures=captures,
        result=result,
    )
    print(
        json.dumps(
            {
                "provider_calls_attempted": transport.attempts,
                "decision": result["decision"],
                "local_run_relative_path": run_directory.relative_to(ROOT).as_posix(),
                "state_change": "NONE",
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
