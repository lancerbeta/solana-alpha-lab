---
task_id: TASK-02
task_version: "1.2"
title: Workstation bootstrap
phase: P0
status: DONE
depends_on: [TASK-01]
dependency_status: CLOSED
entry_verdict: START_AS_WRITTEN
execution_shape: STAGED
owner: user+assistant
completed_at_utc: "2026-07-20T21:57:51+00:00"
as_of: 2026-07-21
cash_cap: USD_0
cash_spend: USD_0
contains_secrets: false
state_change: DELTA-02-001
---

# TASK-02 — Workstation bootstrap

## 1. Final result

`PASS / DONE`.

Рабочая станция наблюдена, минимальный бесплатный toolchain установлен и проверен повторяемым валидатором. Docker Engine/Compose реально работают, официальный bounded test container выполнен и удалён. Evidence-файлы согласованы, обезличены и прошли redaction scan.

TASK-02 не создавал repository, provider account, API/RPC request, VPS, wallet или signer.

## 2. Accepted workstation

| Область | Accepted evidence |
|---|---|
| OS | Windows 11 Pro, version/build `10.0.26200 / 26200` |
| Architecture | OS 64-bit; process `AMD64` |
| Shell | Windows PowerShell `5.1.26100.8875 (Desktop)` |
| RAM | `31.1 GB` |
| System disk | `344.2 GB total`; `176.5 GB free` at final validation |
| Time | `Russian Standard Time`; W32Time `Running / Auto`; mode `NTP`; status query `PASS` |
| Virtualization | Hypervisor present; firmware virtualization enabled |
| WSL | `2.3.26.0`; default mode 2; no user Linux distribution required |
| Python | CPython `3.14.2 AMD64`; Python 3.10.6 retained, not removed |
| pip isolation | Global interpreter not inside venv; user site enabled; project policy fixed to `uv`-managed environments only |
| uv | `0.11.29` build `901092ee1` |
| Git | `2.55.0.windows.3` |
| Docker | Client/Server `29.6.2`; Linux `amd64`; per-user WSL 2 backend |
| Compose | `docker compose` plugin `5.3.1` |
| Editor | Not installed; explicitly non-blocking for TASK-02 |
| Docker test | Cached official `hello-world:latest`: `PASS`; residual container: `NONE` |

## 3. Decisions

1. Existing Python 3.14.2 was accepted as workstation capability; Python 3.10.6 was not removed.
2. Project dependencies must never be installed globally. TASK-03/04 selects and pins the exact project Python through `uv` after compatibility checks; the project is not forced to use 3.14.
3. `uv` and Git were installed from the WinGet source.
4. Docker Desktop was installed per-user from the official installer resolved through WinGet, using WSL 2 and Linux containers.
5. A separate Ubuntu/WSL distribution was not installed because it had no current consumer.
6. VS Code was not installed because an editor is optional in this task. The developer interface decision belongs to TASK-03 together with the Codex/repository workflow.
7. Docker's cached `hello-world` image may remain; the container was removed and no project state remains.

## 4. Controlled execution log

| Event | Result | State impact |
|---|---|---|
| Read-only OS inventory | PASS after one corrected assistant command | No mutation |
| Resource/tool inventory | PASS | No mutation |
| Python/WinGet/WSL diagnostics | PASS | No mutation |
| Install `uv` | PASS | Intended user-level tool install |
| Install Git | PASS | Intended user-level tool install |
| First Docker WinGet attempt with `--scope user` | Failed before install: no applicable installer | None |
| Docker official per-user install | PASS | Intended user-level install |
| Docker Engine + Compose check | PASS | Engine active |
| Official `hello-world` container | PASS; `--rm`; no residual container | Cached image only |
| First Python diagnostic quoting attempt | Failed read-only | None |
| Corrected time/Python/tool diagnostic | PASS | No mutation |
| `bootstrap_check.py` | 14/14 PASS; exit code 0 | Three sanitized evidence files written |

The failed atoms were diagnosed before proceeding. No broad reset, security-control disablement or destructive replacement was used.

## 5. Validated artifacts

| Artifact | SHA-256 | Role |
|---|---|---|
| `bootstrap_check.py` | `d53dc4f51fd41ddb817f1e3cf54b9282bfa2ea83eb1c036e0314830b5b24bfdc` | Repeatable non-secret validator |
| `env_report.txt` | `44691c228f19ef6b01580318655461b0191e6fdae9418a15fd3a459847b0fb83` | Human-readable sanitized environment |
| `tool_versions.json` | `518e5757fab6711a4364cfc2707e656c913b498d48143d9d529cf4a130367c62` | Machine-readable accepted state |
| `validation_receipt.json` | `5b50b7c0574d323b8dede7e10456832296ce5ac168cd8859e27c4be4d2707270` | 14-check PASS receipt |
| `operator_observation_receipt.json` | `98af4b66c5ff9b885e9afe8774780750d8c6c5efff8a167fdd072d0523991f4e` | Shell, pip/isolation and controlled-failure provenance |

Hashes for the final task record and bundle files are owned by the external checksum manifests to avoid self-reference.

## 6. Definition of Done reconciliation

- [x] OS, architecture and shell recorded without sensitive identifiers.
- [x] Python 3.12+ and 64-bit architecture verified.
- [x] `uv --version` passes.
- [x] `git --version` passes.
- [x] Docker client and healthy Linux engine verified.
- [x] `docker compose` plugin command passes.
- [x] Official bounded test container runs and is removed.
- [x] UTC capability, timezone, NTP mode and Windows time status observed.
- [x] RAM, free disk, hypervisor, firmware virtualization and WSL state recorded.
- [x] `bootstrap_check.py` exits zero and contains no user-specific absolute-path assumption.
- [x] Generated reports contain no username, home path, IP, serial/device ID, token or secret.
- [x] Installation sources, accepted versions, failures and recovery paths recorded.
- [x] Cash spend `$0`; provider/account/API/repository/VPS/wallet/signer side effects `0`.
- [x] Living system state receives `DELTA-02-001`.
- [x] TASK-03 handoff preserves private repository controls and mandatory Project Asset Catalog implementation.

## 7. Recovery and uninstall paths

Use only for a named rollback; do not run as routine cleanup:

```powershell
winget uninstall --id astral-sh.uv -e --source winget
winget uninstall --id Git.Git -e --source winget
winget uninstall --id Docker.DockerDesktop -e --source winget
```

Do not delete broad directories, reset WSL, remove existing Python versions or disable virtualization/security controls.

## 8. State delta

`DELTA-02-001`:

```text
Observed fact:
  Windows workstation and minimal toolchain are now measured and validated.

Old state:
  WORK-001 PROPOSED / workstation UNKNOWN_REQUIRES_ATTESTATION.

New state:
  WORK-001 VALIDATED_ACTIVE.
  Python/uv/Git/Docker/Compose/time/disk/virtualization evidence exists.
  Private repository, Catalog and provider access remain absent.

Affected:
  current_system_state 1.4; roadmap 1.8; P0 archive 7.0;
  active task advances to TASK-03 READY.

Rollback:
  Individual tools can be uninstalled through WinGet, but TASK-02 evidence
  remains immutable historical evidence and statuses must be reconciled.
```

## 9. Handoff to TASK-03

Candidate next task:

`TASK-03 — Private repository, controls & Project Asset Catalog`.

It may enter `IN_PROGRESS` only after a fresh Entry Gate. Mandatory scope:

1. private local Git repository and private remote;
2. dependency lock, `.gitignore`, placeholder-only `.env.example`, secret rejection and CI;
3. `AGENTS.md` plus task/handoff files as the Work↔Codex bridge;
4. Git-tracked `catalog/catalog_manifest.yaml`, versioned JSON Schemas, initial asset/query records, generated map/edges and deterministic validators;
5. empty typed hypothesis/trial/feature/strategy/bot/holdout/reuse/decision registries;
6. import of immutable TASK-01 and TASK-02 artifacts with original IDs, versions, hashes and pre-Git provenance;
7. clean-clone reproduction and accepted commit receipt;
8. living-state catalog checkpoint;
9. graph database remains deferred until measured need.

No provider key, `.env` value, API/RPC call, raw dataset, wallet or signer is allowed in TASK-03.

## 10. Changelog

- `v1.2` — completed workstation bootstrap: actual Windows/tool versions, successful Docker runtime/container check, sanitized deterministic evidence, controlled failure log, state delta and TASK-03 handoff.
- `v1.1` — post-TASK-01 catalog-preserving TASK-03 handoff.
