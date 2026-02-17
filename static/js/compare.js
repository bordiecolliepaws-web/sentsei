// Compare mode — translate one sentence into all languages
import { state, DOM, KEYS, LEARN_TIMEOUT_MS } from './state.js';
import {
    ensurePassword, openPasswordModal, friendlyError
} from './api.js';
import {
    startLoadingTimer, stopLoadingTimer, showError, hideError,
    setRandomLoadingTip, renderCompareResults
} from './ui.js?v=20260217';

export async function compareSentence() {
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
            const { lockApp } = await import('./api.js');
            lockApp();
        }
        DOM.loading.classList.add('hidden');
    }
}
