"""Bounded local operator surface for the registered List A confirming path."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from solana_alpha_lab.factory.experiment_spec import load_experiment_spec
from solana_alpha_lab.factory.list_a_confirmation_inputs import (
    DEFINITION, ConfirmationError, authorize_confirmation, load_json,
    prepare_confirmation, revoke_confirmation, utc, write_native_confirmation_sample, register_source_authority,
)
from solana_alpha_lab.factory.list_a_confirmation import (
    bound_confirmation_checkpoint, trial_confirmation_checkpoint, read_confirmation, resume_confirmation,
)
from solana_alpha_lab.factory.lane_classifier import classify_lane
from solana_alpha_lab.factory.document_runner import DocumentRunner, RunContext
from solana_alpha_lab.factory.research_store import ResearchStore
from solana_alpha_lab.factory.run_passport import experiment_spec_sha256


def public_response(response: dict) -> dict:
    out = dict(response)
    result = out.pop("result", None)
    if result:
        out["result"] = {"identity": result["identity"], "method": result["method"],
            "population": {k: v for k, v in result["population"].items() if k != "membership"},
            "interval": [result["binding"]["interval_start"], result["binding"]["interval_end_exclusive"]]}
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Точный native List A confirmation; grant требует exact domain phrase.")
    parser.add_argument("command", choices=["register-source", "prepare", "authorize", "revoke", "classify", "submit", "status", "show", "resume"])
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--sample-ref")
    parser.add_argument("--source-input", type=Path)
    parser.add_argument("--binding-id")
    parser.add_argument("--trial-id")
    parser.add_argument("--owner-phrase")
    parser.add_argument("--valid-until")
    parser.add_argument("--as-of")
    args = parser.parse_args(argv)
    try:
        spec = load_experiment_spec(ROOT, DEFINITION)
        store = ResearchStore(args.data_root, create_if_missing=args.command == "register-source")
        now = utc(args.as_of) if args.as_of else datetime.now(UTC)
        if args.command == "register-source":
            sample_ref = args.sample_ref
            if args.source_input:
                payload = load_json(args.source_input)
                sample_ref = write_native_confirmation_sample(root=ROOT, store=store, **payload)
            if not sample_ref:
                raise ConfirmationError("SOURCE_INPUT_REQUIRED")
            result = register_source_authority(sample_ref, root=ROOT, store=store, owner_phrase=args.owner_phrase)
        elif args.command == "prepare":
            result = prepare_confirmation(spec, args.sample_ref or "", root=ROOT, store=store, now=now)
        elif args.command == "authorize":
            result = authorize_confirmation(spec, args.binding_id or "", root=ROOT, store=store, now=now,
                owner_phrase=args.owner_phrase or "", valid_until=args.valid_until or "")
        elif args.command == "revoke":
            result = revoke_confirmation(args.binding_id or "", root=ROOT, store=store, owner_phrase=args.owner_phrase)
        elif args.command in {"show", "status"}:
            result = read_confirmation(store, trial_id=args.trial_id or "", root=ROOT)
        elif args.command == "resume":
            result = resume_confirmation(store, trial_id=args.trial_id or "", root=ROOT, definition=spec,
                current_context={"binding_id": args.binding_id, "now": now})
        else:
            lane = classify_lane({"experiment_spec": spec, "execution_binding_id": args.binding_id},
                                 root=ROOT, data_root=store.root, as_of=now)
            if args.command == "classify":
                result = asdict(lane)
            else:
                if lane.terminal not in {"FAST_LANE_READY", "REPLAY_AVAILABLE", "RESUME_REQUIRED"}:
                    result = {**(getattr(lane, "confirmation_checkpoint", None) or {"scientific_charge": None}),
                              "status": lane.terminal, "reason_codes": list(lane.reason_codes),
                              "next_action": lane.next_action}
                else:
                    result = DocumentRunner(root=ROOT, store=None).start_document(spec,
                        spec_sha256=experiment_spec_sha256(spec), run_context=RunContext(store.root, "0" * 64, lane),
                        capture_hooks={"execution_context": {"binding_id": args.binding_id, "now": now}})
        print(json.dumps(public_response(result), ensure_ascii=False, sort_keys=True, allow_nan=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError, RuntimeError) as exc:
        checkpoint = {"scientific_charge": None}
        if args.command in {"status", "show"} and args.trial_id:
            try:
                checkpoint = trial_confirmation_checkpoint(ResearchStore(args.data_root, create_if_missing=False), args.trial_id)
            except (ValueError, OSError, KeyError, TypeError, RuntimeError):
                pass
        elif args.command in {"submit", "resume", "classify", "authorize", "revoke"} and args.binding_id:
            try:
                checkpoint = bound_confirmation_checkpoint(ResearchStore(args.data_root, create_if_missing=False), args.binding_id)
            except (ValueError, OSError, KeyError, TypeError, RuntimeError):
                pass  # Unavailable committed metadata stays UNKNOWN/null.
        charged_cold = args.command in {"status", "show"} and checkpoint.get("scientific_charge") == 1
        immature = getattr(exc, "code", None) == "TARGET_NOT_MATURE_AT_CUTOFF" and checkpoint.get("scientific_charge") != 1
        print(json.dumps({**checkpoint, "status": "UNVERIFIABLE" if charged_cold else "BOUND_CONTRACT_NOT_READY" if immature else "REFUSED",
                          "reason_codes": [getattr(exc, "code", "CONFIRMATION_INPUT_OR_RUNTIME_INVALID")],
                          "next_action": "VERIFY_SAVED_ARTIFACT_KEEP_CONSUMED_ALLOWANCE" if charged_cold else
                                         "WAIT_FOR_MATURITY_THEN_SEPARATELY_REBIND_EXACT_SAMPLE" if immature else
                                         "VERIFY_EXACT_INPUT_AND_SAVED_CHECKPOINT"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
