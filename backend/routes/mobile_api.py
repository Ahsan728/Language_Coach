from datetime import timedelta

from flask import jsonify, request, session, url_for

from backend.services import *  # noqa: F401,F403


def register_mobile_api_routes(app):
    def _request_id():
        return f'req_{uuid.uuid4().hex[:24]}'

    def _error(code: str, message: str, status: int, fields=None):
        payload = {
            'ok': False,
            'error': {
                'code': code,
                'message': message,
                'request_id': _request_id(),
            },
        }
        if fields:
            payload['error']['fields'] = fields
        return jsonify(payload), status

    def _json_body():
        data = request.get_json(silent=True)
        if data is None:
            raw = request.get_data(cache=True) or b''
            if raw.strip():
                return None, _error('validation_error', 'Request body must be valid JSON.', 400)
            return {}, None
        if not isinstance(data, dict):
            return None, _error('validation_error', 'Request body must be a JSON object.', 400)
        return data, None

    def _parse_bool(value, default=False):
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() in {'1', 'true', 'on', 'yes'}
        return default

    def _parse_bearer_token():
        header = (request.headers.get('Authorization') or '').strip()
        if not header:
            return None, None
        parts = header.split(None, 1)
        if len(parts) != 2 or parts[0].lower() != 'bearer' or not parts[1].strip():
            return None, _error('unauthorized', 'Missing or invalid bearer token.', 401)
        return parts[1].strip(), None

    def _api_user(optional=False):
        token, token_error = _parse_bearer_token()
        if token_error:
            return None, None, token_error

        if token:
            api_session = get_api_session(token, touch=True)
            if not api_session:
                return None, None, _error('unauthorized', 'Missing or invalid bearer token.', 401)
            user = get_user_by_id(api_session['user_id'])
            if not user:
                revoke_api_session(token)
                return None, None, _error('unauthorized', 'Missing or invalid bearer token.', 401)
            return user, token, None

        if optional:
            return None, None, None
        return None, None, _error('unauthorized', 'Missing or invalid bearer token.', 401)

    def _user_payload(user):
        return {
            'id': int(user['id']),
            'name': (user.get('name') or '').strip(),
            'email': (user.get('email') or '').strip(),
            'created_at': to_rfc3339(user.get('created_at')),
            'last_login': to_rfc3339(user.get('last_login')),
        }

    def _language_payload(language: str):
        lessons = _sorted_lessons(get_lessons().get(language, []) or [])
        vocab_by_cat = get_vocab().get(language, {}) or {}
        meta = LANG_META[language]
        return {
            'id': language,
            'name': meta['name'],
            'name_native': meta['name_native'],
            'name_bn': meta['name_bn'],
            'flag': meta['flag'],
            'color': meta['color'],
            'lesson_count': len(lessons),
            'vocabulary_category_count': len(vocab_by_cat),
            'vocabulary_word_count': sum(len(words or []) for words in vocab_by_cat.values()),
        }

    def _lesson_progress_payload(progress):
        progress = progress or {}
        return {
            'completed': bool(progress.get('completed')),
            'best_score': int(progress.get('best_score') or 0),
            'attempts': int(progress.get('attempts') or 0),
            'last_seen': to_rfc3339(progress.get('last_seen')),
        }

    def _lesson_summary_payload(lesson, progress=None):
        payload = {
            'id': int(lesson['id']),
            'cefr_level': (lesson.get('cefr_level') or lesson.get('level') or '').strip(),
            'icon': lesson.get('icon'),
            'title_en': lesson.get('title_en'),
            'title_bn': lesson.get('title_bn'),
            'title_lang': lesson.get('title_lang'),
            'description_en': lesson.get('description_en'),
            'description_bn': lesson.get('description_bn'),
            'tip_en': lesson.get('tip_en'),
            'tip_bn': lesson.get('tip_bn'),
            'activity': lesson.get('activity'),
            'vocabulary_categories': list(lesson.get('vocabulary_categories') or []),
            'has_grammar': bool(lesson.get('grammar')),
        }
        if progress is not None:
            payload['progress'] = _lesson_progress_payload(progress)
        return payload

    def _vocabulary_item_payload(item, category):
        return {
            'word': item.get('word'),
            'article': item.get('article'),
            'english': item.get('english'),
            'bengali': item.get('bengali'),
            'pronunciation': item.get('pronunciation'),
            'example': item.get('example'),
            'example_en': item.get('example_en'),
            'example_bn': item.get('example_bn'),
            'category': category,
        }

    def _language_lessons_or_404(language: str):
        if language not in LANG_META:
            return None, _error('not_found', 'Unknown language.', 404)
        lessons = _sorted_lessons(get_lessons().get(language, []) or [])
        return lessons, None

    def _find_lesson_or_404(language: str, lesson_id: int):
        lessons, language_error = _language_lessons_or_404(language)
        if language_error:
            return None, None, language_error
        lesson = _find_lesson(lessons, lesson_id)
        if not lesson:
            return lessons, None, _error('not_found', 'Unknown lesson.', 404)
        return lessons, lesson, None

    def _parse_non_negative_int(value, field_name, default, minimum=0, maximum=None):
        if value in (None, ''):
            return default, None
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None, _error(
                'validation_error',
                f'Invalid {field_name}.',
                400,
                fields={field_name: 'invalid'},
            )
        if parsed < minimum:
            parsed = minimum
        if maximum is not None:
            parsed = min(parsed, maximum)
        return parsed, None

    @app.route('/api/v1/auth/session', methods=['POST'])
    def api_v1_auth_session_create():
        data, body_error = _json_body()
        if body_error:
            return body_error

        email = _normalize_email(data.get('email') or '')
        name = (data.get('name') or '').strip()
        remember_me = _parse_bool(data.get('remember_me'), default=True)

        if not _is_valid_email(email):
            return _error(
                'validation_error',
                'Please enter a valid email address.',
                422,
                fields={'email': 'invalid'},
            )

        user_id = upsert_user(name, email)

        lifetime = app.permanent_session_lifetime if remember_me else timedelta(days=1)
        api_session = create_api_session(user_id, lifetime)
        user = get_user_by_id(user_id)

        _emit_event_to_sheets('login', user=user, page=url_for('api_v1_auth_session_create'))
        _emit_user_snapshot_to_sheets(user, last_event='login', page=url_for('api_v1_auth_session_create'))

        return jsonify(
            {
                'ok': True,
                'auth_mode': 'email_only_unverified',
                'access_token': api_session['access_token'],
                'token_type': 'Bearer',
                'expires_at': api_session['expires_at'],
                'user': _user_payload(user),
            }
        )

    @app.route('/api/v1/auth/session', methods=['DELETE'])
    def api_v1_auth_session_delete():
        user, token, auth_error = _api_user(optional=False)
        if auth_error:
            return auth_error

        if token:
            revoke_api_session(token)
        if user:
            session.pop('user_id', None)

        return jsonify({'ok': True})

    @app.route('/api/v1/me')
    def api_v1_me():
        user, _, auth_error = _api_user(optional=False)
        if auth_error:
            return auth_error
        return jsonify({'ok': True, 'user': _user_payload(user)})

    @app.route('/api/v1/languages')
    def api_v1_languages():
        return jsonify(
            {
                'ok': True,
                'languages': [_language_payload(language) for language in LANGS],
            }
        )

    @app.route('/api/v1/languages/<language>/lessons')
    def api_v1_language_lessons(language):
        lessons, language_error = _language_lessons_or_404(language)
        if language_error:
            return language_error

        user, _, auth_error = _api_user(optional=True)
        if auth_error:
            return auth_error

        progress = load_progress(language, user_id=user['id']) if user else {}
        recommended = _recommended_lesson(lessons, progress)
        lesson_payloads = []
        for lesson in lessons:
            lesson_progress = progress.get(lesson['id'], {}) if user else None
            lesson_payloads.append(_lesson_summary_payload(lesson, lesson_progress))

        return jsonify(
            {
                'ok': True,
                'language': language,
                'recommended_lesson_id': int(recommended['id']) if recommended else None,
                'lessons': lesson_payloads,
            }
        )

    @app.route('/api/v1/languages/<language>/lessons/<int:lesson_id>/touch', methods=['POST'])
    def api_v1_lesson_touch(language, lesson_id):
        _, lesson, lookup_error = _find_lesson_or_404(language, lesson_id)
        if lookup_error:
            return lookup_error

        user, _, auth_error = _api_user(optional=False)
        if auth_error:
            return auth_error

        last_seen = touch_lesson(language, int(lesson['id']), user_id=user['id'])
        return jsonify({'ok': True, 'last_seen': to_rfc3339(last_seen)})

    @app.route('/api/v1/languages/<language>/vocabulary')
    def api_v1_vocabulary(language):
        if language not in LANG_META:
            return _error('not_found', 'Unknown language.', 404)

        vocab_by_cat = get_vocab().get(language, {}) or {}
        category = (request.args.get('category') or 'all').strip()
        limit, limit_error = _parse_non_negative_int(request.args.get('limit'), 'limit', 60, minimum=1, maximum=200)
        if limit_error:
            return limit_error
        offset, offset_error = _parse_non_negative_int(request.args.get('offset'), 'offset', 0, minimum=0)
        if offset_error:
            return offset_error

        if category != 'all' and category not in vocab_by_cat:
            return _error('not_found', 'Unknown vocabulary category.', 404)

        categories = [
            {
                'id': cat,
                'label': cat.replace('_', ' ').title(),
                'count': len(words or []),
            }
            for cat, words in vocab_by_cat.items()
        ]
        categories.sort(key=lambda item: (-item['count'], item['id']))

        if category == 'all':
            selected_categories = categories
            items = []
            for cat, words in vocab_by_cat.items():
                for item in words or []:
                    items.append(_vocabulary_item_payload(item, cat))
        else:
            selected_categories = [item for item in categories if item['id'] == category]
            items = [_vocabulary_item_payload(item, category) for item in (vocab_by_cat.get(category) or [])]

        total = len(items)
        paged_items = items[offset: offset + limit]

        return jsonify(
            {
                'ok': True,
                'language': language,
                'category': category,
                'offset': offset,
                'limit': limit,
                'total': total,
                'categories': selected_categories,
                'items': paged_items,
            }
        )

    @app.route('/api/v1/progress')
    def api_v1_progress():
        user, _, auth_error = _api_user(optional=False)
        if auth_error:
            return auth_error

        include_raw = (request.args.get('include') or '').strip()
        includes = {part.strip() for part in include_raw.split(',') if part.strip()}
        include_lessons = not includes or 'lessons' in includes

        lessons_all = get_lessons()
        languages_payload = {}
        lessons_payload = {}
        for language in LANGS:
            lesson_list = _sorted_lessons(lessons_all.get(language, []) or [])
            progress = load_progress(language, user_id=user['id'])
            completed = sum(1 for item in progress.values() if item.get('completed'))
            recommended = _recommended_lesson(lesson_list, progress)
            languages_payload[language] = {
                'completed': completed,
                'total': len(lesson_list),
                'percent': int(completed / len(lesson_list) * 100) if lesson_list else 0,
                'recommended_lesson_id': int(recommended['id']) if recommended else None,
                'last_seen_lesson_id': _last_seen_lesson_id(progress),
            }

            if include_lessons:
                lessons_payload[language] = [
                    {
                        'lesson_id': int(item['lesson_id']),
                        'completed': bool(item['completed']),
                        'best_score': int(item.get('best_score') or 0),
                        'attempts': int(item.get('attempts') or 0),
                        'last_seen': to_rfc3339(item.get('last_seen')),
                    }
                    for item in sorted(progress.values(), key=lambda row: int(row['lesson_id']))
                ]

        payload = {
            'ok': True,
            'today': get_activity_summary(user_id=user['id']),
            'languages': languages_payload,
        }
        if include_lessons:
            payload['lessons'] = lessons_payload
        return jsonify(payload)
