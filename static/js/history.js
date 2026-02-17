// History panel
import { state, DOM, LANG_FLAGS, KEYS, HISTORY_LIMIT, RECENT_DISPLAY_LIMIT, hooks } from './state.js';
import { ensurePassword, copyTextToClipboard, friendlyError, openPasswordModal } from './api.js';
import { getLanguageNamesMap } from './ui.js';
import { addToSRS } from './srs.js';

export function loadRichHistory() {
    try {
        const raw = localStorage.getItem(KEYS.RICH_HISTORY) || '[]';
        const parsed = JSON.parse(raw);
        if (!Array.isArray(parsed)) return [];
        return parsed.slice(0, HISTORY_LIMIT);
    } catch { return []; }
}

export function saveRichHistory() {
    localStorage.setItem(KEYS.RICH_HISTORY, JSON.stringify(state.richHistory));
    hooks.afterSaveRichHistory.forEach(fn => fn());
}

export function loadSentenceHistory() {
    try {
        const raw = localStorage.getItem(KEYS.SENTENCE_HISTORY) || '[]';
        const parsed = JSON.parse(raw);
        if (!Array.isArray(parsed)) return [];
        return parsed
            .filter(item => typeof item === 'string' && item.trim())
            .slice(0, HISTORY_LIMIT);
    } catch {
        return [];
    }
}

export function addToRichHistory(sentence, translation, targetLang, pronunciation) {
    const entry = {
        sentence,
        translation,
        lang: targetLang,
        pronunciation: pronunciation || '',
        ts: Date.now()
    };
    state.richHistory = state.richHistory.filter(e => !(e.sentence === sentence && e.lang === targetLang));
    state.richHistory.unshift(entry);
    state.richHistory = state.richHistory.slice(0, HISTORY_LIMIT);
    saveRichHistory();
    renderHistoryPanel();
    updateHistoryBadge();
    addToSRS(sentence, translation, targetLang, pronunciation);
}

export function saveSentenceToHistory(sentence) {
    const cleanSentence = sentence.trim();
    if (!cleanSentence) return;
    state.sentenceHistory = [cleanSentence, ...state.sentenceHistory.filter(item => item !== cleanSentence)].slice(0, HISTORY_LIMIT);
    localStorage.setItem(KEYS.SENTENCE_HISTORY, JSON.stringify(state.sentenceHistory));
    renderSentenceHistory();
}

export function renderSentenceHistory() {
    DOM.sentenceHistory.innerHTML = '';
    if (state.sentenceHistory.length === 0) {
        DOM.sentenceHistoryWrap.classList.add('hidden');
        return;
    }

    DOM.sentenceHistoryWrap.classList.remove('hidden');
    const displayItems = state.sentenceHistory.slice(0, RECENT_DISPLAY_LIMIT);
    displayItems.forEach((sentence) => {
        const chip = document.createElement('button');
        chip.type = 'button';
        chip.className = 'history-chip';
        chip.textContent = sentence;
        chip.title = sentence;
        chip.addEventListener('click', () => {
            DOM.sentenceInput.value = sentence;
            DOM.sentenceInput.style.height = 'auto';
            DOM.sentenceInput.style.height = DOM.sentenceInput.scrollHeight + 'px';
            DOM.sentenceInput.focus();
        });
        DOM.sentenceHistory.appendChild(chip);
    });
    if (state.sentenceHistory.length > RECENT_DISPLAY_LIMIT) {
        const moreBtn = document.createElement('button');
        moreBtn.type = 'button';
        moreBtn.className = 'history-chip';
        moreBtn.style.cssText = 'background:rgba(99,102,241,0.25);color:#a5b4fc;font-weight:600;';
        moreBtn.textContent = `View all (${state.sentenceHistory.length}) →`;
        moreBtn.addEventListener('click', () => {
            openHistoryPanel();
        });
        DOM.sentenceHistory.appendChild(moreBtn);
    }
}

export function toggleHistoryPanel() {
    state.historyPanelOpen = !state.historyPanelOpen;
    DOM.historyPanel.classList.toggle('open', state.historyPanelOpen);
    DOM.historyOverlay.classList.toggle('open', state.historyPanelOpen);
}

export function openHistoryPanel() {
    state.historyPanelOpen = true;
    DOM.historyPanel.classList.add('open');
    DOM.historyOverlay.classList.add('open');
    renderHistoryPanel();
}

export function closeHistoryPanel() {
    state.historyPanelOpen = false;
    DOM.historyPanel.classList.remove('open');
    DOM.historyOverlay.classList.remove('open');
}

export function updateHistoryBadge() {
    const count = state.richHistory.length;
    DOM.historyBadge.textContent = count;
    DOM.historyToggle.classList.toggle('hidden', count === 0);
    hooks.afterUpdateHistoryBadge.forEach(fn => fn());
}

export function renderHistoryPanel() {
    if (state.richHistory.length === 0) {
        DOM.historyPanelList.innerHTML = '<div class="history-panel-empty">No sentences yet. Start learning!</div>';
        return;
    }
    const langNames = getLanguageNamesMap();

    DOM.historyPanelList.innerHTML = state.richHistory.map((entry, idx) => {
        const flag = LANG_FLAGS[entry.lang] || '🌐';
        const langName = langNames[entry.lang] || entry.lang;
        const time = new Date(entry.ts);
        const timeStr = time.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) + ' ' + time.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
        return `<div class="history-panel-item" data-idx="${idx}">
            <div class="hp-translation">${entry.translation}</div>
            <div class="hp-sentence">${entry.sentence}</div>
            <div class="hp-meta"><span class="hp-lang">${flag} ${langName}</span><span>${timeStr}</span></div>
        </div>`;
    }).join('');

    DOM.historyPanelList.querySelectorAll('.history-panel-item').forEach(item => {
        item.addEventListener('click', () => {
            const idx = parseInt(item.dataset.idx);
            const entry = state.richHistory[idx];
            if (entry) {
                DOM.sentenceInput.value = entry.sentence;
                DOM.sentenceInput.style.height = 'auto';
                DOM.sentenceInput.style.height = DOM.sentenceInput.scrollHeight + 'px';
                if (entry.lang) _deps.selectLangPill(entry.lang);
                closeHistoryPanel();
                DOM.sentenceInput.focus();
            }
        });
    });
}

export function buildHistoryCopyText() {
    const langNames = getLanguageNamesMap();
    return state.richHistory.map((entry, idx) => {
        const langCode = entry.lang || '';
        const langName = langNames[langCode] || langCode || 'Unknown';
        const langLine = langCode ? `${langName} (${langCode})` : langName;
        const timeLine = entry.ts ? new Date(entry.ts).toLocaleString() : '';
        const lines = [
            `${idx + 1}. ${entry.translation || ''}`,
            `Original: ${entry.sentence || ''}`,
            `Pronunciation: ${entry.pronunciation || '—'}`,
            `Language: ${langLine}`
        ];
        if (timeLine) lines.push(`Saved: ${timeLine}`);
        return lines.join('\n');
    }).join('\n\n');
}

export function buildHistoryAnkiPayload() {
    return state.richHistory.map(entry => ({
        sentence: entry.sentence || '',
        translation: entry.translation || '',
        pronunciation: entry.pronunciation || '',
        target: entry.lang || '',
        timestamp: entry.ts ? new Date(entry.ts).toISOString() : ''
    }));
}

export async function exportHistoryAsAnki() {
    if (!ensurePassword()) return;
    if (state.richHistory.length === 0) {
        alert('No history to export yet.');
        return;
    }

    const originalLabel = DOM.historyExportAnki.textContent;
    DOM.historyExportAnki.disabled = true;
    DOM.historyExportAnki.textContent = 'Exporting...';

    try {
        const resp = await fetch('/api/export-anki', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-App-Password': state.appPassword
            },
            body: JSON.stringify(buildHistoryAnkiPayload())
        });

        if (resp.status === 401) {
            localStorage.removeItem(KEYS.PASSWORD_STORAGE);
            state.appPassword = '';
            openPasswordModal('Session expired. Enter password again.');
            return;
        }
        if (!resp.ok) throw new Error(await friendlyError(resp));

        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'sentsay-flashcards.txt';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        DOM.historyExportAnki.textContent = 'Done';
    } catch (err) {
        console.error(err);
        alert('Could not export Anki file.');
        DOM.historyExportAnki.textContent = 'Failed';
    } finally {
        setTimeout(() => {
            DOM.historyExportAnki.textContent = originalLabel;
            DOM.historyExportAnki.disabled = false;
        }, 1000);
    }
}

export async function copyAllHistoryToClipboard() {
    if (state.richHistory.length === 0) {
        alert('No history to copy yet.');
        return;
    }

    const originalLabel = DOM.historyCopyAll.textContent;
    DOM.historyCopyAll.disabled = true;
    try {
        const copied = await copyTextToClipboard(buildHistoryCopyText());
        DOM.historyCopyAll.textContent = copied ? 'Copied' : 'Failed';
    } catch (err) {
        console.error(err);
        DOM.historyCopyAll.textContent = 'Failed';
    } finally {
        setTimeout(() => {
            DOM.historyCopyAll.textContent = originalLabel;
            DOM.historyCopyAll.disabled = false;
        }, 1000);
    }
}

// Dependency injection
let _deps = {};
export function setHistoryDeps(deps) { _deps = deps; }
