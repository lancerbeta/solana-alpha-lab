"""Owned Docker metadata readback, never inspect unrelated containers or credentials."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

CAMPAIGN='SMIAL_SCIENCE_LIFECYCLE_SMOKE_V1'

def capture(runtime):
    assert (runtime/'.science-owner').read_text()==CAMPAIGN
    identifiers=subprocess.check_output(['docker','ps','-aq','--filter','label=science.campaign='+CAMPAIGN],text=True).split()
    rows=json.loads(subprocess.check_output(['docker','inspect','--size',*identifiers],text=True)) if identifiers else []
    operations=[]
    for row in rows:
        name=row['Name'].lstrip('/')
        assert name.startswith('science-lifecycle-v1-') and row['Config']['Labels']['science.campaign']==CAMPAIGN
        state=row['State']; assert not state['Running'], 'OWNED_PRODUCT_PROCESS_STILL_RUNNING'
        logs=subprocess.check_output(['docker','logs',name],stderr=subprocess.STDOUT)
        operations.append({'ledger_kind':'owned_container_attempt','attempt':name,'image':row['Image'],
            'started_at':state['StartedAt'],'finished_at':state['FinishedAt'],'exit_code':state['ExitCode'],
            'oom_killed':state['OOMKilled'],'running':state['Running'],'network':row['HostConfig']['NetworkMode'],
            'readonly_root':row['HostConfig']['ReadonlyRootfs'],'user':row['Config']['User'],
            'size_rw_bytes':row.get('SizeRw'),'log_stream_bytes':len(logs),
            'log_stream_sha256':hashlib.sha256(logs).hexdigest(),
            'log_locator':{'runtime_child':'output','attempt':name.removeprefix('science-lifecycle-v1-')},
            'native_charges':'JOIN_FROM_NATIVE_LEDGER; NEVER_REFUND_NONZERO_EXIT'})
    operations.sort(key=lambda r:(r['started_at'],r['attempt']))
    return {'operations':operations,'running_owned_processes':0,
        'container_rw_known_bytes':sum(r['size_rw_bytes'] or 0 for r in operations),
        'docker_log_stream_bytes':sum(r['log_stream_bytes'] for r in operations),
        'container_metadata_directory_allocation':'UNKNOWN_NOT_EXPOSED_BY_DOCKER_INSPECT',
        'shared_docker_vhd_growth':'UNKNOWN_NO_BEFORE_BASELINE','cleanup_performed':False}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--runtime',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    args.out.write_text(json.dumps(capture(args.runtime),sort_keys=True,indent=2)+'\n')
    print('OWNED_METADATA_CAPTURED; NO_RUNNING_PRODUCT_PROCESSES')
