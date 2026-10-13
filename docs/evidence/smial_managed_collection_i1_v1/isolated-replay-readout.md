# I1 isolated C1/C2 replay — bounded readout

Scope: disposable `local/smial_managed_collection_i1_run_03` only. This is
software/recovery evidence, not a production C2 import or Drive backup. The
machine result is `isolated-proof.json`; the five public CLI responses remain
under `local/smial_managed_collection_i1_run_03/receipts/` with their SHA256
and wall time recorded in that result. Reproduce its cold independent oracle:

```text
uv run --locked --managed-python python -B scripts/prove_managed_collection_i1.py --work-root local/smial_managed_collection_i1_run_03 --verify-existing --exercise-historical-fallback --exercise-imported-conflict --exercise-metadata-conflict
```

The original C2 stop receipt reported `MIRROR_CONFLICT` at
`datasets/members_snapshot_plus_delta/20261011/unit.json`: C1 mirror had
8 publications (9,146 bytes), C2 source had 24 (27,581 bytes). Of 3,082
manifest files / 33,819,016 payload bytes, 2,000 were identical in the shared
mirror, 1,081 were absent and one mutable path conflicted. Original transfer
placed zero files and imported zero cohorts. Its diagnostic
`capture.transfer_manifest_sha256=11b8c96c3d609ddc4e215d7f2fceef8e4e30012ab000640597158cfb3d9ab3a`
disagrees with the preserved packet's self-verified manifest hash
`5b06e711b46e65740889446fc3e138358c552727e15e264c85eb9171a3fb7009`;
the latter is used for replay and the inconsistency remains explicit. The stop
receipt's packet SHA256 agrees with the exact packet bytes
`5422507511381f587dd4d970088530b963d5ef98349b20e2148186181408d6ef`.

The fresh public CLI C2 import returned `IMPORTED` in 299.52 seconds:
1,082 files transferred, 2,000 reused, epoch bump true, capture-scoped source
view exact for 3,082/3,082 manifest dependencies, sealed release
`5532f3b0f69c5a22d2dd3e4111162a90e19b92aab3de40d1a95e4a9e147df51d`.
The same command repeated C2 in 271.36 seconds with
`PASS_ALREADY_PRESENT_EXACT`, zero transferred files and no epoch bump.
Historical C1 public replay took 301.48 seconds and returned
`PASS_ALREADY_PRESENT_EXACT` with no epoch bump. A read-only `--plan-only`
probe on a separate disposable C1 copy reported 2,000 reusable and 1,082
missing files, zero conflicts, zero imports, and no transfer or corpus write.

An independent cold reader compared source Parquet with installed corpus by
exact episode/point/field membership, state and missingness. C1 has 24 episodes,
3,336 episode-point pairs, 53,376 field rows and fingerprint
`566394db5cb788dacf1e223cd5fe9aaa6188389afe5c7e9ba3cf7cb1581ae565`.
C2 has 23, 3,197, 51,152 and
`470ae82d8c168bfda8c86bebdba9f546518235665cc3d19995ba26425e9dd36f`;
total 47 episodes / 6,533 pairs. All eight original canonical C1 pins remain
exact. In the disposable corpus six C1 files remain byte-exact and one C1
labels file changes only its current-version boolean as C2 becomes current.
The C1 sealed release manifest is byte-exact.
The independent row oracle does not compare field values or availability
timestamps; release/file hashes and the existing release verifier cover bytes,
while this I1 result makes no new PIT or scientific-validity claim.

With one exact C1 metadata source temporarily absent, and separately with only
a later grown version present, the public path returned
`EPISODE_BATCH_REPLAY_SOURCE_MISSING` plus a fully verified imported-release
replay; neither case claimed new transfer or import. A temporarily altered
installed C2 release manifest refused with `CANONICAL_TARGET_CONFLICT`;
missing current labels and altered `yield_missing` both refused with
`CANONICAL_METADATA_CONFLICT`. A partition manifest redirected to a different
valid copied Parquet payload, with internally valid partition/dataset hashes,
validation and published fingerprint, also refused with
`CANONICAL_METADATA_CONFLICT` because it disagreed with lineage. Disposable
bytes were restored after each negative probe. The latest cold independent run
took 44.75 seconds; it is verification time, not first-transfer wall time.

The earlier run_01 first C2 invocation exceeded a 300-second caller wait after
committing release/corpus but before a terminal receipt. Its resumed public
command succeeded, yet that interrupted invocation is not called an
uninterrupted PASS. The first proof script then failed on a wrong oracle that
counted field rows instead of unique pairs. A subsequent run_02 proof script
failed before C2 on a mistaken expectation about C1 currentness; the corrected
fresh run_03 and cold replay above passed. A full vertical test first reached
the ordinary Forge draft step after P1 capture and P2 consume, then refused
`PREFLIGHT_GIT_COMPOSITE_MISMATCH` against the dirty working tree. A committed
run then exposed a new test's incorrect assumption that its small synthetic
fixture contained a day-open `member_unit`; it actually publishes plain member
files. The corrected vertical test passed on a clean commit in 242.40 seconds;
after the metadata verifier correction it passed again on a clean commit in
243.61 seconds. Focused owner-path/harness tests passed nine cases after that
correction. A sampled C2 worker process showed
at least 174,604,288 bytes PeakWorkingSet64; this is a lower-bound snapshot,
not a measured end-to-end peak RSS. End-to-end peak RSS remains `UNKNOWN`.

No collector, grant, frozen schedule, provider, production mirror/corpus or
Drive recovery object was modified. The next actual C2 consume remains under
the separately gated `C2_OPERATE_PACKET.md`; this readout cannot claim
`DELIVERY_FIXED_AND_C2_IMPORTED`.
