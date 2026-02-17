// shortcuts.js — Keyboard shortcuts
import { state, dom } from './state.js';
import { toggleHistoryPanel, closeHistoryPanel } from './history.js';

export function initShortcuts({ learn, closeSideMenu, closeStoriesPanel }) {
    const sentenceInput = dom('sentence');
    const surpriseBtn = dom('surprise-btn');
    const sideMenuEl = dom('side-menu');
    const hamburgerBtn = dom('hamburger-btn');

    document.addEventListener('keydown', (e) => {
        const mod = e.ctrlKey || e.metaKey;

        if (e.key === 'Escape') {
            const helpEl = document.getElementById('shortcut-help');
            if (helpEl && helpEl.classList.contains('open')) { helpEl.classList.remove('open'); return; }
            if (sideMenuEl && sideMenuEl.classList.contains('open')) { closeSideMenu(); hamburgerBtn.focus(); return; }
            if (state.historyPanelOpen) { closeHistoryPanel(); return; }
            if (state.storyPanelOpen) { closeStoriesPanel(); return; }
            return;
        }

        const tag = document.activeElement?.tagName;
        const inInput = tag === 'INPUT' || tag === 'TEXTAREA';

        if (mod && e.key === 'Enter') { e.preventDefault(); learn(); return; }
        if (mod && e.key === 'h') { e.preventDefault(); toggleHistoryPanel(); return; }
        if (mod && e.key === 'k') { e.preventDefault(); sentenceInput.focus(); sentenceInput.select(); return; }
        if (mod && e.shiftKey && (e.key === 'S' || e.key === 's')) { e.preventDefault(); surpriseBtn.click(); return; }
        if (e.key === '?' && !inInput) { toggleShortcutHelp(); return; }
    });

    // Escape closes stats modal
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const statsModalEl = dom('stats-modal');
            if (statsModalEl && !statsModalEl.classList.contains('hidden')) {
                statsModalEl.classList.add('hidden');
                document.body.classList.toggle('modal-open', false);
            }
        }
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
