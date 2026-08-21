#!/usr/bin/env python3
"""Run one foreground early-path H900 audition after owner authorization."""

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

from solana_alpha_lab.ordinary_recent_early_path_h900_audition import (  # noqa: E402
    ATOM_ID,
    AUTHORITY_PHRASE,
    RECEIPT_SCHEMA,
    run_early_path_campaign,
    validate_early_path_policy,
)
from solana_alpha_lab.ordinary_recent_organic_pressure_h900_audition import (  # noqa: E402
    OrganicPressureError,
)
from solana_alpha_lab.quote_native_evidence_channel_qualification import (  # noqa: E402
    QualificationError,
    load_process_credential,
)
from solana_alpha_lab.pmf_quote_slice_one_shot import credential_free_preflight  # noqa: E402


CONFIG_PATH = ROOT / "configs/ordinary_recent_early_path_h900_audition_v1.yaml"
RAW_ROOT = ROOT / "local/ordinary_recent_early_path_h900_audition"
RUNTIME_RECEIPT_PATH = (
    ROOT
    / "docs/evidence/ordinary_recent_early_path_h900_audition"
    / "a1_ordinary_recent_early_path_h900_audition_runtime_receipt_v1.json"
)
TYPED_STOP_TERMINALS = {
    "API_KEY_IN_URL_LOG_RECEIPT_OR_GIT",
    "RAW_BODY_CONTAINS_CREDENTIAL",
    "CALL_CAP_EXCEEDED",
    "CREDENTIAL_READ_BEFORE_ATTEMPT_RESERVATION",
    "CREDENTIAL_READ_BEFORE_CREDENTIAL_FREE_PREFLIGHT",
}


def canonical_json(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _format_utc(value: datetime) -> str:
    if value.tzinfo is None:
        raise OrganicPressureError("CLOCK_INVALID")
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def capture_envelope(*, observation_id: str, observed_at: str, body_sha256: str) -> dict[str, str]:
    payload = {
        "body_sha256": body_sha256,
        "observation_id": observation_id,
        "observed_at": observed_at,
        "schema": "smial.ordinary-recent-early-path-h900-audition.capture-envelope",
        "schema_version": "1.0",
    }
    return {
        **payload,
        "envelope_sha256": hashlib.sha256(canonical_json(payload)).hexdigest(),
    }


def attempt_reservation_document(*, started_at: str, policy_sha256: str) -> dict[str, object]:
    payload = {
        "atom_id": ATOM_ID,
        "credential_reads": 0,
        "policy_sha256": policy_sha256,
        "provider_requests": 0,
        "schema": "smial.ordinary-recent-early-path-h900-audition.attempt-reservation",
        "schema_version": "1.0",
        "started_at": started_at,
        "state": "STARTED",
    }
    return {
        **payload,
        "reservation_sha256": hashlib.sha256(canonical_json(payload)).hexdigest(),
    }


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
    validate_early_path_policy(loaded, root=ROOT)
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
    receipt_path: Path = RUNTIME_RECEIPT_PATH,
    environ: Mapping[str, str] | None = None,
    credential_loader: Callable[[], str] | None = None,
    preflight_fn: Callable[..., Mapping[str, Any]] = credential_free_preflight,
    opener: object | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    sleeper: Callable[[float], None] = time.sleep,
    monotonic_clock: Callable[[], float] = time.monotonic,
) -> dict[str, object]:
    selected_policy = dict(policy or _load_policy())
    validate_early_path_policy(selected_policy, root=ROOT)
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
        receipt = run_early_path_campaign(
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
    receipt["receipt_id"] = "EVIDENCE-ORDINARY-RECENT-EARLY-PATH-H900-AUDITION-001"
    receipt["attempt_reservation"] = reservation
    receipt["prior_mints_sha256"] = excluded_mints_sha256
    receipt["raw_retention"] = {
        "mode": "A4_OUTSIDE_GIT",
        "manifests": manifests,
    }
    receipt["credential_reads"] = credential_reads
    encoded = canonical_json(receipt)
    if credential_value and credential_value.encode("utf-8") in encoded:
        raise OrganicPressureError("API_KEY_IN_URL_LOG_RECEIPT_OR_GIT")
    _write_create_only(receipt_path, encoded)
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-phrase", required=True)
    parser.add_argument("--excluded-mints-file", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        receipt = run_capture(
            authority_phrase=args.owner_phrase,
            excluded_mints_path=args.excluded_mints_file,
        )
    except (OrganicPressureError, QualificationError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
