from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task24_entity_evidence_projection import (  # noqa: E402
    build_task24_projection,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the deterministic offline TASK-24 partial entity graph."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=(
            ROOT
            / "docs/evidence/task24/a3_entity_evidence_pre_read_manifest_v1.json"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "docs/evidence/task24/a3_projection_v1",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_task24_projection(
        repo_root=ROOT,
        manifest_path=args.manifest,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
