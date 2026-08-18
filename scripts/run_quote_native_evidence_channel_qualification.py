#!/usr/bin/env python3
"""Run one foreground Free-key quote-native evidence qualification."""

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

from solana_alpha_lab.quote_native_evidence_channel_qualification import (  # noqa: E402
    ATOM_ID,
    QualificationError,
    load_process_credential,
    run_campaign,
    validate_policy,
)


CONFIG_PATH = ROOT / "configs/quote_native_evidence_channel_qualification_v1.yaml"
RAW_ROOT = ROOT / "local/quote_native_evidence_channel_qualification"
RUNTIME_RECEIPT_PATH = (
    ROOT
    / "docs/evidence/quote_native_evidence_channel_qualification"
    / "a1_quote_native_evidence_channel_qualification_runtime_receipt_v1.json"
)


TYPED_STOP_TERMINALS = {
    "API_KEY_IN_URL_LOG_RECEIPT_OR_GIT",
    "RAW_BODY_CONTAINS_CREDENTIAL",
    "CALL_CAP_EXCEEDED",
    "RESPONSE_BYTES_EXCEEDED",
}


def _terminal_from_qualification_error(exc: QualificationError) -> str:
    code = str(exc)
    if code in TYPED_STOP_TERMINALS:
        return code
    return "TRANSPORT_UNKNOWN_OWNER_ACTION_REQUIRED"


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise QualificationError(code)


def _format_utc(value: datetime) -> str:
    _require(value.tzinfo is not None, "CLOCK_INVALID")
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _load_policy() -> dict[str, object]:
    loaded = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    _require(isinstance(loaded, dict), "POLICY_INVALID")
    return loaded


def _write_create_only(path: Path, document: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(document, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
    except FileExistsError as exc:
        raise QualificationError("RUNTIME_RECEIPT_ALREADY_EXISTS") from exc


def _reserve_campaign(raw_root: Path, *, started_at: datetime) -> Path:
    reservation_path = raw_root / "campaign_reservation.json"
    raw_root.mkdir(parents=True, exist_ok=True)
    document = {
        "schema": "smial.quote-native-evidence-channel-qualification.attempt-reservation",
        "schema_version": "1.0",
        "atom_id": ATOM_ID,
        "state": "STARTED",
        "started_at": _format_utc(started_at),
        "credential_reads": 0,
        "provider_requests": 0,
    }
    try:
        with reservation_path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(document, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
    except FileExistsError as exc:
        raise QualificationError("CAMPAIGN_RESERVATION_EXISTS") from exc
    return reservation_path


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
) -> dict[str, object]:
    selected_policy = dict(policy or _load_policy())
    validate_policy(selected_policy, root=ROOT)
    authority = selected_policy.get("external_authority")
    _require(isinstance(authority, Mapping), "AUTHORITY_INVALID")
    _require(authority_phrase == authority.get("owner_phrase"), "AUTHORITY_PHRASE_INVALID")
    attempt_started_at = clock()
    reservation_path = _reserve_campaign(raw_root, started_at=attempt_started_at)
    credential_environment = os.environ if environ is None else environ
    run_id = _format_utc(attempt_started_at).replace("-", "").replace(":", "")
    raw_directory = raw_root / f"run={run_id}"
    manifests: list[dict[str, object]] = []
    credential_reads = 0

    def raw_sink(observation_id: str, body: bytes, observed_at: str) -> None:
        raw_directory.mkdir(parents=True, exist_ok=True)
        safe_name = observation_id.replace(":", "_") + ".json"
        destination = raw_directory / safe_name
        with destination.open("xb") as handle:
            handle.write(body)
            handle.flush()
        write_complete_at = _format_utc(clock())
        manifests.append(
            {
                "observation_id": observation_id,
                "path": destination.relative_to(raw_root).as_posix(),
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "observed_at": observed_at,
                "raw_write_complete_at": write_complete_at,
                "retention": "A4_OUTSIDE_GIT",
            }
        )

    def credential_loader() -> str:
        nonlocal credential_reads
        credential_reads += 1
        return load_process_credential(credential_environment)

    run_kwargs: dict[str, object] = {
        "credential_loader": credential_loader,
        "opener": opener,
        "clock": clock,
        "sleeper": sleeper,
        "raw_sink": raw_sink,
    }
    if preflight_fn is not None:
        run_kwargs["preflight_fn"] = preflight_fn
    try:
        receipt = run_campaign(selected_policy, **run_kwargs)
    except QualificationError as exc:
        counted = exc.provider_requests
        terminal = _terminal_from_qualification_error(exc)
        receipt = {
            "schema": "smial.quote-native-evidence-channel-qualification.runtime-receipt",
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
            "campaign": {
                "campaign_verdict": terminal,
                "complete_xy_count": 0,
                "time_separated_complete_xy_count": 0,
            },
            "non_claims": [
                "NO_RETRY",
                "NO_FALLBACK",
                "NO_EXECUTE",
                "NO_TAKER_OR_SIGNER",
                "NO_ALPHA",
                "NO_NETRETURN",
            ],
        }
    receipt["receipt_id"] = "EVIDENCE-QUOTE-NATIVE-EVIDENCE-CHANNEL-QUALIFICATION-001"
    receipt["raw_retention"] = {
        "raw_retained": bool(manifests),
        "manifests": manifests,
    }
    receipt["attempt_reservation"] = {
        "path": reservation_path.relative_to(raw_root).as_posix(),
        "started_at": _format_utc(attempt_started_at),
    }
    _write_create_only(receipt_path, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority-phrase", required=True)
    args = parser.parse_args()
    try:
        receipt = run_capture(authority_phrase=args.authority_phrase)
    except QualificationError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    print(
        json.dumps(
            {
                "ok": True,
                "atom_id": ATOM_ID,
                "terminal_outcome": receipt["terminal_outcome"],
                "provider_requests": receipt["provider_requests"],
                "campaign_verdict": receipt["campaign"]["campaign_verdict"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
