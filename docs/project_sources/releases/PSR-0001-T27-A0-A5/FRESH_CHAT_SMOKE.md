# TASK-27 A0-A5 — seven-role Project Sources smoke

After replacing exactly the five mutable Source roles from this directory and
keeping the two immutable roles already in the Project unchanged, run this
smoke in the Project chat:

```text
Read Project Sources manifest-first. For each semantic role report:
semantic role → semantic version → required header → actual SHA-256 → physical filename.

Expected candidate:
- canonical_manifest 4.7, header `schema: solana_alpha_lab.canonical_manifest`, checksum from CHECKSUMS_SHA256.txt;
- operating_system 8.5, header `# SOLANA ALPHA LAB OPERATING SYSTEM v8.5`, SHA-256 `187aa5d1405c55868d7147a7cdf9e0605a9a51f613ab5597ae44682fcbc67c84`;
- research_blueprint 2.3, contains `Синтетическая версия v2.3`, SHA-256 `ec756d5be0196dd8207ac08512af5e3a9a5032eb5b0b40e3f8fcca2beb170ba1`;
- roadmap 4.7, contains `Версия 4.7`, SHA-256 from the manifest;
- current_system_state 4.3, contains `CURRENT SYSTEM STATE — SOLANA MEMECOIN INTRADAY ALPHA LAB v4.3`, SHA-256 from the manifest;
- phase_archive 37.0, contains `TASK ARCHIVE P0/P1 v37`, SHA-256 from the manifest;
- active_task TASK-27 / 1.0, header `# TASK-27 — Bounded public historical price/volume feasibility`, SHA-256 from the manifest.

Then report exactly:
TASK27_A0A5_SOURCE_SMOKE=PASS|FAIL;
repository_main=082f3f8184e84c31c876a484cf8e876a40691f62;
main_ci_run=31224401848 SUCCESS;
provider_read_authority=false;
wallet/signer/transaction/cash_authority=false;
STATE_CHANGE=NONE;
side_effects=0.

If any role/version/header/hash differs, report FAIL and do not claim activation,
provider authority, historical data, PIT, alpha, execution, PnL or NetReturn.
```
