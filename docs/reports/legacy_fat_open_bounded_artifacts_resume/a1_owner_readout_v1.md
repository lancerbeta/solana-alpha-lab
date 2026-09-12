# LEGACY_FAT_OPEN_BOUNDED_ARTIFACTS_RESUME_V1 — owner readout

Paused-only recovery for oversized `publication_jobs/open/` jobs that already
reached `stage=ARTIFACTS`. Routine tick stays fail-closed. No VPS, deploy,
tick, or C1 in this atom.

## Operator flow

Inspect is the pause proof. Do not invent a separate pause command.

1. List open jobs. If the directory is empty, stop. If several files exist,
   pick the exact 64-hex stem you intend to resume — this command never
   auto-scans.

```
ls -1 /opt/solana-alpha-lab/local/factory_v1/observation_rdp/datasets/publication_jobs/open
```

2. Inspect that one identity:

```
/usr/bin/uv run --locked --managed-python python -B scripts/observation_publication_jobs.py inspect-fat-open --runtime-config configs/observation_schedule_runtime_v1.yaml --content <64-hex-content-sha256>
```

3. Continue only on `FAT_ARTIFACTS_RESUME_READY` or `FAT_ARTIFACTS_RESUME_READY_RETRY`.
   `FAT_ARTIFACTS_RESUME_ALREADY_COMPLETE` means the job is already done.
   `COLLECTOR_NOT_PAUSED` means a live collector, an empty set, or the job's
   activation is not `PAUSED_OPERATOR`.
4. Resume (producer SHA comes from Git HEAD or `.factory_deploy_sha`):

```
/usr/bin/uv run --locked --managed-python python -B scripts/observation_publication_jobs.py resume-fat-artifacts --runtime-config configs/observation_schedule_runtime_v1.yaml --content <64-hex-content-sha256> --i-understand-resume
```

5. Expect `FAT_ARTIFACTS_RESUME_COMPLETED` and a compact `completed/` receipt.

Stop on any other terminal. Do not edit JSON. Do not run this while the
collector is live. Do not use it for pre-ARTIFACTS jobs. If resume prints
`FAT_ARTIFACTS_RESUME_PRODUCER_SHA_REQUIRED`, pass `--producer-git-sha` from
`.factory_deploy_sha`.

## What this is / is not

This is a dormant recovery class for the same invariants as the live fat
`open/` residue. It is not a general legacy migrator and does not hardcode the
incident identity.

Ordinary `repair_open_publication_jobs` / `has_open_publication_jobs` / tick
still raise `LEGACY_FAT_OPEN_REQUIRES_PAUSED_MIGRATION`.

## Proof (software)

- Normal publication and fat ARTIFACTS resume converge on the same manifest,
  partitions, RDP payloads, published marker, and compact receipt keys.
- Fault/retry after RDP / manifest / marker / compact receipt converges once.
- Artifact hash mismatch, wrong stage, empty activations, unknown states,
  activation mismatch, missing `members[]`, path escape, and unbounded
  captured strings refuse with the source untouched.
- ACTIVE/DRAINING refuse. Already-complete inspect is distinct from READY_RETRY.
- Memory child: generated members array; MaxRSS below the 768 MiB soft
  envelope. `provider_calls=0`.

## Residual

Pause is a snapshot, same class as existing journal `apply`. This atom does
not add a scheduler lease lock or a new daemon.

## Next (not this atom)

After merge, a separate owner-authorized OPERATE atom may inspect/resume the
live fat `open/` job on Factory. `POST_INCIDENT_CLEANUP_AUDIT` stays later.
