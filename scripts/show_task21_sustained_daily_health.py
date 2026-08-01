from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task21_sustained_daily_health import (  # noqa: E402
    build_daily_health,
    canonical_json_bytes,
    render_daily_health_text,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render the offline synthetic TASK-21 sustained daily health view."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Render canonical JSON instead of the default Russian owner text.",
    )
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    view = build_daily_health(
        repo_root=ROOT,
        config_path=ROOT
        / "configs/task21_sustained_daily_health_read_model_v1.yaml",
        daily_input_path=ROOT
        / "tests/fixtures/task21/sustained_daily_health_receipt_v1.json",
    )
    if args.json:
        sys.stdout.buffer.write(canonical_json_bytes(view))
    else:
        sys.stdout.write(render_daily_health_text(view))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
