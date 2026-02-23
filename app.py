import base64
import hashlib
import io
import os
import json
import random
import re
import sqlite3
import threading
import unicodedata
import uuid
from datetime import datetime, date, timedelta
from collections import Counter
from functools import lru_cache, wraps
from typing import Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from flask import Flask, render_template, jsonify, request, redirect, url_for, send_file, session


def _load_env_file(path: str) -> None:
    """Load KEY=VALUE lines from a local .env file (optional).

    This keeps secrets/config out of git while allowing easy local setup.
    Existing environment variables are not overwritten.
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for raw in f:
                line = (raw or '').strip()
                if not line or line.startswith('#'):
                    continue
                if line.lower().startswith('export '):
                    line = line[7:].strip()
                if '=' not in line:
                    continue
                key, val = line.split('=', 1)
                key = (key or '').strip()
                if not key:
                    continue
                val = (val or '').strip()
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                if key not in os.environ or not os.environ.get(key):
                    os.environ[key] = val
    except FileNotFoundError:
        return
    except OSError:
        return


_load_env_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

app = Flask(__name__)
_secret_key = os.environ.get('SECRET_KEY', '').strip()
if not _secret_key:
    import warnings
    warnings.warn(
        "SECRET_KEY env var is not set — using an insecure dev key. "
        "Run: python -c \"import secrets; print(secrets.token_hex(32))\" "
        "and set SECRET_KEY in your environment or a .env file.",
        stacklevel=1,
    )
    _secret_key = 'language_coach_dev_INSECURE'
app.secret_key = _secret_key

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DB_PATH  = os.path.join(DATA_DIR, 'progress.db')
TTS_CACHE_DIR = (os.environ.get('TTS_CACHE_DIR') or os.path.join(DATA_DIR, 'tts_cache')).strip() or os.path.join(DATA_DIR, 'tts_cache')

_TTS_PROVIDER = 'gtts'
app.config['TTS_PROVIDER'] = _TTS_PROVIDER
app.config['TTS_CACHE_DIR'] = TTS_CACHE_DIR

_TRANSLATE_PROVIDER = (os.environ.get('TRANSLATE_PROVIDER') or 'hybrid').strip().lower()
if _TRANSLATE_PROVIDER not in {'local', 'mymemory', 'hybrid'}:
    _TRANSLATE_PROVIDER = 'hybrid'
app.config['TRANSLATE_PROVIDER'] = _TRANSLATE_PROVIDER

# ---------- Optional: Google Sheets logging (via Apps Script webhook) ----------
SHEETS_WEBHOOK_URL = (os.environ.get('SHEETS_WEBHOOK_URL') or '').strip()
SHEETS_WEBHOOK_TOKEN = (os.environ.get('SHEETS_WEBHOOK_TOKEN') or '').strip()
try:
    SHEETS_WEBHOOK_TIMEOUT = float(os.environ.get('SHEETS_WEBHOOK_TIMEOUT', '3.0') or 3.0)
except (TypeError, ValueError):
    SHEETS_WEBHOOK_TIMEOUT = 3.0
SHEETS_WEBHOOK_TIMEOUT = max(1.0, min(15.0, SHEETS_WEBHOOK_TIMEOUT))
SHEETS_USERS_SHEET = (os.environ.get('SHEETS_USERS_SHEET') or 'LanguageCoach_Users').strip() or 'LanguageCoach_Users'
SHEETS_EVENTS_SHEET = (os.environ.get('SHEETS_EVENTS_SHEET') or 'LanguageCoach_Events').strip() or 'LanguageCoach_Events'
SHEETS_FEEDBACK_SHEET = (os.environ.get('SHEETS_FEEDBACK_SHEET') or 'LanguageCoach_Feedback').strip() or 'LanguageCoach_Feedback'

# ---------- Content loading (auto-reload when JSON changes) ----------
VOCAB_PATH = os.path.join(DATA_DIR, 'vocabulary.json')
LESSONS_PATH = os.path.join(DATA_DIR, 'lessons.json')
RESOURCE_SENTENCES_PATH = os.path.join(DATA_DIR, 'resource_sentences.json')

_DATA_LOCK = threading.Lock()
_DATA_CACHE = {}
_DATA_MTIME = {}
_DATA_ERROR_MTIME = {}


def _read_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def _cached_json(key, path, default):
    """Load JSON once and auto-reload if the file changes on disk."""
    try:
        mtime = os.path.getmtime(path)
    except FileNotFoundError:
        return default

    with _DATA_LOCK:
        if _DATA_MTIME.get(key) == mtime and key in _DATA_CACHE:
            return _DATA_CACHE[key]

        # If the current mtime previously failed to parse, avoid spamming logs.
        if _DATA_ERROR_MTIME.get(key) == mtime and key in _DATA_CACHE:
            return _DATA_CACHE[key]

        try:
            data = _read_json(path)
        except json.JSONDecodeError as exc:
            _DATA_ERROR_MTIME[key] = mtime
            print(f"WARNING: Could not parse {path}: {exc}")
            return _DATA_CACHE.get(key, default)

        _DATA_CACHE[key] = data
        _DATA_MTIME[key] = mtime
        _DATA_ERROR_MTIME.pop(key, None)
        return data


def get_vocab():
    return _cached_json('vocab', VOCAB_PATH, default={})


def get_lessons():
    return _cached_json('lessons', LESSONS_PATH, default={})


def get_resource_sentences():
    """Optional: extracted sentences from local PDFs (see scripts/build_resource_sentences.py)."""
    return _cached_json('resource_sentences', RESOURCE_SENTENCES_PATH, default={})


def _strip_accents(text: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')


def _norm_match(text: str) -> str:
    s = _strip_accents((text or '').lower().strip())
    s = s.replace("'", ' ')
    s = re.sub(r'[^a-z0-9]+', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def _word_match_variants(word: str):
    w = (word or '').strip()
    if not w:
        return []

    variants = {w}
    # Handle "argentino/a" -> ["argentino", "argentina"]
    m = re.match(r'^(.+?)([oa])\/([oa])$', w, flags=re.I)
    if m:
        variants.add(m.group(1) + m.group(2))
        variants.add(m.group(1) + m.group(3))

    return sorted({_norm_match(v) for v in variants if v.strip()})


def _has_bengali_script(text: str) -> bool:
    for ch in (text or ''):
        if '\u0980' <= ch <= '\u09FF':
            return True
    return False


def _norm_bn(text: str) -> str:
    s = unicodedata.normalize('NFC', (text or '').strip())
    s = re.sub(r'\s+', ' ', s)
    return s


def _primary_gloss(english: str) -> str:
    """Pick a single English gloss from entries like 'hello / good morning'."""
    parts = _split_english_glosses(english)
    return parts[0] if parts else ''


def _split_english_glosses(english: str):
    s = (english or '').strip()
    if not s:
        return []
    parts = re.split(r'\s*(?:/|;|,|\||·|•)\s*', s)
    return [p.strip() for p in parts if p and p.strip()]


def _best_vocab_match_word(vocab_by_cat, q_norm: str):
    if not q_norm:
        return None, 0

    best = None
    best_score = 0
    for words in (vocab_by_cat or {}).values():
        for w in (words or []):
            word = (w or {}).get('word') or ''
            nw = _norm_match(word)
            if not nw:
                continue
            if q_norm == nw:
                score = 100
            elif nw.startswith(q_norm):
                score = 80
            elif q_norm in nw:
                score = 60
            else:
                score = 0
            if score > best_score:
                best = w
                best_score = score
                if best_score >= 100:
                    return best, best_score
    return best, best_score


def _best_vocab_match_english(vocab_by_cat, q_norm: str):
    if not q_norm:
        return None, 0

    q_tokens = q_norm.split()
    q_single = len(q_tokens) == 1

    best = None
    best_score = 0
    for words in (vocab_by_cat or {}).values():
        for w in (words or []):
            eng = (w or {}).get('english') or ''
            glosses = _split_english_glosses(eng)
            if not glosses:
                continue

            score = 0
            for g in glosses:
                ng = _norm_match(g)
                if not ng:
                    continue

                if q_norm == ng:
                    score = max(score, 100)
                    continue

                if q_single:
                    g_tokens = ng.split()
                    if g_tokens and g_tokens[0] == q_norm:
                        score = max(score, 88)
                        continue
                    if q_norm in g_tokens:
                        score = max(score, 55)
                        continue
                    if ng.startswith(q_norm):
                        score = max(score, 60)
                        continue
                    if q_norm in ng:
                        score = max(score, 45)
                        continue
                else:
                    if ng.startswith(q_norm):
                        score = max(score, 85)
                        continue
                    if q_norm in ng:
                        score = max(score, 70)
                        continue

            if score > best_score:
                best = w
                best_score = score
    return best, best_score


def _best_vocab_match_bengali(vocab_by_cat, q_bn: str):
    if not q_bn:
        return None, 0

    best = None
    best_score = 0
    for words in (vocab_by_cat or {}).values():
        for w in (words or []):
            bn = _norm_bn((w or {}).get('bengali') or '')
            if not bn:
                continue

            if q_bn == bn:
                score = 100
            elif q_bn in bn:
                score = 80
            else:
                score = 0

            if score > best_score:
                best = w
                best_score = score
    return best, best_score


@lru_cache(maxsize=4096)
def _mymemory_translate(text: str, source: str, target: str) -> str:
    q = (text or '').strip()
    if not q:
        return ''

    url = 'https://api.mymemory.translated.net/get?' + urlencode({
        'q': q,
        'langpair': f'{source}|{target}',
    })
    req = Request(url, headers={'User-Agent': 'LanguageCoach/1.0'})

    with urlopen(req, timeout=8) as resp:
        payload = json.loads(resp.read().decode('utf-8', errors='replace') or '{}')

    status = str(payload.get('responseStatus', ''))
    if status != '200':
        detail = (payload.get('responseDetails') or '').strip()
        raise RuntimeError(detail or f'MyMemory error (status {status})')

    translated = (((payload.get('responseData') or {}) or {}).get('translatedText') or '').strip()
    return translated


def _local_translate_lookup(text: str, source_hint: str):
    vocab_all = get_vocab()
    fr_vocab = vocab_all.get('french', {}) or {}
    es_vocab = vocab_all.get('spanish', {}) or {}

    has_bn = _has_bengali_script(text)
    q_norm = _norm_match(text) if not has_bn else ''
    q_bn = _norm_bn(text) if has_bn else ''

    fr_word, fr_word_score = _best_vocab_match_word(fr_vocab, q_norm)
    es_word, es_word_score = _best_vocab_match_word(es_vocab, q_norm)

    detected = (source_hint or 'auto').strip().lower()
    if detected not in {'auto', 'en', 'fr', 'es', 'bn'}:
        detected = 'auto'

    if detected == 'auto':
        if has_bn:
            detected = 'bn'
        elif fr_word_score >= 90 and fr_word_score > es_word_score:
            detected = 'fr'
        elif es_word_score >= 90 and es_word_score > fr_word_score:
            detected = 'es'
        else:
            detected = 'en'

    results = {'en': None, 'fr': None, 'es': None, 'bn': None}

    if detected == 'fr':
        if fr_word:
            results['fr'] = (fr_word.get('word') or '').strip() or None
            results['en'] = (fr_word.get('english') or '').strip() or None
            results['bn'] = (fr_word.get('bengali') or '').strip() or None
            pivot = _primary_gloss(results['en'] or '')
            es_by_en, _ = _best_vocab_match_english(es_vocab, _norm_match(pivot)) if pivot else (None, 0)
            if es_by_en:
                results['es'] = (es_by_en.get('word') or '').strip() or None
        else:
            results['fr'] = text

    elif detected == 'es':
        if es_word:
            results['es'] = (es_word.get('word') or '').strip() or None
            results['en'] = (es_word.get('english') or '').strip() or None
            results['bn'] = (es_word.get('bengali') or '').strip() or None
            pivot = _primary_gloss(results['en'] or '')
            fr_by_en, _ = _best_vocab_match_english(fr_vocab, _norm_match(pivot)) if pivot else (None, 0)
            if fr_by_en:
                results['fr'] = (fr_by_en.get('word') or '').strip() or None
        else:
            results['es'] = text

    elif detected == 'bn':
        fr_by_bn, fr_bn_score = _best_vocab_match_bengali(fr_vocab, q_bn)
        es_by_bn, es_bn_score = _best_vocab_match_bengali(es_vocab, q_bn)

        best = fr_by_bn if fr_bn_score >= es_bn_score else es_by_bn
        if best:
            results['en'] = (best.get('english') or '').strip() or None
        if fr_by_bn:
            results['fr'] = (fr_by_bn.get('word') or '').strip() or None
        if es_by_bn:
            results['es'] = (es_by_bn.get('word') or '').strip() or None
        results['bn'] = text

        pivot = _primary_gloss(results['en'] or '')
        pivot_norm = _norm_match(pivot) if pivot else ''
        if pivot_norm:
            if not results['fr']:
                fr_by_en, _ = _best_vocab_match_english(fr_vocab, pivot_norm)
                if fr_by_en:
                    results['fr'] = (fr_by_en.get('word') or '').strip() or None
            if not results['es']:
                es_by_en, _ = _best_vocab_match_english(es_vocab, pivot_norm)
                if es_by_en:
                    results['es'] = (es_by_en.get('word') or '').strip() or None

    else:  # detected == 'en'
        fr_by_en, fr_score = _best_vocab_match_english(fr_vocab, q_norm)
        es_by_en, es_score = _best_vocab_match_english(es_vocab, q_norm)

        results['en'] = text

        min_score = 90  # Avoid overly-specific matches like "wine glass" for "glass"
        best_bn_score = 0

        if fr_by_en and fr_score >= min_score:
            results['fr'] = (fr_by_en.get('word') or '').strip() or None
            bn = (fr_by_en.get('bengali') or '').strip()
            if bn and fr_score > best_bn_score:
                results['bn'] = bn
                best_bn_score = fr_score

        if es_by_en and es_score >= min_score:
            results['es'] = (es_by_en.get('word') or '').strip() or None
            bn = (es_by_en.get('bengali') or '').strip()
            if bn and es_score > best_bn_score:
                results['bn'] = bn
                best_bn_score = es_score

    return detected, results

_SENT_TOKEN_RE = re.compile(r"[A-Za-zÀ-ÿ]+(?:'[A-Za-zÀ-ÿ]+)?")


def _blank_first_token(sentence: str, word: str) -> Optional[str]:
    """Return sentence with first matching token replaced by ____ (accent/case tolerant)."""
    if not sentence or not word:
        return None
    variants = set(_word_match_variants(word))
    if not variants:
        return None

    for m in _SENT_TOKEN_RE.finditer(sentence):
        tok = m.group(0)
        tok_norm = _norm_match(tok)
        if tok_norm in variants:
            return sentence[:m.start()] + '____' + sentence[m.end():]
    return None


_STOPWORDS = {
    # Normalized (lowercased, accents stripped) to match _norm_match()
    'french': {
        'a', 'au', 'aux', 'avec', 'ce', 'ces', 'cest', 'dans', 'de', 'des', 'du', 'elle', 'en', 'et',
        'il', 'ils', 'je', 'la', 'le', 'les', 'leur', 'leurs', 'ma', 'mais', 'mes', 'mon', 'ne', 'nous',
        'on', 'ou', 'par', 'pas', 'pour', 'que', 'qui', 'sa', 'se', 'ses', 'son', 'ta', 'te', 'tes',
        'toi', 'ton', 'tu', 'un', 'une', 'vous', 'y',
    },
    'spanish': {
        'a', 'al', 'con', 'como', 'de', 'del', 'el', 'ella', 'ellas', 'ellos', 'en', 'es', 'esta', 'esto',
        'la', 'las', 'lo', 'los', 'mas', 'mi', 'mis', 'muy', 'no', 'nosotros', 'o', 'para', 'pero', 'por',
        'porque', 'que', 'se', 'si', 'sin', 'su', 'sus', 'tu', 'tus', 'un', 'una', 'unos', 'unas', 'y',
        'yo',
    },
}


def _build_vocab_variant_index(vocab_by_cat):
    entries = []
    variant_index = {}
    for cat, words in (vocab_by_cat or {}).items():
        for w in (words or []):
            word = (w or {}).get('word')
            if not word:
                continue
            entry = {**w, 'category': cat}
            entries.append(entry)
            for v in _word_match_variants(word):
                if v and v not in variant_index:
                    variant_index[v] = entry
    return entries, variant_index


def _compute_resource_insights(lang, resource_sentences, vocab_by_cat, lesson_list, progress):
    if not resource_sentences:
        return None

    sample_limit = 900
    sample = (
        resource_sentences
        if len(resource_sentences) <= sample_limit
        else random.sample(resource_sentences, sample_limit)
    )

    entries, variant_index = _build_vocab_variant_index(vocab_by_cat)
    category_counts = {}
    total_tokens = 0
    matched_tokens = 0

    sources = set()
    for s in resource_sentences:
        src = (s.get('source') or '').strip()
        if src:
            sources.add(src)

    for s in sample:
        text = (s.get('text') or '').strip()
        if not text:
            continue
        for tok in _SENT_TOKEN_RE.findall(text):
            norm = _norm_match(tok)
            if not norm:
                continue
            total_tokens += 1
            entry = variant_index.get(norm)
            if not entry:
                continue
            matched_tokens += 1
            cat = entry.get('category')
            if cat:
                category_counts[cat] = category_counts.get(cat, 0) + 1

    coverage_pct = int(round((matched_tokens / total_tokens) * 100)) if total_tokens else 0
    top_cats = sorted(category_counts.items(), key=lambda x: (-x[1], x[0]))[:3]
    top_categories = [
        {'id': cat, 'label': cat.replace('_', ' ').title(), 'count': cnt}
        for cat, cnt in top_cats
    ]

    focus_lesson = None
    best_score = 0
    for lesson in _sorted_lessons(lesson_list):
        lid = lesson.get('id')
        if (progress or {}).get(lid, {}).get('completed'):
            continue
        score = sum(category_counts.get(c, 0) for c in (lesson.get('vocabulary_categories') or []))
        if score > best_score:
            best_score = score
            focus_lesson = lesson

    if best_score <= 0:
        focus_lesson = None

    return {
        'sentence_count': len(resource_sentences),
        'source_count': len(sources),
        'coverage_pct': coverage_pct,
        'top_categories': top_categories,
        'focus_lesson': focus_lesson,
    }


def _build_resource_drill_questions(lang, total_q, vocab_by_cat, vocab_all, resource_sentences, tts_lang, user_id=None):
    if not resource_sentences:
        return []

    entries, variant_index = _build_vocab_variant_index(vocab_by_cat)
    if not entries:
        return []

    stop = _STOPWORDS.get(lang, set())

    # Prefer due words, but fall back to any vocab word if no SRS history exists.
    now_iso = datetime.now().isoformat(timespec='seconds')
    conn = get_db()
    if user_id is None:
        due_rows = conn.execute('''
            SELECT word
            FROM word_progress
            WHERE language=?
              AND (next_due IS NULL OR next_due <= ?)
            ORDER BY COALESCE(next_due, '') ASC, box ASC, incorrect DESC
            LIMIT ?
        ''', (lang, now_iso, max(200, total_q * 12))).fetchall()
    else:
        due_rows = conn.execute('''
            SELECT word
            FROM user_word_progress
            WHERE user_id=?
              AND language=?
              AND (next_due IS NULL OR next_due <= ?)
            ORDER BY COALESCE(next_due, '') ASC, box ASC, incorrect DESC
            LIMIT ?
        ''', (user_id, lang, now_iso, max(200, total_q * 12))).fetchall()
    conn.close()
    due_set = {r['word'] for r in due_rows if r.get('word')}

    wrong_pool = [w.get('word') for w in vocab_all if w.get('word')]
    wrong_pool = [w for w in dict.fromkeys(wrong_pool) if w]  # stable de-dupe

    used_words = set()
    questions = []
    attempts = 0
    max_attempts = total_q * 80

    while len(questions) < total_q and attempts < max_attempts:
        attempts += 1
        s = random.choice(resource_sentences)
        text = (s.get('text') or '').strip()
        if not text:
            continue

        candidates = []
        seen = set()
        for tok in _SENT_TOKEN_RE.findall(text):
            norm = _norm_match(tok)
            if not norm or norm in stop:
                continue
            entry = variant_index.get(norm)
            if not entry:
                continue
            w = entry.get('word')
            if not w or w in seen or ' ' in w:
                continue
            seen.add(w)
            candidates.append(entry)

        if due_set:
            due_candidates = [e for e in candidates if e.get('word') in due_set]
            if due_candidates:
                candidates = due_candidates

        if not candidates:
            continue

        # Prefer not to repeat words in the same session if possible.
        fresh = [e for e in candidates if e.get('word') and e.get('word') not in used_words]
        pick_from = fresh or candidates
        entry = random.choice(pick_from)

        word = entry.get('word')
        if not word:
            continue
        blanked = _blank_first_token(text, word)
        if not blanked:
            continue

        english = entry.get('english', '')
        bengali = entry.get('bengali', '')
        hint = f"Hint: {english}" if english else 'Hint:'
        if bengali:
            hint += f" \u2022 বাংলা: {bengali}"

        # Choices: correct + 3 wrong
        wrong_choices = [w for w in wrong_pool if w != word]
        random.shuffle(wrong_choices)
        choices = [word] + wrong_choices[:3]
        if len(choices) < 2:
            continue

        q = {
            'kind': 'mcq',
            'mode': 'resource_cloze',
            'mode_label': '📚 Resource',
            'prompt_en': f"Fill in the blank: {blanked}",
            'prompt_bn': hint,
            'tts_text': text,
            'tts_lang': tts_lang,
            'choices': choices,
            'answer': word,
            'word': word,
            'xp_correct': 14,
            'xp_wrong': 3,
        }

        q['id'] = len(questions) + 1
        random.shuffle(q['choices'])
        questions.append(q)
        used_words.add(word)

    return questions

# ---------- Database helpers ----------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            email       TEXT NOT NULL UNIQUE,
            created_at  TEXT,
            last_login  TEXT
        );
        CREATE TABLE IF NOT EXISTS lesson_progress (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            language    TEXT    NOT NULL,
            lesson_id   INTEGER NOT NULL,
            completed   INTEGER DEFAULT 0,
            best_score  INTEGER DEFAULT 0,
            attempts    INTEGER DEFAULT 0,
            last_seen   TEXT,
            UNIQUE(language, lesson_id)
        );
        CREATE TABLE IF NOT EXISTS user_lesson_progress (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            language    TEXT    NOT NULL,
            lesson_id   INTEGER NOT NULL,
            completed   INTEGER DEFAULT 0,
            best_score  INTEGER DEFAULT 0,
            attempts    INTEGER DEFAULT 0,
            last_seen   TEXT,
            UNIQUE(user_id, language, lesson_id)
        );
        CREATE TABLE IF NOT EXISTS word_progress (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            language    TEXT NOT NULL,
            word        TEXT NOT NULL,
            correct     INTEGER DEFAULT 0,
            incorrect   INTEGER DEFAULT 0,
            UNIQUE(language, word)
        );
        CREATE TABLE IF NOT EXISTS user_word_progress (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            language    TEXT NOT NULL,
            word        TEXT NOT NULL,
            correct     INTEGER DEFAULT 0,
            incorrect   INTEGER DEFAULT 0,
            box         INTEGER DEFAULT 1,
            next_due    TEXT,
            last_review TEXT,
            UNIQUE(user_id, language, word)
        );
        CREATE TABLE IF NOT EXISTS daily_activity (
            date     TEXT PRIMARY KEY,
            xp       INTEGER DEFAULT 0,
            reviews  INTEGER DEFAULT 0,
            correct  INTEGER DEFAULT 0,
            wrong    INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS user_daily_activity (
            user_id  INTEGER NOT NULL,
            date     TEXT NOT NULL,
            xp       INTEGER DEFAULT 0,
            reviews  INTEGER DEFAULT 0,
            correct  INTEGER DEFAULT 0,
            wrong    INTEGER DEFAULT 0,
            PRIMARY KEY(user_id, date)
        );
        CREATE TABLE IF NOT EXISTS feedback (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            name       TEXT,
            email      TEXT,
            category   TEXT,
            language   TEXT,
            message    TEXT,
            page       TEXT,
            created_at TEXT
        );
    ''')

    # Lightweight migrations (for evolving DB schema over time)
    def _ensure_columns(table, columns):
        existing = {r['name'] for r in conn.execute(f'PRAGMA table_info({table})').fetchall()}
        for name, definition in columns.items():
            if name in existing:
                continue
            conn.execute(f'ALTER TABLE {table} ADD COLUMN {name} {definition}')

    _ensure_columns('word_progress', {
        'box': 'INTEGER DEFAULT 1',
        'next_due': 'TEXT',
        'last_review': 'TEXT',
    })
    _ensure_columns('user_word_progress', {
        'box': 'INTEGER DEFAULT 1',
        'next_due': 'TEXT',
        'last_review': 'TEXT',
    })

    # Performance indexes for SRS due-word queries (no-op if already present)
    conn.executescript('''
        CREATE INDEX IF NOT EXISTS idx_wp_lang_due
            ON word_progress(language, next_due);
        CREATE INDEX IF NOT EXISTS idx_wp_lang_word
            ON word_progress(language, word);
        CREATE INDEX IF NOT EXISTS idx_uwp_user_lang_due
            ON user_word_progress(user_id, language, next_due);
        CREATE INDEX IF NOT EXISTS idx_uwp_user_lang_word
            ON user_word_progress(user_id, language, word);
        CREATE INDEX IF NOT EXISTS idx_ulp_user_lang
            ON user_lesson_progress(user_id, language);
        CREATE INDEX IF NOT EXISTS idx_uda_user_date
            ON user_daily_activity(user_id, date);
        CREATE INDEX IF NOT EXISTS idx_feedback_created_at
            ON feedback(created_at);
    ''')

    conn.commit()
    conn.close()

# Initialise DB at import time so gunicorn (production) also creates tables
init_db()

_EMAIL_SIMPLE_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def _normalize_email(value: str) -> str:
    return (value or '').strip().lower()


def _is_valid_email(value: str) -> bool:
    v = _normalize_email(value)
    if not v or len(v) > 320:
        return False
    return bool(_EMAIL_SIMPLE_RE.match(v))


def _default_name_from_email(email: str) -> str:
    """Derive a reasonable display name from an email address."""
    email = _normalize_email(email)
    local = email.split('@', 1)[0] if '@' in email else email
    local = re.sub(r'[^a-z0-9._-]+', ' ', local, flags=re.IGNORECASE).strip()
    local = re.sub(r'[._-]+', ' ', local).strip()
    local = re.sub(r'\s+', ' ', local).strip()
    if not local:
        return 'Learner'
    # Title-case only if it's mostly latin letters/numbers (avoid mangling other scripts).
    if re.fullmatch(r'[a-z0-9 ]+', local, flags=re.IGNORECASE):
        return local.title()
    return local


def _sheets_send(action: str, sheet: str, row: dict):
    """Send a row to Google Sheets via an Apps Script webhook (optional).

    This is best-effort: failures are swallowed so the learning app remains usable.
    Configure via env vars:
      - SHEETS_WEBHOOK_URL
      - SHEETS_WEBHOOK_TOKEN (optional but recommended)
    """
    if not SHEETS_WEBHOOK_URL:
        return

    payload = {
        'action': (action or '').strip() or 'append_row',
        'sheet': (sheet or '').strip() or SHEETS_EVENTS_SHEET,
        'row': row or {},
    }
    if SHEETS_WEBHOOK_TOKEN:
        payload['token'] = SHEETS_WEBHOOK_TOKEN

    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req = Request(
        SHEETS_WEBHOOK_URL,
        data=body,
        headers={'Content-Type': 'application/json; charset=utf-8'},
    )

    def _do_post():
        try:
            with urlopen(req, timeout=SHEETS_WEBHOOK_TIMEOUT) as resp:
                # Read a tiny amount to ensure the request completes.
                resp.read(256)
        except Exception:
            return

    try:
        threading.Thread(target=_do_post, daemon=True).start()
    except Exception:
        # As a last resort, just skip (don't crash the app).
        return


def _sheets_send_sync(action: str, sheet: str, row: dict):
    """Send a row to Google Sheets and return status (for UX / debugging)."""
    if not SHEETS_WEBHOOK_URL:
        return {'enabled': False, 'ok': False, 'error': 'not_configured'}

    payload = {
        'action': (action or '').strip() or 'append_row',
        'sheet': (sheet or '').strip() or SHEETS_EVENTS_SHEET,
        'row': row or {},
    }
    if SHEETS_WEBHOOK_TOKEN:
        payload['token'] = SHEETS_WEBHOOK_TOKEN

    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req = Request(
        SHEETS_WEBHOOK_URL,
        data=body,
        headers={'Content-Type': 'application/json; charset=utf-8'},
    )
    try:
        with urlopen(req, timeout=SHEETS_WEBHOOK_TIMEOUT) as resp:
            raw = (resp.read(8192) or b'')
    except Exception as exc:
        return {'enabled': True, 'ok': False, 'error': str(exc) or type(exc).__name__}

    try:
        parsed = json.loads(raw.decode('utf-8', 'replace') or '{}')
    except Exception:
        return {'enabled': True, 'ok': False, 'error': 'non_json_response'}

    if isinstance(parsed, dict):
        ok = bool(parsed.get('ok'))
        err = parsed.get('error')
        return {'enabled': True, 'ok': ok, 'error': err or None}

    return {'enabled': True, 'ok': False, 'error': 'invalid_response'}


def _user_snapshot(user_id: int):
    """Return per-language progress + today's activity for a user (or empty)."""
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return {}, {'xp_today': 0, 'reviews_today': 0, 'correct_today': 0, 'wrong_today': 0}

    lessons_all = get_lessons()
    out = {}
    for lang in LANGS:
        prog = load_progress(lang, user_id=user_id)
        total = len(lessons_all.get(lang, []) or [])
        completed = sum(1 for v in (prog or {}).values() if v.get('completed'))
        out[lang] = {
            'completed': int(completed),
            'total': int(total),
            'percent': int(completed / total * 100) if total else 0,
        }

    activity = get_activity_summary(user_id=user_id) or {}
    return out, activity


def _emit_user_snapshot_to_sheets(user: dict, last_event: str = '', language: str = '', lesson_id=None, score=None, page: str = ''):
    if not user or not user.get('email'):
        return
    uid = user.get('id')
    progress, activity = _user_snapshot(uid)
    now_iso = datetime.now().isoformat(timespec='seconds')

    fr = progress.get('french') or {}
    es = progress.get('spanish') or {}

    row = {
        'updated_at': now_iso,
        'user_id': uid or '',
        'name': user.get('name') or '',
        'email': user.get('email') or '',
        'last_login': user.get('last_login') or '',
        'last_event': last_event or '',
        'last_lang': language or '',
        'last_lesson_id': lesson_id if lesson_id is not None else '',
        'last_score': score if score is not None else '',
        'french_completed': fr.get('completed', ''),
        'french_total': fr.get('total', ''),
        'french_percent': fr.get('percent', ''),
        'spanish_completed': es.get('completed', ''),
        'spanish_total': es.get('total', ''),
        'spanish_percent': es.get('percent', ''),
        'xp_today': activity.get('xp_today', 0),
        'reviews_today': activity.get('reviews_today', 0),
        'correct_today': activity.get('correct_today', 0),
        'wrong_today': activity.get('wrong_today', 0),
        'page': page or '',
    }

    _sheets_send('upsert_user', SHEETS_USERS_SHEET, row)


def _emit_event_to_sheets(event: str, user: dict = None, language: str = '', lesson_id=None, score=None,
                          category: str = '', message: str = '', page: str = ''):
    now_iso = datetime.now().isoformat(timespec='seconds')
    user = user or {}
    uid = user.get('id')
    progress, activity = _user_snapshot(uid) if uid is not None else ({}, {})
    fr = progress.get('french') or {}
    es = progress.get('spanish') or {}

    row = {
        'timestamp': now_iso,
        'event': (event or '').strip(),
        'user_id': uid or '',
        'name': user.get('name') or '',
        'email': user.get('email') or '',
        'language': language or '',
        'lesson_id': lesson_id if lesson_id is not None else '',
        'score': score if score is not None else '',
        'category': category or '',
        'message': (message or '')[:2000],
        'page': page or '',
        'french_completed': fr.get('completed', ''),
        'french_total': fr.get('total', ''),
        'french_percent': fr.get('percent', ''),
        'spanish_completed': es.get('completed', ''),
        'spanish_total': es.get('total', ''),
        'spanish_percent': es.get('percent', ''),
        'xp_today': activity.get('xp_today', 0) if activity else '',
        'reviews_today': activity.get('reviews_today', 0) if activity else '',
        'correct_today': activity.get('correct_today', 0) if activity else '',
        'wrong_today': activity.get('wrong_today', 0) if activity else '',
    }

    _sheets_send('append_row', SHEETS_EVENTS_SHEET, row)


def get_user_by_id(user_id: int):
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return None

    conn = get_db()
    row = conn.execute(
        'SELECT id, name, email, created_at, last_login FROM users WHERE id=?', (user_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_email(email: str):
    email = _normalize_email(email)
    if not email:
        return None
    conn = get_db()
    row = conn.execute(
        'SELECT id, name, email, created_at, last_login FROM users WHERE email=?', (email,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def upsert_user(name: str, email: str) -> int:
    name = (name or '').strip()
    email = _normalize_email(email)
    if not email:
        raise ValueError('Missing email')

    now_iso = datetime.now().isoformat(timespec='seconds')
    conn = get_db()
    row = conn.execute('SELECT id, name FROM users WHERE email=?', (email,)).fetchone()
    if row:
        user_id = int(row['id'])
        # Preserve the existing name unless a non-empty name was provided.
        if name:
            conn.execute('UPDATE users SET name=?, last_login=? WHERE id=?', (name, now_iso, user_id))
        else:
            conn.execute('UPDATE users SET last_login=? WHERE id=?', (now_iso, user_id))
    else:
        if not name:
            name = _default_name_from_email(email)
        cur = conn.execute(
            'INSERT INTO users (name, email, created_at, last_login) VALUES (?, ?, ?, ?)',
            (name, email, now_iso, now_iso),
        )
        user_id = int(cur.lastrowid)
    conn.commit()
    conn.close()
    return user_id


def current_user_id():
    try:
        uid = session.get('user_id')
        return int(uid) if uid is not None else None
    except (TypeError, ValueError):
        return None


def load_progress(lang, user_id=None):
    conn = get_db()
    if user_id is None:
        rows = conn.execute(
            'SELECT lesson_id, completed, best_score, attempts, last_seen FROM lesson_progress WHERE language=?', (lang,)
        ).fetchall()
    else:
        rows = conn.execute(
            'SELECT lesson_id, completed, best_score, attempts, last_seen FROM user_lesson_progress WHERE user_id=? AND language=?',
            (user_id, lang),
        ).fetchall()
    conn.close()
    return {r['lesson_id']: dict(r) for r in rows}

def touch_lesson(lang, lesson_id, user_id=None):
    """Update last_seen for a lesson even if the user doesn't finish a quiz."""
    conn = get_db()
    now_iso = datetime.now().isoformat(timespec='seconds')
    if user_id is None:
        conn.execute('''
            INSERT INTO lesson_progress (language, lesson_id, completed, best_score, attempts, last_seen)
            VALUES (?, ?, 0, 0, 0, ?)
            ON CONFLICT(language, lesson_id) DO UPDATE SET
                last_seen = excluded.last_seen
        ''', (lang, lesson_id, now_iso))
    else:
        conn.execute('''
            INSERT INTO user_lesson_progress (user_id, language, lesson_id, completed, best_score, attempts, last_seen)
            VALUES (?, ?, ?, 0, 0, 0, ?)
            ON CONFLICT(user_id, language, lesson_id) DO UPDATE SET
                last_seen = excluded.last_seen
        ''', (user_id, lang, lesson_id, now_iso))
    conn.commit()
    conn.close()

def add_activity(xp=0, reviews=0, correct=0, wrong=0, user_id=None):
    xp = int(xp or 0)
    reviews = int(reviews or 0)
    correct = int(correct or 0)
    wrong = int(wrong or 0)
    if xp == 0 and reviews == 0 and correct == 0 and wrong == 0:
        return

    today = date.today().isoformat()
    conn = get_db()
    if user_id is None:
        conn.execute('''
            INSERT INTO daily_activity (date, xp, reviews, correct, wrong)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                xp = xp + excluded.xp,
                reviews = reviews + excluded.reviews,
                correct = correct + excluded.correct,
                wrong = wrong + excluded.wrong
        ''', (today, xp, reviews, correct, wrong))
    else:
        conn.execute('''
            INSERT INTO user_daily_activity (user_id, date, xp, reviews, correct, wrong)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, date) DO UPDATE SET
                xp = xp + excluded.xp,
                reviews = reviews + excluded.reviews,
                correct = correct + excluded.correct,
                wrong = wrong + excluded.wrong
        ''', (user_id, today, xp, reviews, correct, wrong))
    conn.commit()
    conn.close()


def get_activity_summary(user_id=None):
    today = date.today()
    today_key = today.isoformat()

    conn = get_db()
    if user_id is None:
        row = conn.execute(
            'SELECT xp, reviews, correct, wrong FROM daily_activity WHERE date=?', (today_key,)
        ).fetchone()
        rows = conn.execute(
            'SELECT date, xp FROM daily_activity WHERE xp > 0 ORDER BY date DESC LIMIT 60'
        ).fetchall()
    else:
        row = conn.execute(
            'SELECT xp, reviews, correct, wrong FROM user_daily_activity WHERE user_id=? AND date=?', (user_id, today_key)
        ).fetchone()
        rows = conn.execute(
            'SELECT date, xp FROM user_daily_activity WHERE user_id=? AND xp > 0 ORDER BY date DESC LIMIT 60', (user_id,)
        ).fetchall()
    conn.close()

    xp_today = int(row['xp']) if row else 0
    reviews_today = int(row['reviews']) if row else 0

    active_dates = {r['date'] for r in rows}
    streak = 0
    cursor = today
    while cursor.isoformat() in active_dates:
        streak += 1
        cursor -= timedelta(days=1)

    return {
        'xp_today': xp_today,
        'reviews_today': reviews_today,
        'streak_days': streak,
    }

# ---------- Helpers ----------
def get_lesson_vocab(lang, lesson):
    words = []
    vocab_by_cat = (get_vocab().get(lang) or {})
    slices = lesson.get('vocabulary_slices') or {}
    try:
        default_limit = int(lesson.get('vocab_limit_per_category') or 60)
    except (TypeError, ValueError):
        default_limit = 60

    for cat in (lesson.get('vocabulary_categories') or []):
        cat_words = list(vocab_by_cat.get(cat, []) or [])
        if not cat_words:
            continue

        sl = slices.get(cat) or {}
        try:
            offset = int(sl.get('offset') or 0)
        except (TypeError, ValueError):
            offset = 0

        limit = sl.get('limit', None)
        if limit is None:
            limit = default_limit
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = default_limit

        offset = max(0, offset)
        if limit > 0:
            cat_words = cat_words[offset: offset + limit]
        else:
            cat_words = cat_words[offset:]

        words.extend(cat_words)

    return words


_PDF_FONT_LOCK = threading.Lock()
_PDF_FONT_READY = False
_PDF_FONT_NAME = 'LC-NotoSerifBengali'
_PDF_FONT_PATH = os.path.join(BASE_DIR, 'static', 'fonts', 'NotoSerifBengali-Regular.ttf')


def _ensure_pdf_font_registered() -> bool:
    """Register a Unicode font for Bengali/Latin PDF exports (idempotent)."""
    global _PDF_FONT_READY  # noqa: PLW0603 - intentional cache flag
    if _PDF_FONT_READY:
        return True

    with _PDF_FONT_LOCK:
        if _PDF_FONT_READY:
            return True

        if not os.path.exists(_PDF_FONT_PATH):
            return False

        try:
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
        except Exception:
            return False

        try:
            if _PDF_FONT_NAME not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(_PDF_FONT_NAME, _PDF_FONT_PATH))
        except Exception as exc:
            print(f"WARNING: Could not register PDF font {_PDF_FONT_NAME}: {exc}")
            return False

        _PDF_FONT_READY = True
        return True


def _escape_paragraph_text(text: str) -> str:
    """Escape text for reportlab Paragraph (minimal XML escaping)."""
    s = '' if text is None else str(text)
    s = s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    s = s.replace('\r\n', '\n').replace('\r', '\n').replace('\n', '<br/>')
    return s


def _build_lesson_pdf_bytes_reportlab(lang: str, meta: dict, lesson: dict, vocabulary: list, grammar: Optional[dict]) -> bytes:
    """Render a single lesson as a downloadable PDF."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import ParagraphStyle
    except Exception as exc:
        raise RuntimeError("Missing dependency: reportlab. Run: pip install -r requirements.txt") from exc

    if not _ensure_pdf_font_registered():
        raise RuntimeError(f"Missing PDF font file: {_PDF_FONT_PATH}")

    font_name = _PDF_FONT_NAME
    page_w, page_h = A4
    left = right = 36
    top = bottom = 40
    content_width = page_w - left - right

    def para(text: str, style: ParagraphStyle) -> Paragraph:
        return Paragraph(_escape_paragraph_text(text), style)

    styles = {
        'title': ParagraphStyle(
            name='LCTitle',
            fontName=font_name,
            fontSize=18,
            leading=22,
            spaceAfter=10,
        ),
        'subtitle': ParagraphStyle(
            name='LCSubtitle',
            fontName=font_name,
            fontSize=11,
            leading=14,
            textColor=colors.HexColor('#444444'),
            spaceAfter=14,
        ),
        'h2': ParagraphStyle(
            name='LCH2',
            fontName=font_name,
            fontSize=13,
            leading=16,
            spaceBefore=10,
            spaceAfter=8,
            textColor=colors.HexColor('#111111'),
        ),
        'normal': ParagraphStyle(
            name='LCNormal',
            fontName=font_name,
            fontSize=11,
            leading=14,
            textColor=colors.HexColor('#111111'),
            spaceAfter=6,
        ),
        'muted': ParagraphStyle(
            name='LCMuted',
            fontName=font_name,
            fontSize=11,
            leading=14,
            textColor=colors.HexColor('#444444'),
            spaceAfter=6,
        ),
        'cell': ParagraphStyle(
            name='LCCell',
            fontName=font_name,
            fontSize=9,
            leading=11,
            textColor=colors.HexColor('#111111'),
        ),
    }

    story = []

    lesson_no = lesson.get('id', '')
    title_en = (lesson.get('title_en') or '').strip()
    title_bn = (lesson.get('title_bn') or '').strip()
    title_lang = (lesson.get('title_lang') or '').strip()

    story.append(para(f"{meta.get('name', '').strip()} — Lesson {lesson_no}", styles['h2']))
    story.append(para(title_en or f"Lesson {lesson_no}", styles['title']))
    subparts = [p for p in (title_bn, title_lang) if p]
    if subparts:
        story.append(para(' • '.join(subparts), styles['subtitle']))
    else:
        story.append(Spacer(1, 6))

    desc_en = (lesson.get('description_en') or '').strip()
    desc_bn = (lesson.get('description_bn') or '').strip()
    if desc_en:
        story.append(para(desc_en, styles['normal']))
    if desc_bn:
        story.append(para(desc_bn, styles['muted']))

    tip_en = (lesson.get('tip_en') or '').strip()
    tip_bn = (lesson.get('tip_bn') or '').strip()
    if tip_en or tip_bn:
        story.append(Spacer(1, 6))
        story.append(para("Tip", styles['h2']))
        if tip_en:
            story.append(para(tip_en, styles['normal']))
        if tip_bn:
            story.append(para(tip_bn, styles['muted']))

    # Vocabulary
    story.append(Spacer(1, 6))
    story.append(para("Vocabulary — শব্দভান্ডার", styles['h2']))
    if vocabulary:
        header = [
            para("Word", styles['cell']),
            para("Pron.", styles['cell']),
            para("English", styles['cell']),
            para("বাংলা", styles['cell']),
        ]
        rows = [header]
        for w in vocabulary:
            article = (w.get('article') or '').strip()
            word = (w.get('word') or '').strip()
            full_word = (article + (' ' if article and not article.endswith("'") else '') + word).strip()
            rows.append([
                para(full_word, styles['cell']),
                para((w.get('pronunciation') or '').strip(), styles['cell']),
                para((w.get('english') or '').strip(), styles['cell']),
                para((w.get('bengali') or '').strip(), styles['cell']),
            ])

        col_widths = [0.22 * content_width, 0.16 * content_width, 0.30 * content_width, 0.32 * content_width]
        vocab_table = Table(rows, colWidths=col_widths, repeatRows=1, hAlign='LEFT')
        vocab_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f3f5')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#111111')),
            ('LINEBELOW', (0, 0), (-1, 0), 0.5, colors.HexColor('#adb5bd')),
            ('GRID', (0, 1), (-1, -1), 0.25, colors.HexColor('#ced4da')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#fbfcfd')]),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(vocab_table)
    else:
        story.append(para("No vocabulary for this lesson.", styles['muted']))

    # Grammar
    if grammar:
        story.append(Spacer(1, 10))
        story.append(para("Grammar — ব্যাকরণ", styles['h2']))
        intro_en = (grammar.get('intro_en') or '').strip()
        intro_bn = (grammar.get('intro_bn') or '').strip()
        if intro_en:
            story.append(para(intro_en, styles['normal']))
        if intro_bn:
            story.append(para(intro_bn, styles['muted']))

        for section in (grammar.get('sections') or []):
            sec_en = (section.get('title_en') or '').strip()
            sec_bn = (section.get('title_bn') or '').strip()
            if sec_en or sec_bn:
                story.append(Spacer(1, 8))
                story.append(para(sec_en or sec_bn, styles['h2']))
                if sec_en and sec_bn:
                    story.append(para(sec_bn, styles['muted']))

            table_rows = section.get('table') or []
            if table_rows:
                ncols = max((len(r) for r in table_rows if r), default=0)
                if ncols > 0:
                    table_data = []
                    for r in table_rows:
                        r = list(r or [])
                        while len(r) < ncols:
                            r.append('')
                        table_data.append([para(str(c), styles['cell']) for c in r[:ncols]])

                    col_w = content_width / ncols
                    g_table = Table(table_data, colWidths=[col_w] * ncols, repeatRows=1, hAlign='LEFT')
                    g_table.setStyle(TableStyle([
                        ('FONTNAME', (0, 0), (-1, -1), font_name),
                        ('FONTSIZE', (0, 0), (-1, -1), 9),
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f3f5')),
                        ('LINEBELOW', (0, 0), (-1, 0), 0.5, colors.HexColor('#adb5bd')),
                        ('GRID', (0, 1), (-1, -1), 0.25, colors.HexColor('#ced4da')),
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ('LEFTPADDING', (0, 0), (-1, -1), 6),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                        ('TOPPADDING', (0, 0), (-1, -1), 4),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ]))
                    story.append(g_table)

            note_en = (section.get('note_en') or '').strip()
            note_bn = (section.get('note_bn') or '').strip()
            if note_en or note_bn:
                story.append(Spacer(1, 6))
                if note_en:
                    story.append(para(f"Note: {note_en}", styles['normal']))
                if note_bn:
                    story.append(para(note_bn, styles['muted']))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=left,
        rightMargin=right,
        topMargin=top,
        bottomMargin=bottom,
        title=f"{meta.get('name', '').strip()} Lesson {lesson_no}",
        author="Language Coach",
    )

    def on_page(canvas, doc_):
        canvas.saveState()
        canvas.setFont(font_name, 9)
        canvas.setFillColor(colors.HexColor('#666666'))
        canvas.drawRightString(page_w - right, 18, f"Page {doc_.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()


_PDF_HTML_ASSET_LOCK = threading.Lock()
_PDF_HTML_ASSET_CACHE = {}

_PDF_HTML_BN_FONT_REG_PATH = os.path.join(BASE_DIR, 'static', 'fonts', 'NotoSerifBengali-Regular.ttf')
_PDF_HTML_BN_FONT_BOLD_PATH = os.path.join(BASE_DIR, 'static', 'fonts', 'NotoSerifBengali-Bold.ttf')


def _file_to_data_uri(path: str, mime: str) -> str:
    with open(path, 'rb') as f:
        b = f.read()
    return f"data:{mime};base64,{base64.b64encode(b).decode('ascii')}"


def _pdf_html_asset(key: str, path: str, mime: str) -> str:
    """Load & cache a small binary asset as a data URI for HTML-to-PDF rendering."""
    with _PDF_HTML_ASSET_LOCK:
        cached = _PDF_HTML_ASSET_CACHE.get(key)
        if cached:
            return cached
        if not os.path.exists(path):
            raise RuntimeError(f"Missing PDF asset: {path}")
        data = _file_to_data_uri(path, mime)
        _PDF_HTML_ASSET_CACHE[key] = data
        return data


def _render_lesson_pdf_html(lang: str, meta: dict, lesson: dict, vocabulary: list, grammar: Optional[dict]) -> str:
    bn_font_regular_data = _pdf_html_asset('bn_font_regular', _PDF_HTML_BN_FONT_REG_PATH, 'font/ttf')
    bn_font_bold_data = _pdf_html_asset('bn_font_bold', _PDF_HTML_BN_FONT_BOLD_PATH, 'font/ttf')
    return render_template(
        'lesson_pdf.html',
        lang=lang,
        meta=meta,
        lesson=lesson,
        vocabulary=vocabulary,
        grammar=grammar,
        bn_font_regular_data=bn_font_regular_data,
        bn_font_bold_data=bn_font_bold_data,
    )


def _lesson_pdf_header_footer(lang: str, meta: dict, lesson: dict) -> tuple[str, str]:
    logo_data = _pdf_html_asset('logo_png', _logo_file_path(), 'image/png')

    lesson_no = lesson.get('id') or ''
    title = (lesson.get('title_en') or '').strip() or f"Lesson {lesson_no}"
    lang_name = (meta.get('name') or lang or '').strip()
    flag = (meta.get('flag') or '').strip()

    header = f"""
    <div style="width:100%; padding:0 36px; font-family:Arial, sans-serif; color:#111;">
      <div style="display:flex; align-items:center; justify-content:space-between; gap:12px; border-bottom:1px solid #e5e5e5; padding-bottom:6px;">
        <div style="display:flex; align-items:center; gap:10px; min-width:0;">
          <div style="width:28px; height:28px; border-radius:999px; overflow:hidden; border:1px solid #e5e5e5; background:#fff; flex:0 0 28px; line-height:0;">
            <img src="{logo_data}" style="width:100%; height:100%; object-fit:cover; object-position:50% 20%; display:block; border-radius:999px;" />
          </div>
          <div style="display:flex; flex-direction:column; min-width:0;">
            <div style="font-size:10px; font-weight:700; line-height:1.1;">Language Coach</div>
            <div style="color:#666; font-size:9px; line-height:1.1; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
              {flag} {lang_name} · Lesson {lesson_no}
            </div>
          </div>
        </div>
        <div style="color:#666; font-size:9px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:40%;">{title}</div>
      </div>
    </div>
    """

    year = datetime.now().year
    footer = f"""
    <div style="width:100%; padding:0 36px; font-family:Arial, sans-serif; font-size:8.5px; color:#666;">
      <div style="border-top:1px solid #e5e5e5; padding-top:6px;">
        <div style="display:flex; align-items:flex-end; justify-content:space-between; gap:12px;">
          <div style="width:90px;"></div>
          <div style="flex:1; text-align:center; line-height:1.25;">
            <div style="font-weight:700; color:#111;">Language Coach</div>
            <div>📧mentors.career.abroad26@gmail.com</div>
            <div>An initiative from : <a href="https://www.ahsansuny.com" style="color:#666; text-decoration:none; font-weight:700;">Career Abroad Mentor</a></div>
            <div>© {year} Ahsan Suny. All rights reserved</div>
          </div>
          <div style="width:90px; text-align:right; white-space:nowrap;">Page <span class=\"pageNumber\"></span>/<span class=\"totalPages\"></span></div>
        </div>
      </div>
    </div>
    """

    return header, footer


def _build_lesson_pdf_bytes_chromium(html: str, header_html: str, footer_html: str) -> bytes:
    """Render HTML to PDF using a headless Chromium engine (supports Bengali shaping)."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        raise RuntimeError(
            "Missing dependency: playwright. Run: pip install -r requirements.txt"
        ) from exc

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=['--no-sandbox'])
            page = browser.new_page()
            page.set_content(html, wait_until='load')
            page.wait_for_load_state('networkidle')
            pdf = page.pdf(
                format='A4',
                print_background=True,
                display_header_footer=True,
                header_template=header_html,
                footer_template=footer_html,
                margin={'top': '96px', 'bottom': '110px', 'left': '36px', 'right': '36px'},
            )
            browser.close()
            return pdf
    except Exception as exc:
        msg = str(exc) or ''
        if 'Executable doesn' in msg or 'browserType.launch' in msg or 'chromium' in msg.lower():
            raise RuntimeError("Playwright browser is not installed. Run: python -m playwright install chromium") from exc
        raise

_CEFR_ORDER = {'A1': 1, 'A2': 2, 'B1': 3, 'B2': 4, 'C1': 5, 'C2': 6}


def _lesson_cefr(lesson) -> str:
    return (lesson.get('cefr_level') or lesson.get('level') or '').strip().upper()


def _cefr_rank(level: str) -> int:
    return _CEFR_ORDER.get((level or '').strip().upper(), 99)


def _sorted_lessons(lesson_list):
    return sorted(lesson_list or [], key=lambda l: (_cefr_rank(_lesson_cefr(l)), l.get('id', 0)))


def _find_lesson(lesson_list, lesson_id):
    return next((l for l in lesson_list if l.get('id') == lesson_id), None)


def _build_placement_questions(lang: str, per_level: int = 10):
    """Build a CEFR placement test question set for a language.

    Uses existing lesson grammar/vocabulary (resources) plus a few curated questions.
    Output format matches the existing Practice engine (templates/practice.html + initPractice()).
    """
    lang = (lang or '').strip().lower()
    if lang not in LANG_META:
        return []

    levels = ['A1', 'A2', 'B1', 'B2']
    per_level = max(6, min(16, int(per_level or 10)))
    lessons_all = _sorted_lessons(get_lessons().get(lang, []) or [])
    tts_lang = 'fr-FR' if lang == 'french' else 'es-ES'

    # Curated extras (small set so the test isn't only "in-app" content).
    curated = {
        'french': {
            'A1': [
                {
                    'question_en': "Choose the correct French for: Good evening.",
                    'question_bn': "সঠিক ফরাসি বাছাই করুন: Good evening।",
                    'correct': 'Bonsoir',
                    'choices': ['Bonjour', 'Bonsoir', 'Bonne nuit', 'Salut'],
                },
                {
                    'question_en': "Which pronoun means we?",
                    'question_bn': "we কোন সর্বনাম?",
                    'correct': 'nous',
                    'choices': ['nous', 'vous', 'ils', 'tu'],
                },
            ],
            'A2': [
                {
                    'question_en': "Choose the correct form: Je ___ manger. (I'm going to eat)",
                    'question_bn': "সঠিক রূপ: Je ___ manger. (আমি খেতে যাচ্ছি)",
                    'correct': 'vais',
                    'choices': ['vais', 'vas', 'va', 'allez'],
                },
            ],
            'B1': [
                {
                    'question_en': "Complete: J'___ vais. (I'm going there)",
                    'question_bn': "পূর্ণ করুন: J'___ vais. (আমি সেখানে যাচ্ছি)",
                    'correct': 'y',
                    'choices': ['y', 'en', 'le', 'la'],
                },
            ],
            'B2': [
                {
                    'question_en': "Choose the correct mood: Il faut que tu ___ (venir).",
                    'question_bn': "সঠিক রূপ: Il faut que tu ___ (venir)।",
                    'correct': 'viennes',
                    'choices': ['viens', 'viendras', 'viennes', 'venir'],
                },
            ],
        },
        'spanish': {
            'A1': [
                {
                    'question_en': "Choose the correct Spanish for: I am from Bangladesh.",
                    'question_bn': "সঠিক স্প্যানিশ বাছাই করুন: I am from Bangladesh।",
                    'correct': 'Soy de Bangladesh.',
                    'choices': ['Estoy de Bangladesh.', 'Soy de Bangladesh.', 'Soy en Bangladesh.', 'Estoy en Bangladesh.'],
                },
            ],
            'A2': [
                {
                    'question_en': "Choose the correct form: Ayer yo ___ (comer).",
                    'question_bn': "সঠিক রূপ: Ayer yo ___ (comer)।",
                    'correct': 'comí',
                    'choices': ['como', 'comía', 'comí', 'comer'],
                },
            ],
            'B1': [
                {
                    'question_en': "Choose the best option: Cuando era niño, yo ___ en Dhaka.",
                    'question_bn': "সঠিকটি বাছাই করুন: Cuando era niño, yo ___ en Dhaka।",
                    'correct': 'vivía',
                    'choices': ['viví', 'vivía', 'he vivido', 'vivir'],
                },
            ],
            'B2': [
                {
                    'question_en': "Complete: Espero que tú ___ (venir).",
                    'question_bn': "পূর্ণ করুন: Espero que tú ___ (venir)।",
                    'correct': 'vengas',
                    'choices': ['vienes', 'vendrás', 'vengas', 'venir'],
                },
            ],
        },
    }

    def _strip_punct(s: str) -> str:
        return re.sub(r'[\\.,;:!?¿¡"“”()\\[\\]]+', '', (s or '')).strip()

    def _mk_mcq(level: str, mode_label: str, prompt_en: str, prompt_bn: str, choices, answer: str, tts_text: str = None):
        ch = [str(c) for c in (choices or []) if str(c).strip()]
        # Ensure answer is included.
        if answer and answer not in ch:
            ch = [answer] + ch
        # Limit to 4 choices for UI consistency.
        if len(ch) > 4:
            # Keep answer + 3 others
            others = [c for c in ch if c != answer]
            random.shuffle(others)
            ch = [answer] + others[:3]
        random.shuffle(ch)
        return {
            'kind': 'mcq',
            'mode': 'placement',
            'mode_label': mode_label,
            'prompt_en': prompt_en,
            'prompt_bn': prompt_bn,
            'choices': ch,
            'answer': answer,
            'tts_text': tts_text,
            'tts_lang': tts_lang,
            'cefr': level,
            # Keep XP tiny (hidden in UI for placement).
            'xp_correct': 1,
            'xp_wrong': 0,
        }

    def _mk_type(level: str, mode_label: str, prompt_en: str, prompt_bn: str, answer: str, hint_bn: str = ''):
        return {
            'kind': 'type',
            'mode': 'placement',
            'mode_label': mode_label,
            'prompt_en': prompt_en,
            'prompt_bn': prompt_bn,
            'answer': answer,
            'hint_bn': hint_bn or '',
            'tts_text': answer,
            'tts_lang': tts_lang,
            'cefr': level,
            'xp_correct': 1,
            'xp_wrong': 0,
        }

    def _mk_order(level: str, mode_label: str, prompt_en: str, prompt_bn: str, sentence: str, tokens):
        tokens = [t for t in (tokens or []) if str(t).strip()]
        return {
            'kind': 'order',
            'mode': 'placement',
            'mode_label': mode_label,
            'prompt_en': prompt_en,
            'prompt_bn': prompt_bn,
            'tokens': tokens,
            'answer': sentence,
            'tts_text': sentence,
            'tts_lang': tts_lang,
            'cefr': level,
            'xp_correct': 1,
            'xp_wrong': 0,
        }

    questions = []

    for lvl in levels:
        lvl_lessons = [l for l in lessons_all if _lesson_cefr(l) == lvl]

        grammar_pool = []
        vocab_pool = []
        example_pool = []
        for lesson in lvl_lessons:
            gr = lesson.get('grammar') or {}
            for gq in (gr.get('quiz_questions') or []):
                if not isinstance(gq, dict):
                    continue
                if not gq.get('question_en') or not gq.get('correct') or not gq.get('choices'):
                    continue
                grammar_pool.append(gq)

            for w in get_lesson_vocab(lang, lesson) or []:
                if not isinstance(w, dict):
                    continue
                if not w.get('word') or not w.get('english'):
                    continue
                vocab_pool.append(w)
                if w.get('example') and w.get('example_en'):
                    example_pool.append(w)

        # Mix: grammar + vocab + one sentence task (when available)
        lvl_q = []

        # 1) Curated questions (optional)
        extra = curated.get(lang, {}).get(lvl, []) or []
        random.shuffle(extra)
        for x in extra[:2]:
            lvl_q.append(_mk_mcq(
                lvl,
                f"Placement • {lvl} • Grammar",
                x.get('question_en', ''),
                x.get('question_bn', ''),
                x.get('choices', []),
                x.get('correct', ''),
            ))

        # 2) Grammar from lesson resources
        random.shuffle(grammar_pool)
        for gq in grammar_pool[: max(2, per_level // 3)]:
            lvl_q.append(_mk_mcq(
                lvl,
                f"Placement • {lvl} • Grammar",
                gq.get('question_en', ''),
                gq.get('question_bn', ''),
                gq.get('choices', []),
                gq.get('correct', ''),
            ))

        # 3) Sentence tasks (cloze or order)
        if example_pool:
            ex = random.choice(example_pool)
            sent = _strip_punct(ex.get('example') or '')
            if sent:
                tokens = sent.split()
                random.shuffle(tokens)
                lvl_q.append(_mk_order(
                    lvl,
                    f"Placement • {lvl} • Sentence",
                    ex.get('example_en') or 'Order the sentence',
                    ex.get('example_bn') or 'শব্দগুলো সাজান',
                    sent,
                    tokens,
                ))

        # 4) Vocab questions
        random.shuffle(vocab_pool)
        vocab_words = [w for w in vocab_pool if w.get('word') and w.get('english')]
        if vocab_words:
            # Build a wrong-pool for distractors
            wrong_pool = vocab_words[:]
            random.shuffle(vocab_words)
            used_words = set()
            for w in vocab_words:
                if len(lvl_q) >= per_level:
                    break
                word = (w.get('word') or '').strip()
                english = (w.get('english') or '').strip()
                bengali = (w.get('bengali') or '').strip()

                if not word or not english:
                    continue
                if word in used_words:
                    continue
                used_words.add(word)

                qtype = random.choice(['word_to_english', 'english_to_word', 'type_english_to_word', 'listen_to_word'])
                others = [x for x in wrong_pool if (x.get('word') or '').strip() != word]
                random.shuffle(others)

                if qtype == 'english_to_word':
                    choices = [word] + [(x.get('word') or '') for x in others[:3]]
                    lvl_q.append(_mk_mcq(
                        lvl,
                        f"Placement • {lvl} • Vocabulary",
                        f"How do you say “{english}” in {LANG_META[lang]['name_native'] or LANG_META[lang]['name']}?",
                        f"“{english}” {LANG_META[lang]['name_bn']} ভাষায় কীভাবে বলে?",
                        choices,
                        word,
                        tts_text=word,
                    ))
                elif qtype == 'type_english_to_word':
                    lvl_q.append(_mk_type(
                        lvl,
                        f"Placement • {lvl} • Type",
                        f"Type the {LANG_META[lang]['name']} word for: {english}",
                        f"{english} — লিখুন ({LANG_META[lang]['name_bn']} শব্দ)",
                        word,
                        hint_bn=bengali,
                    ))
                elif qtype == 'listen_to_word':
                    # Listen (TTS) then choose the spelling.
                    choices = [word] + [(x.get('word') or '') for x in others[:3]]
                    lvl_q.append(_mk_mcq(
                        lvl,
                        f"Placement • {lvl} • Listening",
                        "Listen and choose what you hear.",
                        "শুনুন এবং যা শুনেছেন তা বাছাই করুন।",
                        choices,
                        word,
                        tts_text=word,
                    ))
                else:
                    # word_to_english
                    choices = [english] + [(x.get('english') or '') for x in others[:3]]
                    lvl_q.append(_mk_mcq(
                        lvl,
                        f"Placement • {lvl} • Vocabulary",
                        f"What does “{word}” mean in English?",
                        f"“{word}” ইংরেজিতে কী?",
                        choices,
                        english,
                        tts_text=word,
                    ))

        # Ensure we have exactly per_level
        lvl_q = [q for q in lvl_q if q.get('answer') and (q.get('choices') if q.get('kind') == 'mcq' else True)]
        if len(lvl_q) > per_level:
            lvl_q = lvl_q[:per_level]
        while len(lvl_q) < per_level and grammar_pool:
            gq = grammar_pool.pop()
            lvl_q.append(_mk_mcq(
                lvl,
                f"Placement • {lvl} • Grammar",
                gq.get('question_en', ''),
                gq.get('question_bn', ''),
                gq.get('choices', []),
                gq.get('correct', ''),
            ))

        # Tag IDs and append in level order.
        for q in lvl_q:
            q['id'] = len(questions) + 1
            questions.append(q)

    return questions


def _next_incomplete_lesson(lesson_list, progress):
    for lesson in _sorted_lessons(lesson_list):
        p = (progress or {}).get(lesson['id'])
        if not p or not p.get('completed'):
            return lesson
    return None


def _last_seen_lesson_id(progress):
    best = None  # (last_seen_iso, lesson_id)
    for lid, p in (progress or {}).items():
        ls = p.get('last_seen')
        if not ls:
            continue
        if best is None or ls > best[0]:
            best = (ls, lid)
    return best[1] if best else None


def _recommended_lesson(lesson_list, progress):
    """Prefer last seen (if not completed), otherwise the next incomplete lesson."""
    lesson_list = _sorted_lessons(lesson_list)
    last_seen_id = _last_seen_lesson_id(progress)
    if last_seen_id is not None:
        p = (progress or {}).get(last_seen_id, {})
        if not p.get('completed'):
            last = _find_lesson(lesson_list, last_seen_id)
            if last:
                return last
    return _next_incomplete_lesson(lesson_list, progress)

LANG_META = {
    'french':  {'name': 'French',  'name_native': 'Français', 'name_bn': 'ফরাসি',    'flag': '🇫🇷', 'color': '#0055A4'},
    'spanish': {'name': 'Spanish', 'name_native': 'Español',  'name_bn': 'স্প্যানিশ', 'flag': '🇪🇸', 'color': '#c60b1e'},
}

LANGS = list(LANG_META.keys())

def _static_asset_version():
    """Cache-bust static assets (CSS/JS) by appending a version query parameter.

    Prefer `STATIC_VERSION` env var; otherwise derive from file mtimes.
    """
    env = (os.environ.get('STATIC_VERSION') or '').strip()
    if env:
        return env

    paths = [
        os.path.join(BASE_DIR, 'static', 'css', 'style.css'),
        os.path.join(BASE_DIR, 'static', 'js', 'app.js'),
        os.path.join(BASE_DIR, 'logo', 'AhsanSuny_Logo.png'),
    ]
    mtimes = []
    for p in paths:
        try:
            mtimes.append(int(os.path.getmtime(p)))
        except OSError:
            pass
    if mtimes:
        return str(max(mtimes))
    return str(int(datetime.now().timestamp()))


@app.context_processor
def inject_globals():
    ui_theme = 'lime'
    uid = current_user_id()
    auth_user = get_user_by_id(uid) if uid is not None else None
    return {
        'lang_meta': LANG_META,
        'tts_provider': app.config.get('TTS_PROVIDER', 'auto'),
        'ui_theme': ui_theme,
        'auth_user': auth_user,
        'current_year': datetime.now().year,
        'static_version': _static_asset_version(),
    }

# ---------- Routes ----------
@app.route('/')
def dashboard():
    uid = current_user_id()
    lessons_all = get_lessons()
    vocab_all = get_vocab()
    resource_all = get_resource_sentences()
    activity = get_activity_summary(user_id=uid)

    cefr_counts = Counter()
    canon = lessons_all.get('french', []) or next(iter(lessons_all.values()), [])
    for l in canon or []:
        lvl = (l.get('cefr_level') or l.get('level') or '').strip() or 'A1'
        cefr_counts[lvl] += 1

    stats = {}
    for lang in LANGS:
        prog = load_progress(lang, user_id=uid)
        lesson_list = lessons_all.get(lang, [])
        total = len(lesson_list)
        completed = sum(1 for v in prog.values() if v.get('completed'))
        rec = _recommended_lesson(lesson_list, prog)
        vocab_by_cat = vocab_all.get(lang, {}) or {}
        resources = resource_all.get(lang, []) or []
        resource_info = _compute_resource_insights(lang, resources, vocab_by_cat, lesson_list, prog)
        stats[lang] = {'total': total, 'completed': completed,
                       'percent': int(completed / total * 100) if total else 0,
                       'next_lesson': rec,
                       'continue_url': url_for('lesson_view', lang=lang, lesson_id=rec['id']) if rec else url_for('language_home', lang=lang),
                       'resource': resource_info}
    return render_template('dashboard.html', stats=stats, activity=activity, cefr_counts=dict(cefr_counts))

@app.route('/resources')
def resources_view():
    return render_template('resources.html')

def _safe_next_url(next_url: str) -> str:
    if not next_url:
        return url_for('dashboard')
    next_url = str(next_url)
    return next_url if next_url.startswith('/') else url_for('dashboard')


def _request_path_with_query() -> str:
    """Return the current request path including query string (for login redirects)."""
    try:
        qs = (request.query_string or b'').decode('utf-8', 'ignore')
    except Exception:
        qs = ''
    return request.path + (('?' + qs) if qs else '')


def login_required(view_func):
    @wraps(view_func)
    def _wrapped(*args, **kwargs):
        if current_user_id() is None:
            return redirect(url_for('login', next=_request_path_with_query()))
        return view_func(*args, **kwargs)
    return _wrapped


@app.route('/login', methods=['GET', 'POST'])
def login():
    next_url = request.args.get('next') or request.form.get('next') or url_for('dashboard')
    name = (request.form.get('name') or '').strip() if request.method == 'POST' else ''
    email = _normalize_email(request.form.get('email')) if request.method == 'POST' else ''
    error = None

    if request.method == 'POST':
        if not _is_valid_email(email):
            error = 'Please enter a valid email address.'
        else:
            user_id = upsert_user(name, email)
            session['user_id'] = user_id
            user = get_user_by_id(user_id)
            _emit_event_to_sheets('login', user=user, page=_safe_next_url(next_url))
            _emit_user_snapshot_to_sheets(user, last_event='login', page=_safe_next_url(next_url))
            return redirect(_safe_next_url(next_url))

    return render_template('login.html', error=error, next=_safe_next_url(next_url), name=name, email=email)


@app.route('/logout')
def logout():
    try:
        session.pop('user_id', None)
    except Exception:
        pass
    return redirect(url_for('dashboard'))


def _logo_file_path():
    return os.path.join(BASE_DIR, 'logo', 'AhsanSuny_Logo.png')


@app.route('/logo.png')
def logo_png():
    path = _logo_file_path()
    if not os.path.exists(path):
        return ('Missing logo', 404)
    resp = send_file(path, mimetype='image/png', conditional=True)
    resp.headers['Cache-Control'] = 'public, max-age=86400'
    return resp


@app.route('/favicon.png')
def favicon_png():
    return logo_png()


@app.route('/favicon.ico')
def favicon_ico():
    return logo_png()


@app.route('/language/<lang>')
def language_home(lang):
    if lang not in LANG_META:
        return redirect(url_for('dashboard'))
    lessons = get_lessons().get(lang, [])
    progress = load_progress(lang, user_id=current_user_id())
    resume = _recommended_lesson(lessons, progress)
    return render_template('language.html', lang=lang, meta=LANG_META[lang],
                           lessons=lessons, progress=progress, resume_lesson=resume)


@app.route('/placement/<lang>')
@login_required
def placement_test(lang):
    if lang not in LANG_META:
        return redirect(url_for('dashboard'))

    try:
        per_level = int((request.args.get('per') or request.args.get('n') or 10))
    except (TypeError, ValueError):
        per_level = 10

    questions = _build_placement_questions(lang, per_level=per_level)
    if not questions:
        return redirect(url_for('language_home', lang=lang))

    lesson_list = _sorted_lessons(get_lessons().get(lang, []) or [])
    start_urls = {}
    for lvl in ['A1', 'A2', 'B1', 'B2']:
        l = next((x for x in lesson_list if _lesson_cefr(x) == lvl), None)
        if l:
            start_urls[lvl] = url_for('lesson_view', lang=lang, lesson_id=int(l.get('id') or 0))
        else:
            start_urls[lvl] = url_for('language_home', lang=lang)

    return render_template(
        'placement.html',
        lang=lang,
        meta=LANG_META[lang],
        questions=questions,
        questions_json=json.dumps(questions, ensure_ascii=False),
        start_urls_json=json.dumps(start_urls, ensure_ascii=False),
    )


@app.route('/lesson/<lang>/<int:lesson_id>')
@login_required
def lesson_view(lang, lesson_id):
    if lang not in LANG_META:
        return redirect(url_for('dashboard'))
    lesson_list = _sorted_lessons(get_lessons().get(lang, []))
    lesson = _find_lesson(lesson_list, lesson_id)
    if not lesson:
        return redirect(url_for('language_home', lang=lang))

    touch_lesson(lang, lesson_id, user_id=current_user_id())
    vocab   = get_lesson_vocab(lang, lesson)
    grammar = lesson.get('grammar')
    tts_lang = 'fr-FR' if lang == 'french' else 'es-ES'
    speak_match = []
    for w in (vocab or []):
        word = (w.get('word') or '').strip()
        if not word:
            continue
        article = (w.get('article') or '').strip()
        full_word = (article + (' ' if article and not article.endswith("'") else '') + word).strip() or word
        speak_match.append({
            'word': word,
            'full_word': full_word,
            'english': (w.get('english') or '').strip(),
            'bengali': (w.get('bengali') or '').strip(),
            'pronunciation': (w.get('pronunciation') or '').strip(),
            'example': (w.get('example') or '').strip(),
            'example_en': (w.get('example_en') or '').strip(),
            'example_bn': (w.get('example_bn') or '').strip(),
            'tts_text': full_word,
            'tts_lang': tts_lang,
        })
    # next lesson for navigation
    idx      = next((i for i, l in enumerate(lesson_list) if l.get('id') == lesson_id), None)
    next_l   = lesson_list[idx + 1] if idx is not None and idx + 1 < len(lesson_list) else None
    prev_l   = lesson_list[idx - 1] if idx is not None and idx > 0 else None

    return render_template('lesson.html', lang=lang, meta=LANG_META[lang],
                           lesson=lesson, vocabulary=vocab, grammar=grammar,
                           next_lesson=next_l, prev_lesson=prev_l,
                           speak_match_json=json.dumps(speak_match, ensure_ascii=False))


@app.route('/lesson/<lang>/<int:lesson_id>/download.pdf')
@login_required
def lesson_download_pdf(lang, lesson_id):
    if lang not in LANG_META:
        return redirect(url_for('dashboard'))

    lesson_list = _sorted_lessons(get_lessons().get(lang, []))
    lesson = _find_lesson(lesson_list, lesson_id)
    if not lesson:
        return redirect(url_for('language_home', lang=lang))

    vocab = get_lesson_vocab(lang, lesson)
    grammar = lesson.get('grammar')

    try:
        engine = (request.args.get('engine') or (os.environ.get('PDF_ENGINE') or 'chromium')).strip().lower()
        if engine == 'reportlab':
            pdf_bytes = _build_lesson_pdf_bytes_reportlab(lang, LANG_META[lang], lesson, vocab, grammar)
        else:
            html = _render_lesson_pdf_html(lang, LANG_META[lang], lesson, vocab, grammar)
            header_html, footer_html = _lesson_pdf_header_footer(lang, LANG_META[lang], lesson)
            pdf_bytes = _build_lesson_pdf_bytes_chromium(html, header_html, footer_html)
    except Exception as exc:
        msg = str(exc) or "Failed to generate PDF."
        return (msg, 500, {'Content-Type': 'text/plain; charset=utf-8'})

    safe_lang = re.sub(r'[^a-z0-9]+', '-', (lang or '').lower()).strip('-') or 'lesson'
    try:
        safe_id = int(lesson.get('id') or lesson_id)
    except (TypeError, ValueError):
        safe_id = lesson_id
    title_en = (lesson.get('title_en') or '').strip()
    title_slug = re.sub(r'[^a-z0-9]+', '-', _strip_accents(title_en.lower())).strip('-')[:60]
    filename = f"{safe_lang}-lesson-{safe_id}{('-' + title_slug) if title_slug else ''}.pdf"

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename,
        max_age=0,
    )

@app.route('/flashcards/<lang>/<int:lesson_id>')
@login_required
def flashcards(lang, lesson_id):
    if lang not in LANG_META:
        return redirect(url_for('dashboard'))
    lesson_list = get_lessons().get(lang, [])
    lesson = _find_lesson(lesson_list, lesson_id)
    if not lesson:
        return redirect(url_for('language_home', lang=lang))
    touch_lesson(lang, lesson_id, user_id=current_user_id())
    vocab = get_lesson_vocab(lang, lesson)
    return render_template('flashcard.html', lang=lang, meta=LANG_META[lang],
                           lesson=lesson, vocabulary=vocab,
                           vocab_json=json.dumps(vocab, ensure_ascii=False),
                           back_url=url_for('lesson_view', lang=lang, lesson_id=lesson_id),
                           show_quiz_link=True)

@app.route('/vocabulary/<lang>')
def vocabulary_view(lang):
    if lang not in LANG_META:
        return redirect(url_for('dashboard'))

    vocab_data = get_vocab().get(lang, {})
    categories = []
    flat = []
    for cat, words in vocab_data.items():
        categories.append({'id': cat, 'label': cat.replace('_', ' ').title(), 'count': len(words)})
        for w in words:
            flat.append({**w, 'category': cat})

    categories = sorted(categories, key=lambda c: (-c['count'], c['id']))
    selected_cat = request.args.get('cat') or 'all'
    if selected_cat != 'all' and selected_cat not in vocab_data:
        selected_cat = 'all'

    return render_template(
        'vocabulary.html',
        lang=lang,
        meta=LANG_META[lang],
        categories=categories,
        selected_cat=selected_cat,
        vocab_json=json.dumps(flat, ensure_ascii=False),
    )


@app.route('/flashcards/category/<lang>/<category>')
def flashcards_category(lang, category):
    if lang not in LANG_META:
        return redirect(url_for('dashboard'))

    vocab_data = get_vocab().get(lang, {})
    vocab_full = vocab_data.get(category, [])
    if not vocab_full:
        return redirect(url_for('vocabulary_view', lang=lang))

    try:
        limit = max(10, min(200, int(request.args.get('n', 60))))
    except (TypeError, ValueError):
        limit = 60
    try:
        offset = max(0, int(request.args.get('offset', 0)))
    except (TypeError, ValueError):
        offset = 0

    vocab = vocab_full[offset: offset + limit]
    if not vocab:
        return redirect(url_for('flashcards_category', lang=lang, category=category, n=limit, offset=0))

    title = category.replace('_', ' ').title()
    pseudo_lesson = {'id': 0, 'title_en': f"Category: {title}", 'title_bn': '', 'title_lang': ''}
    total = len(vocab_full)
    start = offset + 1
    end = min(offset + limit, total)
    subtitle = f"Showing {start}–{end} of {total} words"
    return render_template('flashcard.html', lang=lang, meta=LANG_META[lang],
                           lesson=pseudo_lesson, vocabulary=vocab,
                           vocab_json=json.dumps(vocab, ensure_ascii=False),
                           back_url=url_for('vocabulary_view', lang=lang, cat=category),
                           show_quiz_link=False,
                           header_subtitle=subtitle)


@app.route('/review/<lang>')
def review_flashcards(lang):
    if lang not in LANG_META:
        return redirect(url_for('dashboard'))

    mode = (request.args.get('mode') or 'due').lower()
    try:
        limit = max(5, min(80, int(request.args.get('n', 40))))
    except (TypeError, ValueError):
        limit = 40

    uid = current_user_id()
    vocab_by_cat = get_vocab().get(lang, {})
    vocab_lookup = {}
    for cat, words in vocab_by_cat.items():
        for w in words:
            key = w.get('word')
            if not key:
                continue
            entry = {**w, 'category': cat}
            if key not in vocab_lookup:
                vocab_lookup[key] = entry
                continue
            existing = vocab_lookup[key]
            if (not existing.get('pronunciation') and entry.get('pronunciation')) or (not existing.get('example') and entry.get('example')):
                vocab_lookup[key] = entry

    review_words = []
    if mode == 'due':
        now_iso = datetime.now().isoformat(timespec='seconds')
        conn = get_db()
        if uid is None:
            rows = conn.execute('''
                SELECT word
                FROM word_progress
                WHERE language=?
                  AND (next_due IS NULL OR next_due <= ?)
                ORDER BY COALESCE(next_due, '') ASC, box ASC, incorrect DESC
                LIMIT ?
            ''', (lang, now_iso, limit)).fetchall()
        else:
            rows = conn.execute('''
                SELECT word
                FROM user_word_progress
                WHERE user_id=?
                  AND language=?
                  AND (next_due IS NULL OR next_due <= ?)
                ORDER BY COALESCE(next_due, '') ASC, box ASC, incorrect DESC
                LIMIT ?
            ''', (uid, lang, now_iso, limit)).fetchall()
        conn.close()

        for r in rows:
            entry = vocab_lookup.get(r['word'])
            if entry:
                review_words.append(entry)

    if mode == 'weak' and not review_words:
        conn = get_db()
        if uid is None:
            rows = conn.execute(
                'SELECT word, correct, incorrect FROM word_progress WHERE language=?', (lang,)
            ).fetchall()
        else:
            rows = conn.execute(
                'SELECT word, correct, incorrect FROM user_word_progress WHERE user_id=? AND language=?', (uid, lang)
            ).fetchall()
        conn.close()

        scored = []
        for r in rows:
            word = r['word']
            correct = int(r['correct'] or 0)
            incorrect = int(r['incorrect'] or 0)
            attempts = correct + incorrect
            if attempts <= 1:
                continue
            score = (incorrect * 2) - correct
            if score <= 0:
                continue
            scored.append((score, incorrect, attempts, word))

        scored.sort(reverse=True)
        for _, __, ___, word in scored[:limit]:
            entry = vocab_lookup.get(word)
            if entry:
                review_words.append(entry)

    if not review_words:
        # Fallback: random sample (good for new users without history)
        all_entries = list(vocab_lookup.values())
        random.shuffle(all_entries)
        review_words = all_entries[:min(limit, len(all_entries))]

    pseudo_lesson = {'id': 0, 'title_en': 'Review Flashcards', 'title_bn': 'ভুল শব্দ রিভিউ', 'title_lang': ''}
    subtitle = (
        'Due words (spaced repetition)'
        if mode == 'due'
        else 'Weak words based on your mistakes'
        if mode == 'weak'
        else 'Random vocabulary review'
    )
    return render_template('flashcard.html', lang=lang, meta=LANG_META[lang],
                           lesson=pseudo_lesson, vocabulary=review_words,
                           vocab_json=json.dumps(review_words, ensure_ascii=False),
                           back_url=url_for('language_home', lang=lang),
                           show_quiz_link=False,
                           header_subtitle=subtitle)

@app.route('/practice/<lang>')
def practice(lang):
    if lang not in LANG_META:
        return redirect(url_for('dashboard'))

    try:
        total_q = max(5, min(25, int(request.args.get('n', 12))))
    except (TypeError, ValueError):
        total_q = 12

    mode = (request.args.get('mode') or '').strip().lower()

    vocab_by_cat = get_vocab().get(lang, {})
    vocab_all = [w for words in vocab_by_cat.values() for w in words if w.get('word') and w.get('english')]
    if not vocab_all:
        return redirect(url_for('language_home', lang=lang))

    lesson_list = get_lessons().get(lang, [])
    progress = load_progress(lang, user_id=current_user_id())
    lesson_list_sorted = _sorted_lessons(lesson_list)
    rec = _recommended_lesson(lesson_list_sorted, progress)
    current_rank = _cefr_rank(_lesson_cefr(rec)) if rec else 99

    unlocked = []
    unlocked_words = set()
    for lesson in lesson_list_sorted:
        if _cefr_rank(_lesson_cefr(lesson)) > current_rank:
            continue
        for w in get_lesson_vocab(lang, lesson):
            ww = (w.get('word') or '').strip()
            if not ww or ww in unlocked_words:
                continue
            unlocked_words.add(ww)
            unlocked.append(w)

    tts_lang = 'fr-FR' if lang == 'french' else 'es-ES'
    resource_sentences = get_resource_sentences().get(lang, []) or []

    if mode in {'resources', 'resource'}:
        if not resource_sentences:
            return redirect(url_for('practice', lang=lang))
        questions = _build_resource_drill_questions(
            lang, total_q, vocab_by_cat, vocab_all, resource_sentences, tts_lang, user_id=current_user_id()
        )
        if questions:
            return render_template('practice.html',
                                   lang=lang, meta=LANG_META[lang],
                                   questions=questions,
                                   questions_json=json.dumps(questions, ensure_ascii=False))
        return redirect(url_for('practice', lang=lang))

    # Prefer due words (spaced repetition); otherwise pick random vocabulary.
    uid = current_user_id()
    now_iso = datetime.now().isoformat(timespec='seconds')
    conn = get_db()
    if uid is None:
        due_rows = conn.execute('''
            SELECT word
            FROM word_progress
            WHERE language=?
              AND (next_due IS NULL OR next_due <= ?)
            ORDER BY COALESCE(next_due, '') ASC, box ASC, incorrect DESC
            LIMIT ?
        ''', (lang, now_iso, total_q)).fetchall()
    else:
        due_rows = conn.execute('''
            SELECT word
            FROM user_word_progress
            WHERE user_id=?
              AND language=?
              AND (next_due IS NULL OR next_due <= ?)
            ORDER BY COALESCE(next_due, '') ASC, box ASC, incorrect DESC
            LIMIT ?
        ''', (uid, lang, now_iso, total_q)).fetchall()
    conn.close()

    vocab_lookup = {w['word']: w for w in vocab_all}
    selected = []
    for r in due_rows:
        entry = vocab_lookup.get(r['word'])
        if entry and (not unlocked_words or entry['word'] in unlocked_words):
            selected.append(entry)

    if len(selected) < total_q:
        base_pool = unlocked or vocab_all
        pool = [w for w in base_pool if w.get('word') and w['word'] not in {e['word'] for e in selected}]
        random.shuffle(pool)
        selected.extend(pool[: max(0, total_q - len(selected))])

    # Build interactive exercises (Duolingo-like mix: listen, choice, type)
    all_for_wrong = (unlocked[:] if len(unlocked) >= 40 else vocab_all[:])
    random.shuffle(all_for_wrong)

    questions = []
    for idx, entry in enumerate(selected[:total_q]):
        word = entry['word']
        english = entry.get('english', '')
        bengali = entry.get('bengali', '')

        qtype_choices = ['listen_to_english', 'word_to_english', 'english_to_word', 'type_english_to_word']
        example = (entry.get('example') or '').strip()
        example_en = (entry.get('example_en') or '').strip()
        example_bn = (entry.get('example_bn') or '').strip()
        if example and example_en:
            tokens = re.sub(r'[\\.,;:!?]', '', example).split()
            if 3 <= len(tokens) <= 10:
                qtype_choices.append('order_sentence')

        ctx = None
        if resource_sentences and ' ' not in word and len(word) >= 2:
            variants = _word_match_variants(word)
            if variants:
                sample_n = min(80, len(resource_sentences))
                candidates = random.sample(resource_sentences, sample_n) if sample_n else []
                for s in candidates:
                    sent = (s.get('text') or '').strip()
                    if not sent:
                        continue
                    sent_norm = _norm_match(sent)
                    if any(f' {v} ' in f' {sent_norm} ' for v in variants):
                        blanked = _blank_first_token(sent, word)
                        if blanked:
                            ctx = {**s, 'blanked': blanked}
                            break

                if not ctx:
                    for s in resource_sentences:
                        sent = (s.get('text') or '').strip()
                        if not sent:
                            continue
                        sent_norm = _norm_match(sent)
                        if any(f' {v} ' in f' {sent_norm} ' for v in variants):
                            blanked = _blank_first_token(sent, word)
                            if blanked:
                                ctx = {**s, 'blanked': blanked}
                                break

        if ctx:
            qtype_choices.extend(['context_cloze', 'context_cloze'])

        qtype = random.choice(qtype_choices)

        others = [w for w in all_for_wrong if w.get('word') != word]
        wrong = random.sample(others, min(3, len(others)))

        if qtype == 'listen_to_english':
            q = {
                'kind': 'mcq',
                'mode': 'listen_to_english',
                'mode_label': '🔊 Listening',
                'prompt_en': 'Listen and choose the correct meaning (English)',
                'prompt_bn': 'শুনে সঠিক অর্থ নির্বাচন করুন (ইংরেজি)',
                'tts_text': word,
                'tts_lang': tts_lang,
                'choices': [english] + [w.get('english', '') for w in wrong],
                'answer': english,
                'word': word,
                'xp_correct': 10,
                'xp_wrong': 2,
            }
        elif qtype == 'context_cloze' and ctx:
            hint = f"Hint: {english}"
            if bengali:
                hint += f" \u2022 বাংলা: {bengali}"

            q = {
                'kind': 'mcq',
                'mode': 'context_cloze',
                'mode_label': 'Context',
                'prompt_en': f"Fill in the blank: {ctx.get('blanked', '')}",
                'prompt_bn': hint,
                'tts_text': (ctx.get('text') or word),
                'tts_lang': tts_lang,
                'choices': [word] + [w.get('word', '') for w in wrong],
                'answer': word,
                'word': word,
                'xp_correct': 14,
                'xp_wrong': 3,
            }
        elif qtype == 'order_sentence':
            tokens = re.sub(r'[\\.,;:!?]', '', example).split()
            random.shuffle(tokens)
            q = {
                'kind': 'order',
                'mode': 'order_sentence',
                'mode_label': '🧩 Order the sentence',
                'prompt_en': example_en,
                'prompt_bn': example_bn or 'শব্দগুলো সাজান',
                'tokens': tokens,
                'answer': ' '.join(re.sub(r'[\\.,;:!?]', '', example).split()),
                'word': word,
                'tts_text': example,
                'tts_lang': tts_lang,
                'xp_correct': 12,
                'xp_wrong': 3,
            }
        elif qtype == 'english_to_word':
            q = {
                'kind': 'mcq',
                'mode': 'english_to_word',
                'mode_label': '✅ Choose',
                'prompt_en': f"How do you say “{english}” in {LANG_META[lang]['name_native'] or LANG_META[lang]['name']}?",
                'prompt_bn': f"“{english}” {LANG_META[lang]['name_bn']} ভাষায় কীভাবে বলে?",
                'choices': [word] + [w.get('word', '') for w in wrong],
                'answer': word,
                'word': word,
                'xp_correct': 10,
                'xp_wrong': 2,
            }
        elif qtype == 'type_english_to_word':
            q = {
                'kind': 'type',
                'mode': 'type_english_to_word',
                'mode_label': '⌨️ Type',
                'prompt_en': f"Type the {LANG_META[lang]['name']} word for: {english}",
                'prompt_bn': f"{english} — লিখুন ({LANG_META[lang]['name_bn']} শব্দ)",
                'hint_bn': bengali,
                'answer': word,
                'word': word,
                'tts_text': word,
                'tts_lang': tts_lang,
                'xp_correct': 12,
                'xp_wrong': 3,
            }
        else:
            q = {
                'kind': 'mcq',
                'mode': 'word_to_english',
                'mode_label': '✅ Choose',
                'prompt_en': f"What does “{word}” mean in English?",
                'prompt_bn': f"“{word}” ইংরেজিতে কী?",
                'choices': [english] + [w.get('english', '') for w in wrong],
                'answer': english,
                'word': word,
                'tts_text': word,
                'tts_lang': tts_lang,
                'xp_correct': 10,
                'xp_wrong': 2,
            }

        q['id'] = idx + 1
        random.shuffle(q.get('choices', []))
        questions.append(q)

    random.shuffle(questions)

    return render_template('practice.html',
                           lang=lang, meta=LANG_META[lang],
                           questions=questions,
                           questions_json=json.dumps(questions, ensure_ascii=False))

@app.route('/dictation/<lang>/<int:lesson_id>')
@login_required
def dictation(lang, lesson_id):
    if lang not in LANG_META:
        return redirect(url_for('dashboard'))
    lesson_list = _sorted_lessons(get_lessons().get(lang, []))
    lesson = _find_lesson(lesson_list, lesson_id)
    if not lesson:
        return redirect(url_for('language_home', lang=lang))
    touch_lesson(lang, lesson_id, user_id=current_user_id())
    vocab = get_lesson_vocab(lang, lesson)
    if not vocab:
        return redirect(url_for('lesson_view', lang=lang, lesson_id=lesson_id))

    tts_lang = 'fr-FR' if lang == 'french' else 'es-ES'
    items = []
    for w in vocab:
        if w.get('word'):
            items.append({
                'word': w['word'],
                'english': w.get('english', ''),
                'bengali': w.get('bengali', ''),
                'pronunciation': w.get('pronunciation', ''),
                'tts_text': w['word'],
                'tts_lang': tts_lang,
            })
    random.shuffle(items)

    return render_template('dictation.html',
                           lang=lang, meta=LANG_META[lang],
                           lesson=lesson,
                           items=items,
                           items_json=json.dumps(items, ensure_ascii=False))


@app.route('/speaking/<lang>/<int:lesson_id>')
@login_required
def speaking(lang, lesson_id):
    if lang not in LANG_META:
        return redirect(url_for('dashboard'))
    lesson_list = _sorted_lessons(get_lessons().get(lang, []))
    lesson = _find_lesson(lesson_list, lesson_id)
    if not lesson:
        return redirect(url_for('language_home', lang=lang))
    touch_lesson(lang, lesson_id, user_id=current_user_id())

    vocab = get_lesson_vocab(lang, lesson)
    if not vocab:
        return redirect(url_for('lesson_view', lang=lang, lesson_id=lesson_id))

    tts_lang = 'fr-FR' if lang == 'french' else 'es-ES'
    items = []
    for w in vocab:
        word = (w.get('word') or '').strip()
        if not word:
            continue
        article = (w.get('article') or '').strip()
        full_word = (article + (' ' if article and not article.endswith("'") else '') + word).strip() or word
        items.append({
            'word': word,
            'full_word': full_word,
            'english': (w.get('english') or '').strip(),
            'bengali': (w.get('bengali') or '').strip(),
            'pronunciation': (w.get('pronunciation') or '').strip(),
            'example': (w.get('example') or '').strip(),
            'example_en': (w.get('example_en') or '').strip(),
            'example_bn': (w.get('example_bn') or '').strip(),
            'tts_text': full_word,
            'tts_lang': tts_lang,
        })

    random.shuffle(items)
    items = items[:min(20, len(items))]

    return render_template('speaking.html',
                           lang=lang, meta=LANG_META[lang],
                           lesson=lesson,
                           items=items,
                           items_json=json.dumps(items, ensure_ascii=False))


@app.route('/quiz/<lang>/<int:lesson_id>')
@login_required
def quiz(lang, lesson_id):
    if lang not in LANG_META:
        return redirect(url_for('dashboard'))
    lesson_list = _sorted_lessons(get_lessons().get(lang, []))
    lesson = _find_lesson(lesson_list, lesson_id)
    if not lesson:
        return redirect(url_for('language_home', lang=lang))
    touch_lesson(lang, lesson_id, user_id=current_user_id())

    vocab = get_lesson_vocab(lang, lesson)
    grammar = lesson.get('grammar')
    questions = []
    tts_lang = 'fr-FR' if lang == 'french' else 'es-ES'

    # --- vocabulary questions ---
    if len(vocab) >= 4:
        q_count = min(10, len(vocab))
        sampled = random.sample(vocab, q_count)
        all_vocab = vocab[:]
        for word in sampled:
            qtype = random.choice(['word_to_english', 'english_to_word', 'word_to_bengali'])
            others = [w for w in all_vocab if w['word'] != word['word']]
            wrong  = random.sample(others, min(3, len(others)))

            if qtype == 'word_to_english':
                q = {
                    'kind': 'vocab',
                    'mode': 'word_to_english',
                    'word': word['word'],
                    'tts_text': word['word'],
                    'tts_lang': tts_lang,
                    'question_en': f"What does <strong>{word['word']}</strong> mean in English?",
                    'question_bn': f"<strong>{word['word']}</strong> ইংরেজিতে কী?",
                    'correct': word['english'],
                    'choices': [word['english']] + [w['english'] for w in wrong],
                }
            elif qtype == 'english_to_word':
                lang_name_bn = LANG_META[lang]['name_bn']
                q = {
                    'kind': 'vocab',
                    'mode': 'english_to_word',
                    'word': word['word'],
                    'tts_text': word['word'],
                    'tts_lang': tts_lang,
                    'question_en': f"How do you say <strong>{word['english']}</strong> in {LANG_META[lang]['name']}?",
                    'question_bn': f"<strong>{word['english']}</strong> {lang_name_bn} ভাষায় কীভাবে বলে?",
                    'correct': word['word'],
                    'choices': [word['word']] + [w['word'] for w in wrong],
                }
            else:
                q = {
                    'kind': 'vocab',
                    'mode': 'word_to_bengali',
                    'word': word['word'],
                    'tts_text': word['word'],
                    'tts_lang': tts_lang,
                    'question_en': f"What does <strong>{word['word']}</strong> mean in Bengali?",
                    'question_bn': f"<strong>{word['word']}</strong> বাংলায় কী?",
                    'correct': word['bengali'],
                    'choices': [word['bengali']] + [w['bengali'] for w in wrong],
                }
            random.shuffle(q['choices'])
            questions.append(q)

    # --- grammar questions (embedded in lesson) ---
    if grammar and grammar.get('quiz_questions'):
        gq = [{**q, 'kind': 'grammar'} for q in grammar['quiz_questions'][:]]
        random.shuffle(gq)
        questions.extend(gq[:5])

    random.shuffle(questions)

    idx = next((i for i, l in enumerate(lesson_list) if l.get('id') == lesson_id), None)
    next_lesson = lesson_list[idx + 1] if idx is not None and idx + 1 < len(lesson_list) else None

    return render_template('quiz.html', lang=lang, meta=LANG_META[lang],
                           lesson=lesson, questions=questions,
                           questions_json=json.dumps(questions, ensure_ascii=False),
                           next_lesson=next_lesson)

@app.route('/progress')
def progress_view():
    uid = current_user_id()
    lessons_all = get_lessons()
    all_prog = {}
    for lang in LANGS:
        prog = load_progress(lang, user_id=uid)
        lesson_list = _sorted_lessons(lessons_all.get(lang, []))
        enriched = []
        for l in lesson_list:
            p = prog.get(l['id'], {'completed': 0, 'best_score': 0, 'attempts': 0})
            enriched.append({**l, **p})
        all_prog[lang] = enriched

    # Last 30 days of XP history for chart
    conn = get_db()
    if uid is None:
        xp_rows = conn.execute(
            'SELECT date, xp FROM daily_activity WHERE xp > 0 ORDER BY date DESC LIMIT 30'
        ).fetchall()
    else:
        xp_rows = conn.execute(
            'SELECT date, xp FROM user_daily_activity WHERE user_id=? AND xp > 0 ORDER BY date DESC LIMIT 30',
            (uid,)
        ).fetchall()
    conn.close()
    xp_history = [{'date': r['date'], 'xp': r['xp']} for r in reversed(xp_rows)]

    return render_template('progress.html', progress=all_prog, xp_history=xp_history)

# ---------- API ----------
@app.route('/api/tts')
def api_tts():
    provider = (app.config.get('TTS_PROVIDER') or 'auto').strip().lower()
    if provider not in {'gtts', 'auto'}:
        return ('TTS disabled (set TTS_PROVIDER=gtts or auto on the server)', 501)

    text = (request.args.get('text') or '').strip()
    lang_tag = (request.args.get('lang') or '').strip().lower().replace('_', '-')

    if not text:
        return ('Missing "text"', 400)
    if len(text) > 400:
        return ('Text too long (max 400 chars)', 400)

    if lang_tag.startswith('fr'):
        tts_lang = 'fr'
    elif lang_tag.startswith('es'):
        tts_lang = 'es'
    elif lang_tag.startswith('en'):
        tts_lang = 'en'
    elif lang_tag.startswith('bn'):
        tts_lang = 'bn'
    else:
        return ('Unsupported language (use en-US, fr-FR, es-ES, bn-BD)', 400)

    # Normalize whitespace to improve cache hit rate and avoid odd linebreak reads.
    norm_text = ' '.join(text.split())
    # Both `gtts` and `auto` generate audio via gTTS; use a stable cache prefix so the same
    # text+language hits the same cached MP3 regardless of the configured provider.
    cache_provider = 'gtts'
    cache_key = hashlib.sha256(f'{cache_provider}|{tts_lang}|{norm_text}'.encode('utf-8')).hexdigest()

    cache_dir = app.config.get('TTS_CACHE_DIR') or TTS_CACHE_DIR
    os.makedirs(cache_dir, exist_ok=True)
    final_path = os.path.join(cache_dir, f'{cache_key}.mp3')

    if not os.path.exists(final_path):
        try:
            from gtts import gTTS
        except Exception as exc:  # pragma: no cover
            return (f'TTS server dependency missing: {exc}', 500)

        # gTTS can vary slightly by top-level domain (accent/voice). Allow override per language.
        tld_default = (os.environ.get('GTTS_TLD') or 'com').strip() or 'com'
        tld = tld_default
        if tts_lang == 'es':
            tld = (os.environ.get('GTTS_TLD_ES') or tld_default).strip() or tld_default
        elif tts_lang == 'fr':
            tld = (os.environ.get('GTTS_TLD_FR') or tld_default).strip() or tld_default
        elif tts_lang == 'bn':
            tld = (os.environ.get('GTTS_TLD_BN') or tld_default).strip() or tld_default
        elif tts_lang == 'en':
            tld = (os.environ.get('GTTS_TLD_EN') or tld_default).strip() or tld_default

        tmp_path = os.path.join(cache_dir, f'.{cache_key}.{uuid.uuid4().hex}.tmp.mp3')
        try:
            gTTS(text=norm_text, lang=tts_lang, slow=False, tld=tld).save(tmp_path)
            os.replace(tmp_path, final_path)
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass

    resp = send_file(final_path, mimetype='audio/mpeg', conditional=True)
    resp.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    return resp

@app.route('/api/translate', methods=['POST'])
def api_translate():
    data = request.json or {}
    text = (data.get('text') or '').strip()
    source_hint = (data.get('source') or 'auto').strip().lower()
    if source_hint not in {'auto', 'en', 'fr', 'es', 'bn'}:
        source_hint = 'auto'

    if not text:
        return jsonify({'ok': False, 'error': 'Missing \"text\"'}), 400
    if len(text) > 200:
        return jsonify({'ok': False, 'error': 'Text too long (max 200 chars)'}), 400

    provider = (app.config.get('TRANSLATE_PROVIDER') or 'hybrid').strip().lower()
    if provider not in {'local', 'mymemory', 'hybrid'}:
        provider = 'hybrid'

    detected, local_results = _local_translate_lookup(text, source_hint)

    results = dict(local_results or {})
    used_provider = 'local'
    warnings = []

    if provider == 'mymemory':
        # Ignore local results; translate everything from the detected source language.
        results = {'en': None, 'fr': None, 'es': None, 'bn': None}
        results[detected] = text
        used_provider = 'mymemory'
    elif provider == 'hybrid':
        used_provider = 'hybrid'

    if provider in {'mymemory', 'hybrid'}:
        src_code = {'en': 'en', 'fr': 'fr', 'es': 'es', 'bn': 'bn-BD'}.get(detected, 'en')
        for code in ['en', 'fr', 'es', 'bn']:
            if results.get(code):
                continue
            tgt_code = {'en': 'en', 'fr': 'fr', 'es': 'es', 'bn': 'bn-BD'}[code]
            if src_code == tgt_code:
                results[code] = text
                continue
            try:
                results[code] = _mymemory_translate(text, src_code, tgt_code) or None
            except Exception as exc:
                warnings.append(str(exc))

    lang_tags = {'en': 'en-US', 'fr': 'fr-FR', 'es': 'es-ES', 'bn': 'bn-BD'}
    payload_results = {}
    for code in ['en', 'fr', 'es', 'bn']:
        t = results.get(code)
        payload_results[code] = {
            'text': (t.strip() if isinstance(t, str) and t.strip() else None),
            'lang_tag': lang_tags[code],
        }

    return jsonify({
        'ok': True,
        'query': text,
        'source': detected,
        'provider': used_provider,
        'warnings': warnings[:3],
        'results': payload_results,
    })

@app.route('/api/complete', methods=['POST'])
def api_complete():
    data      = request.json or {}
    lang      = data.get('language')
    lesson_id = data.get('lesson_id')
    score     = int(data.get('score', 0))
    if lang not in LANG_META or lesson_id is None:
        return jsonify({'ok': False}), 400
    try:
        lesson_id = int(lesson_id)
    except (TypeError, ValueError):
        return jsonify({'ok': False}), 400

    uid = current_user_id()
    now_iso = datetime.now().isoformat(timespec='seconds')
    conn = get_db()
    if uid is None:
        conn.execute('''
            INSERT INTO lesson_progress (language, lesson_id, completed, best_score, attempts, last_seen)
            VALUES (?, ?, 1, ?, 1, ?)
            ON CONFLICT(language, lesson_id) DO UPDATE SET
                completed  = 1,
                best_score = MAX(best_score, excluded.best_score),
                attempts   = attempts + 1,
                last_seen  = excluded.last_seen
        ''', (lang, lesson_id, score, now_iso))
    else:
        conn.execute('''
            INSERT INTO user_lesson_progress (user_id, language, lesson_id, completed, best_score, attempts, last_seen)
            VALUES (?, ?, ?, 1, ?, 1, ?)
            ON CONFLICT(user_id, language, lesson_id) DO UPDATE SET
                completed  = 1,
                best_score = MAX(best_score, excluded.best_score),
                attempts   = attempts + 1,
                last_seen  = excluded.last_seen
        ''', (uid, lang, lesson_id, score, now_iso))
    conn.commit()
    conn.close()
    if uid is not None:
        user = get_user_by_id(uid)
        quiz_url = url_for('quiz', lang=lang, lesson_id=lesson_id)
        _emit_event_to_sheets('lesson_complete', user=user, language=lang, lesson_id=lesson_id, score=score, page=quiz_url)
        _emit_user_snapshot_to_sheets(user, last_event='lesson_complete', language=lang, lesson_id=lesson_id, score=score, page=quiz_url)
    return jsonify({'ok': True})


@app.route('/api/feedback', methods=['POST'])
def api_feedback():
    data = request.json or {}
    name = (data.get('name') or '').strip()
    email = _normalize_email(data.get('email') or '')
    category = (data.get('category') or '').strip()
    language = (data.get('language') or '').strip().lower()
    message = (data.get('message') or '').strip()
    page = (data.get('page') or '').strip()

    if not name:
        return jsonify({'ok': False, 'error': 'Name is required.'}), 400
    if len(name) > 120:
        name = name[:120]
    if not _is_valid_email(email):
        return jsonify({'ok': False, 'error': 'Please enter a valid email address.'}), 400
    if not message:
        return jsonify({'ok': False, 'error': 'Message is required.'}), 400
    if len(message) > 2000:
        message = message[:2000]
    if len(category) > 80:
        category = category[:80]
    if language and language not in LANG_META:
        language = ''
    if len(page) > 300:
        page = page[:300]

    uid = current_user_id()
    now_iso = datetime.now().isoformat(timespec='seconds')

    conn = get_db()
    conn.execute(
        'INSERT INTO feedback (user_id, name, email, category, language, message, page, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        (uid, name, email, category, language, message, page, now_iso),
    )
    conn.commit()
    conn.close()

    # If the user is logged in, prefer the canonical stored name/email.
    user = get_user_by_id(uid) if uid is not None else {'id': '', 'name': name, 'email': email, 'last_login': ''}
    if user and user.get('email'):
        name = user.get('name') or name
        email = user.get('email') or email

    _emit_event_to_sheets('feedback', user={'id': user.get('id') if user else '', 'name': name, 'email': email, 'last_login': user.get('last_login') if user else ''},
                          language=language, category=category, message=message, page=page)

    feedback_row = {
        'timestamp': now_iso,
        'user_id': (user.get('id') if user else '') or '',
        'name': name,
        'email': email,
        'category': category,
        'language': language,
        'message': message,
        'page': page,
    }
    # For feedback, try a synchronous send so the UI can show a useful message if Sheets isn't configured.
    sheets_status = _sheets_send_sync('append_row', SHEETS_FEEDBACK_SHEET, feedback_row)

    if user and user.get('id') is not None:
        _emit_user_snapshot_to_sheets(user, last_event='feedback', language=language, page=page)

    return jsonify({'ok': True, 'sheets': sheets_status})

@app.route('/api/word_progress', methods=['POST'])
def api_word_progress():
    data = request.json or {}
    lang    = data.get('language')
    word    = (data.get('word') or '')[:300]   # guard against oversized input
    correct = int(data.get('correct', 0))
    source  = (data.get('source') or '').strip().lower()
    try:
        xp = int(data.get('xp', 0))
    except (TypeError, ValueError):
        xp = 0
    xp = max(0, min(50, xp))
    if lang not in LANG_META or not word:
        return jsonify({'ok': False}), 400
    now = datetime.now()
    now_iso = now.isoformat(timespec='seconds')

    # Simple spaced repetition (Leitner boxes)
    box_intervals_days = {1: 1, 2: 2, 3: 4, 4: 7, 5: 14}
    fail_retry_hours = 6

    uid = current_user_id()
    conn = get_db()
    if uid is None:
        row = conn.execute(
            'SELECT id, box FROM word_progress WHERE language=? AND word=?', (lang, word)
        ).fetchone()
    else:
        row = conn.execute(
            'SELECT id, box FROM user_word_progress WHERE user_id=? AND language=? AND word=?', (uid, lang, word)
        ).fetchone()
    old_box = int(row['box'] or 1) if row else 1

    if correct:
        new_box = min(old_box + 1, 5)
        next_due = (now + timedelta(days=box_intervals_days[new_box])).isoformat(timespec='seconds')
        if row:
            if uid is None:
                conn.execute('''
                    UPDATE word_progress
                    SET correct = correct + 1,
                        box = ?,
                        next_due = ?,
                        last_review = ?
                    WHERE language=? AND word=?
                ''', (new_box, next_due, now_iso, lang, word))
            else:
                conn.execute('''
                    UPDATE user_word_progress
                    SET correct = correct + 1,
                        box = ?,
                        next_due = ?,
                        last_review = ?
                    WHERE user_id=? AND language=? AND word=?
                ''', (new_box, next_due, now_iso, uid, lang, word))
        else:
            if uid is None:
                conn.execute('''
                    INSERT INTO word_progress (language, word, correct, incorrect, box, next_due, last_review)
                    VALUES (?,?,?,?,?,?,?)
                ''', (lang, word, 1, 0, new_box, next_due, now_iso))
            else:
                conn.execute('''
                    INSERT INTO user_word_progress (user_id, language, word, correct, incorrect, box, next_due, last_review)
                    VALUES (?,?,?,?,?,?,?,?)
                ''', (uid, lang, word, 1, 0, new_box, next_due, now_iso))
    else:
        new_box = 1
        next_due = (now + timedelta(hours=fail_retry_hours)).isoformat(timespec='seconds')
        if row:
            if uid is None:
                conn.execute('''
                    UPDATE word_progress
                    SET incorrect = incorrect + 1,
                        box = ?,
                        next_due = ?,
                        last_review = ?
                    WHERE language=? AND word=?
                ''', (new_box, next_due, now_iso, lang, word))
            else:
                conn.execute('''
                    UPDATE user_word_progress
                    SET incorrect = incorrect + 1,
                        box = ?,
                        next_due = ?,
                        last_review = ?
                    WHERE user_id=? AND language=? AND word=?
                ''', (new_box, next_due, now_iso, uid, lang, word))
        else:
            if uid is None:
                conn.execute('''
                    INSERT INTO word_progress (language, word, correct, incorrect, box, next_due, last_review)
                    VALUES (?,?,?,?,?,?,?)
                ''', (lang, word, 0, 1, new_box, next_due, now_iso))
            else:
                conn.execute('''
                    INSERT INTO user_word_progress (user_id, language, word, correct, incorrect, box, next_due, last_review)
                    VALUES (?,?,?,?,?,?,?,?)
                ''', (uid, lang, word, 0, 1, new_box, next_due, now_iso))

    # Log daily activity for streak/XP (client can pass xp per action)
    today = date.today().isoformat()
    if uid is None:
        conn.execute('''
            INSERT INTO daily_activity (date, xp, reviews, correct, wrong)
            VALUES (?, ?, 1, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                xp = xp + excluded.xp,
                reviews = reviews + excluded.reviews,
                correct = correct + excluded.correct,
                wrong = wrong + excluded.wrong
        ''', (today, xp, 1 if correct else 0, 0 if correct else 1))
    else:
        conn.execute('''
            INSERT INTO user_daily_activity (user_id, date, xp, reviews, correct, wrong)
            VALUES (?, ?, ?, 1, ?, ?)
            ON CONFLICT(user_id, date) DO UPDATE SET
                xp = xp + excluded.xp,
                reviews = reviews + excluded.reviews,
                correct = correct + excluded.correct,
                wrong = wrong + excluded.wrong
        ''', (uid, today, xp, 1 if correct else 0, 0 if correct else 1))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

# ---------- Entry point (local dev only) ----------
if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    port = int(os.environ.get('PORT', 5000))
    # Bind to all interfaces in production (PORT env set by host), localhost otherwise
    host = '0.0.0.0' if os.environ.get('PORT') else '127.0.0.1'
    print()
    print("=" * 55)
    print("  Language Coach  --  Bhasha Shikkha")
    print("=" * 55)
    print(f"  Open your browser:  http://localhost:{port}")
    print("  Press Ctrl+C to stop")
    print("=" * 55)
    print()
    app.run(debug=False, host=host, port=port)
