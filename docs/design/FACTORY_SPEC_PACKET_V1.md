---
doc_id: FACTORY_SPEC_PACKET_V1
doc_kind: SPEC_STANDARD
status: DESIGN_ONLY
as_of: '2026-09-06'
owner: GOAL_OWNER
authority: DESIGN_ONLY
implementation: FORBIDDEN_UNTIL_NAMED_TASK
reuse_decision: WRAP
wrapped:
  - OpenSpec change artifacts (intent / delta-specs / design / session-bridge)
  - OpenAI harness-engineering (AGENTS.md as map; Git docs as system of record)
  - Anthropic effective-harnesses + writing-tools (observable tests; agents must not rewrite DoD)
forked:
  - OpenSpec CLI, /opsx slash-commands, openspec/ tree, telemetry
  - Split proposal.md / spec.md / design.md / tasks.md
  - JSON feature-list `passes` scoreboard
  - A living parallel spec store beside tests / protocol / Catalog / exact task contracts
named_consumers:
  - DESIGN_ONLY
  - GOAL_DOD_CRITIC
non_consumers:
  - DIRECT_CURSOR_DELIVERY
  - DIRECT_CODEX_DELIVERY
  - CATALOG_AS_BEHAVIOR_TRUTH
  - OWNER_MERGE_PHRASE
worked_example: docs/design/DELIVERY_HARNESS_DERIVED_SYNC_THROUGHPUT_V1.md
---

# Factory Spec Packet V1

Canonical shape for a **PRD + SSD** in this repository. One Git packet.
Not a second Delivery Harness. Not an executable task.

`MODEL_EFFORT_RECOMMENDATION = SOL_XHIGH` to author or change this standard.
Filling a packet for a later atom is `LUNA_MAX` unless the packet is architecture,
schema, PIT, or safety.

## 0. Reuse verdict

```text
ADOPT  OpenSpec CLI / openspec/ specs+changes tree     NO
WRAP   OpenSpec artifact semantics + lab spec hygiene  YES
FORK   Control plane, archive, living behavior owner   YES (stay on Delivery Harness)
BUILD  A new spec platform, MCP, or schema linter      NO in this DESIGN_ONLY
```

OpenSpec’s useful spine is four **meanings**, not four folders and not a CLI:

| Meaning | OpenSpec file | Factory layer |
|---|---|---|
| Why / who / not | OpenSpec `proposal.md` | L1 PRD |
| Observable behavior change | OpenSpec `specs/` delta | L2 behavior delta |
| How / proof / residue | OpenSpec `design.md` | L3 SSD |
| What a later session actually does | OpenSpec `tasks.md` | L4 session-bridge inside the **same** file |

OpenAI (harness engineering, 2026-02): `AGENTS.md` is a **map**. Specs live in
Git `docs/`. Dumping this standard into `AGENTS.md` is the encyclopedia failure
they already measured. Progressive disclosure: identity in frontmatter, depth
on demand.

Anthropic (effective harnesses; writing tools): a requirement is an
**observable** contract. Agents one-shot, declare victory, and rewrite the
scoreboard. Therefore L2 SHALL lines and the cheapest falsifier are frozen
until the owner revises them. A later implementer may only add tests that
**witness** L2; they may not edit L2 to make the atom look done.

Living behavior after merge is **tests + protocol + Catalog pins**, not a
second spec tree. Archive analog is ordinary Git merge. Exact task contracts
in `docs/tasks/` remain the only EXECUTE binding.

After EXECUTE merge, this packet’s `status` becomes `SUPERSEDED_BY_TESTS`
(or `HISTORICAL` if the atom was replanned). L2 is then an audit trail.
Implementers and later agents MUST treat tests/protocol as living SHALL, not
this file. Leaving `status: DESIGN_ONLY` or `TASK_BOUND` after merge is a
second living spec store and is forbidden.

## 1. Where a packet lives

| State | Path | Authority |
|---|---|---|
| DESIGN_ONLY idea / PRD+SSD | `docs/design/<PACKET_ID>.md` | cannot mutate product or harness |
| Commissioned atom | `docs/tasks/<TASK_ID>.md` | exact contract + owner OK |
| Stable product meaning | `docs/contracts/` and/or tests | after merge |
| Agent map | `AGENTS.md` one-line pointer **later**, not now | harness write; freeze applies |

One packet is **exactly one** Markdown file `docs/design/<PACKET_ID>.md`.
Do not split into `proposal.md` / `spec.md` / `design.md` / `tasks.md`.
Do not create `openspec/`. Unused depth is skipped by not filling optional
layers (`TRIVIAL` / `BOUNDED_ATOM`), not by extra files.

Ceremony is proportional:

| Scale | Required layers | Example |
|---|---|---|
| `TRIVIAL` | none — exact task + cheapest falsifier | typo, comment, one lint |
| `BOUNDED_ATOM` | L0 + L1; L2 if observable behavior changes | ordinary product atom |
| `MATERIAL` | L0–L4 | this standard; derived-sync throughput |

A change that needs “and also” in one sentence is two packets.

## 2. Layers

### L0 Identity (frontmatter)

Machine-readable. Required keys:

```text
doc_id, doc_kind, status, as_of, owner, authority
named_consumers, non_consumers
implementation   # FORBIDDEN_UNTIL_NAMED_TASK | TASK_BOUND | MERGED
status           # DESIGN_ONLY | TASK_BOUND | SUPERSEDED_BY_TESTS | HISTORICAL
```

`doc_kind` is one of `SPEC_STANDARD` | `PRD_AND_SSD` | `PRD` | `SSD`.
`status` is `DESIGN_ONLY` until an exact task exists, then `TASK_BOUND`,
then `SUPERSEDED_BY_TESTS` or `HISTORICAL` after merge/replan.

### L1 PRD (intent)

Owner-readable, agent-executable. Must name:

1. **Owner decision** in one sentence.
2. **Named consumers** and what each needs (not “the team”).
3. **Product outcome** that a later session could witness without this chat.
4. **Cheapest falsifier** — a command or fixture that kills a wrong design
   even if CI on today’s tests is green.
5. **Terminal outcomes** with stable IDs (`*_PASS`, `REPLAN_*`).
6. **Non-goals** specific enough to block the obvious adjacent atom.
7. **Atom card**: `DECISION_DELTA`, `UNCERTAINTY_REMOVED`,
   `CAPABILITY_OR_EVIDENCE`, `STOP`, `NEXT`.

Acceptance criteria are predicates a **fresh agent** can check by running
something and reading output. “Feels faster” is not a criterion.
“unique `desired_sha256` paths equal HASH_SCOPE on the RECORD_ADD_OR_MOVE fixture” is.

### L2 Behavior delta (the missing piece)

This is the OpenSpec delta, aimed at **current Git behavior** (tests,
protocol, code), not at a parallel spec tree.

```text
## ADDED Requirements
## MODIFIED Requirements     # full new SHALL; one line on what changed
## REMOVED Requirements      # why it goes
```

Each requirement is **one** RFC 2119 `SHALL` / `MUST`, observable, no
implementation baked in. Each has ≥1 scenario:

```text
#### Scenario: <named case>
- GIVEN ...
- WHEN ...
- THEN ...
```

Cover the case you would be upset to see broken, not only the happy path.
`SHOULD` is a justified exception, not politeness.

**Classifier:** if the behavior already exists in tests/protocol, it is
`MODIFIED` or already-true (do not `ADDED`-duplicate). If it is new, `ADDED`.
Wrong classifier creates two competing requirements after merge.

L2 is the scoreboard. Implementers do not edit it to pass. Owner revises L2;
then implementation follows.

### L3 SSD (design)

How, only after L1/L2 can be tested. Must name:

- proof obligations / invariants
- current-code mapping (files, functions) without turning L2 into code
- adversarial residue: what can pass unit tests and still fail the outcome
- freeze / authority / what is **not** built so a later cache/shard can plug in

Keep flexibility in **named public tokens** (impact class, projection envelope,
route id). Do not keep flexibility by leaving L2 vague.

### L4 Session-bridge

What a **new context window** reads, in order, and what it is forbidden to
flip. This is Anthropic’s initializer/coding split without a second agent
binary:

```text
READ:   this packet → named tests/protocol → cheapest falsifier fixture
DO:     one intent; leave Git merge-clean
DO NOT: edit L1/L2 to declare victory; start a second packet; thaw freeze
```

Do **not** ship a Markdown checkbox list or a JSON `passes` feature-list as
DoD. Agents check boxes and flip `passes`. Factory DoD is the cheapest
falsifier plus terminal-outcome IDs, later witnessed by tests.

## 3. Lifecycle (same Git harness, not a cloned SDD product)

These are **roles already in Delivery Harness**, not phase gates and not
slash commands. Skip a role when the scale table says so. Do not invent
`/opsx:explore` here.

```text
ORIENTATION / DESIGN_ONLY     write packet; no mutation
GOAL_DOD_CRITIC               falsify L1/L2 before any task exists
exact task + owner OK         only EXECUTE authorization
EXECUTE Delivery Harness      implement; tests witness L2
merge                         packet status → SUPERSEDED_BY_TESTS
```

GOAL_DOD_CRITIC on a packet asks: *can a named consumer falsify this, or will
it pass tests and still miss the outcome?* Architecture critic asks what can
be green and still break research/delivery validity.

A packet is **not** a task. `DESIGN_ONLY` cannot select EXECUTE work.
Commissioning copies identity + L1 outcome into `docs/tasks/`; it does not
rewrite L2 silently. After merge, do not keep L2 as living SHALL.

## 4. Anti-patterns (measured, not taste)

| Failure | Source | Factory rule |
|---|---|---|
| Spec in chat only | OpenSpec problem statement | packet in Git or it does not exist |
| AGENTS.md encyclopedia | OpenAI harness engineering | pointer later; body stays here |
| Behavior mixed into how | OpenSpec writing-specs | L2 vs L3 split |
| Agent rewrites the scoreboard | Anthropic long-running | L2 frozen to implementers |
| Second living spec tree | our Catalog/test truth | no `openspec/specs/`; demote packet after merge |
| Rigid phase gates | OpenSpec vs Spec-Kit | layers editable before EXECUTE; not a command sequence |
| Checkbox / JSON `passes` DoD | Anthropic feature-list cheat | cheapest falsifier owns done |
| Split artifact files | OpenSpec change folder | one Markdown packet |
| Tool/CLI as product | Anthropic writing-tools | wrap semantics; do not wrap npm telemetry |

## 5. What this standard does **not** do

- Install `@fission-ai/openspec`, slash commands, or Stores.
- Mutate `delivery-harness/`, skills, or `AGENTS.md` under the control-plane freeze.
- Replace exact task contracts, Catalog, or bind-evidence.
- Claim product DONE, alpha, or faster science because a packet exists.

## 6. First worked example

`docs/design/DELIVERY_HARNESS_DERIVED_SYNC_THROUGHPUT_V1.md` is the first
`MATERIAL` packet. One intent: HASH_SCOPE follows proof obligation, not
registry membership.

This standard is **not** PASS while that example’s A.4 fails to kill
“hash the whole registry, print a cheap plan, leave `--check` as oracle”.
Judge both together. Skill/critic folklore is not a second packet hiding
inside the example.

## 7. Next (not now)

If commissioned later: one pointer from the delivery-harness skill
(“material DESIGN_ONLY uses FACTORY_SPEC_PACKET_V1”), Catalog pin of this
file, no OpenSpec dependency. Mechanical frontmatter lint is optional and
must not become a new ceremony tax.
