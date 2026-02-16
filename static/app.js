const langSelect = document.getElementById('lang');
        const langPillsEl = document.getElementById('lang-pills');
        const LANG_FLAGS = {
            ko: '🇰🇷', ja: '🇯🇵', zh: '🇹🇼', en: '🇺🇸',
            he: '🇮🇱', el: '🇬🇷', it: '🇮🇹', es: '🇪🇸',
            fr: '🇫🇷', de: '🇩🇪', pt: '🇧🇷', ar: '🇸🇦',
            th: '🇹🇭', vi: '🇻🇳', hi: '🇮🇳', ru: '🇷🇺'
        };
        const sentenceInput = document.getElementById('sentence');
        const learnBtn = document.getElementById('learn-btn');
        const surpriseBtn = document.getElementById('surprise-btn');
        const compareBtn = document.getElementById('compare-btn');
        const loadingEl = document.getElementById('loading');
        const loadingTipEl = document.getElementById('loading-tip');
        const compareResultsEl = document.getElementById('compare-results');
        const resultsEl = document.getElementById('results');
        const sentenceHistoryWrapEl = document.getElementById('sentence-history-wrap');
        const sentenceHistoryEl = document.getElementById('sentence-history');
        const passwordModalEl = document.getElementById('password-modal');
        const passwordFormEl = document.getElementById('password-form');
        const passwordInputEl = document.getElementById('password-input');
        const passwordErrorEl = document.getElementById('password-error');
        const statsToggleBtn = document.getElementById('stats-toggle');
        const statsModalEl = document.getElementById('stats-modal');
        const statsModalCloseBtn = document.getElementById('stats-modal-close');
        const statsTotalSentencesEl = document.getElementById('stats-total-sentences');
        const statsLanguagesEl = document.getElementById('stats-languages');
        const statsQuizAccuracyEl = document.getElementById('stats-quiz-accuracy');
        const statsStreakEl = document.getElementById('stats-streak');
        const statsLearningSinceEl = document.getElementById('stats-learning-since');
        const genderPillsEl = document.getElementById('gender-pills');
        const formalityPillsEl = document.getElementById('formality-pills');
        const GENDER_KEY = 'sent-say_speaker_gender';
        const FORMALITY_KEY = 'sent-say_speaker_formality';
        let selectedGender = localStorage.getItem(GENDER_KEY) || 'neutral';
        let selectedFormality = localStorage.getItem(FORMALITY_KEY) || 'polite';

        function initToggle(container, current, storageKey, setter) {
            container.querySelectorAll('.toggle-pill').forEach(p => {
                p.classList.toggle('active', p.dataset.value === current);
                p.addEventListener('click', () => {
                    container.querySelectorAll('.toggle-pill').forEach(q => q.classList.remove('active'));
                    p.classList.add('active');
                    localStorage.setItem(storageKey, p.dataset.value);
                    setter(p.dataset.value);
                });
            });
        }

        initToggle(genderPillsEl, selectedGender, GENDER_KEY, v => selectedGender = v);
        initToggle(formalityPillsEl, selectedFormality, FORMALITY_KEY, v => selectedFormality = v);

        // Input language selector
        const INPUT_LANG_KEY = 'sent-say_input_lang';
        let selectedInputLang = localStorage.getItem(INPUT_LANG_KEY) || 'en';
        const inputLangPillsEl = document.getElementById('input-lang-pills');
        inputLangPillsEl.querySelectorAll('.lang-pill').forEach(p => {
            p.classList.toggle('active', p.dataset.lang === selectedInputLang);
            p.addEventListener('click', () => {
                inputLangPillsEl.querySelectorAll('.lang-pill').forEach(q => q.classList.remove('active'));
                p.classList.add('active');
                selectedInputLang = p.dataset.lang;
                localStorage.setItem(INPUT_LANG_KEY, selectedInputLang);
            });
        });

        const APP_PASSWORD = 'sentsei2026';
        const PASSWORD_STORAGE_KEY = 'sent-say_app_password';
        const SENTENCE_HISTORY_KEY = 'sent-say_sentence_history';
        const RICH_HISTORY_KEY = 'sent-say_rich_history';
        const STORY_PROGRESS_KEY = 'sent-say_story_progress';
        const PROGRESS_STATS_KEY = 'sent-say_progress_stats';
        const HISTORY_LIMIT = 50;
        const MS_PER_DAY = 24 * 60 * 60 * 1000;
        const storiesToggleBtn = document.getElementById('stories-toggle');
        const storiesBadgeEl = document.getElementById('stories-badge');
        const storiesPanelEl = document.getElementById('stories-panel');
        const storiesOverlayEl = document.getElementById('stories-overlay');
        const storiesPanelCloseBtn = document.getElementById('stories-panel-close');
        const storiesFilterEl = document.getElementById('stories-filter');
        const storiesListEl = document.getElementById('stories-list');
        const storiesBrowserEl = document.getElementById('stories-browser');
        const storyReaderEl = document.getElementById('story-reader');
        const storyBackBtn = document.getElementById('story-back-btn');
        const storyTitleEl = document.getElementById('story-title');
        const storySourceEl = document.getElementById('story-source');
        const storySentenceEl = document.getElementById('story-sentence');
        const storyProgressEl = document.getElementById('story-progress');
        const storyPrevBtn = document.getElementById('story-prev-btn');
        const storyNextBtn = document.getElementById('story-next-btn');
        const historyToggleBtn = document.getElementById('history-toggle');
        const historyBadgeEl = document.getElementById('history-badge');
        const historyPanelEl = document.getElementById('history-panel');
        const historyPanelListEl = document.getElementById('history-panel-list');
        const historyOverlayEl = document.getElementById('history-overlay');
        const historyClearBtn = document.getElementById('history-clear-btn');
        const historyExportAnkiBtn = document.getElementById('history-export-anki-btn');
        const historyCopyAllBtn = document.getElementById('history-copy-all-btn');
        const historyPanelCloseBtn = document.getElementById('history-panel-close');
        const quizToggleBtn = document.getElementById('quiz-toggle');
        const quizAreaEl = document.getElementById('quiz-area');
        const quizMetaEl = document.getElementById('quiz-meta');
        const quizScoreEl = document.getElementById('quiz-score');
        const quizSentenceEl = document.getElementById('quiz-sentence');
        const quizPronunciationEl = document.getElementById('quiz-pronunciation');
        const quizSourceEl = document.getElementById('quiz-source');
        const quizHintEl = document.getElementById('quiz-hint');
        const quizAnswerInputEl = document.getElementById('quiz-answer'); // removed from HTML, may be null
        const quizCheckBtn = document.getElementById('quiz-check-btn'); // removed from HTML, may be null
        const quizResultEl = document.getElementById('quiz-result');
        const quizNextBtn = document.getElementById('quiz-next-btn');
        const quizExitBtn = document.getElementById('quiz-exit-btn');
        const LANGUAGE_TIPS = {
            ko: [
                'Korean changes formality based on who you are talking to.',
                'Sentence endings in Korean carry a lot of the tone.',
                'Particles like eun/neun and i/ga show topic and subject.'
            ],
            ja: [
                'In Japanese, context often lets you omit the subject.',
                'Sentence endings like ne and yo add nuance to intent.',
                'Polite and casual Japanese can sound very different.'
            ],
            zh: [
                'Chinese word order is often similar to English, but measure words matter.',
                'Aspect particles such as le and guo change meaning quickly.',
                'Tone changes can completely change a word.'
            ],
            es: [
                'Spanish verb endings encode person, number, and tense.',
                'Gender agreement applies to many nouns and adjectives.',
                'Formal and informal "you" forms change conjugation.'
            ],
            fr: [
                'French articles are essential and must match noun gender.',
                'Liaison can change how words connect in speech.',
                'Reflexive verbs are very common in everyday French.'
            ],
            de: [
                'German noun gender affects articles and adjective endings.',
                'Verb position changes in subordinate clauses.',
                'Cases signal each word role in the sentence.'
            ],
            default: [
                'Try short, natural phrases first, then expand complexity.',
                'Notice patterns in sentence endings to learn faster.',
                'Repetition with tiny changes helps grammar stick.'
            ]
        };
        let appPassword = localStorage.getItem(PASSWORD_STORAGE_KEY) || '';
        let sentenceHistory = loadSentenceHistory();
        let richHistory = loadRichHistory();
        let languagesLoaded = false;
        let stories = [];
        let storyPanelOpen = false;
        let storyProgress = loadStoryProgress();
        let activeStory = null;
        let activeStoryIndex = 0;
        let storyCache = {};
        let historyPanelOpen = false;
        let quizMode = false;
        let currentQuiz = null;
        let progressStats = loadProgressStats();
        let quizStats = loadQuizStats();

        const QUIZ_SCORE_LABELS = {
            perfect: '✅ Perfect',
            good: '👍 Good',
            partial: '🤔 Partial',
            wrong: '❌ Wrong'
        };

        function loadRichHistory() {
            try {
                const raw = localStorage.getItem(RICH_HISTORY_KEY) || '[]';
                const parsed = JSON.parse(raw);
                if (!Array.isArray(parsed)) return [];
                return parsed.slice(0, HISTORY_LIMIT);
            } catch { return []; }
        }

        function saveRichHistory() {
            localStorage.setItem(RICH_HISTORY_KEY, JSON.stringify(richHistory));
        }

        function loadStoryProgress() {
            try {
                const raw = localStorage.getItem(STORY_PROGRESS_KEY) || '{}';
                const parsed = JSON.parse(raw);
                if (!parsed || typeof parsed !== 'object') return {};
                return parsed;
            } catch {
                return {};
            }
        }

        function saveStoryProgress() {
            localStorage.setItem(STORY_PROGRESS_KEY, JSON.stringify(storyProgress));
        }

        function loadProgressStats() {
            const base = {
                sentencesLearned: 0,
                languagesUsed: [],
                quiz: { correct: 0, total: 0 },
                streak: 0,
                lastActivityDate: '',
                firstActivityDate: '',
                lastLearnDate: ''
            };

            try {
                const raw = localStorage.getItem(PROGRESS_STATS_KEY) || '{}';
                const parsed = JSON.parse(raw);
                if (!parsed || typeof parsed !== 'object') return base;

                const sentencesLearned = Math.max(0, Number(parsed.sentencesLearned) || 0);
                const languagesRaw = Array.isArray(parsed.languagesUsed) ? parsed.languagesUsed : [];
                const languagesUsed = [...new Set(languagesRaw
                    .map(v => (typeof v === 'string' ? v.trim().toLowerCase() : ''))
                    .filter(Boolean))];
                const quizRaw = parsed.quiz && typeof parsed.quiz === 'object' ? parsed.quiz : {};
                const quiz = {
                    correct: Math.max(0, Number(quizRaw.correct) || 0),
                    total: Math.max(0, Number(quizRaw.total) || 0)
                };
                const streak = Math.max(0, Number(parsed.streak) || 0);
                const lastActivityDate = typeof parsed.lastActivityDate === 'string' ? parsed.lastActivityDate : '';
                const firstActivityDate = typeof parsed.firstActivityDate === 'string' ? parsed.firstActivityDate : '';
                const lastLearnDate = typeof parsed.lastLearnDate === 'string' ? parsed.lastLearnDate : '';

                return {
                    sentencesLearned,
                    languagesUsed,
                    quiz,
                    streak,
                    lastActivityDate,
                    firstActivityDate,
                    lastLearnDate
                };
            } catch {
                return base;
            }
        }

        function saveProgressStats() {
            localStorage.setItem(PROGRESS_STATS_KEY, JSON.stringify(progressStats));
        }

        function todayDateKey() {
            const now = new Date();
            const year = now.getFullYear();
            const month = String(now.getMonth() + 1).padStart(2, '0');
            const day = String(now.getDate()).padStart(2, '0');
            return `${year}-${month}-${day}`;
        }

        function parseDateKey(dateKey) {
            if (!dateKey || typeof dateKey !== 'string') return null;
            const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dateKey);
            if (!match) return null;

            const year = Number(match[1]);
            const monthIndex = Number(match[2]) - 1;
            const day = Number(match[3]);
            const date = new Date(year, monthIndex, day);
            if (
                date.getFullYear() !== year ||
                date.getMonth() !== monthIndex ||
                date.getDate() !== day
            ) {
                return null;
            }
            return date;
        }

        function dayDiff(fromDateKey, toDateKey) {
            const from = parseDateKey(fromDateKey);
            const to = parseDateKey(toDateKey);
            if (!from || !to) return null;
            return Math.round((to.getTime() - from.getTime()) / MS_PER_DAY);
        }

        function formatDateLabel(dateKey) {
            const parsed = parseDateKey(dateKey);
            if (!parsed) return '';
            return parsed.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
        }

        function addProgressLanguage(languageCode) {
            const code = typeof languageCode === 'string' ? languageCode.trim().toLowerCase() : '';
            if (!code) return;
            if (!progressStats.languagesUsed.includes(code)) {
                progressStats.languagesUsed.push(code);
            }
        }

        function renderProgressLanguages() {
            if (!statsLanguagesEl) return;
            statsLanguagesEl.innerHTML = '';

            const langNames = getLanguageNamesMap();
            if (!progressStats.languagesUsed.length) {
                const empty = document.createElement('span');
                empty.className = 'progress-stat-value';
                empty.textContent = 'No languages yet';
                statsLanguagesEl.appendChild(empty);
                return;
            }

            progressStats.languagesUsed.forEach(code => {
                const chip = document.createElement('span');
                chip.className = 'progress-lang-chip';
                const flag = LANG_FLAGS[code] || '🌐';
                const name = langNames[code] || code.toUpperCase();
                chip.textContent = `${flag} ${name}`;
                statsLanguagesEl.appendChild(chip);
            });
        }

        function renderProgressStats() {
            if (!statsTotalSentencesEl) return;

            statsTotalSentencesEl.textContent = String(progressStats.sentencesLearned || 0);
            renderProgressLanguages();

            const quizTotal = Math.max(0, Number(progressStats.quiz?.total) || 0);
            const quizCorrect = Math.max(0, Number(progressStats.quiz?.correct) || 0);
            if (quizTotal > 0) {
                const accuracy = Math.round((quizCorrect / quizTotal) * 100);
                statsQuizAccuracyEl.textContent = `${accuracy}% (${quizCorrect}/${quizTotal})`;
            } else {
                statsQuizAccuracyEl.textContent = 'No quizzes taken yet';
            }

            const streak = Math.max(0, Number(progressStats.streak) || 0);
            statsStreakEl.textContent = `${streak} ${streak === 1 ? 'day' : 'days'}`;

            const learningSince = formatDateLabel(progressStats.firstActivityDate);
            statsLearningSinceEl.textContent = learningSince || 'Not started yet';
        }

        function persistProgressAndRefresh() {
            saveProgressStats();
            renderProgressStats();
        }

        function recordLearnProgress(languageCode, learnedCount = 1) {
            const increment = Math.max(0, Number(learnedCount) || 0);
            if (increment < 1) return;

            const today = todayDateKey();
            if (!progressStats.firstActivityDate) {
                progressStats.firstActivityDate = today;
            }
            progressStats.lastActivityDate = today;
            progressStats.sentencesLearned += increment;
            addProgressLanguage(languageCode);

            if (!progressStats.lastLearnDate) {
                progressStats.streak = 1;
                progressStats.lastLearnDate = today;
            } else if (progressStats.lastLearnDate !== today) {
                const diff = dayDiff(progressStats.lastLearnDate, today);
                progressStats.streak = diff === 1 ? progressStats.streak + 1 : 1;
                progressStats.lastLearnDate = today;
            }

            persistProgressAndRefresh();
        }

        function loadQuizStats() {
            const quiz = progressStats.quiz && typeof progressStats.quiz === 'object' ? progressStats.quiz : {};
            return {
                correct: Math.max(0, Number(quiz.correct) || 0),
                total: Math.max(0, Number(quiz.total) || 0)
            };
        }

        function saveQuizStats() {
            progressStats.quiz = {
                correct: Math.max(0, Number(quizStats.correct) || 0),
                total: Math.max(0, Number(quizStats.total) || 0)
            };
            persistProgressAndRefresh();
        }

        function recordQuizCompletion(isCorrect, languageCode) {
            const today = todayDateKey();
            if (!progressStats.firstActivityDate) {
                progressStats.firstActivityDate = today;
            }
            progressStats.lastActivityDate = today;
            addProgressLanguage(languageCode);

            quizStats.total += 1;
            if (isCorrect) quizStats.correct += 1;
            saveQuizStats();
            renderQuizScore();
        }

        function renderQuizScore() {
            quizScoreEl.textContent = `${quizStats.correct}/${quizStats.total}`;
        }

        function renderQuizMeta() {
            const selectedLang = langSelect.value;
            const flag = LANG_FLAGS[selectedLang] || '🌐';
            const langName = langSelect.options[langSelect.selectedIndex]?.textContent || selectedLang || '';
            quizMetaEl.textContent = `${flag} ${langName} • Meaning match`;
        }

        function clearQuizResult() {
            quizResultEl.className = 'quiz-result hidden';
            quizResultEl.innerHTML = '';
        }

        function showQuizResult(result) {
            const score = ['perfect', 'good', 'partial', 'wrong'].includes(result.score) ? result.score : 'wrong';
            const label = QUIZ_SCORE_LABELS[score];
            const answer = result.correct_answer || 'N/A';
            const feedback = result.feedback || '';
            quizResultEl.innerHTML = `
                <div class="quiz-result-head">${label}</div>
                <div class="quiz-result-answer"><strong>Correct answer:</strong> ${answer}</div>
                <div class="quiz-result-feedback">${feedback}</div>
            `;
            quizResultEl.className = `quiz-result ${score}`;
            // Restart reveal animation each time new feedback appears.
            void quizResultEl.offsetWidth;
            quizResultEl.classList.add('show');
        }

        async function loadQuizQuestion() {
            if (!ensurePassword()) return;
            if (!languagesLoaded) await loadLanguages();

            renderQuizMeta();
            clearQuizResult();
            currentQuiz = null;

            const choicesEl = document.getElementById('quiz-choices');
            choicesEl.innerHTML = '';
            quizSentenceEl.textContent = 'Loading...';
            quizPronunciationEl.textContent = '';
            quizSourceEl.textContent = '';
            quizHintEl.textContent = '';
            quizNextBtn.disabled = true;

            // Get history items for current target language
            const histItems = richHistory
                .filter(e => e.lang === langSelect.value && e.result && e.result.translation)
                .map(e => ({ sentence: e.sentence, translation: e.result.translation, pronunciation: e.result.pronunciation }));

            if (histItems.length < 2) {
                quizSentenceEl.textContent = 'Learn at least 2 sentences first!';
                quizSourceEl.textContent = 'Go back and translate some sentences, then try the quiz.';
                quizNextBtn.disabled = false;
                return;
            }

            // Pick a random question from history
            const qIdx = Math.floor(Math.random() * histItems.length);
            const question = histItems[qIdx];

            // Randomly decide: show translation → pick meaning, or show meaning → pick translation
            const showTranslation = Math.random() > 0.5;

            if (showTranslation) {
                // Show target language, pick the correct input sentence
                document.getElementById('quiz-label').textContent = 'What does this mean?';
                quizSentenceEl.textContent = question.translation;
                quizPronunciationEl.textContent = question.pronunciation ? question.pronunciation : '';
                
                // Build wrong answers from other history items
                const wrongItems = histItems.filter((_, i) => i !== qIdx);
                const shuffledWrong = wrongItems.sort(() => Math.random() - 0.5).slice(0, 3);
                const choices = shuffledWrong.map(w => ({ text: w.sentence, correct: false }));
                choices.push({ text: question.sentence, correct: true });
                choices.sort(() => Math.random() - 0.5);

                currentQuiz = { correctAnswer: question.sentence, choices };
            } else {
                // Show input sentence, pick the correct translation
                document.getElementById('quiz-label').textContent = 'How do you say this?';
                quizSentenceEl.textContent = question.sentence;
                quizPronunciationEl.textContent = '';

                const wrongItems = histItems.filter((_, i) => i !== qIdx);
                const shuffledWrong = wrongItems.sort(() => Math.random() - 0.5).slice(0, 3);
                const choices = shuffledWrong.map(w => ({ text: w.translation, correct: false }));
                choices.push({ text: question.translation, correct: true });
                choices.sort(() => Math.random() - 0.5);

                currentQuiz = { correctAnswer: question.translation, choices };
            }

            quizSourceEl.textContent = 'From your history';

            // Render choice buttons
            currentQuiz.choices.forEach(choice => {
                const btn = document.createElement('button');
                btn.type = 'button';
                btn.textContent = choice.text;
                btn.style.cssText = 'padding:0.75rem 1rem;border-radius:var(--radius);border:1px solid var(--border);background:var(--surface2);color:var(--text);font-size:0.95rem;cursor:pointer;text-align:left;transition:all 0.2s;';
                btn.addEventListener('click', () => {
                    // Disable all buttons
                    choicesEl.querySelectorAll('button').forEach(b => { b.disabled = true; b.style.cursor = 'default'; });
                    
                    if (choice.correct) {
                        btn.style.background = '#1a4a2a';
                        btn.style.borderColor = 'var(--easy)';
                        btn.style.color = 'var(--easy)';
                        quizCorrect++;
                        updateProgressStats('quiz_correct');
                    } else {
                        btn.style.background = '#4a1a1a';
                        btn.style.borderColor = 'var(--hard)';
                        btn.style.color = 'var(--hard)';
                        // Highlight correct answer
                        choicesEl.querySelectorAll('button').forEach(b => {
                            if (b.textContent === currentQuiz.correctAnswer) {
                                b.style.background = '#1a4a2a';
                                b.style.borderColor = 'var(--easy)';
                                b.style.color = 'var(--easy)';
                            }
                        });
                        updateProgressStats('quiz_wrong');
                    }
                    quizTotal++;
                    quizScoreEl.textContent = `${quizCorrect}/${quizTotal}`;
                    quizNextBtn.disabled = false;
                });
                choicesEl.appendChild(btn);
            });

            quizNextBtn.disabled = true;
        }

        async function checkQuizAnswer() {
            if (!ensurePassword()) return;
            if (!currentQuiz) return;

            const answer = quizAnswerInputEl.value.trim();
            if (!answer) {
                quizAnswerInputEl.focus();
                return;
            }

            const originalLabel = quizCheckBtn.textContent;
            quizCheckBtn.disabled = true;
            quizCheckBtn.textContent = 'Checking...';

            try {
                const resp = await fetch('/api/quiz-check', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-App-Password': appPassword
                    },
                    body: JSON.stringify({
                        quiz_id: currentQuiz.quiz_id,
                        answer,
                        target_language: currentQuiz.language
                    })
                });

                if (resp.status === 401) {
                    localStorage.removeItem(PASSWORD_STORAGE_KEY);
                    appPassword = '';
                    openPasswordModal('Session expired. Enter password again.');
                    return;
                }
                if (!resp.ok) throw new Error(await friendlyError(resp));

                const data = await resp.json();
                recordQuizCompletion(Boolean(data.correct), currentQuiz.language || langSelect.value);
                showQuizResult(data);
            } catch (err) {
                console.error(err);
                clearQuizResult();
                quizResultEl.innerHTML = '<div class="quiz-result-feedback">Could not check this answer. Try again.</div>';
                quizResultEl.className = 'quiz-result wrong show';
            } finally {
                quizCheckBtn.textContent = originalLabel;
                quizCheckBtn.disabled = false;
            }
        }

        async function enterQuizMode() {
            if (!ensurePassword()) return;
            quizMode = true;
            document.body.classList.add('quiz-mode');
            quizAreaEl.classList.remove('hidden');
            quizToggleBtn.classList.add('active');
            renderQuizScore();
            await loadQuizQuestion();
        }

        function exitQuizMode() {
            quizMode = false;
            currentQuiz = null;
            document.body.classList.remove('quiz-mode');
            quizAreaEl.classList.add('hidden');
            quizToggleBtn.classList.remove('active');
            clearQuizResult();
        }

        async function toggleQuizMode() {
            if (quizMode) {
                exitQuizMode();
                return;
            }
            await enterQuizMode();
        }

        function updateStoriesBadge() {
            if (!storiesBadgeEl) return;
            const selectedLang = langSelect.value;
            const count = selectedLang ? stories.filter(s => s.language === selectedLang).length : stories.length;
            storiesBadgeEl.textContent = count;
        }

        function getStoryProgress(storyId, sentenceCount) {
            const raw = Number(storyProgress[storyId] || 0);
            if (!Number.isFinite(raw) || raw < 0) return 0;
            if (!sentenceCount || sentenceCount < 1) return 0;
            return Math.min(raw, sentenceCount - 1);
        }

        function setStoryProgress(storyId, index) {
            if (!storyId || !Number.isFinite(index) || index < 0) return;
            storyProgress[storyId] = index;
            saveStoryProgress();
        }

        function addToRichHistory(sentence, translation, targetLang, pronunciation) {
            const entry = {
                sentence,
                translation,
                lang: targetLang,
                pronunciation: pronunciation || '',
                ts: Date.now()
            };
            // Remove duplicate
            richHistory = richHistory.filter(e => !(e.sentence === sentence && e.lang === targetLang));
            richHistory.unshift(entry);
            richHistory = richHistory.slice(0, HISTORY_LIMIT);
            saveRichHistory();
            renderHistoryPanel();
            updateHistoryBadge();
        }

        function getLanguageNamesMap() {
            const langNames = {};
            langSelect.querySelectorAll('option').forEach(o => { langNames[o.value] = o.textContent; });
            return langNames;
        }

        function buildHistoryCopyText() {
            const langNames = getLanguageNamesMap();
            return richHistory.map((entry, idx) => {
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

        function buildHistoryAnkiPayload() {
            return richHistory.map(entry => ({
                sentence: entry.sentence || '',
                translation: entry.translation || '',
                pronunciation: entry.pronunciation || '',
                target: entry.lang || '',
                timestamp: entry.ts ? new Date(entry.ts).toISOString() : ''
            }));
        }

        async function exportHistoryAsAnki() {
            if (!ensurePassword()) return;
            if (richHistory.length === 0) {
                alert('No history to export yet.');
                return;
            }

            const originalLabel = historyExportAnkiBtn.textContent;
            historyExportAnkiBtn.disabled = true;
            historyExportAnkiBtn.textContent = 'Exporting...';

            try {
                const resp = await fetch('/api/export-anki', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-App-Password': appPassword
                    },
                    body: JSON.stringify(buildHistoryAnkiPayload())
                });

                if (resp.status === 401) {
                    localStorage.removeItem(PASSWORD_STORAGE_KEY);
                    appPassword = '';
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
                historyExportAnkiBtn.textContent = 'Done';
            } catch (err) {
                console.error(err);
                alert('Could not export Anki file.');
                historyExportAnkiBtn.textContent = 'Failed';
            } finally {
                setTimeout(() => {
                    historyExportAnkiBtn.textContent = originalLabel;
                    historyExportAnkiBtn.disabled = false;
                }, 1000);
            }
        }

        async function copyAllHistoryToClipboard() {
            if (richHistory.length === 0) {
                alert('No history to copy yet.');
                return;
            }

            const originalLabel = historyCopyAllBtn.textContent;
            historyCopyAllBtn.disabled = true;
            try {
                const copied = await copyTextToClipboard(buildHistoryCopyText());
                historyCopyAllBtn.textContent = copied ? 'Copied' : 'Failed';
            } catch (err) {
                console.error(err);
                historyCopyAllBtn.textContent = 'Failed';
            } finally {
                setTimeout(() => {
                    historyCopyAllBtn.textContent = originalLabel;
                    historyCopyAllBtn.disabled = false;
                }, 1000);
            }
        }

        function toggleHistoryPanel() {
            historyPanelOpen = !historyPanelOpen;
            historyPanelEl.classList.toggle('open', historyPanelOpen);
            historyOverlayEl.classList.toggle('open', historyPanelOpen);
        }

        function openHistoryPanel() {
            historyPanelOpen = true;
            historyPanelEl.classList.add('open');
            historyOverlayEl.classList.add('open');
            renderHistoryPanel();
        }

        function closeHistoryPanel() {
            historyPanelOpen = false;
            historyPanelEl.classList.remove('open');
            historyOverlayEl.classList.remove('open');
        }

        function updateHistoryBadge() {
            const count = richHistory.length;
            historyBadgeEl.textContent = count;
            historyToggleBtn.classList.toggle('hidden', count === 0);
        }

        function renderHistoryPanel() {
            if (richHistory.length === 0) {
                historyPanelListEl.innerHTML = '<div class="history-panel-empty">No sentences yet. Start learning!</div>';
                return;
            }
            const langNames = getLanguageNamesMap();

            historyPanelListEl.innerHTML = richHistory.map((entry, idx) => {
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

            historyPanelListEl.querySelectorAll('.history-panel-item').forEach(item => {
                item.addEventListener('click', () => {
                    const idx = parseInt(item.dataset.idx);
                    const entry = richHistory[idx];
                    if (entry) {
                        sentenceInput.value = entry.sentence;
                        sentenceInput.style.height = 'auto';
                        sentenceInput.style.height = sentenceInput.scrollHeight + 'px';
                        if (entry.lang) selectLangPill(entry.lang);
                        closeHistoryPanel();
                        sentenceInput.focus();
                    }
                });
            });
        }

        historyToggleBtn.addEventListener('click', toggleHistoryPanel);
        historyOverlayEl.addEventListener('click', closeHistoryPanel);
        historyPanelCloseBtn.addEventListener('click', closeHistoryPanel);
        historyExportAnkiBtn.addEventListener('click', exportHistoryAsAnki);
        historyCopyAllBtn.addEventListener('click', copyAllHistoryToClipboard);
        statsToggleBtn.addEventListener('click', openStatsModal);
        statsModalCloseBtn.addEventListener('click', closeStatsModal);
        statsModalEl.addEventListener('click', (e) => {
            if (e.target === statsModalEl) closeStatsModal();
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && !statsModalEl.classList.contains('hidden')) {
                closeStatsModal();
            }
        });
        historyClearBtn.addEventListener('click', () => {
            if (confirm('Clear all history?')) {
                richHistory = [];
                sentenceHistory = [];
                saveRichHistory();
                localStorage.setItem(SENTENCE_HISTORY_KEY, '[]');
                renderHistoryPanel();
                renderSentenceHistory();
                updateHistoryBadge();
            }
        });

        updateHistoryBadge();
        renderProgressStats();

        function lockApp() {
            sentenceInput.disabled = true;
            langSelect.disabled = true;
            learnBtn.disabled = true;
            if (compareBtn) compareBtn.disabled = true;
        }

        function unlockApp() {
            sentenceInput.disabled = false;
            langSelect.disabled = false;
            learnBtn.disabled = false;
            if (compareBtn) compareBtn.disabled = false;
        }

        function showPasswordError(message) {
            passwordErrorEl.textContent = message;
            passwordErrorEl.classList.remove('hidden');
        }

        function hidePasswordError() {
            passwordErrorEl.classList.add('hidden');
        }

        function syncModalOpenState() {
            const modalOpen = !passwordModalEl.classList.contains('hidden') || !statsModalEl.classList.contains('hidden');
            document.body.classList.toggle('modal-open', modalOpen);
        }

        function openStatsModal() {
            renderProgressStats();
            statsModalEl.classList.remove('hidden');
            syncModalOpenState();
        }

        function closeStatsModal() {
            statsModalEl.classList.add('hidden');
            syncModalOpenState();
        }

        function openPasswordModal(message = '') {
            lockApp();
            passwordModalEl.classList.remove('hidden');
            syncModalOpenState();
            passwordInputEl.value = '';
            if (message) {
                showPasswordError(message);
            } else {
                hidePasswordError();
            }
            requestAnimationFrame(() => passwordInputEl.focus());
        }

        function closePasswordModal() {
            passwordModalEl.classList.add('hidden');
            syncModalOpenState();
            hidePasswordError();
        }

        function ensurePassword() {
            if (appPassword === APP_PASSWORD) return true;
            openPasswordModal();
            return false;
        }

        function loadSentenceHistory() {
            try {
                const raw = localStorage.getItem(SENTENCE_HISTORY_KEY) || '[]';
                const parsed = JSON.parse(raw);
                if (!Array.isArray(parsed)) return [];
                return parsed
                    .filter(item => typeof item === 'string' && item.trim())
                    .slice(0, HISTORY_LIMIT);
            } catch {
                return [];
            }
        }

        const RECENT_DISPLAY_LIMIT = 4;

        function renderSentenceHistory() {
            sentenceHistoryEl.innerHTML = '';
            if (sentenceHistory.length === 0) {
                sentenceHistoryWrapEl.classList.add('hidden');
                return;
            }

            sentenceHistoryWrapEl.classList.remove('hidden');
            const displayItems = sentenceHistory.slice(0, RECENT_DISPLAY_LIMIT);
            displayItems.forEach((sentence) => {
                const chip = document.createElement('button');
                chip.type = 'button';
                chip.className = 'history-chip';
                chip.textContent = sentence;
                chip.title = sentence;
                chip.addEventListener('click', () => {
                    sentenceInput.value = sentence;
                    sentenceInput.style.height = 'auto';
                    sentenceInput.style.height = sentenceInput.scrollHeight + 'px';
                    sentenceInput.focus();
                });
                sentenceHistoryEl.appendChild(chip);
            });
            if (sentenceHistory.length > RECENT_DISPLAY_LIMIT) {
                const moreBtn = document.createElement('button');
                moreBtn.type = 'button';
                moreBtn.className = 'history-chip';
                moreBtn.style.cssText = 'background:rgba(99,102,241,0.25);color:#a5b4fc;font-weight:600;';
                moreBtn.textContent = `View all (${sentenceHistory.length}) →`;
                moreBtn.addEventListener('click', () => {
                    openHistoryPanel();
                });
                sentenceHistoryEl.appendChild(moreBtn);
            }
        }

        function saveSentenceToHistory(sentence) {
            const cleanSentence = sentence.trim();
            if (!cleanSentence) return;
            sentenceHistory = [cleanSentence, ...sentenceHistory.filter(item => item !== cleanSentence)].slice(0, HISTORY_LIMIT);
            localStorage.setItem(SENTENCE_HISTORY_KEY, JSON.stringify(sentenceHistory));
            renderSentenceHistory();
        }

        function setRandomLoadingTip() {
            const selectedLang = langSelect.value;
            const langName = langSelect.options[langSelect.selectedIndex]?.textContent || 'this language';
            const tips = LANGUAGE_TIPS[selectedLang] || LANGUAGE_TIPS.default;
            const randomTip = tips[Math.floor(Math.random() * tips.length)];
            loadingTipEl.textContent = `${langName} tip: ${randomTip}`;
        }

        // === TTS / Speech ===
        const LANG_SPEECH_MAP = {
            ko: 'ko-KR', ja: 'ja-JP', zh: 'zh-TW', en: 'en-US',
            he: 'he-IL', el: 'el-GR', it: 'it-IT', es: 'es-ES',
            fr: 'fr-FR', de: 'de-DE', pt: 'pt-BR', ar: 'ar-SA',
            th: 'th-TH', vi: 'vi-VN', hi: 'hi-IN', ru: 'ru-RU'
        };

        function speakTranslation(text, langCode, btn) {
            if (!window.speechSynthesis) return;
            // Stop any current speech
            speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.lang = LANG_SPEECH_MAP[langCode] || langCode;
            utterance.rate = 0.9;
            // Try to find the best matching voice — prefer non-compact, local voices
            const voices = speechSynthesis.getVoices();
            const exactVoices = voices.filter(v => v.lang === utterance.lang);
            const prefixVoices = voices.filter(v => v.lang.startsWith(langCode));
            const candidates = exactVoices.length > 0 ? exactVoices : prefixVoices;
            // Prefer local (non-remote) voices, then by name (avoid "compact" variants)
            const sorted = candidates.sort((a, b) => {
                const aLocal = !a.localService ? 1 : 0;
                const bLocal = !b.localService ? 1 : 0;
                if (aLocal !== bLocal) return aLocal - bLocal;
                const aCompact = a.name.toLowerCase().includes('compact') ? 1 : 0;
                const bCompact = b.name.toLowerCase().includes('compact') ? 1 : 0;
                return aCompact - bCompact;
            });
            if (sorted.length > 0) utterance.voice = sorted[0];
            if (btn) {
                btn.classList.add('speaking');
                const label = btn.querySelector('.speak-label');
                if (label) label.textContent = '▶ Playing';
                utterance.onend = () => {
                    btn.classList.remove('speaking');
                    if (label) label.textContent = 'Listen';
                };
                utterance.onerror = () => {
                    btn.classList.remove('speaking');
                    if (label) label.textContent = 'Listen';
                };
            }
            speechSynthesis.speak(utterance);
        }

        // Pre-load voices
        if (window.speechSynthesis) {
            speechSynthesis.getVoices();
            speechSynthesis.onvoiceschanged = () => speechSynthesis.getVoices();
        }

        async function copyTextToClipboard(text) {
            if (navigator.clipboard && window.isSecureContext) {
                await navigator.clipboard.writeText(text);
                return true;
            }

            const fallbackArea = document.createElement('textarea');
            fallbackArea.value = text;
            fallbackArea.setAttribute('readonly', '');
            fallbackArea.style.position = 'fixed';
            fallbackArea.style.opacity = '0';
            document.body.appendChild(fallbackArea);
            fallbackArea.select();

            let copied = false;
            try {
                copied = document.execCommand('copy');
            } catch {
                copied = false;
            }

            document.body.removeChild(fallbackArea);
            return copied;
        }

        // --- Onboarding ---
        const ONBOARDED_KEY = 'sent-say_onboarded';
        const onboardingOverlay = document.getElementById('onboarding-overlay');

        function showOnboarding() {
            if (localStorage.getItem(ONBOARDED_KEY)) return;
            if (richHistory.length > 0 || sentenceHistory.length > 0) {
                localStorage.setItem(ONBOARDED_KEY, '1');
                return;
            }
            onboardingOverlay.classList.remove('hidden');
        }

        function dismissOnboarding() {
            onboardingOverlay.classList.add('hidden');
            localStorage.setItem(ONBOARDED_KEY, '1');
        }

        document.querySelectorAll('.onboarding-suggestion').forEach(btn => {
            btn.addEventListener('click', () => {
                const sentence = btn.dataset.sentence;
                const lang = btn.dataset.lang;
                dismissOnboarding();
                // Wait for languages to load, then select + fill + submit
                const tryFill = () => {
                    if (languagesLoaded) {
                        if (lang) selectLangPill(lang);
                        sentenceInput.value = sentence;
                        sentenceInput.style.height = 'auto';
                        sentenceInput.style.height = sentenceInput.scrollHeight + 'px';
                        learn();
                    } else {
                        setTimeout(tryFill, 200);
                    }
                };
                tryFill();
            });
        });

        document.getElementById('onboarding-skip').addEventListener('click', () => {
            dismissOnboarding();
            sentenceInput.focus();
        });

        // Show onboarding after password check passes
        if (appPassword === APP_PASSWORD) {
            showOnboarding();
        }
        // Also hook into password submit success
        const _origCloseModal = closePasswordModal;
        closePasswordModal = function() {
            _origCloseModal();
            setTimeout(showOnboarding, 300);
        };

        // === Speculative Typing (Learn as you type) ===
        let speculativeTimer = null;
        let speculativeController = null;
        let speculativeCache = {};
        let speculativePending = false;

        function getSpeculativeKey() {
            const sentence = sentenceInput.value.trim();
            if (!sentence || sentence.length < 3) return null;
            return `${sentence}|${langSelect.value}|${selectedInputLang}|${selectedGender}|${selectedFormality}`;
        }

        function showSpeculativeIndicator() {
            let indicator = document.getElementById('speculative-indicator');
            if (!indicator) {
                indicator = document.createElement('div');
                indicator.id = 'speculative-indicator';
                indicator.style.cssText = 'font-size:0.72rem;color:var(--accent);margin-top:0.4rem;opacity:0.8;display:flex;align-items:center;gap:0.35rem;';
                indicator.innerHTML = '<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--accent);animation:specPulse 1.2s ease-in-out infinite;"></span> Preparing translation...';
                const inputArea = document.querySelector('.sentence-input');
                inputArea.parentNode.insertBefore(indicator, inputArea.nextSibling);
            }
            indicator.style.display = 'flex';
        }

        function hideSpeculativeIndicator() {
            const indicator = document.getElementById('speculative-indicator');
            if (indicator) indicator.style.display = 'none';
        }

        function cancelSpeculative() {
            if (speculativeTimer) { clearTimeout(speculativeTimer); speculativeTimer = null; }
            if (speculativeController) { speculativeController.abort(); speculativeController = null; }
            speculativePending = false;
            hideSpeculativeIndicator();
        }

        async function startSpeculative() {
            const key = getSpeculativeKey();
            if (!key || appPassword !== APP_PASSWORD) return;
            if (speculativeCache[key]) return;

            speculativePending = true;
            speculativeController = new AbortController();
            showSpeculativeIndicator();

            const sentence = sentenceInput.value.trim();
            try {
                const resp = await fetch('/api/learn', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-App-Password': appPassword },
                    body: JSON.stringify({
                        sentence,
                        target_language: langSelect.value,
                        input_language: selectedInputLang,
                        speaker_gender: selectedGender,
                        speaker_formality: selectedFormality,
                    }),
                    signal: speculativeController.signal,
                });
                if (resp.ok) {
                    const data = await resp.json();
                    speculativeCache[key] = { data, sentence };
                    // Show ready indicator briefly
                    const indicator = document.getElementById('speculative-indicator');
                    if (indicator && sentenceInput.value.trim() === sentence) {
                        indicator.innerHTML = '<span style="color:var(--easy);">✓</span> Ready — press Learn';
                        setTimeout(() => hideSpeculativeIndicator(), 3000);
                    }
                }
            } catch (e) {
                // aborted or error — ignore
            } finally {
                speculativePending = false;
                if (!speculativeCache[getSpeculativeKey()]) hideSpeculativeIndicator();
            }
        }

        // Hook speculative into input events
        sentenceInput.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = this.scrollHeight + 'px';
            cancelSpeculative();
            if (this.value.trim().length >= 3) {
                speculativeTimer = setTimeout(() => startSpeculative(), 1500);
            }
        });

        // IME composition tracking (注音, etc.)
        let isComposing = false;
        sentenceInput.addEventListener('compositionstart', () => { isComposing = true; cancelSpeculative(); });
        sentenceInput.addEventListener('compositionend', () => { isComposing = false; });

        // Enter to submit (skip during IME composition)
        sentenceInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey && !isComposing) {
                e.preventDefault();
                learn();
            }
        });

        const TARGET_LANG_KEY = 'sent-say_target_lang';

        function selectLangPill(code) {
            langSelect.value = code;
            localStorage.setItem(TARGET_LANG_KEY, code);
            langPillsEl.querySelectorAll('.lang-pill').forEach(p => {
                p.classList.toggle('active', p.dataset.lang === code);
            });
        }

        async function loadLanguages() {
            if (languagesLoaded) return;
            const langs = await fetch('/api/languages').then(r => r.json());
            langPillsEl.innerHTML = '';
            for (const [code, name] of Object.entries(langs)) {
                // Hidden select for compatibility
                const opt = document.createElement('option');
                opt.value = code;
                opt.textContent = name;
                langSelect.appendChild(opt);
                // Pill button
                const pill = document.createElement('button');
                pill.type = 'button';
                pill.className = 'lang-pill';
                pill.dataset.lang = code;
                const flag = LANG_FLAGS[code] || '🌐';
                pill.innerHTML = `<span class="flag">${flag}</span>${name}`;
                pill.addEventListener('click', () => selectLangPill(code));
                langPillsEl.appendChild(pill);
            }
            // Default to Chinese, or restore saved preference
            const savedLang = localStorage.getItem(TARGET_LANG_KEY);
            const defaultLang = (savedLang && Object.prototype.hasOwnProperty.call(langs, savedLang)) ? savedLang : (Object.prototype.hasOwnProperty.call(langs, 'zh') ? 'zh' : Object.keys(langs)[0]);
            if (defaultLang) selectLangPill(defaultLang);
            languagesLoaded = true;
            renderHistoryPanel();
            renderProgressStats();
        }

        passwordFormEl.addEventListener('submit', async function(e) {
            e.preventDefault();
            const entered = passwordInputEl.value.trim();
            if (entered !== APP_PASSWORD) {
                showPasswordError('Incorrect password. Try again.');
                passwordInputEl.select();
                return;
            }

            appPassword = APP_PASSWORD;
            localStorage.setItem(PASSWORD_STORAGE_KEY, APP_PASSWORD);
            closePasswordModal();
            unlockApp();

            try {
                await loadLanguages();
            } catch (err) {
                console.error(err);
                alert('Failed to load languages.');
            }
        });

        renderSentenceHistory();
        // Always load languages (not gated by password)
        loadLanguages().catch(err => {
            console.error(err);
            alert('Failed to load languages.');
        });
        if (ensurePassword()) {
            unlockApp();
        }

        const loadingMessageEl = document.getElementById('loading-message');
        const loadingElapsedEl = document.getElementById('loading-elapsed');
        const loadingCancelBtn = document.getElementById('loading-cancel');
        const errorBannerEl = document.getElementById('error-banner');
        const errorMessageEl = document.getElementById('error-message');
        const retryBtnEl = document.getElementById('retry-btn');
        let currentAbortController = null;
        let loadingTimer = null;
        let lastLearnSentence = '';
        let lastActionType = 'learn';

        const LOADING_PHASES = [
            { at: 0, msg: 'Translating...' },
            { at: 3, msg: 'Analyzing grammar...' },
            { at: 7, msg: 'Building word breakdown...' },
            { at: 12, msg: 'Adding pronunciation...' },
            { at: 18, msg: 'Almost there...' },
            { at: 25, msg: 'Still working — complex sentence!' },
            { at: 35, msg: 'Hang tight, wrapping up...' },
        ];

        function startLoadingTimer() {
            const start = Date.now();
            loadingCancelBtn.style.display = 'none';
            loadingElapsedEl.textContent = '';
            loadingTimer = setInterval(() => {
                const elapsed = Math.floor((Date.now() - start) / 1000);
                loadingElapsedEl.textContent = elapsed + 's';
                // Progressive messages
                for (let i = LOADING_PHASES.length - 1; i >= 0; i--) {
                    if (elapsed >= LOADING_PHASES[i].at) {
                        loadingMessageEl.textContent = LOADING_PHASES[i].msg;
                        break;
                    }
                }
                // Show cancel after 8s
                if (elapsed >= 8) loadingCancelBtn.style.display = 'inline-block';
            }, 1000);
        }

        function stopLoadingTimer() {
            if (loadingTimer) { clearInterval(loadingTimer); loadingTimer = null; }
        }

        function showError(msg) {
            errorMessageEl.textContent = msg;
            errorBannerEl.style.display = 'block';
        }

        function hideError() { errorBannerEl.style.display = 'none'; }

        // Extract user-friendly error from a failed fetch response
        async function friendlyError(resp) {
            const status = resp.status;
            // Try to get detail from JSON body
            let detail = '';
            try {
                const body = await resp.json();
                detail = body.detail || '';
            } catch { /* ignore */ }

            if (status === 429) return 'Too many requests — wait a moment and try again.';
            if (status === 502) return 'Translation model is unreachable. Is Ollama running?';
            if (status === 400 && detail) return detail;
            if (status === 401) return ''; // handled separately
            if (detail) return detail;
            return `Something went wrong (${status}). Tap retry.`;
        }

        function closeCompareResults() {
            compareResultsEl.classList.add('hidden');
            compareResultsEl.innerHTML = '';
        }

        function renderCompareResults(data) {
            const results = Array.isArray(data.results) ? data.results : [];
            const originalSentence = data.sentence || sentenceInput.value.trim();
            const cardsHTML = results.map(entry => {
                const code = (entry.language || '').toLowerCase();
                const flag = LANG_FLAGS[code] || '🌐';
                const languageName = entry.language_name || code.toUpperCase() || 'Language';
                const translation = entry.translation || 'No translation';
                const pronunciation = entry.pronunciation || 'Pronunciation unavailable';
                const literal = entry.literal || 'No literal translation';
                return `
                    <div class="compare-card">
                        <div class="compare-card-lang"><span class="flag">${flag}</span>${languageName}</div>
                        <div class="compare-card-translation">${translation}</div>
                        <div class="compare-card-pronunciation">${pronunciation}</div>
                        <div class="compare-card-literal">Literal: ${literal}</div>
                    </div>
                `;
            }).join('');

            compareResultsEl.innerHTML = `
                <div class="compare-results-head">
                    <div class="compare-results-label">Comparison mode</div>
                    <button type="button" class="compare-close-btn" id="compare-close-btn">✕ Close</button>
                </div>
                <div class="compare-results-source">"${originalSentence}"</div>
                ${results.length ? `<div class="compare-grid">${cardsHTML}</div>` : '<div class="compare-empty">No comparison results returned.</div>'}
            `;
            const closeBtn = document.getElementById('compare-close-btn');
            if (closeBtn) closeBtn.addEventListener('click', closeCompareResults);
            compareResultsEl.classList.remove('hidden');
            compareResultsEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }

        loadingCancelBtn.addEventListener('click', () => {
            if (currentAbortController) currentAbortController.abort();
        });

        retryBtnEl.addEventListener('click', () => {
            hideError();
            if (lastLearnSentence) {
                sentenceInput.value = lastLearnSentence;
                if (lastActionType === 'compare') {
                    compareSentence();
                } else {
                    learn();
                }
            }
        });

        const LEARN_TIMEOUT_MS = 45000;

        function _hasMultipleSentences(text) {
            // Split on sentence terminators; if >1 non-empty part, it's multi
            const parts = text.split(/(?<=[.!?。！？])\s*/).filter(s => s.trim());
            return parts.length > 1;
        }

        async function learn() {
            if (!ensurePassword()) return;

            const sentence = sentenceInput.value.trim();
            if (!sentence) return;
            lastLearnSentence = sentence;
            lastActionType = 'learn';
            hideError();

            // Check speculative cache first
            const specKey = getSpeculativeKey();
            if (specKey && speculativeCache[specKey]) {
                const cached = speculativeCache[specKey];
                delete speculativeCache[specKey];
                cancelSpeculative();
                const reqCtx = { target_language: langSelect.value, input_language: selectedInputLang, sentence: cached.sentence };
                renderResult(cached.data, cached.sentence, reqCtx);
                saveSentenceToHistory(cached.sentence);
                addToRichHistory(cached.sentence, cached.data.translation, langSelect.value, cached.data.pronunciation);
                recordLearnProgress(langSelect.value, 1);
                sentenceInput.value = '';
                sentenceInput.style.height = 'auto';
                return;
            }
            cancelSpeculative();

            learnBtn.disabled = true;
            if (compareBtn) compareBtn.disabled = true;
            setRandomLoadingTip();
            loadingEl.classList.remove('hidden');
            startLoadingTimer();

            const isMulti = _hasMultipleSentences(sentence);
            if (isMulti) {
                loadingMessageEl.textContent = 'Translating multiple sentences...';
            } else {
                loadingMessageEl.textContent = 'Translating...';
            }

            currentAbortController = new AbortController();
            // Longer timeout for multi-sentence (2 min per sentence, max 10)
            const timeoutMs = isMulti ? Math.min(sentence.split(/(?<=[.!?。！？])\s*/).filter(s=>s.trim()).length, 10) * 120000 : LEARN_TIMEOUT_MS;
            const timeoutId = setTimeout(() => currentAbortController.abort(), timeoutMs);

            try {
                if (isMulti) {
                    // Multi-sentence path
                    const resp = await fetch('/api/learn-multi', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-App-Password': appPassword
                        },
                        body: JSON.stringify({
                            sentences: sentence,
                            target_language: langSelect.value, input_language: selectedInputLang,
                            speaker_gender: selectedGender,
                            speaker_formality: selectedFormality
                        }),
                        signal: currentAbortController.signal
                    });

                    clearTimeout(timeoutId);

                    if (resp.status === 401) {
                        localStorage.removeItem(PASSWORD_STORAGE_KEY);
                        appPassword = '';
                        openPasswordModal('Session expired. Enter password again.');
                        throw new Error('Unauthorized');
                    }
                    if (!resp.ok) throw new Error(await friendlyError(resp));
                    const data = await resp.json();
                    const reqCtx = { target_language: langSelect.value, input_language: selectedInputLang, sentence: sentence };
                    const successfulResults = Array.isArray(data.results) ? data.results.filter(item => item && item.result) : [];

                    // Render each result as a separate card
                    successfulResults.forEach(item => {
                        renderResult(item.result, item.sentence, { ...reqCtx, sentence: item.sentence });
                    });

                    saveSentenceToHistory(sentence);
                    // Add first result to rich history
                    if (successfulResults.length) {
                        const first = successfulResults[0];
                        addToRichHistory(sentence, first.result.translation, langSelect.value, first.result.pronunciation);
                    }
                    recordLearnProgress(langSelect.value, successfulResults.length);
                    sentenceInput.value = '';
                    sentenceInput.style.height = 'auto';
                } else {
                    // Single sentence path — streaming SSE
                    const resp = await fetch('/api/learn-stream', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-App-Password': appPassword
                        },
                        body: JSON.stringify({
                            sentence: sentence,
                            target_language: langSelect.value, input_language: selectedInputLang,
                            speaker_gender: selectedGender,
                            speaker_formality: selectedFormality
                        }),
                        signal: currentAbortController.signal
                    });

                    clearTimeout(timeoutId);

                    if (resp.status === 401) {
                        localStorage.removeItem(PASSWORD_STORAGE_KEY);
                        appPassword = '';
                        openPasswordModal('Session expired. Enter password again.');
                        throw new Error('Unauthorized');
                    }
                    if (!resp.ok) throw new Error(await friendlyError(resp));

                    // Read SSE stream
                    const reader = resp.body.getReader();
                    const decoder = new TextDecoder();
                    let sseBuffer = '';
                    let data = null;

                    while (true) {
                        const { done, value } = await reader.read();
                        if (done) break;
                        sseBuffer += decoder.decode(value, { stream: true });

                        // Parse SSE events from buffer
                        const lines = sseBuffer.split('\n');
                        sseBuffer = lines.pop(); // keep incomplete line
                        for (const line of lines) {
                            if (!line.startsWith('data: ')) continue;
                            try {
                                const evt = JSON.parse(line.slice(6));
                                if (evt.type === 'progress') {
                                    loadingMessageEl.textContent = `Generating... (~${evt.tokens} tokens)`;
                                } else if (evt.type === 'result') {
                                    data = evt.data;
                                } else if (evt.type === 'error') {
                                    throw new Error(evt.message);
                                }
                            } catch (parseErr) {
                                if (parseErr.message && !parseErr.message.includes('JSON')) throw parseErr;
                            }
                        }
                    }

                    if (!data) throw new Error('No result received');
                    const reqCtx = { target_language: langSelect.value, input_language: selectedInputLang, sentence: sentence };
                    renderResult(data, sentence, reqCtx);
                    saveSentenceToHistory(sentence);
                    addToRichHistory(sentence, data.translation, langSelect.value, data.pronunciation);
                    recordLearnProgress(langSelect.value, 1);
                    sentenceInput.value = '';
                    sentenceInput.style.height = 'auto';
                }
            } catch (err) {
                clearTimeout(timeoutId);
                console.error(err);
                if (err.name === 'AbortError') {
                    showError('Request timed out — the model might be busy. Tap retry.');
                } else if (err.message === 'Unauthorized') {
                    // already handled above
                } else if (err.message && err.message !== 'API error') {
                    showError(err.message);
                } else {
                    showError('Something went wrong. Tap retry to try again.');
                }
            } finally {
                stopLoadingTimer();
                currentAbortController = null;
                if (appPassword === APP_PASSWORD) {
                    learnBtn.disabled = false;
                    if (compareBtn) compareBtn.disabled = false;
                } else {
                    lockApp();
                }
                loadingEl.classList.add('hidden');
            }
        }

        async function handleWordChipClick(chip, wordData, fullData, reqCtx) {
            // Toggle: if already expanded, collapse
            if (chip.classList.contains('expanded')) {
                chip.classList.remove('expanded');
                const detail = chip.querySelector('.word-detail');
                if (detail) detail.remove();
                return;
            }

            // Collapse any other expanded chips in the same card
            const parent = chip.closest('.word-chips');
            parent.querySelectorAll('.word-chip.expanded').forEach(other => {
                other.classList.remove('expanded');
                const d = other.querySelector('.word-detail');
                if (d) d.remove();
            });

            chip.classList.add('expanded');

            // Show loading
            const detailDiv = document.createElement('div');
            detailDiv.className = 'word-detail';
            detailDiv.innerHTML = '<div class="word-detail-loading">Loading details...</div>';
            chip.appendChild(detailDiv);

            try {
                const resp = await fetch('/api/word-detail', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-App-Password': appPassword
                    },
                    body: JSON.stringify({
                        word: wordData.word,
                        meaning: wordData.meaning,
                        target_language: reqCtx.target_language,
                        sentence_context: fullData.translation
                    })
                });

                if (!resp.ok) throw new Error(await friendlyError(resp));
                const detail = await resp.json();

                let html = '';

                // Example sentences
                if (detail.examples && detail.examples.length) {
                    html += '<div class="word-detail-section"><div class="word-detail-label">Examples</div><ul class="word-detail-examples">';
                    detail.examples.forEach(ex => {
                        html += `<li>${ex.sentence}<br><span class="example-pron">${ex.pronunciation || ''}</span> <span class="example-meaning">${ex.meaning}</span></li>`;
                    });
                    html += '</ul></div>';
                }

                // Conjugations
                if (detail.conjugations && detail.conjugations.length) {
                    html += '<div class="word-detail-section"><div class="word-detail-label">Forms</div><div class="word-detail-conjugations">';
                    detail.conjugations.forEach(c => {
                        html += `<span class="conjugation-tag">${c.form} <span class="conj-label">${c.label}</span></span>`;
                    });
                    html += '</div></div>';
                }

                // Related words
                if (detail.related && detail.related.length) {
                    html += '<div class="word-detail-section"><div class="word-detail-label">Related</div><div class="word-detail-related">';
                    detail.related.forEach(r => {
                        html += `<span class="related-word-tag" title="${r.meaning}">${r.word} — ${r.meaning}</span>`;
                    });
                    html += '</div></div>';
                }

                detailDiv.innerHTML = html || '<div class="word-detail-loading">No additional details available.</div>';
            } catch (err) {
                console.error(err);
                detailDiv.innerHTML = '<div class="word-detail-loading">Failed to load details.</div>';
            }
        }

        function renderResult(data, original, reqCtx) {
            const card = document.createElement('div');
            card.className = 'result-card';

            const breakdownHTML = data.breakdown.map(w => `
                <div class="word-chip">
                    <div class="word-target">
                        <span class="difficulty-dot ${w.difficulty}"></span>
                        ${w.word}
                    </div>
                    <div class="word-pron">${w.pronunciation}</div>
                    <div class="word-meaning">${w.meaning}</div>
                    ${w.note ? `<div class="word-note">${w.note}</div>` : ''}
                </div>
            `).join('');

            const grammarHTML = data.grammar_notes.map(n => `<li>${n}</li>`).join('');

            card.innerHTML = `
                <div class="result-main">
                    <div class="result-source">"${original}"</div>
                    <div class="result-head">
                        <div class="result-translation">${data.translation}</div>
                        <button type="button" class="speak-btn" aria-label="Listen to pronunciation" data-lang="${langSelect.value}">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14" aria-hidden="true">
                                <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
                                <path d="M19.07 4.93a10 10 0 0 1 0 14.14"></path>
                                <path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path>
                            </svg>
                            <span class="speak-label">Listen</span>
                        </button>
                        <button type="button" class="copy-btn" aria-label="Copy translation">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                                <rect x="9" y="9" width="13" height="13" rx="2"></rect>
                                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                            </svg>
                            <span class="copy-label">Copy</span>
                        </button>
                    </div>
                    <div class="result-pronunciation">${data.pronunciation}</div>
                    <div class="result-formality">${data.formality}</div>
                </div>
                <div class="breakdown-section">
                    <div class="section-title">Word Breakdown</div>
                    <div class="word-chips">${breakdownHTML}</div>
                </div>
                <div class="notes-section">
                    <div class="section-title">Grammar Notes</div>
                    <ul class="grammar-list">${grammarHTML}</ul>
                    ${data.cultural_note ? `<div class="cultural-note">💡 ${data.cultural_note}</div>` : ''}
                    ${data.alternative ? `<div class="alternative-note">🔄 Alternative: ${data.alternative}</div>` : ''}
                    ${data.native_expression ? `<div class="cultural-note">🗣️ Native expression: ${data.native_expression}</div>` : ''}
                    ${data.tw_native_phrases && data.tw_native_phrases.length > 0 ? `
                        <div class="cultural-note" style="margin-top:0.5rem;">
                            <div style="font-size:0.75rem;color:var(--text-dim);margin-bottom:0.3rem;">🇹🇼 How Taiwanese people actually say it:</div>
                            ${data.tw_native_phrases.map(p => `<div style="margin:0.3rem 0;"><strong>${p.phrase}</strong> <span style="color:var(--accent);font-size:0.8rem;">${p.pinyin}</span><br><span style="font-size:0.8rem;color:var(--text-dim);">${p.meaning}${p.context ? ' · ' + p.context : ''}</span></div>`).join('')}
                        </div>
                    ` : ''}
                </div>
            `;

            // Clickable word chips
            card.querySelectorAll('.word-chip').forEach((chip, idx) => {
                const wordData = data.breakdown[idx];
                chip.addEventListener('click', () => handleWordChipClick(chip, wordData, data, reqCtx));
            });

            // Speak button
            const speakBtn = card.querySelector('.speak-btn');
            if (speakBtn) {
                speakBtn.addEventListener('click', () => {
                    speakTranslation(data.translation, speakBtn.dataset.lang, speakBtn);
                });
            }

            const copyBtn = card.querySelector('.copy-btn');
            const copyLabelEl = card.querySelector('.copy-label');
            copyBtn.addEventListener('click', async () => {
                const copied = await copyTextToClipboard(data.translation);
                copyLabelEl.textContent = copied ? 'Copied' : 'Failed';
                if (copied) {
                    copyBtn.classList.add('copied');
                }
                setTimeout(() => {
                    copyLabelEl.textContent = 'Copy';
                    copyBtn.classList.remove('copied');
                }, 1200);
            });

            // Prepend new result
            if (resultsEl.children.length > 0) {
                const divider = document.createElement('div');
                divider.className = 'history-divider';
                resultsEl.insertBefore(divider, resultsEl.firstChild);
            }
            resultsEl.insertBefore(card, resultsEl.firstChild);

            requestAnimationFrame(() => {
                card.scrollIntoView({ behavior: 'smooth', block: 'start' });
            });
        }

        async function compareSentence() {
            if (!ensurePassword()) return;

            const sentence = sentenceInput.value.trim();
            if (!sentence) return;
            lastLearnSentence = sentence;
            lastActionType = 'compare';

            hideError();
            learnBtn.disabled = true;
            if (compareBtn) compareBtn.disabled = true;
            setRandomLoadingTip();
            loadingEl.classList.remove('hidden');
            loadingMessageEl.textContent = 'Comparing across languages...';
            startLoadingTimer();

            currentAbortController = new AbortController();
            const timeoutId = setTimeout(() => currentAbortController.abort(), LEARN_TIMEOUT_MS);

            try {
                const resp = await fetch('/api/compare', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-App-Password': appPassword
                    },
                    body: JSON.stringify({
                        sentence: sentence,
                        input_language: selectedInputLang,
                        speaker_gender: selectedGender,
                        speaker_formality: selectedFormality
                    }),
                    signal: currentAbortController.signal
                });

                clearTimeout(timeoutId);

                if (resp.status === 401) {
                    localStorage.removeItem(PASSWORD_STORAGE_KEY);
                    appPassword = '';
                    openPasswordModal('Session expired. Enter password again.');
                    throw new Error('Unauthorized');
                }
                if (!resp.ok) throw new Error(await friendlyError(resp));

                const data = await resp.json();
                renderCompareResults(data);
            } catch (err) {
                clearTimeout(timeoutId);
                console.error(err);
                if (err.name === 'AbortError') {
                    showError('Comparison timed out — tap compare again.');
                } else if (err.message === 'Unauthorized') {
                    // handled above
                } else if (err.message && err.message !== 'API error') {
                    showError(err.message);
                } else {
                    showError('Could not compare this sentence right now.');
                }
            } finally {
                stopLoadingTimer();
                currentAbortController = null;
                if (appPassword === APP_PASSWORD) {
                    learnBtn.disabled = false;
                    if (compareBtn) compareBtn.disabled = false;
                } else {
                    lockApp();
                }
                loadingEl.classList.add('hidden');
            }
        }

        // === Surprise Me ===
        async function surpriseMe() {
            if (!ensurePassword()) return;
            const surpriseBtn = document.getElementById('surprise-btn');
            surpriseBtn.disabled = true;
            try {
                const lang = langSelect.value;
                const inputLang = selectedInputLang === 'auto' ? 'en' : selectedInputLang;
                const resp = await fetch(`/api/surprise?lang=${encodeURIComponent(lang)}&input_lang=${encodeURIComponent(inputLang)}`);
                if (!resp.ok) throw new Error(await friendlyError(resp));
                const data = await resp.json();
                sentenceInput.value = data.sentence;
                sentenceInput.style.height = 'auto';
                sentenceInput.style.height = sentenceInput.scrollHeight + 'px';

                if (data.precomputed && data.result) {
                    // Instant! Use pre-computed result directly
                    cancelSpeculative();
                    const reqCtx = { target_language: lang, input_language: inputLang, sentence: data.sentence };
                    renderResult(data.result, data.sentence, reqCtx);
                    saveSentenceToHistory(data.sentence);
                    addToRichHistory(data.sentence, data.result.translation, lang, data.result.pronunciation);
                    recordLearnProgress(lang, 1);
                    sentenceInput.value = '';
                    sentenceInput.style.height = 'auto';
                } else {
                    // Fallback: compute live
                    await learn();
                }
            } catch (err) {
                console.error(err);
                alert('Could not fetch a surprise sentence.');
            } finally {
                surpriseBtn.disabled = false;
            }
        }

        // === Stories ===
        function toggleStoriesPanel() {
            storyPanelOpen = !storyPanelOpen;
            storiesPanelEl.classList.toggle('open', storyPanelOpen);
            storiesOverlayEl.classList.toggle('open', storyPanelOpen);
            if (storyPanelOpen) {
                renderStoriesBrowser();
            }
        }

        function closeStoriesPanel() {
            storyPanelOpen = false;
            storiesPanelEl.classList.remove('open');
            storiesOverlayEl.classList.remove('open');
        }

        async function loadStories() {
            try {
                const resp = await fetch('/api/stories');
                if (!resp.ok) return;
                stories = await resp.json();
                updateStoriesBadge();
            } catch (e) { console.error(e); }
        }

        function renderStoriesBrowser() {
            const selectedLang = langSelect.value;
            const langName = langSelect.options[langSelect.selectedIndex]?.textContent || selectedLang;
            const flag = LANG_FLAGS[selectedLang] || '🌐';
            storiesFilterEl.textContent = `${flag} ${langName} stories`;

            const filtered = stories.filter(s => s.language === selectedLang);
            if (filtered.length === 0) {
                storiesListEl.innerHTML = '<div class="stories-empty">No stories for this language yet.</div>';
                return;
            }

            storiesListEl.innerHTML = filtered.map(s => {
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

            storiesListEl.querySelectorAll('.story-list-item').forEach(btn => {
                btn.addEventListener('click', () => openStoryReader(btn.dataset.storyId));
            });

            storiesBrowserEl.classList.remove('hidden');
            storyReaderEl.classList.add('hidden');
        }

        async function openStoryReader(storyId) {
            let story = storyCache[storyId];
            if (!story) {
                try {
                    const resp = await fetch(`/api/story/${encodeURIComponent(storyId)}`);
                    if (!resp.ok) return;
                    story = await resp.json();
                    storyCache[storyId] = story;
                } catch (e) { console.error(e); return; }
            }

            activeStory = story;
            activeStoryIndex = getStoryProgress(storyId, story.sentences.length);

            storiesBrowserEl.classList.add('hidden');
            storyReaderEl.classList.remove('hidden');
            renderStoryReader();
        }

        function renderStoryReader() {
            if (!activeStory) return;
            const total = activeStory.sentences.length;
            storyTitleEl.textContent = activeStory.title;
            storySourceEl.textContent = activeStory.source;
            storySentenceEl.textContent = activeStory.sentences[activeStoryIndex];
            storyProgressEl.textContent = `${activeStoryIndex + 1}/${total}`;
            storyPrevBtn.disabled = activeStoryIndex <= 0;
            storyNextBtn.disabled = activeStoryIndex >= total - 1;
        }

        storyPrevBtn.addEventListener('click', () => {
            if (!activeStory || activeStoryIndex <= 0) return;
            activeStoryIndex--;
            setStoryProgress(activeStory.id, activeStoryIndex);
            renderStoryReader();
        });

        storyNextBtn.addEventListener('click', () => {
            if (!activeStory || activeStoryIndex >= activeStory.sentences.length - 1) return;
            activeStoryIndex++;
            setStoryProgress(activeStory.id, activeStoryIndex);
            renderStoryReader();
        });

        // "Learn this sentence" — clicking the story sentence fills input
        storySentenceEl.addEventListener('click', () => {
            if (!activeStory) return;
            const sentence = activeStory.sentences[activeStoryIndex];
            sentenceInput.value = sentence;
            sentenceInput.style.height = 'auto';
            sentenceInput.style.height = sentenceInput.scrollHeight + 'px';
            // Select the story's language
            selectLangPill(activeStory.language);
            closeStoriesPanel();
            sentenceInput.focus();
        });

        storyBackBtn.addEventListener('click', () => {
            activeStory = null;
            renderStoriesBrowser();
        });

        storiesToggleBtn.addEventListener('click', toggleStoriesPanel);
        storiesOverlayEl.addEventListener('click', closeStoriesPanel);
        storiesPanelCloseBtn.addEventListener('click', closeStoriesPanel);

        // Quiz mode event handlers
        quizToggleBtn.addEventListener('click', toggleQuizMode);
        quizCheckBtn.addEventListener('click', checkQuizAnswer);
        quizNextBtn.addEventListener('click', loadQuizQuestion);
        quizExitBtn.addEventListener('click', exitQuizMode);
        quizAnswerInputEl.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.isComposing) {
                e.preventDefault();
                checkQuizAnswer();
            }
        });

        // Load stories after languages load
        const origLoadLanguages = loadLanguages;
        loadLanguages = async function() {
            await origLoadLanguages();
            await loadStories();
        };

        // === Hamburger Side Menu ===
        const hamburgerBtn = document.getElementById('hamburger-btn');
        const hamburgerBadge = document.getElementById('hamburger-badge');
        const sideMenuEl = document.getElementById('side-menu');
        const sideMenuOverlay = document.getElementById('side-menu-overlay');
        const sideMenuClose = document.getElementById('side-menu-close');
        const menuHistoryBadge = document.getElementById('menu-history-badge');

        function openSideMenu() {
            sideMenuEl.classList.add('open');
            sideMenuOverlay.classList.add('open');
            // Update quiz active state
            document.getElementById('menu-quiz').classList.toggle('active', quizMode);
        }
        function closeSideMenu() {
            sideMenuEl.classList.remove('open');
            sideMenuOverlay.classList.remove('open');
        }

        hamburgerBtn.addEventListener('click', openSideMenu);
        sideMenuOverlay.addEventListener('click', closeSideMenu);
        sideMenuClose.addEventListener('click', closeSideMenu);

        document.getElementById('menu-history').addEventListener('click', () => {
            closeSideMenu();
            toggleHistoryPanel();
        });
        document.getElementById('menu-quiz').addEventListener('click', () => {
            closeSideMenu();
            toggleQuizMode();
        });
        document.getElementById('menu-stories').addEventListener('click', () => {
            closeSideMenu();
            toggleStoriesPanel();
        });
        document.getElementById('menu-stats').addEventListener('click', () => {
            closeSideMenu();
            openStatsModal();
        });

        // Patch updateHistoryBadge to also update hamburger + menu badges
        const origUpdateHistoryBadge = updateHistoryBadge;
        updateHistoryBadge = function() {
            origUpdateHistoryBadge();
            const count = richHistory.length;
            menuHistoryBadge.textContent = count;
            menuHistoryBadge.style.display = count > 0 ? '' : 'none';
            hamburgerBadge.textContent = count;
            hamburgerBadge.style.display = count > 0 ? '' : 'none';
        };
(function() {
            const btn = document.getElementById('feedback-btn');
            const modal = document.getElementById('feedback-modal');
            const text = document.getElementById('feedback-text');
            const send = document.getElementById('feedback-send');
            const cancel = document.getElementById('feedback-cancel');
            const status = document.getElementById('feedback-status');
            btn.addEventListener('click', () => { modal.classList.add('open'); text.focus(); });
            cancel.addEventListener('click', () => { modal.classList.remove('open'); });
            modal.addEventListener('click', (e) => { if (e.target === modal) modal.classList.remove('open'); });
            send.addEventListener('click', async () => {
                if (!text.value.trim()) return;
                send.disabled = true; send.textContent = 'Sending...';
                try {
                    const pw = localStorage.getItem('sent-say_app_password') || '';
                    await fetch('/api/feedback', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-App-Password': pw },
                        body: JSON.stringify({ message: text.value.trim() })
                    });
                    status.textContent = '✅ Thanks for your feedback!'; status.style.display = 'block';
                    text.value = '';
                    setTimeout(() => { modal.classList.remove('open'); status.style.display = 'none'; send.disabled = false; send.textContent = 'Send'; }, 1500);
                } catch(e) {
                    status.textContent = '❌ Failed to send'; status.style.color = 'var(--hard)'; status.style.display = 'block';
                    send.disabled = false; send.textContent = 'Send';
                }
            });
        })();