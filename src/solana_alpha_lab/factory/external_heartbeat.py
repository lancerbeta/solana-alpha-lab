"""Provider-neutral external heartbeat. Unconfigured is a typed no-op."""

from __future__ import annotations

import os
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping

HEARTBEAT_ENV = "FACTORY_EXTERNAL_HEARTBEAT_URL"
HEARTBEAT_ON_CALENDAR = "*-*-* *:0/5:00 UTC"
UNCONFIGURED = "NOT_CONFIGURED"


def run_external_heartbeat(
    *,
    environ: Mapping[str, str] | None = None,
    transport: Callable[[str], int] | None = None,
    timeout_seconds: int = 5,
    root: Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    env = environ if environ is not None else os.environ
    url = str(env.get(HEARTBEAT_ENV) or "").strip()
    if url == "":
        return {
            "terminal": UNCONFIGURED,
            "network_calls": 0,
            "url_logged": False,
        }
    if "://" not in url or url.split("://", 1)[0] not in {"https", "http"}:
        return {
            "terminal": "HEARTBEAT_URL_INVALID",
            "network_calls": 0,
            "url_logged": False,
        }
    from solana_alpha_lab.factory.operability_watch import (
        SNAPSHOT_RELATIVE, evaluate_collector_snapshot_freshness, load_collector_snapshot_file,
    )

    repository_root = root if root is not None else Path(__file__).resolve().parents[3]
    state, snapshot = load_collector_snapshot_file(repository_root / SNAPSHOT_RELATIVE)
    age = None
    if state == "PRESENT" and snapshot is not None:
        state, age = evaluate_collector_snapshot_freshness(snapshot["observed_at"], now=now or datetime.now(UTC))
    if state != "FRESH":
        return {"terminal": "NO_PING", "reason": f"WATCH_SNAPSHOT_{state}",
                "network_calls": 0, "url_logged": False, "snapshot_age_seconds": age}
    if transport is not None:
        status = transport(url)
        return {
            "terminal": "HEARTBEAT_SENT" if int(status) < 400 else "HEARTBEAT_FAILED",
            "network_calls": 1,
            "url_logged": False,
            "http_status": int(status),
        }
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            status = int(response.status)
    except urllib.error.URLError:
        return {"terminal": "HEARTBEAT_FAILED", "network_calls": 1, "url_logged": False}
    return {
        "terminal": "HEARTBEAT_SENT" if status < 400 else "HEARTBEAT_FAILED",
        "network_calls": 1,
        "url_logged": False,
        "http_status": status,
    }
