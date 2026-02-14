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

## P4 — Future Polish
- [ ] **Watchdog cron conflicts with test suite** — watchdog `pkill -f "uvicorn backend"` kills server during test runs; needs PID-file approach or lock file
- [ ] **Grammar notes sometimes empty after English source filter** — LLM returns Chinese-only notes, post-processing drops them, leaving no notes; consider retry/reprompt in English
- [ ] **Rule 18 test flaky** — Japanese ramen translation sometimes times out, causing Rule 18 tests to be silently skipped; add retry logic to test suite

## Cron Test Matrix
Each iteration should run these checks:
1. English → Korean: explanations in English? Translation in 한글?
2. English → Japanese (with pronoun): gender note present?
3. English → Chinese: translation uses 台灣用法? No simplified?
4. Chinese → Korean: explanations in 繁體中文?
5. Check pronunciation against deterministic lib (once installed)
6. Check for any 簡體字 in output
