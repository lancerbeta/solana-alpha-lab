from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from solana_alpha_lab.task30_two_slot_live_shakedown_owner_packet import (
    render_owner_packet_markdown,
    validate_owner_packet,
)

PACKET_PATH = ROOT / "configs" / "task30_two_slot_live_shakedown_owner_packet_v1.yaml"


def load_packet() -> dict[str, object]:
    loaded = yaml.safe_load(PACKET_PATH.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("owner packet must be a mapping")
    return loaded


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args()
    packet = load_packet()
    if args.format == "json":
        print(json.dumps(validate_owner_packet(packet), ensure_ascii=False, indent=2))
    else:
        print(render_owner_packet_markdown(packet), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
