# Sent-Say Constitution
_Every design decision Jimmy has made. Test against this._

## Language Rules

1. **ALL Chinese output must be Traditional Chinese (繁體中文) with Taiwan usage (台灣用法)** — NEVER Simplified Chinese
   - ✅ 跟我說 / ❌ 給我講
   - ✅ 軟體 / ❌ 軟件
   - ✅ 捷運 / ❌ 地鐵
   - ✅ 影片 / ❌ 視頻
   - ✅ 計程車 / ❌ 出租車

2. **Explanations (grammar notes, meanings, cultural notes) must be in the INPUT language** — not the target language
   - English input → English explanations
   - Chinese input → 繁體中文 explanations
   - NEVER mix languages in explanations

3. **Japanese translations must note gender implications** of pronouns (私/僕/俺/あたし)

4. **Speaker identity toggles affect ALL languages** — not just Japanese
   - Korean: 나/저, speech levels
   - Hebrew: gendered verbs, adjectives, pronouns
   - Spanish/Italian: gendered adjectives
   - Greek: gendered articles, adjectives

5. **Pronunciation must use standard romanization systems**
   - Japanese: Hepburn romaji (oshiete kudasai, NOT OLLOW-te)
   - Chinese: pinyin with tones
   - Korean: Revised Romanization

6. **Mixed-language input** (e.g. "這杯咖啡 taste 真的好棒") — understand the meaning, translate the WHOLE meaning. Don't keep source words in translation.

7. **Input language selector** — user can choose Auto-detect / English / 中文. Don't guess wrong.

## Layout Rules

8. **Result card order** (top to bottom):
   - Input sentence (small, dim) — "What do you recommend?"
   - Translation (big, bold) — 您推薦這份菜單上的什麼？
   - Pronunciation — nín tuī jiàn...
   - NO literal translation line (removed)
   - Formality badge

9. **Language pills wrap to multiple rows** — no horizontal slider

10. **Favicon uses Traditional Chinese 學** — not Simplified 学

## Interaction Rules

11. **注音 (Zhuyin) IME compatibility** — Enter during composition must NOT trigger submit

12. **Password gate** — password stored in localStorage permanently (trusted device)

13. **Native expression** must be genuinely DIFFERENT from the translation — if it's the same, don't show it

14. **Word breakdown chips have hover highlight** — should be clickable (expand with examples, conjugations) [TODO]

## Feature Rules

15. **"Surprise me" gives sentences in the INPUT language** — not the target language. User translates FROM their language.

16. **Story Mode** — sentence-by-sentence playthrough from famous literature/TV/anime [TODO]

17. **Daily report cron at 7 AM Chicago time** — what was built in last 24 hours

## Quality Standards

18. **Translation must not echo back the input** — if target is Japanese, output must be Japanese, not Chinese

19. **Model limitations are acknowledged** — qwen2.5:7b struggles with mixed-language input and sometimes ignores language instructions. Validate output.

20. **Server must stay up** — watchdog auto-restarts if it crashes

---
_Last updated: 2026-02-14_
_Source: Jimmy's commands in #⚡ Build Lab_
