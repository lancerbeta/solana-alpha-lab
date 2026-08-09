# Stop at external authority

## Purpose

Keep a read-only repository/context workflow from silently crossing into an
external or cash-bearing action.

Run the context card first when relevant:

```powershell
uv run --locked --managed-python python -B scripts/show_task34a_context.py --format text
```

## Mandatory stop

Do not make a provider call. Stop before any of the following unless an exact,
current owner authorization explicitly covers the named action and its limits:

- provider/API/RPC/WSS request or credential use;
- wallet creation/connection, signer use, transaction build/simulate/send, or
  on-chain reconciliation;
- cash spend, funding, fee, purchase, deployment, release, or account/permission
  change;
- cloud Project Sources UI replacement, upload, deletion, or activation.

The next request must name the proposed action, consumer, bounded inputs,
maximum cost/number of calls, desired retention, stop condition, and what result
would change the decision. A quote, simulation, documentation page, or local
test double is not an execution or authority substitute.
