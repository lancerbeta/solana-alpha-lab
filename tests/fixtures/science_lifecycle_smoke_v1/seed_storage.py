"""Only an owned filesystem copy, before any product invocation in volumes."""
import os
import shutil
import sys
from pathlib import Path
if sys.argv[1:] == ['ownership']:
    for target in ('/snapshot','/out'):
        destination=Path(target)
        for entry in [destination,*destination.rglob('*')]:
            os.chown(entry,1000,1000)
    print('OWNED_VOLUME_METADATA_ONLY_CHOWN')
    raise SystemExit(0)
if sys.argv[1:] == ['metadata']:
    for name in ('attempts.jsonl','manifest.json','entry.json','containment-canaries.json','oracle-canaries.json'):
        source=Path('/seed-output')/name
        if source.is_file():shutil.copy2(source,Path('/out')/name)
    print('CAMPAIGN_LEDGER_AND_MANIFEST_COPIED; PRIOR_PARTIAL_WORLD_RETAINED_ON_HOST')
    raise SystemExit(0)
for source,target in [('/seed-product','/snapshot'),('/seed-output','/out')]:
    destination=Path(target)
    assert not any(destination.iterdir()),'OWNED_VOLUME_NOT_EMPTY'
    shutil.copytree(source,target,dirs_exist_ok=True)
    for entry in [destination,*destination.rglob('*')]:
        os.chown(entry,1000,1000)
print('OWNED_STORAGE_SEEDED; NO_PRODUCT_CALL')
