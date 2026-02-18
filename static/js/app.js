// Main entry point — imports all modules and wires everything together
import { state, DOM, LANG_FLAGS, KEYS, HISTORY_LIMIT, hooks, LEARN_TIMEOUT_MS, MAX_AUTO_RETRIES, AUTO_RETRY_DELAY_MS, DAY_MS } from './state.js';
import {
    ensurePassword, openPasswordModal, closePasswordModal, lockApp, unlockApp,
    showPasswordError, hidePasswordError, syncModalOpenState,
    copyTextToClipboard, friendlyError, syncToServer, loadFromServer, updateRateLimitDisplay
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
    toggleReviewMode, loadReviewQuestion, setSRSDeps,
    loadSRSDeckFromServerOnInit, syncSRSDeckOnLogin,
    enterBatchReview, handleReviewNext
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
import { loadFavorites, updateFavoriteBadge, renderFavoritesPanel, exportFavoritesAsAnki, loadFavoritesFromServer } from './favorites.js';
import { initShortcuts, setShortcutDeps } from './shortcuts.js';
import {
    loadStoryProgress, saveStoryProgress, getStoryProgress, setStoryProgress,
    updateStoriesBadge, toggleStoriesPanel, closeStoriesPanel, loadStories,
    renderStoriesBrowser, openStoryReader, renderStoryReader
} from './story.js';
import { compareSentence } from './compare.js';
import { toggleGrammarPanel, closeGrammarPanel, loadGrammarPatterns } from './grammar.js';
import { getSpeculativeKey, showSpeculativeIndicator, hideSpeculativeIndicator, cancelSpeculative, startSpeculative } from './speculative.js';
import { initOnboarding, setOnboardingDeps } from './onboarding.js';
import { pollOllamaHealth, updateOfflineBanner, startHealthPolling } from './offline.js';

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

// === Language Picker ===
function showLanguagePicker() {
    const picker = document.getElementById('language-picker');
    const learnView = document.getElementById('learn-view');
    const resultsEl = DOM.results;
    const compareEl = DOM.compareResults;
    const changeLangBtn = document.getElementById('change-lang-btn');
    if (picker) picker.classList.remove('hidden');
    if (learnView) learnView.style.display = 'none';
    if (resultsEl) resultsEl.style.display = 'none';
    if (compareEl) compareEl.style.display = 'none';
    if (changeLangBtn) changeLangBtn.classList.add('hidden');
}

function hideLanguagePicker() {
    const picker = document.getElementById('language-picker');
    const learnView = document.getElementById('learn-view');
    const resultsEl = DOM.results;
    const compareEl = DOM.compareResults;
    const changeLangBtn = document.getElementById('change-lang-btn');
    if (picker) picker.classList.add('hidden');
    if (learnView) learnView.style.display = '';
    if (resultsEl) resultsEl.style.display = '';
    if (compareEl) compareEl.style.display = '';
    if (changeLangBtn) changeLangBtn.classList.remove('hidden');
}

function updateChangeLangButton(code) {
    const flag = LANG_FLAGS[code] || '🌐';
    const langNames = getLanguageNamesMap();
    const name = langNames[code] || (DOM.langSelect.options[DOM.langSelect.selectedIndex]?.textContent) || code.toUpperCase();
    const flagEl = document.getElementById('change-lang-flag');
    const nameEl = document.getElementById('change-lang-name');
    if (flagEl) flagEl.textContent = flag;
    if (nameEl) nameEl.textContent = name;
}

// === Language selection ===
function selectLangPill(code) {
    const selectedCode = (code || '').trim().toLowerCase();
    DOM.langSelect.value = selectedCode;
    localStorage.setItem(KEYS.TARGET_LANG, selectedCode);
    DOM.langPills.querySelectorAll('.lang-pill').forEach(p => {
        const isActive = p.dataset.lang === selectedCode;
        p.classList.toggle('active', isActive);
        p.setAttribute('aria-checked', String(isActive));
    });
    filterResultsByLanguage(selectedCode);
    setHistoryFilterLang(selectedCode);
    renderHistoryPanel();
    renderSentenceHistory();
    updateStoriesBadge();
    if (state.storyPanelOpen) renderStoriesBrowser();
    updateChangeLangButton(selectedCode);
    hideLanguagePicker();
}

async function loadLanguages() {
    if (state.languagesLoaded) return;
    const langs = await fetch('/api/languages').then(r => r.json());
    DOM.langPills.innerHTML = '';
    const pickerGrid = document.getElementById('picker-grid');
    if (pickerGrid) pickerGrid.innerHTML = '';
    for (const [code, name] of Object.entries(langs)) {
        const opt = document.createElement('option');
        opt.value = code;
        opt.textContent = name;
        DOM.langSelect.appendChild(opt);
        // Old pills (hidden but functional)
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
        // Picker card
        if (pickerGrid) {
            const card = document.createElement('button');
            card.type = 'button';
            card.className = 'picker-card';
            card.dataset.lang = code;
            card.innerHTML = `<span class="picker-flag">${flag}</span><span class="picker-name">${name}</span>`;
            card.addEventListener('click', () => selectLangPill(code));
            pickerGrid.appendChild(card);
        }
    }
    const savedLang = localStorage.getItem(KEYS.TARGET_LANG);
    const hasSavedLang = savedLang && Object.prototype.hasOwnProperty.call(langs, savedLang);
    const defaultLang = hasSavedLang ? savedLang : (Object.prototype.hasOwnProperty.call(langs, 'zh') ? 'zh' : Object.keys(langs)[0]);
    if (defaultLang) selectLangPill(defaultLang);
    // Show picker if no saved preference (first visit)
    if (!hasSavedLang) {
        showLanguagePicker();
    }
    state.languagesLoaded = true;
    renderHistoryPanel();
    renderProgressStats();
    await loadStories();
    // Wire change-language button
    const changeLangBtn = document.getElementById('change-lang-btn');
    if (changeLangBtn) changeLangBtn.addEventListener('click', showLanguagePicker);
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

    const _fetchStart = performance.now();
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
            updateRateLimitDisplay(resp);
            const data = await resp.json();
            const _elapsedMs = Math.round(performance.now() - _fetchStart);
            const reqCtx = { target_language: DOM.langSelect.value, input_language: state.selectedInputLang, sentence: sentence };
            const successfulResults = Array.isArray(data.results) ? data.results.filter(item => item && item.result) : [];
            successfulResults.forEach(item => {
                renderResult(item.result, item.sentence, { ...reqCtx, sentence: item.sentence }, _elapsedMs);
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
            updateRateLimitDisplay(resp);
            const data = await resp.json();
            const _elapsedMs = Math.round(performance.now() - _fetchStart);
            const reqCtx = { target_language: DOM.langSelect.value, input_language: state.selectedInputLang, sentence: sentence };
            renderResult(data, sentence, reqCtx, _elapsedMs);
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

// === Surprise Me ===
async function surpriseMe() {
    if (!ensurePassword()) return;
    DOM.surpriseBtn.disabled = true;
    try {
        const lang = DOM.langSelect.value;
        const inputLang = state.selectedInputLang === 'auto' ? 'en' : state.selectedInputLang;
        const resp = await fetch(`/api/surprise?lang=${encodeURIComponent(lang)}&input_lang=${encodeURIComponent(inputLang)}`);
        if (!resp.ok) throw new Error(await friendlyError(resp));
        updateRateLimitDisplay(resp);
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

            // Best-effort: attach the most recent sentence/translation context
            // so backend can tie feedback to a specific cached result.
            let sentence = '';
            let translation = '';
            let targetLang = '';
            try {
                const latestCard = DOM.results?.querySelector('.result-card');
                if (latestCard) {
                    const srcEl = latestCard.querySelector('.result-source');
                    const transEl = latestCard.querySelector('.result-translation');
                    sentence = (srcEl?.textContent || '').replace(/^"|"$/g, '').trim();
                    translation = (transEl?.textContent || '').trim();
                    targetLang = latestCard.dataset.lang || DOM.langSelect?.value || '';
                }
            } catch (_) {
                // Ignore — context is optional.
            }

            await fetch('/api/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-App-Password': pw },
                body: JSON.stringify({
                    message: text.value.trim(),
                    sentence,
                    translation,
                    target_language: targetLang || undefined,
                })
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
            await syncSRSDeckOnLogin();
            await pullAllFromServer();
            await loadFavoritesFromServer();
            updateFavoriteBadge();
        } catch(err) {
            authErrorEl.textContent = err.message;
            authErrorEl.classList.remove('hidden');
        } finally {
            authSubmitBtn.disabled = false;
        }
    });

    updateAuthUI();
    if (state.authToken) {
        loadSRSDeckFromServerOnInit();
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

// === Favorites Panel ===
let _favoritesPanelOpen = false;
function toggleFavoritesPanel() {
    _favoritesPanelOpen = !_favoritesPanelOpen;
    document.getElementById('favorites-panel').classList.toggle('open', _favoritesPanelOpen);
    document.getElementById('favorites-overlay').classList.toggle('open', _favoritesPanelOpen);
    if (_favoritesPanelOpen) renderFavoritesPanel();
}
function closeFavoritesPanel() {
    _favoritesPanelOpen = false;
    document.getElementById('favorites-panel').classList.remove('open');
    document.getElementById('favorites-overlay').classList.remove('open');
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
    document.getElementById('menu-favorites').addEventListener('click', () => { closeSideMenu(); toggleFavoritesPanel(); });
    document.getElementById('menu-quiz').addEventListener('click', () => { closeSideMenu(); toggleQuizMode(); });
    document.getElementById('menu-review').addEventListener('click', () => { closeSideMenu(); toggleReviewMode(); });
    document.getElementById('menu-stories').addEventListener('click', () => { closeSideMenu(); toggleStoriesPanel(); });
    document.getElementById('menu-stats').addEventListener('click', () => { closeSideMenu(); openStatsModal(); });
    document.getElementById('menu-grammar').addEventListener('click', () => { closeSideMenu(); toggleGrammarPanel(); });
    document.getElementById('menu-theme').addEventListener('click', () => { closeSideMenu(); toggleTheme(); });

    hooks.afterUpdateHistoryBadge.push(() => {
        const count = state.richHistory.length;
        menuHistoryBadge.textContent = count;
        menuHistoryBadge.style.display = count > 0 ? '' : 'none';
        hamburgerBadge.textContent = count;
        hamburgerBadge.style.display = count > 0 ? '' : 'none';
    });

    return { closeSideMenu };
}

// === Sync hooks ===
function initSyncHooks() {
    hooks.afterSaveRichHistory.push(() => syncToServer('rich_history', state.richHistory));
    hooks.afterSaveProgressStats.push(() => syncToServer('progress', state.progressStats));
}

// === Main initialization ===
function init() {
    initDOM();
    initState();

    // Set dependency injections
    setSRSDeps({ ensurePassword });
    setHistoryDeps({ selectLangPill });
    setOnboardingDeps({ learn, selectLangPill });

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

    // Favorites panel events
    const favPanel = document.getElementById('favorites-panel');
    const favOverlay = document.getElementById('favorites-overlay');
    const favClose = document.getElementById('favorites-panel-close');
    const favExportAnki = document.getElementById('favorites-export-anki-btn');
    if (favOverlay) favOverlay.addEventListener('click', () => closeFavoritesPanel());
    if (favClose) favClose.addEventListener('click', () => closeFavoritesPanel());
    if (favExportAnki) favExportAnki.addEventListener('click', exportFavoritesAsAnki);
    updateFavoriteBadge();

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
    if (reviewNextBtn) reviewNextBtn.addEventListener('click', handleReviewNext);
    const batchReviewBtn = document.getElementById('batch-review-btn');
    if (batchReviewBtn) batchReviewBtn.addEventListener('click', enterBatchReview);
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
    const explicitTheme = localStorage.getItem(KEYS.THEME);
    const osPrefersDark = window.matchMedia?.('(prefers-color-scheme: dark)').matches;
    const initialTheme = explicitTheme || (osPrefersDark === false ? 'light' : 'dark');
    applyTheme(initialTheme);
    // Listen for OS theme changes (only when user hasn't explicitly chosen)
    window.matchMedia?.('(prefers-color-scheme: dark)').addEventListener('change', e => {
        if (!localStorage.getItem(KEYS.THEME)) applyTheme(e.matches ? 'dark' : 'light');
    });
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

    // Load languages
    loadLanguages().then(() => {
        const urlParams = new URLSearchParams(window.location.search);
        const sharedSentence = urlParams.get('s');
        const sharedLang = urlParams.get('t');
        if (sharedSentence) {
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

    // Health polling for Ollama status
    startHealthPolling();

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
