#!/usr/bin/env python3
"""Run one exactly authorized TASK-30 A17 same-window discriminator."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.lifecycle_discovery_transport import (  # noqa: E402
    HttpCapture,
    WssCapture,
    stdlib_http_exchange,
)
from solana_alpha_lab.task30_active_pool_route_yield_runtime import (  # noqa: E402
    ActivePoolRouteYieldRuntimeError,
    LOGICAL_ROOT,
    execute_active_pool_route_yield,
)


def _preflight() -> dict[str, bool]:
    host = "mainnet.helius-rpc.com"
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        with socket.create_connection((host, 443), timeout=3.0):
            pass
    except socket.gaierror:
        return {"dns_resolved": False, "tcp_443": False}
    except OSError:
        return {"dns_resolved": bool(locals().get("addresses")), "tcp_443": False}
    return {"dns_resolved": bool(addresses), "tcp_443": True}


def _keyless_get(request: object, *, max_response_bytes: int) -> HttpCapture:
    url = getattr(request, "url", "")
    node = os.environ.get("CODEX_NODE_PATH") or "node"
    source = r"""
const https = require('https');
const target = process.argv[1];
const cap = Number(process.argv[2]);
let chunks = [], seen = 0;
const request = https.get(target, {headers:{accept:'application/json','user-agent':'smial-task30-a17/1.0'}, timeout:5000}, response => {
  response.on('data', chunk => { seen += chunk.length; if (seen <= cap) chunks.push(chunk); });
  response.on('end', () => process.stdout.write(JSON.stringify({status:response.statusCode, bytes:seen, body:Buffer.concat(chunks).toString('base64')})));
});
request.on('timeout', () => request.destroy(new Error('TIMEOUT')));
request.on('error', error => { process.stderr.write(error.code || error.message); process.exit(2); });
"""
    try:
        completed = subprocess.run([node, "-e", source, url, str(max_response_bytes)], check=False, capture_output=True, timeout=8.0)
    except subprocess.TimeoutExpired:
        return HttpCapture(status_code=None, body=b"", response_url=url, terminal_class="TIMEOUT", error_class="discovery_timeout")
    except OSError:
        return HttpCapture(status_code=None, body=b"", response_url=url, terminal_class="DNS_OR_TLS", error_class="discovery_connection_failed")
    if completed.returncode != 0:
        return HttpCapture(status_code=None, body=b"", response_url=url, terminal_class="DNS_OR_TLS", error_class="node_https_failed")
    try:
        document = json.loads(completed.stdout)
        received = int(document["bytes"])
        import base64
        body = base64.b64decode(document["body"], validate=True)
        status = int(document["status"])
    except Exception:
        return HttpCapture(status_code=None, body=b"", response_url=url, terminal_class="TRANSPORT_FAILURE", error_class="node_receipt_invalid")
    if received > max_response_bytes:
        return HttpCapture(status_code=None, body=b"", response_url=url, terminal_class="RESPONSE_TOO_LARGE", error_class="discovery_response_too_large", received_bytes=received)
    return HttpCapture(status_code=status, body=body, response_url=url, received_bytes=received)


def _first_notification_wss(request: object, *, max_open_seconds: int, max_stream_bytes: int, max_notifications: int) -> WssCapture:
    from websockets.exceptions import ConnectionClosed, PayloadTooBig
    from websockets.sync.client import connect

    acknowledgement = b""
    acknowledgement_at: datetime | None = None
    notifications: list[bytes] = []
    notification_times: list[datetime] = []
    started = time.monotonic()
    websocket = None

    def result(terminal: str, error: str | None, reason: str) -> WssCapture:
        return WssCapture(acknowledgement=acknowledgement, notifications=tuple(notifications), acknowledgement_observed_at=acknowledgement_at, notification_observed_at=tuple(notification_times), terminal_class=terminal, error_class=error, stop_reason=reason)

    try:
        websocket = connect(getattr(request, "url"), open_timeout=5.0, close_timeout=1.0, max_size=100000, max_queue=1, compression=None, additional_headers=dict(getattr(request, "headers")), ping_interval=60.0, ping_timeout=20.0, proxy=None)
        websocket.send(getattr(request, "body").decode())
        frame = websocket.recv(timeout=min(10.0, max_open_seconds))
        acknowledgement = frame.encode() if isinstance(frame, str) else frame
        acknowledgement_at = datetime.now(UTC)
        while time.monotonic() - started < max_open_seconds:
            remaining = max_open_seconds - (time.monotonic() - started)
            try:
                frame = websocket.recv(timeout=remaining)
            except TimeoutError:
                return result("BOUND_REACHED", None, "ELAPSED_CAP")
            body = frame.encode() if isinstance(frame, str) else frame
            if len(acknowledgement) + len(body) > max_stream_bytes:
                return result("RESPONSE_TOO_LARGE", "wss_stream_limit", "STREAM_LIMIT")
            notifications.append(body)
            notification_times.append(datetime.now(UTC))
            return result("BOUND_REACHED", None, "FIRST_NOTIFICATION")
        return result("BOUND_REACHED", None, "ELAPSED_CAP")
    except PayloadTooBig:
        return result("RESPONSE_TOO_LARGE", "wss_frame_too_large", "FRAME_LIMIT")
    except ConnectionClosed:
        return result("REMOTE_CLOSED", "wss_remote_closed", "REMOTE_CLOSED")
    except (TimeoutError, socket.timeout):
        return result("TIMEOUT", "wss_timeout", "OPEN_OR_ACK_TIMEOUT")
    except (OSError, ssl.SSLError, ConnectionError):
        return result("DNS_OR_TLS", "wss_connection_failed", "CONNECTION_FAILURE")
    except Exception:
        return result("TRANSPORT_FAILURE", "wss_unclassified_failure", "TRANSPORT_FAILURE")
    finally:
        if websocket is not None:
            try:
                websocket.close()
            except Exception:
                pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", required=True)
    parser.add_argument("--authority", required=True)
    args = parser.parse_args()
    try:
        receipt = execute_active_pool_route_yield(
            yaml.safe_load((ROOT / "configs/task30_active_pool_route_yield_v1.yaml").read_text(encoding="utf-8")),
            yaml.safe_load((ROOT / "configs/provider_route_capability_registry_v2.yaml").read_text(encoding="utf-8")),
            authority_phrase=args.authority,
            repository_root=ROOT,
            raw_root=(ROOT / LOGICAL_ROOT).resolve(),
            discovery_exchange=_keyless_get,
            route_preflight=_preflight,
            credential_loader=lambda name: os.environ[name],
            wss_exchange=_first_notification_wss,
            rpc_exchange=stdlib_http_exchange,
            clock=lambda: datetime.now(UTC),
            nonce_factory=lambda: secrets.token_hex(4),
        )
        print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
        return 0
    except ActivePoolRouteYieldRuntimeError as exc:
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
