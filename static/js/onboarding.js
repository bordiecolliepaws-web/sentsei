// Onboarding overlay — first-time user experience
import { state, KEYS, DOM, hooks } from './state.js';

let _learn = null;
let _selectLangPill = null;

export function setOnboardingDeps({ learn, selectLangPill }) {
    _learn = learn;
    _selectLangPill = selectLangPill;
}

export function initOnboarding() {
    const onboardingOverlay = document.getElementById('onboarding-overlay');

    function showOnboarding() {
        if (localStorage.getItem(KEYS.ONBOARDED)) return;
        if (state.richHistory.length > 0 || state.sentenceHistory.length > 0) {
            localStorage.setItem(KEYS.ONBOARDED, '1');
            return;
        }
        onboardingOverlay.classList.remove('hidden');
    }

    function dismissOnboarding() {
        onboardingOverlay.classList.add('hidden');
        localStorage.setItem(KEYS.ONBOARDED, '1');
    }

    document.querySelectorAll('.onboarding-suggestion').forEach(btn => {
        btn.addEventListener('click', () => {
            const sentence = btn.dataset.sentence;
            const lang = btn.dataset.lang;
            dismissOnboarding();
            const tryFill = () => {
                if (state.languagesLoaded) {
                    if (lang) _selectLangPill(lang);
                    DOM.sentenceInput.value = sentence;
                    DOM.sentenceInput.style.height = 'auto';
                    DOM.sentenceInput.style.height = DOM.sentenceInput.scrollHeight + 'px';
                    _learn();
                } else {
                    setTimeout(tryFill, 200);
                }
            };
            tryFill();
        });
    });

    document.getElementById('onboarding-skip').addEventListener('click', () => {
        dismissOnboarding();
        DOM.sentenceInput.focus();
    });

    if (state.appPassword === KEYS.APP_PASSWORD) {
        showOnboarding();
    }

    hooks.afterClosePasswordModal.push(() => {
        setTimeout(showOnboarding, 300);
    });
}
