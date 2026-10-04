# Campaign cutover completion repair

Frozen-base RED reproduced premature COMPLETE through both lifecycle completion
and real CLI/tick after canonical register/authorize/activate/rollover.

The repair guards the caller before future cutover and independently requires a
matching committed effective DRAINING transition. Valid early rollover remains
supported. Empty queues and raw state do not establish closure. Missing/malformed
proof is DRAINING_PROOF_UNKNOWN without mutation; tick propagates this terminal.
Due/publication/restore obligations hold completion; COMPLETE replay stays terminal.

76 focused lifecycle/scheduler/renewal/commissioning tests passed, including eleven
new zero-network loop tests. Reproduce:

```text
uv run --locked --managed-python python -B -m unittest tests.test_factory_campaign_cutover_completion_repair_v1 tests.test_observation_schedule_lifecycle tests.test_observation_scheduler tests.test_same_envelope_renewal tests.test_observation_schedule_commissioning -q
```

Reviewer falsifiers are now regressions: coherent SQLite sequence/authority drift
cannot match the immutable event ID. Completion proof lookup opens only its named committed
transaction; 10 versus 200 unrelated member headers still open exactly one state
payload. Future or pending drain returns before the immutable lookup.

Normalized frozen-base RED summary SHA256:
`e6d79ba6db16b7968af4322ae6907df7da48e6ba8cb58fba644887338efcf0ad`.
Reproduce the first two loop tests using the candidate test and the exact base
`fc3db6cf164d73b1289bda8472c21f3d4e3edea7` lifecycle/scheduler module blobs:
assertions are `COMPLETED != DRAINING_PENDING` and `COMPLETE != DRAINING`.
The corresponding source blob SHA256 values are `44aeca186b729e5d9f2c42f39c604afb6c5c510b21c79d87299e818d5d7b5770`
and `b2f589a12a132c56c57623f1920d4574e6ab2b8e4f1694a254c5e7c2dd2c8c5d`.
This fingerprint covers the normalized two-test/base/source/assertion summary;
it does not claim a hash of an unsaved raw unittest traceback.

No schema, provider route, sampling, budget, retry, timer or dependency change.
No reopening of historical COMPLETE or filling of the capture gap. Existing runbook
and Catalog relations document the same invariant.

Git acceptance requires exact-head CI and isolated reviews. Live acceptance requires
canonical exact-SHA deploy, isolated Linux loop, two ordinary collector cycles, new
scientific publication and fresh watch/resource readback. Operational receipts stay
outside Git. Synthetic proof does not establish a future natural production rollover.
Existing backup-chain content SHA UNKNOWN remains explicit.

Publication lag is a separate measured follow-up; this repair does not claim to
solve it. Natural rollover is checked at its actual boundary. Rollback uses exact
prior live code SHA and canonical code-rollback, preserving immutable events/data.
