# TASK-30 A21 Patched Bitquery One-Shot Plan

**Goal:** Execute one patched Bitquery request on the evidence-retaining client without retrying A20 or promoting TASK-30.

**Architecture:** Closed YAML/schema reuse A20 identity and the patched HTTP-evidence client on `3b532d6…`. A21 CLI writes only A21 paths. A20 receipts remain immutable.

## Constraints

- Same pool, mints, program, endpoint and UTC window as A20.
- `capture_authorized=true`; one preflight, one POST, one credential read.
- New raw root `local/task30_a21_bitquery_one_shot/`; new tracked receipt `a21p_…`.
- Zero retry, fallback, second provider, cash or TASK-30 promotion.
- Token value never enters Git, chat, CLI arguments, URL, receipts or logs.

## Tasks

1. Closed contract tests, schema, config, task file, design contract and A21 CLI.
2. Catalog registration and generated navigation, including the A21 script.
3. Credential-free DNS/TCP/TLS preflight, then one patched POST.
4. Record the A21 runtime receipt. Stop. Do not retry.

## Stop

One provider request consumed, or `BITQUERY_TOKEN_MISSING_OR_EXPIRED` /
`DNS_TCP_TLS_PREFLIGHT_FAIL` before that request.
