// Settings: theme, romanization, input language pills, gender/formality toggles
import { state, DOM, KEYS } from './state.js';
import { applyTheme, toggleTheme, initToggle, applyRomanization } from './ui.js?v=20260217';

export function initSettings() {
    // Gender & formality toggles
    initToggle(DOM.genderPills, state.selectedGender, KEYS.GENDER, v => state.selectedGender = v);
    initToggle(DOM.formalityPills, state.selectedFormality, KEYS.FORMALITY, v => state.selectedFormality = v);

    // Romanization
    DOM.romanizationToggle.addEventListener('click', () => {
        state.showRomanization = !state.showRomanization;
        localStorage.setItem(KEYS.ROMANIZATION, String(state.showRomanization));
        applyRomanization();
    });
    applyRomanization();

    // Input language pills
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

    // Theme
    const explicitTheme = localStorage.getItem(KEYS.THEME);
    const osPrefersDark = window.matchMedia?.('(prefers-color-scheme: dark)').matches;
    const initialTheme = explicitTheme || (osPrefersDark === false ? 'light' : 'dark');
    applyTheme(initialTheme);
    window.matchMedia?.('(prefers-color-scheme: dark)').addEventListener('change', e => {
        if (!localStorage.getItem(KEYS.THEME)) applyTheme(e.matches ? 'dark' : 'light');
    });
    const themeToggleBtn = document.getElementById('theme-toggle');
    if (themeToggleBtn) themeToggleBtn.addEventListener('click', toggleTheme);
}
