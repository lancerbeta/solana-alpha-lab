"""Lossless evidence bytes; producer-private prefixes stay tokenized in Git."""
from __future__ import annotations
import argparse,base64,hashlib,json,os,zlib
from pathlib import Path,PurePosixPath

def bindings(workspace: str, profile: str) -> dict[bytes,bytes]:
    values={}
    for stem,value in (('WORKSPACE',workspace),('PROFILE',profile)):
        win=value.replace('/','\\').rstrip('\\');posix=win.replace('\\','/')
        for kind,text in (('WIN',win),('POSIX',posix),('WIN_LOWER_DRIVE',win[:1].lower()+win[1:]),('POSIX_LOWER_DRIVE',posix[:1].lower()+posix[1:])):
            for depth in range(5):
                encoded=text.replace('\\','\\'*(2**depth)).encode('utf-8')
                token=f'@@EGG_BIND_{stem}_{kind}_D{depth}@@'.encode('ascii')
                if encoded not in values:values[encoded]=token
    return values

def materialize(bundle: Path, output: Path, *, workspace: str, profile: str) -> dict:
    body=json.loads(bundle.read_text(encoding='utf-8'))
    if body.get('schema')!='smial.egg-tokenized-raw-evidence' or body.get('schema_version')!='1.0':
        raise ValueError('EVIDENCE_BUNDLE_VERSION_UNSUPPORTED')
    restore={token:raw for raw,token in bindings(workspace,profile).items()}
    objects=body['objects'];base=output.resolve();base.mkdir(parents=True,exist_ok=True)
    count=0
    for entry in body['files']:
        name=PurePosixPath(entry['path'])
        if name.is_absolute() or '..' in name.parts or ':' in str(name):
            raise ValueError('EVIDENCE_OUTPUT_PATH_INVALID')
        obj=objects[entry['object_sha256']]
        raw=zlib.decompress(base64.b64decode(obj['zlib_base64'],validate=True))
        if len(raw)!=obj['normalized_bytes'] or hashlib.sha256(raw).hexdigest()!=entry['object_sha256']:
            raise ValueError('EVIDENCE_OBJECT_HASH_MISMATCH')
        for token,value in restore.items():raw=raw.replace(token,value)
        if b'@@EGG_BIND_' in raw:
            raise ValueError('EVIDENCE_MATERIALIZATION_BINDING_REQUIRED')
        if len(raw)!=entry['original_bytes'] or hashlib.sha256(raw).hexdigest()!=entry['original_sha256']:
            raise ValueError('EVIDENCE_ORIGINAL_BYTE_HASH_MISMATCH:'+entry['path'])
        dest=base.joinpath(*name.parts).resolve()
        if not dest.is_relative_to(base):raise ValueError('EVIDENCE_OUTPUT_PATH_INVALID')
        dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw);count+=1
    return {'status':'LOSSLESS_BYTE_HASH_PASS','files':count,'private_paths_in_output_only':True}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle',type=Path);parser.add_argument('output',type=Path)
    parser.add_argument('--workspace-root',default=str(Path(__file__).resolve().parents[3]))
    parser.add_argument('--profile-root',default=os.environ.get('USERPROFILE'))
    args=parser.parse_args()
    if not args.profile_root:parser.error('profile-root binding required')
    print(json.dumps(materialize(args.bundle,args.output,workspace=args.workspace_root,profile=args.profile_root),sort_keys=True))
