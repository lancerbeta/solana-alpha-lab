#!/usr/bin/env python3
"""One-shot keyless getTransaction of the pinned H11 Create signature."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.rc002_h11_bounded_gettransaction_create import (
    BoundedGetTransactionTerminal,
    bind_get_transaction_request,
    classify_gettransaction_body,
    classify_transport_failure,
    dns_tcp_preflight,
    load_pinned_plan,
    perform_http_post_once,
    write_raw_a4,
)

RAW_ROOT = ROOT / "local" / "rc002_h11_bounded_gettransaction_create"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument(
        "--fixture",
        type=Path,
        default=ROOT / "tests/fixtures/rc002_h11/gettransaction_create_same_195_v1.json",
    )
    args = parser.parse_args()
    pinned = load_pinned_plan(ROOT)
    if args.live:
        preflight = dns_tcp_preflight()
        try:
            transport = perform_http_post_once(bind_get_transaction_request())
        except BoundedGetTransactionTerminal as exc:
            result = classify_transport_failure(exc)
            result["preflight"] = preflight
            json.dump(result, sys.stdout, indent=2, sort_keys=True)
            sys.stdout.write("\n")
            return 0
        raw = write_raw_a4(RAW_ROOT, body=bytes(transport["body"]))
        classified = classify_gettransaction_body(
            bytes(transport["body"]), pinned=pinned
        )
        classified["preflight"] = preflight
        classified["transport"] = {
            "http_status": transport["http_status"],
            "response_bytes": transport["response_bytes"],
            "response_sha256": transport["response_sha256"],
            "request_count": transport["request_count"],
            "credential_reads": transport["credential_reads"],
        }
        classified["raw"] = raw
        json.dump(classified, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0
    body = args.fixture.read_bytes()
    result = classify_gettransaction_body(body, pinned=pinned)
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
