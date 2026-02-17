// Keyboard shortcuts
import { state, DOM } from './state.js';
import { closeHistoryPanel, toggleHistoryPanel } from './history.js';

let _deps = {};
export function setShortcutDeps(deps) { _deps = deps; }

export function initShortcuts() {
    const sideMenuEl = document.getElementById('side-menu');
    const hamburgerBtn = document.getElementById('hamburger-btn');

    document.addEventListener('keydown', (e) => {
        const mod = e.ctrlKey || e.metaKey;

        if (e.key === 'Escape') {
            const helpEl = document.getElementById('shortcut-help');
            if (helpEl && helpEl.classList.contains('open')) { helpEl.classList.remove('open'); return; }
            if (sideMenuEl.classList.contains('open')) { _deps.closeSideMenu(); hamburgerBtn.focus(); return; }
            if (state.historyPanelOpen) { closeHistoryPanel(); return; }
            if (state.storyPanelOpen) { _deps.closeStoriesPanel(); return; }
            // Close stats modal
            if (DOM.statsModal && !DOM.statsModal.classList.contains('hidden')) {
                _deps.closeStatsModal();
            }
            return;
        }

        const tag = document.activeElement?.tagName;
        const inInput = tag === 'INPUT' || tag === 'TEXTAREA';

        if (mod && e.key === 'Enter') { e.preventDefault(); _deps.learn(); return; }
        if (mod && e.key === 'h') { e.preventDefault(); toggleHistoryPanel(); return; }
        if (mod && e.key === 'k') { e.preventDefault(); DOM.sentenceInput.focus(); DOM.sentenceInput.select(); return; }
        if (mod && e.shiftKey && (e.key === 'S' || e.key === 's')) { e.preventDefault(); DOM.surpriseBtn.click(); return; }
        if (e.key === '?' && !inInput) { toggleShortcutHelp(); return; }
    });

    // Focus trap for side menu
    sideMenuEl.addEventListener('keydown', (e) => {
        if (e.key !== 'Tab') return;
        const focusable = sideMenuEl.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
        if (!focusable.length) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    });
}

function toggleShortcutHelp() {
    let helpEl = document.getElementById('shortcut-help');
    if (!helpEl) {
        helpEl = document.createElement('div');
        helpEl.id = 'shortcut-help';
        helpEl.setAttribute('role', 'dialog');
        helpEl.setAttribute('aria-label', 'Keyboard shortcuts');
        helpEl.innerHTML = `
            <div class="shortcut-help-inner">
                <h3>⌨️ Keyboard Shortcuts</h3>
                <table>
                    <tr><td><kbd>Ctrl</kbd>+<kbd>Enter</kbd></td><td>Learn sentence</td></tr>
                    <tr><td><kbd>Ctrl</kbd>+<kbd>H</kbd></td><td>Toggle history</td></tr>
                    <tr><td><kbd>Ctrl</kbd>+<kbd>K</kbd></td><td>Focus input</td></tr>
                    <tr><td><kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>S</kbd></td><td>Surprise me</td></tr>
                    <tr><td><kbd>Esc</kbd></td><td>Close panels</td></tr>
                    <tr><td><kbd>?</kbd></td><td>This help</td></tr>
                </table>
                <p class="shortcut-hint">Press <kbd>Esc</kbd> or <kbd>?</kbd> to close</p>
            </div>`;
        document.body.appendChild(helpEl);
        helpEl.addEventListener('click', (ev) => { if (ev.target === helpEl) helpEl.classList.remove('open'); });
    }
    helpEl.classList.toggle('open');
}
