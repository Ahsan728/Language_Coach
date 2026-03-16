
import base64
import hashlib
import io
import os
import json
import random
import re
import secrets
import shutil
import sqlite3
import threading
import time
import unicodedata
import uuid
from datetime import datetime, date, timedelta, timezone
from collections import Counter
from functools import lru_cache, wraps
from typing import Optional
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from flask import (
    Flask,
    current_app,
    has_app_context,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)


def _load_env_file(path: str) -> None:
    """Load KEY=VALUE lines from a local .env file (optional)."""
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


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ENV_DIR = BASE_DIR
_load_env_file(os.path.join(_ENV_DIR, '.env'))
_load_env_file(os.path.join(_ENV_DIR, 'env'))

APP_TIMEZONE = (os.environ.get('APP_TIMEZONE') or '').strip()
_APP_TZ = None
if APP_TIMEZONE:
    try:
        from zoneinfo import ZoneInfo  # Python 3.9+
        _APP_TZ = ZoneInfo(APP_TIMEZONE)
    except Exception:
        _APP_TZ = None


def _app_now() -> datetime:
    """Naive local datetime in the configured `APP_TIMEZONE` (or system local time)."""
    if _APP_TZ is not None:
        return datetime.now(_APP_TZ).replace(tzinfo=None)
    return datetime.now()


def _now_iso() -> str:
    """ISO timestamp (seconds precision) using app-local time (Sheets friendly)."""
    return _app_now().isoformat(timespec='seconds')


def _today_date() -> date:
    """Today's date in app-local time."""
    return _app_now().date()


def _today_iso() -> str:
    """YYYY-MM-DD using app-local time."""
    return _today_date().isoformat()


def _app_tzinfo():
    if _APP_TZ is not None:
        return _APP_TZ
    try:
        return datetime.now().astimezone().tzinfo or timezone.utc
    except Exception:
        return timezone.utc


def to_rfc3339(value) -> Optional[str]:
    if value in (None, ''):
        return None

    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        except (TypeError, ValueError):
            return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_app_tzinfo())
    else:
        dt = dt.astimezone(_app_tzinfo())

    return dt.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def utc_now_rfc3339() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


DATA_DIR = os.path.join(BASE_DIR, 'data')
DB_PATH = os.path.join(DATA_DIR, 'progress.db')
TTS_CACHE_DIR = (os.environ.get('TTS_CACHE_DIR') or os.path.join(DATA_DIR, 'tts_cache')).strip() or os.path.join(DATA_DIR, 'tts_cache')

_TTS_PROVIDER = 'gtts'

_TRANSLATE_PROVIDER = (os.environ.get('TRANSLATE_PROVIDER') or 'hybrid').strip().lower()
if _TRANSLATE_PROVIDER not in {'local', 'mymemory', 'hybrid'}:
    _TRANSLATE_PROVIDER = 'hybrid'

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


def build_path_config(source=None):
    source = source or {}
    base_dir = os.path.abspath(source.get('BASE_DIR') or BASE_DIR)
    data_dir = os.path.abspath(source.get('DATA_DIR') or os.path.join(base_dir, 'data'))
    static_dir = os.path.abspath(source.get('STATIC_DIR') or os.path.join(base_dir, 'static'))
    template_dir = os.path.abspath(source.get('TEMPLATE_DIR') or os.path.join(base_dir, 'templates'))
    logo_dir = os.path.abspath(source.get('LOGO_DIR') or os.path.join(base_dir, 'logo'))
    return {
        'BASE_DIR': base_dir,
        'DATA_DIR': data_dir,
        'STATIC_DIR': static_dir,
        'TEMPLATE_DIR': template_dir,
        'LOGO_DIR': logo_dir,
        'DB_PATH': os.path.abspath(source.get('DB_PATH') or os.path.join(data_dir, 'progress.db')),
        'TTS_CACHE_DIR': os.path.abspath(source.get('TTS_CACHE_DIR') or os.path.join(data_dir, 'tts_cache')),
        'VOCAB_PATH': os.path.abspath(source.get('VOCAB_PATH') or os.path.join(data_dir, 'vocabulary.json')),
        'LESSONS_PATH': os.path.abspath(source.get('LESSONS_PATH') or os.path.join(data_dir, 'lessons.json')),
        'RESOURCE_SENTENCES_PATH': os.path.abspath(source.get('RESOURCE_SENTENCES_PATH') or os.path.join(data_dir, 'resource_sentences.json')),
        'PDF_FONT_PATH': os.path.abspath(
            source.get('PDF_FONT_PATH') or os.path.join(static_dir, 'fonts', 'NotoSerifBengali-Regular.ttf')
        ),
        'PDF_FONT_BOLD_PATH': os.path.abspath(
            source.get('PDF_FONT_BOLD_PATH') or os.path.join(static_dir, 'fonts', 'NotoSerifBengali-Bold.ttf')
        ),
        'PDF_HTML_BN_FONT_REG_PATH': os.path.abspath(
            source.get('PDF_HTML_BN_FONT_REG_PATH') or os.path.join(static_dir, 'fonts', 'NotoSerifBengali-Regular.ttf')
        ),
        'PDF_HTML_BN_FONT_BOLD_PATH': os.path.abspath(
            source.get('PDF_HTML_BN_FONT_BOLD_PATH') or os.path.join(static_dir, 'fonts', 'NotoSerifBengali-Bold.ttf')
        ),
    }


_DEFAULT_PATH_CONFIG = build_path_config()


def _config_value(name: str, default=None):
    if has_app_context():
        value = current_app.config.get(name)
        if value not in (None, ''):
            return value
    return default


def _config_path(name: str) -> str:
    default = _DEFAULT_PATH_CONFIG[name]
    value = _config_value(name, default)
    return os.path.abspath(value)


def configure_app(app: Flask) -> None:
    app.config.update(build_path_config(app.config))

    secret_key = (app.config.get('SECRET_KEY') or os.environ.get('SECRET_KEY') or '').strip()
    if not secret_key:
        import warnings
        warnings.warn(
            'SECRET_KEY env var is not set - using an insecure dev key. '
            'Run: python -c "import secrets; print(secrets.token_hex(32))" '
            'and set SECRET_KEY in your environment or a .env file.',
            stacklevel=1,
        )
        secret_key = 'language_coach_dev_INSECURE'
    app.secret_key = secret_key

    try:
        remember_days = int(app.config.get('REMEMBER_ME_DAYS') or os.environ.get('REMEMBER_ME_DAYS') or 30)
    except (TypeError, ValueError):
        remember_days = 30
    remember_days = max(1, min(365, remember_days))
    app.permanent_session_lifetime = timedelta(days=remember_days)

    app.config['TTS_PROVIDER'] = app.config.get('TTS_PROVIDER') or _TTS_PROVIDER
    app.config['TRANSLATE_PROVIDER'] = app.config.get('TRANSLATE_PROVIDER') or _TRANSLATE_PROVIDER
    app.config['SHEETS_WEBHOOK_URL'] = app.config.get('SHEETS_WEBHOOK_URL') or SHEETS_WEBHOOK_URL
    app.config['SHEETS_WEBHOOK_TOKEN'] = app.config.get('SHEETS_WEBHOOK_TOKEN') or SHEETS_WEBHOOK_TOKEN
    app.config['SHEETS_WEBHOOK_TIMEOUT'] = app.config.get('SHEETS_WEBHOOK_TIMEOUT') or SHEETS_WEBHOOK_TIMEOUT
    app.config['SHEETS_USERS_SHEET'] = app.config.get('SHEETS_USERS_SHEET') or SHEETS_USERS_SHEET
    app.config['SHEETS_EVENTS_SHEET'] = app.config.get('SHEETS_EVENTS_SHEET') or SHEETS_EVENTS_SHEET
    app.config['SHEETS_FEEDBACK_SHEET'] = app.config.get('SHEETS_FEEDBACK_SHEET') or SHEETS_FEEDBACK_SHEET


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
    cache_key = (key, os.path.abspath(path))
    try:
        mtime = os.path.getmtime(path)
    except FileNotFoundError:
        return default

    with _DATA_LOCK:
        if _DATA_MTIME.get(cache_key) == mtime and cache_key in _DATA_CACHE:
            return _DATA_CACHE[cache_key]

        # If the current mtime previously failed to parse, avoid spamming logs.
        if _DATA_ERROR_MTIME.get(cache_key) == mtime and cache_key in _DATA_CACHE:
            return _DATA_CACHE[cache_key]

        try:
            data = _read_json(path)
        except json.JSONDecodeError as exc:
            _DATA_ERROR_MTIME[cache_key] = mtime
            print(f"WARNING: Could not parse {path}: {exc}")
            return _DATA_CACHE.get(cache_key, default)

        _DATA_CACHE[cache_key] = data
        _DATA_MTIME[cache_key] = mtime
        _DATA_ERROR_MTIME.pop(cache_key, None)
        return data


def get_vocab():
    return _cached_json('vocab', _config_path('VOCAB_PATH'), default={})


def get_lessons():
    return _cached_json('lessons', _config_path('LESSONS_PATH'), default={})


def get_resource_sentences():
    """Optional: extracted sentences from local PDFs (see scripts/build_resource_sentences.py)."""
    return _cached_json('resource_sentences', _config_path('RESOURCE_SENTENCES_PATH'), default={})


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
    now_iso = _now_iso()
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
    conn = sqlite3.connect(_config_path('DB_PATH'))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(_config_path('DATA_DIR'), exist_ok=True)
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
        CREATE TABLE IF NOT EXISTS api_sessions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            token_hash   TEXT NOT NULL UNIQUE,
            created_at   TEXT NOT NULL,
            expires_at   TEXT NOT NULL,
            last_used_at TEXT,
            revoked_at   TEXT
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
        CREATE INDEX IF NOT EXISTS idx_api_sessions_user_id
            ON api_sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_api_sessions_expires_at
            ON api_sessions(expires_at);
    ''')

    conn.commit()
    conn.close()

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


_SHEETS_ALLOWED_WEBHOOK_HOSTS = {
    'script.google.com',
    'script.googleusercontent.com',
}


def _validate_sheets_webhook_url(url: str) -> Optional[str]:
    """Return an error string if the webhook URL is misconfigured (otherwise None)."""
    u = (url or '').strip()
    if not u:
        return 'not_configured'
    try:
        parsed = urlparse(u)
    except Exception:
        return 'bad_webhook_url: invalid URL'

    scheme = (parsed.scheme or '').lower()
    host = (parsed.hostname or '').lower()
    path = parsed.path or ''

    if scheme not in {'http', 'https'}:
        return 'bad_webhook_url: must start with https://'

    # Common mistake: pasting the spreadsheet URL instead of the Apps Script Web App URL.
    if host in {'docs.google.com', 'drive.google.com'}:
        return 'bad_webhook_url: paste the Apps Script Web App URL (https://script.google.com/macros/s/.../exec), not the spreadsheet link'

    if host and host not in _SHEETS_ALLOWED_WEBHOOK_HOSTS:
        return f'bad_webhook_url: expected script.google.com (got {host})'

    if not host:
        return 'bad_webhook_url: missing host'

    # Apps Script Web App URLs end with `/exec` (or `/dev` in test mode).
    if host == 'script.google.com':
        if not (path.endswith('/exec') or path.endswith('/dev')):
            return 'bad_webhook_url: Apps Script Web App URL must end with /exec (or /dev)'

    return None


def _sheets_send(action: str, sheet: str, row: dict):
    """Send a row to Google Sheets via an Apps Script webhook (optional).

    This is best-effort: failures are swallowed so the learning app remains usable.
    Configure via env vars:
      - SHEETS_WEBHOOK_URL
      - SHEETS_WEBHOOK_TOKEN (optional but recommended)
    """
    if not SHEETS_WEBHOOK_URL:
        return
    url_error = _validate_sheets_webhook_url(SHEETS_WEBHOOK_URL)
    if url_error and url_error != 'not_configured':
        return

    payload = {
        'action': (action or '').strip() or 'append_row',
        'sheet': (sheet or '').strip() or SHEETS_EVENTS_SHEET,
        'row': row or {},
    }
    if SHEETS_WEBHOOK_TOKEN:
        payload['token'] = SHEETS_WEBHOOK_TOKEN

    def _do_post():
        try:
            # Prefer requests if available (more robust redirect/TLS handling on some hosts).
            try:
                import requests  # type: ignore
                resp = requests.post(
                    SHEETS_WEBHOOK_URL,
                    json=payload,
                    timeout=SHEETS_WEBHOOK_TIMEOUT,
                    allow_redirects=False,
                    headers={'User-Agent': 'LanguageCoach/1.0'},
                )
                _ = (resp.content or b'')[:256]
                return
            except Exception:
                pass

            body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            req = Request(
                SHEETS_WEBHOOK_URL,
                data=body,
                headers={'Content-Type': 'application/json; charset=utf-8'},
            )
            try:
                with urlopen(req, timeout=SHEETS_WEBHOOK_TIMEOUT) as resp:
                    resp.read(256)
            except Exception:
                return
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
    url_error = _validate_sheets_webhook_url(SHEETS_WEBHOOK_URL)
    if url_error and url_error != 'not_configured':
        return {'enabled': True, 'ok': False, 'error': url_error}

    payload = {
        'action': (action or '').strip() or 'append_row',
        'sheet': (sheet or '').strip() or SHEETS_EVENTS_SHEET,
        'row': row or {},
    }
    if SHEETS_WEBHOOK_TOKEN:
        payload['token'] = SHEETS_WEBHOOK_TOKEN

    try:
        # Prefer requests if available (more robust redirect/TLS handling on some hosts).
        try:
            import requests  # type: ignore
            redirect_statuses = {301, 302, 303, 307, 308}

            # Post without following redirects. Apps Script often returns a 302 to a
            # `script.googleusercontent.com` URL that serves the JSON response.
            resp = requests.post(
                SHEETS_WEBHOOK_URL,
                json=payload,
                timeout=SHEETS_WEBHOOK_TIMEOUT,
                allow_redirects=False,
                headers={'User-Agent': 'LanguageCoach/1.0'},
            )
            raw = (resp.content or b'')[:8192]
            status = int(resp.status_code)

            # If we got redirected, try to follow the redirect to confirm JSON.
            # If the follow fails (common on some restricted hosts), assume the POST succeeded.
            if status in redirect_statuses:
                location = (resp.headers or {}).get('location') or (resp.headers or {}).get('Location')
                if not location:
                    return {'enabled': True, 'ok': True, 'error': None, 'note': 'redirect_no_location'}
                try:
                    follow = requests.get(
                        location,
                        timeout=SHEETS_WEBHOOK_TIMEOUT,
                        headers={'User-Agent': 'LanguageCoach/1.0'},
                    )
                    follow_status = int(follow.status_code)
                    if follow_status >= 400:
                        return {'enabled': True, 'ok': True, 'error': None, 'note': f'redirect_follow_http_{follow_status}'}
                    raw = (follow.content or b'')[:8192]
                    status = follow_status
                except Exception:
                    return {'enabled': True, 'ok': True, 'error': None, 'note': 'redirect_follow_failed'}
        except Exception:
            body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            req = Request(
                SHEETS_WEBHOOK_URL,
                data=body,
                headers={'Content-Type': 'application/json; charset=utf-8'},
            )
            try:
                from urllib.error import HTTPError
                with urlopen(req, timeout=SHEETS_WEBHOOK_TIMEOUT) as resp:
                    raw = (resp.read(8192) or b'')
                    status = int(getattr(resp, 'status', 200) or 200)
            except HTTPError as http_err:
                status = int(getattr(http_err, 'code', 500) or 500)
                raw = (http_err.read(8192) or b'')
            except Exception as exc:
                # If the urllib path fails, surface a useful error string.
                return {'enabled': True, 'ok': False, 'error': str(exc) or type(exc).__name__}
    except Exception as exc:
        return {'enabled': True, 'ok': False, 'error': str(exc) or type(exc).__name__}

    if status >= 400:
        snippet = raw.decode('utf-8', 'replace')[:300].strip()
        host = ''
        try:
            host = urlparse(SHEETS_WEBHOOK_URL).hostname or ''
        except Exception:
            host = ''
        prefix = f"http_{status}"
        if host:
            prefix += f" ({host})"
        return {'enabled': True, 'ok': False, 'error': f"{prefix}: {snippet or 'request_failed'}"}

    try:
        parsed = json.loads(raw.decode('utf-8', 'replace') or '{}')
    except Exception:
        snippet = raw.decode('utf-8', 'replace')[:300].strip()
        return {'enabled': True, 'ok': False, 'error': f"non_json_response: {snippet or 'invalid'}"}

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


def _get_user_last_lesson_info(user_id: int, language: str = '') -> Optional[dict]:
    """Return the most recently seen lesson for a user (best-effort)."""
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return None

    conn = get_db()
    row = None
    try:
        if language:
            row = conn.execute(
                'SELECT language, lesson_id, best_score, last_seen FROM user_lesson_progress '
                'WHERE user_id=? AND language=? ORDER BY last_seen DESC LIMIT 1',
                (user_id, language),
            ).fetchone()
        if row is None:
            row = conn.execute(
                'SELECT language, lesson_id, best_score, last_seen FROM user_lesson_progress '
                'WHERE user_id=? ORDER BY last_seen DESC LIMIT 1',
                (user_id,),
            ).fetchone()
    finally:
        conn.close()

    return dict(row) if row else None


def _emit_user_snapshot_to_sheets(user: dict, last_event: str = '', language: str = '', lesson_id=None, score=None, page: str = ''):
    if not user or not user.get('email'):
        return
    uid = user.get('id')
    progress, activity = _user_snapshot(uid)
    last_lesson = _get_user_last_lesson_info(uid, language=language) or {}
    now_iso = _now_iso()

    fr = progress.get('french') or {}
    es = progress.get('spanish') or {}

    row = {
        'updated_at': now_iso,
        'user_id': uid or '',
        'name': user.get('name') or '',
        'email': user.get('email') or '',
        'last_login': user.get('last_login') or '',
        'last_event': last_event or '',
        'last_lang': language or (last_lesson.get('language') or ''),
        'last_lesson_id': lesson_id if lesson_id is not None else (last_lesson.get('lesson_id') if last_lesson else ''),
        'last_score': score if score is not None else (last_lesson.get('best_score') if last_lesson else ''),
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

    status = _sheets_send_sync('upsert_user', SHEETS_USERS_SHEET, row)
    if status and status.get('enabled') and status.get('ok') is False:
        err = status.get('error') or 'unknown error'
        print(f"WARNING: Google Sheets user snapshot failed: {err}")


def _emit_event_to_sheets(event: str, user: dict = None, language: str = '', lesson_id=None, score=None,
                          category: str = '', message: str = '', page: str = ''):
    now_iso = _now_iso()
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

    now_iso = _now_iso()
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


def _hash_api_token(token: str) -> str:
    return hashlib.sha256((token or '').encode('utf-8')).hexdigest()


def create_api_session(user_id: int, expires_in: timedelta) -> dict:
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        raise ValueError('Invalid user_id') from None

    if not isinstance(expires_in, timedelta) or expires_in <= timedelta(0):
        raise ValueError('expires_in must be a positive timedelta')

    token = f'lc_{secrets.token_urlsafe(32)}'
    now = datetime.now(timezone.utc)
    now_iso = to_rfc3339(now)
    expires_at = to_rfc3339(now + expires_in)

    conn = get_db()
    conn.execute(
        '''
        INSERT INTO api_sessions (user_id, token_hash, created_at, expires_at, last_used_at)
        VALUES (?, ?, ?, ?, ?)
        ''',
        (user_id, _hash_api_token(token), now_iso, expires_at, now_iso),
    )
    conn.commit()
    conn.close()

    return {'access_token': token, 'expires_at': expires_at}


def get_api_session(token: str, touch: bool = False):
    token = (token or '').strip()
    if not token:
        return None

    now_iso = utc_now_rfc3339()
    conn = get_db()
    row = conn.execute(
        '''
        SELECT id, user_id, created_at, expires_at, last_used_at, revoked_at
        FROM api_sessions
        WHERE token_hash=?
        ''',
        (_hash_api_token(token),),
    ).fetchone()
    if not row:
        conn.close()
        return None

    payload = dict(row)
    expired = False
    if payload.get('revoked_at'):
        expired = True
    else:
        try:
            expires_at = datetime.fromisoformat(str(payload.get('expires_at')).replace('Z', '+00:00'))
            expired = expires_at <= datetime.now(timezone.utc)
        except (TypeError, ValueError):
            expired = True

    if expired:
        conn.execute(
            'UPDATE api_sessions SET revoked_at=COALESCE(revoked_at, ?) WHERE id=?',
            (now_iso, payload['id']),
        )
        conn.commit()
        conn.close()
        return None

    if touch:
        conn.execute('UPDATE api_sessions SET last_used_at=? WHERE id=?', (now_iso, payload['id']))
        conn.commit()
        payload['last_used_at'] = now_iso

    conn.close()
    return payload


def revoke_api_session(token: str) -> bool:
    token = (token or '').strip()
    if not token:
        return False

    now_iso = utc_now_rfc3339()
    conn = get_db()
    cur = conn.execute(
        'UPDATE api_sessions SET revoked_at=? WHERE token_hash=? AND revoked_at IS NULL',
        (now_iso, _hash_api_token(token)),
    )
    conn.commit()
    conn.close()
    return bool(cur.rowcount)


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
    now_iso = _now_iso()
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
    return now_iso

def add_activity(xp=0, reviews=0, correct=0, wrong=0, user_id=None):
    xp = int(xp or 0)
    reviews = int(reviews or 0)
    correct = int(correct or 0)
    wrong = int(wrong or 0)
    if xp == 0 and reviews == 0 and correct == 0 and wrong == 0:
        return

    today = _today_iso()
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
    today = _today_date()
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
    correct_today = int(row['correct']) if row else 0
    wrong_today = int(row['wrong']) if row else 0

    active_dates = {r['date'] for r in rows}
    streak = 0
    cursor = today
    while cursor.isoformat() in active_dates:
        streak += 1
        cursor -= timedelta(days=1)

    return {
        'xp_today': xp_today,
        'reviews_today': reviews_today,
        'correct_today': correct_today,
        'wrong_today': wrong_today,
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
_PDF_FONT_READY = {}


def _pdf_font_names(regular_path: str):
    suffix = hashlib.sha1(os.path.abspath(regular_path).encode('utf-8')).hexdigest()[:10]
    return f'LC-NotoSerifBengali-{suffix}', f'LC-NotoSerifBengali-Bold-{suffix}'


def _ensure_pdf_font_registered():
    """Register a Unicode font for Bengali/Latin PDF exports (idempotent)."""
    regular_path = _config_path('PDF_FONT_PATH')
    bold_path = _config_path('PDF_FONT_BOLD_PATH')
    cache_key = (regular_path, bold_path)
    if cache_key in _PDF_FONT_READY:
        return _PDF_FONT_READY[cache_key]

    with _PDF_FONT_LOCK:
        if cache_key in _PDF_FONT_READY:
            return _PDF_FONT_READY[cache_key]

        if not os.path.exists(regular_path):
            return None, None

        try:
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
        except Exception:
            return None, None

        font_name, font_bold_name = _pdf_font_names(regular_path)

        try:
            if font_name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(font_name, regular_path))
            if os.path.exists(bold_path) and font_bold_name not in pdfmetrics.getRegisteredFontNames():
                try:
                    pdfmetrics.registerFont(TTFont(font_bold_name, bold_path))
                except Exception as exc:
                    print(f"WARNING: Could not register PDF font {font_bold_name}: {exc}")
        except Exception as exc:
            print(f"WARNING: Could not register PDF font {font_name}: {exc}")
            return None, None

        final_bold = font_bold_name if font_bold_name in pdfmetrics.getRegisteredFontNames() else font_name
        _PDF_FONT_READY[cache_key] = (font_name, final_bold)
        return _PDF_FONT_READY[cache_key]


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
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfbase import pdfmetrics
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import ParagraphStyle
    except Exception as exc:
        raise RuntimeError("Missing dependency: reportlab. Run: pip install -r requirements.txt") from exc

    font_name, font_bold = _ensure_pdf_font_registered()
    if not font_name:
        raise RuntimeError(f"Missing PDF font file: {_config_path('PDF_FONT_PATH')}")
    page_w, page_h = A4
    left = right = 36
    # Leave space for a simple header+footer (logo/title + footer text)
    top = bottom = 72
    content_width = page_w - left - right

    def para(text: str, style: ParagraphStyle) -> Paragraph:
        return Paragraph(_escape_paragraph_text(text), style)

    styles = {
        'title': ParagraphStyle(
            name='LCTitle',
            fontName=font_name,
            shaping=1,
            fontSize=18,
            leading=22,
            spaceAfter=10,
        ),
        'subtitle': ParagraphStyle(
            name='LCSubtitle',
            fontName=font_name,
            shaping=1,
            fontSize=11,
            leading=14,
            textColor=colors.HexColor('#444444'),
            spaceAfter=14,
        ),
        'h2': ParagraphStyle(
            name='LCH2',
            fontName=font_name,
            shaping=1,
            fontSize=13,
            leading=16,
            spaceBefore=10,
            spaceAfter=8,
            textColor=colors.HexColor('#111111'),
        ),
        'normal': ParagraphStyle(
            name='LCNormal',
            fontName=font_name,
            shaping=1,
            fontSize=11,
            leading=14,
            textColor=colors.HexColor('#111111'),
            spaceAfter=6,
        ),
        'muted': ParagraphStyle(
            name='LCMuted',
            fontName=font_name,
            shaping=1,
            fontSize=11,
            leading=14,
            textColor=colors.HexColor('#444444'),
            spaceAfter=6,
        ),
        'cell': ParagraphStyle(
            name='LCCell',
            fontName=font_name,
            shaping=1,
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

    # Prepare logo (optional)
    logo_reader = None
    logo_w = logo_h = 0
    try:
        logo_path = _logo_file_path()
        if logo_path and os.path.exists(logo_path):
            logo_reader = ImageReader(logo_path)
            logo_w, logo_h = logo_reader.getSize()
    except Exception:
        logo_reader = None
        logo_w = logo_h = 0

    def on_page(canvas, doc_):
        canvas.saveState()
        # ----- Header (logo + title) -----
        header_line_y = page_h - top + 12
        header_content_y = page_h - top + 34

        canvas.setStrokeColor(colors.HexColor('#e5e5e5'))
        canvas.setLineWidth(0.8)
        canvas.line(left, header_line_y, page_w - right, header_line_y)

        x = left
        if logo_reader and logo_w and logo_h:
            d = 22
            r = d / 2
            y = header_content_y - r
            # Clip the logo to a circle (like the website avatar)
            canvas.saveState()
            path = canvas.beginPath()
            path.circle(x + r, y + r, r)
            canvas.clipPath(path, stroke=0, fill=0)

            # "Cover" fit: scale to fill the square, then center-crop.
            scale = max(d / float(logo_w), d / float(logo_h))
            dw = logo_w * scale
            dh = logo_h * scale
            dx = x + r - dw / 2
            dy = y + r - dh / 2
            canvas.drawImage(logo_reader, dx, dy, width=dw, height=dh, mask='auto')
            canvas.restoreState()

            # Circle border
            canvas.setStrokeColor(colors.HexColor('#e5e5e5'))
            canvas.setLineWidth(1)
            canvas.circle(x + r, y + r, r, stroke=1, fill=0)
            x = x + d + 10

        canvas.setFillColor(colors.HexColor('#111111'))
        canvas.setFont(font_bold, 10)
        canvas.drawString(x, header_content_y + 4, "Language Coach")

        lang_name = (meta.get('name') or lang or '').strip()
        subtitle = f"{lang_name} · Lesson {lesson_no}"
        canvas.setFillColor(colors.HexColor('#666666'))
        canvas.setFont(font_name, 9)
        canvas.drawString(x, header_content_y - 8, subtitle)

        # Right-side lesson title (truncate a bit so it doesn't wrap)
        right_title = title_en or f"Lesson {lesson_no}"
        right_title = re.sub(r'\s+', ' ', right_title).strip()
        if len(right_title) > 46:
            right_title = right_title[:45].rstrip() + "…"
        canvas.setFillColor(colors.HexColor('#666666'))
        canvas.setFont(font_name, 9)
        canvas.drawRightString(page_w - right, header_content_y - 2, right_title)

        # ----- Footer (website footer text + page number) -----
        footer_line_y = bottom - 18
        canvas.setStrokeColor(colors.HexColor('#e5e5e5'))
        canvas.setLineWidth(0.8)
        canvas.line(left, footer_line_y, page_w - right, footer_line_y)

        year = _app_now().year
        footer_center_x = (left + (page_w - right)) / 2
        canvas.setFillColor(colors.HexColor('#111111'))
        canvas.setFont(font_bold, 9)
        canvas.drawCentredString(footer_center_x, footer_line_y - 12, "Language Coach")
        canvas.setFillColor(colors.HexColor('#666666'))
        canvas.setFont(font_name, 8.5)
        canvas.drawCentredString(footer_center_x, footer_line_y - 24, "mentors.career.abroad26@gmail.com")
        canvas.drawCentredString(footer_center_x, footer_line_y - 35, "An initiative from : Career Abroad Mentor")
        canvas.drawCentredString(footer_center_x, footer_line_y - 46, f"© {year} Ahsan Suny. All rights reserved")

        canvas.setFillColor(colors.HexColor('#666666'))
        canvas.setFont(font_name, 9)
        canvas.drawRightString(page_w - right, 18, f"Page {doc_.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()


_PDF_HTML_ASSET_LOCK = threading.Lock()
_PDF_HTML_ASSET_CACHE = {}


def _file_to_data_uri(path: str, mime: str) -> str:
    with open(path, 'rb') as f:
        b = f.read()
    return f"data:{mime};base64,{base64.b64encode(b).decode('ascii')}"


def _pdf_html_asset(key: str, path: str, mime: str) -> str:
    """Load & cache a small binary asset as a data URI for HTML-to-PDF rendering."""
    cache_key = (key, os.path.abspath(path))
    with _PDF_HTML_ASSET_LOCK:
        cached = _PDF_HTML_ASSET_CACHE.get(cache_key)
        if cached:
            return cached
        if not os.path.exists(path):
            raise RuntimeError(f"Missing PDF asset: {path}")
        data = _file_to_data_uri(path, mime)
        _PDF_HTML_ASSET_CACHE[cache_key] = data
        return data


def _render_lesson_pdf_html(lang: str, meta: dict, lesson: dict, vocabulary: list, grammar: Optional[dict]) -> str:
    bn_font_regular_data = _pdf_html_asset('bn_font_regular', _config_path('PDF_HTML_BN_FONT_REG_PATH'), 'font/ttf')
    bn_font_bold_data = _pdf_html_asset('bn_font_bold', _config_path('PDF_HTML_BN_FONT_BOLD_PATH'), 'font/ttf')
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

    year = _app_now().year
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


def _logo_candidate_paths():
    logo_dir = _config_path('LOGO_DIR')
    return [
        os.path.join(logo_dir, 'Language_Coach_logo.png'),
        os.path.join(logo_dir, 'languagecoach_logo.png'),
        os.path.join(logo_dir, 'AhsanSuny_Logo.png'),
    ]


def _logo_file_path():
    for path in _logo_candidate_paths():
        if os.path.exists(path):
            return path
    return _logo_candidate_paths()[0]


LANG_META = {
    'french':  {'name': 'French',  'name_native': 'Français', 'name_bn': 'ফরাসি',    'flag': '🇫🇷', 'color': '#0055A4'},
    'spanish': {'name': 'Spanish', 'name_native': 'Español',  'name_bn': 'স্প্যানিশ', 'flag': '🇪🇸', 'color': '#c60b1e'},
}

LANGS = list(LANG_META.keys())

def _static_asset_version():
    """Cache-bust static assets (CSS/JS) by appending a version query parameter.

    Prefer `STATIC_VERSION` env var; otherwise derive from file mtimes.
    """
    env = (_config_value('STATIC_VERSION', os.environ.get('STATIC_VERSION') or '') or '').strip()
    if env:
        return env

    static_dir = _config_path('STATIC_DIR')
    paths = [
        os.path.join(static_dir, 'css', 'style.css'),
        os.path.join(static_dir, 'js', 'app.js'),
        *_logo_candidate_paths(),
    ]
    mtimes = []
    for p in paths:
        try:
            mtimes.append(int(os.path.getmtime(p)))
        except OSError:
            pass
    if mtimes:
        return str(max(mtimes))
    return str(int(time.time()))




__all__ = [name for name in globals() if not name.startswith('__')]
