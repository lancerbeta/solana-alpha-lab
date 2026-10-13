"""Disposable, exact C1/C2 owner-path replay. Never writes a canonical data root."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from solana_alpha_lab.factory.live_cohort_source_bundle import sha256_file_streaming
from solana_alpha_lab.factory.observation_schedule import canonical_sha256
from solana_alpha_lab.factory.opportunity_episode_release import EpisodeReleaseError, import_episode_release, verify_episode_release

CANARY = ROOT / "local/canary_exit_and_100_per_day_arm_v1/20261013_resume"
C1 = ROOT / "local/opportunity_episodes_first_delivery/REL-20261007T000000Z-20261008T000000Z"
MIRROR = ROOT / "local/factory_mirror/observation_rdp"
PLANE = ROOT / "local/factory_v1/data_plane"


def copy_exact(src: Path, dest: Path, sha256: str) -> None:
    if not src.is_file() or src.is_symlink() or sha256_file_streaming(src) != sha256:
        raise RuntimeError("SOURCE_PIN_MISMATCH")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    if sha256_file_streaming(dest) != sha256:
        raise RuntimeError("COPY_PIN_MISMATCH")


def invoke(packet: Path, source: Path, mirror: Path, plane: Path, *, receipt_path: Path) -> dict:
    argv = [sys.executable, "-B", str(ROOT / "scripts/discovery_evidence_release.py"),
            "unpack-next-live-cohort", "--collection", "OPPORTUNITY_EPISODES",
            "--max-cohorts", "1", "--capture-packet", str(packet),
            "--source-rdp", str(source), "--mirror-rdp", str(mirror),
            "--data-root", str(plane), "--repo-root", str(ROOT),
            "--as-of", "2026-10-13T12:00:00Z"]
    began = time.monotonic()
    result = subprocess.run(argv, cwd=ROOT, text=True, capture_output=True, timeout=900, check=False)
    try:
        output = json.loads(result.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError) as exc:
        raise RuntimeError(f"CLI_OUTPUT_INVALID:{result.returncode}:{result.stderr[-200:]}") from exc
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_bytes((json.dumps({"exit_code": result.returncode,
                                          "wall_seconds": round(time.monotonic() - began, 2),
                                          "response": output}, sort_keys=True) + "\n").encode("utf-8"))
    if result.returncode or output.get("status") != "PASS":
        raise RuntimeError(f"CLI_REFUSED:{result.returncode}:{output.get('code') or output.get('next')}")
    results = output.get("result", {}).get("cohorts") or output.get("result", {}).get("results") or []
    if not results:
        raise RuntimeError(f"CLI_RESULT_INVALID:{str(output)[:500]}")
    return results[0]


def independent_source_oracle(packet: dict, source_root: Path, corpus_path: Path) -> dict:
    """Compare literal source field states and exact episode/point members with corpus."""

    episode_ids = {item["episode_id"] for item in packet["closure_receipt"]["episodes"]}
    source_states: Counter[tuple[str, str, str, str, str, str | None]] = Counter()
    source_pairs: set[tuple[str, str]] = set()
    for entry in packet["transfer_manifest"]["entries"]:
        if entry["source_class"] != "observation_parquet":
            continue
        path = source_root / str(entry.get("transfer_path") or entry["path"])
        for row in pq.read_table(path, columns=["episode_id", "point_id", "field_values"]).to_pylist():
            episode, point = row["episode_id"], row["point_id"]
            if episode not in episode_ids:
                continue
            source_pairs.add((episode, point))
            for field in row["field_values"] or []:
                source_states[(episode, point, field["primitive_id"], field["field_id"],
                               field["state"], field["missing_reason"])] += 1
    corpus = pq.read_table(corpus_path, columns=["episode_id", "point_id", "primitive_id", "field_id", "state", "missing_reason"])
    corpus_states = Counter((row["episode_id"], row["point_id"], row["primitive_id"], row["field_id"],
                             row["state"], row["missing_reason"]) for row in corpus.to_pylist())
    corpus_pairs = {(row["episode_id"], row["point_id"]) for row in corpus.to_pylist()}
    if source_pairs != corpus_pairs or source_states != corpus_states or {episode for episode, _ in corpus_pairs} != episode_ids:
        raise RuntimeError("SOURCE_CORPUS_MEMBERSHIP_OR_STATE_MISMATCH")
    frozen = json.dumps(sorted((list(key) + [count] for key, count in corpus_states.items()), key=str),
                        sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {"episodes": len(episode_ids), "pairs": len(corpus_pairs), "field_rows": sum(corpus_states.values()),
            "membership_state_sha256": hashlib.sha256(frozen).hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--resume", action="store_true", help="Continue the exact disposable proof after an interruption")
    parser.add_argument("--verify-existing", action="store_true", help="Cold verify the completed disposable proof state")
    parser.add_argument("--exercise-historical-fallback", action="store_true", help="Temporarily hide one C1 source version in the disposable copy")
    parser.add_argument("--exercise-imported-conflict", action="store_true", help="Temporarily alter one installed release dependency in the disposable copy")
    parser.add_argument("--exercise-metadata-conflict", action="store_true", help="Temporarily remove current corpus labels in the disposable copy")
    args = parser.parse_args()
    work = args.work_root.resolve()
    if work == ROOT or not work.is_relative_to(ROOT / "local"):
        raise SystemExit("WORK_ROOT_MUST_BE_UNDER_LOCAL")
    if args.resume or args.verify_existing:
        if not (work / "mirror" / "captures").is_dir() or not (work / "plane" / "datasets/opportunity_episodes_corpus/lineage.json").is_file():
            raise SystemExit("RESUME_STATE_MISSING")
    elif work.exists():
        raise SystemExit("WORK_ROOT_MUST_BE_NEW_UNDER_LOCAL")
    else:
        work.mkdir(parents=True)
    mirror, plane = work / "mirror", work / "plane"
    c1_packet = C1 / "capture-packet.json"
    c2_packet = CANARY / "c2-capture-packet.json"
    c1 = json.loads(c1_packet.read_bytes())
    c2 = json.loads(c2_packet.read_bytes())
    c2_inventory = []
    for entry in c2["transfer_manifest"]["entries"]:
        transfer_rel = str(entry.get("transfer_path") or entry["path"])
        source_file = CANARY / "c2-source-rdp" / transfer_rel
        if not source_file.is_file() or source_file.is_symlink() or source_file.stat().st_size != entry["bytes"] or sha256_file_streaming(source_file) != entry["sha256"]:
            raise RuntimeError("C2_SOURCE_PACKAGE_MISMATCH")
        c2_inventory.append({"path": transfer_rel, "bytes": entry["bytes"], "sha256": entry["sha256"]})
    c2_inventory_sha = canonical_sha256(sorted(c2_inventory, key=lambda item: item["path"]))
    start = time.monotonic()
    c1_release = MIRROR / "sealed_releases/OPPORTUNITY_EPISODES/2bfb07b6862365df-ACT-2BFB07B6862365DF/REL-20261007T000000Z-20261008T000000Z"
    local_release = mirror / c1_release.relative_to(MIRROR)
    if not (args.resume or args.verify_existing):
        for entry in c1["transfer_manifest"]["entries"]:
            rel = entry["path"]
            copy_exact(MIRROR / rel, mirror / rel, entry["sha256"])
        shutil.copytree(c1_release, local_release)
    c1_release_before = sha256_file_streaming(local_release / "release_manifest.json")
    if verify_episode_release(local_release)["release_id"] != "1128cbcad55e4f11f666722d5b967b1aa5b3c8624ca3dfb9d02981c5651fe47c":
        raise RuntimeError("C1_RELEASE_ID_MISMATCH")
    if not (args.resume or args.verify_existing):
        shutil.copytree(PLANE / "datasets/opportunity_episodes_corpus", plane / "datasets/opportunity_episodes_corpus")
        shutil.copytree(PLANE / "datasets/manifests", plane / "datasets/manifests")
    original_files = json.loads((CANARY / "c1-identity-before-c2.json").read_bytes())["files"]
    original = original_files["local/factory_v1/data_plane/datasets/opportunity_episodes_corpus/lineage.json"]["expected"]
    copied_c1_pins = 0
    c1_currentness_updates = 0
    for rel, pin in original_files.items():
        expected = pin["expected"]
        if sha256_file_streaming(ROOT / rel) != expected:
            raise RuntimeError("CANONICAL_C1_PIN_CHANGED")
        if rel.endswith("/lineage.json"):
            continue
        if rel.startswith("local/factory_mirror/observation_rdp/"):
            installed = mirror / rel.removeprefix("local/factory_mirror/observation_rdp/")
        elif rel.startswith("local/factory_v1/data_plane/"):
            installed = plane / rel.removeprefix("local/factory_v1/data_plane/")
        else:
            raise RuntimeError("C1_PIN_PATH_UNRECOGNIZED")
        if rel.endswith(".labels.json"):
            original_labels = json.loads((ROOT / rel).read_bytes())
            installed_labels = json.loads(installed.read_bytes())
            expected_currentness = not (args.resume or args.verify_existing)
            if original_labels.get("is_current_corpus_version") is not True or installed_labels.get("is_current_corpus_version") is not expected_currentness:
                raise RuntimeError("C1_CURRENTNESS_INCORRECT")
            installed_labels["is_current_corpus_version"] = True
            if installed_labels != original_labels:
                raise RuntimeError("C1_LABELS_CHANGED_BEYOND_CURRENTNESS")
            c1_currentness_updates += int(not expected_currentness)
        else:
            if sha256_file_streaming(installed) != expected:
                raise RuntimeError("COPIED_C1_PIN_CHANGED")
            copied_c1_pins += 1
    if args.verify_existing:
        from solana_alpha_lab.factory.live_cohort_vanilla_path import classify_mirror, episode_capture_source_root
        for packet in (c1, c2):
            view = episode_capture_source_root(packet["transfer_manifest"], mirror)
            if classify_mirror(packet["transfer_manifest"], view)["status"] != "READY" or not (view.parent / "transfer_manifest.json").is_file():
                raise RuntimeError("CAPTURE_VIEW_NOT_EXACT")
        c2_root = mirror / "sealed_releases/OPPORTUNITY_EPISODES/2bfb07b6862365df-ACT-2BFB07B6862365DF/REL-20261008T000000Z-20261009T000000Z"
        first_receipt = work / "receipts/c2-first.json"
        if first_receipt.is_file():
            recorded_first = json.loads(first_receipt.read_bytes())
            if recorded_first["exit_code"] != 0 or recorded_first["response"]["status"] != "PASS":
                raise RuntimeError("PUBLIC_FIRST_RECEIPT_NOT_PASS")
            first = {"import_status": recorded_first["response"]["result"]["cohorts"][0]["import_status"]}
        else:
            first = {"import_status": "COMMITTED_BEFORE_INTERRUPTED_READOUT"}
        proof_time = datetime(2026, 10, 13, 12, tzinfo=UTC)
        repeat = {"import_status": import_episode_release(release_root=c2_root, data_root=plane, import_time=proof_time)["status"], "epoch_bump": False}
        old = {"import_status": import_episode_release(release_root=local_release, data_root=plane, import_time=proof_time)["status"], "epoch_bump": False}
    else:
        print("C2 first/resume", file=sys.stderr, flush=True)
        first = invoke(c2_packet, CANARY / "c2-source-rdp", mirror, plane,
                       receipt_path=work / "receipts/c2-first.json")
        print("C2 exact repeat", file=sys.stderr, flush=True)
        repeat = invoke(c2_packet, CANARY / "c2-source-rdp", mirror, plane,
                        receipt_path=work / "receipts/c2-repeat.json")
        print("C1 historical replay", file=sys.stderr, flush=True)
        old = invoke(c1_packet, MIRROR, mirror, plane,
                     receipt_path=work / "receipts/c1-old-replay.json")
    if not (args.resume or args.verify_existing):
        original_label_rel = next(rel for rel in original_files if rel.endswith(".labels.json"))
        original_labels = json.loads((ROOT / original_label_rel).read_bytes())
        copied_labels = json.loads((plane / original_label_rel.removeprefix("local/factory_v1/data_plane/")).read_bytes())
        if copied_labels.get("is_current_corpus_version") is not False:
            raise RuntimeError("C1_CURRENTNESS_INCORRECT")
        copied_labels["is_current_corpus_version"] = True
        if copied_labels != original_labels:
            raise RuntimeError("C1_LABELS_CHANGED_BEYOND_CURRENTNESS")
        c1_currentness_updates = 1
    fallback = "NOT_EXERCISED"
    grown_fallback = "NOT_EXERCISED"
    if args.exercise_historical_fallback:
        if not args.verify_existing:
            raise RuntimeError("FALLBACK_REQUIRES_VERIFIED_DISPOSABLE_STATE")
        from solana_alpha_lab.factory.live_cohort_vanilla_path import episode_capture_source_root
        unit = next(item["path"] for item in c1["transfer_manifest"]["entries"] if item["source_class"] == "member_unit")
        view = episode_capture_source_root(c1["transfer_manifest"], mirror)
        temporarily_hidden = work / "temporary-hidden-source"
        temporarily_hidden.mkdir(exist_ok=True)
        paths = [mirror / unit, view / unit]
        backups = [temporarily_hidden / "shared-unit.json", temporarily_hidden / "view-unit.json"]
        if any(not path.is_file() or path.is_symlink() for path in paths) or any(path.exists() for path in backups):
            raise RuntimeError("FALLBACK_SOURCE_PRECONDITION")
        moved: list[tuple[Path, Path]] = []
        try:
            for path, backup in zip(paths, backups):
                os.replace(path, backup)
                moved.append((path, backup))
            result = invoke(c1_packet, work / "absent-c1-source", mirror, plane,
                            receipt_path=work / "receipts/c1-missing-source.json")
            batch = json.loads((work / "receipts/c1-missing-source.json").read_bytes())["response"]["result"]
            if (result.get("source_resolution") != "VERIFIED_IMPORTED_RELEASE" or
                    result.get("import_status") != "PASS_ALREADY_PRESENT_EXACT" or result.get("epoch_bump") or
                    batch.get("terminal") != "EPISODE_BATCH_REPLAY_SOURCE_MISSING" or
                    batch.get("source_unverified_n") != 1 or batch.get("newly_imported_n") != 0):
                raise RuntimeError("FALLBACK_RESULT_MISMATCH")
            fallback = "VERIFIED_IMPORTED_RELEASE"
        finally:
            for path, backup in reversed(moved):
                os.replace(backup, path)
        grown_root = work / "later-day-index"
        grown = grown_root / unit
        grown.parent.mkdir(parents=True, exist_ok=True)
        grown.write_bytes(b"a later day-open index version, not the historical C1 bytes")
        old_shared = paths[0].read_bytes()
        view_backup = temporarily_hidden / "view-unit-grown.json"
        if view_backup.exists():
            raise RuntimeError("GROWN_SOURCE_PRECONDITION")
        try:
            os.replace(paths[1], view_backup)
            paths[0].write_bytes(grown.read_bytes())
            result = invoke(c1_packet, grown_root, mirror, plane,
                            receipt_path=work / "receipts/c1-grown-source.json")
            batch = json.loads((work / "receipts/c1-grown-source.json").read_bytes())["response"]["result"]
            if (result.get("source_resolution") != "VERIFIED_IMPORTED_RELEASE" or
                    result.get("import_status") != "PASS_ALREADY_PRESENT_EXACT" or result.get("epoch_bump") or
                    batch.get("terminal") != "EPISODE_BATCH_REPLAY_SOURCE_MISSING" or
                    batch.get("source_unverified_n") != 1 or batch.get("newly_imported_n") != 0):
                raise RuntimeError("GROWN_SOURCE_FALLBACK_MISMATCH")
            grown_fallback = "VERIFIED_IMPORTED_RELEASE"
        finally:
            paths[0].write_bytes(old_shared)
            os.replace(view_backup, paths[1])
    lineage = json.loads((plane / "datasets/opportunity_episodes_corpus/lineage.json").read_bytes())
    imported_conflict = "NOT_EXERCISED"
    if args.exercise_imported_conflict:
        if not args.verify_existing:
            raise RuntimeError("CONFLICT_REQUIRES_VERIFIED_DISPOSABLE_STATE")
        installed_manifest = plane / lineage["cohorts"][1]["release_dir_rel"] / "release_manifest.json"
        exact = installed_manifest.read_bytes()
        try:
            installed_manifest.write_bytes(exact + b"\n")
            try:
                import_episode_release(release_root=c2_root, data_root=plane, import_time=proof_time)
            except EpisodeReleaseError as exc:
                if str(exc) != "CANONICAL_TARGET_CONFLICT":
                    raise
                imported_conflict = str(exc)
            else:
                raise RuntimeError("IMPORTED_CONFLICT_ACCEPTED")
        finally:
            installed_manifest.write_bytes(exact)
    metadata_conflict = "NOT_EXERCISED"
    if args.exercise_metadata_conflict:
        if not args.verify_existing:
            raise RuntimeError("METADATA_CONFLICT_REQUIRES_VERIFIED_DISPOSABLE_STATE")
        labels = plane / "datasets/manifests" / f"{lineage['current_dataset_manifest_id']}.labels.json"
        backup = work / "temporary-hidden-source" / "current-labels.json"
        backup.parent.mkdir(exist_ok=True)
        if not labels.is_file() or backup.exists():
            raise RuntimeError("METADATA_CONFLICT_PRECONDITION")
        try:
            os.replace(labels, backup)
            try:
                import_episode_release(release_root=c2_root, data_root=plane, import_time=proof_time)
            except EpisodeReleaseError as exc:
                if str(exc) != "CANONICAL_METADATA_CONFLICT":
                    raise
                metadata_conflict = str(exc)
            else:
                raise RuntimeError("MISSING_METADATA_ACCEPTED")
        finally:
            os.replace(backup, labels)
    pairs = []
    for item in lineage["cohorts"]:
        path = plane / item["obs_rel"]
        columns = pq.read_table(path, columns=["episode_id", "point_id"])
        pairs.append((item["admissions_n"], len(set(zip(columns["episode_id"].to_pylist(), columns["point_id"].to_pylist())))))
    if len(lineage["cohorts"]) != 2 or pairs != [(24, 3336), (23, 3197)]:
        raise RuntimeError("CORPUS_ORACLE_MISMATCH")
    c1_oracle = independent_source_oracle(c1, MIRROR, plane / lineage["cohorts"][0]["obs_rel"])
    c2_oracle = independent_source_oracle(c2, CANARY / "c2-source-rdp", plane / lineage["cohorts"][1]["obs_rel"])
    if (first.get("import_status") not in {"IMPORTED", "PASS_ALREADY_PRESENT_EXACT", "COMMITTED_BEFORE_INTERRUPTED_READOUT"} or
            repeat.get("import_status") != "PASS_ALREADY_PRESENT_EXACT" or repeat.get("epoch_bump") or
            old.get("import_status") != "PASS_ALREADY_PRESENT_EXACT" or old.get("epoch_bump") or
            sha256_file_streaming(local_release / "release_manifest.json") != c1_release_before):
        raise RuntimeError("REPLAY_OR_C1_IDENTITY_MISMATCH")
    public_receipts = {}
    for name in ("c2-first", "c2-repeat", "c1-old-replay", "c1-missing-source", "c1-grown-source"):
        receipt_path = work / "receipts" / f"{name}.json"
        if receipt_path.is_file():
            recorded = json.loads(receipt_path.read_bytes())
            cohorts = recorded["response"]["result"]["cohorts"]
            public_receipts[name] = {
                "sha256": sha256_file_streaming(receipt_path),
                "exit_code": recorded["exit_code"],
                "wall_seconds": recorded["wall_seconds"],
                "batch_terminal": recorded["response"]["result"]["terminal"],
                "import_status": cohorts[0]["import_status"],
                "transferred_files": cohorts[0].get("transferred_files"),
                "epoch_bump": cohorts[0].get("epoch_bump"),
            }
    if not (args.resume or args.verify_existing):
        if (set(public_receipts) & {"c2-first", "c2-repeat", "c1-old-replay"} !=
                {"c2-first", "c2-repeat", "c1-old-replay"}
                or public_receipts["c2-first"]["import_status"] != "IMPORTED"
                or public_receipts["c2-repeat"]["transferred_files"] != 0):
            raise RuntimeError("PUBLIC_RECEIPT_ORACLE_MISMATCH")
    if args.verify_existing and "c2-first" in public_receipts:
        if (not {"c2-first", "c2-repeat", "c1-old-replay"}.issubset(public_receipts)
                or public_receipts["c2-first"]["import_status"] != "IMPORTED"
                or public_receipts["c2-repeat"]["import_status"] != "PASS_ALREADY_PRESENT_EXACT"
                or public_receipts["c2-repeat"]["transferred_files"] != 0
                or public_receipts["c2-repeat"]["epoch_bump"] is not False
                or public_receipts["c1-old-replay"]["import_status"] != "PASS_ALREADY_PRESENT_EXACT"
                or any(public_receipts[name]["exit_code"] != 0 for name in ("c2-first", "c2-repeat", "c1-old-replay"))):
            raise RuntimeError("PUBLIC_RECEIPT_ORACLE_MISMATCH")
    c2_root = mirror / "sealed_releases/OPPORTUNITY_EPISODES/2bfb07b6862365df-ACT-2BFB07B6862365DF/REL-20261008T000000Z-20261009T000000Z"
    c2_verified = verify_episode_release(c2_root)
    output = {"status": "PASS", "c1_lineage_before_sha256": original,
              "c1_release_manifest_sha256": c1_release_before,
              "canonical_c1_pins_verified": len(original_files), "copied_c1_pins_verified": copied_c1_pins,
              "c1_currentness_updates": c1_currentness_updates,
              "c2_packet_sha256": hashlib.sha256(c2_packet.read_bytes()).hexdigest(),
              "c2_source_inventory_sha256": c2_inventory_sha,
              "c2_source_files": len(c2_inventory),
              "c2_source_payload_bytes": sum(item["bytes"] for item in c2_inventory),
              "c2_transfer_manifest_sha256": c2["transfer_manifest"]["manifest_sha256"],
              "c2_release_id": c2_verified["release_id"],
              "first_import": first["import_status"], "repeat_import": repeat["import_status"],
              "repeat_epoch_bump": repeat["epoch_bump"], "old_c1_replay": old["import_status"],
              "episodes": 47, "episode_point_pairs": 6533,
              "c1_oracle": c1_oracle, "c2_oracle": c2_oracle,
              "public_receipts": public_receipts,
              "proof_mode": ("COLD_PUBLIC_PATH_REPLAY" if first.get("import_status") == "IMPORTED" else
                             "COLD_POST_INTERRUPTED_PUBLIC_PATH") if args.verify_existing else "PUBLIC_PATH",
              "historical_missing_source_fallback": fallback,
              "historical_grown_source_fallback": grown_fallback,
              "tampered_installed_release_refusal": imported_conflict,
              "missing_current_labels_refusal": metadata_conflict,
              "wall_seconds": round(time.monotonic() - start, 2), "canonical_writes": 0}
    (work / "proof.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
