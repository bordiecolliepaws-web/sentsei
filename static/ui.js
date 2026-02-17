// ui.js — DOM helpers, rendering, TTS, progress display
import {
    state, dom, LANG_FLAGS, LANG_SPEECH_MAP, LANGUAGE_TIPS, DAY_MS,
    getLanguageNamesMap, formatDateLabel, todayDateKey, dayDiff,
    saveProgressStats, copyTextToClipboard, escapeHtml
} from './state.js';
import { friendlyError } from './api.js';
import { getDueItems } from './srs.js';

// --- Progress rendering ---

function addProgressLanguage(languageCode) {
    const code = typeof languageCode === 'string' ? languageCode.trim().toLowerCase() : '';
    if (!code) return;
    if (!state.progressStats.languagesUsed.includes(code)) {
        state.progressStats.languagesUsed.push(code);
    }
}

export function renderProgressLanguages() {
    const statsLanguagesEl = dom('stats-languages');
    if (!statsLanguagesEl) return;
    statsLanguagesEl.innerHTML = '';
    const langNames = getLanguageNamesMap();
    if (!state.progressStats.languagesUsed.length) {
        const empty = document.createElement('span');
        empty.className = 'progress-stat-value';
        empty.textContent = 'No languages yet';
        statsLanguagesEl.appendChild(empty);
        return;
    }
    state.progressStats.languagesUsed.forEach(code => {
        const chip = document.createElement('span');
        chip.className = 'progress-lang-chip';
        const flag = LANG_FLAGS[code] || '🌐';
        const name = langNames[code] || code.toUpperCase();
        chip.textContent = `${flag} ${name}`;
        statsLanguagesEl.appendChild(chip);
    });
}

export function renderProgressStats() {
    const statsTotalSentencesEl = dom('stats-total-sentences');
    if (!statsTotalSentencesEl) return;

    statsTotalSentencesEl.textContent = String(state.progressStats.sentencesLearned || 0);
    renderProgressLanguages();

    const quizTotal = Math.max(0, Number(state.progressStats.quiz?.total) || 0);
    const quizCorrect = Math.max(0, Number(state.progressStats.quiz?.correct) || 0);
    const statsQuizAccuracyEl = dom('stats-quiz-accuracy');
    if (quizTotal > 0) {
        const accuracy = Math.round((quizCorrect / quizTotal) * 100);
        statsQuizAccuracyEl.textContent = `${accuracy}% (${quizCorrect}/${quizTotal})`;
    } else {
        statsQuizAccuracyEl.textContent = 'No quizzes taken yet';
    }

    const streak = Math.max(0, Number(state.progressStats.streak) || 0);
    dom('stats-streak').textContent = `${streak} ${streak === 1 ? 'day' : 'days'}`;

    const learningSince = formatDateLabel(state.progressStats.firstActivityDate);
    dom('stats-learning-since').textContent = learningSince || 'Not started yet';

    const srsDeckEl = dom('stats-srs-deck');
    const srsDueEl = dom('stats-srs-due');
    const srsMasteredEl = dom('stats-srs-mastered');
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
    if (!state.progressStats.firstActivityDate) state.progressStats.firstActivityDate = today;
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

// --- TTS / Speech ---

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
        utterance.onend = () => { btn.classList.remove('speaking'); if (label) label.textContent = 'Listen'; };
        utterance.onerror = () => { btn.classList.remove('speaking'); if (label) label.textContent = 'Listen'; };
    }
    speechSynthesis.speak(utterance);
}

// Pre-load voices
export function initSpeechSynthesis() {
    if (window.speechSynthesis) {
        speechSynthesis.getVoices();
        speechSynthesis.onvoiceschanged = () => speechSynthesis.getVoices();
    }
}

// --- Loading tips ---

export function setRandomLoadingTip() {
    const langSelect = dom('lang');
    const selectedLang = langSelect.value;
    const langName = langSelect.options[langSelect.selectedIndex]?.textContent || 'this language';
    const tips = LANGUAGE_TIPS[selectedLang] || LANGUAGE_TIPS.default;
    const randomTip = tips[Math.floor(Math.random() * tips.length)];
    dom('loading-tip').textContent = `${langName} tip: ${randomTip}`;
}

// --- Compare results ---

export function closeCompareResults() {
    const compareResultsEl = dom('compare-results');
    compareResultsEl.classList.add('hidden');
    compareResultsEl.innerHTML = '';
}

export function renderCompareResults(data) {
    const compareResultsEl = dom('compare-results');
    const sentenceInput = dom('sentence');
    const results = Array.isArray(data.results) ? data.results : [];
    const originalSentence = data.sentence || sentenceInput.value.trim();
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

    compareResultsEl.innerHTML = `
        <div class="compare-results-head">
            <div class="compare-results-label">Comparison mode</div>
            <button type="button" class="compare-close-btn" id="compare-close-btn">✕ Close</button>
        </div>
        <div class="compare-results-source">"${originalSentence}"</div>
        ${results.length ? `<div class="compare-grid">${cardsHTML}</div>` : '<div class="compare-empty">No comparison results returned.</div>'}
    `;
    const closeBtn = document.getElementById('compare-close-btn');
    if (closeBtn) closeBtn.addEventListener('click', closeCompareResults);
    compareResultsEl.classList.remove('hidden');
    compareResultsEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// --- Word chip detail handler ---

export async function handleWordChipClick(chip, wordData, fullData, reqCtx) {
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
    detailDiv.innerHTML = '<div class="word-detail-loading">Loading details...</div>';
    chip.appendChild(detailDiv);

    try {
        const resp = await fetch('/api/word-detail', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-App-Password': state.appPassword },
            body: JSON.stringify({
                word: wordData.word,
                meaning: wordData.meaning,
                target_language: reqCtx.target_language,
                sentence_context: fullData.translation
            })
        });
        if (!resp.ok) throw new Error(await friendlyError(resp));
        const detail = await resp.json();

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
            detail.conjugations.forEach(c => { html += `<span class="conjugation-tag">${c.form} <span class="conj-label">${c.label}</span></span>`; });
            html += '</div></div>';
        }
        if (detail.related && detail.related.length) {
            html += '<div class="word-detail-section"><div class="word-detail-label">Related</div><div class="word-detail-related">';
            detail.related.forEach(r => { html += `<span class="related-word-tag" title="${r.meaning}">${r.word} — ${r.meaning}</span>`; });
            html += '</div></div>';
        }
        detailDiv.innerHTML = html || '<div class="word-detail-loading">No additional details available.</div>';
    } catch (err) {
        console.error(err);
        detailDiv.innerHTML = '<div class="word-detail-loading">Failed to load details.</div>';
    }
}

// --- Main result rendering ---

export function renderResult(data, original, reqCtx) {
    const langSelect = dom('lang');
    const resultsEl = dom('results');
    const card = document.createElement('div');
    card.className = 'result-card';

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
            <div class="result-head">
                <div class="result-translation">${data.translation}</div>
                <button type="button" class="speak-btn" aria-label="Listen to pronunciation" data-lang="${langSelect.value}">
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
                <button type="button" class="share-btn" aria-label="Share link" data-sentence="${original.replace(/"/g, '&quot;')}" data-lang="${reqCtx.target_language || langSelect.value}">
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
            <div class="result-pronunciation">${data.pronunciation}</div>
            <div class="result-formality">${data.formality}</div>
            ${data.sentence_difficulty ? `<div class="result-difficulty result-difficulty--${data.sentence_difficulty.level}" title="${(data.sentence_difficulty.factors || []).join(', ')}">${data.sentence_difficulty.level === 'beginner' ? '🟢' : data.sentence_difficulty.level === 'intermediate' ? '🟡' : '🔴'} ${data.sentence_difficulty.level}</div>` : ''}
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

    // Word chip click handlers
    card.querySelectorAll('.word-chip').forEach((chip, idx) => {
        const wordData = data.breakdown[idx];
        const chipHandler = () => {
            handleWordChipClick(chip, wordData, data, reqCtx);
            chip.setAttribute('aria-expanded', String(chip.classList.contains('expanded')));
        };
        chip.addEventListener('click', chipHandler);
        chip.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); chipHandler(); } });
    });

    // Speak button
    const speakBtn = card.querySelector('.speak-btn');
    if (speakBtn) speakBtn.addEventListener('click', () => speakTranslation(data.translation, speakBtn.dataset.lang, speakBtn));

    // Copy button
    const copyBtn = card.querySelector('.copy-btn');
    const copyLabelEl = card.querySelector('.copy-label');
    copyBtn.addEventListener('click', async () => {
        const copied = await copyTextToClipboard(data.translation);
        copyLabelEl.textContent = copied ? 'Copied' : 'Failed';
        if (copied) copyBtn.classList.add('copied');
        setTimeout(() => { copyLabelEl.textContent = 'Copy'; copyBtn.classList.remove('copied'); }, 1200);
    });

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
                try { await navigator.share({ title: 'Learn: ' + s, url: url }); } catch(e) { /* cancelled */ }
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
    shareUrl.searchParams.set('t', reqCtx.target_language || langSelect.value);
    history.replaceState(null, '', shareUrl.toString());

    // Fast segment: load jieba/cedict breakdown immediately
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
                        target_language: reqCtx.target_language || langSelect.value,
                    })
                });
                if (!segResp.ok) throw new Error('Failed');
                if (myGeneration !== state.learnGeneration) return;
                const seg = await segResp.json();
                const segWords = seg.breakdown || [];
                if (segWords.length === 0) { segmentChips.innerHTML = '<div class="word-detail-loading">No segmentation available.</div>'; return; }
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
                    const chipHandler = () => handleWordChipClick(chip, wordData, data, reqCtx);
                    chip.addEventListener('click', chipHandler);
                    chip.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); chipHandler(); } });
                });
            } catch (err) {
                segmentChips.innerHTML = '<div class="word-detail-loading">Segmentation unavailable.</div>';
            }
        })();
    }

    // Lazy-load full grammar notes
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
                        sentence: original, translation: data.translation,
                        target_language: reqCtx.target_language || langSelect.value,
                        input_language: reqCtx.input_language || state.selectedInputLang,
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
                    const chipHandler = () => handleWordChipClick(chip, wordData, data, reqCtx);
                    chip.addEventListener('click', chipHandler);
                    chip.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); chipHandler(); } });
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
                        target_language: reqCtx.target_language || langSelect.value,
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
    ctxToggle.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleCtx(); } });

    // Prepend new result
    if (resultsEl.children.length > 0) {
        const divider = document.createElement('div');
        divider.className = 'history-divider';
        resultsEl.insertBefore(divider, resultsEl.firstChild);
    }
    resultsEl.insertBefore(card, resultsEl.firstChild);
    requestAnimationFrame(() => card.scrollIntoView({ behavior: 'smooth', block: 'start' }));
}

// --- Theme ---

export function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    const icon = theme === 'light' ? '☀️' : '🌙';
    const label = theme === 'light' ? 'Dark Mode' : 'Light Mode';
    const toggleBtn = dom('theme-toggle');
    const menuIcon = dom('menu-theme-icon');
    const menuLabel = dom('menu-theme-label');
    if (toggleBtn) toggleBtn.textContent = icon;
    if (menuIcon) menuIcon.textContent = icon;
    if (menuLabel) menuLabel.textContent = label;
}

export function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'dark';
    const next = current === 'dark' ? 'light' : 'dark';
    localStorage.setItem('sentsei-theme', next);
    applyTheme(next);
}

export function initTheme() {
    const saved = localStorage.getItem('sentsei-theme') || 'dark';
    applyTheme(saved);
    const toggleBtn = dom('theme-toggle');
    if (toggleBtn) toggleBtn.addEventListener('click', toggleTheme);
}
