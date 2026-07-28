#!/usr/bin/env python3
"""Run the exact frozen TASK-13 audit locally without external effects."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.pilot_audit import (  # noqa: E402
    EXPECTED_POPULATION_SHA256,
    PilotAuditContractError,
    audit_population,
)

DEFAULT_POPULATION_PATH = (
    "tests/fixtures/task13/pilot_audit_population_v1.json"
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Verify and audit the exact frozen TASK-13 local evidence "
            "population. This command has no network or write mode."
        )
    )
    parser.add_argument(
        "--population",
        default=DEFAULT_POPULATION_PATH,
        help="repository-relative frozen population fixture",
    )
    return parser


def _safe_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _safe_error_code(exc: BaseException) -> str:
    value = str(exc)
    if re.fullmatch(r"[a-z0-9_]{1,96}", value):
        return value
    return "offline_audit_failed_closed"


def main(
    argv: Sequence[str] | None = None,
    *,
    repository_root: Path = ROOT,
    expected_population_sha256: str = EXPECTED_POPULATION_SHA256,
) -> int:
    args = _parser().parse_args(argv)
    try:
        result = audit_population(
            repository_root=repository_root,
            population_path=args.population,
            expected_population_sha256=expected_population_sha256,
        )
    except PilotAuditContractError as exc:
        print("TASK13_PILOT_AUDIT: FAIL")
        print(f"ERROR_CODE: {_safe_error_code(exc)}")
        print("EXTERNAL_EFFECTS: ZERO")
        return 2
    except Exception:
        print("TASK13_PILOT_AUDIT: FAIL")
        print("ERROR_CODE: offline_audit_failed_closed")
        print("EXTERNAL_EFFECTS: ZERO")
        return 3
    print("TASK13_PILOT_AUDIT: PASS")
    print(_safe_json(result))
    print("EXTERNAL_EFFECTS: ZERO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
