// Quiz mode
import { state, DOM, LANG_FLAGS, QUIZ_SCORE_LABELS, KEYS, hooks } from './state.js';
import { ensurePassword, friendlyError, openPasswordModal } from './api.js';
import { todayDateKey, addProgressLanguage, persistProgressAndRefresh, loadQuizStats, saveQuizStats } from './ui.js';

export function renderQuizScore() {
    DOM.quizScore.textContent = `${state.quizStats.correct}/${state.quizStats.total}`;
}

export function renderQuizMeta() {
    const selectedLang = DOM.langSelect.value;
    const flag = LANG_FLAGS[selectedLang] || '🌐';
    const langName = DOM.langSelect.options[DOM.langSelect.selectedIndex]?.textContent || selectedLang || '';
    DOM.quizMeta.textContent = `${flag} ${langName} • Meaning match`;
}

export function clearQuizResult() {
    DOM.quizResult.className = 'quiz-result hidden';
    DOM.quizResult.innerHTML = '';
}

export function showQuizResult(result) {
    const score = ['perfect', 'good', 'partial', 'wrong'].includes(result.score) ? result.score : 'wrong';
    const label = QUIZ_SCORE_LABELS[score];
    const answer = result.correct_answer || 'N/A';
    const feedback = result.feedback || '';
    DOM.quizResult.innerHTML = `
        <div class="quiz-result-head">${label}</div>
        <div class="quiz-result-answer"><strong>Correct answer:</strong> ${answer}</div>
        <div class="quiz-result-feedback">${feedback}</div>
    `;
    DOM.quizResult.className = `quiz-result ${score}`;
    void DOM.quizResult.offsetWidth;
    DOM.quizResult.classList.add('show');
}

export function recordQuizCompletion(isCorrect, languageCode) {
    const today = todayDateKey();
    if (!state.progressStats.firstActivityDate) {
        state.progressStats.firstActivityDate = today;
    }
    state.progressStats.lastActivityDate = today;
    addProgressLanguage(languageCode);

    state.quizStats.total += 1;
    if (isCorrect) state.quizStats.correct += 1;
    saveQuizStats();
    renderQuizScore();
}

export function updateProgressStats(type) {
    // Called from quiz choice button clicks
    if (type === 'quiz_correct') {
        recordQuizCompletion(true, DOM.langSelect.value);
    } else if (type === 'quiz_wrong') {
        recordQuizCompletion(false, DOM.langSelect.value);
    }
}

export async function loadQuizQuestion() {
    if (!ensurePassword()) return;

    renderQuizMeta();
    clearQuizResult();
    state.currentQuiz = null;

    const choicesEl = document.getElementById('quiz-choices');
    choicesEl.innerHTML = '';
    DOM.quizSentence.textContent = 'Loading...';
    DOM.quizPronunciation.textContent = '';
    DOM.quizSource.textContent = '';
    DOM.quizHint.textContent = '';
    DOM.quizNext.disabled = true;

    const histItems = state.richHistory
        .filter(e => e.lang === DOM.langSelect.value && e.result && e.result.translation)
        .map(e => ({ sentence: e.sentence, translation: e.result.translation, pronunciation: e.result.pronunciation }));

    // Also check entries without .result wrapper (flat format)
    const flatItems = state.richHistory
        .filter(e => e.lang === DOM.langSelect.value && e.translation)
        .map(e => ({ sentence: e.sentence, translation: e.translation, pronunciation: e.pronunciation }));

    const allItems = histItems.length >= 2 ? histItems : flatItems;

    if (allItems.length < 2) {
        DOM.quizSentence.textContent = 'Learn at least 2 sentences first!';
        DOM.quizSource.textContent = 'Go back and translate some sentences, then try the quiz.';
        DOM.quizNext.disabled = false;
        return;
    }

    const qIdx = Math.floor(Math.random() * allItems.length);
    const question = allItems[qIdx];
    const showTranslation = Math.random() > 0.5;

    if (showTranslation) {
        document.getElementById('quiz-label').textContent = 'What does this mean?';
        DOM.quizSentence.textContent = question.translation;
        DOM.quizPronunciation.textContent = question.pronunciation ? question.pronunciation : '';

        const wrongItems = allItems.filter((_, i) => i !== qIdx);
        const shuffledWrong = wrongItems.sort(() => Math.random() - 0.5).slice(0, 3);
        const choices = shuffledWrong.map(w => ({ text: w.sentence, correct: false }));
        choices.push({ text: question.sentence, correct: true });
        choices.sort(() => Math.random() - 0.5);
        state.currentQuiz = { correctAnswer: question.sentence, choices };
    } else {
        document.getElementById('quiz-label').textContent = 'How do you say this?';
        DOM.quizSentence.textContent = question.sentence;
        DOM.quizPronunciation.textContent = '';

        const wrongItems = allItems.filter((_, i) => i !== qIdx);
        const shuffledWrong = wrongItems.sort(() => Math.random() - 0.5).slice(0, 3);
        const choices = shuffledWrong.map(w => ({ text: w.translation, correct: false }));
        choices.push({ text: question.translation, correct: true });
        choices.sort(() => Math.random() - 0.5);
        state.currentQuiz = { correctAnswer: question.translation, choices };
    }

    DOM.quizSource.textContent = 'From your history';

    state.currentQuiz.choices.forEach(choice => {
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
                state.quizCorrect++;
                updateProgressStats('quiz_correct');
            } else {
                btn.style.background = '#4a1a1a';
                btn.style.borderColor = 'var(--hard)';
                btn.style.color = 'var(--hard)';
                choicesEl.querySelectorAll('button').forEach(b => {
                    if (b.textContent === state.currentQuiz.correctAnswer) {
                        b.style.background = '#1a4a2a';
                        b.style.borderColor = 'var(--easy)';
                        b.style.color = 'var(--easy)';
                    }
                });
                updateProgressStats('quiz_wrong');
            }
            renderQuizScore();
            DOM.quizNext.disabled = false;
        });
        choicesEl.appendChild(btn);
    });

    DOM.quizNext.disabled = true;
}

export async function checkQuizAnswer() {
    if (!ensurePassword()) return;
    if (!state.currentQuiz) return;

    const answer = DOM.quizAnswerInput?.value?.trim();
    if (!answer) {
        DOM.quizAnswerInput?.focus();
        return;
    }

    const originalLabel = DOM.quizCheck.textContent;
    DOM.quizCheck.disabled = true;
    DOM.quizCheck.textContent = 'Checking...';

    try {
        const resp = await fetch('/api/quiz-check', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-App-Password': state.appPassword
            },
            body: JSON.stringify({
                quiz_id: state.currentQuiz.quiz_id,
                answer,
                target_language: state.currentQuiz.language
            })
        });

        if (resp.status === 401) {
            localStorage.removeItem(KEYS.PASSWORD_STORAGE);
            state.appPassword = '';
            openPasswordModal('Session expired. Enter password again.');
            return;
        }
        if (!resp.ok) throw new Error(await friendlyError(resp));

        const data = await resp.json();
        recordQuizCompletion(Boolean(data.correct), state.currentQuiz.language || DOM.langSelect.value);
        showQuizResult(data);
    } catch (err) {
        console.error(err);
        clearQuizResult();
        DOM.quizResult.innerHTML = '<div class="quiz-result-feedback">Could not check this answer. Try again.</div>';
        DOM.quizResult.className = 'quiz-result wrong show';
    } finally {
        DOM.quizCheck.textContent = originalLabel;
        DOM.quizCheck.disabled = false;
    }
}

export async function enterQuizMode() {
    if (!ensurePassword()) return;
    state.quizMode = true;
    document.body.classList.add('quiz-mode');
    DOM.quizArea.classList.remove('hidden');
    DOM.quizToggle.classList.add('active');
    renderQuizScore();
    await loadQuizQuestion();
}

export function exitQuizMode() {
    state.quizMode = false;
    state.currentQuiz = null;
    document.body.classList.remove('quiz-mode');
    DOM.quizArea.classList.add('hidden');
    DOM.quizToggle.classList.remove('active');
    clearQuizResult();
}

export async function toggleQuizMode() {
    if (state.quizMode) {
        exitQuizMode();
        return;
    }
    await enterQuizMode();
}
