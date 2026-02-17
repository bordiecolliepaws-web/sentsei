// Speculative typing — pre-fetches translations while user types
import { state, DOM, KEYS } from './state.js';

export function getSpeculativeKey() {
    const sentence = DOM.sentenceInput.value.trim();
    if (!sentence || sentence.length < 3) return null;
    return `${sentence}|${DOM.langSelect.value}|${state.selectedInputLang}|${state.selectedGender}|${state.selectedFormality}`;
}

export function showSpeculativeIndicator() {
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

export function hideSpeculativeIndicator() {
    const indicator = document.getElementById('speculative-indicator');
    if (indicator) indicator.style.display = 'none';
}

export function cancelSpeculative() {
    if (state.speculativeTimer) { clearTimeout(state.speculativeTimer); state.speculativeTimer = null; }
    if (state.speculativeController) { state.speculativeController.abort(); state.speculativeController = null; }
    state.speculativePending = false;
    hideSpeculativeIndicator();
}

export async function startSpeculative() {
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
