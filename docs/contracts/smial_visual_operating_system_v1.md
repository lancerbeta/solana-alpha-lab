# SMIAL Visual Operating System V1

Canonical presentation contract for Solana Memecoin Intraday Alpha Lab (SMIAL).
Machine tokens live in `configs/smial_visual_operating_system_v1.yaml`.
This document explains meaning. It does not own lifecycle, science, risk,
authority, or economics.

Catalog current binding: `ACTIVE-SMIAL-VISUAL-OPERATING-SYSTEM`
Semantic route: `SEM-VISUAL-OPERATING-SYSTEM`
Appearance: `DARK_ONLY`

## 1. Philosophy

SMIAL owner-facing surfaces are instruments, not marketing pages.

```text
DOMAIN TRUTH
    │ supplies state / evidence / authority meaning
    ▼
VISUAL OPERATING SYSTEM
    │ supplies presentation semantics
    ▼
Workbench / charts / reports / Telegram / future surfaces
```

The visual system answers how a state or result must look. Domain contracts
answer when that state is true. Color never grants authority, never upgrades
evidence class, and never fills missing data.

Truth wins over beauty, density, brand consistency, and decorative minimalism.

## 2. One system, four behaviors

These are not selectable themes. They are one identity whose expression
changes with the job: STEEL SIGNAL plus COMPUTATIONAL FIELD,
EVIDENCE EDITORIAL, and CONTROL SURFACE.

```text
                      STEEL SIGNAL
                            │
           ┌────────────────┼────────────────┐
           │                │                │
   COMPUTATIONAL       EVIDENCE         CONTROL
       FIELD           EDITORIAL        SURFACE
           │                │                │
 lifecycle / flow    science / truth    operation / risk
```

| Mode | Use for | Character |
| --- | --- | --- |
| `STEEL_SIGNAL` | shell, navigation, overview, ordinary tables, default cards, base charts | precise, cold, dense, quiet, professional |
| `COMPUTATIONAL_FIELD` | lifecycle, lineage, causal path, idea → experiment → evidence → strategy → execution | dynamic only when state actually changes |
| `EVIDENCE_EDITORIAL` | hypothesis, experiment, result, StrategyVersion provenance, scientific reports | live scientific dossier, not a magazine |
| `CONTROL_SURFACE` | positions, trading ops, risk, incidents, reconciliation, bounded commands | instrumental, calm, action-oriented |

A future Positions screen and a future experiment report must still look like
the same product.

## 3. Dark-only

SMIAL has one appearance: `DARK_ONLY`. Not “dark first”. No light-theme
parity. No theme switcher. Darkness is for long operator sessions, dense
data, semantic-color salience, and coherent screenshots/Telegram assets.

## 4. Color tokens and meaning

Exact V1 values are in the machine contract. Roles:

| Token | Meaning |
| --- | --- |
| `accent.signal` | selected, current, focus, informational emphasis |
| `accent.cobalt` | primary analytical series; data focus when cyan would be ambiguous |
| `semantic.positive` | positive result / healthy / pass / within limits — only when domain meaning supports it |
| `semantic.warning` | attention, degraded, stale/approaching limit, unresolved non-terminal concern |
| `semantic.danger` | failure, blocked, breach, destructive command, materially negative condition |
| `semantic.unknown` | UNKNOWN / unavailable / unresolved |

Invariants:

1. Color carries meaning, not decoration. Red, amber, and green are reserved.
2. Color never carries meaning alone. Pair with text, label, shape, icon, line
   style, or position. A grayscale screenshot must remain materially readable.
3. Brand accent is not success. Cyan/cobalt must not mean “good”.
4. Red is scarce. Do not paint every risk object red.
5. Evidence class is never color-only. `MODEL`, `BACKTEST`, `PAPER`, `SHADOW`,
   `LIVE` stay textually explicit.

`UNKNOWN` must never resemble zero, healthy, success, or empty decorative
space. `STALE` is not `HEALTHY`. `PROCESS_UP` is not `SYSTEM_HEALTHY`.
`PAPER` is not `LIVE`. `BACKTEST` is not `PAPER`.

## 5. Typography, spacing, hierarchy

Typography intent: neo-grotesk, compact, tabular-number friendly, no sci-fi
lettering. Preferred class `Inter` / `Manrope` for UI sans; `IBM Plex Mono` /
`ui-monospace` only for IDs, hashes, timestamps, code, exact machine values.
This contract does not adopt font binaries. Future implementations use the
available stack unless a separate consumer justifies adoption.

Spacing: 4px-derived scale `4 8 12 16 24 32`. Geometry: 1px hairlines; radius
2–6px normal, 8px exceptional. No giant bubbly cards. No pill for every
state. Whitespace is hierarchy, not luxury emptiness.

Hierarchy order: position → typography → spacing → rule/border → restrained
color → icon → motion. Do not compensate weak hierarchy with color.

## 6. Data visualization

Decision-relevant charts must make scientific scope inspectable when the
underlying truth contract provides it:

```text
as_of / observed_at
population
N
units
missingness
evidence_class
```

If a field is absent: `UNKNOWN` / `NOT_AVAILABLE`. Do not fabricate precision.

Chart rules: graphite canvas, restrained grid, one primary series, quieter
confidence bands, annotation over decoration. Forbidden: rainbow series,
default gradient-filled PnL areas, 3D, neon glow, chartjunk, green-because-
the-line-ended-positive. Positive/negative color is allowed only when the
visual statement explicitly represents a positive/negative outcome.

## 7. Evidence / freshness disclosure

Decision-relevant surfaces expose, proportionally: source/provenance, as_of
or observed_at, freshness, evidence_class, UNKNOWN.

Disclosure: scan → inspect → drill down. Never hide material uncertainty
behind visual cleanliness. Not every table cell must be verbose.

## 8. Research surface grammar (`EVIDENCE_EDITORIAL`)

A hypothesis/experiment/evidence object is a dossier on a falsifiable claim,
not a ticket. Visual hierarchy favors:

```text
QUESTION
MECHANISM
FALSIFIER
EVIDENCE SCOPE / N / COVERAGE / MISSINGNESS / EVIDENCE CLASS
RESULT / UNCERTAINTY / ROBUSTNESS
DECISION / BLOCKER / NEXT SAFE ACTION
```

Fields remain owned by domain contracts. This system only ranks them.

## 9. Operations surface grammar (`CONTROL_SURFACE`)

```text
WHAT EXISTS
WHAT STATE
WHAT CHANGED
WHAT RISK IS OPEN
HOW FRESH IS THE OBSERVATION
WHAT NEEDS ATTENTION
WHAT IS THE NEXT SAFE ACTION
```

Identifiers first; numbers align; blocker/attention distinguishable; commands
visually separated from observation. Do not invent a second lifecycle.
`STATUS RAIL` is the compact scan zone for state/freshness/attention. It is
not a decorative stripe on every card.

## 10. Command UX

A button does not grant authority. Presentation must preserve existing
authority boundaries:

```text
intent → target → expected current state → preconditions → authority
→ command → machine result → readback
```

Routine safe operations are not danger-red. Irreversible/high-risk commands
need explicit textual danger meaning and spatial separation. Disabled
commands explain why. Success requires readback, not click acknowledgement.

## 11. Telegram / service messages

Telegram belongs to the same information system. No separate bot aesthetic.

```text
[STATE / SEVERITY]
WHAT
WHY NOW
IMPACT
CURRENT SAFE STATE
NEXT SAFE ACTION
observed_at / evidence reference
```

First screen contains the decision-relevant fact. No decorative emoji soup,
no giant ASCII banners. Semantic emoji, if a consumer ever uses them, cannot
be the only state signal.

## 12. Attention grammar

Bind visually only to fields the source already exposes:

```text
WHAT
WHY_NOW
IMPACT
EVIDENCE
CURRENT_SAFE_STATE
NEXT_SAFE_ACTION
AUTHORITY_REQUIRED
```

Do not invent new domain fields here.

## 13. Proprietary primitives

Keep the language small. These are guidelines, not a component framework.

| Primitive | Role |
| --- | --- |
| `SIGNAL_RAIL` | short edge marker for current/status/attention scanning |
| `TRACE` | causal/lifecycle line for real lineages only |
| `EVIDENCE_HEADER` | compact editorial header: question + evidence class/scope |
| `CONTROL_ZONE` | spatial separation between observation and actions |

`TRACE` must not become ambient decoration. Motion explains state change, or
motion does not exist. No perpetual animation. Future implementations respect
reduced-motion. Typical transition intent `120–220ms`.

Forbidden motion: ambient pulsing, decorative glow, moving backgrounds, fake
live activity, endless network traces, animation for “premium feel”.

## 14. Accessibility

- Material text meets WCAG AA where applicable.
- Focus is distinguishable without color alone.
- Positive / warning / danger / unknown are distinguishable without color alone.
- Decision-critical facts are not tiny low-contrast text.
- Dense UI does not justify illegibility.
- Future motion supports reduced-motion preference.

## 15. Anti-patterns

Forbidden drift: generic crypto dashboard, cyberpunk, neon, RGB glow, purple
AI gradient, glassmorphism, holographic HUD, terminal cosplay, fake scanlines,
circuit-board decoration, hexagon overload, robot/brain/AI sparkle, giant
gradients, 3D chrome, fake stock ticker, Bloomberg imitation, sci-fi condensed
fonts, every status as a pill, every box as a rounded card, decorative
green/red, emoji-heavy operations, gratuitous animation, generic enterprise
dashboard with empty surfaces.

Also forbidden:

```text
beauty > truth
density > legibility
minimalism > evidence
brand consistency > domain semantics
```

## 16. Future-consumer rules

1. Resolve `SEM-VISUAL-OPERATING-SYSTEM` before inventing colors or chrome.
2. Read the machine contract; this document is the companion, not a second palette.
3. Select a surface mode from the job, not from taste.
4. Do not implement this contract by adopting a UI framework, theme engine,
   font package, or charting dependency unless a later exact task authorizes it.
5. Do not mutate Workbench merely to demonstrate the system.
6. Do not treat Catalog `IMPLEMENTED_UNVERIFIED` as product DONE.
7. Resolving this route grants no command, deploy, spend, merge, provider,
   wallet, signer, or transaction authority (`authority_granted = false`).

## 17. Reference image

If a `REFERENCE_ONLY` / `NON_CANONICAL` board is stored beside this contract,
it is inspiration. Tokens and invariants win on conflict. Absence of the image
does not weaken this contract.
