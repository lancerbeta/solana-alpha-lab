#!/usr/bin/env python3
"""Run the Factory commissioning live capture after the exact owner phrase."""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.application import ApplicationError, FactoryApplication  # noqa: E402
from solana_alpha_lab.quote_native_admissible_friction_audition import (  # noqa: E402
    FACTORY_V1_COMMISSIONING_AUTHORITY_PHRASE,
)


def main() -> int:
    print("FACTORY_COMMISSIONING_CAPTURE_START", flush=True)
    stop = threading.Event()

    def beat() -> None:
        minutes = 0
        while not stop.wait(60):
            minutes += 1
            print(f"FACTORY_COMMISSIONING_HEARTBEAT_MIN={minutes}", flush=True)

    threading.Thread(target=beat, daemon=True).start()
    app = FactoryApplication(
        root=ROOT,
        authority_phrase=FACTORY_V1_COMMISSIONING_AUTHORITY_PHRASE,
    )
    try:
        model = app.start()
    except ApplicationError as exc:
        stop.set()
        print(str(exc), file=sys.stderr)
        print("FACTORY_COMMISSIONING_CAPTURE_END", "APPLICATION_ERROR", flush=True)
        return 2
    stop.set()
    safe = {
        "blocker": model.get("blocker"),
        "next_safe_action": model.get("next_safe_action"),
        "result": model.get("result"),
        "robustness": model.get("robustness"),
        "status": model.get("status"),
        "terminal_result": model.get("terminal_result"),
        "uncertainty": model.get("uncertainty"),
    }
    print(json.dumps(safe, indent=2, sort_keys=True, ensure_ascii=False), flush=True)
    print("FACTORY_COMMISSIONING_CAPTURE_END", model.get("status"), flush=True)
    return 0 if model.get("status") == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
