# Population discovery Stage A — owner readout

Терминал: `INSTANT_RECENT_CANNOT_FILL_EARLY`.

Это не alpha, не quotes, не 3 X и не live Jupiter.

## Простыми словами

Замороженные окна 5–15 минут и 30–120 минут остаются. Но **прямо сейчас с `/recent` их не набрать**: эти токены живут секунды, не минуты. Если сразу сделать 3 вызова из мемо и потом 24 котировки — получится пустой EARLY и зря сожжённый live-бюджет.

Как набирать EARLY — уже известно из early-path: подождать ≥5 минут, потом один bulk search. SEASONED — через `/toptraded` + search, не «весь TRADED». Liquidity на Git-receipt early-path нет, поэтому 12+12 product cells офлайн не закрываются.

Quotes и три state-X **вынесены**. Live 3-call+wait ждёт отдельную owner-фразу.

Provider calls: 0. Factory runner не менялся.
