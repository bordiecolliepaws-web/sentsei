"""Pydantic schemas, constants, and static data for Sentsei."""
from typing import Optional, List
from pydantic import BaseModel

# --- Constants ---
SUPPORTED_LANGUAGES = {
    "he": "Hebrew",
    "ja": "Japanese",
    "ko": "Korean",
    "en": "English",
    "zh": "Chinese",
    "el": "Greek",
    "it": "Italian",
    "es": "Spanish",
}

ALLOWED_DATA_KEYS = {"history", "srs_deck", "progress", "preferences", "rich_history"}

# --- Pydantic Models ---

class SentenceRequest(BaseModel):
    sentence: str
    target_language: str
    input_language: Optional[str] = "auto"
    speaker_gender: Optional[str] = None
    speaker_formality: Optional[str] = None


class BreakdownRequest(BaseModel):
    sentence: str           # original input
    translation: str        # the translated text
    target_language: str
    input_language: Optional[str] = "auto"
    speaker_gender: Optional[str] = None
    speaker_formality: Optional[str] = None


class MultiSentenceRequest(BaseModel):
    sentences: str  # raw paragraph text
    target_language: str
    input_language: Optional[str] = "auto"
    speaker_gender: Optional[str] = None
    speaker_formality: Optional[str] = None


class WordDetailRequest(BaseModel):
    word: str
    meaning: str
    target_language: str
    sentence_context: Optional[str] = None


class ContextExamplesRequest(BaseModel):
    translation: str
    target_language: str
    source_sentence: str
    source_language: Optional[str] = "en"


class AnkiExportEntry(BaseModel):
    sentence: str
    translation: str
    pronunciation: Optional[str] = None
    target: Optional[str] = None
    lang: Optional[str] = None
    timestamp: Optional[str] = None


class QuizCheckRequest(BaseModel):
    quiz_id: str
    answer: str
    target_language: str


class QuizHistoryItem(BaseModel):
    sentence: str
    translation: str
    pronunciation: Optional[str] = None


class QuizFromHistoryRequest(BaseModel):
    history: List[QuizHistoryItem]


class CompareRequest(BaseModel):
    sentence: str
    input_language: Optional[str] = "auto"
    speaker_gender: Optional[str] = None
    speaker_formality: Optional[str] = None


class FeedbackRequest(BaseModel):
    message: str
    sentence: Optional[str] = None
    translation: Optional[str] = None
    target_language: Optional[str] = None


class AuthRequest(BaseModel):
    username: str
    password: str


# --- Static Data ---

CURATED_SENTENCES = {
    "ja": [
        {"sentence": "ここで働かせてください。", "difficulty": "easy", "category": "anime", "source": "Spirited Away"},
        {"sentence": "君の名は。", "difficulty": "easy", "category": "anime", "source": "Your Name"},
        {"sentence": "諦めたらそこで試合終了ですよ。", "difficulty": "medium", "category": "anime", "source": "Slam Dunk"},
        {"sentence": "お前はもう死んでいる。", "difficulty": "easy", "category": "anime", "source": "Fist of the North Star"},
        {"sentence": "海賊王におれはなる！", "difficulty": "easy", "category": "anime", "source": "One Piece"},
        {"sentence": "生きろ。そなたは美しい。", "difficulty": "medium", "category": "movie", "source": "Princess Mononoke"},
        {"sentence": "まだ会ったことのない君を、探している。", "difficulty": "medium", "category": "anime", "source": "Your Name"},
        {"sentence": "行け。振り向くんじゃない。", "difficulty": "easy", "category": "anime", "source": "Spirited Away"},
        {"sentence": "生きるべきか死ぬべきか、それが問題だ。", "difficulty": "hard", "category": "literature", "source": "Hamlet (Japanese translation)"},
    ],
    "ko": [
        {"sentence": "아들아, 너는 계획이 다 있구나.", "difficulty": "easy", "category": "movie", "source": "Parasite"},
        {"sentence": "가장 완벽한 계획이 뭔지 알아? 무계획이야.", "difficulty": "medium", "category": "movie", "source": "Parasite"},
        {"sentence": "무궁화 꽃이 피었습니다.", "difficulty": "easy", "category": "drama", "source": "Squid Game"},
        {"sentence": "우리는 깐부잖아.", "difficulty": "easy", "category": "drama", "source": "Squid Game"},
        {"sentence": "날이 좋아서, 날이 좋지 않아서, 날이 적당해서 모든 날이 좋았다.", "difficulty": "hard", "category": "drama", "source": "Goblin"},
        {"sentence": "시작이 반이다.", "difficulty": "easy", "category": "proverb", "source": "Korean proverb"},
        {"sentence": "고생 끝에 낙이 온다.", "difficulty": "medium", "category": "proverb", "source": "Korean proverb"},
        {"sentence": "티끌 모아 태산.", "difficulty": "easy", "category": "proverb", "source": "Korean proverb"},
        {"sentence": "묻고 더블로 가!", "difficulty": "medium", "category": "movie", "source": "Tazza: The High Rollers"},
    ],
    "zh": [
        {"sentence": "學而時習之，不亦說乎？", "difficulty": "medium", "category": "literature", "source": "《論語》"},
        {"sentence": "千里之行，始於足下。", "difficulty": "easy", "category": "literature", "source": "《道德經》"},
        {"sentence": "三人行，必有我師焉。", "difficulty": "easy", "category": "literature", "source": "《論語》"},
        {"sentence": "知之為知之，不知為不知，是知也。", "difficulty": "medium", "category": "literature", "source": "《論語》"},
        {"sentence": "天行健，君子以自強不息。", "difficulty": "hard", "category": "literature", "source": "《周易》"},
        {"sentence": "路漫漫其修遠兮，吾將上下而求索。", "difficulty": "hard", "category": "literature", "source": "《離騷》"},
        {"sentence": "海內存知己，天涯若比鄰。", "difficulty": "medium", "category": "literature", "source": "王勃"},
        {"sentence": "失敗為成功之母。", "difficulty": "easy", "category": "proverb", "source": "Chinese saying"},
        {"sentence": "水滴石穿。", "difficulty": "easy", "category": "proverb", "source": "Chinese saying"},
    ],
    "he": [
        {"sentence": "אם אין אני לי, מי לי?", "difficulty": "medium", "category": "literature", "source": "Pirkei Avot"},
        {"sentence": "גם זה יעבור.", "difficulty": "easy", "category": "proverb", "source": "Hebrew saying"},
        {"sentence": "עוד לא אבדה תקוותנו.", "difficulty": "medium", "category": "song", "source": "Hatikvah"},
        {"sentence": "להיות עם חופשי בארצנו.", "difficulty": "easy", "category": "song", "source": "Hatikvah"},
        {"sentence": "ואהבת לרעך כמוך.", "difficulty": "medium", "category": "literature", "source": "Leviticus 19:18"},
        {"sentence": "החיים והמוות ביד הלשון.", "difficulty": "hard", "category": "literature", "source": "Proverbs 18:21"},
        {"sentence": "כל העולם כולו גשר צר מאוד.", "difficulty": "hard", "category": "literature", "source": "Rabbi Nachman"},
        {"sentence": "אין דבר העומד בפני הרצון.", "difficulty": "medium", "category": "proverb", "source": "Hebrew saying"},
        {"sentence": "סוף מעשה במחשבה תחילה.", "difficulty": "medium", "category": "literature", "source": "Lekha Dodi"},
    ],
    "en": [
        {"sentence": "May the Force be with you.", "difficulty": "easy", "category": "movie", "source": "Star Wars"},
        {"sentence": "I'll be back.", "difficulty": "easy", "category": "movie", "source": "The Terminator"},
        {"sentence": "To be, or not to be, that is the question.", "difficulty": "hard", "category": "literature", "source": "Hamlet"},
        {"sentence": "All the world's a stage.", "difficulty": "medium", "category": "literature", "source": "As You Like It"},
        {"sentence": "Here's looking at you, kid.", "difficulty": "easy", "category": "movie", "source": "Casablanca"},
        {"sentence": "Keep your friends close, but your enemies closer.", "difficulty": "medium", "category": "movie", "source": "The Godfather Part II"},
        {"sentence": "Frankly, my dear, I don't give a damn.", "difficulty": "medium", "category": "movie", "source": "Gone with the Wind"},
        {"sentence": "It was the best of times, it was the worst of times.", "difficulty": "hard", "category": "literature", "source": "A Tale of Two Cities"},
        {"sentence": "Not all those who wander are lost.", "difficulty": "medium", "category": "literature", "source": "J.R.R. Tolkien"},
    ],
    "el": [
        {"sentence": "Γνῶθι σεαυτόν.", "difficulty": "easy", "category": "literature", "source": "Delphic maxim"},
        {"sentence": "Ἓν οἶδα ὅτι οὐδὲν οἶδα.", "difficulty": "hard", "category": "literature", "source": "Socrates"},
        {"sentence": "Πάντα ῥεῖ.", "difficulty": "easy", "category": "literature", "source": "Heraclitus"},
        {"sentence": "Μολὼν λαβέ.", "difficulty": "easy", "category": "history", "source": "Leonidas"},
        {"sentence": "Ελευθερία ή θάνατος.", "difficulty": "easy", "category": "history", "source": "Greek motto"},
        {"sentence": "Οὐκ ἐν τῷ πολλῷ τὸ εὖ.", "difficulty": "hard", "category": "proverb", "source": "Ancient Greek saying"},
        {"sentence": "Δεν ελπίζω τίποτα. Δεν φοβάμαι τίποτα. Είμαι λεύτερος.", "difficulty": "hard", "category": "literature", "source": "Nikos Kazantzakis"},
        {"sentence": "Καλύτερα αργά παρά ποτέ.", "difficulty": "easy", "category": "proverb", "source": "Greek proverb"},
        {"sentence": "Η αρχή είναι το ήμισυ του παντός.", "difficulty": "medium", "category": "literature", "source": "Aristotle"},
    ],
    "it": [
        {"sentence": "Nel mezzo del cammin di nostra vita.", "difficulty": "hard", "category": "literature", "source": "Dante, Inferno"},
        {"sentence": "Lasciate ogni speranza, voi ch'entrate.", "difficulty": "hard", "category": "literature", "source": "Dante, Inferno"},
        {"sentence": "Fatti non foste a viver come bruti.", "difficulty": "hard", "category": "literature", "source": "Dante, Inferno"},
        {"sentence": "Amor, ch'a nullo amato amar perdona.", "difficulty": "hard", "category": "literature", "source": "Dante, Inferno"},
        {"sentence": "Buongiorno, principessa!", "difficulty": "easy", "category": "movie", "source": "La vita è bella"},
        {"sentence": "Chi va piano va sano e va lontano.", "difficulty": "easy", "category": "proverb", "source": "Italian proverb"},
        {"sentence": "Finché c'è vita c'è speranza.", "difficulty": "medium", "category": "proverb", "source": "Italian proverb"},
        {"sentence": "La vita è bella.", "difficulty": "easy", "category": "movie", "source": "La vita è bella"},
        {"sentence": "Il fine giustifica i mezzi.", "difficulty": "medium", "category": "literature", "source": "Attributed to Machiavelli"},
    ],
    "es": [
        {"sentence": "En un lugar de La Mancha, de cuyo nombre no quiero acordarme.", "difficulty": "hard", "category": "literature", "source": "Don Quijote"},
        {"sentence": "Caminante, no hay camino, se hace camino al andar.", "difficulty": "medium", "category": "literature", "source": "Antonio Machado"},
        {"sentence": "Más vale tarde que nunca.", "difficulty": "easy", "category": "proverb", "source": "Spanish proverb"},
        {"sentence": "No hay mal que por bien no venga.", "difficulty": "medium", "category": "proverb", "source": "Spanish proverb"},
        {"sentence": "El que madruga, Dios le ayuda.", "difficulty": "easy", "category": "proverb", "source": "Spanish proverb"},
        {"sentence": "Poderoso caballero es don Dinero.", "difficulty": "hard", "category": "literature", "source": "Francisco de Quevedo"},
        {"sentence": "Volverán las oscuras golondrinas.", "difficulty": "medium", "category": "literature", "source": "Gustavo Adolfo Bécquer"},
        {"sentence": "¡Hasta la vista, baby!", "difficulty": "easy", "category": "movie", "source": "Terminator 2"},
        {"sentence": "Quien tiene un amigo, tiene un tesoro.", "difficulty": "easy", "category": "proverb", "source": "Spanish saying"},
    ],
}

STORIES = {
    "spirited-away": {
        "id": "spirited-away",
        "title": "千と千尋の神隠し",
        "source": "Spirited Away",
        "language": "ja",
        "sentences": [
            "ここで働かせてください。",
            "千尋という名は贅沢な名だね。",
            "千だ。今からお前の名前は千だ。",
            "一度あったことは忘れないものさ。思い出せないだけで。",
            "行け。振り向くんじゃない。",
        ],
    },
    "your-name": {
        "id": "your-name",
        "title": "君の名は。",
        "source": "Your Name",
        "language": "ja",
        "sentences": [
            "朝、目が覚めると、なぜか泣いている。",
            "まだ会ったことのない君を、探している。",
            "お前は誰だ？",
            "君の名は。",
            "大事な人。忘れたくない人。忘れちゃダメな人。",
        ],
    },
    "parasite": {
        "id": "parasite",
        "title": "기생충",
        "source": "Parasite",
        "language": "ko",
        "sentences": [
            "아들아, 너는 계획이 다 있구나.",
            "가장 완벽한 계획이 뭔지 알아? 무계획이야.",
            "부잣집 애들은 착해.",
            "돈이 다림질이야.",
            "그래서 존중이 생기는 거야.",
        ],
    },
    "squid-game": {
        "id": "squid-game",
        "title": "오징어 게임",
        "source": "Squid Game",
        "language": "ko",
        "sentences": [
            "무궁화 꽃이 피었습니다.",
            "우리는 깐부잖아.",
            "여기선 다 공평해.",
            "이번 게임을 시작하겠습니다.",
            "탈락입니다.",
        ],
    },
    "chinese-proverbs": {
        "id": "chinese-proverbs",
        "title": "經典成語與格言",
        "source": "Chinese Proverbs & Classics",
        "language": "zh",
        "sentences": [
            "千里之行，始於足下。",
            "學而時習之，不亦說乎？",
            "三人行，必有我師焉。",
            "失敗為成功之母。",
            "水滴石穿。",
        ],
    },
}

SURPRISE_SENTENCES_EN = [
    {"sentence": "I want to eat ramen for dinner tonight", "difficulty": "easy", "category": "daily life"},
    {"sentence": "Where is the nearest train station?", "difficulty": "easy", "category": "travel"},
    {"sentence": "This coffee tastes absolutely amazing", "difficulty": "easy", "category": "food"},
    {"sentence": "Could you please speak a little slower?", "difficulty": "easy", "category": "travel"},
    {"sentence": "I've been studying this language for three months", "difficulty": "medium", "category": "learning"},
    {"sentence": "The sunset over the ocean was breathtaking", "difficulty": "medium", "category": "nature"},
    {"sentence": "I'm sorry, I don't understand what you're saying", "difficulty": "easy", "category": "travel"},
    {"sentence": "Let's grab a beer after work", "difficulty": "easy", "category": "social"},
    {"sentence": "I need to wake up early tomorrow morning", "difficulty": "easy", "category": "daily life"},
    {"sentence": "What do you recommend from the menu?", "difficulty": "easy", "category": "food"},
    {"sentence": "I've been meaning to tell you something important", "difficulty": "medium", "category": "social"},
    {"sentence": "The more I practice, the more confident I feel", "difficulty": "medium", "category": "learning"},
    {"sentence": "Can I get the bill please?", "difficulty": "easy", "category": "travel"},
    {"sentence": "I think we're lost, let me check the map", "difficulty": "medium", "category": "travel"},
    {"sentence": "If I had known earlier, I would have come sooner", "difficulty": "hard", "category": "grammar"},
]

SURPRISE_SENTENCES_ZH = [
    {"sentence": "今天晚上我想吃拉麵", "difficulty": "easy", "category": "日常生活"},
    {"sentence": "請問最近的捷運站在哪裡？", "difficulty": "easy", "category": "旅遊"},
    {"sentence": "這杯咖啡真的超好喝", "difficulty": "easy", "category": "美食"},
    {"sentence": "你可以講慢一點嗎？", "difficulty": "easy", "category": "旅遊"},
    {"sentence": "我學這個語言已經三個月了", "difficulty": "medium", "category": "學習"},
    {"sentence": "海邊的夕陽真的美到不行", "difficulty": "medium", "category": "自然"},
    {"sentence": "不好意思，我聽不懂你在說什麼", "difficulty": "easy", "category": "旅遊"},
    {"sentence": "下班之後一起去喝一杯吧", "difficulty": "easy", "category": "社交"},
    {"sentence": "我明天早上要早起", "difficulty": "easy", "category": "日常生活"},
    {"sentence": "你們推薦菜單上的什麼？", "difficulty": "easy", "category": "美食"},
    {"sentence": "我一直想跟你說一件很重要的事", "difficulty": "medium", "category": "社交"},
    {"sentence": "越練習就越有自信", "difficulty": "medium", "category": "學習"},
    {"sentence": "可以幫我結帳嗎？", "difficulty": "easy", "category": "旅遊"},
    {"sentence": "我覺得我們迷路了，讓我看一下地圖", "difficulty": "medium", "category": "旅遊"},
    {"sentence": "如果我早點知道的話，我就會早點來", "difficulty": "hard", "category": "文法"},
]
