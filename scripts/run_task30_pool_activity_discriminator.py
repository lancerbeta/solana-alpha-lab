#!/usr/bin/env python3
"""Execute one authorized TASK-30 A16P Helius RPC request."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import socket
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.lifecycle_discovery_transport import stdlib_http_exchange  # noqa: E402
from solana_alpha_lab.task30_pool_activity_discriminator_runtime import (  # noqa: E402
    LOGICAL_ROOT,
    LOGICAL_ROOT_V2,
    PoolActivityRuntimeError,
    execute_pool_activity_attempt,
)


def _route_preflight() -> dict[str, bool]:
    host = "mainnet.helius-rpc.com"
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError:
        return {"dns_resolved": False, "tcp_443": False}
    if not addresses:
        return {"dns_resolved": False, "tcp_443": False}
    try:
        with socket.create_connection((host, 443), timeout=3.0):
            pass
    except OSError:
        return {"dns_resolved": True, "tcp_443": False}
    return {"dns_resolved": True, "tcp_443": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", required=True)
    parser.add_argument("--authority", required=True)
    parser.add_argument("--profile", choices=("v1", "v2"), default="v1")
    args = parser.parse_args()
    try:
        config = yaml.safe_load(
            (ROOT / "configs/task30_pool_activity_discriminator_v1.yaml").read_text(
                encoding="utf-8"
            )
        )
        receipt = execute_pool_activity_attempt(
            config,
            authority_phrase=args.authority,
            execution_profile=args.profile,
            repository_root=ROOT,
            raw_root=(ROOT / (LOGICAL_ROOT if args.profile == "v1" else LOGICAL_ROOT_V2)).resolve(),
            route_preflight=_route_preflight,
            credential_loader=lambda name: os.environ[name],
            http_exchange=stdlib_http_exchange,
            clock=lambda: datetime.now(UTC),
            nonce_factory=lambda: secrets.token_hex(4),
        )
        print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
        return 0
    except PoolActivityRuntimeError as exc:
        print(json.dumps({"result": "STOP", "error": exc.code}, sort_keys=True))
        return 2
    except KeyError:
        print(json.dumps({"result": "STOP", "error": "HELIUS_CREDENTIAL_MISSING"}, sort_keys=True))
        return 2
    except Exception:
        print(json.dumps({"result": "STOP", "error": "UNCLASSIFIED_LOCAL_FAILURE"}, sort_keys=True))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
