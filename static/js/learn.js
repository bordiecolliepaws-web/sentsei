// Learn flow: learn(), surpriseMe(), _hasMultipleSentences()
import { state, DOM, KEYS, LEARN_TIMEOUT_MS, MAX_AUTO_RETRIES, AUTO_RETRY_DELAY_MS } from './state.js';
import { ensurePassword, openPasswordModal, friendlyError, updateRateLimitDisplay } from './api.js';
import {
    startLoadingTimer, stopLoadingTimer, showError, hideError, setRandomLoadingTip,
    renderResult, recordLearnProgress
} from './ui.js?v=20260217';
import { saveSentenceToHistory, addToRichHistory } from './history.js';
import { getSpeculativeKey, cancelSpeculative, startSpeculative } from './speculative.js';
import { lockApp, unlockApp } from './api.js';
import { compareSentence } from './compare.js';

// === Multi-sentence detection ===
export function _hasMultipleSentences(text) {
    const parts = text.split(/(?<=[.!?。！？])\s*/).filter(s => s.trim());
    return parts.length > 1;
}

// === Learn ===
export async function learn() {
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
export async function surpriseMe() {
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
