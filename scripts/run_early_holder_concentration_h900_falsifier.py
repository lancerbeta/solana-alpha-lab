#!/usr/bin/env python3
"""Run one foreground EARLY holder-concentration H900 window after owner authorization."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.early_holder_concentration_h900_falsifier import (  # noqa: E402
    ATOM_ID,
    AUTHORITY_PHRASE,
    CLOSE_TERMINAL,
    EARN_TERMINAL,
    RECEIPT_SCHEMA,
    run_holder_concentration_campaign,
    validate_holder_concentration_policy,
)
from solana_alpha_lab.ordinary_recent_organic_pressure_h900_audition import (  # noqa: E402
    OrganicPressureError,
    _format_utc,
)
from solana_alpha_lab.quote_native_evidence_channel_qualification import (  # noqa: E402
    QualificationError,
    load_process_credential,
)
from solana_alpha_lab.pmf_quote_slice_one_shot import credential_free_preflight  # noqa: E402


CONFIG_PATH = ROOT / "configs/early_holder_concentration_h900_falsifier_v1.yaml"
RAW_ROOT = ROOT / "local/early_holder_concentration_h900_falsifier"
EVIDENCE_ROOT = ROOT / "docs/evidence/early_holder_concentration_h900_falsifier"
TYPED_STOP_TERMINALS = {
    "API_KEY_IN_URL_LOG_RECEIPT_OR_GIT",
    "RAW_BODY_CONTAINS_CREDENTIAL",
    "CALL_CAP_EXCEEDED",
    "CREDENTIAL_READ_BEFORE_ATTEMPT_RESERVATION",
    "CREDENTIAL_READ_BEFORE_CREDENTIAL_FREE_PREFLIGHT",
}


def canonical_json(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def capture_envelope(*, observation_id: str, observed_at: str, body_sha256: str) -> dict[str, str]:
    payload = {
        "body_sha256": body_sha256,
        "observation_id": observation_id,
        "observed_at": observed_at,
        "schema": "smial.early-holder-concentration-h900-falsifier.capture-envelope",
        "schema_version": "1.0",
    }
    return {**payload, "envelope_sha256": hashlib.sha256(canonical_json(payload)).hexdigest()}


def attempt_reservation_document(*, started_at: str, policy_sha256: str) -> dict[str, object]:
    payload = {
        "atom_id": ATOM_ID,
        "credential_reads": 0,
        "policy_sha256": policy_sha256,
        "provider_requests": 0,
        "schema": "smial.early-holder-concentration-h900-falsifier.attempt-reservation",
        "schema_version": "1.0",
        "started_at": started_at,
        "state": "STARTED",
        "window": "ONE",
    }
    return {**payload, "reservation_sha256": hashlib.sha256(canonical_json(payload)).hexdigest()}


def _write_create_only(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(payload)
    except FileExistsError as exc:
        raise OrganicPressureError("CREATE_ONLY_EXISTS") from exc


def _load_policy() -> dict[str, object]:
    loaded = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise OrganicPressureError("POLICY_INVALID")
    validate_holder_concentration_policy(loaded, root=ROOT)
    return loaded


def _parse_excluded_mints(raw: bytes) -> set[str]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OrganicPressureError("PRIOR_MINT_EXCLUSION_INPUT_INVALID") from exc
    values = payload.get("mints") if isinstance(payload, Mapping) else payload
    if not isinstance(values, list) or not values or not all(isinstance(value, str) and value for value in values):
        raise OrganicPressureError("PRIOR_MINT_EXCLUSION_INPUT_INVALID")
    return set(values)


def _safe_observation_stem(observation_id: str) -> str:
    candidate = observation_id.replace(":", "_")
    allowed = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-")
    if candidate and all(character in allowed for character in candidate):
        return candidate
    return hashlib.sha256(observation_id.encode("utf-8")).hexdigest()


def _terminal_from_error(exc: OrganicPressureError) -> str:
    code = str(exc)
    if code in TYPED_STOP_TERMINALS:
        return code
    return "INVALID_EVIDENCE_REPLAN"


def run_capture(
    *,
    authority_phrase: str,
    excluded_mints_path: Path,
    policy: Mapping[str, Any] | None = None,
    raw_root: Path = RAW_ROOT,
    receipt_path: Path | None = None,
    environ: Mapping[str, str] | None = None,
    credential_loader: Callable[[], str] | None = None,
    preflight_fn: Callable[..., Mapping[str, Any]] = credential_free_preflight,
    opener: object | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    sleeper: Callable[[float], None] = time.sleep,
    monotonic_clock: Callable[[], float] = time.monotonic,
) -> dict[str, object]:
    selected_policy = dict(policy or _load_policy())
    validate_holder_concentration_policy(selected_policy, root=ROOT)
    if authority_phrase != AUTHORITY_PHRASE:
        raise OrganicPressureError("AUTHORITY_PHRASE_INVALID")
    try:
        excluded_mints_bytes = excluded_mints_path.read_bytes()
    except OSError as exc:
        raise OrganicPressureError("PRIOR_MINT_EXCLUSION_INPUT_INVALID") from exc
    excluded_mints = _parse_excluded_mints(excluded_mints_bytes)
    excluded_mints_sha256 = hashlib.sha256(excluded_mints_bytes).hexdigest()
    started_at = clock()
    policy_sha256 = hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest()
    reservation = attempt_reservation_document(
        started_at=_format_utc(started_at),
        policy_sha256=policy_sha256,
    )
    raw_root.mkdir(parents=True, exist_ok=True)
    reservation_path = raw_root / "campaign_reservation.json"
    _write_create_only(
        reservation_path,
        canonical_json({key: value for key, value in reservation.items() if key != "reservation_sha256"}),
    )
    raw_directory = raw_root / f"run={_format_utc(started_at).replace('-', '').replace(':', '')}"
    manifests: list[dict[str, object]] = []
    credential_reads = 0
    credential_value: str | None = None

    def raw_sink(observation_id: str, body: bytes, observed_at: str) -> None:
        raw_directory.mkdir(parents=True, exist_ok=True)
        body_sha256 = hashlib.sha256(body).hexdigest()
        envelope = capture_envelope(
            observation_id=observation_id,
            observed_at=observed_at,
            body_sha256=body_sha256,
        )
        stem = _safe_observation_stem(observation_id)
        body_path = raw_directory / f"{stem}.body"
        envelope_path = raw_directory / f"{stem}.envelope.json"
        _write_create_only(body_path, body)
        _write_create_only(
            envelope_path,
            canonical_json({key: value for key, value in envelope.items() if key != "envelope_sha256"}),
        )
        manifests.append(
            {
                "observation_id": observation_id,
                "path": body_path.relative_to(raw_root).as_posix(),
                "envelope_path": envelope_path.relative_to(raw_root).as_posix(),
                "bytes": len(body),
                "sha256": body_sha256,
                "observed_at": observed_at,
                "capture_envelope_sha256": envelope["envelope_sha256"],
                "retention": "A4_OUTSIDE_GIT",
            }
        )

    def load_credential() -> str:
        nonlocal credential_reads, credential_value
        if not reservation_path.is_file():
            raise OrganicPressureError("CREDENTIAL_READ_BEFORE_ATTEMPT_RESERVATION")
        credential_reads += 1
        if credential_loader is not None:
            credential_value = credential_loader()
            return credential_value
        environment = os.environ if environ is None else environ
        credential_value = load_process_credential(environment)
        return credential_value

    try:
        receipt = run_holder_concentration_campaign(
            selected_policy,
            authority_phrase=authority_phrase,
            reservation=reservation,
            excluded_mints=excluded_mints,
            credential_loader=load_credential,
            preflight_fn=preflight_fn,
            opener=opener,
            clock=clock,
            sleeper=sleeper,
            monotonic_clock=monotonic_clock,
            raw_sink=raw_sink,
        )
    except (OrganicPressureError, QualificationError) as exc:
        receipt = {
            "schema": RECEIPT_SCHEMA,
            "schema_version": "1.0",
            "atom_id": ATOM_ID,
            "terminal_outcome": _terminal_from_error(exc),
            "terminal_error_code": str(exc),
            "credential_reads": credential_reads,
            "provider_requests": getattr(exc, "provider_requests", 0) or 0,
            "retries": 0,
            "fallbacks": 0,
            "execute_calls": 0,
            "observations": [],
            "non_claims": ["NO_EXECUTE", "NO_TAKER_OR_SIGNER", "NO_ALPHA", "NO_NETRETURN"],
        }
    receipt["receipt_id"] = "EVIDENCE-EARLY-HOLDER-CONCENTRATION-H900-RUNTIME-001"
    receipt["attempt_reservation"] = reservation
    receipt["prior_mints_sha256"] = excluded_mints_sha256
    receipt["raw_retention"] = {"mode": "A4_OUTSIDE_GIT", "manifests": manifests}
    receipt["credential_reads"] = credential_reads
    encoded = canonical_json(receipt)
    if credential_value and credential_value.encode("utf-8") in encoded:
        raise OrganicPressureError("API_KEY_IN_URL_LOG_RECEIPT_OR_GIT")
    target = receipt_path or (EVIDENCE_ROOT / "a1_runtime_receipt_v1.json")
    _write_create_only(target, encoded)
    return receipt


def _owner_next_for_error(code: str) -> str:
    if code == "CREATE_ONLY_EXISTS":
        return (
            "ONE_WINDOW_ALREADY_RESERVED_DO_NOT_RESTART; "
            "read the existing reservation or wait for the live run to finish; "
            "do not Ctrl+C a 300s+H900 wait and rerun"
        )
    if code == "AUTHORITY_PHRASE_INVALID":
        return "PASTE_EXACT_FROZEN_PHRASE_AS_SINGLE_QUOTED_POWERSHELL_STRING"
    if code == "PRIOR_MINT_EXCLUSION_INPUT_INVALID":
        return "SUPPLY_NONEMPTY_JSON_OBJECT_WITH_MINTS_ARRAY_OF_PRIOR_CONSUMED_MINTS"
    if code == "JUPITER_API_KEY_MISSING_OR_EMPTY":
        return "SET_JUPITER_API_KEY_IN_PROCESS_ENVIRONMENT_ONLY_THEN_ONE_WINDOW"
    return "INVALID_EVIDENCE_REPLAN_DO_NOT_RETRY_THE_SAME_RESERVATION"


def _owner_next_for_terminal(terminal: str) -> str:
    if terminal == "CLOSE_HOLDER_CONCENTRATION_FAMILY":
        return "FAMILY_CLOSED_NO_RESCUE_NO_SHADOW"
    if terminal == "EARN_ONE_CONFIRMATORY_FRESH_OOS":
        return "STOP_AND_RETURN_TO_OWNER_NO_AUTOMATIC_OOS_NEW_ORCHESTRATION_CODE_EQUALS_ZERO"
    return "INVALID_EVIDENCE_REPLAN_DISTINGUISH_DATA_VS_RUNTIME_NO_AUTOMATIC_RETRY"


def owner_exit_blocked(terminal: str) -> bool:
    return terminal not in {CLOSE_TERMINAL, EARN_TERMINAL}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Scientific terminals: CLOSE_HOLDER_CONCENTRATION_FAMILY | "
            "INVALID_EVIDENCE_REPLAN | EARN_ONE_CONFIRMATORY_FRESH_OOS.\n"
            "excluded-mints-file: non-empty JSON {\"mints\":[\"...\"]} of prior consumed "
            "mints, kept outside Git.\n"
            "JUPITER_API_KEY must already be in the process environment; never .env.\n"
            "PowerShell: pass --owner-phrase as a single-quoted string so $0 and ; do not expand.\n"
            "One window only. After reservation the process waits ~300s then ~900s with no progress output. "
            "Do not restart; a second start is CREATE_ONLY_EXISTS."
        ),
    )
    parser.add_argument(
        "--owner-phrase",
        required=True,
        help="Exact frozen owner phrase; single-quoted on PowerShell.",
    )
    parser.add_argument(
        "--excluded-mints-file",
        required=True,
        type=Path,
        help="JSON {\"mints\":[...]} of prior consumed mints, outside Git.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        receipt = run_capture(
            authority_phrase=args.owner_phrase,
            excluded_mints_path=args.excluded_mints_file,
        )
    except (OrganicPressureError, QualificationError) as exc:
        code = str(exc)
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": code,
                    "owner_state": "BLOCKED",
                    "terminal_outcome": "INVALID_EVIDENCE_REPLAN",
                    "next": _owner_next_for_error(code),
                },
                ensure_ascii=False,
            )
        )
        return 2
    terminal = str(receipt.get("terminal_outcome") or "INVALID_EVIDENCE_REPLAN")
    error_code = str(receipt.get("terminal_error_code") or "")
    blocked = owner_exit_blocked(terminal)
    print(
        json.dumps(
            {
                "ok": not blocked,
                "owner_state": "BLOCKED" if blocked else "DONE",
                "terminal_outcome": terminal,
                "next": (
                    _owner_next_for_error(error_code)
                    if error_code
                    else _owner_next_for_terminal(terminal)
                ),
                "receipt": receipt,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 2 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
