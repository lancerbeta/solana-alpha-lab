"""Run one future TASK-30 A11C slot only after exact owner authorization."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from time import sleep, time
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from solana_alpha_lab.task30_two_slot_live_shakedown_runtime import (  # noqa: E402
    BoundedGeckoTransport,
    TwoSlotShakedownRuntimeError,
    build_slot_plan,
    parse_execution_authority,
    run_slot,
    validate_runtime_policy,
)


POLICY_PATH = ROOT / "configs" / "task30_two_slot_live_shakedown_runtime_v1.yaml"


def _load_policy() -> dict[str, Any]:
    value = yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TwoSlotShakedownRuntimeError("POLICY_INVALID")
    validate_runtime_policy(value)
    return value


def _required_local_root(policy: dict[str, Any], value: Path) -> Path:
    retention = policy["retention"]
    if not isinstance(retention, dict):
        raise TwoSlotShakedownRuntimeError("RETENTION_POLICY_INVALID")
    expected_root = (ROOT / str(retention["raw_root_relative"])).resolve()
    candidate = value.resolve()
    if not candidate.is_relative_to(expected_root):
        raise TwoSlotShakedownRuntimeError("RAW_ROOT_OUTSIDE_A4_FORBIDDEN")
    return candidate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--slot-index", type=int, choices=(1, 2), required=True)
    parser.add_argument("--authority", required=True)
    parser.add_argument("--raw-root", type=Path)
    parser.add_argument("--prior-receipt", type=Path)
    parser.add_argument("--now-epoch", type=int, help="dry-run-only deterministic clock")
    arguments = parser.parse_args()

    try:
        policy = _load_policy()
        authority = parse_execution_authority(arguments.authority)
        if arguments.dry_run:
            if arguments.now_epoch is None:
                raise TwoSlotShakedownRuntimeError("DRY_RUN_NOW_EPOCH_REQUIRED")
            if arguments.raw_root is not None or arguments.prior_receipt is not None:
                raise TwoSlotShakedownRuntimeError("DRY_RUN_OUTPUT_FORBIDDEN")
            plan = build_slot_plan(policy, authority, slot_index=arguments.slot_index, now_epoch=arguments.now_epoch)
            print(json.dumps({"network_calls": 0, "output_created": False, "plan": plan}, sort_keys=True))
            return 0

        if arguments.now_epoch is not None:
            raise TwoSlotShakedownRuntimeError("EXECUTE_CLOCK_OVERRIDE_FORBIDDEN")
        if arguments.raw_root is None:
            raise TwoSlotShakedownRuntimeError("RAW_ROOT_REQUIRED")
        if arguments.slot_index == 1 and arguments.prior_receipt is not None:
            raise TwoSlotShakedownRuntimeError("PRIOR_RECEIPT_UNEXPECTED")
        if arguments.slot_index == 2 and arguments.prior_receipt is None:
            raise TwoSlotShakedownRuntimeError("PRIOR_RECEIPT_REQUIRED")
        raw_root = _required_local_root(policy, arguments.raw_root)
        request = policy["request"]
        if not isinstance(request, dict):
            raise TwoSlotShakedownRuntimeError("REQUEST_POLICY_INVALID")
        transport = BoundedGeckoTransport(response_bytes_max=int(request["response_bytes_max"]), timeout_seconds=int(request["request_timeout_seconds"]))
        result = run_slot(
            policy, authority, slot_index=arguments.slot_index, raw_root=raw_root,
            transport=transport, now=lambda: int(time()), sleep=sleep,
            prior_receipt=arguments.prior_receipt,
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except TwoSlotShakedownRuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
