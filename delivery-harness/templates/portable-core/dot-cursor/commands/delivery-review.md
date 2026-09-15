# Delivery review

Review the exact diff against the exact task contract. Launch isolated critics.
Run code review always. Other roles are frozen by the task contract
`required_review_roles` according to canonical triggers and strengthened by
deterministic floors (architecture on control/schema/authority surfaces);
contracts without the field and LIVE_PR_HEAD use the legacy triple
CODE_REVIEWER+GOAL_DOD_CRITIC+ARCHITECTURE_CRITIC. Machine gates require the
exact resolved role-set. `SINGLE_AGENT_REVIEW_FALLBACK` is not merge PASS.
