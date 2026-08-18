#!/usr/bin/env python3
"""Run one foreground Free-key admissible friction audition."""

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

from solana_alpha_lab.quote_native_admissible_friction_audition import (  # noqa: E402
    ATOM_ID,
    AUTHORITY_PHRASE,
    AuditionError,
    attempt_reservation_document,
    canonical_json,
    capture_envelope,
    load_process_credential,
    run_campaign,
    unscored_campaign,
    unscored_mechanism,
    validate_policy,
)
from solana_alpha_lab.quote_native_evidence_channel_qualification import (  # noqa: E402
    QualificationError,
)


CONFIG_PATH = ROOT / "configs/quote_native_admissible_friction_audition_v1.yaml"
RAW_ROOT = ROOT / "local/quote_native_admissible_friction_audition"
RUNTIME_RECEIPT_PATH = (
    ROOT
    / "docs/evidence/quote_native_admissible_friction_audition"
    / "a1_quote_native_admissible_friction_audition_runtime_receipt_v1.json"
)

TYPED_STOP_TERMINALS = {
    "API_KEY_IN_URL_LOG_RECEIPT_OR_GIT",
    "RAW_BODY_CONTAINS_CREDENTIAL",
    "CALL_CAP_EXCEEDED",
    "RESPONSE_BYTES_EXCEEDED",
    "CREDENTIAL_READ_BEFORE_ATTEMPT_RESERVATION",
}


def _terminal_from_error(exc: AuditionError | QualificationError) -> str:
    code = str(exc)
    if code in TYPED_STOP_TERMINALS:
        return code
    return "TRANSPORT_UNKNOWN_OWNER_ACTION_REQUIRED"


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise AuditionError(code)


def _format_utc(value: datetime) -> str:
    _require(value.tzinfo is not None, "CLOCK_INVALID")
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _load_policy() -> dict[str, object]:
    loaded = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    _require(isinstance(loaded, dict), "POLICY_INVALID")
    return loaded


def _write_create_only(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(payload)
    except FileExistsError as exc:
        raise AuditionError("CREATE_ONLY_EXISTS") from exc


def _write_create_only_json(path: Path, document: Mapping[str, Any]) -> None:
    _write_create_only(path, canonical_json(document) if "schema" in document else (
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8"))


def run_capture(
    *,
    authority_phrase: str,
    policy: Mapping[str, Any] | None = None,
    raw_root: Path = RAW_ROOT,
    receipt_path: Path = RUNTIME_RECEIPT_PATH,
    environ: Mapping[str, str] | None = None,
    preflight_fn: Callable[..., Mapping[str, Any]] | None = None,
    opener: object | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    sleeper: Callable[[float], None] = time.sleep,
    monotonic_clock: Callable[[], float] | None = None,
) -> dict[str, object]:
    selected_policy = dict(policy or _load_policy())
    validate_policy(selected_policy, root=ROOT)
    authority = selected_policy.get("external_authority")
    _require(isinstance(authority, Mapping), "AUTHORITY_INVALID")
    _require(authority_phrase == authority.get("owner_phrase"), "AUTHORITY_PHRASE_INVALID")
    _require(authority_phrase == AUTHORITY_PHRASE, "AUTHORITY_PHRASE_DRIFT")
    attempt_started_at = clock()
    policy_sha256 = hashlib.sha256(
        yaml.safe_dump(selected_policy, sort_keys=True).encode("utf-8")
        if policy is not None
        else CONFIG_PATH.read_bytes()
    ).hexdigest()
    reservation = attempt_reservation_document(
        started_at=_format_utc(attempt_started_at),
        policy_sha256=policy_sha256,
    )
    raw_root.mkdir(parents=True, exist_ok=True)
    reservation_path = raw_root / "campaign_reservation.json"
    _write_create_only(reservation_path, canonical_json(
        {key: value for key, value in reservation.items() if key != "reservation_sha256"}
    ))
    credential_environment = os.environ if environ is None else environ
    run_id = _format_utc(attempt_started_at).replace("-", "").replace(":", "")
    raw_directory = raw_root / f"run={run_id}"
    manifests: list[dict[str, object]] = []
    credential_reads = 0

    def raw_sink(
        observation_id: str,
        body: bytes,
        observed_at: str,
        envelope_sha256: str,
    ) -> None:
        raw_directory.mkdir(parents=True, exist_ok=True)
        body_sha256 = hashlib.sha256(body).hexdigest()
        envelope = capture_envelope(
            observation_id=observation_id,
            observed_at=observed_at,
            body_sha256=body_sha256,
        )
        _require(envelope["envelope_sha256"] == envelope_sha256, "CAPTURE_ENVELOPE_DRIFT")
        body_path = raw_directory / (observation_id.replace(":", "_") + ".body")
        envelope_path = raw_directory / (observation_id.replace(":", "_") + ".envelope.json")
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
                "capture_envelope_sha256": envelope_sha256,
                "retention": "A4_OUTSIDE_GIT",
            }
        )

    def credential_loader() -> str:
        nonlocal credential_reads
        _require(reservation_path.is_file(), "CREDENTIAL_READ_BEFORE_ATTEMPT_RESERVATION")
        credential_reads += 1
        return load_process_credential(credential_environment)

    run_kwargs: dict[str, object] = {
        "reservation": reservation,
        "credential_loader": credential_loader,
        "opener": opener,
        "clock": clock,
        "sleeper": sleeper,
        "raw_sink": raw_sink,
    }
    if monotonic_clock is not None:
        run_kwargs["monotonic_clock"] = monotonic_clock
    if preflight_fn is not None:
        run_kwargs["preflight_fn"] = preflight_fn
    try:
        receipt = run_campaign(selected_policy, **run_kwargs)
    except (AuditionError, QualificationError) as exc:
        counted = exc.provider_requests
        terminal = _terminal_from_error(exc)
        receipt = {
            "schema": "smial.quote-native-admissible-friction-audition.runtime-receipt",
            "schema_version": "1.0",
            "atom_id": ATOM_ID,
            "terminal_outcome": terminal,
            "terminal_error_code": str(exc),
            "credential_reads": credential_reads,
            "provider_requests": counted if counted is not None else len(manifests),
            "retries": 0,
            "fallbacks": 0,
            "execute_calls": 0,
            "frozen_cells": [],
            "discovery_observations": [],
            "observations": [],
            "attempt_reservation": reservation,
            "capture": {
                "accepted": False,
                "blockers": [str(exc)],
            },
            "campaign": unscored_campaign(reason="NOT_SCORED_TYPED_STOP"),
            "mechanism": unscored_mechanism(reason="NOT_SCORED_TYPED_STOP"),
            "family_close": False,
            "non_claims": [
                "NO_RETRY",
                "NO_FALLBACK",
                "NO_EXECUTE",
                "NO_TAKER_OR_SIGNER",
                "NO_ALPHA",
                "NO_NETRETURN",
            ],
        }
    receipt["receipt_id"] = "EVIDENCE-QUOTE-NATIVE-ADMISSIBLE-FRICTION-AUDITION-001"
    receipt["raw_retention"] = {
        "raw_retained": bool(manifests),
        "manifests": manifests,
    }
    receipt["attempt_reservation"] = {
        **reservation,
        "path": reservation_path.relative_to(raw_root).as_posix(),
        "before_credential_read": True,
    }
    _write_create_only_json(receipt_path, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority-phrase", required=True)
    args = parser.parse_args()
    try:
        receipt = run_capture(authority_phrase=args.authority_phrase)
    except AuditionError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    print(
        json.dumps(
            {
                "ok": True,
                "atom_id": ATOM_ID,
                "terminal_outcome": receipt["terminal_outcome"],
                "provider_requests": receipt["provider_requests"],
                "capture_accepted": receipt["capture"]["accepted"],
                "family_close": receipt.get("family_close"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
