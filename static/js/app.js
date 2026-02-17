// Main entry point — imports all modules and wires everything together
import { state, DOM, LANG_FLAGS, KEYS, HISTORY_LIMIT, hooks, LEARN_TIMEOUT_MS, MAX_AUTO_RETRIES, AUTO_RETRY_DELAY_MS, DAY_MS } from './state.js';
import {
    ensurePassword, openPasswordModal, closePasswordModal, lockApp, unlockApp,
    showPasswordError, hidePasswordError, syncModalOpenState,
    copyTextToClipboard, friendlyError, syncToServer, loadFromServer
} from './api.js';
import {
    loadProgressStats, saveProgressStats, renderProgressStats, persistProgressAndRefresh,
    recordLearnProgress, loadQuizStats, saveQuizStats, todayDateKey, addProgressLanguage,
    getLanguageNamesMap, openStatsModal, closeStatsModal,
    startLoadingTimer, stopLoadingTimer, showError, hideError, setRandomLoadingTip,
    speakTranslation, applyTheme, toggleTheme, initToggle, applyRomanization,
    renderResult, renderCompareResults, closeCompareResults, escapeHtml, filterResultsByLanguage
} from './ui.js?v=20260217';
import {
    loadSRSDeck, saveSRSDeck, addToSRS, getDueItems, updateSRSItem,
    updateReviewBadge, formatTimeUntil, enterReviewMode, exitReviewMode,
    toggleReviewMode, loadReviewQuestion, setSRSDeps
} from './srs.js';
import {
    loadQuizQuestion, checkQuizAnswer, enterQuizMode, exitQuizMode,
    toggleQuizMode, renderQuizScore, updateProgressStats
} from './quiz.js';
import {
    loadRichHistory, saveRichHistory, loadSentenceHistory,
    addToRichHistory, saveSentenceToHistory, renderSentenceHistory,
    toggleHistoryPanel, openHistoryPanel, closeHistoryPanel,
    updateHistoryBadge, renderHistoryPanel,
    exportHistoryAsAnki, copyAllHistoryToClipboard, setHistoryDeps,
    setHistoryFilterLang, normalizeSentenceHistoryEntries
} from './history.js';
import { initShortcuts, setShortcutDeps } from './shortcuts.js';

// === Populate DOM refs ===
function initDOM() {
    DOM.langSelect = document.getElementById('lang');
    DOM.langPills = document.getElementById('lang-pills');
    DOM.sentenceInput = document.getElementById('sentence');
    DOM.learnBtn = document.getElementById('learn-btn');
    DOM.surpriseBtn = document.getElementById('surprise-btn');
    DOM.compareBtn = document.getElementById('compare-btn');
    DOM.loading = document.getElementById('loading');
    DOM.loadingTip = document.getElementById('loading-tip');
    DOM.loadingMessage = document.getElementById('loading-message');
    DOM.loadingElapsed = document.getElementById('loading-elapsed');
    DOM.loadingCancel = document.getElementById('loading-cancel');
    DOM.compareResults = document.getElementById('compare-results');
    DOM.results = document.getElementById('results');
    DOM.sentenceHistoryWrap = document.getElementById('sentence-history-wrap');
    DOM.sentenceHistory = document.getElementById('sentence-history');
    DOM.passwordModal = document.getElementById('password-modal');
    DOM.passwordForm = document.getElementById('password-form');
    DOM.passwordInput = document.getElementById('password-input');
    DOM.passwordError = document.getElementById('password-error');
    DOM.statsToggle = document.getElementById('stats-toggle');
    DOM.statsModal = document.getElementById('stats-modal');
    DOM.statsModalClose = document.getElementById('stats-modal-close');
    DOM.statsTotalSentences = document.getElementById('stats-total-sentences');
    DOM.statsLanguages = document.getElementById('stats-languages');
    DOM.statsQuizAccuracy = document.getElementById('stats-quiz-accuracy');
    DOM.statsStreak = document.getElementById('stats-streak');
    DOM.statsLearningSince = document.getElementById('stats-learning-since');
    DOM.genderPills = document.getElementById('gender-pills');
    DOM.formalityPills = document.getElementById('formality-pills');
    DOM.romanizationToggle = document.getElementById('romanization-toggle');
    DOM.inputLangPills = document.getElementById('input-lang-pills');
    DOM.storiesToggle = document.getElementById('stories-toggle');
    DOM.storiesBadge = document.getElementById('stories-badge');
    DOM.storiesPanel = document.getElementById('stories-panel');
    DOM.storiesOverlay = document.getElementById('stories-overlay');
    DOM.storiesPanelClose = document.getElementById('stories-panel-close');
    DOM.storiesFilter = document.getElementById('stories-filter');
    DOM.storiesList = document.getElementById('stories-list');
    DOM.storiesBrowser = document.getElementById('stories-browser');
    DOM.storyReader = document.getElementById('story-reader');
    DOM.storyBackBtn = document.getElementById('story-back-btn');
    DOM.storyTitle = document.getElementById('story-title');
    DOM.storySource = document.getElementById('story-source');
    DOM.storySentence = document.getElementById('story-sentence');
    DOM.storyProgress = document.getElementById('story-progress');
    DOM.storyPrevBtn = document.getElementById('story-prev-btn');
    DOM.storyNextBtn = document.getElementById('story-next-btn');
    DOM.historyToggle = document.getElementById('history-toggle');
    DOM.historyBadge = document.getElementById('history-badge');
    DOM.historyPanel = document.getElementById('history-panel');
    DOM.historyLangFilter = document.getElementById('history-lang-filter');
    DOM.historyPanelList = document.getElementById('history-panel-list');
    DOM.historyOverlay = document.getElementById('history-overlay');
    DOM.historyClear = document.getElementById('history-clear-btn');
    DOM.historyExportAnki = document.getElementById('history-export-anki-btn');
    DOM.historyCopyAll = document.getElementById('history-copy-all-btn');
    DOM.historyPanelClose = document.getElementById('history-panel-close');
    DOM.quizToggle = document.getElementById('quiz-toggle');
    DOM.quizArea = document.getElementById('quiz-area');
    DOM.quizMeta = document.getElementById('quiz-meta');
    DOM.quizScore = document.getElementById('quiz-score');
    DOM.quizSentence = document.getElementById('quiz-sentence');
    DOM.quizPronunciation = document.getElementById('quiz-pronunciation');
    DOM.quizSource = document.getElementById('quiz-source');
    DOM.quizHint = document.getElementById('quiz-hint');
    DOM.quizAnswerInput = document.getElementById('quiz-answer');
    DOM.quizCheck = document.getElementById('quiz-check-btn');
    DOM.quizResult = document.getElementById('quiz-result');
    DOM.quizNext = document.getElementById('quiz-next-btn');
    DOM.quizExit = document.getElementById('quiz-exit-btn');
    DOM.errorBanner = document.getElementById('error-banner');
    DOM.errorMessage = document.getElementById('error-message');
    DOM.retryBtn = document.getElementById('retry-btn');
}

// === Initialize state from localStorage ===
function initState() {
    state.sentenceHistory = loadSentenceHistory();
    state.richHistory = loadRichHistory();
    state.storyProgress = loadStoryProgress();
    state.srsDeck = loadSRSDeck();
    state.progressStats = loadProgressStats();
    state.quizStats = loadQuizStats();
}

// === Story progress ===
function loadStoryProgress() {
    try {
        const raw = localStorage.getItem(KEYS.STORY_PROGRESS) || '{}';
        const parsed = JSON.parse(raw);
        if (!parsed || typeof parsed !== 'object') return {};
        return parsed;
    } catch { return {}; }
}

function saveStoryProgress() {
    localStorage.setItem(KEYS.STORY_PROGRESS, JSON.stringify(state.storyProgress));
}

function getStoryProgress(storyId, sentenceCount) {
    const raw = Number(state.storyProgress[storyId] || 0);
    if (!Number.isFinite(raw) || raw < 0) return 0;
    if (!sentenceCount || sentenceCount < 1) return 0;
    return Math.min(raw, sentenceCount - 1);
}

function setStoryProgress(storyId, index) {
    if (!storyId || !Number.isFinite(index) || index < 0) return;
    state.storyProgress[storyId] = index;
    saveStoryProgress();
}

// === Language selection ===
function selectLangPill(code) {
    DOM.langSelect.value = code;
    localStorage.setItem(KEYS.TARGET_LANG, code);
    DOM.langPills.querySelectorAll('.lang-pill').forEach(p => {
        const isActive = p.dataset.lang === code;
        p.classList.toggle('active', isActive);
        p.setAttribute('aria-checked', String(isActive));
    });
    filterResultsByLanguage(code);
    setHistoryFilterLang(code);
    renderHistoryPanel();
    renderSentenceHistory();
    updateStoriesBadge();
    if (state.storyPanelOpen) renderStoriesBrowser();
}

async function loadLanguages() {
    if (state.languagesLoaded) return;
    const langs = await fetch('/api/languages').then(r => r.json());
    DOM.langPills.innerHTML = '';
    for (const [code, name] of Object.entries(langs)) {
        const opt = document.createElement('option');
        opt.value = code;
        opt.textContent = name;
        DOM.langSelect.appendChild(opt);
        const pill = document.createElement('button');
        pill.type = 'button';
        pill.className = 'lang-pill';
        pill.dataset.lang = code;
        pill.setAttribute('role', 'radio');
        pill.setAttribute('aria-checked', 'false');
        const flag = LANG_FLAGS[code] || '🌐';
        pill.innerHTML = `<span class="flag">${flag}</span>${name}`;
        pill.addEventListener('click', () => selectLangPill(code));
        DOM.langPills.appendChild(pill);
    }
    const savedLang = localStorage.getItem(KEYS.TARGET_LANG);
    const defaultLang = (savedLang && Object.prototype.hasOwnProperty.call(langs, savedLang)) ? savedLang : (Object.prototype.hasOwnProperty.call(langs, 'zh') ? 'zh' : Object.keys(langs)[0]);
    if (defaultLang) selectLangPill(defaultLang);
    state.languagesLoaded = true;
    renderHistoryPanel();
    renderProgressStats();
    // Post-hook: load stories
    await loadStories();
}

// === Speculative Typing ===
function getSpeculativeKey() {
    const sentence = DOM.sentenceInput.value.trim();
    if (!sentence || sentence.length < 3) return null;
    return `${sentence}|${DOM.langSelect.value}|${state.selectedInputLang}|${state.selectedGender}|${state.selectedFormality}`;
}

function showSpeculativeIndicator() {
    let indicator = document.getElementById('speculative-indicator');
    if (!indicator) {
        indicator = document.createElement('div');
        indicator.id = 'speculative-indicator';
        indicator.style.cssText = 'font-size:0.72rem;color:var(--accent);margin-top:0.4rem;opacity:0.8;display:flex;align-items:center;gap:0.35rem;';
        indicator.innerHTML = '<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--accent);animation:specPulse 1.2s ease-in-out infinite;"></span> Preparing translation...';
        const inputArea = document.querySelector('.sentence-input');
        inputArea.parentNode.insertBefore(indicator, inputArea.nextSibling);
    }
    indicator.style.display = 'flex';
}

function hideSpeculativeIndicator() {
    const indicator = document.getElementById('speculative-indicator');
    if (indicator) indicator.style.display = 'none';
}

function cancelSpeculative() {
    if (state.speculativeTimer) { clearTimeout(state.speculativeTimer); state.speculativeTimer = null; }
    if (state.speculativeController) { state.speculativeController.abort(); state.speculativeController = null; }
    state.speculativePending = false;
    hideSpeculativeIndicator();
}

async function startSpeculative() {
    const key = getSpeculativeKey();
    if (!key || state.appPassword !== KEYS.APP_PASSWORD) return;
    if (state.speculativeCache[key]) return;

    state.speculativePending = true;
    state.speculativeController = new AbortController();
    showSpeculativeIndicator();

    const sentence = DOM.sentenceInput.value.trim();
    try {
        const resp = await fetch('/api/learn', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-App-Password': state.appPassword },
            body: JSON.stringify({
                sentence,
                target_language: DOM.langSelect.value,
                input_language: state.selectedInputLang,
                speaker_gender: state.selectedGender,
                speaker_formality: state.selectedFormality,
            }),
            signal: state.speculativeController.signal,
        });
        if (resp.ok) {
            const data = await resp.json();
            state.speculativeCache[key] = { data, sentence };
            const indicator = document.getElementById('speculative-indicator');
            if (indicator && DOM.sentenceInput.value.trim() === sentence) {
                indicator.innerHTML = '<span style="color:var(--easy);">✓</span> Ready — press Learn';
                setTimeout(() => hideSpeculativeIndicator(), 3000);
            }
        }
    } catch (e) {
        // aborted or error
    } finally {
        state.speculativePending = false;
        if (!state.speculativeCache[getSpeculativeKey()]) hideSpeculativeIndicator();
    }
}

// === Multi-sentence detection ===
function _hasMultipleSentences(text) {
    const parts = text.split(/(?<=[.!?。！？])\s*/).filter(s => s.trim());
    return parts.length > 1;
}

// === Learn ===
async function learn() {
    if (!ensurePassword()) return;

    const sentence = DOM.sentenceInput.value.trim();
    if (!sentence) return;
    state.learnGeneration++;
    state.lastLearnSentence = sentence;
    state.lastActionType = 'learn';
    hideError();

    // Check speculative cache
    const specKey = getSpeculativeKey();
    if (specKey && state.speculativeCache[specKey]) {
        const cached = state.speculativeCache[specKey];
        delete state.speculativeCache[specKey];
        cancelSpeculative();
        const reqCtx = { target_language: DOM.langSelect.value, input_language: state.selectedInputLang, sentence: cached.sentence };
        renderResult(cached.data, cached.sentence, reqCtx);
        saveSentenceToHistory(cached.sentence, reqCtx.target_language);
        addToRichHistory(cached.sentence, cached.data.translation, DOM.langSelect.value, cached.data.pronunciation);
        recordLearnProgress(DOM.langSelect.value, 1);
        DOM.sentenceInput.value = '';
        DOM.sentenceInput.style.height = 'auto';
        return;
    }
    cancelSpeculative();

    if (state._autoRetryCount === 0 || !state.lastLearnSentence || state.lastLearnSentence !== sentence) {
        state._autoRetryCount = 0;
    }

    DOM.learnBtn.disabled = true;
    if (DOM.compareBtn) DOM.compareBtn.disabled = true;
    setRandomLoadingTip();
    DOM.loading.classList.remove('hidden');
    startLoadingTimer();

    const isMulti = _hasMultipleSentences(sentence);
    if (isMulti) {
        DOM.loadingMessage.textContent = 'Translating multiple sentences...';
    } else {
        DOM.loadingMessage.textContent = 'Translating...';
    }

    state.currentAbortController = new AbortController();
    const timeoutMs = isMulti ? Math.min(sentence.split(/(?<=[.!?。！？])\s*/).filter(s => s.trim()).length, 10) * 120000 : LEARN_TIMEOUT_MS;
    const timeoutId = setTimeout(() => state.currentAbortController.abort(), timeoutMs);

    try {
        if (isMulti) {
            const resp = await fetch('/api/learn-multi', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-App-Password': state.appPassword },
                body: JSON.stringify({
                    sentences: sentence,
                    target_language: DOM.langSelect.value, input_language: state.selectedInputLang,
                    speaker_gender: state.selectedGender, speaker_formality: state.selectedFormality
                }),
                signal: state.currentAbortController.signal
            });
            clearTimeout(timeoutId);
            if (resp.status === 401) {
                localStorage.removeItem(KEYS.PASSWORD_STORAGE);
                state.appPassword = '';
                openPasswordModal('Session expired. Enter password again.');
                throw new Error('Unauthorized');
            }
            if (!resp.ok) throw new Error(await friendlyError(resp));
            const data = await resp.json();
            const reqCtx = { target_language: DOM.langSelect.value, input_language: state.selectedInputLang, sentence: sentence };
            const successfulResults = Array.isArray(data.results) ? data.results.filter(item => item && item.result) : [];
            successfulResults.forEach(item => {
                renderResult(item.result, item.sentence, { ...reqCtx, sentence: item.sentence });
            });
            saveSentenceToHistory(sentence, reqCtx.target_language);
            if (successfulResults.length) {
                const first = successfulResults[0];
                addToRichHistory(sentence, first.result.translation, DOM.langSelect.value, first.result.pronunciation);
            }
            recordLearnProgress(DOM.langSelect.value, successfulResults.length);
            DOM.sentenceInput.value = '';
            DOM.sentenceInput.style.height = 'auto';
        } else {
            const reqBody = {
                sentence: sentence,
                target_language: DOM.langSelect.value, input_language: state.selectedInputLang,
                speaker_gender: state.selectedGender, speaker_formality: state.selectedFormality
            };
            const resp = await fetch('/api/learn-fast', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-App-Password': state.appPassword },
                body: JSON.stringify(reqBody),
                signal: state.currentAbortController.signal
            });
            clearTimeout(timeoutId);
            if (resp.status === 401) {
                localStorage.removeItem(KEYS.PASSWORD_STORAGE);
                state.appPassword = '';
                openPasswordModal('Session expired. Enter password again.');
                throw new Error('Unauthorized');
            }
            if (!resp.ok) throw new Error(await friendlyError(resp));
            const data = await resp.json();
            const reqCtx = { target_language: DOM.langSelect.value, input_language: state.selectedInputLang, sentence: sentence };
            renderResult(data, sentence, reqCtx);
            saveSentenceToHistory(sentence, reqCtx.target_language);
            addToRichHistory(sentence, data.translation, DOM.langSelect.value, data.pronunciation);
            recordLearnProgress(DOM.langSelect.value, 1);
            DOM.sentenceInput.value = '';
            DOM.sentenceInput.style.height = 'auto';
        }
    } catch (err) {
        clearTimeout(timeoutId);
        console.error(err);
        if (err.message === '__AUTO_RETRY_502__' && state._autoRetryCount < MAX_AUTO_RETRIES) {
            state._autoRetryCount++;
            DOM.loadingMessage.textContent = `Translation engine warming up... retry ${state._autoRetryCount}/${MAX_AUTO_RETRIES}`;
            DOM.loading.classList.remove('hidden');
            await new Promise(r => setTimeout(r, AUTO_RETRY_DELAY_MS));
            if (!DOM.sentenceInput.value.trim() && state.lastLearnSentence) {
                DOM.sentenceInput.value = state.lastLearnSentence;
            }
            learn();
            return;
        }
        state._autoRetryCount = 0;
        if (err.name === 'AbortError') {
            showError('Request timed out — the model might be busy. Tap retry.');
        } else if (err.message === 'Unauthorized') {
            // already handled
        } else if (err.message === '__AUTO_RETRY_502__') {
            showError('Translation engine is unreachable after multiple retries. Please check if Ollama is running.');
        } else if (err.message && err.message !== 'API error') {
            showError(err.message);
        } else {
            showError('Something went wrong. Tap retry to try again.');
        }
    } finally {
        stopLoadingTimer();
        state.currentAbortController = null;
        if (state.appPassword === KEYS.APP_PASSWORD) {
            DOM.learnBtn.disabled = false;
            if (DOM.compareBtn) DOM.compareBtn.disabled = false;
        } else {
            lockApp();
        }
        DOM.loading.classList.add('hidden');
    }
}

// === Compare ===
async function compareSentence() {
    if (!ensurePassword()) return;
    const sentence = DOM.sentenceInput.value.trim();
    if (!sentence) return;
    state.lastLearnSentence = sentence;
    state.lastActionType = 'compare';
    hideError();
    DOM.learnBtn.disabled = true;
    if (DOM.compareBtn) DOM.compareBtn.disabled = true;
    setRandomLoadingTip();
    DOM.loading.classList.remove('hidden');
    DOM.loadingMessage.textContent = 'Comparing across languages...';
    startLoadingTimer();
    state.currentAbortController = new AbortController();
    const timeoutId = setTimeout(() => state.currentAbortController.abort(), LEARN_TIMEOUT_MS);
    try {
        const resp = await fetch('/api/compare', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-App-Password': state.appPassword },
            body: JSON.stringify({
                sentence: sentence,
                input_language: state.selectedInputLang,
                speaker_gender: state.selectedGender,
                speaker_formality: state.selectedFormality
            }),
            signal: state.currentAbortController.signal
        });
        clearTimeout(timeoutId);
        if (resp.status === 401) {
            localStorage.removeItem(KEYS.PASSWORD_STORAGE);
            state.appPassword = '';
            openPasswordModal('Session expired. Enter password again.');
            throw new Error('Unauthorized');
        }
        if (!resp.ok) throw new Error(await friendlyError(resp));
        const data = await resp.json();
        renderCompareResults(data);
    } catch (err) {
        clearTimeout(timeoutId);
        console.error(err);
        if (err.name === 'AbortError') {
            showError('Comparison timed out — tap compare again.');
        } else if (err.message === 'Unauthorized') {
            // handled
        } else if (err.message && err.message !== 'API error') {
            showError(err.message);
        } else {
            showError('Could not compare this sentence right now.');
        }
    } finally {
        stopLoadingTimer();
        state.currentAbortController = null;
        if (state.appPassword === KEYS.APP_PASSWORD) {
            DOM.learnBtn.disabled = false;
            if (DOM.compareBtn) DOM.compareBtn.disabled = false;
        } else {
            lockApp();
        }
        DOM.loading.classList.add('hidden');
    }
}

// === Surprise Me ===
async function surpriseMe() {
    if (!ensurePassword()) return;
    DOM.surpriseBtn.disabled = true;
    try {
        const lang = DOM.langSelect.value;
        const inputLang = state.selectedInputLang === 'auto' ? 'en' : state.selectedInputLang;
        const resp = await fetch(`/api/surprise?lang=${encodeURIComponent(lang)}&input_lang=${encodeURIComponent(inputLang)}`);
        if (!resp.ok) throw new Error(await friendlyError(resp));
        const data = await resp.json();
        DOM.sentenceInput.value = data.sentence;
        DOM.sentenceInput.style.height = 'auto';
        DOM.sentenceInput.style.height = DOM.sentenceInput.scrollHeight + 'px';
        if (data.precomputed && data.result) {
            cancelSpeculative();
            const reqCtx = { target_language: lang, input_language: inputLang, sentence: data.sentence };
            renderResult(data.result, data.sentence, reqCtx);
            saveSentenceToHistory(data.sentence, lang);
            addToRichHistory(data.sentence, data.result.translation, lang, data.result.pronunciation);
            recordLearnProgress(lang, 1);
            DOM.sentenceInput.value = '';
            DOM.sentenceInput.style.height = 'auto';
        } else {
            await learn();
        }
    } catch (err) {
        console.error(err);
        alert('Could not fetch a surprise sentence.');
    } finally {
        DOM.surpriseBtn.disabled = false;
    }
}

// === Stories ===
function updateStoriesBadge() {
    if (!DOM.storiesBadge) return;
    const selectedLang = DOM.langSelect.value;
    const count = selectedLang ? state.stories.filter(s => s.language === selectedLang).length : state.stories.length;
    DOM.storiesBadge.textContent = count;
}

function toggleStoriesPanel() {
    state.storyPanelOpen = !state.storyPanelOpen;
    DOM.storiesPanel.classList.toggle('open', state.storyPanelOpen);
    DOM.storiesOverlay.classList.toggle('open', state.storyPanelOpen);
    if (state.storyPanelOpen) renderStoriesBrowser();
}

function closeStoriesPanel() {
    state.storyPanelOpen = false;
    DOM.storiesPanel.classList.remove('open');
    DOM.storiesOverlay.classList.remove('open');
}

async function loadStories() {
    try {
        const resp = await fetch('/api/stories');
        if (!resp.ok) return;
        state.stories = await resp.json();
        updateStoriesBadge();
    } catch (e) { console.error(e); }
}

function renderStoriesBrowser() {
    const selectedLang = DOM.langSelect.value;
    const langName = DOM.langSelect.options[DOM.langSelect.selectedIndex]?.textContent || selectedLang;
    const flag = LANG_FLAGS[selectedLang] || '🌐';
    DOM.storiesFilter.textContent = `${flag} ${langName} stories`;
    const filtered = state.stories.filter(s => s.language === selectedLang);
    if (filtered.length === 0) {
        DOM.storiesList.innerHTML = '<div class="stories-empty">No stories for this language yet.</div>';
        return;
    }
    DOM.storiesList.innerHTML = filtered.map(s => {
        const prog = getStoryProgress(s.id, s.sentence_count);
        const progText = `${prog + 1}/${s.sentence_count}`;
        return `<button class="story-list-item" data-story-id="${s.id}">
            <div class="story-list-title">${s.title}</div>
            <div class="story-list-meta">
                <span>${s.source}</span>
                <span class="story-list-progress">${progText}</span>
            </div>
        </button>`;
    }).join('');
    DOM.storiesList.querySelectorAll('.story-list-item').forEach(btn => {
        btn.addEventListener('click', () => openStoryReader(btn.dataset.storyId));
    });
    DOM.storiesBrowser.classList.remove('hidden');
    DOM.storyReader.classList.add('hidden');
}

async function openStoryReader(storyId) {
    let story = state.storyCache[storyId];
    if (!story) {
        try {
            const resp = await fetch(`/api/story/${encodeURIComponent(storyId)}`);
            if (!resp.ok) return;
            story = await resp.json();
            state.storyCache[storyId] = story;
        } catch (e) { console.error(e); return; }
    }
    state.activeStory = story;
    state.activeStoryIndex = getStoryProgress(storyId, story.sentences.length);
    DOM.storiesBrowser.classList.add('hidden');
    DOM.storyReader.classList.remove('hidden');
    renderStoryReader();
}

function renderStoryReader() {
    if (!state.activeStory) return;
    const total = state.activeStory.sentences.length;
    DOM.storyTitle.textContent = state.activeStory.title;
    DOM.storySource.textContent = state.activeStory.source;
    DOM.storySentence.textContent = state.activeStory.sentences[state.activeStoryIndex];
    DOM.storyProgress.textContent = `${state.activeStoryIndex + 1}/${total}`;
    DOM.storyPrevBtn.disabled = state.activeStoryIndex <= 0;
    DOM.storyNextBtn.disabled = state.activeStoryIndex >= total - 1;
}

// === Grammar Panel ===
function toggleGrammarPanel() {
    state.grammarPanelOpen = !state.grammarPanelOpen;
    const grammarPanelEl = document.getElementById('grammar-panel');
    const grammarOverlayEl = document.getElementById('grammar-overlay');
    grammarPanelEl.classList.toggle('open', state.grammarPanelOpen);
    grammarOverlayEl.classList.toggle('open', state.grammarPanelOpen);
    if (state.grammarPanelOpen) loadGrammarPatterns();
}

function closeGrammarPanel() {
    state.grammarPanelOpen = false;
    document.getElementById('grammar-panel').classList.remove('open');
    document.getElementById('grammar-overlay').classList.remove('open');
}

async function loadGrammarPatterns() {
    try {
        const url = state.grammarFilterLang ? `/api/grammar-patterns?lang=${state.grammarFilterLang}` : '/api/grammar-patterns';
        const resp = await fetch(url, { headers: { 'x-app-password': KEYS.APP_PASSWORD } });
        if (!resp.ok) return;
        state.grammarPatterns = await resp.json();
        renderGrammarPatterns();
    } catch (e) { console.error('[grammar]', e); }
}

function renderGrammarPatterns() {
    const grammarFilterEl = document.getElementById('grammar-filter');
    const grammarPanelListEl = document.getElementById('grammar-panel-list');
    const langs = [...new Set(state.grammarPatterns.map(p => p.lang))];
    if (grammarFilterEl) {
        grammarFilterEl.innerHTML = `<button class="grammar-filter-pill ${!state.grammarFilterLang ? 'active' : ''}" data-lang="">All</button>` +
            langs.map(l => {
                const flag = LANG_FLAGS[l] || '🌐';
                return `<button class="grammar-filter-pill ${state.grammarFilterLang === l ? 'active' : ''}" data-lang="${l}">${flag} ${l}</button>`;
            }).join('');
        grammarFilterEl.querySelectorAll('.grammar-filter-pill').forEach(btn => {
            btn.addEventListener('click', () => {
                state.grammarFilterLang = btn.dataset.lang || null;
                loadGrammarPatterns();
            });
        });
    }
    if (!state.grammarPatterns.length) {
        grammarPanelListEl.innerHTML = '<div class="grammar-panel-empty">No grammar patterns yet. Translate some sentences to discover patterns!</div>';
        return;
    }
    grammarPanelListEl.innerHTML = state.grammarPatterns.map(p => `
        <div class="grammar-card" data-pattern-id="${p.id}">
            <div class="grammar-card-head">
                <span class="grammar-card-name">${escapeHtml(p.name)}</span>
                <span class="grammar-card-count">${p.count}× · ${p.example_count} examples</span>
            </div>
            <div class="grammar-card-explanation">${escapeHtml(p.explanation)}</div>
            <div class="grammar-card-examples" id="gp-examples-${p.id}"></div>
        </div>
    `).join('');
    grammarPanelListEl.querySelectorAll('.grammar-card').forEach(card => {
        card.addEventListener('click', async () => {
            const pid = card.dataset.patternId;
            if (card.classList.contains('expanded')) { card.classList.remove('expanded'); return; }
            try {
                const resp = await fetch(`/api/grammar-patterns/${pid}`, { headers: { 'x-app-password': KEYS.APP_PASSWORD } });
                if (!resp.ok) return;
                const detail = await resp.json();
                const exDiv = card.querySelector('.grammar-card-examples');
                exDiv.innerHTML = (detail.examples || []).map(ex => `
                    <div class="grammar-example" data-source="${escapeHtml(ex.source)}">
                        <div class="grammar-example-source">"${escapeHtml(ex.source)}"</div>
                        <div class="grammar-example-translation">→ ${escapeHtml(ex.translation)}</div>
                    </div>
                `).join('') || '<div style="color:var(--text-dim);font-size:0.78rem;">No examples yet.</div>';
                exDiv.querySelectorAll('.grammar-example').forEach(ex => {
                    ex.addEventListener('click', (e) => {
                        e.stopPropagation();
                        const src = ex.dataset.source;
                        if (src && DOM.sentenceInput) {
                            DOM.sentenceInput.value = src;
                            DOM.sentenceInput.dispatchEvent(new Event('input'));
                            closeGrammarPanel();
                            DOM.sentenceInput.focus();
                        }
                    });
                });
                card.classList.add('expanded');
            } catch (e) { console.error(e); }
        });
    });
}

// === Feedback ===
function initFeedback() {
    const btn = document.getElementById('feedback-btn');
    const modal = document.getElementById('feedback-modal');
    const text = document.getElementById('feedback-text');
    const send = document.getElementById('feedback-send');
    const cancel = document.getElementById('feedback-cancel');
    const status = document.getElementById('feedback-status');
    btn.addEventListener('click', () => { modal.classList.add('open'); text.focus(); });
    cancel.addEventListener('click', () => { modal.classList.remove('open'); });
    modal.addEventListener('click', (e) => { if (e.target === modal) modal.classList.remove('open'); });
    send.addEventListener('click', async () => {
        if (!text.value.trim()) return;
        send.disabled = true; send.textContent = 'Sending...';
        try {
            const pw = localStorage.getItem(KEYS.PASSWORD_STORAGE) || '';
            await fetch('/api/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-App-Password': pw },
                body: JSON.stringify({ message: text.value.trim() })
            });
            status.textContent = '✅ Thanks for your feedback!'; status.style.display = 'block';
            text.value = '';
            setTimeout(() => { modal.classList.remove('open'); status.style.display = 'none'; send.disabled = false; send.textContent = 'Send'; }, 1500);
        } catch(e) {
            status.textContent = '❌ Failed to send'; status.style.color = 'var(--hard)'; status.style.display = 'block';
            send.disabled = false; send.textContent = 'Send';
        }
    });
}

// === Auth ===
function initAuth() {
    const authModalEl = document.getElementById('auth-modal');
    const authFormEl = document.getElementById('auth-form');
    const authUsernameInput = document.getElementById('auth-username-input');
    const authPasswordInput = document.getElementById('auth-password-input');
    const authSubmitBtn = document.getElementById('auth-submit-btn');
    const authErrorEl = document.getElementById('auth-error');
    const authModalTitle = document.getElementById('auth-modal-title');
    const authSwitchBtn = document.getElementById('auth-switch-btn');
    const authSwitchText = document.getElementById('auth-switch-text');
    const authModalClose = document.getElementById('auth-modal-close');
    const authUserDisplay = document.getElementById('auth-user-display');
    const authUsernameEl = document.getElementById('auth-username');
    const authButtonsEl = document.getElementById('auth-buttons');
    const authLoginBtn = document.getElementById('auth-login-btn');
    const authRegisterBtn = document.getElementById('auth-register-btn');
    const authLogoutBtn = document.getElementById('auth-logout-btn');

    function setAuthMode(mode) {
        state.authMode = mode;
        if (mode === 'login') {
            authModalTitle.textContent = 'Log In';
            authSubmitBtn.textContent = 'Log In';
            authSwitchText.textContent = "Don't have an account?";
            authSwitchBtn.textContent = 'Sign up';
            authPasswordInput.autocomplete = 'current-password';
        } else {
            authModalTitle.textContent = 'Sign Up';
            authSubmitBtn.textContent = 'Create Account';
            authSwitchText.textContent = 'Already have an account?';
            authSwitchBtn.textContent = 'Log in';
            authPasswordInput.autocomplete = 'new-password';
        }
        authErrorEl.classList.add('hidden');
    }

    function openAuthModal(mode) {
        setAuthMode(mode || 'login');
        authUsernameInput.value = '';
        authPasswordInput.value = '';
        authModalEl.classList.remove('hidden');
        requestAnimationFrame(() => authUsernameInput.focus());
    }

    function closeAuthModal() {
        authModalEl.classList.add('hidden');
        authErrorEl.classList.add('hidden');
    }

    function updateAuthUI() {
        if (state.authToken && state.authUsername) {
            authUserDisplay.style.display = '';
            authUsernameEl.textContent = state.authUsername;
            authButtonsEl.style.display = 'none';
        } else {
            authUserDisplay.style.display = 'none';
            authButtonsEl.style.display = '';
        }
    }

    authLoginBtn.addEventListener('click', () => openAuthModal('login'));
    authRegisterBtn.addEventListener('click', () => openAuthModal('register'));
    authModalClose.addEventListener('click', closeAuthModal);
    authModalEl.addEventListener('click', (e) => { if (e.target === authModalEl) closeAuthModal(); });
    authSwitchBtn.addEventListener('click', () => setAuthMode(state.authMode === 'login' ? 'register' : 'login'));

    authLogoutBtn.addEventListener('click', async () => {
        try {
            await fetch('/api/auth/logout', {
                method: 'POST',
                headers: { 'Authorization': 'Bearer ' + state.authToken }
            });
        } catch(e) {}
        state.authToken = '';
        state.authUsername = '';
        localStorage.removeItem(KEYS.AUTH_TOKEN);
        localStorage.removeItem(KEYS.AUTH_USERNAME);
        updateAuthUI();
    });

    authFormEl.addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = authUsernameInput.value.trim();
        const password = authPasswordInput.value;
        if (!username || !password) return;

        authSubmitBtn.disabled = true;
        authErrorEl.classList.add('hidden');
        const endpoint = state.authMode === 'register' ? '/api/auth/register' : '/api/auth/login';

        try {
            const resp = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });
            if (!resp.ok) {
                const body = await resp.json().catch(() => ({}));
                throw new Error(body.detail || 'Failed');
            }
            const data = await resp.json();
            state.authToken = data.token;
            state.authUsername = data.username;
            localStorage.setItem(KEYS.AUTH_TOKEN, state.authToken);
            localStorage.setItem(KEYS.AUTH_USERNAME, state.authUsername);
            closeAuthModal();
            updateAuthUI();
            await pullAllFromServer();
        } catch(err) {
            authErrorEl.textContent = err.message;
            authErrorEl.classList.remove('hidden');
        } finally {
            authSubmitBtn.disabled = false;
        }
    });

    updateAuthUI();
    if (state.authToken) {
        fetch('/api/auth/me', { headers: { 'Authorization': 'Bearer ' + state.authToken } })
            .then(r => { if (!r.ok) throw new Error(); return r.json(); })
            .then(d => { state.authUsername = d.username; localStorage.setItem(KEYS.AUTH_USERNAME, d.username); updateAuthUI(); })
            .catch(() => {
                state.authToken = '';
                state.authUsername = '';
                localStorage.removeItem(KEYS.AUTH_TOKEN);
                localStorage.removeItem(KEYS.AUTH_USERNAME);
                updateAuthUI();
            });
    }
}

// === Data Sync ===
const SYNC_KEYS_MAP = {
    'rich_history': {
        get: () => state.richHistory,
        set: (d) => { state.richHistory = d || []; saveRichHistory(); renderHistoryPanel(); updateHistoryBadge(); }
    },
    'srs_deck': {
        get: () => state.srsDeck,
        set: (d) => { state.srsDeck = d || []; saveSRSDeck(); updateReviewBadge(); }
    },
    'progress': {
        get: () => state.progressStats,
        set: (d) => { if (d) { state.progressStats = d; saveProgressStats(); renderProgressStats(); } }
    },
    'history': {
        get: () => state.sentenceHistory,
        set: (d) => {
            state.sentenceHistory = normalizeSentenceHistoryEntries(d, localStorage.getItem(KEYS.TARGET_LANG) || '');
            localStorage.setItem(KEYS.SENTENCE_HISTORY, JSON.stringify(state.sentenceHistory));
            renderSentenceHistory();
        }
    },
};

async function pullAllFromServer() {
    if (!state.authToken) return;
    for (const [key, handler] of Object.entries(SYNC_KEYS_MAP)) {
        const serverData = await loadFromServer(key);
        if (serverData !== null && serverData !== undefined) {
            handler.set(serverData);
        } else {
            const localData = handler.get();
            if (localData && (Array.isArray(localData) ? localData.length > 0 : Object.keys(localData).length > 0)) {
                await syncToServer(key, localData);
            }
        }
    }
}

// === Hamburger Menu ===
function initSideMenu() {
    const hamburgerBtn = document.getElementById('hamburger-btn');
    const hamburgerBadge = document.getElementById('hamburger-badge');
    const sideMenuEl = document.getElementById('side-menu');
    const sideMenuOverlay = document.getElementById('side-menu-overlay');
    const sideMenuClose = document.getElementById('side-menu-close');
    const menuHistoryBadge = document.getElementById('menu-history-badge');

    function openSideMenu() {
        sideMenuEl.classList.add('open');
        sideMenuOverlay.classList.add('open');
        document.getElementById('menu-quiz').classList.toggle('active', state.quizMode);
    }
    function closeSideMenu() {
        sideMenuEl.classList.remove('open');
        sideMenuOverlay.classList.remove('open');
    }

    hamburgerBtn.addEventListener('click', openSideMenu);
    sideMenuOverlay.addEventListener('click', closeSideMenu);
    sideMenuClose.addEventListener('click', closeSideMenu);

    document.getElementById('menu-history').addEventListener('click', () => { closeSideMenu(); toggleHistoryPanel(); });
    document.getElementById('menu-quiz').addEventListener('click', () => { closeSideMenu(); toggleQuizMode(); });
    document.getElementById('menu-review').addEventListener('click', () => { closeSideMenu(); toggleReviewMode(); });
    document.getElementById('menu-stories').addEventListener('click', () => { closeSideMenu(); toggleStoriesPanel(); });
    document.getElementById('menu-stats').addEventListener('click', () => { closeSideMenu(); openStatsModal(); });
    document.getElementById('menu-grammar').addEventListener('click', () => { closeSideMenu(); toggleGrammarPanel(); });
    document.getElementById('menu-theme').addEventListener('click', () => { closeSideMenu(); toggleTheme(); });

    // Hook: update hamburger + menu badges when history badge updates
    hooks.afterUpdateHistoryBadge.push(() => {
        const count = state.richHistory.length;
        menuHistoryBadge.textContent = count;
        menuHistoryBadge.style.display = count > 0 ? '' : 'none';
        hamburgerBadge.textContent = count;
        hamburgerBadge.style.display = count > 0 ? '' : 'none';
    });

    // Expose for shortcuts
    return { closeSideMenu };
}

// === Onboarding ===
function initOnboarding() {
    const onboardingOverlay = document.getElementById('onboarding-overlay');

    function showOnboarding() {
        if (localStorage.getItem(KEYS.ONBOARDED)) return;
        if (state.richHistory.length > 0 || state.sentenceHistory.length > 0) {
            localStorage.setItem(KEYS.ONBOARDED, '1');
            return;
        }
        onboardingOverlay.classList.remove('hidden');
    }

    function dismissOnboarding() {
        onboardingOverlay.classList.add('hidden');
        localStorage.setItem(KEYS.ONBOARDED, '1');
    }

    document.querySelectorAll('.onboarding-suggestion').forEach(btn => {
        btn.addEventListener('click', () => {
            const sentence = btn.dataset.sentence;
            const lang = btn.dataset.lang;
            dismissOnboarding();
            const tryFill = () => {
                if (state.languagesLoaded) {
                    if (lang) selectLangPill(lang);
                    DOM.sentenceInput.value = sentence;
                    DOM.sentenceInput.style.height = 'auto';
                    DOM.sentenceInput.style.height = DOM.sentenceInput.scrollHeight + 'px';
                    learn();
                } else {
                    setTimeout(tryFill, 200);
                }
            };
            tryFill();
        });
    });

    document.getElementById('onboarding-skip').addEventListener('click', () => {
        dismissOnboarding();
        DOM.sentenceInput.focus();
    });

    if (state.appPassword === KEYS.APP_PASSWORD) {
        showOnboarding();
    }

    // Hook: show onboarding after password modal closes
    hooks.afterClosePasswordModal.push(() => {
        setTimeout(showOnboarding, 300);
    });
}

// === Sync hooks ===
function initSyncHooks() {
    hooks.afterSaveRichHistory.push(() => syncToServer('rich_history', state.richHistory));
    hooks.afterSaveSRSDeck.push(() => syncToServer('srs_deck', state.srsDeck));
    hooks.afterSaveProgressStats.push(() => syncToServer('progress', state.progressStats));
}

// === Main initialization ===
function init() {
    initDOM();
    initState();

    // Set dependency injections
    setSRSDeps({ ensurePassword });
    setHistoryDeps({ selectLangPill });

    // Init toggles
    initToggle(DOM.genderPills, state.selectedGender, KEYS.GENDER, v => state.selectedGender = v);
    initToggle(DOM.formalityPills, state.selectedFormality, KEYS.FORMALITY, v => state.selectedFormality = v);

    // Romanization
    DOM.romanizationToggle.addEventListener('click', () => {
        state.showRomanization = !state.showRomanization;
        localStorage.setItem(KEYS.ROMANIZATION, String(state.showRomanization));
        applyRomanization();
    });
    applyRomanization();

    // Input language
    DOM.inputLangPills.querySelectorAll('.lang-pill').forEach(p => {
        const isActive = p.dataset.lang === state.selectedInputLang;
        p.classList.toggle('active', isActive);
        p.setAttribute('role', 'radio');
        p.setAttribute('aria-checked', String(isActive));
        p.addEventListener('click', () => {
            DOM.inputLangPills.querySelectorAll('.lang-pill').forEach(q => {
                q.classList.remove('active');
                q.setAttribute('aria-checked', 'false');
            });
            p.classList.add('active');
            p.setAttribute('aria-checked', 'true');
            state.selectedInputLang = p.dataset.lang;
            localStorage.setItem(KEYS.INPUT_LANG, state.selectedInputLang);
        });
    });

    // Password form
    DOM.passwordForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        const entered = DOM.passwordInput.value.trim();
        if (entered !== KEYS.APP_PASSWORD) {
            showPasswordError('Incorrect password. Try again.');
            DOM.passwordInput.select();
            return;
        }
        state.appPassword = KEYS.APP_PASSWORD;
        localStorage.setItem(KEYS.PASSWORD_STORAGE, KEYS.APP_PASSWORD);
        closePasswordModal();
        hooks.afterClosePasswordModal.forEach(fn => fn());
        unlockApp();
        try { await loadLanguages(); } catch (err) { console.error(err); alert('Failed to load languages.'); }
    });

    // History events
    DOM.historyToggle.addEventListener('click', toggleHistoryPanel);
    DOM.historyOverlay.addEventListener('click', closeHistoryPanel);
    DOM.historyPanelClose.addEventListener('click', closeHistoryPanel);
    DOM.historyExportAnki.addEventListener('click', exportHistoryAsAnki);
    DOM.historyCopyAll.addEventListener('click', copyAllHistoryToClipboard);
    DOM.statsToggle.addEventListener('click', openStatsModal);
    DOM.statsModalClose.addEventListener('click', closeStatsModal);
    DOM.statsModal.addEventListener('click', (e) => { if (e.target === DOM.statsModal) closeStatsModal(); });
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !DOM.statsModal.classList.contains('hidden')) closeStatsModal();
    });
    DOM.historyClear.addEventListener('click', () => {
        if (confirm('Clear all history?')) {
            state.richHistory = [];
            state.sentenceHistory = [];
            saveRichHistory();
            localStorage.setItem(KEYS.SENTENCE_HISTORY, '[]');
            renderHistoryPanel();
            renderSentenceHistory();
            updateHistoryBadge();
        }
    });

    updateHistoryBadge();
    renderProgressStats();
    renderSentenceHistory();

    // Sentence input events
    DOM.sentenceInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = this.scrollHeight + 'px';
        cancelSpeculative();
        if (this.value.trim().length >= 3) {
            state.speculativeTimer = setTimeout(() => startSpeculative(), 1500);
        }
    });
    DOM.sentenceInput.addEventListener('compositionstart', () => { state.isComposing = true; cancelSpeculative(); });
    DOM.sentenceInput.addEventListener('compositionend', () => { state.isComposing = false; });
    DOM.sentenceInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey && !state.isComposing) {
            e.preventDefault();
            learn();
        }
    });

    // Loading cancel & retry
    DOM.loadingCancel.addEventListener('click', () => {
        if (state.currentAbortController) state.currentAbortController.abort();
    });
    DOM.retryBtn.addEventListener('click', () => {
        hideError();
        if (state.lastLearnSentence) {
            DOM.sentenceInput.value = state.lastLearnSentence;
            if (state.lastActionType === 'compare') compareSentence();
            else learn();
        }
    });

    // Stories
    DOM.storyPrevBtn.addEventListener('click', () => {
        if (!state.activeStory || state.activeStoryIndex <= 0) return;
        state.activeStoryIndex--;
        setStoryProgress(state.activeStory.id, state.activeStoryIndex);
        renderStoryReader();
    });
    DOM.storyNextBtn.addEventListener('click', () => {
        if (!state.activeStory || state.activeStoryIndex >= state.activeStory.sentences.length - 1) return;
        state.activeStoryIndex++;
        setStoryProgress(state.activeStory.id, state.activeStoryIndex);
        renderStoryReader();
    });
    DOM.storySentence.addEventListener('click', () => {
        if (!state.activeStory) return;
        const sentence = state.activeStory.sentences[state.activeStoryIndex];
        DOM.sentenceInput.value = sentence;
        DOM.sentenceInput.style.height = 'auto';
        DOM.sentenceInput.style.height = DOM.sentenceInput.scrollHeight + 'px';
        selectLangPill(state.activeStory.language);
        closeStoriesPanel();
        DOM.sentenceInput.focus();
    });
    DOM.storyBackBtn.addEventListener('click', () => {
        state.activeStory = null;
        renderStoriesBrowser();
    });
    DOM.storiesToggle.addEventListener('click', toggleStoriesPanel);
    DOM.storiesOverlay.addEventListener('click', closeStoriesPanel);
    DOM.storiesPanelClose.addEventListener('click', closeStoriesPanel);

    // Quiz
    if (DOM.quizToggle) DOM.quizToggle.addEventListener('click', toggleQuizMode);
    if (DOM.quizCheck) DOM.quizCheck.addEventListener('click', checkQuizAnswer);
    if (DOM.quizNext) DOM.quizNext.addEventListener('click', loadQuizQuestion);
    if (DOM.quizExit) DOM.quizExit.addEventListener('click', exitQuizMode);
    if (DOM.quizAnswerInput) DOM.quizAnswerInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.isComposing) { e.preventDefault(); checkQuizAnswer(); }
    });

    // Review
    const reviewToggleBtn = document.getElementById('review-toggle');
    const reviewNextBtn = document.getElementById('review-next-btn');
    const reviewExitBtn = document.getElementById('review-exit-btn');
    if (reviewToggleBtn) reviewToggleBtn.addEventListener('click', toggleReviewMode);
    if (reviewNextBtn) reviewNextBtn.addEventListener('click', loadReviewQuestion);
    if (reviewExitBtn) reviewExitBtn.addEventListener('click', exitReviewMode);
    updateReviewBadge();

    // Grammar panel close
    const grammarPanelCloseBtn = document.getElementById('grammar-panel-close');
    const grammarOverlayEl = document.getElementById('grammar-overlay');
    if (grammarPanelCloseBtn) grammarPanelCloseBtn.addEventListener('click', closeGrammarPanel);
    if (grammarOverlayEl) grammarOverlayEl.addEventListener('click', closeGrammarPanel);

    // Side menu
    const { closeSideMenu } = initSideMenu();

    // Shortcuts
    setShortcutDeps({ closeSideMenu, closeStoriesPanel, closeStatsModal, learn });
    initShortcuts();

    // Feedback
    initFeedback();

    // Theme
    const saved = localStorage.getItem(KEYS.THEME) || 'dark';
    applyTheme(saved);
    const themeToggleBtn = document.getElementById('theme-toggle');
    if (themeToggleBtn) themeToggleBtn.addEventListener('click', toggleTheme);

    // Auth
    initAuth();
    initSyncHooks();

    // Onboarding
    initOnboarding();

    // Pre-load voices
    if (window.speechSynthesis) {
        speechSynthesis.getVoices();
        speechSynthesis.onvoiceschanged = () => speechSynthesis.getVoices();
    }

    // Load languages (always, not gated by password)
    loadLanguages().then(() => {
        const urlParams = new URLSearchParams(window.location.search);
        const sharedSentence = urlParams.get('s');
        const sharedLang = urlParams.get('t');
        if (sharedSentence) {
            // Clear URL params so refresh doesn't re-run the sentence
            history.replaceState(null, '', '/');
            DOM.sentenceInput.value = sharedSentence;
            if (sharedLang && DOM.langSelect.querySelector(`option[value="${sharedLang}"]`)) {
                selectLangPill(sharedLang);
            }
            const tryAutoLearn = () => {
                if (ensurePassword()) {
                    learn();
                } else {
                    DOM.passwordForm.addEventListener('submit', function autoLearnAfterPw() {
                        DOM.passwordForm.removeEventListener('submit', autoLearnAfterPw);
                        setTimeout(() => learn(), 300);
                    });
                }
            };
            tryAutoLearn();
        }
    }).catch(err => {
        console.error(err);
        alert('Failed to load languages.');
    });

    if (ensurePassword()) unlockApp();

    // Service Worker
    if ('serviceWorker' in navigator) {
        window.addEventListener('load', () => {
            navigator.serviceWorker.register('/sw.js').then(reg => {
                console.log('SW registered, scope:', reg.scope);
            }).catch(err => {
                console.log('SW registration failed:', err);
            });
        });
    }

    // Expose globals for inline onclick handlers in HTML
    window.learn = learn;
    window.surpriseMe = surpriseMe;
    window.toggleHistoryPanel = toggleHistoryPanel;
    window.toggleQuizMode = toggleQuizMode;
    window.toggleReviewMode = toggleReviewMode;
    window.toggleStoriesPanel = toggleStoriesPanel;
    window.toggleGrammarPanel = toggleGrammarPanel;
    window.openStatsModal = openStatsModal;
    window.toggleTheme = toggleTheme;
}

// Run
init();
