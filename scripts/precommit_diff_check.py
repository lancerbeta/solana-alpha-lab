"""Check new whitespace against exact incoming origin/main during its merge."""
from __future__ import annotations

import json
import re
import subprocess


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], capture_output=True, text=True)


def main() -> int:
    merge = git("rev-parse", "--verify", "MERGE_HEAD")
    upstream = git("rev-parse", "--verify", "refs/remotes/origin/main")
    incoming = merge.stdout.strip()
    baseline = None
    if (merge.returncode == upstream.returncode == 0
            and re.fullmatch(r"[0-9a-f]{40}", incoming)
            and incoming == upstream.stdout.strip()):
        baseline = incoming
    args = ["diff", "--cached", "--check"]
    if baseline:
        args.append(baseline)
    result = git(*args)
    print(json.dumps({"scope": "EXACT_INCOMING_ORIGIN_MAIN" if baseline else "ORDINARY_STAGED_DIFF",
                      "base": baseline, "status": "PASS" if result.returncode == 0 else "FAIL"}))
    # Native diagnostics remain terminal output, never persisted evidence.
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
