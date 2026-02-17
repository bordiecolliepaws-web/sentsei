// Shared mutable state — all modules read/write through this object
// DOM element references are populated by init() in app.js

export const DOM = {};

export const LANG_FLAGS = {
    ko: '🇰🇷', ja: '🇯🇵', zh: '🇹🇼', en: '🇺🇸',
    he: '🇮🇱', el: '🇬🇷', it: '🇮🇹', es: '🇪🇸',
    fr: '🇫🇷', de: '🇩🇪', pt: '🇧🇷', ar: '🇸🇦',
    th: '🇹🇭', vi: '🇻🇳', hi: '🇮🇳', ru: '🇷🇺'
};

export const LANG_SPEECH_MAP = {
    ko: 'ko-KR', ja: 'ja-JP', zh: 'zh-TW', en: 'en-US',
    he: 'he-IL', el: 'el-GR', it: 'it-IT', es: 'es-ES',
    fr: 'fr-FR', de: 'de-DE', pt: 'pt-BR', ar: 'ar-SA',
    th: 'th-TH', vi: 'vi-VN', hi: 'hi-IN', ru: 'ru-RU'
};

export const LANGUAGE_TIPS = {
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

export const KEYS = {
    APP_PASSWORD: 'sentsei2026',
    PASSWORD_STORAGE: 'sent-say_app_password',
    SENTENCE_HISTORY: 'sent-say_sentence_history',
    RICH_HISTORY: 'sent-say_rich_history',
    STORY_PROGRESS: 'sent-say_story_progress',
    PROGRESS_STATS: 'sent-say_progress_stats',
    GENDER: 'sent-say_speaker_gender',
    FORMALITY: 'sent-say_speaker_formality',
    ROMANIZATION: 'sent-say_show_romanization',
    INPUT_LANG: 'sent-say_input_lang',
    TARGET_LANG: 'sent-say_target_lang',
    ONBOARDED: 'sent-say_onboarded',
    SRS: 'sentsei-srs',
    AUTH_TOKEN: 'sentsei-auth-token',
    AUTH_USERNAME: 'sentsei-auth-username',
    THEME: 'sentsei-theme',
};

export const HISTORY_LIMIT = 50;
export const MS_PER_DAY = 24 * 60 * 60 * 1000;
export const DAY_MS = 86400000;
export const RECENT_DISPLAY_LIMIT = 4;
export const LEARN_TIMEOUT_MS = 45000;
export const MAX_AUTO_RETRIES = 3;
export const AUTO_RETRY_DELAY_MS = 4000;

export const QUIZ_SCORE_LABELS = {
    perfect: '✅ Perfect',
    good: '👍 Good',
    partial: '🤔 Partial',
    wrong: '❌ Wrong'
};

export const LOADING_PHASES = [
    { at: 0, msg: 'Translating...' },
    { at: 3, msg: 'Analyzing grammar...' },
    { at: 7, msg: 'Building word breakdown...' },
    { at: 12, msg: 'Adding pronunciation...' },
    { at: 18, msg: 'Almost there...' },
    { at: 25, msg: 'Still working — complex sentence!' },
    { at: 35, msg: 'Hang tight, wrapping up...' },
];

// Mutable app state
export const state = {
    selectedGender: localStorage.getItem('sent-say_speaker_gender') || 'neutral',
    selectedFormality: localStorage.getItem('sent-say_speaker_formality') || 'polite',
    showRomanization: localStorage.getItem('sent-say_show_romanization') !== 'false',
    selectedInputLang: localStorage.getItem('sent-say_input_lang') || 'en',
    appPassword: localStorage.getItem('sent-say_app_password') || '',
    sentenceHistory: [],
    richHistory: [],
    languagesLoaded: false,
    stories: [],
    storyPanelOpen: false,
    storyProgress: {},
    activeStory: null,
    activeStoryIndex: 0,
    storyCache: {},
    historyPanelOpen: false,
    quizMode: false,
    reviewMode: false,
    currentQuiz: null,
    currentReview: null,
    srsDeck: [],
    reviewCorrect: 0,
    reviewTotal: 0,
    progressStats: null,
    quizStats: null,
    currentAbortController: null,
    loadingTimer: null,
    lastLearnSentence: '',
    learnGeneration: 0,
    lastActionType: 'learn',
    _autoRetryCount: 0,
    speculativeTimer: null,
    speculativeController: null,
    speculativeCache: {},
    speculativePending: false,
    isComposing: false,
    grammarPanelOpen: false,
    grammarPatterns: [],
    grammarFilterLang: null,
    authToken: localStorage.getItem('sentsei-auth-token') || '',
    authUsername: localStorage.getItem('sentsei-auth-username') || '',
    authMode: 'login',
    quizCorrect: 0,
    quizTotal: 0,
    ollamaOnline: true,
    _healthPollTimer: null,
    // Batch SRS review
    batchReview: false,
    batchQueue: [],
    batchIndex: 0,
    batchStartTime: 0,
    batchCardStart: 0,
    batchCardTimes: [],
    batchResults: [], // {correct: bool, item, timeMs}
};

// Hook registry for monkey-patch replacements
export const hooks = {
    afterSaveRichHistory: [],
    afterSaveSRSDeck: [],
    afterSaveProgressStats: [],
    afterClosePasswordModal: [],
    afterLoadLanguages: [],
    afterUpdateHistoryBadge: [],
};
