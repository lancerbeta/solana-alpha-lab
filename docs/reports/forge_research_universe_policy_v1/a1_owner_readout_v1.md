# Forge research-universe policy

New Forge runs require an active research-universe profile in ResearchStore. The owner changes minimum holders and minimum liquidity with preview, apply, and status. The first intended profile is 50 holders and 5000 USD liquidity, both at decision time. Changing 5000 to 20000 is the same three commands.

A missing profile stops before an operation is recorded. An open operation must be finished before apply. A published corpus whose logical content hash or caller binding hash does not match writes nothing. A frozen recipe replays its own snapshot. Returning to the same profile and the same rows does not spend a new main look.

This atom does not activate the live profile and does not take a main look.
