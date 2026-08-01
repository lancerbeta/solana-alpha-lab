"""Render or verify the deterministic TASK-22 A5 split resolution."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from solana_alpha_lab.task22_split_resolution import (
    LEDGER_PATH,
    SCHEMA_PATH,
    SPLIT_PATH,
    artifact_bytes,
    build_all,
    load_json,
)


ROOT = Path(__file__).resolve().parents[1]


def _outputs() -> dict[str, object]:
    manifest, ledger = build_all(ROOT)
    schema = load_json(ROOT / SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
    )
    validator.validate(manifest)
    validator.validate(ledger)
    return {"manifest": manifest, "ledger": ledger}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--render", choices=("manifest", "ledger"))
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()
    outputs = _outputs()

    if args.render:
        print(
            json.dumps(
                outputs[args.render],
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    paths = {"manifest": SPLIT_PATH, "ledger": LEDGER_PATH}
    if args.write:
        for name, relative in paths.items():
            path = ROOT / relative
            encoded = artifact_bytes(outputs[name])
            if path.exists():
                if path.read_bytes() != encoded:
                    raise SystemExit(f"create_only_conflict:{relative}")
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(encoded)
        print("TASK22_A5_CREATE_ONLY_WRITE=PASS")
        return 0

    for name, relative in paths.items():
        path = ROOT / relative
        if not path.is_file():
            raise SystemExit(f"missing_output:{relative}")
        if path.read_bytes() != artifact_bytes(outputs[name]):
            raise SystemExit(f"deterministic_output_drift:{relative}")
    print("TASK22_A5_DETERMINISTIC_CHECK=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
