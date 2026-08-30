#!/usr/bin/env python3
"""Render .github/workflows/ci.yml from the exact validate_ci contract."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import validate_ci as ci  # noqa: E402


def render_workflow() -> str:
    plan = ci.load_shard_plan()
    shard_count = plan["shard_count"]
    shard_lines = "\n".join(f"          - {index}" for index in range(shard_count))
    shard_command = ci.SHARD_RUN_COMMAND_TEMPLATE.format(shard_count=shard_count)
    aggregator = ci.AGGREGATOR_DENY_SCRIPT
    # Indent aggregator script for a YAML literal block.
    aggregator_block = "\n".join(
        ("          " + line) if line else "" for line in aggregator.splitlines()
    )
    return f"""name: Repository validation

on:
  workflow_dispatch:
  pull_request:
    branches:
      - main
  push:
    branches:
      - main

permissions:
  contents: read

concurrency:
  group: ${{{{ github.workflow }}}}-${{{{ github.ref }}}}
  cancel-in-progress: true

jobs:
  validate-core:
    runs-on: ubuntu-24.04
    timeout-minutes: {ci.GITHUB_VALIDATE_TIMEOUT_MINUTES}
    env:
      UV_NO_ENV_FILE: "1"
      PYTHONDONTWRITEBYTECODE: "1"
    steps:
      - name: Check out repository
        uses: {ci.CHECKOUT_PIN} # v7.0.0
        with:
          persist-credentials: false
          fetch-depth: 0
      - name: Install pinned uv and Python
        uses: {ci.SETUP_UV_PIN} # v8.3.2
        with:
          version: "{ci.EXPECTED_UV}"
          checksum: "{ci.LINUX_UV_CHECKSUM}"
          python-version: "{".".join(map(str, ci.EXPECTED_PYTHON))}"
          enable-cache: false
      - name: Configure local hooks
        run: git config --local core.hooksPath .githooks
      - name: Validate repository
        run: {ci.CORE_ONLY_COMMAND}

  validate-tests:
    runs-on: ubuntu-24.04
    timeout-minutes: {ci.GITHUB_VALIDATE_TIMEOUT_MINUTES}
    env:
      UV_NO_ENV_FILE: "1"
      PYTHONDONTWRITEBYTECODE: "1"
    strategy:
      fail-fast: false
      max-parallel: {shard_count}
      matrix:
        shard:
{shard_lines}
    steps:
      - name: Check out repository
        uses: {ci.CHECKOUT_PIN} # v7.0.0
        with:
          persist-credentials: false
          fetch-depth: 0
      - name: Install pinned uv and Python
        uses: {ci.SETUP_UV_PIN} # v8.3.2
        with:
          version: "{ci.EXPECTED_UV}"
          checksum: "{ci.LINUX_UV_CHECKSUM}"
          python-version: "{".".join(map(str, ci.EXPECTED_PYTHON))}"
          enable-cache: false
      - name: Configure local hooks
        run: git config --local core.hooksPath .githooks
      - name: Validate repository
        run: {shard_command}

  validate:
    if: ${{{{ always() }}}}
    needs:
      - validate-core
      - validate-tests
    runs-on: ubuntu-24.04
    timeout-minutes: {ci.GITHUB_AGGREGATOR_TIMEOUT_MINUTES}
    env:
      CORE_RESULT: ${{{{ needs.validate-core.result }}}}
      TESTS_RESULT: ${{{{ needs.validate-tests.result }}}}
    steps:
      - name: Deny non-success core or shard results
        run: |
{aggregator_block}
"""


def main() -> int:
    text = render_workflow()
    path = ROOT / ".github/workflows/ci.yml"
    path.write_text(text, encoding="utf-8")
    ci.validate_workflow_text(text)
    print(f"wrote {path.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
