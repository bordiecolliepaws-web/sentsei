# Sentsei TODO Queue
_Items for cron iterations to work through, in priority order._

## P0 — Critical Quality Issues
- [ ] **Pronunciation: use deterministic libraries, not LLM**
  - Japanese: pykakasi or cutlet (MeCab-based romaji)
  - Korean: korean-romanizer or hangul-romanize
  - Chinese: pypinyin (with tone marks)
  - Hebrew: transliteration lib TBD
  - Greek: transliterate lib TBD
  - Install via uv, post-process LLM output server-side
- [ ] **Japanese gender/pronoun warnings**
  - When 私/僕/俺/あたし appear in breakdown, inject explicit gender/formality note
  - Backend: add post-processing step for Japanese results

## P1 — UX / Product Features
- [ ] **Mobile-first layout**
  - Test and fix narrow viewport behavior
  - Input + language picker not crushed
  - Results scroll nicely
  - Consider bottom sheet for history instead of sidebar
- [ ] **Better language selector UI (not dropdown)**
  - Pill toggles / flag chips instead of `<select>`
  - Works on both mobile and desktop
  - Consider: horizontal scrollable row of language pills
- [ ] **Speaker toggles**
  - Gender: ♀ / ♂ / Neutral (language-dependent)
  - Formality: Casual / Polite / Formal
  - Scenario context (restaurant, office, etc.)
  - Pass these to the LLM prompt
- [ ] **Persistent sentence history (sidebar/drawer)**
  - Already in localStorage
  - Promote to visible side panel (desktop) or bottom drawer (mobile)
  - Show target language + translation preview
  - Survives refresh (already does via localStorage)
- [ ] **Random/auto-suggest input sentences**
  - "Surprise me" / "I don't know what to say" button
  - Curated per target language + difficulty
  - Maybe: "Daily sentence" feature

## P2 — Design / Branding
- [ ] **New name** (Jimmy doesn't like "Sentsei")
  - Generate candidates, evaluate
- [ ] **New color palette + typography**
  - Current purple/dark theme: needs refresh
  - Consider warmer tones, better contrast
  - Test on mobile

## Cron Test Matrix
Each iteration should run these checks:
1. English → Korean: explanations in English? Translation in 한글?
2. English → Japanese (with pronoun): gender note present?
3. English → Chinese: translation uses 台灣用法? No simplified?
4. Chinese → Korean: explanations in 繁體中文?
5. Check pronunciation against deterministic lib (once installed)
6. Check for any 簡體字 in output
