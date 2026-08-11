#!/usr/bin/env python3
"""Guarded foreground runner for one future TASK-30 stream capture."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.lifecycle_discovery_transport import (  # noqa: E402
    WssCapture,
    websockets_wss_exchange,
)
from solana_alpha_lab.task30_forward_stream_execution import (  # noqa: E402
    ForwardStreamExecutionError,
    execute_forward_stream_attempt,
    validate_forward_stream_preflight,
)
from solana_alpha_lab.task30_forward_stream_runtime import (  # noqa: E402
    ForwardStreamRuntimeError,
)


CONFIG_ROOT = Path(__file__).resolve().parents[1] / "configs"
PROFILE_PATHS = {
    "v1": (
        CONFIG_ROOT / "task30_forward_stream_execution_adapter_v1.yaml",
        CONFIG_ROOT / "task30_forward_stream_runtime_harness_v1.yaml",
    ),
    "v2": (
        CONFIG_ROOT / "task30_forward_stream_execution_adapter_v2.yaml",
        CONFIG_ROOT / "task30_forward_stream_runtime_harness_v2.yaml",
    ),
}
# Compatibility aliases retained for callers and existing offline tests.
EXECUTION_CONFIG_PATH, RUNTIME_CONFIG_PATH = PROFILE_PATHS["v1"]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--authority", required=True)
    parser.add_argument("--raw-root", required=True, type=Path)
    parser.add_argument("--profile", choices=tuple(PROFILE_PATHS), default="v1")
    return parser


def _safe_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _load_mapping(path: Path) -> Mapping[str, object]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ForwardStreamExecutionError("CONFIG_MAPPING_REQUIRED")
    return value


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    wss_exchange: Callable[..., WssCapture] = websockets_wss_exchange,
) -> int:
    args = _parser().parse_args(argv)
    try:
        execution_path, runtime_path = PROFILE_PATHS[args.profile]
        execution_config = _load_mapping(execution_path)
        runtime_config = _load_mapping(runtime_path)
        if args.dry_run:
            validate_forward_stream_preflight(
                execution_config,
                runtime_config,
                authority_phrase=args.authority,
                repository_root=ROOT,
                raw_root=args.raw_root,
            )
            print(
                _safe_json(
                    {
                        "credential_read": False,
                        "network_calls": 0,
                        "output_created": False,
                        "result": "DRY_RUN_PASS",
                    }
                )
            )
            return 0

        environment = os.environ if environ is None else environ

        def credential_loader(name: str) -> str:
            return environment[name]

        receipt = execute_forward_stream_attempt(
            execution_config,
            runtime_config,
            authority_phrase=args.authority,
            repository_root=ROOT,
            raw_root=args.raw_root,
            credential_loader=credential_loader,
            wss_exchange=wss_exchange,
            clock=lambda: datetime.now(UTC),
            nonce_factory=lambda: secrets.token_hex(4),
        )
        print(_safe_json(receipt))
        return 0
    except ForwardStreamExecutionError as exc:
        print(_safe_json({"error": exc.code, "result": "BLOCKED"}))
        return 2
    except ForwardStreamRuntimeError as exc:
        print(_safe_json({"error": str(exc), "result": "BLOCKED"}))
        return 2
    except Exception:
        print(_safe_json({"error": "UNCLASSIFIED_LOCAL_FAILURE", "result": "STOP"}))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
