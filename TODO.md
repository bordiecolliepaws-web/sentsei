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
  - Generate candidates, evaluate
- [ ] **New color palette + typography**
  - Current purple/dark theme: needs refresh
  - Consider warmer tones, better contrast
  - Test on mobile

## P3 — Infrastructure & Polish (from reflection)
- [ ] **Audio pronunciation (TTS)** — browser SpeechSynthesis or server-side TTS
- [ ] **Loading UX** — better feedback for slow model responses (10-20s), timeout/retry
- [ ] **Multi-sentence input** — split paragraphs into individual sentences
- [ ] **Reverse mode / Quiz** — see target language, type the English/Chinese
- [ ] **Save/export** — Anki flashcard export, PDF, screenshot-friendly format
- [ ] **Caching** — same sentence + same target = cached result, no repeat API call
- [ ] **Rate limiting** — prevent API hammering once past password
- [ ] **Onboarding** — first-time "try this" example for new users
- [ ] **Comparison mode** — one sentence → all languages side by side
- [ ] **Progress tracking** — sentences learned, languages used, streaks

## Cron Test Matrix
Each iteration should run these checks:
1. English → Korean: explanations in English? Translation in 한글?
2. English → Japanese (with pronoun): gender note present?
3. English → Chinese: translation uses 台灣用法? No simplified?
4. Chinese → Korean: explanations in 繁體中文?
5. Check pronunciation against deterministic lib (once installed)
6. Check for any 簡體字 in output
