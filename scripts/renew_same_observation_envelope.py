"""Renew the live observation envelope when it is the same grant, shifted."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.observation_schedule_lifecycle import (  # noqa: E402
    ObservationLifecycleError,
)
from solana_alpha_lab.factory.observation_schedule_runtime import (  # noqa: E402
    DEFAULT_RUNTIME_RELATIVE,
    ObservationRuntimeError,
    git_sha,
    load_runtime_config,
    resolve_clock,
    resolve_data_root,
)
from solana_alpha_lab.factory.observation_schedule_store import (  # noqa: E402
    ObservationScheduleStore,
)
from solana_alpha_lab.factory.same_envelope_renewal import (  # noqa: E402
    exit_code,
    renew_same_envelope,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-config", default=DEFAULT_RUNTIME_RELATIVE)
    parser.add_argument("--data-root")
    args = parser.parse_args(argv)
    try:
        config = load_runtime_config(ROOT, args.runtime_config)
        if args.data_root:
            data_root = Path(args.data_root)
            if data_root.is_absolute() is False:
                raise ObservationRuntimeError("DATA_ROOT_NOT_ABSOLUTE")
            ops = data_root / "observation_schedule_state.sqlite"
        else:
            data_root = resolve_data_root(ROOT, str(config["data_root"]))
            ops = resolve_data_root(ROOT, str(config["ops_store_relative"]))
        store = ObservationScheduleStore(ops)
        try:
            result = renew_same_envelope(
                root=ROOT,
                data_root=data_root,
                store=store,
                now=resolve_clock(config),
                producer_git_sha=git_sha(ROOT, config.get("producer_git_sha")),
            )
        finally:
            store.close()
    except (ObservationLifecycleError, ObservationRuntimeError) as exc:
        result = {"terminal": str(exc)}
    text = json.dumps(result, sort_keys=True)
    if "AUTHORIZE OBSERVATION SCHEDULE" in text:
        result = {"terminal": "REFUSED_PROOF"}
        text = json.dumps(result, sort_keys=True)
    print(text)
    return exit_code(str(result.get("terminal") or ""))


if __name__ == "__main__":
    raise SystemExit(main())
