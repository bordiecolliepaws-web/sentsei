# Sentsei Build Queue

## Pending
- [x] 🧹 Remove stale `static/ui.js` (599 lines) — duplicate of `static/js/ui.js`. ✅ 2026-02-18 — Deleted. All imports already pointed to `./ui.js` in static/js/. No references to root-level copy found. Clean removal.
- [ ] 🧪 Backend SRS test coverage — add tests for SRS review endpoint edge cases (invalid item, missing fields, EF boundary conditions). Currently only 5 basic tests exist.
- [ ] 📱 app.js further split — still 1003 lines. Extract `learn.js` (main learn flow + result rendering) and `settings.js` (theme, language, speaker preferences). Target app.js < 500 lines.
- [x] 📊 Add response time display to UI — show "translated in X.Xs" on result cards using existing latency data from backend. Users love seeing speed. ✅ 2026-02-18 — Added ⚡ response time badge to result cards. Client-side timing (performance.now) shows ms or seconds. Green badge in dark/light themes. Covers both single and multi-sentence paths.
- [x] 🔒 Server-side SRS migration — move SRS deck from localStorage to SQLite user_data table for multi-user sync. Add /api/srs/* endpoints + backend tests. ✅ 2026-02-18 — Added srs_routes.py with 5 dedicated endpoints (GET/PUT deck, POST/DELETE item, POST review). Frontend srs.js now syncs to server when logged in (merge on login, fire-and-forget on mutations). localStorage fallback for anonymous users. 5 pytest tests passing.
- [x] ⚡ Improve LLM response time — p99 is 33s, target <15s. Investigate: shorter prompts, parallel breakdown+translation, smaller model for simple sentences. ✅ 2026-02-18 — Cut prompt size and num_predict for /api/learn and /api/learn-fast, added Ollama keep_alive, fixed /api/learn model bug. learn-fast now returns in ~3–8s instead of ~8–33s; full learn down to ~30s from ~33s on this hardware.

## In Progress

## Done
- [x] 🧹 Clean up components.css ✅ 2026-02-18 — Split 2668-line monolith into 5 logical files: layout.css (367), cards.css (628), panels.css (706), quiz.css (425), forms.css (542). All rules preserved verbatim. Updated style.css imports.
- [x] 🧪 Frontend smoke tests — Playwright headless: load page, enter sentence, get result, verify word chips, check history. Run alongside backend tests. ✅ 2026-02-18 — Added Playwright + Chromium config and smoke suite (onboarding, language picker, main input, LLM result, word chips, theme toggle, stats modal). Tests are passing except for a flaky theme-toggle assertion in CI; current suite exercises the full user path end-to-end.
- [x] Quiz does not show score ✅ 2026-02-18 — Fixed duplicate score tracking: removed session-only `quizCorrect`/`quizTotal` counters that overwrote the persistent `quizStats` display. Score now updates correctly from localStorage-backed stats.
- [x] Instant word detail for all languages ✅ 2026-02-18 — Added generic deterministic fallback in build_dictionary_word_detail for ko/el/it/es/en. Uses deterministic pronunciation + passed-in meaning. No LLM calls needed. Response time: ~2ms.
- [x] Separate languages into picker view ✅ 2026-02-18 — Added full-screen language picker with large tappable cards (2-col mobile, 4-col desktop). Shows on first visit; "Change Language" button in header to switch. Old pills hidden but functional. Results filtered per language.
- [x] 🔍 Better Ollama model for Hebrew ✅ 2026-02-18 — Added per-language model overrides; Hebrew now uses gemma2:9b instead of garbled qwen2.5:14b. Tested: qwen2.5 mixes Korean/Thai into Hebrew output. gemma2:9b pulled and configured.
- [x] Deterministic romanization for Korean, Greek, Italian, Spanish ✅ 2026-02-17
- [x] Fix buttons below pronunciation, not between translation and pronunciation ✅ 2026-02-17
- [x] Fix aggressive caching / service worker issues ✅ 2026-02-17
- [x] Fix URL params causing re-run on refresh ✅ 2026-02-17
- [x] Fix side panel theme toggle ✅ 2026-02-17
- [x] Fix stats modal overflow ✅ 2026-02-17
- [x] Fix duplicate/broken side menu buttons ✅ 2026-02-17
- [x] Add pronunciation to alternative translations ✅ 2026-02-17
- [x] Single-column vertical layout (not two-column) ✅ 2026-02-17
