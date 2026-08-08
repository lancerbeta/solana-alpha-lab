# TASK-27 close — seven-role Project Sources smoke

After repository delivery is merged and its exact main CI is successful,
replace exactly these five mutable Project Source roles from this directory:

- `canonical_manifest.yaml`;
- `roadmap.md`;
- `current_system_state.md`;
- `task_archive_P0_P1_v38.md`;
- `task_27_public_history_feasibility.md`.

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
- canonical_manifest 4.8, header `schema: solana_alpha_lab.canonical_manifest`, SHA-256 `8a0e5c8ac5cf7351e15c290214800cf5736457a135c9820f25add392d466d78e`, filename `canonical_manifest.yaml`;
- operating_system 8.5, header `# SOLANA ALPHA LAB OPERATING SYSTEM v8.5`, SHA-256 `187aa5d1405c55868d7147a7cdf9e0605a9a51f613ab5597ae44682fcbc67c84`;
- research_blueprint 2.3, contains `Синтетическая версия v2.3`, SHA-256 `ec756d5be0196dd8207ac08512af5e3a9a5032eb5b0b40e3f8fcca2beb170ba1`;
- roadmap 4.8, contains `Версия 4.8`, SHA-256 `53bb688334ecd98bac53b31fd19c20fdbcad31b7b132cd50e5d1f52003dfb66e`, filename `roadmap.md`;
- current_system_state 4.4, contains `CURRENT SYSTEM STATE — SOLANA MEMECOIN INTRADAY ALPHA LAB v4.4`, SHA-256 `17ece52a06f166c7e3e32593fa5cfaf20a6113d97cb0b40029d7c831b7543a7d`, filename `current_system_state.md`;
- phase_archive 38.0, contains `TASK ARCHIVE P0/P1 v38`, SHA-256 `2b2cc851fd825aa55286e4101e6e0fd4a1d04734464aa8e545fb058a7b8ba864`, filename `task_archive_P0_P1_v38.md`;
- active_task TASK-27 / 1.1, header `# TASK-27 — Bounded public historical price/volume feasibility`, SHA-256 `439d7668304938ef4f252f9ca87a00a2fbd7ce72eda9de24d94563e54244731a`, filename `task_27_public_history_feasibility.md`.

Then report exactly:
TASK27_CLOSE_SOURCE_SMOKE=PASS|FAIL;
provider_read_authority=false;
wallet/signer/transaction/cash_authority=false;
next_task_selected=false;
STATE_CHANGE=NONE;
side_effects=0.

If any role/version/header/hash differs, report FAIL. Do not claim activation,
provider authority, new history data, PIT, alpha, execution, PnL, NetReturn or cashflow.
```
