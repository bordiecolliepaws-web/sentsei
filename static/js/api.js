// API fetch wrappers and helpers
import { state, KEYS, DOM } from './state.js';

export async function friendlyError(resp) {
    const status = resp.status;
    let detail = '';
    try {
        const body = await resp.json();
        detail = body.detail || '';
    } catch { /* ignore */ }

    if (status === 429) return 'Too many requests — wait a moment and try again.';
    if (status === 502) return '__AUTO_RETRY_502__';
    if (status === 400 && detail) return detail;
    if (status === 401) return '';
    if (detail) return detail;
    return `Something went wrong (${status}). Tap retry.`;
}

export function ensurePassword() {
    if (state.appPassword === KEYS.APP_PASSWORD) return true;
    openPasswordModal();
    return false;
}

export function openPasswordModal(message = '') {
    lockApp();
    DOM.passwordModal.classList.remove('hidden');
    syncModalOpenState();
    DOM.passwordInput.value = '';
    if (message) {
        showPasswordError(message);
    } else {
        hidePasswordError();
    }
    requestAnimationFrame(() => DOM.passwordInput.focus());
}

export function closePasswordModal() {
    DOM.passwordModal.classList.add('hidden');
    syncModalOpenState();
    hidePasswordError();
}

export function lockApp() {
    DOM.sentenceInput.disabled = true;
    DOM.langSelect.disabled = true;
    DOM.learnBtn.disabled = true;
    if (DOM.compareBtn) DOM.compareBtn.disabled = true;
}

export function unlockApp() {
    DOM.sentenceInput.disabled = false;
    DOM.langSelect.disabled = false;
    DOM.learnBtn.disabled = false;
    if (DOM.compareBtn) DOM.compareBtn.disabled = false;
}

export function showPasswordError(message) {
    DOM.passwordError.textContent = message;
    DOM.passwordError.classList.remove('hidden');
}

export function hidePasswordError() {
    DOM.passwordError.classList.add('hidden');
}

export function syncModalOpenState() {
    const modalOpen = !DOM.passwordModal.classList.contains('hidden') || !DOM.statsModal.classList.contains('hidden');
    document.body.classList.toggle('modal-open', modalOpen);
}

export async function copyTextToClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
        return true;
    }

    const fallbackArea = document.createElement('textarea');
    fallbackArea.value = text;
    fallbackArea.setAttribute('readonly', '');
    fallbackArea.style.position = 'fixed';
    fallbackArea.style.opacity = '0';
    document.body.appendChild(fallbackArea);
    fallbackArea.select();

    let copied = false;
    try {
        copied = document.execCommand('copy');
    } catch {
        copied = false;
    }

    document.body.removeChild(fallbackArea);
    return copied;
}

// Auth sync helpers
export async function syncToServer(key, data) {
    if (!state.authToken) return;
    try {
        await fetch(`/api/user-data/${key}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + state.authToken
            },
            body: JSON.stringify({ data })
        });
    } catch (e) {
        console.warn('[sync] push failed:', key, e);
    }
}

export async function loadFromServer(key) {
    if (!state.authToken) return null;
    try {
        const resp = await fetch(`/api/user-data/${key}`, {
            headers: { 'Authorization': 'Bearer ' + state.authToken }
        });
        if (resp.status === 401) {
            state.authToken = '';
            state.authUsername = '';
            localStorage.removeItem(KEYS.AUTH_TOKEN);
            localStorage.removeItem(KEYS.AUTH_USERNAME);
            return null;
        }
        if (!resp.ok) return null;
        const body = await resp.json();
        return body.data;
    } catch (e) {
        console.warn('[sync] pull failed:', key, e);
        return null;
    }
}
