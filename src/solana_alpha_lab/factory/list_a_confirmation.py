"""One registered confirming executor: durable reservation before values.

The operational lock is owned by the OS for the entire evaluation. The durable
scientific charge survives process death; only exact resume can reuse it.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import subprocess
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import jsonschema
import pyarrow.parquet as pq

from solana_alpha_lab.factory.list_a_confirmation_inputs import (
    CAPABILITY, ConfirmationError, event, inspect_confirmation, load_json,
    publish, records, require, safe_path, utc, validate_confirmation_result, SOURCE_OWNER, validate_exact_grant,
)
from solana_alpha_lab.factory.list_a_confirmation_method import (
    CORE_SHA, NUMERIC_REFUSALS, PARTITIONS, block_for, calculate_list_a, digest, finite_bytes,
)
from solana_alpha_lab.factory.hfic_temporal_discovery import (
    GroundedDiscoveryError, confirmation_price_cell, confirmation_price_relative,
)
from solana_alpha_lab.factory.opportunity_episodes import resolve_point
from solana_alpha_lab.factory.research_store import RecordKind, ResearchStore, ResearchStoreError
from solana_alpha_lab.factory.run_passport import compute_run_key_sha256, validate_run_passport

VALUE_COLUMNS = ["episode_id", "cohort_id", "release_id", "mint", "point_id", "field_id", "state", "typed_value",
    "observation_clock_policy", "source_price_event_time", "primitive_id", "call_occurrence_id", "request_sha256",
    "request_started_at", "response_received_at", "first_reliable_available_at"]


@contextlib.contextmanager
def study_lock(data_root: Path, budget_sha: str):
    """Kernel-owned local lock, no TTL, no live evaluator takeover."""
    require(bool(re.fullmatch(r"[0-9a-f]{64}", budget_sha)), "STUDY_ID_INVALID")
    relative = f"confirmation/locks/{budget_sha}.lock"
    path = safe_path(data_root, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open("a+b")
    try:
        if path.stat().st_size == 0:
            stream.write(b"\0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            elif os.name == "posix":
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            else:
                raise ConfirmationError("STUDY_LOCK_PLATFORM_UNSUPPORTED")
        except OSError as exc:
            raise ConfirmationError("STUDY_EVALUATOR_BUSY") from exc
        yield
    finally:
        stream.close()  # OS releases on close or process death.


def committed(store, record_id: str) -> dict | None:
    matches = [r for r in records(store) if r["record_id"] == record_id]
    require(len(matches) <= 1, "COMMITTED_IDENTITY_CONFLICT")
    return matches[0] if matches else None


def confirmation_checkpoint(store, binding_id: str) -> dict:
    """Committed charge/identity only; independent of current execution authority.

    This never decodes observations or result values. A read/identity failure
    raises: callers must project UNKNOWN, never infer an unspent allowance.
    """
    require(bool(re.fullmatch(r"[0-9a-f]{64}", binding_id)), "EXECUTION_BINDING_UNBOUND")
    matches = [r for r in records(store) if r["kind"] == "RESEARCH_ARTIFACT" and
               r["payload"].get("type") == "CONFIRMATION_RESERVATION" and
               r["payload"].get("execution_binding_sha256") == binding_id]
    require(len(matches) <= 1, "COMMITTED_RESERVATION_CONFLICT")
    if not matches:
        return {"execution_binding_sha256": binding_id, "scientific_charge": 0,
                "trial_id": None, "run_id": None, "run_key_sha256": None, "domain": None}
    record, payload = matches[0], matches[0]["payload"]
    trial_id = "LA-TRIAL-" + digest({"binding": binding_id, "grant": payload["grant_id"], "protocol": CORE_SHA}).upper()
    require(record["producer"] == CAPABILITY and record["record_id"] == "LA-RESERVATION-" + trial_id[9:] and
            payload["trial_id"] == trial_id and payload["scientific_charge"] == 1 and
            payload["protocol_core_sha256"] == CORE_SHA and
            compute_run_key_sha256(payload["run_key_inputs"]) == payload["run_key_sha256"] and
            payload["run_id"] == "RUN-" + payload["run_key_sha256"][:24].upper(), "COMMITTED_RESERVATION_INVALID")
    return {key: payload[key] for key in
            ("execution_binding_sha256", "scientific_charge", "trial_id", "run_id", "run_key_sha256", "domain")}


def trial_confirmation_checkpoint(store, trial_id: str) -> dict:
    """Recover a validated consumed identity without opening result values."""
    require(bool(re.fullmatch(r"LA-TRIAL-[0-9A-F]{64}", trial_id)), "TRIAL_ID_INVALID")
    matches = [r for r in records(store) if r["kind"] == "RESEARCH_ARTIFACT" and
               r["payload"].get("type") == "CONFIRMATION_RESERVATION" and
               r["payload"].get("trial_id") == trial_id]
    require(len(matches) == 1, "RESERVATION_NOT_FOUND_OR_CONFLICT")
    checkpoint = confirmation_checkpoint(store, matches[0]["payload"]["execution_binding_sha256"])
    require(checkpoint["scientific_charge"] == 1 and checkpoint["trial_id"] == trial_id,
            "COMMITTED_RESERVATION_INVALID")
    return checkpoint


def bound_confirmation_checkpoint(store, binding_id: str) -> dict:
    """Include consumed acquisition of a previously prepared alias, no values."""
    checkpoint = confirmation_checkpoint(store, binding_id)
    if checkpoint["scientific_charge"] == 1:
        return checkpoint
    prepared = committed(store, "LA-BINDING-" + binding_id)
    if prepared is None:
        return checkpoint
    binding = {k: v for k, v in prepared["payload"].items() if k not in {"execution_binding_sha256", "artifact_ref"}}
    require(prepared["kind"] == "RESEARCH_ARTIFACT" and prepared["producer"] == CAPABILITY and
            prepared["payload"]["execution_binding_sha256"] == digest(binding) == binding_id and
            binding["type"] == "EXECUTION_BINDING", "COMMITTED_BINDING_INVALID")
    from solana_alpha_lab.factory.list_a_confirmation_inputs import spent_confirmation_checkpoint
    checkpoint = spent_confirmation_checkpoint(store, binding_id, binding)
    if checkpoint["execution_binding_sha256"] != binding_id:
        checkpoint = {**checkpoint, "requested_execution_binding_sha256": binding_id}
    return checkpoint


def current_context(spec: dict, binding_id: str, *, root: Path, store: ResearchStore, now: datetime) -> dict:
    now = max(now, datetime.now(UTC))
    require(bool(re.fullmatch(r"[0-9a-f]{64}", binding_id)), "EXECUTION_BINDING_UNBOUND")
    binding = load_json(safe_path(store.root, f"confirmation/bindings/{binding_id}.json"))
    context = inspect_confirmation(spec, binding["sample_ref"], root=root, data_root=store.root, now=now)
    require(digest(binding) == binding_id == digest(context["binding"]), "EXECUTION_BINDING_STALE")
    prepared = committed(store, "LA-BINDING-" + binding_id)
    require(prepared is not None and prepared["payload"].get("execution_binding_sha256") == binding_id, "BINDING_NOT_COMMITTED")
    history = records(store)
    candidates = [r for r in history if r["payload"].get("type") == "CONFIRMATION_GRANT" and
                  r["payload"].get("execution_binding_sha256") == binding_id]
    require(len(candidates) == 1, "EXACT_GRANT_UNBOUND_OR_CONFLICT")
    grant = candidates[0]
    p = grant["payload"]
    validate_exact_grant(grant, binding, binding_id)
    require(utc(p["valid_until"]) > now and p["domain"] == binding["domain"] and
            p["source_set_sha256"] == binding["source_set_sha256"] and p["protocol_core_sha256"] == CORE_SHA and
            p["study_budget_sha256"] == binding["study_budget_sha256"] and p["source_id"] == binding["source_id"] and
            p["executor"] == CAPABILITY and p["purpose"] == "ALLOW_EXACT_CONFIRMATION" and
            p["max_scientific_attempts"] == 1 and p["role"] == "UNTOUCHED_FORWARD_HOLDOUT", "EXACT_GRANT_INVALID")
    require(not any(r["payload"].get("type") == "GRANT_REVOKED" and
                    r["payload"].get("grant_id") == grant["record_id"] for r in history), "GRANT_REVOKED")
    trial_sha = digest({"binding": binding_id, "grant": grant["record_id"], "protocol": CORE_SHA})
    context.update(binding_id=binding_id, grant=grant, trial_id="LA-TRIAL-" + trial_sha.upper(),
                   reservation_id="LA-RESERVATION-" + trial_sha.upper())
    spent = [r for r in history if r["payload"].get("type") == "CONFIRMATION_RESERVATION" and
             (r["payload"].get("study_budget_sha256") == binding["study_budget_sha256"] or
              set(r["payload"].get("acquisition_keys", [])).intersection(binding["acquisition_keys"]))]
    require(all(r["record_id"] in {context["reservation_id"], "LA-STARTED-" + context["trial_id"]} for r in spent),
            "SCIENTIFIC_ALLOWANCE_EXHAUSTED")
    return context


def run_identity(context: dict, root: Path) -> dict:
    b = context["binding"]
    git_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True,
                             capture_output=True).stdout.decode("ascii").strip()
    inputs = {"hypothesis_definition_sha256": CORE_SHA, "experiment_spec_sha256": b["experiment_spec_sha256"],
        "capability_id": CAPABILITY, "capability_closure_sha256": digest(b["qualification"]["closure"]),
        "runner_git_sha": git_sha, "uv_lock_sha256": b["qualification"]["closure"]["uv.lock"],
        "ordered_input_dataset_manifest_ids": [], "ordered_input_dataset_fingerprints": [b["source_set_sha256"]],
        "ordered_query_recipe_ids": [b["query"]["query_id"]], "ordered_query_recipe_sha256s": [b["query"]["spec_sha256"]],
        "config_sha256": context["binding_id"], "as_of": b["data_cutoff"], "availability_cutoff": b["data_cutoff"],
        "holdout_consumption_ids": [context["reservation_id"]], "random_seed_or_null": None}
    key = compute_run_key_sha256(inputs)
    return {"run_key_inputs": inputs, "run_key_sha256": key, "run_id": "RUN-" + key[:24].upper()}


def require_reservation(store, context: dict) -> dict:
    reservation = committed(store, context["reservation_id"])
    require(reservation is not None and reservation["payload"].get("type") == "CONFIRMATION_RESERVATION" and
            reservation["payload"].get("execution_binding_sha256") == context["binding_id"] and
            reservation["payload"].get("grant_id") == context["grant"]["record_id"] and
            reservation["payload"].get("scientific_charge") == 1, "VALUES_REQUIRE_COMMITTED_RESERVATION")
    return reservation["payload"]


def evaluate_native(context: dict, *, store, phase=None) -> tuple[dict, dict]:
    require_reservation(store, context)
    sample, metadata = context["sample"], context["metadata"]
    observed, population, denominators, missing = [], [], {"A": 0, "C": 0}, Counter()
    path = safe_path(store.root, sample.observations_rel)
    keys = {(r["episode_id"], r["cohort_id"], r["release_id"], r["mint"]) for r in metadata["census"]}
    identities = pq.read_table(path, columns=["episode_id", "cohort_id", "release_id", "mint"]).to_pylist()
    require(all((r["episode_id"], r["cohort_id"], r["release_id"], r["mint"]) in keys for r in identities),
            "FOREIGN_OBSERVATION_IDENTITY")
    for row in metadata["census"]:
        group = "A" if metadata["scope"].signal[row["episode_id"]] == "TRUE" else "C"
        clocks = {point: resolve_point(metadata["episode_schedule_bindings"][row["episode_id"]], utc(row["t0"]), point)
                  for point in ("E1800", "E14400")}
        cells = {}
        for point in ("E1800", "E14400"):
            if point == "E14400" and not population[-1]["decision_eligible"]:
                break
            window = clocks[point]
            require(window.availability_deadline <= utc(sample.data_cutoff), "TARGET_NOT_MATURE_AT_CUTOFF")
            # The immutable committed reservation was proved before entering this
            # decoder loop; no append/deletion or lock release occurs in it.
            source_rows = pq.read_table(path, columns=VALUE_COLUMNS, filters=[
                ("episode_id", "=", row["episode_id"]), ("cohort_id", "=", row["cohort_id"]),
                ("release_id", "=", row["release_id"]), ("field_id", "=", "FIELD-USD-PRICE-001"),
                ("point_id", "=", point)]).to_pylist()
            require(all(r["mint"] == row["mint"] for r in source_rows), "OBSERVATION_IDENTITY_CONFLICT")
            unique_rows = {digest(r): r for r in source_rows}
            require(len(unique_rows) <= 1, "OBSERVATION_CELL_CONFLICT")
            source_rows = list(unique_rows.values())
            cell = confirmation_price_cell(source_rows, cohort=row["cohort_id"], release=row["release_id"],
                    episode_id=row["episode_id"], point=point, window=window)
            typed_missing = {"MISSING_TYPED", "CENSORED", "CENSORED_LATE", "DISAPPEARED"}
            if cell["status"] != "OBSERVED":
                require(not any(r["state"] == "OBSERVED" for r in source_rows), "OBSERVED_CLOCK_OR_VALUE_INVALID")
                require(all(r["state"] in typed_missing for r in source_rows), "OBSERVATION_STATE_INVALID")
            else:
                require(cell["value"] > 0, "OBSERVED_PRICE_INVALID")
            cells[point] = cell
            if point == "E1800":
                eligible = cell["status"] == "OBSERVED"
                population.append({"episode_id": row["episode_id"], "mint": row["mint"], "group": group,
                    "decision_eligible": eligible, "decision_nominal_due": window.nominal_due.isoformat(),
                    "blocks": {str(h): block_for(window.nominal_due, h) for h in PARTITIONS}})
                denominators[group] += int(eligible)
        if not population[-1]["decision_eligible"]:
            continue
        if cells["E14400"]["status"] == "OBSERVED":
            try:
                value = confirmation_price_relative(cells["E14400"]["value"], cells["E1800"]["value"])
            except GroundedDiscoveryError as exc:
                if exc.code not in NUMERIC_REFUSALS:
                    raise ConfirmationError(exc.code) from exc
                # Preserve native observed-price membership/counts. A numeric
                # return unavailable in binary64 is neither missing nor zero.
                observed.append({**{k: population[-1][k] for k in ("episode_id", "mint", "group", "blocks")},
                                 "r": None, "numeric_refusal": exc.code})
            else:
                observed.append({**{k: population[-1][k] for k in ("episode_id", "mint", "group", "blocks")}, "r": value})
        else:
            missing[group + ":" + (source_rows[0]["state"] if source_rows else "ABSENT")] += 1
    if phase:
        phase("AFTER_VALUES")
    method = calculate_list_a(observed, denominators, qualified_protocol_core=CORE_SHA)
    return method, {"admitted": len(metadata["census"]), "scope_known": len(population),
        "decision_denominators": denominators, "decision_mask_sha256": digest(population),
        "observed": len(observed), "typed_missing_counts": dict(missing),
        "repeated_mints": len(population) - len({p["mint"] for p in population}),
        "membership": population, "observed_mask_sha256": digest(observed)}


def read_confirmation(store, *, trial_id: str, root: Path) -> dict:
    identifier_pattern = r"LA-TRIAL-[0-9A-F]{64}"
    require(bool(re.fullmatch(identifier_pattern, trial_id)), "TRIAL_ID_INVALID")
    history = records(store)
    reservations = [r for r in history if r["kind"] == "RESEARCH_ARTIFACT" and r["payload"].get("type") == "CONFIRMATION_RESERVATION" and
                    r["payload"].get("trial_id") == trial_id]
    require(len(reservations) == 1, "RESERVATION_NOT_FOUND_OR_CONFLICT")
    reservation = reservations[0]["payload"]
    invalid = [r for r in history if r["payload"].get("type") == "INVALID_AFTER_RESERVE" and r["payload"].get("trial_id") == trial_id]
    completions = [r for r in history if r["kind"] == "RUN_COMPLETED" and r["payload"].get("trial_id") == trial_id]
    if not completions:
        return {"status": "INVALID_AFTER_RESERVE" if invalid else "INTERRUPTED",
            "protocol_terminal": "INVALID_OR_BLOCKED" if invalid else None,
            "trial_id": trial_id, "run_id": reservation["run_id"], "execution_binding_sha256": reservation["execution_binding_sha256"],
            "scientific_charge": 1, "new_evaluator_invocations": 0, "domain": reservation["domain"],
            "reason_codes": invalid[-1]["payload"]["reason_codes"] if invalid else [],
            "next_action": "REFUSE_NEW_LOOK" if invalid else "RESUME_EXACT_TRIAL"}
    require(len(completions) == 1 and not invalid, "COMPLETION_CONFLICT")
    passport = completions[0]["payload"]
    validate_run_passport(passport)
    result = load_json(safe_path(store.root, passport["result_ref"]))
    validate_confirmation_result(result, root=root)
    require(digest(result) == passport["result_digest_sha256"], "RESULT_HASH_MISMATCH")
    identity = result["identity"]
    require(digest(result["binding"]) == identity["execution_binding_sha256"], "RESULT_BINDING_HASH_MISMATCH")
    frozen_binding = committed(store, "LA-BINDING-" + identity["execution_binding_sha256"])
    require(frozen_binding is not None and frozen_binding["payload"].get("execution_binding_sha256") == identity["execution_binding_sha256"], "RESULT_BINDING_NOT_COMMITTED")
    require({k: v for k, v in frozen_binding["payload"].items() if k not in {"execution_binding_sha256", "artifact_ref"}} == result["binding"], "RESULT_BINDING_COMMIT_CONFLICT")
    grant = committed(store, result["lineage"]["grant_id"])
    require(grant is not None and grant["payload"].get("execution_binding_sha256") == identity["execution_binding_sha256"], "RESULT_GRANT_NOT_COMMITTED")
    validate_exact_grant(grant, result["binding"], identity["execution_binding_sha256"])
    require(all(grant["payload"].get(k) == result["binding"][k] for k in
        ("source_set_sha256", "source_id", "protocol_core_sha256", "domain", "role", "study_budget_sha256")) and
        grant["payload"].get("purpose") == "ALLOW_EXACT_CONFIRMATION" and grant["payload"].get("executor") == CAPABILITY and
        grant["payload"].get("request_sha256") == digest({"binding": identity["execution_binding_sha256"], "purpose": "ALLOW_EXACT_CONFIRMATION"}), "RESULT_GRANT_CONFLICT")
    require(compute_run_key_sha256(reservation["run_key_inputs"]) == identity["run_key_sha256"], "RESULT_RUN_KEY_CONFLICT")
    source = committed(store, result["binding"]["source_authority_id"])
    require(source is not None and source["producer"] == SOURCE_OWNER and source["payload"].get("type") == "SOURCE_AUTHORITY" and
            source["payload"].get("sample_sha256") == result["binding"]["sample_sha256"] and
            source["payload"].get("source_set_sha256") == identity["source_set_sha256"], "RESULT_SOURCE_AUTHORITY_CONFLICT")
    for key in ("trial_id", "run_id", "run_key_sha256", "execution_binding_sha256", "experiment_spec_sha256",
                "protocol_core_sha256", "source_set_sha256", "domain"):
        require(identity[key] == passport[key] == reservation[key], "RESULT_LINEAGE_CONFLICT")
    require(result["lineage"]["reservation_id"] == reservations[0]["record_id"] and
            result["lineage"]["grant_id"] == reservation["grant_id"], "RESULT_RESERVATION_CONFLICT")
    terminal = result["method"]["terminal"]
    outcomes = ("POSITIVE", "RETAINED") if terminal == "ASSOCIATION_SUPPORTED_CONDITIONAL" else (
        ("NEGATIVE", "REJECTED") if terminal == "ASSOCIATION_NOT_SUPPORTED_AT_FROZEN_BOUNDARY" else ("INCONCLUSIVE", "INCONCLUSIVE"))
    require((passport["trial_outcome"], passport["scientific_terminal"]) == outcomes and
            passport["protocol_terminal"] == terminal, "RESULT_PASSPORT_TERMINAL_CONFLICT")
    kinds = {"TRIAL": "LA-TRIAL-COMPLETED-", "RESEARCH_ARTIFACT": "LA-RESULT-", "EXPERIMENT_METRIC": "LA-METRIC-", "EVIDENCE_BINDING": "LA-EVIDENCE-"}
    for kind, prefix in kinds.items():
        carriers = [r for r in history if r["kind"] == kind and (r["payload"].get("trial_id") == trial_id or
                    r["payload"].get("run_id") == identity["run_id"]) and r["payload"].get("type") not in
                    {"CONFIRMATION_RESERVATION", "TECHNICAL_ATTEMPT"}]
        require(len(carriers) == 1 and carriers[0]["record_id"] == prefix + trial_id, "TYPED_COMPLETION_CARRIER_CONFLICT")
        carrier = carriers[0]
        require(carrier["transaction_id"] == completions[0]["transaction_id"] and carrier["producer"] == CAPABILITY and
            all(carrier["payload"].get(k) == v for k, v in identity.items()) and
            carrier["payload"].get("result_digest_sha256") == passport["result_digest_sha256"] and
            carrier["payload"].get("result_ref") == passport["result_ref"] and carrier["payload"].get("protocol_terminal") == terminal,
            "TYPED_COMPLETION_CARRIER_IDENTITY_CONFLICT")
        if kind == "EXPERIMENT_METRIC":
            require(carrier["payload"].get("list_a") == {"A": result["method"]["support"]["A"], "C": result["method"]["support"]["C"],
                "contrast": result["method"]["contrast"], "intervals": result["method"]["partitions"]}, "TYPED_METRIC_CONFLICT")
    return {"status": "COMPLETED", "protocol_terminal": result["method"]["terminal"], "result": result,
        "trial_id": trial_id, "run_id": reservation["run_id"], "execution_binding_sha256": reservation["execution_binding_sha256"],
        "scientific_charge": 1, "new_evaluator_invocations": 0, "domain": reservation["domain"],
        "reason_codes": result["method"]["reason_codes"], "next_action": "READ_SAVED_RESULT_OR_RECORD_OWNER_DECISION"}


def compose_confirmation_dossier(*, spec: dict, locator, root: Path, store,
                                store_records, records_status: str, write_capability=None) -> dict:
    """Typed ordinary consumer. Presence is linked availability, not promotion."""
    from solana_alpha_lab.factory.run_passport import experiment_spec_sha256
    spec_sha = experiment_spec_sha256(spec)
    store_records = store_records or []
    direct, decisions, trials, conflicts = [], [], [], []
    for record in store_records:
        payload = json.loads(record.payload_json)
        if payload.get("experiment_id") == spec["experiment_id"] or payload.get("target_entity_id") == spec["experiment_id"]:
            if payload.get("experiment_spec_sha256", spec_sha) != spec_sha:
                conflicts.append("EXPERIMENT_SPEC_IDENTITY_CONFLICT")
                continue
            direct.append({"record_id": record.record_id, "record_kind": str(record.record_kind),
                "payload_sha256": record.payload_sha256, "relation": "DIRECT", "payload": payload})
            if str(record.record_kind) == "DECISION_EVENT":
                decisions.append({"record_id": record.record_id, "relation": "DIRECT", **payload,
                                  "effective_at": record.effective_at.isoformat()})
            if payload.get("type") == "CONFIRMATION_RESERVATION" and str(record.record_kind) == "RESEARCH_ARTIFACT":
                try:
                    require(store is not None, "TYPED_ARTIFACT_READER_UNAVAILABLE")
                    readback = read_confirmation(store, trial_id=payload["trial_id"], root=root)
                    if readback.get("result"):
                        require(readback["result"]["identity"]["experiment_spec_sha256"] == spec_sha, "RESULT_DEFINITION_CONFLICT")
                    trials.append(readback)
                except (ConfirmationError, ResearchStoreError, ValueError, OSError, KeyError) as exc:
                    reason = getattr(exc, "code", "TYPED_RESULT_UNVERIFIABLE")
                    conflicts.append(reason)
                    # A failed artifact verification cannot erase a committed
                    # potentially exposed reservation from the owner readout.
                    try:
                        checkpoint = confirmation_checkpoint(store, payload["execution_binding_sha256"])
                        require(checkpoint["scientific_charge"] == 1 and checkpoint["trial_id"] == payload["trial_id"],
                                "COMMITTED_RESERVATION_INVALID")
                        trials.append({**checkpoint, "status": "UNVERIFIABLE", "protocol_terminal": None,
                            "reason_codes": [reason], "next_action": "VERIFY_SAVED_ARTIFACT_KEEP_CONSUMED_ALLOWANCE"})
                    except (ConfirmationError, ResearchStoreError, ValueError, OSError, KeyError, AttributeError):
                        conflicts.append("COMMITTED_RESERVATION_UNVERIFIABLE")
    decisions.sort(key=lambda d: (d["effective_at"], d["record_id"]))
    known_trials = {t["trial_id"] for t in trials}
    for card in direct:
        if card["record_kind"] in {"RUN_COMPLETED", "TRIAL", "EXPERIMENT_METRIC", "EVIDENCE_BINDING"}:
            if card["payload"].get("trial_id") not in known_trials:
                conflicts.append("UNBOUND_DIRECT_CONFIRMATION_CARRIER")
    complete = [t for t in trials if t["status"] == "COMPLETED"]
    status = "CONFLICT" if conflicts else "PRESENT" if complete else "UNKNOWN" if records_status != "AVAILABLE" else "MISSING"
    # Boundings stay explicit; never silently combine distinct studies/samples.
    result_view = [{"trial_id": t["trial_id"], "execution_binding_sha256": t["execution_binding_sha256"],
        "domain": t["domain"], "scientific_charge": t["scientific_charge"], "status": t["status"],
        "protocol_terminal": t["protocol_terminal"], "reason_codes": t["reason_codes"],
        "next_action": t["next_action"], **({"population": {k: v for k, v in t["result"]["population"].items() if k != "membership"},
            "method": t["result"]["method"], "interval": [t["result"]["binding"]["interval_start"],
            t["result"]["binding"]["interval_end_exclusive"]]} if t.get("result") else {})} for t in trials]
    from solana_alpha_lab.factory.experiment_evidence import build_science_obligations, science_guard
    ordinary_spec = {**spec, "falsifier": "BOTH_UPPER_BOUNDS_AND_ALL_LEAVE_ONE_NONPOSITIVE"}
    obligations = build_science_obligations(ordinary_spec, entity={"entity_id": locator.entity_id}, direct=direct,
        records=store_records, records_status=records_status, root=root)
    obligations = [o for o in obligations if o["code"] != "RESULT"] + [{"code": "RESULT", "status": status, "values": {"trials": result_view},
                    "reason_codes": sorted(set(conflicts)), "next_safe_action": "VERIFY_TYPED_RESULT_LINEAGE"},
        {"code": "CONFIRMATION_DOMAIN", "status": "PRESENT" if trials else "UNKNOWN",
         "values": {"domains": sorted({t["domain"] for t in trials})}, "next_safe_action": "NO_PROMOTE_FROM_SYNTHETIC_CONFIRMATION"}]
    real_positive = bool(complete) and len(complete) == len(trials) and not conflicts and all(
        t["domain"] == "REAL" and t["protocol_terminal"] == "ASSOCIATION_SUPPORTED_CONDITIONAL" for t in trials)
    if real_positive:
        # Typed exact confirmation eligibility replaces only the legacy holdout consumption assumption.
        obligations = [({**o, "status": "PRESENT", "values": {"eligibility": "VERIFIED_EXACT_CONFIRMATION"}}
                        if o["code"] == "HOLDOUT" else o) for o in obligations]
    ordinary_guard = science_guard(obligations)
    domain_reasons = ["SYNTHETIC_CONFIRMATION_NONPROMOTABLE"] if any(t["domain"] == "SYNTHETIC" for t in trials) else []
    if not trials or any(t["protocol_terminal"] != "ASSOCIATION_SUPPORTED_CONDITIONAL" for t in trials):
        domain_reasons.append("POSITIVE_CONFIRMATION_REQUIRED")
    guard = {**ordinary_guard, "allowed": real_positive and ordinary_guard["allowed"],
             "reason_codes": sorted(set([*domain_reasons, *conflicts, *ordinary_guard["blocked_codes"]])),
             "next_safe_action": "REAL_SOURCE_AND_EXISTING_SCIENCE_GATES_REQUIRED"}
    snapshot = digest({"experiment": spec_sha, "records_status": records_status,
        "records": sorted((r.record_id, r.payload_sha256) for r in store_records),
        "typed_status": status, "conflicts": sorted(set(conflicts))})
    return {"schema": "smial.experiment-evidence-dossier", "schema_version": "1.0", "authority_granted": False,
        "locator": {"entity_id": locator.entity_id, "truth_plane": locator.truth_plane, "native_kind": locator.native_kind},
        "planes": {"execution": "UNKNOWN" if records_status != "AVAILABLE" or conflicts else
                   "COMPLETE" if complete and len(complete) == len(trials) else "INTERRUPTED" if trials else "NO_RUN",
                   "evidence": status, "decision": "UNKNOWN" if records_status != "AVAILABLE" else
                   decisions[-1].get("decision_kind") if decisions else "NO_DECISION"},
        "tested": {"question": spec["question"], "estimand": spec["estimand"], "population": spec["population"],
                   "hypothesis_version_id": spec["hypothesis_version"], "holdout_policy": "ALLOW_EXACT_CONFIRMATION",
                   "method": "CROSSED_CLUSTER_PERCENTILE_BOOTSTRAP", "falsifier": "BOTH_UPPER_BOUNDS_AND_ALL_LEAVE_ONE_NONPOSITIVE"},
        "obligations": obligations, "result": {"trials": result_view}, "direct_evidence": direct,
        "execution_relation_gaps": [{"reason_code": c} for c in sorted(set(conflicts))], "related_prior_memory": [],
        "decision_history": decisions, "science_guard": guard, "evidence_snapshot_sha256": snapshot,
        "promotion_packet_sha256": None, "experiment_spec_binding": {"canonical_spec_sha256": spec_sha,
            "source_kind": "git_path", "source_value": "configs/experiment_specs/list_a_chronological_confirmation_v1.yaml"},
        "write_capability": dict(write_capability or {}), "owner_decision_kinds": ["PAUSE", "REJECT", "REVISE", "PROMOTE"],
        "promote_creates_strategy_version": False, "records_status": records_status}


def execute_list_a_confirmation(spec, *, root: Path, authority_phrase=None, capture_hooks=None) -> dict:
    hooks = capture_hooks or {}
    execution = hooks.get("execution_context") or {}
    data_root = execution.get("data_root")
    require(data_root is not None, "CONFIRMATION_DATA_ROOT_UNBOUND")
    store = ResearchStore(Path(data_root), create_if_missing=False)
    now = execution.get("now") or datetime.now(UTC)
    context = current_context(spec, str(execution.get("binding_id") or ""), root=root, store=store, now=now)
    if committed(store, "LA-COMPLETED-" + context["trial_id"]):
        return read_confirmation(store, trial_id=context["trial_id"], root=root)
    with study_lock(store.root, context["binding"]["study_budget_sha256"]):
        context = current_context(spec, context["binding_id"], root=root, store=store, now=now)
        if committed(store, "LA-COMPLETED-" + context["trial_id"]):
            return read_confirmation(store, trial_id=context["trial_id"], root=root)
        existing = committed(store, context["reservation_id"])
        require(not any(r["payload"].get("type") == "INVALID_AFTER_RESERVE" and
                        r["payload"].get("trial_id") == context["trial_id"] for r in records(store)), "TRIAL_INVALID_NO_RESUME")
        if existing:
            reservation = require_reservation(store, context)
        else:
            identity = run_identity(context, root)
            b = context["binding"]
            reservation = {"type": "CONFIRMATION_RESERVATION", **identity,
                "experiment_id": b["experiment_id"], "hypothesis_version_id": b["hypothesis_version_id"],
                "experiment_spec_sha256": b["experiment_spec_sha256"], "protocol_core_sha256": CORE_SHA,
                "execution_binding_sha256": context["binding_id"], "source_set_sha256": b["source_set_sha256"],
                "source_id": b["source_id"], "study_budget_sha256": b["study_budget_sha256"],
                "acquisition_keys": b["acquisition_keys"], "acquisition_identity_sha256": b["acquisition_identity_sha256"],
                "trial_id": context["trial_id"], "grant_id": context["grant"]["record_id"],
                "scientific_charge": 1, "status": "RESERVED_POTENTIALLY_EXPOSED", "domain": b["domain"],
                "started_at": datetime.now(UTC).isoformat()}
            txn = "RESEARCH-TXN-LA-RESERVE-" + context["trial_id"][-24:].upper()
            def compare_and_reserve():
                current_context(spec, context["binding_id"], root=root, store=store, now=now)
                require(not any(r["payload"].get("type") == "CONFIRMATION_RESERVATION" and
                                r["payload"].get("study_budget_sha256") == b["study_budget_sha256"]
                                for r in records(store)), "SCIENTIFIC_ALLOWANCE_EXHAUSTED")
            store.append([event(root, record_id=context["reservation_id"], kind=RecordKind.RESEARCH_ARTIFACT,
                transaction_id=txn, payload=reservation), event(root, record_id="LA-STARTED-" + context["trial_id"],
                kind=RecordKind.RUN_STARTED, transaction_id=txn, payload=reservation, run_id=reservation["run_id"])],
                transaction_id=txn, before_commit=compare_and_reserve)
        phase = hooks.get("phase")
        if phase:
            phase("AFTER_RESERVATION")
        attempt_id = uuid.uuid4().hex
        attempt_payload = {"type": "TECHNICAL_ATTEMPT", "trial_id": context["trial_id"],
                           "attempt_id": attempt_id, "scientific_charge": 1}
        txn = "RESEARCH-TXN-LA-ATTEMPT-" + attempt_id.upper()
        store.append([event(root, record_id="LA-ATTEMPT-" + attempt_id, kind=RecordKind.RESEARCH_ARTIFACT,
                     transaction_id=txn, payload=attempt_payload)], transaction_id=txn)
        exposure_stage = "BEFORE_VALUES"
        try:
            context = current_context(spec, context["binding_id"], root=root, store=store, now=now)
            exposure_stage = "VALUES_MAY_BE_EXPOSED"
            method, population = evaluate_native(context, store=store, phase=phase)
            if phase:
                phase("AFTER_BOOTSTRAP")
            b = context["binding"]
            result = {"schema": "smial.list-a-confirmation-result", "schema_version": "1.0",
                "identity": {k: reservation[k] for k in ("experiment_id", "hypothesis_version_id", "experiment_spec_sha256",
                    "protocol_core_sha256", "execution_binding_sha256", "source_set_sha256", "source_id", "trial_id", "run_id",
                    "run_key_sha256", "domain")}, "population": population, "method": method,
                "binding": b, "lineage": {"reservation_id": context["reservation_id"], "grant_id": context["grant"]["record_id"],
                    "attempt_id": attempt_id}, "limits": ["CONDITIONAL_ON_OBSERVED_TARGETS", "PREDICTIVE_OBSERVATIONAL",
                    "NO_CAUSAL_CLAIM", "NO_EMPIRICAL_COVERAGE_GUARANTEE", "NO_STRATEGY_ACTIVATION_AUTHORITY"]}
            validate_confirmation_result(result, root=root)
            result_sha = digest(result)
            result_ref = f"confirmation/attempts/{context['trial_id']}/{attempt_id}/result-{result_sha}.json"
            publish(store.root, result_ref, finite_bytes(result))
            if phase:
                phase("AFTER_RESULT_PUBLICATION")
            terminal = method["terminal"]
            outcome, scientific = ("POSITIVE", "RETAINED") if terminal == "ASSOCIATION_SUPPORTED_CONDITIONAL" else (
                ("NEGATIVE", "REJECTED") if terminal == "ASSOCIATION_NOT_SUPPORTED_AT_FROZEN_BOUNDARY" else ("INCONCLUSIVE", "INCONCLUSIVE"))
            completed_at = datetime.now(UTC).isoformat()
            inputs = reservation["run_key_inputs"]
            passport = {**reservation, "type": "CONFIRMATION_COMPLETION", "runner_capability_id": CAPABILITY,
                "hypothesis_definition_sha256": CORE_SHA, "runner_git_sha": inputs["runner_git_sha"],
                "capability_closure_sha256": inputs["capability_closure_sha256"], "uv_lock_sha256": inputs["uv_lock_sha256"],
                "dataset_manifest_ids": [], "dataset_fingerprints": inputs["ordered_input_dataset_fingerprints"],
                "query_recipe_ids": inputs["ordered_query_recipe_ids"], "query_recipe_sha256s": inputs["ordered_query_recipe_sha256s"],
                "config_sha256": context["binding_id"], "as_of": b["data_cutoff"], "availability_cutoff": b["data_cutoff"],
                "holdout_consumption_ids": [context["reservation_id"]], "random_seed_or_null": None,
                "completed_at": completed_at, "first_reliable_available_at": completed_at,
                "provider_calls_planned": 0, "provider_calls_actual": 0, "cash_spend_usd_cents": 0,
                "execution_status": "COMPLETE", "trial_outcome": outcome, "scientific_terminal": scientific,
                "result_digest_sha256": result_sha, "artifact_manifest_sha256": result_sha,
                "limitations": result["limits"], "non_claims": result["limits"], "result_ref": result_ref,
                "protocol_terminal": terminal}
            validate_run_passport(passport)
            txn = "RESEARCH-TXN-LA-COMPLETE-" + context["trial_id"][-24:].upper()
            common = {**result["identity"], "result_digest_sha256": result_sha, "result_ref": result_ref,
                "protocol_terminal": terminal, "scientific_charge": 1, "producer_capability_id": CAPABILITY}
            payloads = [
                (RecordKind.RUN_COMPLETED, "LA-COMPLETED-", passport),
                (RecordKind.TRIAL, "LA-TRIAL-COMPLETED-", {**common, "trial_outcome": outcome, "scientific_terminal": scientific}),
                (RecordKind.RESEARCH_ARTIFACT, "LA-RESULT-", {**common, "type": "VERIFIED_CONFIRMATION_RESULT"}),
                (RecordKind.EXPERIMENT_METRIC, "LA-METRIC-", {**common, "list_a": {"A": method["support"]["A"],
                    "C": method["support"]["C"], "contrast": method["contrast"], "intervals": method["partitions"]}}),
                (RecordKind.EVIDENCE_BINDING, "LA-EVIDENCE-", {**common, "type": "TYPED_LIST_A_CONFIRMATION",
                    "binding_status": "DIRECT", "conditional_claim": "OBSERVED_TARGETS"})]
            def before_completion():
                current_context(spec, context["binding_id"], root=root, store=store, now=now)
                require_reservation(store, context)
            store.append([event(root, record_id=prefix + context["trial_id"], kind=kind, transaction_id=txn,
                payload=payload, run_id=reservation["run_id"]) for kind, prefix, payload in payloads],
                transaction_id=txn, before_commit=before_completion)
        except ConfirmationError as exc:
            txn = "RESEARCH-TXN-LA-INVALID-" + attempt_id.upper()
            store.append([event(root, record_id="LA-INVALID-" + attempt_id, kind=RecordKind.RUN_INVALID,
                transaction_id=txn, run_id=reservation["run_id"], payload={"type": "INVALID_AFTER_RESERVE",
                "trial_id": context["trial_id"], "scientific_charge": 1, "exposure_stage": exposure_stage,
                "reason_codes": [exc.code]})], transaction_id=txn)
            raise
        if phase:
            phase("AFTER_COMPLETION")
        response = read_confirmation(store, trial_id=context["trial_id"], root=root)
        response["new_evaluator_invocations"] = 1
        return response


def resume_confirmation(store, *, trial_id: str, current_context: dict, root: Path, definition: dict) -> dict:
    saved = read_confirmation(store, trial_id=trial_id, root=root)
    require(saved["execution_binding_sha256"] == current_context["binding_id"], "RESUME_IDENTITY_MISMATCH")
    return execute_list_a_confirmation(definition, root=root, capture_hooks={"execution_context": {
        **current_context, "data_root": store.root}})
