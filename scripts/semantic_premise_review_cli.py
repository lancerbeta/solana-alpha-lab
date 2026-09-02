#!/usr/bin/env python3
"""CLI for semantic-premise review profile classification and packet build."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.semantic_premise_review import (  # noqa: E402
    SemanticPremiseReviewError,
    build_semantic_premise_packet,
    classify_review_profile,
    evaluate_fixture_premise,
    load_profile,
    map_semantic_verdict_to_architecture,
    validate_launch_inputs,
    validate_packet_against_candidate,
)


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SemanticPremiseReviewError("JSON_OBJECT_REQUIRED")
    return payload


def _load_json_list(path: Path) -> list:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise SemanticPremiseReviewError("JSON_LIST_REQUIRED")
    return payload


def _packet_from_fixture(root: Path, fixture: dict) -> dict:
    profile = load_profile(root)
    return build_semantic_premise_packet(
        repo_root=root,
        task_id=str(fixture["task_id"]),
        task_contract_bytes=str(fixture.get("task_contract_text") or "").encode("utf-8"),
        base=str(fixture["base"]),
        head=str(fixture["head"]),
        diff_bytes=str(fixture.get("diff_text") or "").encode("utf-8"),
        semantic_claims=list(fixture["semantic_claims"]),
        non_claims=list(fixture.get("non_claims") or []),
        evidence=list(fixture.get("evidence") or []),
        risk_dimensions=list(fixture.get("risk_dimensions") or []),
        model_diversity=str(fixture.get("model_diversity") or "UNPROVEN"),
        model_diversity_identity=fixture.get("model_diversity_identity"),
        profile=profile,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    sub = parser.add_subparsers(dest="command", required=True)

    classify = sub.add_parser("classify")
    classify.add_argument("--changed-path", action="append", default=[])
    classify.add_argument("--task", type=Path)
    classify.add_argument("--force-profile", choices=["STANDARD", "SEMANTIC_PREMISE"])

    packet = sub.add_parser("build-packet")
    packet.add_argument("--fixture", type=Path)
    packet.add_argument("--task-id")
    packet.add_argument("--task", type=Path)
    packet.add_argument("--base")
    packet.add_argument("--head")
    packet.add_argument("--diff", type=Path)
    packet.add_argument("--claims-json", type=Path)
    packet.add_argument("--non-claims-json", type=Path)
    packet.add_argument("--evidence-json", type=Path)
    packet.add_argument("--risk-dimension", action="append", default=[])
    packet.add_argument("--model-diversity", default="UNPROVEN")
    packet.add_argument("--model-identity")
    packet.add_argument("--out", type=Path)

    validate = sub.add_parser("validate-packet")
    validate.add_argument("--packet", type=Path, required=True)
    validate.add_argument("--task", type=Path, required=True)
    validate.add_argument("--base", required=True)
    validate.add_argument("--head", required=True)
    validate.add_argument("--diff", type=Path, required=True)
    validate.add_argument("--claims-json", type=Path, required=True)
    validate.add_argument("--non-claims-json", type=Path, required=True)
    validate.add_argument("--evidence-json", type=Path, required=True)
    validate.add_argument("--risk-dimension", action="append", default=[])

    launch = sub.add_parser("validate-launch")
    launch.add_argument("--classification-json", type=Path, required=True)
    launch.add_argument("--packet", type=Path)
    launch.add_argument("--task", type=Path)
    launch.add_argument("--base")
    launch.add_argument("--head")
    launch.add_argument("--diff", type=Path)
    launch.add_argument("--claims-json", type=Path)
    launch.add_argument("--non-claims-json", type=Path)
    launch.add_argument("--evidence-json", type=Path)
    launch.add_argument("--risk-dimension", action="append", default=[])

    eval_cmd = sub.add_parser("evaluate-fixture")
    eval_cmd.add_argument("--fixture", type=Path, required=True)

    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        if args.command == "classify":
            task_text = (
                args.task.read_text(encoding="utf-8") if args.task is not None else None
            )
            result = classify_review_profile(
                changed_paths=list(args.changed_path),
                task_text=task_text,
                force_profile=args.force_profile,
                repo_root=root,
            )
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.command == "build-packet":
            if args.fixture is not None:
                built = _packet_from_fixture(root, _load_json(args.fixture))
            else:
                required = [
                    args.task_id,
                    args.task,
                    args.base,
                    args.head,
                    args.diff,
                    args.claims_json,
                    args.non_claims_json,
                    args.evidence_json,
                ]
                if any(item is None for item in required):
                    raise SemanticPremiseReviewError(
                        "BUILD_PACKET_REQUIRES_FIXTURE_OR_LIVE_ARGS"
                    )
                profile = load_profile(root)
                built = build_semantic_premise_packet(
                    repo_root=root,
                    task_id=str(args.task_id),
                    task_contract_bytes=args.task.read_bytes(),
                    base=str(args.base),
                    head=str(args.head),
                    diff_bytes=args.diff.read_bytes(),
                    semantic_claims=list(_load_json_list(args.claims_json)),
                    non_claims=[str(x) for x in _load_json_list(args.non_claims_json)],
                    evidence=list(_load_json_list(args.evidence_json)),
                    risk_dimensions=list(args.risk_dimension),
                    model_diversity=str(args.model_diversity),
                    model_diversity_identity=args.model_identity,
                    profile=profile,
                )
            if args.out is not None:
                args.out.write_text(
                    json.dumps(built, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
            print(json.dumps(built, indent=2, sort_keys=True))
            return 0
        if args.command == "validate-packet":
            packet = _load_json(args.packet)
            result = validate_packet_against_candidate(
                packet,
                repo_root=root,
                task_contract_bytes=args.task.read_bytes(),
                base=str(args.base),
                head=str(args.head),
                diff_bytes=args.diff.read_bytes(),
                semantic_claims=list(_load_json_list(args.claims_json)),
                non_claims=[str(x) for x in _load_json_list(args.non_claims_json)],
                evidence=list(_load_json_list(args.evidence_json)),
                risk_dimensions=list(args.risk_dimension),
            )
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.command == "validate-launch":
            classification = _load_json(args.classification_json)
            packet = _load_json(args.packet) if args.packet is not None else None
            binding_kwargs: dict = {}
            if classification.get("profile") == "SEMANTIC_PREMISE":
                required = [
                    args.task,
                    args.base,
                    args.head,
                    args.diff,
                    args.claims_json,
                    args.non_claims_json,
                    args.evidence_json,
                ]
                if any(item is None for item in required):
                    raise SemanticPremiseReviewError("SEMANTIC_PACKET_BINDING_INCOMPLETE")
                binding_kwargs = {
                    "task_contract_bytes": args.task.read_bytes(),
                    "base": str(args.base),
                    "head": str(args.head),
                    "diff_bytes": args.diff.read_bytes(),
                    "semantic_claims": list(_load_json_list(args.claims_json)),
                    "non_claims": [
                        str(x) for x in _load_json_list(args.non_claims_json)
                    ],
                    "evidence": list(_load_json_list(args.evidence_json)),
                    "risk_dimensions": list(args.risk_dimension)
                    or list(classification.get("risk_dimensions") or []),
                }
            result = validate_launch_inputs(
                classification=classification,
                packet=packet,
                repo_root=root,
                **binding_kwargs,
            )
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.command == "evaluate-fixture":
            fixture = _load_json(args.fixture)
            profile = load_profile(root)
            result = evaluate_fixture_premise(
                claims=list(fixture["semantic_claims"]),
                non_claims=list(fixture.get("non_claims") or []),
            )
            result["architecture_verdict"] = map_semantic_verdict_to_architecture(
                result["semantic_verdict"], profile
            )
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0 if result["architecture_verdict"] == "PASS" else 2
    except SemanticPremiseReviewError as exc:
        print(json.dumps({"error": str(exc)}, indent=2, sort_keys=True))
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
