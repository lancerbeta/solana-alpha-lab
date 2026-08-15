# Roadmap challenge

Load on: finished-atom boundary, new-atom select, `поднимем голову`,
repeated blocker, or evidence that destroys the next-step premise.

```text
Roadmap = best currently accepted route, not immutable future truth.
```

Return exactly one verdict. Default cheap: `KEEP` or `PATCH`. A material
change must land in authoritative Git artifacts before more delivery.
Silent divergence is forbidden.

## KEEP

Evidence still supports the premise, priority, and dependency chain. Continue
the current sequence. No roadmap mutation.

## PATCH

Goal and order are still right; assumptions, scope, dependency, DoD, or the
exact contract need a bounded fix. Patch those artifacts in the same atom
that relies on them, or as the atom's first write.

## REORDER

Planned atoms remain useful, but the current order no longer maximizes
information gain, product leverage, or risk reduction. Change sequence
explicitly; do not skip ahead while leaving the old order as if canonical.

## REBASE

Material new evidence changed the product model, estimand, architecture, or
fundamental route. Stop implementation of the obsolete sequence. The rebase
itself is the atom (or `OWNER_DECISION` when the estimand/goal is owner-only).

## When a challenge is warranted

- Previous outcome invalidated the next-task premise
- Same material blocker repeated after a reasonable repair
- A materially cheaper/better route is now evidenced
- External reality changed (data, provider, constraint)
- Capability has no named consumer
- Next planned task has weak information value
- Sequence optimizes local implementation rather than product outcome
- Strategy or product objective materially changed

## Anti-overthinking — do not REBASE because

- A prettier architecture appeared
- A more generic framework could be invented
- One routine defect occurred
- The model wants to "start correctly from zero"
- The existing path is already evidence-backed and the new path adds no
  material gain

Do not run this challenge on every small commit. `STRATEGY` theater is not
progress.

## Propagation

```text
evidence
→ verdict
→ exact contract/roadmap delta
→ dependencies / state / Catalog if affected
→ validation
```

Keep the delta transactional and named. If Catalog, registries, or generated
views are consumers of the changed sequence, update them in the same managed
write set. If the verdict is `KEEP`, record it in the atom brief and move on.
