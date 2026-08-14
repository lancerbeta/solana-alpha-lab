---
name: delivery-harness
description: Use for bounded Git-native repository delivery from exact task context through guarded merge read-back.
---

# Delivery Harness

Run `CHECK -> CONTEXT -> EXECUTE -> REVIEW -> FINISH -> MERGE GATE -> READ-BACK`.
Require one exact task contract and explicit missingness. Keep routine work
autonomous; stop only for material authority or the exact PR/head merge gate.
Use targeted checks during work and one full gate per unchanged fingerprint.
Git is project memory; cloud export is optional and owner-managed.
After the exact PR/head owner phrase, use the repository-owned grounded merge
entrypoint; never replace its live checks with caller-supplied booleans.
