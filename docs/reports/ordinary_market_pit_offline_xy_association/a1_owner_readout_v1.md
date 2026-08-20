# Ordinary market PIT — offline XY association

Это всё ещё Muv-2 Move 1, не Muv-3 и не PIT_READY.

**Product terminal:** EXPLORATORY_ASSOCIATION_NOT_PIT

**Family decision:** DEFER_FRESH_PIT_CAPTURE

Bound X из PR #164 соединён с уже снятым forward Y qualification.
complete_xy=10, не n=12. RECENT_1 и RECENT_4 — Y MISSING, не 0.
RECENT n=4 < min_stratum_n=6 → INCONCLUSIVE_STRATUM.
TRADED n=6: exploratory Kendall 5 concordant / 10 discordant (negative hint).
Это не CLOSE family и не EARN_REPLICATION: выборка не outcome-blind для этого X.

Следующий шаг — bounded fresh PIT capture, не shadow execution.
