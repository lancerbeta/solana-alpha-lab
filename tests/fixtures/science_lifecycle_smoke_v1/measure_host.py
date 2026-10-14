"""Windows allocation readback; only exact elected checkout and marked runtime."""
import argparse
import ctypes
import json
import os
from pathlib import Path

def measure(roots):
    assert os.name=='nt'
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    create=kernel.CreateFileW
    create.argtypes=[ctypes.c_wchar_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p]
    create.restype=ctypes.c_void_p
    class Standard(ctypes.Structure):
        _fields_=[('allocation',ctypes.c_int64),('length',ctypes.c_int64),('links',ctypes.c_uint32),('pending',ctypes.c_uint8),('directory',ctypes.c_uint8)]
    info=kernel.GetFileInformationByHandleEx
    info.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p,ctypes.c_uint32];info.restype=ctypes.c_int
    close=kernel.CloseHandle
    close.argtypes=[ctypes.c_void_p];close.restype=ctypes.c_int
    seen=set();groups={};errors=[]
    for label,root in roots:
        root=Path(root).resolve()
        item={'logical_bytes':0,'allocated_unique_bytes':0,'files':0}
        for path in root.rglob('*'):
            try:
                if not path.is_file():continue
                stat=path.stat();item['logical_bytes']+=stat.st_size;item['files']+=1
                identity=(stat.st_dev,stat.st_ino)
                if identity in seen:continue
                handle=create(str(path),0x80,7,None,3,0,None)
                if handle in (None,ctypes.c_void_p(-1).value):raise OSError('ALLOCATION_UNAVAILABLE')
                try:
                    value=Standard()
                    if not info(handle,1,ctypes.byref(value),ctypes.sizeof(value)):raise OSError('ALLOCATION_UNAVAILABLE')
                    item['allocated_unique_bytes']+=value.allocation;seen.add(identity)
                finally:close(handle)
            except OSError:errors.append({'scope':label,'relative':path.relative_to(root).as_posix()})
        groups[label]=item
    return {'groups':groups,'allocated_unique_bytes':sum(i['allocated_unique_bytes'] for i in groups.values()),
        'logical_bytes':sum(i['logical_bytes'] for i in groups.values()),'measurement_errors':errors,
        'common_git_objects_runtime_cache_existing_worlds':'EXCLUDED_SHARED_OR_PREEXISTING',
        'directory_metadata_and_output_receipt':'EXCLUDED','cleanup_performed':False}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--runtime',type=Path,required=True)
    parser.add_argument('--checkout',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    assert (args.runtime/'.science-owner').read_text()=='SMIAL_SCIENCE_LIFECYCLE_SMOKE_V1'
    assert (args.checkout/'docs/tasks/SMIAL_SCIENCE_LIFECYCLE_SMOKE_V1.md').is_file()
    value=measure([('elected_checkout',args.checkout),('runtime_snapshot_and_retained_host_output',args.runtime)])
    args.out.write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps(value))

if __name__=='__main__':main()
