// Grammar pattern library — browse and explore recurring patterns
import { state, DOM, LANG_FLAGS, KEYS } from './state.js';
import { escapeHtml } from './ui.js?v=20260217';

export function toggleGrammarPanel() {
    state.grammarPanelOpen = !state.grammarPanelOpen;
    const grammarPanelEl = document.getElementById('grammar-panel');
    const grammarOverlayEl = document.getElementById('grammar-overlay');
    grammarPanelEl.classList.toggle('open', state.grammarPanelOpen);
    grammarOverlayEl.classList.toggle('open', state.grammarPanelOpen);
    if (state.grammarPanelOpen) loadGrammarPatterns();
}

export function closeGrammarPanel() {
    state.grammarPanelOpen = false;
    document.getElementById('grammar-panel').classList.remove('open');
    document.getElementById('grammar-overlay').classList.remove('open');
}

export async function loadGrammarPatterns() {
    try {
        const url = state.grammarFilterLang ? `/api/grammar-patterns?lang=${state.grammarFilterLang}` : '/api/grammar-patterns';
        const resp = await fetch(url, { headers: { 'x-app-password': KEYS.APP_PASSWORD } });
        if (!resp.ok) return;
        state.grammarPatterns = await resp.json();
        renderGrammarPatterns();
    } catch (e) { console.error('[grammar]', e); }
}

export function renderGrammarPatterns() {
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
