// History panel
import { state, DOM, LANG_FLAGS, KEYS, HISTORY_LIMIT, RECENT_DISPLAY_LIMIT, hooks } from './state.js';
import { ensurePassword, copyTextToClipboard, friendlyError, openPasswordModal } from './api.js';
import { getLanguageNamesMap } from './ui.js';
import { addToSRS } from './srs.js';

function normalizeLangCode(code) {
    if (typeof code !== 'string') return '';
    return code.trim().toLowerCase();
}

export function normalizeSentenceHistoryEntries(entries, fallbackLang = '') {
    if (!Array.isArray(entries)) return [];
    const resolvedFallbackLang = normalizeLangCode(fallbackLang);
    const normalized = [];
    const seen = new Set();

    entries.forEach(item => {
        let sentence = '';
        let lang = resolvedFallbackLang;

        if (typeof item === 'string') {
            sentence = item.trim();
        } else if (item && typeof item === 'object') {
            sentence = typeof item.sentence === 'string' ? item.sentence.trim() : '';
            lang = normalizeLangCode(item.lang) || resolvedFallbackLang;
        }

        if (!sentence) return;
        const dedupeKey = `${sentence}||${lang}`;
        if (seen.has(dedupeKey)) return;
        seen.add(dedupeKey);
        normalized.push({ sentence, lang });
    });

    return normalized.slice(0, HISTORY_LIMIT);
}

let _historyFilterLang = null;

export function setHistoryFilterLang(langCode) {
    _historyFilterLang = normalizeLangCode(langCode) || null;
}

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
        const fallbackLang = normalizeLangCode(localStorage.getItem(KEYS.TARGET_LANG) || '');
        const normalized = normalizeSentenceHistoryEntries(parsed, fallbackLang);
        if (JSON.stringify(parsed) !== JSON.stringify(normalized)) {
            localStorage.setItem(KEYS.SENTENCE_HISTORY, JSON.stringify(normalized));
        }
        return normalized;
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

export function saveSentenceToHistory(sentence, languageCode) {
    const cleanSentence = sentence.trim();
    if (!cleanSentence) return;
    const fallbackLang = normalizeLangCode(localStorage.getItem(KEYS.TARGET_LANG) || '');
    const lang = normalizeLangCode(languageCode || DOM.langSelect?.value || fallbackLang);
    const normalizedHistory = normalizeSentenceHistoryEntries(state.sentenceHistory, fallbackLang);
    state.sentenceHistory = [
        { sentence: cleanSentence, lang },
        ...normalizedHistory.filter(item => !(item.sentence === cleanSentence && item.lang === lang))
    ].slice(0, HISTORY_LIMIT);
    localStorage.setItem(KEYS.SENTENCE_HISTORY, JSON.stringify(state.sentenceHistory));
    renderSentenceHistory();
}

export function renderSentenceHistory() {
    const fallbackLang = normalizeLangCode(localStorage.getItem(KEYS.TARGET_LANG) || '');
    const normalizedHistory = normalizeSentenceHistoryEntries(state.sentenceHistory, fallbackLang);
    const needsPersist = normalizedHistory.length !== state.sentenceHistory.length || state.sentenceHistory.some(item => {
        if (!item || typeof item !== 'object') return true;
        return typeof item.sentence !== 'string' || typeof item.lang !== 'string';
    });
    if (needsPersist) {
        state.sentenceHistory = normalizedHistory;
        localStorage.setItem(KEYS.SENTENCE_HISTORY, JSON.stringify(state.sentenceHistory));
    }

    const selectedLang = normalizeLangCode(DOM.langSelect?.value || fallbackLang);
    const relevantEntries = selectedLang
        ? normalizedHistory.filter(item => item.lang === selectedLang)
        : normalizedHistory;

    DOM.sentenceHistory.innerHTML = '';
    if (relevantEntries.length === 0) {
        DOM.sentenceHistoryWrap.classList.add('hidden');
        return;
    }

    DOM.sentenceHistoryWrap.classList.remove('hidden');
    const displayItems = relevantEntries.slice(0, RECENT_DISPLAY_LIMIT);
    displayItems.forEach((entry) => {
        const chip = document.createElement('button');
        chip.type = 'button';
        chip.className = 'history-chip';
        chip.textContent = entry.sentence;
        chip.title = entry.sentence;
        chip.addEventListener('click', () => {
            DOM.sentenceInput.value = entry.sentence;
            DOM.sentenceInput.style.height = 'auto';
            DOM.sentenceInput.style.height = DOM.sentenceInput.scrollHeight + 'px';
            DOM.sentenceInput.focus();
        });
        DOM.sentenceHistory.appendChild(chip);
    });
    if (relevantEntries.length > RECENT_DISPLAY_LIMIT) {
        const moreBtn = document.createElement('button');
        moreBtn.type = 'button';
        moreBtn.className = 'history-chip';
        moreBtn.style.cssText = 'background:rgba(99,102,241,0.25);color:#a5b4fc;font-weight:600;';
        moreBtn.textContent = `View all (${relevantEntries.length}) →`;
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
    if (!_historyFilterLang) {
        _historyFilterLang = normalizeLangCode(DOM.langSelect?.value || '');
    }
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

function renderHistoryLanguageFilter(langNames, availableLangs, activeLang) {
    if (!DOM.historyLangFilter) return;
    DOM.historyLangFilter.classList.remove('hidden');
    const allCount = state.richHistory.length;
    const tabs = [{ code: 'all', label: 'All', count: allCount }, ...availableLangs.map(code => ({
        code,
        label: `${LANG_FLAGS[code] || '🌐'} ${langNames[code] || code.toUpperCase()}`,
        count: state.richHistory.filter(entry => normalizeLangCode(entry.lang) === code).length
    }))];

    DOM.historyLangFilter.innerHTML = tabs.map(tab => `
        <button type="button" class="history-lang-pill ${tab.code === activeLang ? 'active' : ''}" data-lang="${tab.code}">
            ${tab.label} <span class="history-lang-count">${tab.count}</span>
        </button>
    `).join('');

    DOM.historyLangFilter.querySelectorAll('.history-lang-pill').forEach(btn => {
        btn.addEventListener('click', () => {
            const next = btn.dataset.lang || 'all';
            _historyFilterLang = next === 'all' ? 'all' : normalizeLangCode(next);
            renderHistoryPanel();
        });
    });
}

export function renderHistoryPanel() {
    if (state.richHistory.length === 0) {
        if (DOM.historyLangFilter) {
            DOM.historyLangFilter.innerHTML = '';
            DOM.historyLangFilter.classList.add('hidden');
        }
        DOM.historyPanelList.innerHTML = '<div class="history-panel-empty">No sentences yet. Start learning!</div>';
        return;
    }
    const langNames = getLanguageNamesMap();
    const selectedLang = normalizeLangCode(DOM.langSelect?.value || '');
    const availableLangs = [...new Set(state.richHistory
        .map(entry => normalizeLangCode(entry.lang))
        .filter(Boolean))];
    if (selectedLang && !availableLangs.includes(selectedLang)) {
        availableLangs.unshift(selectedLang);
    }
    const activeLang = (_historyFilterLang || selectedLang || 'all');

    renderHistoryLanguageFilter(langNames, availableLangs, activeLang);

    const filteredEntries = state.richHistory
        .map((entry, idx) => ({ entry, idx }))
        .filter(({ entry }) => activeLang === 'all' || normalizeLangCode(entry.lang) === activeLang);

    if (filteredEntries.length === 0) {
        const emptyLabel = activeLang === 'all'
            ? 'No sentences yet. Start learning!'
            : `No ${langNames[activeLang] || activeLang.toUpperCase()} history yet.`;
        DOM.historyPanelList.innerHTML = `<div class="history-panel-empty">${emptyLabel}</div>`;
        return;
    }

    DOM.historyPanelList.innerHTML = filteredEntries.map(({ entry, idx }) => {
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
            const idx = parseInt(item.dataset.idx, 10);
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
