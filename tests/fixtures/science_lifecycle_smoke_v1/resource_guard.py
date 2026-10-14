"""Mandatory pre/post allocation checks inside even a short-lived owned child."""
import json
import os
from pathlib import Path
from capture_host import known_allocation
from footprint import measure


def check_values(host_bound, container_rw, volumes, cap):
    assert cap==671088640, 'UNAUTHORIZED_ALLOCATION_CAP'
    total=known_allocation(host_bound)+known_allocation(container_rw)+known_allocation(volumes['allocated_unique_bytes'])+4096
    assert total<=cap, 'FORWARD_STORAGE_CAP_EXCEEDED'
    return total


def check(stage):
    attempt=os.environ['SMIAL_AUDIT_ATTEMPT']
    assert attempt and all(c in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in attempt)
    cap=int(os.environ['SMIAL_ALLOCATION_CAP'])
    host=int(os.environ['SMIAL_HOST_ALLOCATION_BOUND'])
    rw=int(os.environ['SMIAL_CONTAINER_RW_BOUND'])
    volumes=measure()
    total=check_values(host,rw,volumes,cap)
    path=Path('/audit')/('resource-'+attempt+'-'+stage+'.json')
    assert not path.exists(), 'IMMUTABLE_RESOURCE_ATTEMPT_ALREADY_PRESENT'
    path.write_text(json.dumps({'stage':stage,'cap_bytes':cap,'host_bound_bytes':host,
        'container_rw_bound_bytes':rw,'owned_volumes':volumes,'total_bound_with_receipt_reserve':total},sort_keys=True)+'\n')
    return total
