"""One bulk later-search over the exact retained EARLY cohort. Optional maturity probe.

Zero new product code: reuses the existing credentialed GET, search URL builder,
credential-free preflight and process-environment credential loader. The probe
answers whether same-cohort SEASONED availability exists; it never changes the
frozen EARLY ICP.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.ordinary_recent_organic_pressure_h900_audition import (  # noqa: E402
    build_search_url,
)
from solana_alpha_lab.pmf_quote_slice_one_shot import (  # noqa: E402
    QuoteShotError,
    credential_free_preflight,
)
from solana_alpha_lab.quote_native_evidence_channel_qualification import (  # noqa: E402
    QualificationError,
    load_process_credential,
    perform_credentialed_get,
)

ATOM_ID = "EARLY_ICP_FREEZE_AND_MATURITY_BRANCH_CLOSE_V1"
PROBE_SCHEMA = "smial.early-icp-freeze.maturity-probe-runtime-receipt"
RAW_ROOT = ROOT / "local/early_icp_freeze_maturity_probe"
LIVE_GATE_ROOT = ROOT / "local/in_scope_population_live_supply_gate"
SEARCH_BODY = LIVE_GATE_ROOT / (
    "71b1e477322066b1a5876ad22769fb22465641ce2749f5a5e519f3099f20389a.body"
)
OBSERVED_AT = "2026-08-21T12:23:26Z"
LIQUIDITY_MIN = 1000


def _early_mints() -> list[str]:
    rows = json.loads(SEARCH_BODY.read_text(encoding="utf-8"))
    observed_at = datetime.fromisoformat(OBSERVED_AT.replace("Z", "+00:00"))
    mints = []
    for row in rows:
        if row.get("launchpad") != "pump.fun":
            continue
        liquidity = row.get("liquidity")
        if not isinstance(liquidity, (int, float)) or liquidity < LIQUIDITY_MIN:
            continue
        created = datetime.fromisoformat(row["firstPool"]["createdAt"].replace("Z", "+00:00"))
        age_seconds = (observed_at - created).total_seconds()
        if 300 <= age_seconds < 900:
            mints.append(str(row["id"]))
    if len(mints) < 12:
        raise SystemExit("PROBE_COHORT_TOO_SMALL")
    return mints


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    args = parser.parse_args()

    mints = _early_mints()
    started_at = datetime.now(UTC)

    preflight = credential_free_preflight(
        {"provider_route": {"endpoint": "https://api.jup.ag/tokens/v2/search"}},
        observed_at=started_at.isoformat(timespec="seconds").replace("+00:00", "Z"),
    )

    environment = os.environ
    credential = load_process_credential(environment)

    url = build_search_url(mints)
    result = perform_credentialed_get(
        url,
        api_key=credential,
        limits={"max_response_bytes": 2_000_000, "timeout_seconds": 30},
    )
    if result.get("url_has_api_key") is True:
        raise SystemExit("API_KEY_IN_URL")

    body = result.get("body")
    if not isinstance(body, bytes):
        raise SystemExit("PROBE_BODY_MISSING")
    if credential.encode("utf-8") in body:
        raise SystemExit("API_KEY_IN_RESPONSE")
    body_sha256 = hashlib.sha256(body).hexdigest()

    RAW_ROOT.mkdir(parents=True, exist_ok=True)
    stem = body_sha256[:16]
    (RAW_ROOT / f"{stem}.body").write_bytes(body)
    envelope = {
        "body_sha256": body_sha256,
        "bytes": len(body),
        "observation_id": "MATURITY_PROBE:LATER_SEARCH",
        "observed_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    (RAW_ROOT / f"{stem}.envelope.json").write_bytes(
        (json.dumps(envelope, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )

    status = result.get("http_status")
    alive_n = 0
    seasoned_alive_n = 0
    if int(status or 0) == 200:
        payload = json.loads(body.decode("utf-8"))
        probe_at = datetime.fromisoformat(envelope["observed_at"].replace("Z", "+00:00"))
        for row in payload:
            if row.get("launchpad") != "pump.fun":
                continue
            liquidity = row.get("liquidity")
            if not isinstance(liquidity, (int, float)) or liquidity < LIQUIDITY_MIN:
                continue
            created = datetime.fromisoformat(row["firstPool"]["createdAt"].replace("Z", "+00:00"))
            age_seconds = (probe_at - created).total_seconds()
            alive_n += 1
            if 1800 <= age_seconds <= 7200:
                seasoned_alive_n += 1

    receipt = {
        "schema": PROBE_SCHEMA,
        "schema_version": "1.0",
        "atom_id": ATOM_ID,
        "stage": "OPTIONAL_MATURITY_PROBE",
        "cohort_source_body_sha256": hashlib.sha256(SEARCH_BODY.read_bytes()).hexdigest(),
        "cohort_n": len(mints),
        "cohort_decision_time_observed_at": OBSERVED_AT,
        "probe_observed_at": envelope["observed_at"],
        "preflight": preflight,
        "provider_requests": 1,
        "http_status": status,
        "raw_retention": {
            "mode": "A4_OUTSIDE_GIT",
            "body_path": f"local/early_icp_freeze_maturity_probe/{stem}.body",
            "body_sha256": body_sha256,
            "bytes": len(body),
        },
        "alive_pumpfun_liq_ge_min_n": alive_n,
        "same_population_seasoned_band_n": seasoned_alive_n,
        "non_claims": [
            "NO_QUOTES",
            "NO_SWAP",
            "NO_H900",
            "NO_STATE_X",
            "NO_ALPHA",
            "NO_NETRETURN",
            "NO_ICP_CHANGE",
            "UNKNOWN_NEVER_ZERO",
        ],
    }
    receipt_path = RAW_ROOT / "maturity_probe_runtime_receipt_v1.json"
    receipt_path.write_bytes(
        (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )
    print(
        json.dumps(
            {
                "atom_id": ATOM_ID,
                "stage": receipt["stage"],
                "cohort_n": receipt["cohort_n"],
                "http_status": receipt["http_status"],
                "alive_pumpfun_liq_ge_min_n": receipt["alive_pumpfun_liq_ge_min_n"],
                "same_population_seasoned_band_n": receipt["same_population_seasoned_band_n"],
                "receipt_out": str(receipt_path.relative_to(ROOT)).replace("\\", "/"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
