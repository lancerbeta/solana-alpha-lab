# TASK-30 H07/H01 exact data contract entry gate contract v1

`task30_h07_h01_exact_data_contract_entry_gate_v1.yaml` is a closed offline
policy for the frozen H07/H01 requirements.  Every requirement is mapped once
to one lane and each capture-capable lane names its minimum fields,
point-in-time timestamps and typed failure semantics.

The pure evaluator rejects a changed frozen binding, a price-only promotion,
a quote-to-settlement promotion, missing-to-zero coercion, an irrecoverable
future capture without backup/waiver, a silent capture-framework copy and any
non-zero authority or side-effect counter.

The current valid result is `PREPARE_PARTIAL_PIT_CAPTURE_CONTRACT`.  It means
only that a later exact owner gate may decide whether to collect named PIT or
route-feasibility inputs.  It retains `settled_execution_truth: UNSUPPORTED`,
`trial_admissible: false` and all current external authority as not granted.
