"""Losslessly materialize immutable native evidence; never adapt a production packet."""
from __future__ import annotations
import hashlib,json,sys
from pathlib import Path

def materialize(bundle_path: Path, output_dir: Path) -> None:
    bundle=json.loads(bundle_path.read_text(encoding="utf-8"))
    objects=bundle["objects"]
    def expand(value):
        if isinstance(value,dict):
            if set(value)=={"$flow_ref"}:
                return expand(objects[value["$flow_ref"]])
            return {key:expand(child) for key,child in value.items()}
        if isinstance(value,list):
            return [expand(child) for child in value]
        return value
    output_dir.mkdir(parents=True,exist_ok=True)
    for name,entry in bundle["files"].items():
        if Path(name).name!=name:
            raise ValueError("EVIDENCE_OUTPUT_NAME_INVALID")
        value=expand(entry["content"])
        if entry["format"]=="text":
            raw=value.encode("utf-8")
        else:
            options=entry["serialization"]
            raw=(json.dumps(value,ensure_ascii=options["ensure_ascii"],indent=options["indent"],separators=tuple(options["separators"]))+options["trailing"]).encode("utf-8")
        if hashlib.sha256(raw).hexdigest()!=entry["file_sha256"]:
            raise ValueError("EVIDENCE_BYTE_HASH_MISMATCH:"+name)
        (output_dir/name).write_bytes(raw)
        print(name,entry["file_sha256"])

if __name__=="__main__":
    materialize(Path(sys.argv[1]),Path(sys.argv[2]))
