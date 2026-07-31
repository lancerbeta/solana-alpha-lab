# TASK-21 durable resume router binding contract v1

`T21-P7_DURABLE_RESUME_ROUTER_BINDING_V1` makes TASK-21 continuation
discoverable from a new local thread without relying on chat history or on the
owner remembering a command.

## Single discovery chain

The repository already requires every new task or parallel atom to read
`AGENTS.md` and `control/active_time_gates.json`. The marker therefore owns one
additional machine-readable `resume_router` object. It directs a new thread to
run the existing Owner Pulse in read-only mode and then obey the current gate:

```text
AGENTS.md
  -> control/active_time_gates.json:resume_router
  -> scripts/show_task21_owner_pulse.py --json
  -> due gate's exact required_next_atom, or explicitly authorized
     non-interfering work while waiting
```

No second status file, chat-only checklist or scheduler is introduced. The
marker remains the mutable gate owner; Owner Pulse remains a derived read
model. If the command cannot run, the router provides a bounded relative-path
fallback read set rather than guessing current state.

## Precedence and authority

A due unresolved gate preempts new mutation and routes its exact
`required_next_atom`. Before the H24 minimum age, only separately authorized
non-interfering work may continue. The router, marker and pulse grant zero
provider/API/RPC/WSS, Drive, collection, admission, spend, credential,
wallet/signer/transaction, merge or destructive authority.

P7 does not change H24 timing, membership, caps or recovery prerequisites. It
does not create H72/H168 gates, start background work, write raw data or
advance Catalog.

## Durability boundary

The binding is immediately visible to any new thread attached to this exact
local checkout. Because P7 is `LOCAL_WRITE_ONLY`, a fresh clone cannot be
claimed to contain it until a later authorized commit and repository delivery.
That transport limitation is explicit in both config and marker.

## Acceptance

Acceptance requires:

- one active router object bound to the exact config and Owner Pulse script;
- only repository-relative paths and one deterministic read-only command;
- due-gate precedence and zero authority encoded in the marker;
- the existing H24/H72/H168 semantics unchanged;
- historical post-H6 receipt retained byte-for-byte as audit evidence while
  its mutable marker/test paths are recognized as forward-evolved;
- targeted and TASK-21 regression tests passing with zero external actions.
