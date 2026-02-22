import hashlib
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
from functools import lru_cache
from typing import Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from flask import Flask, render_template, jsonify, request, redirect, url_for, send_file

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'language_coach_dev')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DB_PATH  = os.path.join(DATA_DIR, 'progress.db')
TTS_CACHE_DIR = (os.environ.get('TTS_CACHE_DIR') or os.path.join(DATA_DIR, 'tts_cache')).strip() or os.path.join(DATA_DIR, 'tts_cache')

_TTS_PROVIDER = (os.environ.get('TTS_PROVIDER') or 'auto').strip().lower()
if _TTS_PROVIDER not in {'browser', 'gtts', 'auto'}:
    _TTS_PROVIDER = 'auto'
app.config['TTS_PROVIDER'] = _TTS_PROVIDER
app.config['TTS_CACHE_DIR'] = TTS_CACHE_DIR

_TRANSLATE_PROVIDER = (os.environ.get('TRANSLATE_PROVIDER') or 'hybrid').strip().lower()
if _TRANSLATE_PROVIDER not in {'local', 'mymemory', 'hybrid'}:
    _TRANSLATE_PROVIDER = 'hybrid'
app.config['TRANSLATE_PROVIDER'] = _TRANSLATE_PROVIDER

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


def _build_resource_drill_questions(lang, total_q, vocab_by_cat, vocab_all, resource_sentences, tts_lang):
    if not resource_sentences:
        return []

    entries, variant_index = _build_vocab_variant_index(vocab_by_cat)
    if not entries:
        return []

    stop = _STOPWORDS.get(lang, set())

    # Prefer due words, but fall back to any vocab word if no SRS history exists.
    now_iso = datetime.now().isoformat(timespec='seconds')
    conn = get_db()
    due_rows = conn.execute('''
        SELECT word
        FROM word_progress
        WHERE language=?
          AND (next_due IS NULL OR next_due <= ?)
        ORDER BY COALESCE(next_due, '') ASC, box ASC, incorrect DESC
        LIMIT ?
    ''', (lang, now_iso, max(200, total_q * 12))).fetchall()
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
        CREATE TABLE IF NOT EXISTS word_progress (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            language    TEXT NOT NULL,
            word        TEXT NOT NULL,
            correct     INTEGER DEFAULT 0,
            incorrect   INTEGER DEFAULT 0,
            UNIQUE(language, word)
        );
        CREATE TABLE IF NOT EXISTS daily_activity (
            date     TEXT PRIMARY KEY,
            xp       INTEGER DEFAULT 0,
            reviews  INTEGER DEFAULT 0,
            correct  INTEGER DEFAULT 0,
            wrong    INTEGER DEFAULT 0
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

    conn.commit()
    conn.close()

# Initialise DB at import time so gunicorn (production) also creates tables
init_db()

def load_progress(lang):
    conn = get_db()
    rows = conn.execute(
        'SELECT lesson_id, completed, best_score, attempts, last_seen FROM lesson_progress WHERE language=?', (lang,)
    ).fetchall()
    conn.close()
    return {r['lesson_id']: dict(r) for r in rows}

def touch_lesson(lang, lesson_id):
    """Update last_seen for a lesson even if the user doesn't finish a quiz."""
    conn = get_db()
    conn.execute('''
        INSERT INTO lesson_progress (language, lesson_id, completed, best_score, attempts, last_seen)
        VALUES (?, ?, 0, 0, 0, ?)
        ON CONFLICT(language, lesson_id) DO UPDATE SET
            last_seen = excluded.last_seen
    ''', (lang, lesson_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def add_activity(xp=0, reviews=0, correct=0, wrong=0):
    xp = int(xp or 0)
    reviews = int(reviews or 0)
    correct = int(correct or 0)
    wrong = int(wrong or 0)
    if xp == 0 and reviews == 0 and correct == 0 and wrong == 0:
        return

    today = date.today().isoformat()
    conn = get_db()
    conn.execute('''
        INSERT INTO daily_activity (date, xp, reviews, correct, wrong)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET
            xp = xp + excluded.xp,
            reviews = reviews + excluded.reviews,
            correct = correct + excluded.correct,
            wrong = wrong + excluded.wrong
    ''', (today, xp, reviews, correct, wrong))
    conn.commit()
    conn.close()


def get_activity_summary():
    today = date.today()
    today_key = today.isoformat()

    conn = get_db()
    row = conn.execute(
        'SELECT xp, reviews, correct, wrong FROM daily_activity WHERE date=?', (today_key,)
    ).fetchone()
    rows = conn.execute(
        'SELECT date, xp FROM daily_activity WHERE xp > 0 ORDER BY date DESC LIMIT 60'
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

_CEFR_ORDER = {'A1': 1, 'A2': 2, 'B1': 3, 'B2': 4, 'C1': 5, 'C2': 6}


def _lesson_cefr(lesson) -> str:
    return (lesson.get('cefr_level') or lesson.get('level') or '').strip().upper()


def _cefr_rank(level: str) -> int:
    return _CEFR_ORDER.get((level or '').strip().upper(), 99)


def _sorted_lessons(lesson_list):
    return sorted(lesson_list or [], key=lambda l: (_cefr_rank(_lesson_cefr(l)), l.get('id', 0)))


def _find_lesson(lesson_list, lesson_id):
    return next((l for l in lesson_list if l.get('id') == lesson_id), None)


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
    return {
        'lang_meta': LANG_META,
        'tts_provider': app.config.get('TTS_PROVIDER', 'auto'),
        'ui_theme': ui_theme,
        'current_year': datetime.now().year,
        'static_version': _static_asset_version(),
    }

# ---------- Routes ----------
@app.route('/')
def dashboard():
    lessons_all = get_lessons()
    vocab_all = get_vocab()
    resource_all = get_resource_sentences()
    activity = get_activity_summary()

    cefr_counts = Counter()
    canon = lessons_all.get('french', []) or next(iter(lessons_all.values()), [])
    for l in canon or []:
        lvl = (l.get('cefr_level') or l.get('level') or '').strip() or 'A1'
        cefr_counts[lvl] += 1

    stats = {}
    for lang in LANGS:
        prog = load_progress(lang)
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

@app.route('/language/<lang>')
def language_home(lang):
    if lang not in LANG_META:
        return redirect(url_for('dashboard'))
    lessons = get_lessons().get(lang, [])
    progress = load_progress(lang)
    resume = _recommended_lesson(lessons, progress)
    return render_template('language.html', lang=lang, meta=LANG_META[lang],
                           lessons=lessons, progress=progress, resume_lesson=resume)

@app.route('/lesson/<lang>/<int:lesson_id>')
def lesson_view(lang, lesson_id):
    if lang not in LANG_META:
        return redirect(url_for('dashboard'))
    lesson_list = _sorted_lessons(get_lessons().get(lang, []))
    lesson = _find_lesson(lesson_list, lesson_id)
    if not lesson:
        return redirect(url_for('language_home', lang=lang))

    touch_lesson(lang, lesson_id)
    vocab   = get_lesson_vocab(lang, lesson)
    grammar = lesson.get('grammar')
    # next lesson for navigation
    idx      = next((i for i, l in enumerate(lesson_list) if l.get('id') == lesson_id), None)
    next_l   = lesson_list[idx + 1] if idx is not None and idx + 1 < len(lesson_list) else None
    prev_l   = lesson_list[idx - 1] if idx is not None and idx > 0 else None

    return render_template('lesson.html', lang=lang, meta=LANG_META[lang],
                           lesson=lesson, vocabulary=vocab, grammar=grammar,
                           next_lesson=next_l, prev_lesson=prev_l)

@app.route('/flashcards/<lang>/<int:lesson_id>')
def flashcards(lang, lesson_id):
    if lang not in LANG_META:
        return redirect(url_for('dashboard'))
    lesson_list = get_lessons().get(lang, [])
    lesson = _find_lesson(lesson_list, lesson_id)
    if not lesson:
        return redirect(url_for('language_home', lang=lang))
    touch_lesson(lang, lesson_id)
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
        rows = conn.execute('''
            SELECT word
            FROM word_progress
            WHERE language=?
              AND (next_due IS NULL OR next_due <= ?)
            ORDER BY COALESCE(next_due, '') ASC, box ASC, incorrect DESC
            LIMIT ?
        ''', (lang, now_iso, limit)).fetchall()
        conn.close()

        for r in rows:
            entry = vocab_lookup.get(r['word'])
            if entry:
                review_words.append(entry)

    if mode == 'weak' and not review_words:
        conn = get_db()
        rows = conn.execute(
            'SELECT word, correct, incorrect FROM word_progress WHERE language=?', (lang,)
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
    progress = load_progress(lang)
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
        questions = _build_resource_drill_questions(lang, total_q, vocab_by_cat, vocab_all, resource_sentences, tts_lang)
        if questions:
            return render_template('practice.html',
                                   lang=lang, meta=LANG_META[lang],
                                   questions=questions,
                                   questions_json=json.dumps(questions, ensure_ascii=False))
        return redirect(url_for('practice', lang=lang))

    # Prefer due words (spaced repetition); otherwise pick random vocabulary.
    now_iso = datetime.now().isoformat(timespec='seconds')
    conn = get_db()
    due_rows = conn.execute('''
        SELECT word
        FROM word_progress
        WHERE language=?
          AND (next_due IS NULL OR next_due <= ?)
        ORDER BY COALESCE(next_due, '') ASC, box ASC, incorrect DESC
        LIMIT ?
    ''', (lang, now_iso, total_q)).fetchall()
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
def dictation(lang, lesson_id):
    if lang not in LANG_META:
        return redirect(url_for('dashboard'))
    lesson_list = _sorted_lessons(get_lessons().get(lang, []))
    lesson = _find_lesson(lesson_list, lesson_id)
    if not lesson:
        return redirect(url_for('language_home', lang=lang))
    touch_lesson(lang, lesson_id)
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


@app.route('/quiz/<lang>/<int:lesson_id>')
def quiz(lang, lesson_id):
    if lang not in LANG_META:
        return redirect(url_for('dashboard'))
    lesson_list = _sorted_lessons(get_lessons().get(lang, []))
    lesson = _find_lesson(lesson_list, lesson_id)
    if not lesson:
        return redirect(url_for('language_home', lang=lang))
    touch_lesson(lang, lesson_id)

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
    lessons_all = get_lessons()
    all_prog = {}
    for lang in LANGS:
        prog = load_progress(lang)
        lesson_list = _sorted_lessons(lessons_all.get(lang, []))
        enriched = []
        for l in lesson_list:
            p = prog.get(l['id'], {'completed': 0, 'best_score': 0, 'attempts': 0})
            enriched.append({**l, **p})
        all_prog[lang] = enriched
    return render_template('progress.html', progress=all_prog)

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
    conn = get_db()
    conn.execute('''
        INSERT INTO lesson_progress (language, lesson_id, completed, best_score, attempts, last_seen)
        VALUES (?, ?, 1, ?, 1, ?)
        ON CONFLICT(language, lesson_id) DO UPDATE SET
            completed  = 1,
            best_score = MAX(best_score, excluded.best_score),
            attempts   = attempts + 1,
            last_seen  = excluded.last_seen
    ''', (lang, lesson_id, score, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/word_progress', methods=['POST'])
def api_word_progress():
    data = request.json or {}
    lang    = data.get('language')
    word    = data.get('word')
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

    conn = get_db()
    row = conn.execute(
        'SELECT id, box FROM word_progress WHERE language=? AND word=?', (lang, word)
    ).fetchone()
    old_box = int(row['box'] or 1) if row else 1

    if correct:
        new_box = min(old_box + 1, 5)
        next_due = (now + timedelta(days=box_intervals_days[new_box])).isoformat(timespec='seconds')
        if row:
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
                INSERT INTO word_progress (language, word, correct, incorrect, box, next_due, last_review)
                VALUES (?,?,?,?,?,?,?)
            ''', (lang, word, 1, 0, new_box, next_due, now_iso))
    else:
        new_box = 1
        next_due = (now + timedelta(hours=fail_retry_hours)).isoformat(timespec='seconds')
        if row:
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
                INSERT INTO word_progress (language, word, correct, incorrect, box, next_due, last_review)
                VALUES (?,?,?,?,?,?,?)
            ''', (lang, word, 0, 1, new_box, next_due, now_iso))

    # Log daily activity for streak/XP (client can pass xp per action)
    today = date.today().isoformat()
    conn.execute('''
        INSERT INTO daily_activity (date, xp, reviews, correct, wrong)
        VALUES (?, ?, 1, ?, ?)
        ON CONFLICT(date) DO UPDATE SET
            xp = xp + excluded.xp,
            reviews = reviews + excluded.reviews,
            correct = correct + excluded.correct,
            wrong = wrong + excluded.wrong
    ''', (today, xp, 1 if correct else 0, 0 if correct else 1))
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
