"""Existing local root locator only; no values, store writer or corpus resolver."""
from __future__ import annotations
import hashlib
import json
import sys
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from solana_alpha_lab.factory.data_root import resolve_existing_data_root


def project_json(text: str, allowed, log: list[str], prefix=""):
    """Bounded evidence-only projection: skipped value tokens are never decoded.

    Metadata JSON may contain observation-state counts. Do not json.load the
    document. Scan delimiters/strings, decode only explicitly selected fields.
    This is not a production reader or a general schema validator.
    """
    def end_token(i):
        start, stack, quoted, escaped = i, [], False, False
        while i < len(text):
            char = text[i]
            if quoted:
                if escaped: escaped = False
                elif char == "\\": escaped = True
                elif char == '"':
                    quoted = False
                    if not stack and text[start] == '"': return i+1
            elif char == '"': quoted = True
            elif char in '[{': stack.append(char)
            elif char in ']}':
                if not stack: return i
                if (stack.pop(), char) not in (("{", "}"), ("[", "]")): raise ValueError("JSON_DELIMITER_INVALID")
                if not stack: return i+1
            elif char == ',' and not stack: return i
            i += 1
        if quoted or stack: raise ValueError("JSON_TRUNCATED")
        return i
    def ws(i):
        while i < len(text) and text[i].isspace(): i += 1
        return i
    def read(i, shape, path):
        i=ws(i)
        if shape is True:
            end=end_token(i)
            value=json.loads(text[i:end])
            if isinstance(value, (dict,list)): raise ValueError("SCALAR_METADATA_EXPECTED")
            log.append(path)
            return value,end
        if isinstance(shape,list):
            if text[i] != '[': raise ValueError("JSON_ARRAY_EXPECTED")
            values=[]; i=ws(i+1)
            while text[i] != ']':
                item,i=read(i,shape[0],path+"[]"); values.append(item); i=ws(i)
                if text[i] == ',': i=ws(i+1)
                elif text[i] != ']': raise ValueError("JSON_ARRAY_SEPARATOR")
            return values,i+1
        if text[i] != '{': raise ValueError("JSON_OBJECT_EXPECTED")
        output={}; seen=set(); i=ws(i+1)
        while text[i] != '}':
            key_end=end_token(i); key=json.loads(text[i:key_end])
            if not isinstance(key,str) or key in seen: raise ValueError("JSON_DUPLICATE_KEY")
            seen.add(key); i=ws(key_end)
            if text[i] != ':': raise ValueError("JSON_COLON_EXPECTED")
            i=ws(i+1)
            if key in shape: output[key],i=read(i,shape[key],path+"/"+key)
            else: i=end_token(i)
            i=ws(i)
            if text[i] == ',': i=ws(i+1)
            elif text[i] != '}': raise ValueError("JSON_OBJECT_SEPARATOR")
        return output,i+1
    value,end=read(0,allowed,prefix)
    if text[end:].strip(): raise ValueError("JSON_TRAILING_CONTENT")
    return value


def safe_metadata(root: Path, relative: str, fields, readset):
    path=root/relative
    if Path(relative).is_absolute() or not path.resolve().is_relative_to(root.resolve()): raise ValueError("METADATA_PATH_ESCAPE")
    if any(p.is_symlink() or p.is_junction() for p in (path,*path.parents) if p != root.parent): raise ValueError("METADATA_LINK_REFUSED")
    if not path.is_file() or path.stat().st_size > 1048576: raise ValueError("METADATA_FILE_ABSENT_OR_OVERSIZE")
    raw=path.read_bytes(); log=[]
    projected=project_json(raw.decode("utf-8"),fields,log)
    readset.append({"relative":relative,"sha256":hashlib.sha256(raw).hexdigest(),"opaque_bytes_read":len(raw),"selected_fields":sorted(set(log)),"unchanged_after":hashlib.sha256(path.read_bytes()).hexdigest()==hashlib.sha256(raw).hexdigest()})
    return projected


def probe() -> dict:
    resolution = resolve_existing_data_root(ROOT)
    result = {
        "schema": "list-a-local-metadata-probe",
        "root_resolution": resolution.redacted_receipt(),
        "root_resolver_owner": "src/solana_alpha_lab/factory/data_root.py:resolve_existing_data_root",
        "read_scope": "CANONICAL_LOCAL_LINEAGE_LABEL_PROJECTION_AND_PARAMETER_ONLY_SCHEDULE",
        "metadata_fields_read": [], "opaque_bytes_hashed": 0,
        "market_value_fields_deserialized": 0, "scientific_looks_created": 0,
        "research_store_writes": 0, "provider_calls": 0,
        "source_contents_read": False,
    }
    if resolution.root is None:
        result.update(first_blocker=resolution.error, metadata_paths=[],
                      terminal="BOUND_CONTRACT_NOT_READY")
        return result
    paths = ["datasets/opportunity_episodes_corpus/lineage.json",
             "research_lists", "datasets/manifests", "research/events"]
    def inventory():
        rows = []
        for relative in paths:
            path = resolution.root / relative
            linked = path.is_symlink()
            parent = path.parent
            while parent != resolution.root.parent:
                linked = linked or parent.is_symlink()
                parent = parent.parent
            present = not linked and path.exists()
            stat = path.stat() if present else None
            rows.append({"relative": relative, "status": "LINK_REFUSED" if linked else "PRESENT" if present else "ABSENT",
                         "kind": "DIRECTORY" if present and path.is_dir() else "FILE" if present else None,
                         "size": stat.st_size if stat and path.is_file() else None,
                         "mtime_ns": stat.st_mtime_ns if stat else None})
        return rows
    before, after = inventory(), inventory()
    result.update(metadata_paths=before, non_target_stat_inventory_unchanged=before == after,
                  metadata_path_inventory_sha256=hashlib.sha256(json.dumps(before,sort_keys=True,separators=(",",":")).encode()).hexdigest(),
                  first_blocker="EPISODE_CORPUS_LINEAGE_NOT_PRESENT" if before[0]["status"] == "ABSENT" else "EXACT_APPROVED_SAMPLE_AND_COMPLETE_EXPOSURE_PROVENANCE_NOT_BOUND",
                  terminal="BOUND_CONTRACT_NOT_READY")
    if before[0]["status"] != "PRESENT": return result
    readset=[]
    schedule={k:True for k in ("schedule_contract","dense_step_seconds","dense_until_seconds","hourly_step_seconds","horizon_seconds","dispatch_window_seconds","availability_grace_seconds","witness_max_age_seconds")}
    cohort={k:True for k in ("cohort_id","release_id","collection","corpus_version","sealed_at","imported_at","census_rel","obs_rel","census_sha256","observations_sha256","release_dir_rel","schedule_sha256","admissions_n","distinct_mint_n","closure_receipt_sha256","source_sha256","evidence_role")}
    cohort["schedule_binding"]=schedule
    lineage_fields={k:True for k in ("corpus_dataset_id","collection","population","current_corpus_version","current_dataset_manifest_id")}; lineage_fields["cohorts"]=[cohort]
    lineage=safe_metadata(resolution.root,paths[0],lineage_fields,readset)
    manifest_id=lineage.get("current_dataset_manifest_id")
    if not isinstance(manifest_id,str) or not re.fullmatch(r"[A-Za-z0-9_-]+",manifest_id): raise ValueError("MANIFEST_ID_INVALID")
    labels=safe_metadata(resolution.root,f"datasets/manifests/{manifest_id}.labels.json",{k:True for k in ("evidence_role","confirmatory_reuse_forbidden","holdout","outcome_previously_consumed","population","population_contract","anchor_kind","logical_dataset_id","collection","dataset_version","corpus_version","is_current_corpus_version","yield_semantics")},readset)
    from solana_alpha_lab.factory.live_cohort_schedule_artifact import decode_schedule_artifact
    from solana_alpha_lab.factory.hfic_research_scope import jupiter_definitions
    from solana_alpha_lab.factory.opportunity_episodes import cohort_day_bounds, resolve_point
    from solana_alpha_lab.factory.observation_schedule import render_utc
    witnesses=[]
    for source in lineage.get("cohorts",[]):
        relative=str(source["release_dir_rel"])+"/observation_schedule.json"
        path=resolution.root/relative
        if not path.resolve().is_relative_to(resolution.root.resolve()) or any(p.is_symlink() or p.is_junction() for p in (path,*path.parents) if p != resolution.root.parent): raise ValueError("SCHEDULE_PATH_REFUSED")
        if not path.is_file() or path.stat().st_size>1048576: raise ValueError("SCHEDULE_METADATA_ABSENT_OR_OVERSIZE")
        raw=path.read_bytes()
        doc=decode_schedule_artifact(raw,wanted_sha=source["schedule_sha256"],root=ROOT)
        readset.append({"relative":relative,"sha256":hashlib.sha256(raw).hexdigest(),"opaque_bytes_read":len(raw),"selected_fields":["PARAMETER_ONLY_OBSERVATION_SCHEDULE_DOCUMENT"],"unchanged_after":hashlib.sha256(path.read_bytes()).hexdigest()==hashlib.sha256(raw).hexdigest()})
        start,end=cohort_day_bounds(source["cohort_id"])
        clocks={point:{"nominal_due":render_utc(resolve_point(source["schedule_binding"],start,point).nominal_due),"availability_deadline":render_utc(resolve_point(source["schedule_binding"],start,point).availability_deadline)} for point in ("E1800","E14400")}
        upper_blocks={str(h):int((end.timestamp()+1800-1)//h-start.timestamp()//h+1) for h in (86400,172800)}
        witnesses.append({"cohort_id":source["cohort_id"],"schedule_sha256":source["schedule_sha256"],"list_a_definition":jupiter_definitions(doc)["JUPITER:toporganicscore:5m"],"cohort_interval_start":render_utc(start),"cohort_interval_end_exclusive":render_utc(end),"start_anchor_clock_witness":clocks,"frozen_protection_source_refs":doc["protection"]["assignment_sources"],"potential_mints_upper_bound":source["distinct_mint_n"],"potential_time_blocks_upper_bound":upper_blocks,"actual_target_support":"NOT_READ_NOT_PROVEN","structural_feasibility":"INSUFFICIENT_POTENTIAL_SUPPORT" if source["distinct_mint_n"]<30 or any(n<30 for n in upper_blocks.values()) else "SUPPORT_POSSIBLE_NOT_PROVEN"})
    result.update(lineage_metadata=lineage,source_labels=labels,metadata_readset=readset,
                  source_witnesses=witnesses,exposure_status="UNRESOLVED_COMPLETE_PROVENANCE_NOT_ESTABLISHED",
                  protection_status="FROZEN_SOURCE_REFS_ONLY_CURRENT_ASSIGNMENTS_NOT_VALIDATED",
                  metadata_fields_read=sorted({k for row in readset for k in row["selected_fields"]}),
                  opaque_bytes_hashed=sum(row["opaque_bytes_read"]*2 for row in readset),
                  source_contents_read="METADATA_ONLY_SELECTIVE_TOKEN_PROJECTION",
                  non_target_metadata_hashes_unchanged=all(row["unchanged_after"] for row in readset),
                  first_blocker="CONFIRMATORY_REUSE_FORBIDDEN" if labels.get("confirmatory_reuse_forbidden") is True else "EXACT_APPROVED_SAMPLE_AND_COMPLETE_EXPOSURE_PROVENANCE_NOT_BOUND")
    return result


if __name__ == "__main__":
    print(json.dumps(probe(), ensure_ascii=True, indent=2, allow_nan=False))
