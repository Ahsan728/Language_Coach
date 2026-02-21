import os
import json
import random
import re
import sqlite3
import threading
from datetime import datetime, date, timedelta
from flask import Flask, render_template, jsonify, request, redirect, url_for

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'language_coach_dev')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DB_PATH  = os.path.join(DATA_DIR, 'progress.db')

# ---------- Content loading (auto-reload when JSON changes) ----------
VOCAB_PATH = os.path.join(DATA_DIR, 'vocabulary.json')
LESSONS_PATH = os.path.join(DATA_DIR, 'lessons.json')

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
    vocab_data = get_vocab()
    for cat in lesson.get('vocabulary_categories', []):
        words.extend(vocab_data.get(lang, {}).get(cat, []))
    return words

def _sorted_lessons(lesson_list):
    return sorted(lesson_list or [], key=lambda l: l.get('id', 0))


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


@app.context_processor
def inject_globals():
    return {'lang_meta': LANG_META}

# ---------- Routes ----------
@app.route('/')
def dashboard():
    lessons_all = get_lessons()
    activity = get_activity_summary()
    stats = {}
    for lang in LANGS:
        prog = load_progress(lang)
        lesson_list = lessons_all.get(lang, [])
        total = len(lesson_list)
        completed = sum(1 for v in prog.values() if v.get('completed'))
        rec = _recommended_lesson(lesson_list, prog)
        stats[lang] = {'total': total, 'completed': completed,
                       'percent': int(completed / total * 100) if total else 0,
                       'next_lesson': rec,
                       'continue_url': url_for('lesson_view', lang=lang, lesson_id=rec['id']) if rec else url_for('language_home', lang=lang)}
    return render_template('dashboard.html', stats=stats, activity=activity)

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
    vocab = vocab_data.get(category, [])
    if not vocab:
        return redirect(url_for('vocabulary_view', lang=lang))

    title = category.replace('_', ' ').title()
    pseudo_lesson = {'id': 0, 'title_en': f"Category: {title}", 'title_bn': '', 'title_lang': ''}
    return render_template('flashcard.html', lang=lang, meta=LANG_META[lang],
                           lesson=pseudo_lesson, vocabulary=vocab,
                           vocab_json=json.dumps(vocab, ensure_ascii=False),
                           back_url=url_for('vocabulary_view', lang=lang, cat=category),
                           show_quiz_link=False)


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

    vocab_by_cat = get_vocab().get(lang, {})
    vocab_all = [w for words in vocab_by_cat.values() for w in words if w.get('word') and w.get('english')]
    if not vocab_all:
        return redirect(url_for('language_home', lang=lang))

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
        if entry:
            selected.append(entry)

    if len(selected) < total_q:
        pool = [w for w in vocab_all if w['word'] not in {e['word'] for e in selected}]
        random.shuffle(pool)
        selected.extend(pool[: max(0, total_q - len(selected))])

    # Build interactive exercises (Duolingo-like mix: listen, choice, type)
    all_for_wrong = vocab_all[:]
    random.shuffle(all_for_wrong)
    tts_lang = 'fr-FR' if lang == 'french' else 'es-ES'

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
