# Factory semantic map

Generated from validated Catalog + `configs/factory_semantic_operability_v1.yaml`. Do not edit manually.
Reference-only navigation. `authority_granted = false` for every route. Runtime values require machine readback.

Projection: `FACTORY_SEMANTIC_OPERABILITY_V1` (`configs/factory_semantic_operability_v1.yaml`).
Validation: `PASS`.

| Owner/agent need | Semantic route | Current root | Truth plane | Inspection surface | Authority |
| ---------------- | -------------- | ------------ | ----------- | ------------------ | --------- |
| Am I authorized to call, deploy or spend? | SEM-AUTHORITY-BOUNDARIES | POLICY-OWNER-ATTENTION-GATE-002; CONFIG-DELIVERY-PROJECT-PROFILE-001 | AUTHORITY | resolve-route / Catalog dereference | false |
| Can I run this through an existing experiment capability? | SEM-EXPERIMENT-CAPABILITIES | ACTIVE-EXPERIMENT-CAPABILITY-REGISTRY→CONFIG-EXPERIMENT-CAPABILITY-REGISTRY-V2-001 | CAPABILITY | resolve-route / Catalog dereference | false |
| How do I generate or review a hypothesis? | SEM-HYPOTHESIS-FORGE | ACTIVE-HYPOTHESIS-FORGE→CONFIG-HYPOTHESIS-FORGE-INDEPENDENT-CRITIC-001; DOC-HYPOTHESIS-FORGE-OPERATOR-001; SKILL-HYPOTHESIS-FORGE-001 | CAPABILITY | resolve-route / Catalog dereference | false |
| Is lifecycle collection running / where do I inspect it? | SEM-LIVE-COLLECTION | ACTIVE-LIFECYCLE-COLLECTOR→DOC-FACTORY-LIFECYCLE-COLLECTOR-001; CONFIG-OBSERVATION-SCHEDULE-RUNTIME-V1-001 | MIXED | EXTERNAL_GATED_READBACK via DOC-FACTORY-LIFECYCLE-COLLECTOR-001 | false |
| How does live RDP get into Forge? | SEM-LIVE-EVIDENCE-TO-FORGE | ACTIVE-LIVE-LIFECYCLE-EVIDENCE→MODULE-LIVE-COHORT-DISCOVERY-RELEASE-001 | MIXED | resolve-route / Catalog dereference | false |
| What feature or data exists at decision time? | SEM-MARKET-DATA-FEATURES | ACTIVE-FACTORY-MARKET-FEATURE-SURFACE→CONFIG-FACTORY-V1-COMMON-MARKET-FEATURE-SURFACE-001 | MIXED | resolve-route / Catalog dereference | false |
| Has this mechanism been tested? | SEM-PRIOR-WORK | MODULE-FACTORY-V1-RESEARCH-STORE-001; REGISTRY-DECISIONS-NEGATIVE-RESULTS-001 | SCIENTIFIC | resolve-route / Catalog dereference; recipes QUERY-HFIC-EXACT-RELATED-PRIOR-001, QUERY-HYPOTHESIS-FAST-LANE-SEARCH-PRIOR-WORK-001, QUERY-HFIC-SESSION-BY-SEARCH-KEY-001, QUERY-HFIC-PENDING-SESSION-001 | false |
| What is this product / Factory v1? | SEM-PRODUCT-STATE | ACTIVE-FACTORY-OPERATIONAL-READINESS→CONFIG-FACTORY-V1-OPERATIONAL-READINESS-001 | CAPABILITY | resolve-route / Catalog dereference | false |
| What provider route supports this field? | SEM-PROVIDER-ROUTES | ACTIVE-PROVIDER-ROUTE-CAPABILITY-REGISTRY→CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010 | MIXED | resolve-route / Catalog dereference | false |
| Where is the Factory VPS? | SEM-REMOTE-OPS-RECOVERY | ACTIVE-FACTORY-REMOTE-OPERATIONS→CONFIG-FACTORY-REMOTE-OPERATIONS-001; DOC-FACTORY-REMOTE-HOST-001 | RUNTIME | EXTERNAL_GATED_READBACK via DOC-FACTORY-REMOTE-HOST-001 | false |
| How should I design an SMIAL owner-facing surface? | SEM-VISUAL-OPERATING-SYSTEM | ACTIVE-SMIAL-VISUAL-OPERATING-SYSTEM→CONFIG-SMIAL-VISUAL-OPERATING-SYSTEM-001; DOC-SMIAL-VISUAL-OPERATING-SYSTEM-001 | CAPABILITY | resolve-route / Catalog dereference | false |

Planes: `CAPABILITY` = what Git currently knows how to do; `RUNTIME` = machine readback;
`SCIENTIFIC` = evidence/results; `AUTHORITY` = gate/task resolver only; `MIXED` = explicit multi-plane.

Not a roadmap. Not task selection. Not runtime status. Not authority.
