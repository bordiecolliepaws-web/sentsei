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
- [ ] **Speaker toggles**
  - Gender: ♀ / ♂ / Neutral (language-dependent)
  - Formality: Casual / Polite / Formal
  - Scenario context (restaurant, office, etc.)
  - Pass these to the LLM prompt
- [ ] **Clickable word chips**
  - Click a word → expand panel with example sentences, conjugations, related words
  - Design the interaction: inline expand? modal? slide-out?
- [ ] **Speaker/identity toggles (gender, age, formality)** ⭐
  - Toggle: ♀ / ♂ / Neutral — affects ALL languages, not just Japanese
  - Japanese: 私/僕/俺/あたし, verb endings
  - Korean: 나/저, speech levels (반말/존댓말)
  - Hebrew: almost everything is gendered (verbs, adjectives, pronouns)
  - Spanish/Italian: gendered adjectives, noun agreements
  - Greek: gendered articles, adjectives, participles
  - Formality: Casual / Polite / Formal (separate from gender)
  - Pass identity context to LLM prompt so translation reflects speaker
  - Show toggle bar above or beside the input
- [ ] **Persistent sentence history (sidebar/drawer)**
  - Already in localStorage
  - Promote to visible side panel (desktop) or bottom drawer (mobile)
  - Show target language + translation preview
  - Survives refresh (already does via localStorage)
- [ ] **"Surprise me" + Story Mode 📖**
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
