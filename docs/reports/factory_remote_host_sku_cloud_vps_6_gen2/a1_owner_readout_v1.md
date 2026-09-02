# Owner readout — FACTORY_REMOTE_HOST_SKU_CLOUD_VPS_6_GEN2_V1

## Terminal

`FACTORY_REMOTE_HOST_SKU_LOCATOR_UPDATED`

## What changed

- `docs/operator/factory_remote_host_v1.yaml`: `sku` `CLOUD_VPS_4_GEN2` → `CLOUD_VPS_6_GEN2`, `as_of` `2026-09-02`
- `docs/operator/FACTORY_REMOTE_HOST.md`: host table SKU cell updated
- Catalog content hashes rebound for the two locator assets in `catalog/assets/core.yaml`

## Live proof

SSH read-only 2026-09-02: hostname `factory-remote-ops`, nproc 6, Mem 5.8Gi, vda 100G, `/` 96G, ipv4 `5.199.174.153`, instance `973818` unchanged.

## What did not change

ipv4, hostname, SSH, deploy root, collector protocol, purchase-floor configs/schemas, doctor JSON sku enum (stays floor until later unfreeze).

## Next

None from this atom.
