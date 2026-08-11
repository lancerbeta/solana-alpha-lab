from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task30_forward_stream_runtime import (  # noqa: E402
    evaluate_forward_stream_runtime,
    render_forward_stream_runtime,
)


def main() -> None:
    config_path = ROOT / "configs/task30_forward_stream_runtime_harness_v1.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    evaluate_forward_stream_runtime(config)
    print(render_forward_stream_runtime(config), end="")


if __name__ == "__main__":
    main()
