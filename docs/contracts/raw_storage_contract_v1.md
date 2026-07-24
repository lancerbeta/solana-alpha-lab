# Raw storage contract v1 — TASK-06 Atom 2

Status: local uncommitted candidate.

## 1. Purpose

This contract defines the pure, provider-neutral boundary that must run before
any future raw payload reaches durable storage. It converts an in-memory
request identity and response body into a deterministic, redacted
`RawApiEvent`.

Atom 2 does not write files, allocate storage, call a provider, connect to an
API/RPC endpoint, run a collector or change dependencies. Immutable Parquet
pieces and dataset/partition manifests belong to the next separately
authorized atom.

## 2. Accepted upstream truth

The boundary consumes the accepted TASK-05 assets:

- `CONTRACT-T05-DATA-001`;
- `SCHEMA-T05-REL-RAW-API-EVENTS-001`;
- `SCHEMA-T05-PYDANTIC-BOUNDARIES-001`;
- `ADR-MVP-STACK-002`;
- reuse records `REUSE-T04-PARQUET-001`,
  `REUSE-T04-PYARROW-001` and `REUSE-T04-PARQUET-PORT-001`.

`RawApiEvent` remains the canonical row model. This module constructs and
verifies it; it does not create a competing schema.

## 3. Boundary model

```text
in-memory request identity + response payload
→ deterministic redaction
→ canonical UTF-8 bytes
→ request/content hashes
→ deterministic claim identity
→ strict TASK-05 RawApiEvent
```

Only the redacted response bytes may cross the future durable boundary. The
request is represented by a SHA-256 of its canonical redacted identity; raw
request headers, credentials and private URLs are not retained.

## 4. Redaction policy v1.0

The policy is deterministic and fail-closed:

1. UTF-8 JSON objects and arrays are parsed.
2. Sensitive keys are replaced recursively with `[REDACTED]`.
3. Remaining string values are scrubbed for authorization schemes, credential
   assignments, credential-bearing URLs, private-key blocks and user-specific
   machine paths.
4. Caller-supplied secret values are replaced exactly before hashing.
5. JSON is serialized with sorted keys, UTF-8, compact separators and no
   non-finite numbers.
6. Plain UTF-8 text is scrubbed without normalizing line endings or unrelated
   content.
7. Non-UTF-8 payloads fail closed. A future typed adapter must explicitly
   classify public binary program data; Atom 2 does not guess that arbitrary
   binary is safe.
8. Empty bodies remain exact empty bytes. A timeout or error is evidence, not
   an absent row.

Default sensitive key families include authorization, API/access/auth/refresh
tokens, cookies, passwords, client secrets, private keys, seed phrases and
mnemonics. A provider adapter may add key names and explicit values, but it may
not remove the defaults.

The policy cannot prove that an unknown high-entropy value is a credential.
Provider-specific adapters must therefore name non-standard secret fields
before their own runtime authorization.

## 5. Canonical identity

For one prepared event:

- `request_hash = SHA256(canonical_redacted_request_bytes)`;
- `content_sha256 = SHA256(redacted_body)`;
- the idempotency digest is SHA-256 over canonical JSON containing every
  decision-relevant `RawApiEvent` field except `raw_event_id`,
  `idempotency_key` and the body bytes themselves;
- the identity claim includes `content_sha256`, so changed redacted bytes form
  a distinct claim;
- `idempotency_key` is the lowercase 64-hex digest;
- `raw_event_id` is `raw-` plus that digest;
- timestamps are normalized to UTC before identity calculation;
- replaying the same normalized claim returns the same IDs;
- a legitimate revision uses a new response/content identity,
  `revision_number + 1` and `revision_of` pointing to the retained predecessor.

`verify_raw_api_event` recomputes body integrity and deterministic identity. It
rejects tampered bytes, mismatched policy versions, residual high-confidence
secret patterns and altered IDs.

## 6. State and time rules

- Aware timestamps are mandatory.
- `first_reliable_available_at` must not be later than
  `available_to_strategy_at`.
- Event time may be absent only where the upstream source supplies none.
- Response status is exactly one of `SUCCESS`, `HTTP_ERROR`,
  `PROVIDER_ERROR`, `TIMEOUT` or `INVALID_RESPONSE`.
- `SUCCESS` has no error class; every failure has one.
- Missing, empty, timeout and invalid-response states remain distinct.
- Revision zero, self-reference and in-place correction are forbidden.

Atom 2 does not invent stronger timestamp ordering than the accepted TASK-05
model can justify.

## 7. Public API

`solana_alpha_lab.storage` exports:

- `RedactionPolicy`;
- `DEFAULT_REDACTION_POLICY`;
- `canonical_redacted_bytes`;
- `build_raw_api_event`;
- `verify_raw_api_event`;
- typed contract/integrity/redaction errors.

The API performs no I/O and has no network or environment-variable access.

## 8. Security and privacy

- No secret value is logged or included in an exception.
- Source and version identifiers must be public stable identifiers.
- Endpoint/method metadata is scrubbed before it enters the event.
- Raw unredacted bytes are not returned alongside the prepared event.
- The module does not read credentials, `.env`, process environment, files or
  URLs.
- Test values are synthetic and constructed so the repository contains no
  credential-shaped literals.

## 9. Validation and cheapest falsifiers

Atom 2 must fail if any of these occur:

- mapping order changes hashes or IDs;
- nested sensitive JSON survives;
- authorization/query/userinfo credentials survive;
- non-UTF-8 bytes are accepted implicitly;
- identical replay produces different IDs;
- changed content reuses the prior ID;
- empty failure bodies disappear;
- a success/error state violates TASK-05 coherence;
- naive timestamps are accepted;
- tampered body bytes still verify.

Targeted tests cover these cases with deterministic offline fixtures. Full
Catalog registration, generated navigation, repository-state policy and
staging are deferred to a later authorized TASK-06 atom.

## 10. Rollback and non-claims

Before staging or commit, rollback is deletion of exactly the five Atom 2
candidate files after separate destructive authorization. No schema migration,
data or external state exists to undo.

This contract does not claim:

- persistent raw storage;
- atomic filesystem publication;
- dataset/partition fingerprint implementation;
- DuckDB insertion;
- provider compatibility;
- provider/API/RPC calls;
- collected data, alpha, strategy or execution evidence.
