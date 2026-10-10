"""Fresh consumer of a native retained producer plus an open operational WAL."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path[:0] = ["/repo", "/repo/src", "/kit"]
import yaml
from bridge_probe import main as bridge
from solana_alpha_lab.factory.operational_store import OperationalStore


def main():
    assert bridge() == 0
    bridged = json.loads(Path("/audit/bridge-summary.json").read_text())
    root = Path("/audit/bridge-source")
    relative = "configs/experiment_specs/BAA_RETAINED_OPERATOR_INPUT.yaml"
    spec = yaml.safe_load((root / relative).read_text())
    config_path = root / "configs/factory_v1_product_kernel_v1.yaml"
    config = yaml.safe_load(config_path.read_text())
    config["operational_store"]["relative_path"] = "owned-ops/ops.sqlite"
    config_path.write_text(yaml.safe_dump(config))
    ops = root / "owned-ops/ops.sqlite"
    writer = OperationalStore(ops)
    job = dict(job_id="JOB-FTC-JOINT-001", experiment_id=spec["experiment_id"],
               spec_relative=relative, spec_sha256=bridged["experiment_spec_sha256"],
               status="RUNNING", blocker="", terminal=None, evidence={})
    writer.upsert_job(job)
    writer._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    writer.upsert_job({**job, "status": "COMPLETE"})
    # Actual OS file permissions; the already-open writer stays alive. SQLite
    # may use existing SHM coordination, but durable DB/WAL and directory deny writes.
    for path in (ops, Path(str(ops) + "-wal")):
        path.chmod(0o444)
    ops.parent.chmod(0o555)
    durable = lambda: {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in (ops, Path(str(ops) + "-wal"))}
    before = durable()
    source = r'''
import json,sys
from pathlib import Path
sys.path[:0]=['/repo','/repo/src']
from solana_alpha_lab.factory.application import FactoryApplication
from solana_alpha_lab.factory.lifecycle_projection import build_lifecycle_projection
from solana_alpha_lab.factory.research_workbench import LifecycleEntityLocatorV1
from tests.test_experiment_evidence_decision_v1 import _http
root,plane,experiment,relative=map(str,sys.argv[1:])
root=Path(root);plane=Path(plane)
app=FactoryApplication(root=root,research_data_root=plane,spec_relative=relative,unit_status={})
reader=app.existing_operational_store()
assert reader.get_job('JOB-FTC-JOINT-001')['status']=='COMPLETE'
projection=build_lifecycle_projection(root,research_data_root=plane)
entity=next(e for e in projection['entities'] if e['entity_id']=='JOB-FTC-JOINT-001')
assert entity['native_state']=='COMPLETE'
detail=app.research_detail(LifecycleEntityLocatorV1(experiment,'GIT','EXPERIMENT_SPEC'))
assert detail['dossier']['planes']['execution']=='COMPLETED'
assert not detail['dossier']['science_guard']['allowed']
status,html=_http(app,'GET','/research?entity_id='+experiment+'&truth_plane=GIT&native_kind=EXPERIMENT_SPEC')
assert status==200
assert 'COMPLETED' in html
assert not detail['dossier']['execution_relation_gaps']
print(json.dumps({'operational_store':'COMPLETE','lifecycle_projection':'COMPLETE','api_dossier':detail['dossier']['planes'],
                  'http_status':status,'http_completed':True,'science_guard_allowed':False,
                  'native_execution_ids':[r['record_id'] for r in detail['dossier']['direct_evidence'] if r['record_kind'] in ('RUN_STARTED','RUN_COMPLETED')]}))
app._close_operational_readonly()
'''
    # Probe OS enforcement independently of the SQL query-only connection.
    denied = 0
    for path in (ops, Path(str(ops) + "-wal"), ops.parent / "forbidden"):
        try:
            with path.open("ab"):
                pass
        except PermissionError:
            denied += 1
    assert denied == 3
    plane = next(p.parent / "plane" for p in Path("/input/tmp").glob("*/classify.json")
                 if json.loads(p.read_text()).get("experiment_spec", {}).get("experiment_id") == spec["experiment_id"])
    try:
        child = subprocess.run([sys.executable, "-B", "-c", source, str(root), str(plane),
                                spec["experiment_id"], relative], capture_output=True, text=True, timeout=90)
        assert child.returncode == 0, child.stderr
        observed = json.loads(child.stdout.strip().splitlines()[-1])
        assert before == durable()
        result = dict(status="PASS", fidelity="LINKED_NATIVE_PRODUCT_SEGMENTS", fresh_process=True,
                      writer_alive_at_read=True, os_denied_writes=denied, durable_db_wal_before=before,
                      durable_db_wal_after=durable(), shm="VOLATILE_COORDINATION_NOT_DURABLE_TRUTH",
                      synthetic_operational_job="SEPARATE_NATIVE_INPUT_NOT_EXECUTION_EVIDENCE",
                      inserted_scientific_records=0, producer=bridged, consumer=observed)
        Path("/audit/joint-summary.json").write_text(json.dumps(result, indent=2))
        print(json.dumps({"status": "PASS", "consumer": observed}))
    finally:
        ops.parent.chmod(0o755)
        for path in (ops, Path(str(ops) + "-wal")):
            path.chmod(0o644)
        writer.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
