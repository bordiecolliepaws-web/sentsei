// Favorites / Bookmarks module
import { state, DOM, LANG_FLAGS, KEYS } from './state.js';
import { ensurePassword, openPasswordModal, friendlyError } from './api.js';
import { getLanguageNamesMap } from './ui.js';

const FAV_STORAGE_KEY = 'sentsei-favorites';

// --- Local storage ---

export function loadFavorites() {
    try {
        const raw = localStorage.getItem(FAV_STORAGE_KEY) || '[]';
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed : [];
    } catch { return []; }
}

export function saveFavorites(favorites) {
    localStorage.setItem(FAV_STORAGE_KEY, JSON.stringify(favorites));
}

export function isFavorited(sentence, lang) {
    const favs = loadFavorites();
    return favs.some(f => f.sentence === sentence && f.lang === lang);
}

export function toggleFavorite(sentence, translation, lang, pronunciation) {
    let favs = loadFavorites();
    const idx = favs.findIndex(f => f.sentence === sentence && f.lang === lang);
    let added = false;
    if (idx >= 0) {
        favs.splice(idx, 1);
    } else {
        favs.unshift({ sentence, translation, lang, pronunciation: pronunciation || '', ts: Date.now() });
        added = true;
    }
    saveFavorites(favs);
    updateFavoriteBadge();
    // Sync to server if logged in
    syncFavoriteToServer(sentence, translation, lang, pronunciation, added);
    return added;
}

async function syncFavoriteToServer(sentence, translation, lang, pronunciation, added) {
    if (!state.authToken) return;
    try {
        if (added) {
            await fetch('/api/favorites', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-App-Password': state.appPassword,
                    'Authorization': `Bearer ${state.authToken}`
                },
                body: JSON.stringify({ sentence, translation, lang, pronunciation, ts: Date.now() })
            });
        } else {
            await fetch(`/api/favorites?sentence=${encodeURIComponent(sentence)}&lang=${encodeURIComponent(lang)}`, {
                method: 'DELETE',
                headers: {
                    'X-App-Password': state.appPassword,
                    'Authorization': `Bearer ${state.authToken}`
                }
            });
        }
    } catch (e) {
        console.warn('Failed to sync favorite to server:', e);
    }
}

export async function loadFavoritesFromServer() {
    if (!state.authToken) return;
    try {
        const resp = await fetch('/api/favorites', {
            headers: { 'Authorization': `Bearer ${state.authToken}` }
        });
        if (!resp.ok) return;
        const data = await resp.json();
        if (Array.isArray(data.favorites) && data.favorites.length > 0) {
            // Merge server favorites with local
            const local = loadFavorites();
            const seen = new Set(local.map(f => `${f.sentence}||${f.lang}`));
            for (const sf of data.favorites) {
                const key = `${sf.sentence}||${sf.lang}`;
                if (!seen.has(key)) {
                    local.push(sf);
                    seen.add(key);
                }
            }
            local.sort((a, b) => (b.ts || 0) - (a.ts || 0));
            saveFavorites(local);
        }
    } catch (e) {
        console.warn('Failed to load favorites from server:', e);
    }
}

// --- UI ---

export function updateFavoriteBadge() {
    const count = loadFavorites().length;
    const badge = document.getElementById('menu-favorites-badge');
    if (badge) {
        badge.textContent = count;
        badge.style.display = count > 0 ? '' : 'none';
    }
}

export function createFavoriteButton(sentence, translation, lang, pronunciation) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'fav-btn';
    btn.setAttribute('aria-label', 'Favorite this sentence');
    const active = isFavorited(sentence, lang);
    btn.classList.toggle('fav-active', active);
    btn.innerHTML = `<span class="fav-icon">${active ? '★' : '☆'}</span><span class="fav-label">${active ? 'Saved' : 'Save'}</span>`;
    btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const added = toggleFavorite(sentence, translation, lang, pronunciation);
        btn.classList.toggle('fav-active', added);
        btn.querySelector('.fav-icon').textContent = added ? '★' : '☆';
        btn.querySelector('.fav-label').textContent = added ? 'Saved' : 'Save';
        // Update any other fav buttons for same sentence on page
        document.querySelectorAll(`.fav-btn[data-fav-key="${CSS.escape(sentence + '||' + lang)}"]`).forEach(other => {
            if (other !== btn) {
                other.classList.toggle('fav-active', added);
                other.querySelector('.fav-icon').textContent = added ? '★' : '☆';
                other.querySelector('.fav-label').textContent = added ? 'Saved' : 'Save';
            }
        });
    });
    btn.dataset.favKey = sentence + '||' + lang;
    return btn;
}

// --- Favorites Panel (tab within history panel) ---

let _favFilterLang = 'all';

export function renderFavoritesPanel() {
    const container = document.getElementById('favorites-panel-list');
    if (!container) return;
    const favs = loadFavorites();

    if (favs.length === 0) {
        container.innerHTML = '<div class="history-panel-empty">No favorites yet. Tap ☆ on any result to save it.</div>';
        const filterEl = document.getElementById('favorites-lang-filter');
        if (filterEl) { filterEl.innerHTML = ''; filterEl.classList.add('hidden'); }
        return;
    }

    const langNames = getLanguageNamesMap();
    const availableLangs = [...new Set(favs.map(f => f.lang).filter(Boolean))];

    // Language filter
    const filterEl = document.getElementById('favorites-lang-filter');
    if (filterEl) {
        filterEl.classList.remove('hidden');
        const tabs = [
            { code: 'all', label: 'All', count: favs.length },
            ...availableLangs.map(code => ({
                code,
                label: `${LANG_FLAGS[code] || '🌐'} ${langNames[code] || code.toUpperCase()}`,
                count: favs.filter(f => f.lang === code).length
            }))
        ];
        filterEl.innerHTML = tabs.map(tab => `
            <button type="button" class="history-lang-pill ${tab.code === _favFilterLang ? 'active' : ''}" data-lang="${tab.code}">
                ${tab.label} <span class="history-lang-count">${tab.count}</span>
            </button>
        `).join('');
        filterEl.querySelectorAll('.history-lang-pill').forEach(btn => {
            btn.addEventListener('click', () => {
                _favFilterLang = btn.dataset.lang || 'all';
                renderFavoritesPanel();
            });
        });
    }

    const filtered = _favFilterLang === 'all' ? favs : favs.filter(f => f.lang === _favFilterLang);
    if (filtered.length === 0) {
        container.innerHTML = '<div class="history-panel-empty">No favorites for this language.</div>';
        return;
    }

    container.innerHTML = filtered.map((fav, idx) => {
        const flag = LANG_FLAGS[fav.lang] || '🌐';
        const langName = langNames[fav.lang] || fav.lang;
        const time = new Date(fav.ts);
        const timeStr = time.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) + ' ' + time.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
        return `<div class="history-panel-item fav-panel-item" data-sentence="${fav.sentence.replace(/"/g, '&quot;')}" data-lang="${fav.lang}">
            <div class="hp-translation">${fav.translation}</div>
            <div class="hp-sentence">${fav.sentence}</div>
            <div class="hp-meta">
                <span class="hp-lang">${flag} ${langName}</span>
                <span>${timeStr}</span>
                <button type="button" class="fav-remove-btn" title="Remove from favorites" aria-label="Remove favorite">✕</button>
            </div>
        </div>`;
    }).join('');

    container.querySelectorAll('.fav-panel-item').forEach(item => {
        const sentence = item.dataset.sentence;
        const lang = item.dataset.lang;

        // Click to load sentence
        item.addEventListener('click', (e) => {
            if (e.target.closest('.fav-remove-btn')) return;
            DOM.sentenceInput.value = sentence;
            DOM.sentenceInput.style.height = 'auto';
            DOM.sentenceInput.style.height = DOM.sentenceInput.scrollHeight + 'px';
            DOM.sentenceInput.focus();
        });

        // Remove button
        const removeBtn = item.querySelector('.fav-remove-btn');
        if (removeBtn) {
            removeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                toggleFavorite(sentence, '', lang, '');
                renderFavoritesPanel();
            });
        }
    });
}

export async function exportFavoritesAsAnki() {
    if (!ensurePassword()) return;
    const favs = loadFavorites();
    if (favs.length === 0) {
        alert('No favorites to export.');
        return;
    }

    const btn = document.getElementById('favorites-export-anki-btn');
    if (btn) { btn.disabled = true; btn.textContent = 'Exporting...'; }

    try {
        const payload = favs.map(f => ({
            sentence: f.sentence || '',
            translation: f.translation || '',
            pronunciation: f.pronunciation || '',
            lang: f.lang || ''
        }));
        const resp = await fetch('/api/export-favorites', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-App-Password': state.appPassword
            },
            body: JSON.stringify(payload)
        });
        if (resp.status === 401) {
            localStorage.removeItem(KEYS.PASSWORD_STORAGE);
            state.appPassword = '';
            openPasswordModal('Session expired.');
            return;
        }
        if (!resp.ok) throw new Error(await friendlyError(resp));
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'sentsei-favorites.txt';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        if (btn) btn.textContent = 'Done';
    } catch (err) {
        console.error(err);
        alert('Could not export favorites.');
        if (btn) btn.textContent = 'Failed';
    } finally {
        setTimeout(() => {
            if (btn) { btn.textContent = '📥 Anki'; btn.disabled = false; }
        }, 1000);
    }
}
