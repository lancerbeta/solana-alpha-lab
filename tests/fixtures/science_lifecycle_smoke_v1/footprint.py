"""Actual allocated blocks deduplicated by file identity, owned mounts only."""
from pathlib import Path

def measure(roots=('/repo','/audit')):
    seen=set();groups={}
    for root in roots:
        logical=allocated=files=0
        for path in Path(root).rglob('*'):
            if not path.is_file():continue
            stat=path.stat();files+=1;logical+=stat.st_size
            identity=(stat.st_dev,stat.st_ino)
            if identity not in seen:
                allocated+=stat.st_blocks*512;seen.add(identity)
        groups[root]={'logical_bytes':logical,'allocated_unique_bytes':allocated,'files':files}
    return {'groups':groups,'allocated_unique_bytes':sum(g['allocated_unique_bytes'] for g in groups.values()),
        'logical_bytes':sum(g['logical_bytes'] for g in groups.values()),'directory_metadata':'EXCLUDED',
        'shared_image_runtime_cache':'EXCLUDED_EXISTING','cleanup_performed':False}
