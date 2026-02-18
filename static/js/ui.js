// DOM helpers, rendering functions, progress stats
import { state, DOM, LANG_FLAGS, KEYS, LANGUAGE_TIPS, MS_PER_DAY, LOADING_PHASES, DAY_MS, hooks } from './state.js';
import { friendlyError, copyTextToClipboard, syncModalOpenState } from './api.js';
import { getDueItems } from './srs.js';
import { createFavoriteButton } from './favorites.js';

// === Progress Stats ===

export function loadProgressStats() {
    const base = {
        sentencesLearned: 0,
        languagesUsed: [],
        quiz: { correct: 0, total: 0 },
        streak: 0,
        lastActivityDate: '',
        firstActivityDate: '',
        lastLearnDate: ''
    };

    try {
        const raw = localStorage.getItem(KEYS.PROGRESS_STATS) || '{}';
        const parsed = JSON.parse(raw);
        if (!parsed || typeof parsed !== 'object') return base;

        const sentencesLearned = Math.max(0, Number(parsed.sentencesLearned) || 0);
        const languagesRaw = Array.isArray(parsed.languagesUsed) ? parsed.languagesUsed : [];
        const languagesUsed = [...new Set(languagesRaw
            .map(v => (typeof v === 'string' ? v.trim().toLowerCase() : ''))
            .filter(Boolean))];
        const quizRaw = parsed.quiz && typeof parsed.quiz === 'object' ? parsed.quiz : {};
        const quiz = {
            correct: Math.max(0, Number(quizRaw.correct) || 0),
            total: Math.max(0, Number(quizRaw.total) || 0)
        };
        const streak = Math.max(0, Number(parsed.streak) || 0);
        const lastActivityDate = typeof parsed.lastActivityDate === 'string' ? parsed.lastActivityDate : '';
        const firstActivityDate = typeof parsed.firstActivityDate === 'string' ? parsed.firstActivityDate : '';
        const lastLearnDate = typeof parsed.lastLearnDate === 'string' ? parsed.lastLearnDate : '';

        return { sentencesLearned, languagesUsed, quiz, streak, lastActivityDate, firstActivityDate, lastLearnDate };
    } catch {
        return base;
    }
}

export function saveProgressStats() {
    localStorage.setItem(KEYS.PROGRESS_STATS, JSON.stringify(state.progressStats));
    hooks.afterSaveProgressStats.forEach(fn => fn());
}

export function todayDateKey() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

export function parseDateKey(dateKey) {
    if (!dateKey || typeof dateKey !== 'string') return null;
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dateKey);
    if (!match) return null;
    const year = Number(match[1]);
    const monthIndex = Number(match[2]) - 1;
    const day = Number(match[3]);
    const date = new Date(year, monthIndex, day);
    if (date.getFullYear() !== year || date.getMonth() !== monthIndex || date.getDate() !== day) return null;
    return date;
}

export function dayDiff(fromDateKey, toDateKey) {
    const from = parseDateKey(fromDateKey);
    const to = parseDateKey(toDateKey);
    if (!from || !to) return null;
    return Math.round((to.getTime() - from.getTime()) / MS_PER_DAY);
}

export function formatDateLabel(dateKey) {
    const parsed = parseDateKey(dateKey);
    if (!parsed) return '';
    return parsed.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

export function addProgressLanguage(languageCode) {
    const code = typeof languageCode === 'string' ? languageCode.trim().toLowerCase() : '';
    if (!code) return;
    if (!state.progressStats.languagesUsed.includes(code)) {
        state.progressStats.languagesUsed.push(code);
    }
}

export function getLanguageNamesMap() {
    const langNames = {};
    DOM.langSelect.querySelectorAll('option').forEach(o => { langNames[o.value] = o.textContent; });
    return langNames;
}

export function renderProgressLanguages() {
    if (!DOM.statsLanguages) return;
    DOM.statsLanguages.innerHTML = '';

    const langNames = getLanguageNamesMap();
    if (!state.progressStats.languagesUsed.length) {
        const empty = document.createElement('span');
        empty.className = 'progress-stat-value';
        empty.textContent = 'No languages yet';
        DOM.statsLanguages.appendChild(empty);
        return;
    }

    state.progressStats.languagesUsed.forEach(code => {
        const chip = document.createElement('span');
        chip.className = 'progress-lang-chip';
        const flag = LANG_FLAGS[code] || '🌐';
        const name = langNames[code] || code.toUpperCase();
        chip.textContent = `${flag} ${name}`;
        DOM.statsLanguages.appendChild(chip);
    });
}

export function renderProgressStats() {
    if (!DOM.statsTotalSentences) return;

    DOM.statsTotalSentences.textContent = String(state.progressStats.sentencesLearned || 0);
    renderProgressLanguages();

    const quizTotal = Math.max(0, Number(state.progressStats.quiz?.total) || 0);
    const quizCorrect = Math.max(0, Number(state.progressStats.quiz?.correct) || 0);
    if (quizTotal > 0) {
        const accuracy = Math.round((quizCorrect / quizTotal) * 100);
        DOM.statsQuizAccuracy.textContent = `${accuracy}% (${quizCorrect}/${quizTotal})`;
    } else {
        DOM.statsQuizAccuracy.textContent = 'No quizzes taken yet';
    }

    const streak = Math.max(0, Number(state.progressStats.streak) || 0);
    DOM.statsStreak.textContent = `${streak} ${streak === 1 ? 'day' : 'days'}`;

    const learningSince = formatDateLabel(state.progressStats.firstActivityDate);
    DOM.statsLearningSince.textContent = learningSince || 'Not started yet';

    const srsDeckEl = document.getElementById('stats-srs-deck');
    const srsDueEl = document.getElementById('stats-srs-due');
    const srsMasteredEl = document.getElementById('stats-srs-mastered');
    if (srsDeckEl) srsDeckEl.textContent = String(state.srsDeck.length);
    if (srsDueEl) srsDueEl.textContent = String(getDueItems().length);
    if (srsMasteredEl) srsMasteredEl.textContent = String(state.srsDeck.filter(i => i.interval > 30 * DAY_MS).length);
}

export function persistProgressAndRefresh() {
    saveProgressStats();
    renderProgressStats();
}

export function recordLearnProgress(languageCode, learnedCount = 1) {
    const increment = Math.max(0, Number(learnedCount) || 0);
    if (increment < 1) return;

    const today = todayDateKey();
    if (!state.progressStats.firstActivityDate) {
        state.progressStats.firstActivityDate = today;
    }
    state.progressStats.lastActivityDate = today;
    state.progressStats.sentencesLearned += increment;
    addProgressLanguage(languageCode);

    if (!state.progressStats.lastLearnDate) {
        state.progressStats.streak = 1;
        state.progressStats.lastLearnDate = today;
    } else if (state.progressStats.lastLearnDate !== today) {
        const diff = dayDiff(state.progressStats.lastLearnDate, today);
        state.progressStats.streak = diff === 1 ? state.progressStats.streak + 1 : 1;
        state.progressStats.lastLearnDate = today;
    }

    persistProgressAndRefresh();
}

export function loadQuizStats() {
    const quiz = state.progressStats.quiz && typeof state.progressStats.quiz === 'object' ? state.progressStats.quiz : {};
    return {
        correct: Math.max(0, Number(quiz.correct) || 0),
        total: Math.max(0, Number(quiz.total) || 0)
    };
}

export function saveQuizStats() {
    state.progressStats.quiz = {
        correct: Math.max(0, Number(state.quizStats.correct) || 0),
        total: Math.max(0, Number(state.quizStats.total) || 0)
    };
    persistProgressAndRefresh();
}

export function openStatsModal() {
    renderProgressStats();
    DOM.statsModal.classList.remove('hidden');
    syncModalOpenState();
}

export function closeStatsModal() {
    DOM.statsModal.classList.add('hidden');
    syncModalOpenState();
}

// === Loading UI ===

export function startLoadingTimer() {
    stopLoadingTimer();
    const start = Date.now();
    DOM.loadingCancel.style.display = 'none';
    DOM.loadingElapsed.textContent = '';
    state.loadingTimer = setInterval(() => {
        const elapsed = Math.floor((Date.now() - start) / 1000);
        DOM.loadingElapsed.textContent = elapsed + 's';
        for (let i = LOADING_PHASES.length - 1; i >= 0; i--) {
            if (elapsed >= LOADING_PHASES[i].at) {
                DOM.loadingMessage.textContent = LOADING_PHASES[i].msg;
                break;
            }
        }
        if (elapsed >= 8) DOM.loadingCancel.style.display = 'inline-block';
    }, 1000);
}

export function stopLoadingTimer() {
    if (state.loadingTimer) { clearInterval(state.loadingTimer); state.loadingTimer = null; }
}

export function showError(msg) {
    DOM.errorMessage.textContent = msg;
    DOM.errorBanner.style.display = 'block';
}

export function hideError() { DOM.errorBanner.style.display = 'none'; }

export function setRandomLoadingTip() {
    const selectedLang = DOM.langSelect.value;
    const langName = DOM.langSelect.options[DOM.langSelect.selectedIndex]?.textContent || 'this language';
    const tips = LANGUAGE_TIPS[selectedLang] || LANGUAGE_TIPS.default;
    const randomTip = tips[Math.floor(Math.random() * tips.length)];
    DOM.loadingTip.textContent = `${langName} tip: ${randomTip}`;
}

// === TTS / Speech ===
import { LANG_SPEECH_MAP } from './state.js';

export function speakTranslation(text, langCode, btn) {
    if (!window.speechSynthesis) return;
    speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = LANG_SPEECH_MAP[langCode] || langCode;
    utterance.rate = 0.9;
    const voices = speechSynthesis.getVoices();
    const exactVoices = voices.filter(v => v.lang === utterance.lang);
    const prefixVoices = voices.filter(v => v.lang.startsWith(langCode));
    const candidates = exactVoices.length > 0 ? exactVoices : prefixVoices;
    const sorted = candidates.sort((a, b) => {
        const aLocal = !a.localService ? 1 : 0;
        const bLocal = !b.localService ? 1 : 0;
        if (aLocal !== bLocal) return aLocal - bLocal;
        const aCompact = a.name.toLowerCase().includes('compact') ? 1 : 0;
        const bCompact = b.name.toLowerCase().includes('compact') ? 1 : 0;
        return aCompact - bCompact;
    });
    if (sorted.length > 0) utterance.voice = sorted[0];
    if (btn) {
        btn.classList.add('speaking');
        const label = btn.querySelector('.speak-label');
        if (label) label.textContent = '▶ Playing';
        utterance.onend = () => {
            btn.classList.remove('speaking');
            if (label) label.textContent = 'Listen';
        };
        utterance.onerror = () => {
            btn.classList.remove('speaking');
            if (label) label.textContent = 'Listen';
        };
    }
    speechSynthesis.speak(utterance);
}

// === Theme ===
export function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    const icon = theme === 'light' ? '☀️' : '🌙';
    const label = theme === 'light' ? 'Dark Mode' : 'Light Mode';
    const toggleBtn = document.getElementById('theme-toggle');
    const menuIcon = document.getElementById('menu-theme-icon');
    const menuLabel = document.getElementById('menu-theme-label');
    if (toggleBtn) toggleBtn.textContent = icon;
    if (menuIcon) menuIcon.textContent = icon;
    if (menuLabel) menuLabel.textContent = label;
}

export function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'dark';
    const next = current === 'dark' ? 'light' : 'dark';
    localStorage.setItem(KEYS.THEME, next);
    applyTheme(next);
}

// === Init toggle helper ===
export function initToggle(container, current, storageKey, setter) {
    container.querySelectorAll('.toggle-pill').forEach(p => {
        const isActive = p.dataset.value === current;
        p.classList.toggle('active', isActive);
        p.setAttribute('role', 'radio');
        p.setAttribute('aria-checked', String(isActive));
        p.addEventListener('click', () => {
            container.querySelectorAll('.toggle-pill').forEach(q => {
                q.classList.remove('active');
                q.setAttribute('aria-checked', 'false');
            });
            p.classList.add('active');
            p.setAttribute('aria-checked', 'true');
            localStorage.setItem(storageKey, p.dataset.value);
            setter(p.dataset.value);
        });
    });
}

// === Romanization ===
export function applyRomanization() {
    document.body.classList.toggle('hide-romanization', !state.showRomanization);
    DOM.romanizationToggle.classList.toggle('active', state.showRomanization);
    const label = document.getElementById('romanization-label');
    if (label) label.textContent = state.showRomanization ? 'On' : 'Off';
}

// === Escape HTML ===
export function escapeHtml(s) {
    if (!s) return '';
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// === Compare results ===
export function renderCompareResults(data) {
    const results = Array.isArray(data.results) ? data.results : [];
    const originalSentence = data.sentence || DOM.sentenceInput.value.trim();
    const cardsHTML = results.map(entry => {
        const code = (entry.language || '').toLowerCase();
        const flag = LANG_FLAGS[code] || '🌐';
        const languageName = entry.language_name || code.toUpperCase() || 'Language';
        const translation = entry.translation || 'No translation';
        const pronunciation = entry.pronunciation || 'Pronunciation unavailable';
        const literal = entry.literal || 'No literal translation';
        return `
            <div class="compare-card">
                <div class="compare-card-lang"><span class="flag">${flag}</span>${languageName}</div>
                <div class="compare-card-translation">${translation}</div>
                <div class="compare-card-pronunciation">${pronunciation}</div>
                <div class="compare-card-literal">Literal: ${literal}</div>
            </div>
        `;
    }).join('');

    DOM.compareResults.innerHTML = `
        <div class="compare-results-head">
            <div class="compare-results-label">Comparison mode</div>
            <button type="button" class="compare-close-btn" id="compare-close-btn">✕ Close</button>
        </div>
        <div class="compare-results-source">"${originalSentence}"</div>
        ${results.length ? `<div class="compare-grid">${cardsHTML}</div>` : '<div class="compare-empty">No comparison results returned.</div>'}
    `;
    const closeBtn = document.getElementById('compare-close-btn');
    if (closeBtn) closeBtn.addEventListener('click', closeCompareResults);
    DOM.compareResults.classList.remove('hidden');
    DOM.compareResults.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

export function closeCompareResults() {
    DOM.compareResults.classList.add('hidden');
    DOM.compareResults.innerHTML = '';
}

function syncVisibleResultDividers() {
    if (!DOM.results) return;
    DOM.results.querySelectorAll('.history-divider').forEach(divider => {
        divider.classList.add('lang-hidden');
    });

    let hasVisibleCard = false;
    DOM.results.querySelectorAll('.result-card').forEach(card => {
        if (card.classList.contains('lang-hidden')) return;
        if (hasVisibleCard) {
            const divider = card.previousElementSibling;
            if (divider && divider.classList.contains('history-divider')) {
                divider.classList.remove('lang-hidden');
            }
        }
        hasVisibleCard = true;
    });
}

export function filterResultsByLanguage(langCode) {
    if (!DOM.results) return;
    const selectedLang = (langCode || '').trim().toLowerCase();
    DOM.results.querySelectorAll('.result-card').forEach(card => {
        const cardLang = (card.dataset.lang || '').trim().toLowerCase();
        const shouldHide = Boolean(selectedLang) && cardLang !== selectedLang;
        card.classList.toggle('lang-hidden', shouldHide);
    });
    syncVisibleResultDividers();
}

// === Render result card ===
export function renderResult(data, original, reqCtx, elapsedMs) {
    const targetLang = (reqCtx.target_language || DOM.langSelect.value || '').trim().toLowerCase();
    const activeReqCtx = {
        ...reqCtx,
        target_language: targetLang || (reqCtx.target_language || DOM.langSelect.value || '').trim().toLowerCase()
    };
    const resultLangCode = activeReqCtx.target_language || '';
    const langNames = getLanguageNamesMap();
    const langFlag = LANG_FLAGS[resultLangCode] || '🌐';
    const langLabel = langNames[resultLangCode] || (resultLangCode ? resultLangCode.toUpperCase() : 'Unknown');
    const card = document.createElement('div');
    card.className = 'result-card';
    card.dataset.lang = resultLangCode;

    const DIFFICULTY_LABELS = { easy: 'Easy', medium: 'Medium', hard: 'Hard' };
    const hasBreakdown = data.breakdown && data.breakdown.length > 0;
    const breakdownHTML = hasBreakdown ? data.breakdown.map(w => `
        <div class="word-chip" role="button" tabindex="0" aria-expanded="false">
            <div class="word-target">
                <span class="difficulty-dot ${w.difficulty}" aria-label="${DIFFICULTY_LABELS[w.difficulty] || w.difficulty} difficulty"></span>
                ${w.word}
            </div>
            <div class="word-pron">${w.pronunciation}</div>
            <div class="word-meaning">${w.meaning}</div>
            ${w.note ? `<div class="word-note">${w.note}</div>` : ''}
        </div>
    `).join('') : '';

    const grammarHTML = (data.grammar_notes || []).map(n => `<li>${n}</li>`).join('');

    card.innerHTML = `
        <div class="result-main">
            <div class="result-source">"${original}"</div>
            <div class="result-translation">${data.translation}</div>
            <div class="result-pronunciation">${data.pronunciation}</div>
            <div class="result-meta">
                <div class="result-lang-badge" title="${escapeHtml(langLabel)}">${langFlag} ${escapeHtml((resultLangCode || '--').toUpperCase())}</div>
                <div class="result-formality">${data.formality}</div>
                ${data.sentence_difficulty ? `<div class="result-difficulty result-difficulty--${data.sentence_difficulty.level}" title="${(data.sentence_difficulty.factors || []).join(', ')}">${data.sentence_difficulty.level === 'beginner' ? '🟢' : data.sentence_difficulty.level === 'intermediate' ? '🟡' : '🔴'} ${data.sentence_difficulty.level}</div>` : ''}
                ${data.from_cache && data.ollama_offline ? '<div class="cached-badge" title="Served from cache while translation engine is offline">📦 cached</div>' : ''}
                ${data.detected_input_language ? `<div class="detected-lang-badge" title="Detected input language">🌐 ${data.detected_input_language === 'zh' ? '中文' : 'English'}</div>` : ''}
                ${elapsedMs ? `<div class="response-time" title="Response time">⚡ ${elapsedMs >= 1000 ? (elapsedMs / 1000).toFixed(1) + 's' : elapsedMs + 'ms'}</div>` : ''}
            </div>
            <div class="result-actions">
                <button type="button" class="speak-btn" aria-label="Listen to pronunciation" data-lang="${activeReqCtx.target_language}">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14" aria-hidden="true">
                        <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
                        <path d="M19.07 4.93a10 10 0 0 1 0 14.14"></path>
                        <path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path>
                    </svg>
                    <span class="speak-label">Listen</span>
                </button>
                <button type="button" class="copy-btn" aria-label="Copy translation">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                        <rect x="9" y="9" width="13" height="13" rx="2"></rect>
                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                    </svg>
                    <span class="copy-label">Copy</span>
                </button>
                <button type="button" class="share-btn" aria-label="Share link" data-sentence="${original.replace(/"/g, '&quot;')}" data-lang="${activeReqCtx.target_language}">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14" aria-hidden="true">
                        <circle cx="18" cy="5" r="3"></circle>
                        <circle cx="6" cy="12" r="3"></circle>
                        <circle cx="18" cy="19" r="3"></circle>
                        <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line>
                        <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line>
                    </svg>
                    <span class="share-label">Share</span>
                </button>
            </div>
        </div>
        ${hasBreakdown ? `
        <div class="breakdown-section">
            <div class="section-title">Word Breakdown</div>
            <div class="word-chips">${breakdownHTML}</div>
        </div>
        <div class="notes-section">
            <div class="section-title">Grammar Notes</div>
            <ul class="grammar-list">${grammarHTML}</ul>
            ${data.cultural_note ? `<div class="cultural-note">💡 ${data.cultural_note}</div>` : ''}
            ${data.alternative ? `<div class="alternative-note">🔄 Alternative: ${data.alternative}</div>` : ''}
            ${data.native_expression ? `<div class="cultural-note">🗣️ Native expression: ${data.native_expression}</div>` : ''}
            ${data.tw_native_phrases && data.tw_native_phrases.length > 0 ? `
                <div class="cultural-note" style="margin-top:0.5rem;">
                    <div style="font-size:0.75rem;color:var(--text-dim);margin-bottom:0.3rem;">🇹🇼 How Taiwanese people actually say it:</div>
                    ${data.tw_native_phrases.map(p => `<div style="margin:0.3rem 0;"><strong>${p.phrase}</strong> <span style="color:var(--accent);font-size:0.8rem;">${p.pinyin}</span><br><span style="font-size:0.8rem;color:var(--text-dim);">${p.meaning}${p.context ? ' · ' + p.context : ''}</span></div>`).join('')}
                </div>
            ` : ''}
        </div>
        ` : `
        <div class="breakdown-section breakdown-lazy">
            <div class="section-title">Word Breakdown</div>
            <div class="word-chips segment-chips"><div class="word-detail-loading">Segmenting...</div></div>
            <div class="grammar-lazy-section" style="margin-top:0.8rem;">
                <button type="button" class="show-grammar-btn" style="width:100%;padding:0.65rem;background:var(--accent-glow);border:1px solid rgba(232,168,56,0.25);border-radius:8px;color:var(--accent);font-size:0.85rem;cursor:pointer;transition:all 0.2s;font-family:inherit;">
                    📝 Load grammar notes & detailed breakdown
                </button>
            </div>
        </div>
        `}
    `;

    // Clickable word chips
    card.querySelectorAll('.word-chip').forEach((chip, idx) => {
        const wordData = data.breakdown[idx];
        const chipHandler = () => {
            handleWordChipClick(chip, wordData, data, activeReqCtx);
            chip.setAttribute('aria-expanded', String(chip.classList.contains('expanded')));
        };
        chip.addEventListener('click', chipHandler);
        chip.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                chipHandler();
            }
        });
    });

    // Speak button
    const speakBtn = card.querySelector('.speak-btn');
    if (speakBtn) {
        speakBtn.addEventListener('click', () => {
            speakTranslation(data.translation, speakBtn.dataset.lang, speakBtn);
        });
    }

    const copyBtn = card.querySelector('.copy-btn');
    const copyLabelEl = card.querySelector('.copy-label');
    copyBtn.addEventListener('click', async () => {
        const copied = await copyTextToClipboard(data.translation);
        copyLabelEl.textContent = copied ? 'Copied' : 'Failed';
        if (copied) copyBtn.classList.add('copied');
        setTimeout(() => {
            copyLabelEl.textContent = 'Copy';
            copyBtn.classList.remove('copied');
        }, 1200);
    });

    // Favorite button
    const resultActions = card.querySelector('.result-actions');
    if (resultActions) {
        const favBtn = createFavoriteButton(original, data.translation, activeReqCtx.target_language, data.pronunciation);
        resultActions.appendChild(favBtn);
    }

    // Share button
    const shareBtn = card.querySelector('.share-btn');
    if (shareBtn) {
        shareBtn.addEventListener('click', async () => {
            const s = shareBtn.dataset.sentence;
            const t = shareBtn.dataset.lang;
            const shareUrl = new URL(window.location.href);
            shareUrl.search = '';
            shareUrl.searchParams.set('s', s);
            shareUrl.searchParams.set('t', t);
            const url = shareUrl.toString();
            const shareLabelEl = shareBtn.querySelector('.share-label');
            if (navigator.share) {
                try { await navigator.share({ title: 'Learn: ' + s, url: url }); } catch(e) { /* user cancelled */ }
            } else {
                const ok = await copyTextToClipboard(url);
                shareLabelEl.textContent = ok ? 'Copied!' : 'Failed';
                setTimeout(() => { shareLabelEl.textContent = 'Share'; }, 1200);
            }
        });
    }

    // Update URL
    const shareUrl = new URL(window.location.href);
    shareUrl.search = '';
    shareUrl.searchParams.set('s', original);
    shareUrl.searchParams.set('t', activeReqCtx.target_language);
    history.replaceState(null, '', shareUrl.toString());

    // Fast segment
    const segmentChips = card.querySelector('.segment-chips');
    const myGeneration = state.learnGeneration;
    if (segmentChips) {
        (async () => {
            try {
                const segResp = await fetch('/api/segment', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-App-Password': state.appPassword },
                    body: JSON.stringify({
                        sentence: original,
                        translation: data.translation,
                        target_language: activeReqCtx.target_language,
                    })
                });
                if (!segResp.ok) throw new Error('Failed');
                if (myGeneration !== state.learnGeneration) return;
                const seg = await segResp.json();
                const segWords = seg.breakdown || [];
                if (segWords.length === 0) {
                    segmentChips.innerHTML = '<div class="word-detail-loading">No segmentation available.</div>';
                    return;
                }
                segmentChips.innerHTML = segWords.map(w => `
                    <div class="word-chip" role="button" tabindex="0" aria-expanded="false">
                        <div class="word-target">${w.word}</div>
                        <div class="word-pron">${w.pronunciation || ''}</div>
                        <div class="word-meaning">${w.meaning || ''}</div>
                    </div>
                `).join('');
                data._segmentBreakdown = segWords;
                segmentChips.querySelectorAll('.word-chip').forEach((chip, idx) => {
                    const wordData = segWords[idx];
                    const chipHandler = () => handleWordChipClick(chip, wordData, data, activeReqCtx);
                    chip.addEventListener('click', chipHandler);
                    chip.addEventListener('keydown', (e) => {
                        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); chipHandler(); }
                    });
                });
            } catch (err) {
                segmentChips.innerHTML = '<div class="word-detail-loading">Segmentation unavailable.</div>';
            }
        })();
    }

    // Lazy-load grammar
    const showGrammarBtn = card.querySelector('.show-grammar-btn');
    if (showGrammarBtn) {
        showGrammarBtn.addEventListener('click', async () => {
            showGrammarBtn.disabled = true;
            showGrammarBtn.textContent = '⏳ Loading grammar notes...';
            try {
                const bdResp = await fetch('/api/breakdown', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-App-Password': state.appPassword },
                    body: JSON.stringify({
                        sentence: original,
                        translation: data.translation,
                        target_language: activeReqCtx.target_language,
                        input_language: activeReqCtx.input_language || state.selectedInputLang,
                        speaker_gender: state.selectedGender,
                        speaker_formality: state.selectedFormality
                    })
                });
                if (!bdResp.ok) throw new Error('Failed');
                if (myGeneration !== state.learnGeneration) return;
                const bd = await bdResp.json();

                data.breakdown = bd.breakdown || data._segmentBreakdown || [];
                data.grammar_notes = bd.grammar_notes || [];
                data.cultural_note = bd.cultural_note || null;
                data.alternative = bd.alternative || null;

                const DIFF_LABELS = { easy: 'Easy', medium: 'Medium', hard: 'Hard' };
                const bdHTML = data.breakdown.map(w => `
                    <div class="word-chip" role="button" tabindex="0" aria-expanded="false">
                        <div class="word-target">
                            <span class="difficulty-dot ${w.difficulty}" aria-label="${DIFF_LABELS[w.difficulty] || w.difficulty} difficulty"></span>
                            ${w.word}
                        </div>
                        <div class="word-pron">${w.pronunciation}</div>
                        <div class="word-meaning">${w.meaning}</div>
                        ${w.note ? `<div class="word-note">${w.note}</div>` : ''}
                    </div>
                `).join('');
                const gHTML = (data.grammar_notes || []).map(n => `<li>${n}</li>`).join('');

                const section = showGrammarBtn.closest('.breakdown-section');
                section.innerHTML = `
                    <div class="section-title">Word Breakdown</div>
                    <div class="word-chips">${bdHTML}</div>
                    <div class="notes-section" style="margin-top:0.8rem;">
                        <div class="section-title">Grammar Notes</div>
                        <ul class="grammar-list">${gHTML}</ul>
                        ${data.cultural_note ? `<div class="cultural-note">💡 ${data.cultural_note}</div>` : ''}
                        ${data.alternative ? `<div class="alternative-note">🔄 Alternative: ${data.alternative}</div>` : ''}
                    </div>
                `;
                section.classList.remove('breakdown-lazy');

                section.querySelectorAll('.word-chip').forEach((chip, idx) => {
                    const wordData = data.breakdown[idx];
                    const chipHandler = () => handleWordChipClick(chip, wordData, data, activeReqCtx);
                    chip.addEventListener('click', chipHandler);
                    chip.addEventListener('keydown', (e) => {
                        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); chipHandler(); }
                    });
                });
            } catch (err) {
                showGrammarBtn.textContent = '❌ Failed to load — tap to retry';
                showGrammarBtn.disabled = false;
            }
        });
    }

    // Context examples
    const ctxSection = document.createElement('div');
    ctxSection.className = 'context-examples-section';
    ctxSection.innerHTML = `
        <div class="context-examples-toggle" role="button" tabindex="0" aria-expanded="false">
            📝 See it in context <span class="ctx-arrow">▸</span>
        </div>
        <div class="context-examples-body" style="display:none;">
            <div class="ctx-loading">Loading examples...</div>
        </div>
    `;
    card.appendChild(ctxSection);

    const ctxToggle = ctxSection.querySelector('.context-examples-toggle');
    const ctxBody = ctxSection.querySelector('.context-examples-body');
    const ctxArrow = ctxSection.querySelector('.ctx-arrow');
    let ctxLoaded = false;
    const toggleCtx = async () => {
        const isOpen = ctxBody.style.display !== 'none';
        ctxBody.style.display = isOpen ? 'none' : 'block';
        ctxArrow.textContent = isOpen ? '▸' : '▾';
        ctxToggle.setAttribute('aria-expanded', String(!isOpen));
        if (!isOpen && !ctxLoaded) {
            ctxLoaded = true;
            try {
                const ctxResp = await fetch('/api/context-examples', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-App-Password': state.appPassword },
                    body: JSON.stringify({
                        translation: data.translation,
                        target_language: activeReqCtx.target_language,
                        source_sentence: original
                    })
                });
                if (!ctxResp.ok) throw new Error('Failed');
                const ctxData = await ctxResp.json();
                if (ctxData.examples && ctxData.examples.length > 0) {
                    ctxBody.innerHTML = ctxData.examples.map(ex => `
                        <div class="ctx-example">
                            <div class="ctx-sentence">${ex.sentence}</div>
                            <div class="ctx-pron">${ex.pronunciation || ''}</div>
                            <div class="ctx-meaning">${ex.meaning}</div>
                            ${ex.context ? `<div class="ctx-context">${ex.context}</div>` : ''}
                        </div>
                    `).join('');
                } else {
                    ctxBody.innerHTML = '<div class="ctx-empty">No examples available.</div>';
                }
            } catch(e) {
                ctxBody.innerHTML = '<div class="ctx-empty">Could not load examples.</div>';
            }
        }
    };
    ctxToggle.addEventListener('click', toggleCtx);
    ctxToggle.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleCtx(); }
    });

    // Prepend new result
    if (DOM.results.children.length > 0) {
        const divider = document.createElement('div');
        divider.className = 'history-divider';
        DOM.results.insertBefore(divider, DOM.results.firstChild);
    }
    DOM.results.insertBefore(card, DOM.results.firstChild);
    filterResultsByLanguage(DOM.langSelect.value);

    requestAnimationFrame(() => {
        if (!card.classList.contains('lang-hidden')) {
            card.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    });
}

async function handleWordChipClick(chip, wordData, fullData, reqCtx) {
    if (chip.classList.contains('expanded')) {
        chip.classList.remove('expanded');
        const detail = chip.querySelector('.word-detail');
        if (detail) detail.remove();
        return;
    }

    const parent = chip.closest('.word-chips');
    parent.querySelectorAll('.word-chip.expanded').forEach(other => {
        other.classList.remove('expanded');
        const d = other.querySelector('.word-detail');
        if (d) d.remove();
    });

    chip.classList.add('expanded');

    const detailDiv = document.createElement('div');
    detailDiv.className = 'word-detail';
    detailDiv.innerHTML = '<div class="word-detail-loading">Looking up word details...</div>';
    chip.appendChild(detailDiv);

    try {
        const resp = await fetch('/api/word-detail-stream', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-App-Password': state.appPassword
            },
            body: JSON.stringify({
                word: wordData.word,
                meaning: wordData.meaning,
                target_language: reqCtx.target_language,
                sentence_context: fullData.translation
            })
        });

        if (!resp.ok) throw new Error(await friendlyError(resp));

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let detail = null;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });

            const lines = buffer.split('\n');
            buffer = lines.pop();

            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                try {
                    const evt = JSON.parse(line.slice(6));
                    if (evt.type === 'progress') {
                        const loadingEl = detailDiv.querySelector('.word-detail-loading');
                        if (loadingEl) loadingEl.textContent = evt.status;
                    } else if (evt.type === 'result') {
                        detail = evt.data;
                    } else if (evt.type === 'error') {
                        throw new Error(evt.message);
                    }
                } catch (parseErr) {
                    if (parseErr.message && !parseErr.message.includes('JSON')) throw parseErr;
                }
            }
        }

        if (!detail) detail = { examples: [], conjugations: [], related: [] };

        let html = '';
        if (detail.examples && detail.examples.length) {
            html += '<div class="word-detail-section"><div class="word-detail-label">Examples</div><ul class="word-detail-examples">';
            detail.examples.forEach(ex => {
                html += `<li>${ex.sentence}<br><span class="example-pron">${ex.pronunciation || ''}</span> <span class="example-meaning">${ex.meaning}</span></li>`;
            });
            html += '</ul></div>';
        }
        if (detail.conjugations && detail.conjugations.length) {
            html += '<div class="word-detail-section"><div class="word-detail-label">Forms</div><div class="word-detail-conjugations">';
            detail.conjugations.forEach(c => {
                html += `<span class="conjugation-tag">${c.form} <span class="conj-label">${c.label}</span></span>`;
            });
            html += '</div></div>';
        }
        if (detail.related && detail.related.length) {
            html += '<div class="word-detail-section"><div class="word-detail-label">Related</div><div class="word-detail-related">';
            detail.related.forEach(r => {
                html += `<span class="related-word-tag" title="${r.meaning}">${r.word} — ${r.meaning}</span>`;
            });
            html += '</div></div>';
        }
        detailDiv.innerHTML = html || '<div class="word-detail-loading">No additional details available.</div>';
    } catch (err) {
        console.error(err);
        detailDiv.innerHTML = '<div class="word-detail-loading">Failed to load details.</div>';
    }
}
