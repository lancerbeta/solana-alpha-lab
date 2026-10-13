"""Measure only the explicitly supplied campaign root; never clean anything."""
import argparse
import ctypes
import json
import os
from pathlib import Path

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);a=parser.parse_args()
    root=a.root.resolve();assert root.is_dir() and (root/'source/docs/tasks/SMIAL_SYNTHETIC_LIFECYCLE_SMOKE_V1.md').is_file()
    assert os.name=='nt'
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    create=kernel.CreateFileW;create.argtypes=[ctypes.c_wchar_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p];create.restype=ctypes.c_void_p
    class Standard(ctypes.Structure):
        _fields_=[('allocation',ctypes.c_int64),('length',ctypes.c_int64),('links',ctypes.c_uint32),('pending',ctypes.c_uint8),('directory',ctypes.c_uint8)]
    info=kernel.GetFileInformationByHandleEx;info.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p,ctypes.c_uint32];info.restype=ctypes.c_int
    close=kernel.CloseHandle;close.argtypes=[ctypes.c_void_p];close.restype=ctypes.c_int
    groups={};seen=set();errors=[]
    for path in root.rglob('*'):
        if not path.is_file() or path==a.out.resolve():continue
        try:
            stat=path.stat();rel=path.relative_to(root)
            group='source/.venv' if rel.parts[:2]==('source','.venv') else rel.parts[0]
            item=groups.setdefault(group,{'logical_bytes':0,'allocated_unique_owned_bytes':0,'files':0})
            item['logical_bytes']+=stat.st_size;item['files']+=1
            identity=(stat.st_dev,stat.st_ino)
            if identity not in seen:
                handle=create(str(path),0x80,7,None,3,0,None)
                if handle in (None,ctypes.c_void_p(-1).value):raise OSError('ALLOCATION_UNAVAILABLE')
                value=Standard()
                try:
                    if not info(handle,1,ctypes.byref(value),ctypes.sizeof(value)):raise OSError('ALLOCATION_UNAVAILABLE')
                    item['allocated_unique_owned_bytes']+=value.allocation;seen.add(identity)
                finally:close(handle)
        except OSError:errors.append(path.relative_to(root).as_posix())
    receipt={'scope':'EXACT_CAMPAIGN_ROOT_ONLY','groups':groups,
        'logical_bytes':sum(x['logical_bytes'] for x in groups.values()),
        'allocated_unique_owned_bytes':sum(x['allocated_unique_owned_bytes'] for x in groups.values()),
        'measurement_errors':errors,'deleted':False,
        'allocation_limit':'NTFS allocation deduplicated within campaign; hardlinks to existing uv cache may overstate incremental allocation. Directory metadata and measurement receipt excluded.'}
    a.out.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))

if __name__=='__main__':main()
