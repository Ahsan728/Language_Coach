import os
import json
import random
import sqlite3
from datetime import datetime
from flask import Flask, render_template, jsonify, request, redirect, url_for

app = Flask(__name__)
app.secret_key = 'language_coach_bengali_2024'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DB_PATH  = os.path.join(DATA_DIR, 'progress.db')

# ---------- Load data once at startup ----------
with open(os.path.join(DATA_DIR, 'vocabulary.json'), encoding='utf-8') as f:
    VOCAB = json.load(f)

with open(os.path.join(DATA_DIR, 'lessons.json'), encoding='utf-8') as f:
    LESSONS = json.load(f)

# Initialise DB at import time so gunicorn (production) also creates tables
init_db()

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
    ''')
    conn.commit()
    conn.close()

def load_progress(lang):
    conn = get_db()
    rows = conn.execute(
        'SELECT lesson_id, completed, best_score, attempts FROM lesson_progress WHERE language=?', (lang,)
    ).fetchall()
    conn.close()
    return {r['lesson_id']: dict(r) for r in rows}

# ---------- Helpers ----------
def get_lesson_vocab(lang, lesson):
    words = []
    for cat in lesson.get('vocabulary_categories', []):
        words.extend(VOCAB.get(lang, {}).get(cat, []))
    return words

LANG_META = {
    'french':  {'name': 'French', 'name_bn': 'ফরাসি',   'flag': '🇫🇷', 'color': '#0055A4'},
    'spanish': {'name': 'Spanish','name_bn': 'স্প্যানিশ','flag': '🇪🇸', 'color': '#c60b1e'},
}

# ---------- Routes ----------
@app.route('/')
def dashboard():
    stats = {}
    for lang in ['french', 'spanish']:
        prog = load_progress(lang)
        total     = len(LESSONS.get(lang, []))
        completed = sum(1 for v in prog.values() if v['completed'])
        stats[lang] = {'total': total, 'completed': completed,
                       'percent': int(completed / total * 100) if total else 0}
    return render_template('dashboard.html', stats=stats, lang_meta=LANG_META)

@app.route('/language/<lang>')
def language_home(lang):
    if lang not in LANG_META:
        return redirect(url_for('dashboard'))
    lessons   = LESSONS.get(lang, [])
    progress  = load_progress(lang)
    return render_template('language.html', lang=lang, meta=LANG_META[lang],
                           lessons=lessons, progress=progress)

@app.route('/lesson/<lang>/<int:lesson_id>')
def lesson_view(lang, lesson_id):
    if lang not in LANG_META:
        return redirect(url_for('dashboard'))
    lesson_list = LESSONS.get(lang, [])
    lesson = next((l for l in lesson_list if l['id'] == lesson_id), None)
    if not lesson:
        return redirect(url_for('language_home', lang=lang))

    vocab   = get_lesson_vocab(lang, lesson)
    grammar = lesson.get('grammar')
    # next lesson for navigation
    idx      = next((i for i, l in enumerate(lesson_list) if l['id'] == lesson_id), None)
    next_l   = lesson_list[idx + 1] if idx is not None and idx + 1 < len(lesson_list) else None
    prev_l   = lesson_list[idx - 1] if idx and idx > 0 else None

    return render_template('lesson.html', lang=lang, meta=LANG_META[lang],
                           lesson=lesson, vocabulary=vocab, grammar=grammar,
                           next_lesson=next_l, prev_lesson=prev_l)

@app.route('/flashcards/<lang>/<int:lesson_id>')
def flashcards(lang, lesson_id):
    if lang not in LANG_META:
        return redirect(url_for('dashboard'))
    lesson_list = LESSONS.get(lang, [])
    lesson = next((l for l in lesson_list if l['id'] == lesson_id), None)
    if not lesson:
        return redirect(url_for('language_home', lang=lang))
    vocab = get_lesson_vocab(lang, lesson)
    return render_template('flashcard.html', lang=lang, meta=LANG_META[lang],
                           lesson=lesson, vocabulary=vocab,
                           vocab_json=json.dumps(vocab, ensure_ascii=False))

@app.route('/quiz/<lang>/<int:lesson_id>')
def quiz(lang, lesson_id):
    if lang not in LANG_META:
        return redirect(url_for('dashboard'))
    lesson_list = LESSONS.get(lang, [])
    lesson = next((l for l in lesson_list if l['id'] == lesson_id), None)
    if not lesson:
        return redirect(url_for('language_home', lang=lang))

    vocab = get_lesson_vocab(lang, lesson)
    grammar = lesson.get('grammar')
    questions = []

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
                    'question_en': f"What does <strong>{word['word']}</strong> mean in English?",
                    'question_bn': f"<strong>{word['word']}</strong> ইংরেজিতে কী?",
                    'correct': word['english'],
                    'choices': [word['english']] + [w['english'] for w in wrong],
                }
            elif qtype == 'english_to_word':
                lang_name_bn = 'ফরাসি' if lang == 'french' else 'স্প্যানিশ'
                q = {
                    'question_en': f"How do you say <strong>{word['english']}</strong> in {LANG_META[lang]['name']}?",
                    'question_bn': f"<strong>{word['english']}</strong> {lang_name_bn}তে কীভাবে বলে?",
                    'correct': word['word'],
                    'choices': [word['word']] + [w['word'] for w in wrong],
                }
            else:
                q = {
                    'question_en': f"What does <strong>{word['word']}</strong> mean in Bengali?",
                    'question_bn': f"<strong>{word['word']}</strong> বাংলায় কী?",
                    'correct': word['bengali'],
                    'choices': [word['bengali']] + [w['bengali'] for w in wrong],
                }
            random.shuffle(q['choices'])
            questions.append(q)

    # --- grammar questions (embedded in lesson) ---
    if grammar and grammar.get('quiz_questions'):
        gq = grammar['quiz_questions'][:]
        random.shuffle(gq)
        questions.extend(gq[:5])

    random.shuffle(questions)

    return render_template('quiz.html', lang=lang, meta=LANG_META[lang],
                           lesson=lesson, questions=questions,
                           questions_json=json.dumps(questions, ensure_ascii=False))

@app.route('/progress')
def progress_view():
    all_prog = {}
    for lang in ['french', 'spanish']:
        prog = load_progress(lang)
        lesson_list = LESSONS.get(lang, [])
        enriched = []
        for l in lesson_list:
            p = prog.get(l['id'], {'completed': 0, 'best_score': 0, 'attempts': 0})
            enriched.append({**l, **p})
        all_prog[lang] = enriched
    return render_template('progress.html', progress=all_prog, lang_meta=LANG_META)

# ---------- API ----------
@app.route('/api/complete', methods=['POST'])
def api_complete():
    data      = request.json or {}
    lang      = data.get('language')
    lesson_id = data.get('lesson_id')
    score     = int(data.get('score', 0))
    if not lang or not lesson_id:
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
    conn = get_db()
    if correct:
        conn.execute('''
            INSERT INTO word_progress (language, word, correct) VALUES (?,?,1)
            ON CONFLICT(language, word) DO UPDATE SET correct = correct + 1
        ''', (lang, word))
    else:
        conn.execute('''
            INSERT INTO word_progress (language, word, incorrect) VALUES (?,?,1)
            ON CONFLICT(language, word) DO UPDATE SET incorrect = incorrect + 1
        ''', (lang, word))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

# ---------- Entry point (local dev only) ----------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    # Bind to all interfaces in production (PORT env set by host), localhost otherwise
    host = '0.0.0.0' if os.environ.get('PORT') else '127.0.0.1'
    print()
    print("=" * 55)
    print("  🌍  Language Coach  —  ভাষা শিক্ষক")
    print("=" * 55)
    print(f"  Open your browser:  http://localhost:{port}")
    print("  Press Ctrl+C to stop")
    print("=" * 55)
    print()
    app.run(debug=False, host=host, port=port)
