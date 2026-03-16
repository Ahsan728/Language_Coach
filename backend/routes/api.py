from backend.services import *  # noqa: F401,F403


def register_api_routes(app):
    # ---------- API ----------
    _TTS_CLEAN_LOCK = threading.Lock()
    _TTS_CLEAN_RUNNING = False
    _TTS_CLEAN_LAST_TS = 0.0


    def _env_int(name: str, default: int, min_val: int = None, max_val: int = None) -> int:
        raw = os.environ.get(name, None)
        try:
            v = int(raw) if raw is not None and str(raw).strip() != '' else int(default)
        except (TypeError, ValueError):
            v = int(default)
        if min_val is not None:
            v = max(min_val, v)
        if max_val is not None:
            v = min(max_val, v)
        return v


    def _cleanup_tts_cache_dir(cache_dir: str, keep_paths=None) -> dict:
        """Best-effort cleanup for gTTS MP3 cache (size cap + TTL)."""
        keep = {os.path.abspath(p) for p in (keep_paths or []) if p}

        ttl_days = _env_int('TTS_CACHE_TTL_DAYS', 45, min_val=0, max_val=3650)
        max_mb = _env_int('TTS_CACHE_MAX_MB', 80, min_val=0, max_val=4096)
        max_files = _env_int('TTS_CACHE_MAX_FILES', 5000, min_val=0, max_val=500000)
        min_age_sec = _env_int('TTS_CACHE_MIN_AGE_SEC', 120, min_val=0, max_val=86400)

        ttl_sec = ttl_days * 86400
        max_bytes = max_mb * 1024 * 1024

        now = time.time()
        removed = 0
        removed_bytes = 0
        scanned = 0

        if not cache_dir:
            return {'ok': False, 'error': 'missing_cache_dir'}
        if not os.path.isdir(cache_dir):
            return {'ok': True, 'scanned': 0, 'removed': 0, 'removed_bytes': 0}

        entries = []  # [(last_used, size, path)]
        try:
            for ent in os.scandir(cache_dir):
                if not ent.is_file():
                    continue
                scanned += 1
                name = ent.name or ''
                try:
                    st = ent.stat()
                except OSError:
                    continue

                path = ent.path
                if not path:
                    continue
                apath = os.path.abspath(path)
                age = now - float(st.st_mtime or 0.0)

                # Clean up stale temp files if any remain after crashes.
                if name.endswith('.tmp.mp3') or name.endswith('.tmp'):
                    if age >= max(3600, min_age_sec):
                        try:
                            os.remove(apath)
                            removed += 1
                            removed_bytes += int(st.st_size or 0)
                        except OSError:
                            pass
                    continue

                if not name.endswith('.mp3'):
                    continue

                if apath in keep:
                    continue

                last_used = max(float(getattr(st, 'st_atime', 0.0) or 0.0), float(st.st_mtime or 0.0))
                # Avoid deleting files that may be in-flight / very recent.
                if (now - last_used) < min_age_sec:
                    continue

                # TTL delete pass (based on last access when available).
                if ttl_sec and (now - last_used) > ttl_sec:
                    try:
                        os.remove(apath)
                        removed += 1
                        removed_bytes += int(st.st_size or 0)
                    except OSError:
                        pass
                    continue

                entries.append((last_used, int(st.st_size or 0), apath))
        except OSError:
            # Directory vanished or permission issue; just skip.
            return {'ok': False, 'error': 'scan_failed'}

        # Enforce max file count and/or size (delete least-recently-used by last_used).
        if (max_files and len(entries) > max_files) or (max_bytes and sum(s for _, s, __ in entries) > max_bytes):
            entries.sort(key=lambda x: x[0])  # oldest first

            total_bytes = sum(s for _, s, __ in entries)
            i = 0
            while i < len(entries):
                if (max_files and (len(entries) - i) <= max_files) and (not max_bytes or total_bytes <= max_bytes):
                    break
                _, size, path = entries[i]
                try:
                    os.remove(path)
                    removed += 1
                    removed_bytes += int(size or 0)
                    total_bytes -= int(size or 0)
                except OSError:
                    pass
                i += 1

        return {'ok': True, 'scanned': scanned, 'removed': removed, 'removed_bytes': removed_bytes}


    def _trigger_tts_cache_cleanup(cache_dir: str, keep_paths=None) -> None:
        """Rate-limited background cleanup for the TTS cache dir."""
        nonlocal _TTS_CLEAN_RUNNING, _TTS_CLEAN_LAST_TS

        interval = _env_int('TTS_CACHE_CLEANUP_INTERVAL_SEC', 3600, min_val=60, max_val=86400)
        now = time.time()

        with _TTS_CLEAN_LOCK:
            if _TTS_CLEAN_RUNNING:
                return
            if (now - _TTS_CLEAN_LAST_TS) < float(interval):
                return
            _TTS_CLEAN_RUNNING = True

        def _run():
            nonlocal _TTS_CLEAN_RUNNING, _TTS_CLEAN_LAST_TS
            try:
                _cleanup_tts_cache_dir(cache_dir, keep_paths=keep_paths)
            except Exception as exc:
                print(f"WARNING: TTS cache cleanup failed: {exc}")
            finally:
                with _TTS_CLEAN_LOCK:
                    _TTS_CLEAN_LAST_TS = time.time()
                    _TTS_CLEAN_RUNNING = False

        t = threading.Thread(target=_run, daemon=True)
        t.start()


    _PROJECT_DEBUG_CLEAN_LOCK = threading.Lock()
    _PROJECT_DEBUG_CLEAN_RUNNING = False
    _PROJECT_DEBUG_CLEAN_LAST_TS = 0.0


    def _cleanup_project_debug_files(project_root: str) -> dict:
        """Best-effort cleanup for local debug artifacts under the project folder."""
        removed = 0
        removed_bytes = 0

        if not project_root or not os.path.isdir(project_root):
            return {'ok': False, 'error': 'missing_project_root'}

        # Top-level tmp_* artifacts (kept out of git via .gitignore, but can fill server disk).
        try:
            for name in os.listdir(project_root):
                low = (name or '').lower()
                if not low.startswith('tmp_'):
                    continue
                if not (low.endswith('.png') or low.endswith('.pdf')):
                    continue
                path = os.path.join(project_root, name)
                if not os.path.isfile(path):
                    continue
                try:
                    size = int(os.path.getsize(path) or 0)
                except OSError:
                    size = 0
                try:
                    os.remove(path)
                    removed += 1
                    removed_bytes += size
                except OSError:
                    pass
        except OSError:
            pass

        # __pycache__ and *.pyc (project only)
        skip_dirs = {'.git', 'venv', '.venv', 'env', 'node_modules'}
        try:
            for root, dirs, files in os.walk(project_root):
                dirs[:] = [d for d in dirs if d not in skip_dirs]
                if '__pycache__' in dirs:
                    cache_path = os.path.join(root, '__pycache__')
                    try:
                        # Size accounting isn't critical; ignore errors.
                        for dp, __, fnames in os.walk(cache_path):
                            for f in fnames:
                                try:
                                    removed_bytes += int(os.path.getsize(os.path.join(dp, f)) or 0)
                                except OSError:
                                    pass
                    except OSError:
                        pass
                    try:
                        shutil.rmtree(cache_path, ignore_errors=True)
                        removed += 1
                    except OSError:
                        pass
                    try:
                        dirs.remove('__pycache__')
                    except ValueError:
                        pass
                for f in files:
                    if not f.endswith('.pyc'):
                        continue
                    p = os.path.join(root, f)
                    try:
                        size = int(os.path.getsize(p) or 0)
                    except OSError:
                        size = 0
                    try:
                        os.remove(p)
                        removed += 1
                        removed_bytes += size
                    except OSError:
                        pass
        except OSError:
            pass

        return {'ok': True, 'removed': removed, 'removed_bytes': removed_bytes}


    def _trigger_project_debug_cleanup(project_root: str) -> None:
        """Rate-limited background cleanup for project debug artifacts."""
        nonlocal _PROJECT_DEBUG_CLEAN_RUNNING, _PROJECT_DEBUG_CLEAN_LAST_TS

        interval = _env_int('PROJECT_DEBUG_CLEANUP_INTERVAL_SEC', 2592000, min_val=0, max_val=31536000)
        if interval <= 0:
            return

        now = time.time()
        with _PROJECT_DEBUG_CLEAN_LOCK:
            if _PROJECT_DEBUG_CLEAN_RUNNING:
                return
            if (now - _PROJECT_DEBUG_CLEAN_LAST_TS) < float(interval):
                return
            _PROJECT_DEBUG_CLEAN_RUNNING = True

        def _run():
            nonlocal _PROJECT_DEBUG_CLEAN_RUNNING, _PROJECT_DEBUG_CLEAN_LAST_TS
            try:
                _cleanup_project_debug_files(project_root)
            except Exception as exc:
                print(f"WARNING: Project debug cleanup failed: {exc}")
            finally:
                with _PROJECT_DEBUG_CLEAN_LOCK:
                    _PROJECT_DEBUG_CLEAN_LAST_TS = time.time()
                    _PROJECT_DEBUG_CLEAN_RUNNING = False

        t = threading.Thread(target=_run, daemon=True)
        t.start()


    @app.before_request
    def _maybe_run_housekeeping():  # pragma: no cover
        """Run lightweight housekeeping even when Scheduled Tasks are unavailable (free tiers)."""
        try:
            cache_dir = app.config.get('TTS_CACHE_DIR') or TTS_CACHE_DIR
            _trigger_tts_cache_cleanup(cache_dir)
            _trigger_project_debug_cleanup(app.config.get('BASE_DIR') or _config_path('BASE_DIR'))
        except Exception:
            # Never block user requests because of housekeeping.
            return None
        return None


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

        _trigger_tts_cache_cleanup(cache_dir, keep_paths={final_path})
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
        now_iso = _now_iso()
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
        now_iso = _now_iso()

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
        now = _app_now()
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
        today = _today_iso()
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
