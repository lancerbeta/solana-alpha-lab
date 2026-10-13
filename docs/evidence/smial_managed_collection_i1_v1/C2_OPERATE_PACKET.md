# C2 consume — prepared OPERATE packet, not an authorization

State: `PREPARED_NOT_EXECUTED`. This packet is for a separate exact owner
OPERATE decision after the I1 PR is merged and its main CI/readback succeeds.
It does not authorize a deploy, production import, Drive write or change to
the running collector `ACT-4744D4017AC4B196`, its grant or frozen schedule.

Target is only `REL-20261008T000000Z-20261009T000000Z` from the preserved
version-1 packet at
`local/canary_exit_and_100_per_day_arm_v1/20261013_resume/c2-capture-packet.json`
(SHA256 `5422507511381f587dd4d970088530b963d5ef98349b20e2148186181408d6ef`).
Its manifest self-hash is
`5b06e711b46e65740889446fc3e138358c552727e15e264c85eb9171a3fb7009`.
The old stop receipt carries a different diagnostic manifest hash
(`11b8c96c3d609dddc4e215d7f2fceef8e4e30012ab000640597158cfb3d9ab3a`)
despite naming the same packet SHA. Revalidate the packet self-hash and exact
staging before OPERATE; do not use the diagnostic field as the transfer identity.
The verified source package has 3,082 files and 33,819,016 payload bytes;
its saved root is
`local/canary_exit_and_100_per_day_arm_v1/20261013_resume/c2-source-rdp`.
The physical package inventory fingerprint is
`568af0a61919f68efc513c80ce91abc808b54c8080475fca7cfb4cff5c18db79`:
SHA256 of the canonical sorted array of `{path,bytes,sha256}` for each manifest
entry, where `path=transfer_path` if present, otherwise `path`. Recompute each
physical file hash/size against the packet before accepting this inventory.
The old mirror had 2,000 exact reusable files, 1,081 missing, and one
`member_unit` path with C1's 8-publication version instead of C2's 24.
C1 exact sealed release ID is
`1128cbcad55e4f11f666722d5b967b1aa5b3c8624ca3dfb9d02981c5651fe47c`.
The isolated C2 rehearsal sealed release ID is
`5532f3b0f69c5a22d2dd3e4111162a90e19b92aab3de40d1a95e4a9e147df51d`;
production must derive and verify its own release, never accept that rehearsal
ID as authorization.

Before any production write, bind the merged main SHA, installed workstation
consumer SHA, exact C1 release/corpus/manifests hashes, C2 packet and source
inventory fingerprint above, current independent recovery copy and free-space/headroom. Re-read
the live collector only as a non-mutating health check. Refuse if source
material, C1 pins, write target, installed consumer or recovery coverage differs.
No new producer capture is required for this saved C2 packet. Version-2
producer capture needs a separately approved producer deploy before claiming
protection from future `unit.json` appends.

1. Make a detached working/recovery copy of exact C1 manifest dependencies,
   C1 sealed release, current C1 corpus and manifests, and the C2 source
   package. Inventory/hashes and independently verify that copy. Do not copy
   the whole 5.57-GB shared mirror by default; select named dependencies.
2. From the repository root, run `uv run --locked --managed-python python -B
   scripts/prove_managed_collection_i1.py --work-root
   local/smial_i1_operate_rehearsal_001` against the current installed consumer
   in a fresh process. The work root must be a new directory under `local/`.
   Re-run with that same root and `--verify-existing` immediately before
   OPERATE to revalidate the saved source inventory and isolated C1/C2 pins.
   Require C2 source
   view 3,082/3,082 exact, no conflicts, C1 unchanged and an independently
   readable C2 release/corpus. The already observed isolated rehearsal is
   evidence for code, not authority for production import.
3. Resolve the workstation target root read-only from the merged task binding,
   current installed consumer and live local paths. The expected paths in this
   checkout are `local/factory_mirror/observation_rdp` and
   `local/factory_v1/data_plane`; if either does not exist or differs from the
   C1 pins, stop for a revised exact gate. Under the separate exact OPERATE
   gate, first run the exact command below with `--plan-only`: it is a read-only
   capture-view plan and should report 2,000 reused, 1,082 missing and zero
   conflicts against today's C1 mirror. If those numbers drift, inspect and
   rebind the source/target before writes. Then run the ordinary
   `uv run --locked --managed-python python -B scripts/discovery_evidence_release.py
   unpack-next-live-cohort --collection
   OPPORTUNITY_EPISODES --max-cohorts 1 --capture-packet
   local/canary_exit_and_100_per_day_arm_v1/20261013_resume/c2-capture-packet.json
   --source-rdp local/canary_exit_and_100_per_day_arm_v1/20261013_resume/c2-source-rdp
   --mirror-rdp local/factory_mirror/observation_rdp
   --data-root local/factory_v1/data_plane` once. C1 is verify-only. Record the
   chosen `--as-of` instant.
4. Read back release manifest, census and observations through a fresh process.
   Require C1 24 episodes/3,336 episode-point pairs and C2 23/3,197, cumulative
   47/6,533, with original missingness/states. Require C1 pins unchanged.
   Repeat the *identical* C2 packet and release; require
   `PASS_ALREADY_PRESENT_EXACT`, `epoch_bump=false`, no newly transferred
   bytes and unchanged lineage/release hashes. Replay old C1 packet against its
   saved source view and verify its sealed/imported bytes.
5. If the new C2 sealed release lacks an independent recovery copy, use the
   existing recovery owner under that same exact approved scope, verify the
   copied bytes independently and record its locator/hash. No new backup
   service or grant scope is implied.

Abort before any write for a failed pin, missing version, wrong target or
missing independent copy. An interrupted transfer resumes with the same packet
and verified fragments; a torn import uses the existing import intent and
forward repair. Never restore a pre-C2 corpus snapshot over newer commits, or
delete lineage to make a retry pass. Before C2 writes, consumer code may be
reverted. After new writes, recovery is forward-only and must preserve every
already committed cohort. Stop at an integrity conflict and report its first
failing object; no manual `unit.json` replacement or provider call.

Expected handback is section 12 of the accepted PRD/SSD with measured files,
bytes, wall/RSS, release/lineage identities, new recovery coverage and one
next tactical decision. `DELIVERY_FIXED_AND_C2_IMPORTED` requires this real
consume and verification; Git merge and isolated rehearsal alone are
`CODE_READY_RUNTIME_PENDING`.
