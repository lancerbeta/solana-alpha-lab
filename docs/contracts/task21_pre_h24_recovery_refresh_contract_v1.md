# TASK-21 pre-H24 recovery refresh and capture-prep contract v1

`T21-A6S_PRE_H24_RECOVERY_REFRESH_AND_CAPTURE_PREP_V1` protects the exact H0,
H1 and explicit H6-gap evidence before the H24 sentinel. It creates one
deterministic, content-addressed ZIP locally; creates one new private file in
the existing TASK-21 Google Drive recovery folder; reads the remote bytes back;
and proves an isolated restore byte-for-byte.

The frozen source set is 23 files and 270,498 stored bytes under the three
exact local run roots named in the YAML contract. Every source byte is indexed
by path, size and SHA-256 in the archive manifest. The ZIP uses fixed metadata,
stored entries and a content-addressed filename, so identical inputs produce
identical bytes.

All writes are create-only. Existing source files, local archives, restore
trees and Drive objects may be verified but never overwritten or deleted. A
same-name Drive object blocks upload unless its exact bytes are independently
proven identical; it is not silently reused as a fresh backup event.

H24 remains a separate boundary. This atom may prepare its deterministic
implementation and satisfy recovery freshness, but grants zero market-provider
API/RPC/WSS calls, zero credentials, zero cash spend and zero wallet, signer or
transaction actions. H24 provider execution still needs its own exact user
gate inside `2026-08-01T07:50:34.414367Z` through
`2026-08-01T08:00:34.414367Z`; after that window only an explicit gap is valid.

Catalog finalization stays pending until TASK-21 A7. A local archive, Drive
upload, quote response or successful process is not evidence of fills,
positions, PnL, alpha or dataset sufficiency.
