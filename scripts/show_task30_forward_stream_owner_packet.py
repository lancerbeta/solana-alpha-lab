"""Render the tracked TASK-30 A13 owner packet without external I/O."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task30_forward_stream_owner_packet import (  # noqa: E402
    render_forward_stream_owner_packet,
)


def main() -> None:
    """Print the exact zero-authority owner packet from tracked policy."""
    config_path = ROOT / "configs/task30_forward_stream_owner_packet_v1.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    print(render_forward_stream_owner_packet(config), end="")


if __name__ == "__main__":
    main()
