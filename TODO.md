# Sentsei TODO Queue
_Items for cron iterations to work through, in priority order._

## P0 — Critical Quality Issues
- [x] **Pronunciation: use deterministic libraries, not LLM** ✅ 2026-02-14
  - Japanese: pykakasi (Hepburn romaji)
  - Korean: korean-romanizer (Revised Romanization)
  - Chinese: pypinyin (with tone marks)
  - Hebrew: transliteration lib TBD
  - Greek: transliterate lib TBD
  - Post-processing overrides LLM pronunciation server-side
- [x] **Japanese gender/pronoun warnings** ✅ 2026-02-14
  - Detects 私/僕/俺/あたし/わたくし in translation, injects gender/formality note into grammar_notes
  - Backend post-processing step

## P1 — UX / Product Features
- [x] **Mobile-first layout** ✅ 2026-02-14
  - Sticky input area with backdrop blur on mobile
  - 2-column word chip grid (1-col on tiny phones)
  - Compact header, hidden "Press Enter" hint on mobile
  - Copy button on own line (not crowding translation)
  - Safe area insets for notched phones
  - Tested at 375px and 360px widths
- [x] **Better language selector UI (not dropdown)** ✅ 2026-02-14
  - Pill toggles with flag emojis instead of `<select>`
  - Horizontal scrollable row, works on mobile and desktop
  - Active pill highlighted with accent color
- [x] **Speaker toggles** ✅ 2026-02-14
  - Gender: ♀ / ♂ / Neutral toggle pills
  - Formality: Casual / Polite / Formal toggle pills
  - Persisted to localStorage
  - Passed to LLM prompt with language-specific guidance (ja pronouns, ko speech levels, he conjugation, es/it agreement)
- [x] **Clickable word chips** ✅ 2026-02-14
  - Click a word → inline expand panel with examples, conjugations, related words
  - /api/word-detail endpoint fetches from LLM on demand
  - Collapse by clicking again; only one expanded at a time
  - Expanded chip spans full width for readability
- [x] **Speaker/identity toggles (gender, age, formality)** ⭐ ✅ 2026-02-14
  - Combined with Speaker toggles above — same implementation
- [x] **Persistent sentence history (sidebar/drawer)** ✅ 2026-02-14
  - Rich history with translation preview, target language flag, timestamp
  - Desktop: 320px slide-out side panel from right
  - Mobile: 60vh bottom drawer with rounded top corners
  - Click entry to reload sentence + select target language
  - Badge shows count, clear all button, up to 50 entries
  - Survives refresh via localStorage
- [x] **"Surprise me" + Story Mode 📖** ✅ 2026-02-14
  - **Surprise me**: random curated sentence per target language + difficulty
  - **Story Mode**: continuous sentence-by-sentence playthrough drawn from famous modern literature, TV series, movies, anime
    - Curated sentence sets per language (Japanese → anime/drama, Korean → K-drama, Hebrew → modern novels, etc.)
    - "Next →" button to advance through the story/script
    - Show source attribution (title, episode, author)
    - Progress tracking per story
    - Could be a whole second tab/mode alongside free-type

## P2 — Design / Branding
- [ ] **New name** (Jimmy doesn't like "Sentsei")
  - Candidates for Jimmy to pick:
    - **Mouthful** — "learn a mouthful at a time"
    - **Ippun (一分)** — "one sentence" in Japanese
    - **Hanmadi (한마디)** — "one word/phrase" in Korean
    - **SayIt** — dead simple, action-oriented
    - **Kuchinaoshi (口直し)** — "palate cleanser" / fresh start with words
    - **Phrasecraft** — building craft with phrases
  - Waiting for Jimmy's pick before renaming
- [x] **New color palette + typography** ✅ 2026-02-14
  - Warm amber/gold accent (#e8a838) replacing purple
  - Neutral dark backgrounds (#0c0c0c / #161616 / #1e1e1e)
  - Warm text tones (#f0ece4 / #908a7e)
  - DM Sans font replacing Inter — rounder, warmer feel
  - Larger border-radius (14px)
  - Better contrast ratios on dark backgrounds

## P3 — Infrastructure & Polish (from reflection)
- [x] **Audio pronunciation (TTS)** ✅ 2026-02-14 — browser SpeechSynthesis with BCP-47 language mapping, 0.85 rate for learners, visual feedback
- [x] **Loading UX** ✅ 2026-02-14 — elapsed timer, progressive messages ("Translating..." → "Analyzing grammar..." → "Almost there..."), 45s timeout with retry button, cancel after 8s
- [x] **Multi-sentence input** ✅ 2026-02-14 — split paragraphs into individual sentences, /api/learn-multi endpoint, frontend auto-detects and renders stacked cards
- [x] **Reverse mode / Quiz** ✅ 2026-02-14 — see target language, guess the English/Chinese. 🧠 Quiz toggle, LLM-graded semantic matching, score tracking
- [x] **Save/export** ✅ 2026-02-14 — Anki TSV export (📥 button in history panel, /api/export-anki endpoint), Copy All to clipboard (📋), styled with amber toggle pills
- [x] **Caching** ✅ 2026-02-14 — in-memory LRU cache (500 entries, 24h TTL), keyed by sentence+target+gender+formality
- [x] **Rate limiting** ✅ 2026-02-14 — IP-based sliding window (30 req/min per IP), cleanup every 100 checks, 429 response when exceeded
- [x] **Onboarding** ✅ 2026-02-14 — first-visit overlay with 3 suggested sentences (ja/ko/zh), click to auto-fill + learn, skip option, localStorage flag
- [x] **Comparison mode** ✅ 2026-02-14 — one sentence → all languages side by side
- [x] **Progress tracking** — sentences learned, languages used, streaks ✅ (2026-02-14)

## P3.5 — Performance Features
- [x] **Pre-computed Surprise Me** ✅ 2026-02-16 — Background task pre-generates translations for surprise sentences across all languages on startup. Serves instantly from in-memory bank. Auto-refills when bank gets low. Falls back to live LLM if empty. `/api/surprise-bank-status` for monitoring.
- [x] **Speculative Typing (Learn as you type)** ✅ 2026-02-16 — After 1.5s typing pause, fires LLM request in background. If result is ready when Learn is pressed, renders instantly. Cancels pending request on further typing. Shows subtle "Preparing translation..." pulse indicator. IME-aware (pauses during 注音 composition).

## P4 — Future Polish
- [x] **Watchdog cron conflicts with test suite** ✅ 2026-02-15 — lock file `/tmp/sentsei-test.lock` created by test suite, watchdog skips restart when lock is < 5 min old; PID file for cleaner process management
- [x] **Grammar notes sometimes empty after English source filter** ✅ 2026-02-15 — salvages English content from CJK-heavy notes instead of dropping; adds fallback note when all notes are stripped
- [x] **Rule 18 test flaky** ✅ 2026-02-15 — added retry on timeout

## P3.6 — Code Health & Reliability (from 2026-02-16 reflection)
- [x] **Split monolith index.html (4333 lines)** ✅ 2026-02-16 — extracted JS into `app.js`, CSS into `style.css`. Easier to maintain, debug, and cache separately.
- [x] **Move hardcoded secrets to env vars** ✅ 2026-02-16 — (done with health endpoint commit)
- [x] **Fix empty surprise bank on startup** ✅ 2026-02-16 — Re-enabled background fill with Ollama connectivity check. Fills only when bank is low/empty, yields to user requests. Persists to disk (surprise_bank.json) after fill/refill.
- [x] **Add /api/health endpoint** ✅ 2026-02-16 — Returns Ollama reachability, cache stats (entries/max/TTL), surprise bank status (total/languages/filling).
- [x] **Move hardcoded secrets to env vars** ✅ 2026-02-16 — `APP_PASSWORD` now reads from `SENTSEI_PASSWORD` env var with fallback to default.
- [x] **Persistent translation cache** ✅ 2026-02-16 — JSON file persistence with periodic save (60s interval), loads on startup, respects TTL on load.
- [x] **Admin view for feedback** ✅ 2026-02-16 — `/api/feedback-list` (GET, paginated, newest-first) and `/api/feedback/{index}` (DELETE), both password-protected. Simple admin page at `/admin.html` with dark theme matching main app.

## P4.1 — Next Wave (from 2026-02-16 reflection)
- [x] **Error handling UX** ✅ 2026-02-16 — friendlyError() helper extracts specific messages from API responses (429 rate limit, 502 Ollama down, 400 validation). No more generic "Something went wrong".
- [x] **Accessibility audit** ✅ 2026-02-16 — skip-to-content link, ARIA roles on all panels (dialog), radiogroup+radio on toggle/language pills with aria-checked, word chips get role=button+tabindex+aria-expanded+keyboard handler (Enter/Space), difficulty dots get aria-label, Escape closes panels, focus trap in side menu, sr-only CSS class.
- [x] **Backend test coverage for new endpoints** ✅ 2026-02-16 — feedback-list, feedback delete, health, surprise-bank-status tested (auth checks, response shape, out-of-range handling).
- [x] **Surprise bank stays empty** ✅ 2026-02-16 — Not a bug; fill is working but slow due to sequential Ollama calls (~30-60s each × 72 combos). Health now shows entries accumulating (e.g. he_en: 4). Persistence to disk means it recovers across restarts.

## P5 — Next Wave (from 2026-02-16 reflection #2)
- [x] **Fix 5 pre-existing test failures** ✅ 2026-02-16
- [x] **Offline/PWA support** ✅ 2026-02-16 — service worker caches static assets (cache-first) + API responses (network-first with offline fallback). Web app manifest, 192/512px icons, installable as PWA. Works on subway/plane.
- [x] **Dark/light theme toggle** ✅ 2026-02-16 — Light theme CSS variables, toggle in header + side menu, localStorage persistence, warm cream/amber palette.
- [x] **Keyboard shortcuts** ✅ 2026-02-16 — Ctrl+Enter to learn, Ctrl+H for history, Ctrl+K to focus input, Ctrl+Shift+S for surprise, ? for shortcut help overlay. Escape closes panels. All with accessible kbd styling.
- [x] **Shareable links** ✅ 2026-02-16 — `/learn?s=hello&t=ja` deep links. Share button on results (Web Share API + clipboard fallback). URL updates after each learn via history.replaceState. Auto-learns shared sentence on load.
- [x] **Spaced repetition reminders** ✅ 2026-02-16 — SM-2 algorithm with localStorage SRS deck. Auto-adds learned sentences. Review mode with multiple-choice cards, interval tracking (1d→3d→N*EF), ease factor adjustments. Badge shows due count. Stats modal shows deck size, due items, mastered (30d+). Integrates with existing quiz UI patterns.

## P6 — Next Wave (from 2026-02-16 reflection #3)
- [x] **Contextual example sentences** ✅ 2026-02-16 — "See it in context" toggle on each result card, lazy-loads 3 example sentences via `/api/context-examples` endpoint. Shows same grammar/vocab in different everyday situations (restaurant, texting, etc). Cached, deterministic pronunciation for CJK.
- [x] **Grammar pattern library** ✅ 2026-02-16 — Collect recurring grammar patterns from translations, let users browse by pattern (e.g. "〜てもいい", "〜(으)면"). Backend extraction from grammar_notes, persistent storage, browse/detail endpoints. Frontend panel with language filter, frequency sorting, expandable examples.
- [x] **Multi-user support** ✅ 2026-02-16 — SQLite backend with users/sessions/user_data tables. Register/login/logout endpoints, Bearer token auth (30-day TTL), server-side sync for history/SRS/progress/preferences. Optional — app still works without login. Frontend auth modal + auto-sync on data changes.
- [x] **Difficulty auto-detection** ✅ 2026-02-16 — Heuristic analysis (word count, sentence length, CJK diversity, complexity markers, breakdown word difficulty). Returns beginner/intermediate/advanced with 0-100 score + factors. Color-coded badge on result cards with tooltip.
- [x] **Romanization toggle** ✅ 2026-02-16 — "Aa" toggle pill hides/shows all pronunciation (romaji, pinyin, romanized Korean) across result cards, word chips, quiz, compare, and context examples. Persisted to localStorage. Default ON.
- [ ] **Backend test coverage for SRS/review** — Currently no backend tests needed (SRS is frontend-only), but if SRS moves server-side for multi-user, add comprehensive tests.

## P7 — Code Health & Security (from 2026-02-17 reflection)
- [x] **Use bcrypt for password hashing** ✅ 2026-02-17 — Switched from SHA-256+salt to bcrypt (cost 12). Legacy hashes verified via fallback and auto-rehashed to bcrypt on next login.
- [x] **Split backend.py into modules** — 2340 lines in one file. Split into: `auth.py` (user/session management), `llm.py` (Ollama interaction/prompt building), `cache.py` (LRU + persistence), `routes.py` (API endpoints), `models.py` (Pydantic schemas). Keep `backend.py` as the app entry point that wires everything together.
- [x] **Make test suite pytest-compatible** ✅ 2026-02-17 — Refactored into proper `test_*` functions with pytest fixtures in `conftest.py`. Session-scoped fixtures for base_url, headers, api_learn, lockfile.
- [x] **Difficulty field missing from /api/learn response** ✅ 2026-02-17 — Wired `result["difficulty"]` from `sentence_difficulty.level` in routes.py.
- [x] **CORS headers** ✅ 2026-02-17 — CORSMiddleware activated when `SENTSEI_CORS_ORIGINS` env var is set (comma-separated). Allows credentials, GET/POST/DELETE/OPTIONS, Authorization+Content-Type headers. No CORS when unset (same-origin only).
- [x] **Session cleanup cron** ✅ 2026-02-17 — `cleanup_expired_sessions()` in auth.py, runs on startup + hourly via asyncio task. Deletes sessions past `expires_at`.
- [x] **Structured logging** ✅ 2026-02-17 — `log.py` module with JSON-lines formatter (configurable level/format via env vars). HTTP request middleware logs all API calls with timing. All print() replaced with structured logger, bare excepts use logger.exception() for tracebacks.
- [x] **Input validation hardening** ✅ 2026-02-17 — Added MAX_INPUT_LEN (500) checks to all endpoints: segment, breakdown, learn-stream, learn-multi (2500 for paragraphs), word-detail, context-examples, compare.

## P8 — Next Wave (from 2026-02-17 reflection)
- [x] **Split app.js into modules** — 3109 lines, single file. Split into: `ui.js` (DOM helpers, rendering), `api.js` (fetch wrappers), `srs.js` (spaced repetition logic), `quiz.js` (quiz mode), `history.js` (history panel), `shortcuts.js` (keyboard shortcuts). Use ES modules with `<script type="module">`. ✅ 2026-02-17
- [ ] **Split routes.py further** — 1563 lines. Extract surprise bank logic into `surprise.py`, feedback into `feedback.py`, quiz endpoints into `quiz_routes.py`. Keep `routes.py` as the main router that includes sub-routers.
- [x] **Pronunciation quality** ✅ 2026-02-17 — Replaced raw pykakasi with MeCab (unidic) tokenization + pykakasi romaji conversion. Fixes: particles は→wa/を→o/へ→e via POS tagging, long vowel macrons (ā/ī/ū/ē/ō), reading overrides (私→watashi), punctuation stripping. "raamen wo tabeta idesu" → "rāmen o tabe tai desu".
- [x] **Frontend error recovery** ✅ 2026-02-17 — auto-retries up to 3× on 502 with "Translation engine warming up..." message and 4s delay. Falls back to error message after max retries.
- [x] **Surprise bank persistence bug** ✅ 2026-02-17 — saves every 10 entries during fill, not just on completion.
- [x] **API response time tracking** ✅ 2026-02-17 — rolling latency tracker (last 500 per endpoint) with p50/p95/p99/count stats exposed in `/api/health` response.
- [x] **Missing `difficulty` field in response** ✅ 2026-02-17 — backfills difficulty on cached results missing it (learn + learn-fast), added to compare endpoint response.

## Cron Test Matrix
Each iteration should run these checks:
1. English → Korean: explanations in English? Translation in 한글?
2. English → Japanese (with pronoun): gender note present?
3. English → Chinese: translation uses 台灣用法? No simplified?
4. Chinese → Korean: explanations in 繁體中文?
5. Check pronunciation against deterministic lib (once installed)
6. Check for any 簡體字 in output
