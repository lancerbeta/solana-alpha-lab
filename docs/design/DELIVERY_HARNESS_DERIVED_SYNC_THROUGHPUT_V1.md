---
doc_id: DELIVERY_HARNESS_DERIVED_SYNC_THROUGHPUT_V1
doc_kind: PRD_AND_SSD
packet_schema: FACTORY_SPEC_PACKET_V1
spec_route: BOTH
status: TASK_BOUND
as_of: '2026-09-06'
owner: GOAL_OWNER
named_consumers:
  - DIRECT_CURSOR_DELIVERY
  - DIRECT_CODEX_DELIVERY
  - PRE_COMMIT_DERIVED_SYNC
  - CI_SCOPED_DRIFT_MESSAGE
non_consumers:
  - ISOLATED_CRITICS
  - OWNER_MERGE_PHRASE
  - WORKBENCH
  - RESEARCHSTORE
  - UNSCOPED_CI_CHECK
authority: DIRECT_CURSOR_DELIVERY
implementation: TASK_BOUND
layers: [L0_IDENTITY, L1_PRD, L2_BEHAVIOR_DELTA, L3_SSD, L4_SESSION_BRIDGE]
---

# Delivery Harness derived-sync throughput V1

First worked example of `FACTORY_SPEC_PACKET_V1`. One Git packet: PRD then
behavior delta then SSD. Not an executable task. Not a Catalog redesign.
Not a second hash store. Not an OpenSpec tree.

`MODEL_EFFORT_RECOMMENDATION = SOL_XHIGH` for this contract. Implementation later is `LUNA_MAX` unless the cheap falsifier fails.

## 0. Why this exists

Agents currently treat “hashes” as one ceremony blob that explodes after critics.
That diagnosis is false. Three hash chains exist. Only one is expensive.
The expensive one is usually still labeled `INCREMENTAL`.

Observed on a live product branch versus task `expected_base`:

```text
plan.mode              = INCREMENTAL
full_fallback          = false
navigation_required    = true
REGISTRY_SEMANTIC      = catalog/assets/core.yaml + lifecycle.yaml
direct_sha_assets      = 1534
registered_sha_assets  = 1561
core.yaml members      = 1523
```

A five-asset pin repair via the existing `apply_asset_hashes(..., only_asset_ids=)` path finished in seconds.
The sanctioned `--apply --base-ref` on the same PR would hash ~all of `core.yaml`.
That is the delivery tax. Critics are a correlation, not the cause.

---

# A. PRD-lite

## A.1 Owner decision

Optimize **derived-state maintenance cost** so a normal product atom pays hash/nav work proportional to what actually changed, without weakening fail-closed Catalog integrity, critic isolation, or the bind-evidence freeze.

Do **not** “run Catalog oracle once after all critics PASS”.
That would delay the working-path probe, hide stale pins from Catalog tests, and still leave the O(registry) rule intact.

## A.2 Product outcome

A direct agent on `EXECUTE` sees `HARNESS_SYNC_PLAN` on stderr **before** the
first `desired_sha256`, with impact class, unique HASH_SCOPE size, nav, and
fallback. YAML projection of a large registry vs base may take seconds; that
is not the 15-minute hash tax. Routine Cataloged source edits and routine new
Catalog records no longer imply hashing the factory.

## A.3 Named consumers

| Consumer | Need |
|---|---|
| Cursor / Codex on `EXECUTE` | cheap `--apply --base-ref`; no silent 15-minute oracle |
| Pre-commit `--check --paths-from-staging` | check only what **index vs HEAD** can invalidate |
| CI scoped drift **message** | print `RECORD_ADD_OR_MOVE` + repair command when a **scoped** check fails |
| Future Catalog growth | HASH_SCOPE stays O(changed proof), not O(registry size) |

Unscoped CI `--check` (whole tree, no staging filter) stays the fail-closed
**recovery backstop** and may remain O(registry). It is **not** a cheap V1
consumer. V1 does not weaken that backstop and does not claim CI wall-clock
becomes cheap.

Critics, owner phrase, Workbench, and runtime stores are **not** consumers of this atom.

## A.4 Cheapest falsifier

Class token everywhere: `RECORD_ADD_OR_MOVE`. Equivalence incremental ≡ full is a
**witness**, not a kill: today’s over-hash already preserves bytes.

Fixture: ≥200 existing sha256 members. Add **one** new Catalog record pointing
at **one** new file. Then:

**Kill — apply.** `harness_sync.py --apply --base-ref <fixture-base>`:

1. `mode = incremental` and `full_fallback = false`
2. `HARNESS_SYNC_PLAN` on **stderr** before the first `desired_sha256` call
   (`class=RECORD_ADD_OR_MOVE`)
3. HASH_SCOPE for this class = `affected_paths ∪ NAV_OUTPUTS` (nav is yes).
   `direct_sha_assets` and `hashed_assets_planned` are that unique set.
   Fixture bound: `|HASH_SCOPE| ≤ 8` (today: 1 new path + 3 nav outputs).
   Bound tracks `|affected ∪ NAV_OUTPUTS|`, not a forever magic 8.
4. Spy: unique `repository_path` arguments to `desired_sha256` across **all**
   passes (hash, nav, closure noop) **equals** HASH_SCOPE (same set, same
   cardinality). Repeats of the same path do not inflate the count. In-process
   memo of canonical bytes for a path already hashed in this process is
   allowed and is not `REPLAN_SECOND_HASH_STORE`.
5. `hashed_assets_planned == len(direct_sha_assets) == |unique desired_sha256 paths|`
   and the current-run `hashed_assets` unique-path counter reports the same
   cardinality (a raw invocation counter that counts nav/closure repeats must
   not be the kill metric).
6. Any `desired_sha256` argument **outside** HASH_SCOPE is
   `REPLAN_OVERHASH_WITH_PLAN`, even if unique cardinality stays ≤8.
7. a deliberately stale pin on that new record is repaired

Self-report `hashed_assets` alone is **not** sufficient. A plan line plus a
later untracked full-registry pass is `REPLAN_OVERHASH_WITH_PLAN`.

**Kill — check (named consumer `PRE_COMMIT_DERIVED_SYNC`).** Same fixture,
stage only `catalog/assets/core.yaml`. `harness_sync.py --check --paths-from-staging`
(no `--base-ref`; `CHECK_MODE_REJECTS_APPLY_FLAGS` stays). Classifier input is
**index vs HEAD**, not task `expected_base`. Must obey (2)–(6) and still
fail-closed on that stale pin.

**Required sibling — justifying case (B.5.4).** Same ≥200-member fixture, new
record whose `repository_path` is an **existing unchanged** file with a stale
pin on the new record: unique `desired_sha256` paths stay HASH_SCOPE (that
path ∪ NAV_OUTPUTS, ≤8); neighbors not hashed; stale pin repaired. Special-casing
only “new path” is `REPLAN_OVERHASH_WITH_PLAN`.

**Required sibling before `DERIVED_SYNC_THROUGHPUT_PASS` (same intent, not a
second packet):** purpose/relations-only edit (`SEMANTIC_NAV`) must keep
`len(unique HASH_SCOPE)` within NAV_OUTPUTS, not ≥200. If only `RECORD_ADD_OR_MOVE` is
cheap and purpose-edit still hashes the registry, the MODIFIED SHALL is a lie.

If (3), (4), (5), (6), or the check kill fail, the design is wrong even if t1/t5b/t14
are green and derived bytes match `--full`.

## A.5 Terminal outcomes

| ID | Meaning |
|---|---|
| `DERIVED_SYNC_THROUGHPUT_PASS` | A.4 kills green; HASH_SCOPE ≠ registry membership; full oracle still recovery; bind-evidence and critic isolation unchanged |
| `REPLAN_STALE_PIN_SLIP` | a pin can be stale while `--check` PASSes |
| `REPLAN_OVERHASH_WITH_PLAN` | plan/class look cheap; `direct_sha_assets` or `desired_sha256` still O(registry) |
| `REPLAN_SECOND_HASH_STORE` | any persistent hash cache / sqlite / snapshot became truth |
| `REPLAN_ORACLE_EQUIVALENCE_BROKEN` | HASH_SCOPE ∪ NAV ∪ checkpoint pin/bytes ≠ `--full` on those outputs |
| `REPLAN_CRITIC_COUPLING` | critics now require Catalog sync or Catalog sync waits on critics |

## A.6 User-visible result

Agent-visible:

```text
HARNESS_SYNC_PLAN: class=RECORD_ADD_OR_MOVE hashed=4 nav=1 fallback=none elapsed_ms=...
```

`hashed` is `|HASH_SCOPE|` unique paths (new file ∪ NAV_OUTPUTS), not raw
`desired_sha256` invocations. Always on **stderr**, before the first
`desired_sha256`. JSON reports stay on stdout (current tests
`json.loads(stdout)`). `elapsed_ms` is diagnostic, not a wall-clock gate.

Owner-visible: fewer repair commits, lower `repair_ratio` on product atoms. Not a new dashboard.

## A.7 Non-goals

- Deferring Catalog sync until after critics
- Editing critic launch or making Catalog sync wait on review
- Removing fail-closed `--check`
- Hand-editing `sha256:` fields
- Merging Catalog pins with bind-evidence or packet fingerprints
- Sharding `core.yaml` in this atom
- A background indexer, daemon, or hash database
- Changing merge phrase / OWNER_ATTENTION_GATE_V2
- OpenSpec CLI, `openspec/`, split `proposal.md`/`spec.md`/`design.md`
- Calling the result product DONE / alpha / faster science

## A.8 Evidence budget

One named control atom after freeze. This DESIGN_ONLY packet does not
authorize a friction thaw.
Targeted tests in `tests/test_harness_sync.py`: A.4 apply+check spy on
`RECORD_ADD_OR_MOVE`, plus the SEMANTIC_NAV sibling. Self-report
`hashed_assets` is not the evidence.
No provider, no VPS, no secrets.

## A.9 Replan triggers

- Cheap falsifier cannot run without a 1500-asset clone
- Equivalence with full oracle cannot be proven
- Fix requires a second persistent truth for hashes
- Three consecutive product atoms still show `repair_commits >= 2` after this ships

## A.10 Atom card

```text
DECISION_DELTA:
  HASH_SCOPE follows proof obligation, not registry membership.
  `--check` uses the same classifier. Plan is public on stderr before hash work.

UNCERTAINTY_REMOVED:
  Why “incremental” costs like full; which silent over-proof is safe to drop.

CAPABILITY_OR_EVIDENCE:
  A.4 kills; impact class `RECORD_ADD_OR_MOVE`; fail-closed check; recovery full remains.

STOP:
  Named task is bound. Do not edit L2 to pass. Do not lift CHECK_MODE_REJECTS_APPLY_FLAGS.
  Do not touch owner_attention_gate, critic launch, or bind-evidence inventory.

NEXT:
  Implement HASH_SCOPE so A.4 kills; then isolated critics and guarded merge.
```

---

# A.11 Behavior delta (L2)

Baseline = current Git behavior of `scripts/harness_sync.py` +
`tests/test_harness_sync.py` + derived-hash protocol. These lines are the
scoreboard. A later implementer may add tests that witness them. They may
not edit this section to declare victory.

## ADDED Requirements

### Requirement: Impact class is public before any hash work
The system SHALL emit one `HARNESS_SYNC_PLAN` line on **stderr** containing
`class`, `hashed_assets_planned`, `navigation_required`, `fallback_reason`,
and `base_ref` before the first `desired_sha256` call, including when
`hashed_assets_planned ≤ 8`. Stdout JSON shape is unchanged.

#### Scenario: RECORD_ADD_OR_MOVE announces a cheap plan
- GIVEN a fixture Catalog with ≥200 existing sha256 members
- AND one new Catalog record pointing at one new file versus `expected_base`
- WHEN `harness_sync.py --apply --base-ref <fixture-base>` starts
- THEN stderr contains `HARNESS_SYNC_PLAN` before any `desired_sha256`
- AND `class` is `RECORD_ADD_OR_MOVE`
- AND `hashed_assets_planned` equals `|affected ∪ NAV_OUTPUTS|` (fixture ≤ 8)
- AND `fallback_reason` is empty / none
- AND stdout remains JSON-parseable as today

### Requirement: HASH_SCOPE follows proof obligation
On `RECORD_ADD_OR_MOVE`, `SOURCE_REHASH`, `PIN_DELTA`, and `SEMANTIC_NAV`,
the system SHALL hash only paths whose bytes or pin/path binding changed,
plus `NAV_OUTPUTS` when navigation ran. It SHALL NOT extend HASH_SCOPE to
every sha256 member of the touched registry except `AMBIGUOUS` / `FULL_RECOVERY`.

#### Scenario: New record does not hash neighbors
- GIVEN the same ≥200-member fixture and one new record on one new file
- WHEN `--apply --base-ref <fixture-base>` completes
- THEN `mode = incremental` and `full_fallback = false`
- AND unique `desired_sha256` paths equal HASH_SCOPE (`affected ∪ NAV_OUTPUTS`), cardinality ≤ 8
- AND a path outside HASH_SCOPE was not hashed
- AND nav/closure repeats of those same paths do not fail the equality
- AND a deliberately stale pin on that new record is repaired

#### Scenario: New record on an already-registered path
- GIVEN an existing Catalog path with a correct pin
- AND a new record whose `repository_path` is that same path
- WHEN incremental apply runs
- THEN that path is in HASH_SCOPE once as a unique `repository_path` (nav/closure repeats of the same path do not add neighbors)
- AND both records receive the same pin
- AND other registry members are not in HASH_SCOPE
- AND two live records with disagreeing pins for one path is `AMBIGUOUS` / recovery, not “hash everyone”

#### Scenario: Purpose-only edit is SEMANTIC_NAV not registry rehash
- GIVEN ≥200 members and a purpose/relations/status-only edit on one record
- WHEN `--apply --base-ref <fixture-base>` runs
- THEN `class` is `SEMANTIC_NAV`
- AND `len(direct_sha_assets)` is within NAV_OUTPUTS, not ≥200

### Requirement: Check uses the same classifier as apply
`--check` SHALL apply the same HASH_SCOPE rules as `--apply`. Classifier
**input** for `--paths-from-staging` is index vs HEAD, not `--base-ref`
(`CHECK_MODE_REJECTS_APPLY_FLAGS` stays). Spy bounds match A.4.

#### Scenario: Staged core.yaml is not an oracle
- GIVEN only `catalog/assets/core.yaml` staged because one record was added
- WHEN `harness_sync.py --check --paths-from-staging`
- THEN unique `desired_sha256` paths equal HASH_SCOPE and cardinality ≤ 8
- AND a stale pin on the added record still fails closed

## MODIFIED Requirements

### Requirement: Any semantic registry delta is not a full-registry rehash
Add, move, remove, **or** purpose/relations/status/location/type/search_terms
delta SHALL NOT copy every sha256 member of that registry into HASH_SCOPE.
Previously: `build_impact_plan()` kept `INCREMENTAL` but
`direct.extend(all members of that registry)`.

#### Scenario: Label incremental is not allowed to cost like full
- GIVEN the RECORD_ADD_OR_MOVE fixture
- WHEN incremental apply prints `mode = incremental`
- THEN `len(direct_sha_assets)` is not the same order of magnitude as
  `registered_sha_assets`
- AND a plan line with a later untracked full-registry hash is
  `REPLAN_OVERHASH_WITH_PLAN`
- AND failing this scenario is `REPLAN` even if t1/t5b/t14 stay green

### Requirement: Plan does not occupy stdout
`--apply` / `--check` machine JSON SHALL remain on stdout. Previously: one
JSON blob after the work. The new plan line is an **stderr** prefix, not a
replacement of that contract.

## REMOVED Requirements

None of fail-closed `--check`, full-oracle recovery, critic isolation, or
bind-evidence-after-review. Those are already-true and stay out of this
scoreboard (see A.7). The over-proof “hash every registry member so a new
record cannot keep a stale pin” is withdrawn as a HASH_SCOPE rule; its true
remnant is the single-path case under ADDED above.

---

# B. Design spec (L3)

## B.1 Problem decomposition (do not flatten)

Three chains, three moments, three costs.

```text
Catalog integrity pins + generated nav     ← harness_sync --apply/--check
Delivery inventory freeze                  ← bind-evidence --apply/--verify
Semantic-premise packet fingerprint        ← architecture critic only
```

| Moment | Correct tool | Today’s failure |
|---|---|---|
| Cataloged source or Catalog record changed | `--apply --base-ref` of the **right class** | class collapses to “hash core.yaml” |
| Isolated critics | none of the above | agents resync Catalog “because review” |
| Critics PASS, files unchanged | `bind-evidence --apply` | sometimes another Catalog oracle |
| Ambiguous base / orphan drift | `--apply` full recovery | used as default because the incremental path looks hung |

Critics do not read Catalog pins. Bind-evidence does not need Catalog oracle unless cataloged files changed **after** the review inventory.

## B.2 Root cause (precise)

Not “incremental is unimplemented”.

`build_impact_plan()` already returns `INCREMENTAL`. On semantic registry delta versus `expected_base` it then does:

```text
# Semantic add/move/edit: hash every sha256 member so a new
# record pointing at an unchanged path cannot keep a stale pin.
direct.extend(all asset_ids in that registry)
```

The feared case is real: a **new record** whose `repository_path` already has a pin. The sufficient proof is:

```text
hash(that path) once
write the new record’s pin from those bytes
if two live records share the path → AMBIGUOUS_ASSET_PATH (already fail-closed)
```

Hashing the other 1522 members does not add proof. It only multiplies `canonical_repository_content` (LF/CRLF-aware) on Windows.

Secondary amplifiers:

1. `--check` with staged `catalog/assets/core.yaml` hashes **every** member of that registry (`info["registry"] in scoped_paths`).
2. Full recovery hashes all members **twice** and runs navigation **three** times (`test_t13`).
3. Sync prints nothing until completion, so a 15-minute incremental is indistinguishable from hang → agents escalate to bare `--apply`.
4. `candidate_paths` is the whole PR vs `expected_base`, so one new Catalog record in an otherwise large PR keeps `REGISTRY_SEMANTIC` true for the entire branch lifetime.

## B.3 Design principle

```text
PROOF_OBLIGATION_ISOLATION
```

Each derived write has an explicit proof obligation. Work that does not discharge that obligation is forbidden, even if it feels safer.

```text
HASH_SCOPE  ≠  NAV_SCOPE  ≠  CHECKPOINT_SCOPE  ≠  EVIDENCE_SCOPE
```

| Scope | Obligation | Sufficient work |
|---|---|---|
| HASH_SCOPE | pin matches canonical bytes of its `repository_path` | hash paths whose bytes or pin/path binding changed |
| NAV_SCOPE | generated views match Catalog semantics (purpose, relations, ids, locations) | run generator; then hash NAV_OUTPUTS only |
| CHECKPOINT_SCOPE | manifest counters match observed registry sizes | recount; no file hashes |
| EVIDENCE_SCOPE | completion/review/fit bind the reviewed inventory | `bind-evidence`; never Catalog oracle |

Navigation may run without hashing the factory.
Hashing a new file may run without navigation if only pins moved and semantic projection is unchanged (`test_t5b` already encodes this).

## B.4 Impact classes

Stable machine tokens. First line of `--apply` / `--check` **stderr**.

| Class | Trigger | Hash | Nav | Checkpoint |
|---|---|---|---|---|
| `NOOP` | no derived-relevant delta | 0 | no | no |
| `PIN_DELTA` | registry pin(s) differ, semantic projection equal | those ids only | no | no |
| `SOURCE_REHASH` | registered `repository_path` bytes changed, record identity unchanged | those paths only | no unless path is NAV input | no |
| `RECORD_ADD_OR_MOVE` | new/removed/moved asset_id or path binding | **affected paths ∪ NAV_OUTPUTS** | yes | yes |
| `SEMANTIC_NAV` | purpose/relations/status/location/type/search_terms changed; paths unchanged | NAV_OUTPUTS after generate | yes | maybe |
| `NAV_INPUT` | generator/validator/query recipes/docs inputs | NAV_OUTPUTS | yes | no |
| `AMBIGUOUS` | two records one path; unreadable registry; unresolvable base | full recovery | yes | yes |
| `FULL_RECOVERY` | explicit `--full`, missing unique `expected_base`, or `AMBIGUOUS` | all members | yes, recovery loop | yes |

`RECORD_ADD_OR_MOVE` is the class the current code mis-promotes to “hash entire registry”.

Union of classes in one run is allowed. Cost is the union of scopes, not the max class’s historical over-proof.

## B.5 Stale-pin argument (why the over-proof can go)

Claim to preserve:

> A Catalog record’s `integrity.sha256` equals canonical bytes at `location.repository_path`.

Cases:

1. **Existing record, path unchanged, file bytes changed** → `SOURCE_REHASH` of that path. Neighbors irrelevant.
2. **Existing record, pin edited, file unchanged** → `PIN_DELTA`. Rehash that path, rewrite pin. Neighbors irrelevant. Nav no (`t5b`).
3. **New record, new path** → hash the new path. Neighbors irrelevant.
4. **New record, existing path** → hash that one path; both records must get the same pin or the path is ambiguous. Neighbors still irrelevant.
5. **Two records, one path, different intended files** → `AMBIGUOUS` → recovery/DENY. This is the only case that historically justified “rehash everyone”, and it is already a fallback, not a hash.

Therefore “hash every member so a new record on an unchanged path cannot keep a stale pin” is true only for **that path**. Extending it to the registry is a category error: it confuses **membership change** with **byte change**.

## B.6 Check vs apply

`--check` stays fail-closed. It must use the **same HASH_SCOPE classifier**, not
a coarser one. It does **not** take `--base-ref` (`CHECK_MODE_REJECTS_APPLY_FLAGS`
remains). Pre-commit classifies **index vs HEAD**. Task `expected_base` is only
for `--apply --base-ref`. If HEAD is not the task base, cheap check still uses
HEAD; the repair command is still `--apply --base-ref <expected_base>`.

Today: staging `core.yaml` ⇒ hash 1523 files.
Target: staging `core.yaml` ⇒ classify that index-vs-HEAD delta; hash only HASH_SCOPE.

Unscoped CI `--check` is out of the cheap set (A.3). A scoped failure may print:

```text
DERIVED_HASH_DRIFT: class=RECORD_ADD_OR_MOVE hashed≤N; run harness_sync.py --apply --base-ref <expected_base>
```

Bare `--apply` remains legal **only** for `FULL_RECOVERY`. The message must not recommend it when `expected_base` is unique (`routine_harness_sync_base_ref`).

## B.7 Agent protocol (not this atom’s scoreboard)

Folklore “sync after critics” is **not** current Git protocol and is **not** L2.
This atom’s PASS does not edit the skill. Optional later sentence, after HASH_SCOPE
ships, may tell agents to classify before review and bind-evidence after.
Do not couple critic launch to Catalog sync to close a SHALL that is not here.

## B.8 Visibility contract

`--apply` and `--check` MUST emit `HARNESS_SYNC_PLAN` on **stderr** before the
first `desired_sha256`, including cheap runs. Fields:

```text
class, hashed_assets_planned, navigation_required, fallback_reason, base_ref
```

Stdout stays the existing JSON object. Silence ≥30s with no plan line is a
product bug of this spec. No progress bar in V1.

## B.9 Equivalence and recovery

Witness, not kill. Compare **pin values** (and generated nav/checkpoint bytes)
on `HASH_SCOPE ∪ NAV_OUTPUTS ∪ checkpoint` with a subsequent `--full` on those
same outputs. Do **not** require whole `core.yaml` bytes == `--full`: that would
force hashing neighbor records whose pins were already correct.

Unscoped `--check` DENY for out-of-scope stale pins is the A.3 backstop, not this
witness. Full oracle stays the **recovery instrument**. Do not skip the
second-pass noop in V1; just stop calling full as the routine path.

## B.10 What we will not build (flexibility with a spine)

Allowed later, not this spec:

- Split `core.yaml` by domain (Catalog product atom, not harness)
- Content-addressed blob cache keyed by canonical bytes (would be a **cache**, needs invalidator + measurement first)
- Parallel hashing (only after HASH_SCOPE is O(changed))

Forbidden now and later unless a new named consumer appears:

- Persistent `lifecycle_projection`-style derived DB for pins
- Critic-gated Catalog sync
- Timestamp-winner across truth planes (out of scope; already forbidden elsewhere)

The spine that keeps the door open: **impact class is the public API**. A later cache or shard plugs into HASH_SCOPE without changing bind-evidence or critics.

## B.11 Freeze and authority

Control-plane freeze: do not mutate `delivery-harness/`, harness scripts, or evidence protocol except confirmed blocker / repeated working-path friction / security.

This document is bound by task `DELIVERY_HARNESS_DERIVED_SYNC_THROUGHPUT_V1`.
Owner commissioned EXECUTE. Control-plane freeze lifts only for this write set
(`harness_sync.py`, its tests, scoped protocol drift line, Catalog pins).
It does not lift owner-attention, bind-evidence inventory, or critic launch.

Standing remote-ops grant does not apply.

## B.12 Rollout inside the future task (not now)

One atom, one intent (`HASH_SCOPE ≠ registry membership`):

1. Classifier + A.4 apply/check spy tests + stderr plan line on the existing
   `--apply --base-ref` / `--check` entries
2. CI drift line using `RECORD_ADD_OR_MOVE` (same public token)

Skill/protocol folklore is **not** commit 2 of this atom (B.7).
If A.4 spy bounds fail, revert. Equivalence failing is `REPLAN_ORACLE_EQUIVALENCE_BROKEN`, not a substitute kill.

## B.13 Adversarial misses (architecture residue)

Things that can pass unit tests and still fail delivery:

- Classifier marks `RECORD_ADD_OR_MOVE` but still fills `direct_sha_assets` with the whole registry “for safety”
- Plan/hashed_assets look cheap while a later `desired_sha256` pass hashes the registry without `stats=`
- `--check` and `--apply` disagree on HASH_SCOPE (green commit, red CI)
- Nav-required `RECORD_ADD_OR_MOVE` skips hashing the new file because generator succeeded
- Windows CRLF canonicalization skipped on the cheap path only (2026-08-21 class of bug)
- Purpose-edit still uses `direct.extend(all members)` after RECORD_ADD is bounded

The cheapest live probe after implementation: A.4 unique-path spy vs HASH_SCOPE.
If unique `desired_sha256` paths are ~1500, the atom failed. `hashed_assets_planned`
alone is not the probe.

---

# C. Session-bridge (L4)

A future EXECUTE session has no memory of this chat. Git is the brief.

```text
READ IN ORDER:
  1. this packet L1 + L2 (stop if status is still DESIGN_ONLY)
  2. FACTORY_SPEC_PACKET_V1 only if packet shape is disputed
  3. scripts/harness_sync.py — build_impact_plan, check_drift, apply_sync_incremental
  4. tests/test_harness_sync.py — keep t1/t5b/t13/t14; add A.4 spy bounds
  5. delivery-harness protocol freeze (read-only in this DESIGN_ONLY)

DO:
  implement HASH_SCOPE so A.4 kills
  emit HARNESS_SYNC_PLAN on stderr before the first desired_sha256
  keep incremental ≡ full on HASH+NAV+CHECKPOINT outputs as witness

DO NOT:
  edit L2 SHALL/scenarios to declare victory
  install OpenSpec / create openspec/ / split proposal.md spec.md design.md
  add a hash cache, sqlite, or second pin store
  thaw freeze from this packet
  treat skill/critic folklore as this atom’s DoD
  touch owner_attention_gate.py, critic launch, bind-evidence inventory, Catalog record schema, Workbench
```

`scripts/delivery_efficiency.py` already measures `repair_ratio`; no schema change required.

---

# D. Factory Fit preview (design-time)

```text
Second truth owner?                         NO (pins remain derived from files)
Ordinary runtime Git writes?                NO
Reuse current contracts?                    YES (same --apply --base-ref entry)
Can Move/atom consume without archaeology? YES (HARNESS_SYNC_PLAN)
Missing relations explicit?                 YES (AMBIGUOUS / FULL_RECOVERY)
Speculative infra?                          NO
Defer sync until critics?                   NO
```
