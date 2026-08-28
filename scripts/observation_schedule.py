#!/usr/bin/env python3
"""ObservationSchedule operator CLI. No arbitrary URLs, SQL, or output paths."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    ObservationScheduleError,
    load_observation_schedule,
)
from solana_alpha_lab.factory.observation_schedule_compiler import (  # noqa: E402
    compile_schedule_document,
)
from solana_alpha_lab.factory.observation_schedule_lifecycle import (  # noqa: E402
    ObservationLifecycleError,
    activate_schedule,
    authorize_schedule,
    pause_schedule,
    register_schedule,
    snapshot_schedule,
    status_schedule,
)
from solana_alpha_lab.factory.observation_schedule_runtime import (  # noqa: E402
    DEFAULT_RUNTIME_RELATIVE,
    ObservationRuntimeError,
    build_opener,
    git_sha,
    load_credential_after_activation,
    load_runtime_config,
    resolve_clock,
    resolve_data_root,
)
from solana_alpha_lab.factory.observation_panel_publisher import (  # noqa: E402
    ObservationPanelPublisherError,
    PublicationFault,
)
from solana_alpha_lab.factory.observation_primitive_registry import (  # noqa: E402
    PrimitiveRegistryError,
)
from solana_alpha_lab.factory.observation_schedule_store import (  # noqa: E402
    ObservationScheduleStore,
    ObservationScheduleStoreError,
)
from solana_alpha_lab.factory.observation_scheduler import (  # noqa: E402
    ObservationSchedulerError,
    tick_once,
)

SAFE_PREFIXES = ("local/", "tests/fixtures/observation_schedule/", "configs/")


def _safe_relative(root: Path, relative: str) -> Path:
    path = Path(relative)
    posix = PurePosixPath(relative)
    windows = PureWindowsPath(relative)
    if (
        path.is_absolute()
        or posix.is_absolute()
        or windows.is_absolute()
        or bool(windows.drive)
        or ".." in posix.parts
        or ".." in windows.parts
    ):
        raise SystemExit("PATH_UNSAFE")
    normalized = relative.replace("\\", "/")
    if not normalized.startswith(SAFE_PREFIXES) and not normalized.startswith("tests/fixtures/"):
        raise SystemExit("PATH_UNSAFE")
    return root / relative


def _emit(payload: dict, code: int) -> int:
    print(json.dumps(payload, sort_keys=True))
    return code


def _bind_runtime(args: argparse.Namespace) -> tuple[dict, Path, ObservationScheduleStore]:
    relative = getattr(args, "runtime_config", None) or DEFAULT_RUNTIME_RELATIVE
    config = load_runtime_config(ROOT, relative)
    explicit = getattr(args, "data_root", None)
    if explicit:
        resolved = Path(explicit)
        if resolved.is_absolute() is False:
            raise ObservationRuntimeError("DATA_ROOT_NOT_ABSOLUTE")
        ops = resolved / "observation_schedule_state.sqlite"
    else:
        resolved = resolve_data_root(ROOT, str(config["data_root"]))
        ops = resolve_data_root(ROOT, str(config["ops_store_relative"]))
    store = ObservationScheduleStore(ops)
    return config, resolved, store


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in (
        "validate",
        "compile",
        "register",
        "authorize",
        "activate",
        "pause",
        "status",
        "snapshot",
        "doctor",
    ):
        cmd = sub.add_parser(name)
        cmd.add_argument("--schedule")
        cmd.add_argument("--runtime-config", default=DEFAULT_RUNTIME_RELATIVE)
        cmd.add_argument("--data-root")
        if name == "authorize":
            cmd.add_argument("--phrase", required=True)
        if name in {"activate", "pause", "snapshot"}:
            cmd.add_argument("--activation-id", required=True)
        if name in {"authorize", "activate", "pause", "snapshot", "status"}:
            cmd.add_argument("--schedule-sha256")
    tick = sub.add_parser("tick")
    tick.add_argument("--once", action="store_true", required=True)
    tick.add_argument("--runtime-config", default=DEFAULT_RUNTIME_RELATIVE)
    tick.add_argument("--data-root")
    tick.add_argument("--schedule-sha256")
    tick.add_argument("--activation-id")
    args = parser.parse_args(argv)
    try:
        if args.command in {"validate", "compile"}:
            if not args.schedule:
                return _emit({"terminal": "SCHEDULE_PATH_REQUIRED"}, 2)
            document = load_observation_schedule(ROOT, args.schedule)
            if args.command == "validate":
                return _emit(
                    {"terminal": "VALIDATED", "schedule_sha256": document["schedule_sha256"]},
                    0,
                )
            result = compile_schedule_document(document, root=ROOT)
            return _emit(
                {
                    "terminal": result.terminal,
                    "schedule_sha256": result.schedule_sha256,
                    "next_action": result.next_action,
                },
                0 if result.schedule_sha256 else 2,
            )
        config, data_root, store = _bind_runtime(args)
        now = resolve_clock(config)
        producer = git_sha(ROOT, config.get("producer_git_sha"))
        if args.command == "register":
            if not args.schedule:
                return _emit({"terminal": "SCHEDULE_PATH_REQUIRED"}, 2)
            document = load_observation_schedule(ROOT, args.schedule)
            result = register_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                document=document,
                now=now,
                producer_git_sha=producer,
            )
            code = 0 if result.get("schedule_sha256") else 2
            return _emit(result, code)
        if args.command == "authorize":
            digest = args.schedule_sha256
            if not digest and args.schedule:
                digest = load_observation_schedule(ROOT, args.schedule)["schedule_sha256"]
            if not digest:
                return _emit({"terminal": "SCHEDULE_SHA256_REQUIRED"}, 2)
            result = authorize_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule_sha256=digest,
                phrase=args.phrase,
                now=now,
                producer_git_sha=producer,
            )
            return _emit(result, 0)
        if args.command == "activate":
            digest = args.schedule_sha256 or config.get("schedule_sha256")
            if not digest and args.schedule:
                digest = load_observation_schedule(ROOT, args.schedule)["schedule_sha256"]
            if not digest:
                return _emit({"terminal": "SCHEDULE_SHA256_REQUIRED"}, 2)
            result = activate_schedule(
                data_root=data_root,
                store=store,
                schedule_sha256=digest,
                activation_id=args.activation_id,
                now=now,
                producer_git_sha=producer,
            )
            return _emit(result, 0)
        if args.command == "pause":
            digest = args.schedule_sha256 or config.get("schedule_sha256")
            if not digest:
                return _emit({"terminal": "SCHEDULE_SHA256_REQUIRED"}, 2)
            result = pause_schedule(
                data_root=data_root,
                store=store,
                schedule_sha256=digest,
                activation_id=args.activation_id,
                now=now,
                producer_git_sha=producer,
            )
            return _emit(result, 0)
        if args.command == "status":
            result = status_schedule(
                store,
                schedule_sha256=getattr(args, "schedule_sha256", None) or config.get("schedule_sha256"),
                activation_id=getattr(args, "activation_id", None) or config.get("activation_id"),
            )
            return _emit(result, 0)
        if args.command == "snapshot":
            digest = args.schedule_sha256 or config.get("schedule_sha256")
            if not digest:
                return _emit({"terminal": "SCHEDULE_SHA256_REQUIRED"}, 2)
            result = snapshot_schedule(
                data_root=data_root,
                store=store,
                schedule_sha256=digest,
                activation_id=args.activation_id,
                now=now,
                producer_git_sha=producer,
            )
            return _emit(result, 0)
        if args.command == "doctor":
            unresolved = store.restore_marker_unresolved()
            activations = store.list_activations()
            return _emit(
                {
                    "terminal": "DOCTOR_OK",
                    "live_activation": any(row["state"] == "ACTIVE" for row in activations),
                    "restore_marker_unresolved": unresolved,
                    "activation_count": len(activations),
                    "ops_store": str(store.path),
                },
                0,
            )
        if args.command == "tick":
            digest = args.schedule_sha256 or config.get("schedule_sha256")
            activation_id = args.activation_id or config.get("activation_id")
            if not digest or not activation_id:
                return _emit(
                    {
                        "terminal": "TICK_REFUSED_NO_LIVE_DEFAULT",
                        "reason": "runtime config has no authorized activation",
                    },
                    2,
                )
            registered = store.get_registered_schedule(digest)
            activation = store.get_activation(digest, str(activation_id))
            if registered is None or activation is None or activation["state"] != "ACTIVE":
                return _emit(
                    {
                        "terminal": "TICK_REFUSED_NO_LIVE_DEFAULT",
                        "reason": "activation missing or not ACTIVE",
                        "schedule_sha256": digest,
                        "activation_id": activation_id,
                    },
                    2,
                )
            authority = store.latest_authority_for_schedule(digest)
            if authority is None:
                return _emit({"terminal": "AUTHORITY_MISSING"}, 2)
            from solana_alpha_lab.factory.observation_schedule import parse_utc as _parse_utc

            if _parse_utc(str(authority["expires_at"])) <= now:
                return _emit({"terminal": "AUTHORITY_EXPIRED"}, 2)
            opener = build_opener(ROOT, config)
            credential_holder: dict[str, str] = {}

            def _load() -> str:
                if "value" not in credential_holder:
                    credential_holder["value"] = load_credential_after_activation(config)
                return credential_holder["value"]

            result = tick_once(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule=registered["document"],
                activation_id=str(activation_id),
                now=now,
                opener=opener,
                credential_loader=_load if opener is not None else None,
                producer_git_sha=producer,
                fault_after=os.environ.get("OBSERVATION_SCHEDULE_PUBLISH_FAULT")
                or config.get("publish_fault_after"),
            )
            return _emit(result, 0 if result.get("terminal") == "TICK_COMPLETE" else 2)
        return _emit({"terminal": "COMMAND_UNKNOWN"}, 2)
    except (
        ObservationLifecycleError,
        ObservationRuntimeError,
        ObservationSchedulerError,
        ObservationScheduleError,
        ObservationScheduleStoreError,
        ObservationPanelPublisherError,
        PublicationFault,
        PrimitiveRegistryError,
    ) as exc:
        return _emit({"terminal": str(exc)}, 2)
    finally:
        if "store" in locals():
            store.close()


if __name__ == "__main__":
    raise SystemExit(main())
