// Story mode — browsing and reading stories
import { state, DOM, LANG_FLAGS, KEYS } from './state.js';

// === Story progress persistence ===
export function loadStoryProgress() {
    try {
        const raw = localStorage.getItem(KEYS.STORY_PROGRESS) || '{}';
        const parsed = JSON.parse(raw);
        if (!parsed || typeof parsed !== 'object') return {};
        return parsed;
    } catch { return {}; }
}

export function saveStoryProgress() {
    localStorage.setItem(KEYS.STORY_PROGRESS, JSON.stringify(state.storyProgress));
}

export function getStoryProgress(storyId, sentenceCount) {
    const raw = Number(state.storyProgress[storyId] || 0);
    if (!Number.isFinite(raw) || raw < 0) return 0;
    if (!sentenceCount || sentenceCount < 1) return 0;
    return Math.min(raw, sentenceCount - 1);
}

export function setStoryProgress(storyId, index) {
    if (!storyId || !Number.isFinite(index) || index < 0) return;
    state.storyProgress[storyId] = index;
    saveStoryProgress();
}

// === Story badge ===
export function updateStoriesBadge() {
    if (!DOM.storiesBadge) return;
    const selectedLang = DOM.langSelect.value;
    const count = selectedLang ? state.stories.filter(s => s.language === selectedLang).length : state.stories.length;
    DOM.storiesBadge.textContent = count;
}

// === Story panel toggle ===
export function toggleStoriesPanel() {
    state.storyPanelOpen = !state.storyPanelOpen;
    DOM.storiesPanel.classList.toggle('open', state.storyPanelOpen);
    DOM.storiesOverlay.classList.toggle('open', state.storyPanelOpen);
    if (state.storyPanelOpen) renderStoriesBrowser();
}

export function closeStoriesPanel() {
    state.storyPanelOpen = false;
    DOM.storiesPanel.classList.remove('open');
    DOM.storiesOverlay.classList.remove('open');
}

// === Load stories from API ===
export async function loadStories() {
    try {
        const resp = await fetch('/api/stories');
        if (!resp.ok) return;
        state.stories = await resp.json();
        updateStoriesBadge();
    } catch (e) { console.error(e); }
}

// === Render story browser ===
export function renderStoriesBrowser() {
    const selectedLang = DOM.langSelect.value;
    const langName = DOM.langSelect.options[DOM.langSelect.selectedIndex]?.textContent || selectedLang;
    const flag = LANG_FLAGS[selectedLang] || '🌐';
    DOM.storiesFilter.textContent = `${flag} ${langName} stories`;
    const filtered = state.stories.filter(s => s.language === selectedLang);
    if (filtered.length === 0) {
        DOM.storiesList.innerHTML = '<div class="stories-empty">No stories for this language yet.</div>';
        return;
    }
    DOM.storiesList.innerHTML = filtered.map(s => {
        const prog = getStoryProgress(s.id, s.sentence_count);
        const progText = `${prog + 1}/${s.sentence_count}`;
        return `<button class="story-list-item" data-story-id="${s.id}">
            <div class="story-list-title">${s.title}</div>
            <div class="story-list-meta">
                <span>${s.source}</span>
                <span class="story-list-progress">${progText}</span>
            </div>
        </button>`;
    }).join('');
    DOM.storiesList.querySelectorAll('.story-list-item').forEach(btn => {
        btn.addEventListener('click', () => openStoryReader(btn.dataset.storyId));
    });
    DOM.storiesBrowser.classList.remove('hidden');
    DOM.storyReader.classList.add('hidden');
}

// === Open and render story reader ===
export async function openStoryReader(storyId) {
    let story = state.storyCache[storyId];
    if (!story) {
        try {
            const resp = await fetch(`/api/story/${encodeURIComponent(storyId)}`);
            if (!resp.ok) return;
            story = await resp.json();
            state.storyCache[storyId] = story;
        } catch (e) { console.error(e); return; }
    }
    state.activeStory = story;
    state.activeStoryIndex = getStoryProgress(storyId, story.sentences.length);
    DOM.storiesBrowser.classList.add('hidden');
    DOM.storyReader.classList.remove('hidden');
    renderStoryReader();
}

export function renderStoryReader() {
    if (!state.activeStory) return;
    const total = state.activeStory.sentences.length;
    DOM.storyTitle.textContent = state.activeStory.title;
    DOM.storySource.textContent = state.activeStory.source;
    DOM.storySentence.textContent = state.activeStory.sentences[state.activeStoryIndex];
    DOM.storyProgress.textContent = `${state.activeStoryIndex + 1}/${total}`;
    DOM.storyPrevBtn.disabled = state.activeStoryIndex <= 0;
    DOM.storyNextBtn.disabled = state.activeStoryIndex >= total - 1;
}
