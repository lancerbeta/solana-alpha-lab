#!/usr/bin/env python3
"""Run one foreground ~30m seasoned H900 base-rate window after owner authorization."""

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

from solana_alpha_lab.seasoned_30m_h900_base_rate_probe import (  # noqa: E402
    AUTHORITY_PHRASE,
    ATOM_ID,
    INCONCLUSIVE_TERMINAL,
    INVALID_TERMINAL,
    NO_POSITIVE_MASS_TERMINAL,
    RECEIPT_SCHEMA,
    SHOWS_POSITIVE_MASS_TERMINAL,
    classify_campaign_failure,
    run_seasoned_base_rate_campaign,
    validate_seasoned_base_rate_policy,
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


CONFIG_PATH = ROOT / "configs/seasoned_30m_h900_base_rate_probe_v1.yaml"
SUCCESS_TERMINALS = {
    NO_POSITIVE_MASS_TERMINAL,
    SHOWS_POSITIVE_MASS_TERMINAL,
    INCONCLUSIVE_TERMINAL,
}
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
        "schema": "smial.seasoned-30m-h900-base-rate-probe.capture-envelope",
        "schema_version": "1.0",
    }
    return {**payload, "envelope_sha256": hashlib.sha256(canonical_json(payload)).hexdigest()}


def attempt_reservation_document(
    *, started_at: str, policy_sha256: str, atom_id: str
) -> dict[str, object]:
    payload = {
        "atom_id": atom_id,
        "credential_reads": 0,
        "policy_sha256": policy_sha256,
        "schema": "smial.seasoned-30m-h900-base-rate-probe.attempt-reservation",
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


def _load_policy(config_path: Path = CONFIG_PATH) -> dict[str, object]:
    loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise OrganicPressureError("POLICY_INVALID")
    validate_seasoned_base_rate_policy(loaded, root=ROOT)
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
    return INVALID_TERMINAL


def run_capture(
    *,
    authority_phrase: str,
    excluded_mints_path: Path,
    policy: Mapping[str, Any] | None = None,
    config_path: Path = CONFIG_PATH,
    raw_root: Path | None = None,
    receipt_path: Path | None = None,
    environ: Mapping[str, str] | None = None,
    credential_loader: Callable[[], str] | None = None,
    preflight_fn: Callable[..., Mapping[str, Any]] = credential_free_preflight,
    opener: object | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    sleeper: Callable[[float], None] = time.sleep,
    monotonic_clock: Callable[[], float] = time.monotonic,
) -> dict[str, object]:
    selected_policy = dict(policy or _load_policy(config_path))
    validate_seasoned_base_rate_policy(selected_policy, root=ROOT)
    if authority_phrase != AUTHORITY_PHRASE:
        raise OrganicPressureError("AUTHORITY_PHRASE_INVALID")
    selected_raw_root = raw_root if raw_root is not None else ROOT / "local/seasoned_30m_h900_base_rate_probe"
    try:
        excluded_mints_bytes = excluded_mints_path.read_bytes()
    except OSError as exc:
        raise OrganicPressureError("PRIOR_MINT_EXCLUSION_INPUT_INVALID") from exc
    excluded_mints = _parse_excluded_mints(excluded_mints_bytes)
    excluded_mints_sha256 = hashlib.sha256(excluded_mints_bytes).hexdigest()
    if credential_loader is None:
        environment = os.environ if environ is None else environ
        if not str(environment.get("JUPITER_API_KEY", "")).strip():
            raise OrganicPressureError("JUPITER_API_KEY_MISSING_OR_EMPTY")
    started_at = clock()
    policy_sha256 = hashlib.sha256(
        config_path.read_bytes() if policy is None else canonical_json(selected_policy)
    ).hexdigest()
    reservation = attempt_reservation_document(
        started_at=_format_utc(started_at),
        policy_sha256=policy_sha256,
        atom_id=ATOM_ID,
    )
    selected_raw_root.mkdir(parents=True, exist_ok=True)
    reservation_path = selected_raw_root / "campaign_reservation.json"
    _write_create_only(
        reservation_path,
        canonical_json({key: value for key, value in reservation.items() if key != "reservation_sha256"}),
    )
    raw_directory = selected_raw_root / f"run={_format_utc(started_at).replace('-', '').replace(':', '')}"
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
                "path": body_path.relative_to(selected_raw_root).as_posix(),
                "envelope_path": envelope_path.relative_to(selected_raw_root).as_posix(),
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
        receipt = run_seasoned_base_rate_campaign(
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
            "terminal_outcome": (
                _terminal_from_error(exc) if isinstance(exc, OrganicPressureError) else INVALID_TERMINAL
            ),
            "terminal_error_code": str(exc),
            "credential_reads": credential_reads,
            "provider_requests": getattr(exc, "provider_requests", 0) or 0,
            "retries": 0,
            "fallbacks": 0,
            "execute_calls": 0,
            "observations": [],
            "non_claims": ["NO_EXECUTE", "NO_TAKER_OR_SIGNER", "NO_ALPHA", "NO_NETRETURN"],
        }
        if receipt.get("terminal_outcome") == INVALID_TERMINAL:
            receipt["invalid_class"] = classify_campaign_failure(receipt)
    receipt["receipt_id"] = "EVIDENCE-SEASONED-30M-H900-BASE-RATE-RUNTIME-001"
    receipt["attempt_reservation"] = reservation
    receipt["prior_mints_sha256"] = excluded_mints_sha256
    receipt["raw_retention"] = {"mode": "A4_OUTSIDE_GIT", "manifests": manifests}
    receipt["credential_reads"] = credential_reads
    encoded = canonical_json(receipt)
    if credential_value and credential_value.encode("utf-8") in encoded:
        raise OrganicPressureError("API_KEY_IN_URL_LOG_RECEIPT_OR_GIT")
    target = receipt_path or (ROOT / "docs/evidence/seasoned_30m_h900_base_rate_probe/a1_runtime_receipt_v1.json")
    _write_create_only(target, encoded)
    return receipt


def _owner_next_for_error(code: str) -> str:
    if code == "CREATE_ONLY_EXISTS":
        return (
            "ONE_WINDOW_ALREADY_RESERVED_DO_NOT_RESTART; "
            "read the existing reservation or wait for the live run to finish; "
            "do not Ctrl+C an 1800s+H900 wait and rerun"
        )
    if code == "AUTHORITY_PHRASE_INVALID":
        return "PASTE_EXACT_FROZEN_PHRASE_AS_SINGLE_QUOTED_POWERSHELL_STRING"
    if code == "PRIOR_MINT_EXCLUSION_INPUT_INVALID":
        return "SUPPLY_NONEMPTY_JSON_OBJECT_WITH_MINTS_ARRAY_OF_PRIOR_CONSUMED_MINTS"
    if code == "JUPITER_API_KEY_MISSING_OR_EMPTY":
        return (
            "SET_JUPITER_API_KEY_IN_PROCESS_ENVIRONMENT_ONLY_THEN_ONE_WINDOW; "
            "presence is checked before reservation so a missing key does not consume the window"
        )
    return "INVALID_EVIDENCE_REPLAN_DO_NOT_RETRY_THE_SAME_RESERVATION"


def _owner_next_for_terminal(terminal: str) -> str:
    if terminal == NO_POSITIVE_MASS_TERMINAL:
        return "STOP_DESIGN_ONLY_REFRAME_NO_AUTO_45M_60M_NO_AUTO_X"
    if terminal == SHOWS_POSITIVE_MASS_TERMINAL:
        return "STOP_RECOMMEND_DESIGN_ONLY_SEASONED_POSITIVE_SELECTOR_SEARCH"
    if terminal == INCONCLUSIVE_TERMINAL:
        return "STOP_OWNER_DECIDES_WHETHER_ANOTHER_SURFACE_PROBE_HAS_INFORMATION_VALUE"
    return "INVALID_EVIDENCE_REPLAN_DISTINGUISH_CLASS_NO_AUTOMATIC_RETRY"


def owner_exit_blocked(terminal: str) -> bool:
    return terminal not in SUCCESS_TERMINALS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "PowerShell: pass --owner-phrase as a single-quoted string so $ and ; do not expand.\n"
            "Set JUPITER_API_KEY in the process environment before starting; never .env.\n"
            "After reservation the process waits ~1800s then ~900s with no progress output.\n"
            "Do not Ctrl+C and restart; a second start is CREATE_ONLY_EXISTS."
        ),
    )
    parser.add_argument(
        "--owner-phrase",
        required=True,
        help="Exact frozen owner phrase; single-quoted on PowerShell.",
    )
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
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
            config_path=args.config,
        )
    except (OrganicPressureError, QualificationError) as exc:
        code = str(exc)
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": code,
                    "owner_state": "BLOCKED",
                    "terminal_outcome": INVALID_TERMINAL,
                    "invalid_class": classify_campaign_failure({"terminal_error_code": code}),
                    "next": _owner_next_for_error(code),
                },
                ensure_ascii=False,
            )
        )
        return 2
    terminal = str(receipt.get("terminal_outcome") or INVALID_TERMINAL)
    error_code = str(receipt.get("terminal_error_code") or "")
    blocked = owner_exit_blocked(terminal)
    print(
        json.dumps(
            {
                "ok": not blocked,
                "owner_state": "BLOCKED" if blocked else "DONE",
                "terminal_outcome": terminal,
                "invalid_class": receipt.get("invalid_class"),
                "next": (
                    _owner_next_for_error(error_code)
                    if error_code
                    else _owner_next_for_terminal(terminal)
                ),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 2 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
