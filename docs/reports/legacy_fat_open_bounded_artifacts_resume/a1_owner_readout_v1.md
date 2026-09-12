# LEGACY_FAT_OPEN_BOUNDED_ARTIFACTS_RESUME_V1 — owner readout

Paused-only recovery for oversized `publication_jobs/open/` jobs that already
reached `stage=ARTIFACTS`. Routine tick stays fail-closed. No VPS, deploy,
tick, or C1 in this atom.

## Operator flow

1. Prove the collector is not `ACTIVE`/`DRAINING` and that at least one
   activation is registered (empty set is not a proven pause).
2. Copy `--content` from the `open/<64-hex>.json` filename stem:

```
ls -1 /opt/solana-alpha-lab/local/factory_v1/observation_rdp/datasets/publication_jobs/open
```

3. Inspect:

```
/usr/bin/uv run --locked --managed-python python -B scripts/observation_publication_jobs.py inspect-fat-open --runtime-config configs/observation_schedule_runtime_v1.yaml --content <64-hex-content-sha256>
```

4. Continue only on `FAT_ARTIFACTS_RESUME_READY` or `FAT_ARTIFACTS_RESUME_READY_RETRY`.
   `FAT_ARTIFACTS_RESUME_ALREADY_COMPLETE` means the job is already done.
5. Resume (producer SHA comes from Git HEAD or `.factory_deploy_sha`):

```
/usr/bin/uv run --locked --managed-python python -B scripts/observation_publication_jobs.py resume-fat-artifacts --runtime-config configs/observation_schedule_runtime_v1.yaml --content <64-hex-content-sha256> --i-understand-resume
```

6. Expect `FAT_ARTIFACTS_RESUME_COMPLETED` and a compact `completed/` receipt.

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
- Artifact hash mismatch, wrong stage, empty activations, path escape, and
  unbounded captured strings refuse with the source untouched.
- ACTIVE/DRAINING refuse. Already-complete inspect is distinct from READY_RETRY.
- Memory child: ~16.8 MiB generated members array; MaxRSS **85954560 B (~82 MiB)**,
  below the 768 MiB soft envelope. `provider_calls=0`.

## Next (not this atom)

After merge, a separate owner-authorized OPERATE atom may inspect/resume the
live fat `open/` job on Factory. `POST_INCIDENT_CLEANUP_AUDIT` stays later.
