"""Show the fail-closed, path-redacted TASK-34A context card."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task34a_documentation_foundation import (  # noqa: E402
    ContextBindingError,
    evaluate_context,
    render_context_text,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Show the activated Project Sources release without exposing local mirror paths."
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument(
        "--sources-dir",
        type=Path,
        default=None,
        help="Optional local Sources directory; read-only and redacted from output.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = evaluate_context(ROOT, args.sources_dir)
    except ContextBindingError as error:
        print("TASK34A_CONTEXT: FAIL", file=sys.stderr)
        print(f"error={error}", file=sys.stderr)
        return 1
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render_context_text(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
