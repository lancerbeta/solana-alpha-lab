# TASK-28 RC-001 freeze — seven-role Project Sources smoke

PSR-0002-T27-CLOSE is the currently active Project Source release. After the
repository delivery for this candidate is merged and its exact main CI is
successful, replace exactly these five mutable Project Source roles from this
directory:

- `canonical_manifest.yaml`;
- `roadmap.md`;
- `current_system_state.md`;
- `task_archive_P0_P1_v39.md`;
- `task_28_rc001_registry_freeze.md`.

Keep these two existing Project Sources byte-for-byte unchanged:

- Operating System v8.5, SHA-256
  `187aa5d1405c55868d7147a7cdf9e0605a9a51f613ab5597ae44682fcbc67c84`;
- Research Blueprint v2.3, SHA-256
  `ec756d5be0196dd8207ac08512af5e3a9a5032eb5b0b40e3f8fcca2beb170ba1`.

Then run this prompt in the Project chat:

```text
Read Project Sources manifest-first. For each semantic role report:
semantic role -> semantic version -> required header -> actual SHA-256 -> physical filename.

Expected active candidate:
- canonical_manifest 4.9, header `schema: solana_alpha_lab.canonical_manifest`, SHA-256 `191230d2754d243cad2f04f6efd350efb9b29372b4edcd09c88df6f076126da3`, filename `canonical_manifest.yaml`;
- operating_system 8.5, header `# SOLANA ALPHA LAB OPERATING SYSTEM v8.5`, SHA-256 `187aa5d1405c55868d7147a7cdf9e0605a9a51f613ab5597ae44682fcbc67c84`;
- research_blueprint 2.3, contains `Синтетическая версия v2.3`, SHA-256 `ec756d5be0196dd8207ac08512af5e3a9a5032eb5b0b40e3f8fcca2beb170ba1`;
- roadmap 4.9, contains `Версия 4.9`, SHA-256 `02c0c2ce25e66acc137f2a0e3ec89eee69d2f0512da8dfdffc6aedbcd891d6b2`, filename `roadmap.md`;
- current_system_state 4.5, contains `CURRENT SYSTEM STATE — SOLANA MEMECOIN INTRADAY ALPHA LAB v4.5`, SHA-256 `dfde6791e9ba11c1d771731bf4884a6a429799e90715fc90df872605f83d1a8e`, filename `current_system_state.md`;
- phase_archive 39.0, contains `TASK ARCHIVE P0/P1 v39`, SHA-256 `61defb4cfd8e364705282938898717c56b99cc296dbc84508193635585a7292e`, filename `task_archive_P0_P1_v39.md`;
- active_task TASK-28 / 1.0, header `# TASK-28 — RC-001 research registry freeze`, SHA-256 `6eec32612c7ca6b38cc916c449de5457a586271b52c805ad63566595b93958c0`, filename `task_28_rc001_registry_freeze.md`.

Then report exactly:
TASK28_SOURCE_SMOKE=PASS|FAIL;
provider_read_authority=false;
wallet/signer/transaction/cash_authority=false;
next_task_selected=false;
STATE_CHANGE=NONE;
side_effects=0.

If any role/version/header/hash differs, report FAIL. Do not claim activation,
provider authority, new history data, a research trial, PIT, alpha, execution,
PnL, NetReturn or cashflow.
```
