# Owner readout — DELIVERY_HARNESS_LOCATION_AWARE_INCREMENTAL_SYNC_V1

## Trigger → rule → HASH_SCOPE → time → backstop → residual

1. **Trigger.** Routine `--apply --base-ref` hit `INCREMENTAL_SCOPE_UNPROVEN` because `_registry_path_index` required `repository_path` on every `integrity.kind=sha256` record. Live Catalog correctly holds `external_bundle` / `logical_only` SHA rows without a local path (10 on measured main). Local rehash only ever covered `sha256 + git_path`.

2. **Rule.** Shared `_sha256_location_class`: local `git_path` pins are derived (path required; stripped in semantic projection; path-index + pin-delta only). External/logical SHA stays primary semantic; never locally rehashed. Corrupt `git_path`, unknown location, ambiguous structure stay fail-closed.

3. **HASH_SCOPE.** Representative `RECORD_ADD_OR_MOVE` on real Catalog: spy unique paths = new local file ∪ NAV_OUTPUTS (4). Unchanged neighbors and external objects absent. Plan: `fallback=none`, `full_fallback=false`.

4. **Time.** Measured `elapsed_ms=48607` (~49s) vs historical ~20.3 min full fallback under similar Catalog size (~1712 SHA assets). Approx **25×**; floor 5× met. Not a CI wall-clock assert.

5. **Full backstop.** Bare `--apply` / `--apply --full` and unscoped `--check` unchanged. This atom does **not** accelerate all of CI.

6. **Residual risk.** Future unknown `location.kind` values still force full fallback (intentional). Semantic external-SHA edits still require navigation. Stale historical timing conditions differ; trust the spy/plan counters over folklore.
