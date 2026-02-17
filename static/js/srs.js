// Spaced Repetition System (SRS) logic
import { state, KEYS, DAY_MS, DOM, hooks } from './state.js';

export function loadSRSDeck() {
    try {
        const raw = localStorage.getItem(KEYS.SRS);
        if (!raw) return [];
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed : [];
    } catch { return []; }
}

export function saveSRSDeck() {
    localStorage.setItem(KEYS.SRS, JSON.stringify(state.srsDeck));
    hooks.afterSaveSRSDeck.forEach(fn => fn());
}

export function addToSRS(sentence, translation, lang, pronunciation) {
    if (!sentence || !translation) return;
    const exists = state.srsDeck.some(item => item.sentence === sentence && item.lang === lang);
    if (exists) return;
    state.srsDeck.push({
        sentence,
        translation,
        lang,
        pronunciation: pronunciation || '',
        addedAt: Date.now(),
        nextReview: Date.now() + DAY_MS,
        interval: DAY_MS,
        easeFactor: 2.5,
        reviewCount: 0
    });
    saveSRSDeck();
    updateReviewBadge();
}

export function getDueItems() {
    const now = Date.now();
    return state.srsDeck.filter(item => item.nextReview <= now);
}

export function updateSRSItem(item, correct) {
    const now = Date.now();
    if (correct) {
        if (item.reviewCount === 0) {
            item.interval = DAY_MS;
        } else if (item.reviewCount === 1) {
            item.interval = 3 * DAY_MS;
        } else {
            item.interval = Math.round(item.interval * item.easeFactor);
        }
        item.easeFactor = Math.max(1.3, item.easeFactor + 0.1);
        item.reviewCount++;
    } else {
        item.interval = DAY_MS;
        item.reviewCount = 0;
        item.easeFactor = Math.max(1.3, item.easeFactor - 0.2);
    }
    item.nextReview = now + item.interval;
    saveSRSDeck();
    updateReviewBadge();
}

export function updateReviewBadge() {
    const dueCount = getDueItems().length;
    const badge = document.getElementById('review-badge');
    const menuBadge = document.getElementById('menu-review-badge');
    if (badge) {
        badge.textContent = dueCount;
        badge.style.display = dueCount > 0 ? '' : 'none';
    }
    if (menuBadge) {
        menuBadge.textContent = dueCount;
        menuBadge.style.display = dueCount > 0 ? '' : 'none';
    }
}

export function formatTimeUntil(ms) {
    if (ms <= 0) return 'now';
    const hours = Math.floor(ms / 3600000);
    const days = Math.floor(ms / DAY_MS);
    if (days > 0) return `${days} day${days === 1 ? '' : 's'}`;
    if (hours > 0) return `${hours} hour${hours === 1 ? '' : 's'}`;
    const mins = Math.ceil(ms / 60000);
    return `${mins} min${mins === 1 ? '' : 's'}`;
}

export function enterReviewMode() {
    const { ensurePassword } = _deps;
    if (!ensurePassword()) return;
    const dueItems = getDueItems();
    state.reviewMode = true;
    state.reviewCorrect = 0;
    state.reviewTotal = 0;
    state.currentReview = null;
    document.body.classList.add('review-mode');

    const reviewArea = document.getElementById('review-area');
    reviewArea.classList.remove('hidden');
    document.getElementById('review-toggle').classList.add('active');

    if (dueItems.length === 0) {
        showReviewComplete();
        return;
    }

    document.getElementById('review-meta').textContent = `${dueItems.length} item${dueItems.length === 1 ? '' : 's'} due for review`;

    // Show batch review button if enough items
    const batchStartRow = document.getElementById('batch-start-row');
    if (batchStartRow) {
        batchStartRow.classList.toggle('hidden', dueItems.length < 2);
        const batchBtn = document.getElementById('batch-review-btn');
        if (batchBtn) batchBtn.textContent = `⚡ Review ${Math.min(10, dueItems.length)}`;
    }
    // Hide batch progress
    const progressEl = document.getElementById('batch-progress');
    if (progressEl) progressEl.classList.add('hidden');

    loadReviewQuestion();
}

export function exitReviewMode() {
    state.reviewMode = false;
    state.batchReview = false;
    state.currentReview = null;
    document.body.classList.remove('review-mode');
    document.getElementById('review-area').classList.add('hidden');
    document.getElementById('review-toggle').classList.remove('active');
    const progressEl = document.getElementById('batch-progress');
    if (progressEl) progressEl.classList.add('hidden');
    const batchStartRow = document.getElementById('batch-start-row');
    if (batchStartRow) batchStartRow.classList.add('hidden');
}

export function toggleReviewMode() {
    if (state.reviewMode) {
        exitReviewMode();
    } else {
        enterReviewMode();
    }
}

export function showReviewComplete() {
    const choicesEl = document.getElementById('review-choices');
    choicesEl.innerHTML = '';
    const sentenceEl = document.getElementById('review-sentence');
    const pronunciationEl = document.getElementById('review-pronunciation');
    const labelEl = document.getElementById('review-label');
    const sourceEl = document.getElementById('review-source');

    const now = Date.now();
    let nextTime = Infinity;
    state.srsDeck.forEach(item => {
        if (item.nextReview > now && item.nextReview < nextTime) {
            nextTime = item.nextReview;
        }
    });

    labelEl.textContent = '';
    sentenceEl.textContent = 'All caught up! 🎉';
    pronunciationEl.textContent = '';
    if (nextTime < Infinity) {
        sourceEl.textContent = `Next review in ${formatTimeUntil(nextTime - now)}`;
    } else {
        sourceEl.textContent = 'No items in your review deck yet.';
    }
    document.getElementById('review-next-btn').disabled = true;
}

export function loadReviewQuestion() {
    const dueItems = getDueItems();
    state.currentReview = null;

    const choicesEl = document.getElementById('review-choices');
    choicesEl.innerHTML = '';
    const sentenceEl = document.getElementById('review-sentence');
    const pronunciationEl = document.getElementById('review-pronunciation');
    const labelEl = document.getElementById('review-label');
    const sourceEl = document.getElementById('review-source');
    const nextBtn = document.getElementById('review-next-btn');
    nextBtn.disabled = true;

    if (dueItems.length === 0) {
        showReviewComplete();
        return;
    }

    document.getElementById('review-meta').textContent = `${dueItems.length} item${dueItems.length === 1 ? '' : 's'} remaining`;

    const qIdx = Math.floor(Math.random() * dueItems.length);
    const question = dueItems[qIdx];
    const sameLang = state.srsDeck.filter(item => item.lang === question.lang);
    const showTranslation = Math.random() > 0.5;

    if (showTranslation) {
        labelEl.textContent = 'What does this mean?';
        sentenceEl.textContent = question.translation;
        pronunciationEl.textContent = question.pronunciation || '';

        const wrongItems = sameLang.filter(w => w.sentence !== question.sentence).sort(() => Math.random() - 0.5).slice(0, 3);
        const choices = wrongItems.map(w => ({ text: w.sentence, correct: false }));
        choices.push({ text: question.sentence, correct: true });
        choices.sort(() => Math.random() - 0.5);
        state.currentReview = { item: question, correctAnswer: question.sentence, choices };
    } else {
        labelEl.textContent = 'How do you say this?';
        sentenceEl.textContent = question.sentence;
        pronunciationEl.textContent = '';

        const wrongItems = sameLang.filter(w => w.sentence !== question.sentence).sort(() => Math.random() - 0.5).slice(0, 3);
        const choices = wrongItems.map(w => ({ text: w.translation, correct: false }));
        choices.push({ text: question.translation, correct: true });
        choices.sort(() => Math.random() - 0.5);
        state.currentReview = { item: question, correctAnswer: question.translation, choices };
    }

    sourceEl.textContent = `Interval: ${formatTimeUntil(question.interval)}`;

    state.currentReview.choices.forEach(choice => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.textContent = choice.text;
        btn.style.cssText = 'padding:0.75rem 1rem;border-radius:var(--radius);border:1px solid var(--border);background:var(--surface2);color:var(--text);font-size:0.95rem;cursor:pointer;text-align:left;transition:all 0.2s;';
        btn.addEventListener('click', () => {
            choicesEl.querySelectorAll('button').forEach(b => { b.disabled = true; b.style.cursor = 'default'; });

            if (choice.correct) {
                btn.style.background = '#1a4a2a';
                btn.style.borderColor = 'var(--easy)';
                btn.style.color = 'var(--easy)';
                state.reviewCorrect++;
                updateSRSItem(state.currentReview.item, true);
            } else {
                btn.style.background = '#4a1a1a';
                btn.style.borderColor = 'var(--hard)';
                btn.style.color = 'var(--hard)';
                choicesEl.querySelectorAll('button').forEach(b => {
                    if (b.textContent === state.currentReview.correctAnswer) {
                        b.style.background = '#1a4a2a';
                        b.style.borderColor = 'var(--easy)';
                        b.style.color = 'var(--easy)';
                    }
                });
                updateSRSItem(state.currentReview.item, false);
            }
            state.reviewTotal++;
            document.getElementById('review-score').textContent = `${state.reviewCorrect}/${state.reviewTotal}`;
            nextBtn.disabled = false;
        });
        choicesEl.appendChild(btn);
    });
}

// === Batch Review Mode ===

export function enterBatchReview() {
    const { ensurePassword } = _deps;
    if (!ensurePassword()) return;
    const dueItems = getDueItems();
    if (dueItems.length === 0) {
        enterReviewMode(); // falls through to "all caught up"
        return;
    }

    // Shuffle and take up to 10
    const shuffled = [...dueItems].sort(() => Math.random() - 0.5);
    const batchSize = Math.min(10, shuffled.length);
    state.batchReview = true;
    state.batchQueue = shuffled.slice(0, batchSize);
    state.batchIndex = 0;
    state.batchStartTime = Date.now();
    state.batchCardTimes = [];
    state.batchResults = [];
    state.reviewMode = true;
    state.reviewCorrect = 0;
    state.reviewTotal = 0;
    state.currentReview = null;

    document.body.classList.add('review-mode');
    const reviewArea = document.getElementById('review-area');
    reviewArea.classList.remove('hidden');
    document.getElementById('review-toggle').classList.add('active');

    // Show batch progress bar
    const progressEl = document.getElementById('batch-progress');
    if (progressEl) {
        progressEl.classList.remove('hidden');
        updateBatchProgress();
    }

    // Hide batch start button row if present
    const batchStartRow = document.getElementById('batch-start-row');
    if (batchStartRow) batchStartRow.classList.add('hidden');

    loadBatchCard();
}

function updateBatchProgress() {
    const progressEl = document.getElementById('batch-progress');
    if (!progressEl) return;
    const total = state.batchQueue.length;
    const current = state.batchIndex + 1;
    const pct = Math.round((state.batchIndex / total) * 100);
    progressEl.innerHTML = `
        <div class="batch-progress-text">${current} of ${total}</div>
        <div class="batch-progress-bar"><div class="batch-progress-fill" style="width:${pct}%"></div></div>
    `;
}

function loadBatchCard() {
    if (state.batchIndex >= state.batchQueue.length) {
        showBatchSummary();
        return;
    }

    updateBatchProgress();
    state.batchCardStart = Date.now();
    const question = state.batchQueue[state.batchIndex];

    const choicesEl = document.getElementById('review-choices');
    choicesEl.innerHTML = '';
    const sentenceEl = document.getElementById('review-sentence');
    const pronunciationEl = document.getElementById('review-pronunciation');
    const labelEl = document.getElementById('review-label');
    const sourceEl = document.getElementById('review-source');
    const nextBtn = document.getElementById('review-next-btn');
    nextBtn.disabled = true;

    document.getElementById('review-meta').textContent =
        `Batch review: ${state.batchIndex + 1}/${state.batchQueue.length}`;

    const sameLang = state.srsDeck.filter(item => item.lang === question.lang);
    const showTranslation = Math.random() > 0.5;
    let correctAnswer;

    if (showTranslation) {
        labelEl.textContent = 'What does this mean?';
        sentenceEl.textContent = question.translation;
        pronunciationEl.textContent = question.pronunciation || '';
        correctAnswer = question.sentence;
        const wrongItems = sameLang.filter(w => w.sentence !== question.sentence).sort(() => Math.random() - 0.5).slice(0, 3);
        const choices = wrongItems.map(w => ({ text: w.sentence, correct: false }));
        choices.push({ text: question.sentence, correct: true });
        choices.sort(() => Math.random() - 0.5);
        state.currentReview = { item: question, correctAnswer, choices };
    } else {
        labelEl.textContent = 'How do you say this?';
        sentenceEl.textContent = question.sentence;
        pronunciationEl.textContent = '';
        correctAnswer = question.translation;
        const wrongItems = sameLang.filter(w => w.sentence !== question.sentence).sort(() => Math.random() - 0.5).slice(0, 3);
        const choices = wrongItems.map(w => ({ text: w.translation, correct: false }));
        choices.push({ text: question.translation, correct: true });
        choices.sort(() => Math.random() - 0.5);
        state.currentReview = { item: question, correctAnswer, choices };
    }

    sourceEl.textContent = `Interval: ${formatTimeUntil(question.interval)}`;

    state.currentReview.choices.forEach(choice => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.textContent = choice.text;
        btn.style.cssText = 'padding:0.75rem 1rem;border-radius:var(--radius);border:1px solid var(--border);background:var(--surface2);color:var(--text);font-size:0.95rem;cursor:pointer;text-align:left;transition:all 0.2s;';
        btn.addEventListener('click', () => {
            const cardTime = Date.now() - state.batchCardStart;
            choicesEl.querySelectorAll('button').forEach(b => { b.disabled = true; b.style.cursor = 'default'; });

            const correct = choice.correct;
            if (correct) {
                btn.style.background = '#1a4a2a';
                btn.style.borderColor = 'var(--easy)';
                btn.style.color = 'var(--easy)';
                state.reviewCorrect++;
                updateSRSItem(state.currentReview.item, true);
            } else {
                btn.style.background = '#4a1a1a';
                btn.style.borderColor = 'var(--hard)';
                btn.style.color = 'var(--hard)';
                choicesEl.querySelectorAll('button').forEach(b => {
                    if (b.textContent === state.currentReview.correctAnswer) {
                        b.style.background = '#1a4a2a';
                        b.style.borderColor = 'var(--easy)';
                        b.style.color = 'var(--easy)';
                    }
                });
                updateSRSItem(state.currentReview.item, false);
            }
            state.reviewTotal++;
            state.batchCardTimes.push(cardTime);
            state.batchResults.push({ correct, item: state.currentReview.item, timeMs: cardTime });
            document.getElementById('review-score').textContent = `${state.reviewCorrect}/${state.reviewTotal}`;
            nextBtn.disabled = false;
        });
        choicesEl.appendChild(btn);
    });
}

export function nextBatchCard() {
    state.batchIndex++;
    loadBatchCard();
}

function showBatchSummary() {
    const totalTime = Date.now() - state.batchStartTime;
    const total = state.batchResults.length;
    const correct = state.batchResults.filter(r => r.correct).length;
    const pct = total > 0 ? Math.round((correct / total) * 100) : 0;
    const avgTime = total > 0 ? Math.round(state.batchCardTimes.reduce((a, b) => a + b, 0) / total / 1000 * 10) / 10 : 0;

    // Calculate streak (longest consecutive correct)
    let maxStreak = 0, streak = 0;
    state.batchResults.forEach(r => {
        if (r.correct) { streak++; maxStreak = Math.max(maxStreak, streak); }
        else { streak = 0; }
    });

    const choicesEl = document.getElementById('review-choices');
    choicesEl.innerHTML = '';
    const labelEl = document.getElementById('review-label');
    const sentenceEl = document.getElementById('review-sentence');
    const pronunciationEl = document.getElementById('review-pronunciation');
    const sourceEl = document.getElementById('review-source');
    const nextBtn = document.getElementById('review-next-btn');
    nextBtn.disabled = true;

    // Update progress bar to 100%
    const progressEl = document.getElementById('batch-progress');
    if (progressEl) {
        progressEl.innerHTML = `
            <div class="batch-progress-text">Complete!</div>
            <div class="batch-progress-bar"><div class="batch-progress-fill" style="width:100%"></div></div>
        `;
    }

    labelEl.textContent = '';
    pronunciationEl.textContent = '';
    sourceEl.textContent = '';

    // Grade
    let grade, gradeEmoji;
    if (pct === 100) { grade = 'Perfect'; gradeEmoji = '🏆'; }
    else if (pct >= 80) { grade = 'Great'; gradeEmoji = '⚡'; }
    else if (pct >= 60) { grade = 'Good'; gradeEmoji = '👍'; }
    else if (pct >= 40) { grade = 'Keep going'; gradeEmoji = '💪'; }
    else { grade = 'Needs practice'; gradeEmoji = '📚'; }

    sentenceEl.innerHTML = `
        <div style="text-align:center;">
            <div style="font-size:2rem;margin-bottom:0.5rem;">${gradeEmoji}</div>
            <div style="font-size:1.3rem;font-weight:600;margin-bottom:1rem;">${grade}!</div>
            <div class="batch-summary-stats">
                <div class="batch-stat">
                    <div class="batch-stat-value">${pct}%</div>
                    <div class="batch-stat-label">Correct</div>
                </div>
                <div class="batch-stat">
                    <div class="batch-stat-value">${correct}/${total}</div>
                    <div class="batch-stat-label">Score</div>
                </div>
                <div class="batch-stat">
                    <div class="batch-stat-value">${avgTime}s</div>
                    <div class="batch-stat-label">Avg time</div>
                </div>
                <div class="batch-stat">
                    <div class="batch-stat-value">${maxStreak}</div>
                    <div class="batch-stat-label">Best streak</div>
                </div>
            </div>
            <div style="margin-top:1rem;font-size:0.85rem;color:var(--muted);">
                Total time: ${Math.round(totalTime / 1000)}s
            </div>
        </div>
    `;

    state.batchReview = false;
}

export function handleReviewNext() {
    if (state.batchReview) {
        nextBatchCard();
    } else {
        loadReviewQuestion();
    }
}

// Dependency injection for circular deps
let _deps = {};
export function setSRSDeps(deps) { _deps = deps; }
