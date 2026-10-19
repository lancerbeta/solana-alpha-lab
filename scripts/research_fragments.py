#!/usr/bin/env python3
"""Native fragment registration, source readback, prospective plans and cold resume."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from solana_alpha_lab.factory import research_fragments as fragments
from solana_alpha_lab.factory.research_store import ResearchStore, ResearchStoreError


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["read", "registration-preview", "register", "plan-preview", "plan-apply", "run-due", "protection-status", "protection-preview", "protection-apply"])
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--confirm-append-only", action="store_true")
    parser.add_argument("--authority", type=Path, help="Exact metadata-only installation scope JSON")
    parser.add_argument("--protection-metadata-max-bytes", type=int, default=16_777_216,
                        help="Explicit protection-apply JSON memory bound; separate from science/freshness")
    args = parser.parse_args()
    try:
        root = args.data_root
        if not root.is_absolute():
            raise fragments.FragmentError("FRAGMENT_ABSOLUTE_DATA_ROOT_REQUIRED")
        store = ResearchStore(root, create_if_missing=False)
        if args.action in {"register", "plan-apply", "run-due", "protection-apply"} and not args.confirm_append_only:
            raise fragments.FragmentError("FRAGMENT_APPEND_ONLY_CONFIRMATION_REQUIRED")
        request = {}
        if args.action not in {"read", "run-due", "protection-status", "protection-preview"}:
            if args.input is None:
                raise fragments.FragmentError("FRAGMENT_INPUT_REQUIRED")
            limit = args.protection_metadata_max_bytes if args.action == "protection-apply" else 1_048_576
            if limit < 1:
                raise fragments.FragmentError("PROTECTION_METADATA_INPUT_BOUND_INVALID")
            with args.input.open("rb") as stream:
                raw = stream.read(limit + 1)
            if len(raw) > limit:
                raise fragments.FragmentError("PROTECTION_METADATA_INPUT_LIMIT_EXCEEDED" if args.action == "protection-apply" else "FRAGMENT_INPUT_RESOURCE_LIMIT")
            request = json.loads(raw)
            if not isinstance(request, dict):
                raise fragments.FragmentError("FRAGMENT_INPUT_INVALID")
        git_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                                 capture_output=True, text=True).stdout.strip()
        if args.action.startswith("protection-"):
            from solana_alpha_lab.factory import episode_current_protection as protection
            if args.action == "protection-status":
                result = protection.resolve_current_research_protection(root)[0]
            elif args.action == "protection-preview":
                result = protection.preview_reconciliation(root)
            else:
                if args.authority is None:
                    raise protection.CurrentProtectionError("PROTECTION_INSTALLATION_AUTHORITY_REQUIRED")
                with args.authority.open("rb") as stream:
                    raw_authority = stream.read(args.protection_metadata_max_bytes + 1)
                if len(raw_authority) > args.protection_metadata_max_bytes:
                    raise protection.CurrentProtectionError("PROTECTION_METADATA_INPUT_LIMIT_EXCEEDED")
                authority = json.loads(raw_authority)
                if not isinstance(authority, dict):
                    raise protection.CurrentProtectionError("PROTECTION_INSTALLATION_AUTHORITY_REQUIRED")
                result = protection.apply_reconciliation(store, request, authority=authority)
        elif args.action == "read":
            result = {"fragments": fragments.source_snapshot(store), "data_root_identity_sha256": fragments.root_identity(store), "writes": False, "new_look": False}
        elif args.action == "registration-preview":
            result = fragments.registration_preview(store, request)
        elif args.action == "register":
            result = fragments.register(store, request, git_sha=git_sha)
        elif args.action == "plan-preview":
            result = fragments.plan_preview(store, request)
        elif args.action == "plan-apply":
            result = fragments.apply_plan(store, request, git_sha=git_sha)
        else:
            result = fragments.run_due(store, repo_root=ROOT, git_sha=git_sha)
        print(json.dumps(result, ensure_ascii=True, sort_keys=True, allow_nan=False))
        return 0
    except (ValueError, KeyError, TypeError, OSError, ResearchStoreError, subprocess.SubprocessError) as exc:
        reason = getattr(exc, "code", "FRAGMENT_INPUT_OR_SOURCE_INVALID")
        input_path = reason == "FRAGMENT_ABSOLUTE_DATA_ROOT_REQUIRED"
        from solana_alpha_lab.factory.episode_current_protection import CurrentProtectionError
        detail = exc.detail if isinstance(exc, CurrentProtectionError) else fragments.source_detail(exc)
        print(json.dumps({"status": "BLOCKED", "reason": reason, "new_look": False,
                          "owner": "INPUT" if input_path else "INPUT_OR_SOURCE",
                          "next_action": "CORRECT_ABSOLUTE_DATA_ROOT" if input_path else "CORRECT_INPUT_OR_SOURCE",
                          **detail}, ensure_ascii=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
