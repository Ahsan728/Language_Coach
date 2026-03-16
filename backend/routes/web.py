from backend.services import *  # noqa: F401,F403


def register_web_routes(app):
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
            'current_year': _app_now().year,
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
        remember = True if request.method != 'POST' else (str(request.form.get('remember') or '').strip().lower() in {'1', 'true', 'on', 'yes'})
        error = None

        if request.method == 'POST':
            if not _is_valid_email(email):
                error = 'Please enter a valid email address.'
            else:
                user_id = upsert_user(name, email)
                session.permanent = remember
                session['user_id'] = user_id
                user = get_user_by_id(user_id)
                _emit_event_to_sheets('login', user=user, page=_safe_next_url(next_url))
                _emit_user_snapshot_to_sheets(user, last_event='login', page=_safe_next_url(next_url))
                return redirect(_safe_next_url(next_url))

        return render_template('login.html', error=error, next=_safe_next_url(next_url), name=name, email=email, remember=remember)


    @app.route('/logout')
    def logout():
        try:
            session.pop('user_id', None)
        except Exception:
            pass
        return redirect(url_for('dashboard'))


    def _logo_candidate_paths():
        logo_dir = app.config.get('LOGO_DIR') or _config_path('LOGO_DIR')
        return [
            os.path.join(logo_dir, 'Language_Coach_logo.png'),
            os.path.join(logo_dir, 'languagecoach_logo.png'),
            os.path.join(logo_dir, 'AhsanSuny_Logo.png'),
        ]


    def _logo_file_path():
        # Prefer the Language Coach-specific filename, but keep compatibility with the older name.
        for path in _logo_candidate_paths():
            if os.path.exists(path):
                return path
        return _logo_candidate_paths()[0]


    @app.route('/logo.png')
    def logo_png():
        path = _logo_file_path()
        if not os.path.exists(path):
            return ('Missing logo', 404)
        resp = send_file(path, mimetype='image/png', conditional=True)
        resp.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
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
            engine_param = (request.args.get('engine') or '').strip().lower()
            engine = (engine_param or (os.environ.get('PDF_ENGINE') or 'chromium')).strip().lower()
            if engine == 'reportlab':
                pdf_bytes = _build_lesson_pdf_bytes_reportlab(lang, LANG_META[lang], lesson, vocab, grammar)
            else:
                try:
                    html = _render_lesson_pdf_html(lang, LANG_META[lang], lesson, vocab, grammar)
                    header_html, footer_html = _lesson_pdf_header_footer(lang, LANG_META[lang], lesson)
                    pdf_bytes = _build_lesson_pdf_bytes_chromium(html, header_html, footer_html)
                except Exception as exc:
                    # If Chromium/Playwright isn't available (common on some hosts), fall back to ReportLab
                    # unless the user explicitly requested a specific engine in the URL.
                    if engine_param:
                        raise
                    msg = str(exc) or type(exc).__name__
                    lower = msg.lower()
                    if ('playwright' in lower) or ('chromium' in lower) or ('browser is not installed' in lower):
                        pdf_bytes = _build_lesson_pdf_bytes_reportlab(lang, LANG_META[lang], lesson, vocab, grammar)
                    else:
                        raise
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
            now_iso = _now_iso()
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
        now_iso = _now_iso()
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
