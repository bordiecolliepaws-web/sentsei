// Ollama health polling and offline banner
import { state, DOM, KEYS } from './state.js';
import { unlockApp } from './api.js';

export async function pollOllamaHealth() {
    try {
        const resp = await fetch('/api/health');
        if (!resp.ok) return;
        const data = await resp.json();
        const wasOnline = state.ollamaOnline;
        state.ollamaOnline = data.ollama?.reachable ?? true;
        updateOfflineBanner();
        if (!wasOnline && state.ollamaOnline) {
            if (state.appPassword === KEYS.APP_PASSWORD) unlockApp();
        }
    } catch { /* network error — don't change state */ }
}

export function updateOfflineBanner() {
    let banner = document.getElementById('ollama-offline-banner');
    if (!state.ollamaOnline) {
        if (!banner) {
            banner = document.createElement('div');
            banner.id = 'ollama-offline-banner';
            banner.className = 'ollama-offline-banner';
            banner.innerHTML = '⚠️ Translation engine offline — cached results still available';
            document.querySelector('.app-header')?.after(banner) || document.body.prepend(banner);
        }
        banner.classList.remove('hidden');
        if (DOM.learnBtn) {
            DOM.learnBtn.classList.add('offline-disabled');
            DOM.learnBtn.title = 'Translation engine offline — cached results may still work';
        }
    } else {
        if (banner) banner.classList.add('hidden');
        if (DOM.learnBtn) {
            DOM.learnBtn.classList.remove('offline-disabled');
            DOM.learnBtn.title = '';
        }
    }
}

export function startHealthPolling() {
    pollOllamaHealth();
    state._healthPollTimer = setInterval(pollOllamaHealth, 30000);
}
