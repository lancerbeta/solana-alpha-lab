#!/usr/bin/env python3
"""Execute the authorized quote-native Jupiter V2 /order measurement panel."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.quote_native_evidence_fit_panel import (  # noqa: E402
    ATOM_ID,
    AUTHORITY_PHRASE,
    CONFIG_RELATIVE,
    PanelError,
    run_wave,
)

CONFIG_PATH = ROOT / CONFIG_RELATIVE
RAW_ROOT = ROOT / "local/quote_native_evidence_fit_panel"
RUNTIME_RECEIPT_PATH = (
    ROOT / "docs/evidence/quote_native_evidence_fit_panel/a1_quote_native_evidence_fit_panel_runtime_receipt_v1.json"
)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise PanelError(code)


def _load_policy() -> dict[str, object]:
    value = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "POLICY_INVALID")
    return value


def _write_receipt(path: Path, document: Mapping[str, Any], *, create_only: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if create_only:
        try:
            with path.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(payload)
        except FileExistsError as exc:
            raise PanelError("RUNTIME_RECEIPT_ALREADY_EXISTS") from exc
        return
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(payload, encoding="utf-8", newline="\n")
    tmp_path.replace(path)


def _write_raw(raw_root: Path, run_id: str, bodies: Mapping[str, bytes]) -> list[dict[str, object]]:
    manifests: list[dict[str, object]] = []
    directory = raw_root / f"run={run_id}"
    directory.mkdir(parents=True, exist_ok=True)
    for observation_id, body in bodies.items():
        safe_name = observation_id.replace(":", "_") + ".json"
        payload_path = directory / safe_name
        payload_path.write_bytes(body)
        try:
            stored = payload_path.resolve().relative_to(ROOT.resolve()).as_posix()
        except ValueError:
            stored = payload_path.name
        manifests.append(
            {
                "observation_id": observation_id,
                "path": stored,
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "retention": "A4_OUTSIDE_GIT",
            }
        )
    return manifests


def run_capture(*, authority_phrase: str, wave: str) -> dict[str, object]:
    _require(authority_phrase == AUTHORITY_PHRASE, "AUTHORITY_PHRASE_INVALID")
    policy = _load_policy()
    started = datetime.now(UTC)
    prior = None
    if wave == "due":
        _require(RUNTIME_RECEIPT_PATH.is_file(), "PRIOR_RECEIPT_REQUIRED")
        loaded = json.loads(RUNTIME_RECEIPT_PATH.read_text(encoding="utf-8"))
        _require(isinstance(loaded, dict), "PRIOR_RECEIPT_REQUIRED")
        prior = loaded
    receipt = run_wave(
        policy,
        root=ROOT,
        wave=wave,
        now=started,
        prior_receipt=prior,
        clock=lambda: datetime.now(UTC),
    )
    raw_bodies = dict(receipt.pop("raw_bodies"))
    run_id = str(receipt["started_at"]).replace("-", "").replace(":", "") + f"-{wave}"
    prior_manifests: list[dict[str, object]] = []
    if isinstance(prior, dict):
        retention = prior.get("raw_retention")
        if isinstance(retention, dict) and isinstance(retention.get("manifests"), list):
            prior_manifests = [item for item in retention["manifests"] if isinstance(item, dict)]
    new_manifests = _write_raw(RAW_ROOT, run_id, raw_bodies)
    receipt["raw_retention"] = {
        "raw_retained": bool(prior_manifests or new_manifests),
        "manifests": prior_manifests + new_manifests,
    }
    receipt["receipt_id"] = "EVIDENCE-QUOTE-NATIVE-EVIDENCE-FIT-PANEL-001"
    _write_receipt(RUNTIME_RECEIPT_PATH, receipt, create_only=wave == "t0")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority-phrase", required=True)
    parser.add_argument("--wave", choices=("t0", "due"), default="t0")
    args = parser.parse_args()
    try:
        receipt = run_capture(authority_phrase=args.authority_phrase, wave=args.wave)
    except PanelError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2, sort_keys=True))
        return 2
    print(
        json.dumps(
            {
                "ok": True,
                "atom_id": ATOM_ID,
                "terminal_outcome": receipt.get("terminal_outcome"),
                "provider_requests": receipt.get("provider_requests"),
                "comparable_identities": receipt.get("comparable_identities"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
