# Surprise Me + Story Mode — Implementation Plan

## Surprise Me
- Button next to "Learn" button
- Hits `/api/surprise?lang=ko` endpoint  
- Backend has curated sentence lists per language, categorized by difficulty
- Returns a random sentence + metadata (difficulty, category)
- Frontend fills the input and auto-submits

## Story Mode
- Toggle/tab that switches from free-type to story browse
- `/api/stories` — list available stories with metadata
- `/api/story/{story_id}?index=0` — get sentence at index
- Each story: title, source attribution, language, list of sentences
- "Next →" button advances through story
- Progress tracked in localStorage
- Stories drawn from famous literature, TV, anime, movies per language

## Curated Content (embed in backend)

### Japanese Stories
- **Spirited Away** (千と千尋の神隠し) — 5 iconic lines
- **Your Name** (君の名は) — 5 lines
- **Common Daily** — 5 everyday sentences

### Korean Stories  
- **Parasite** (기생충) — 5 lines
- **Squid Game** (오징어 게임) — 5 lines
- **Common Daily** — 5 everyday sentences

### Chinese Stories
- **In the Mood for Love** (花樣年華) — 5 lines
- **Common Daily** — 5 everyday sentences

### Hebrew Stories
- **Common Daily** — 5 everyday sentences

### General (all languages)
- **Surprise Me pool**: ~10 sentences per language, varied difficulty

