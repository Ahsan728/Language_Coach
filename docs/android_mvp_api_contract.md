# Language Coach Android MVP API Contract

## Purpose

This document defines the minimum JSON API surface for a future Android app, based on the current Flask web application.

It is grounded in:

- `app.py` for routing, persistence, auth, TTS, translation, feedback, placement, quiz, practice, review, and progress logic
- `static/js/app.js` for current browser-side scoring and progress mutations
- `data/lessons.json` for lesson and grammar content
- `data/vocabulary.json` for vocabulary categories and word records

## Current codebase facts that shape the contract

- Supported target languages are `french` and `spanish`.
- Each language currently has `50` lessons.
- Each language currently has `28` vocabulary categories.
- Vocabulary totals are currently `4394` French words and `4120` Spanish words.
- Web login is email-only, with no password and no email verification.
- The web app currently exposes JSON endpoints only for TTS, translation, lesson completion, feedback, and word progress.
- Lesson, placement, quiz, flashcards, dictation, speaking, practice, review, and progress are still rendered as HTML pages.
- Anonymous progress is currently written into shared SQLite tables (`lesson_progress`, `word_progress`, `daily_activity`), which is acceptable for the browser demo but not safe for Android sync.
- Current browser quiz and placement flows expose correct answers to the client and score locally. The Android contract should move scoring server-side.

## Contract goals

The Android MVP API should:

1. Reuse the existing lesson, grammar, vocabulary, placement, quiz, practice, review, progress, feedback, translation, and TTS logic.
2. Keep payloads close to the current JSON/content model in `app.py`, `lessons.json`, and `vocabulary.json`.
3. Stop relying on HTML scraping or browser-only behavior.
4. Require authentication for user-specific progress writes and reads.
5. Version new mobile endpoints under `/api/v1`.

## Auth expectations

### Current behavior

- The current web app uses Flask session cookies.
- Login is done by posting `name`, `email`, and `remember` to `/login`.
- The server creates or updates a user record by email and stores `session['user_id']`.

### Android MVP expectation

- Android should use `Authorization: Bearer <token>`.
- The backend may continue setting Flask cookies for the web app, but mobile should not depend on cookie storage.
- MVP can preserve the current email-only identity model for parity, but the API should make that explicit.
- All Android MVP progress reads and writes should require auth.
- Any endpoint that reads or writes lesson progress, word progress, review state, streak, daily activity, or unlocked-content state should require auth.
- Read-only catalog endpoints may remain public.

### Required auth endpoints

#### `POST /api/v1/auth/session`

Create a mobile session from the current email-only login flow.

Auth: none.

Request:

```json
{
  "email": "learner@example.com",
  "name": "Learner Name",
  "remember_me": true
}
```

Response `200`:

```json
{
  "ok": true,
  "auth_mode": "email_only_unverified",
  "access_token": "opaque-or-jwt-token",
  "token_type": "Bearer",
  "expires_at": "2026-04-14T22:30:00Z",
  "user": {
    "id": 12,
    "name": "Learner Name",
    "email": "learner@example.com",
    "created_at": "2026-03-10T09:12:11Z",
    "last_login": "2026-03-15T22:30:00Z"
  }
}
```

Notes:

- Validation should match the current `_is_valid_email()` behavior.
- If `name` is blank, preserve the current fallback behavior and derive it from the email local-part.

#### `GET /api/v1/me`

Auth: required.

Response `200`:

```json
{
  "ok": true,
  "user": {
    "id": 12,
    "name": "Learner Name",
    "email": "learner@example.com",
    "created_at": "2026-03-10T09:12:11Z",
    "last_login": "2026-03-15T22:30:00Z"
  }
}
```

#### `DELETE /api/v1/auth/session`

Auth: required.

Response `200`:

```json
{
  "ok": true
}
```

## API conventions

- Base path: `/api/v1`
- Content type: `application/json` except successful TTS responses, which return `audio/mpeg`
- Field style: `snake_case`
- Language ids: `french`, `spanish`
- CEFR values: `A1`, `A2`, `B1`, `B2`
- Timestamps: return RFC 3339 strings with timezone offset or `Z`
- Paging:
  - `limit` and `offset` for vocabulary lists
  - server should clamp inputs the same way the current app clamps `n` values

## Error model

Current endpoints mix plain-text and JSON failures. `/api/v1` should standardize on this JSON error envelope:

```json
{
  "ok": false,
  "error": {
    "code": "validation_error",
    "message": "Please enter a valid email address.",
    "fields": {
      "email": "invalid"
    },
    "request_id": "req_01HZZ..."
  }
}
```

Recommended status codes:

- `400` malformed JSON or invalid query/body values
- `401` missing or invalid bearer token
- `403` authenticated but not allowed
- `404` unknown language, lesson, session, or resource
- `409` duplicate or stale submission
- `422` semantically invalid input
- `429` rate-limited translation/TTS requests
- `500` unexpected server error
- `501` feature disabled on the server, matching current TTS behavior when disabled

## Core resource shapes

### Language

```json
{
  "id": "french",
  "name": "French",
  "name_native": "Francais/Français",
  "name_bn": "French in Bangla label",
  "flag": "current LANG_META flag string",
  "color": "#0055A4",
  "lesson_count": 50,
  "vocabulary_category_count": 28,
  "vocabulary_word_count": 4394
}
```

### Lesson summary

```json
{
  "id": 12,
  "cefr_level": "A1",
  "icon": "icon-key",
  "title_en": "Greetings and Introductions",
  "title_bn": "Bangla title",
  "title_lang": "Bonjour et salutations",
  "description_en": "Lesson description",
  "description_bn": "Bangla description",
  "tip_en": "Tip text",
  "tip_bn": "Bangla tip",
  "activity": null,
  "vocabulary_categories": [
    "greetings",
    "family"
  ],
  "has_grammar": true,
  "progress": {
    "completed": true,
    "best_score": 80,
    "attempts": 2,
    "last_seen": "2026-03-15T22:01:00Z"
  }
}
```

Notes:

- `activity` currently appears only on some lessons and is optional.
- `progress` is returned only for authenticated requests.

### Grammar block

```json
{
  "intro_en": "Grammar intro",
  "intro_bn": "Bangla intro",
  "sections": [
    {
      "title_en": "Section title",
      "title_bn": "Bangla title",
      "table": [
        ["Column 1", "Column 2"],
        ["Value 1", "Value 2"]
      ],
      "note_en": "Optional note",
      "note_bn": "Optional Bangla note"
    }
  ]
}
```

### Vocabulary item

```json
{
  "word": "bonjour",
  "article": null,
  "english": "hello / good morning",
  "bengali": "Bangla gloss",
  "pronunciation": "bohn-ZHOOR",
  "example": "Bonjour! Comment allez-vous?",
  "example_en": "Hello! How are you?",
  "example_bn": "Bangla example",
  "category": "greetings"
}
```

### Study question

Use one normalized shape for placement, quiz, and practice fetch responses.

```json
{
  "question_id": "q_001",
  "kind": "mcq",
  "mode": "word_to_english",
  "mode_label": "Choose",
  "category": "vocab",
  "cefr": "A1",
  "prompt": {
    "en": "What does \"bonjour\" mean in English?",
    "bn": "Bangla prompt"
  },
  "choices": [
    "hello",
    "goodbye",
    "thank you",
    "please"
  ],
  "tokens": null,
  "hint_bn": null,
  "tts": {
    "text": "bonjour",
    "lang_tag": "fr-FR"
  },
  "track_word": "bonjour"
}
```

Rules:

- `kind` is one of `mcq`, `type`, `order`
- `choices` is present only for `mcq`
- `tokens` is present only for `order`
- `hint_bn` is mainly for `type`
- `cefr` is required for placement questions and optional elsewhere
- Do not return the correct answer in fetch responses

### Word review event

This is the mobile replacement for the current `/api/word_progress`.

```json
{
  "language": "french",
  "word": "bonjour",
  "correct": true,
  "source": "practice",
  "xp": 10,
  "occurred_at": "2026-03-15T22:11:00Z"
}
```

Server behavior should preserve the current SRS rules:

- correct answer: increment `correct`, advance `box` by 1 up to `5`
- wrong answer: increment `incorrect`, reset `box` to `1`
- correct review due dates follow the current boxes in `app.py`
- wrong review due date is `6` hours later
- XP should update daily activity and streak counters

## Canonical progress update model

Android MVP uses one write rule throughout the contract:

1. Any study flow with a dedicated `/submit` endpoint must be scored server-side. If the flow affects progress, it must also persist those changes inside that same submit call.
2. The client must not call `/api/v1/progress/word_events` for answers that were already submitted through a session `/submit` endpoint.
3. `/api/v1/progress/word_events` is only for MVP activities that do not have a dedicated submit endpoint: flashcards and review.
4. Placement submit is server-scored but does not write lesson completion, word SRS, or daily XP progress.
5. `POST /api/v1/languages/{lang}/lessons/{lesson_id}/touch` is the only standalone lesson-progress write outside session submit.

## Endpoint inventory

### 1. Languages and lessons

#### `GET /api/v1/languages`

Auth: none.

Response `200`:

```json
{
  "ok": true,
  "languages": [
    {
      "id": "french",
      "name": "French",
      "name_native": "Francais/Français",
      "name_bn": "Bangla label",
      "flag": "current LANG_META flag string",
      "color": "#0055A4",
      "lesson_count": 50,
      "vocabulary_category_count": 28,
      "vocabulary_word_count": 4394
    },
    {
      "id": "spanish",
      "name": "Spanish",
      "name_native": "Espanol/Español",
      "name_bn": "Bangla label",
      "flag": "current LANG_META flag string",
      "color": "#c60b1e",
      "lesson_count": 50,
      "vocabulary_category_count": 28,
      "vocabulary_word_count": 4120
    }
  ]
}
```

#### `GET /api/v1/languages/{lang}/lessons`

Auth: optional, but include user progress only when authenticated.

Response `200`:

```json
{
  "ok": true,
  "language": "french",
  "recommended_lesson_id": 12,
  "lessons": [
    {
      "id": 12,
      "cefr_level": "A1",
      "icon": "icon-key",
      "title_en": "Greetings and Introductions",
      "title_bn": "Bangla title",
      "title_lang": "Bonjour et salutations",
      "description_en": "Lesson description",
      "description_bn": "Bangla description",
      "tip_en": "Tip text",
      "tip_bn": "Bangla tip",
      "activity": null,
      "vocabulary_categories": ["greetings"],
      "has_grammar": true,
      "progress": {
        "completed": false,
        "best_score": 0,
        "attempts": 0,
        "last_seen": "2026-03-15T22:01:00Z"
      }
    }
  ]
}
```

#### `GET /api/v1/languages/{lang}/lessons/{lesson_id}`

Auth: required for parity with the current web lesson route.

Response `200`:

```json
{
  "ok": true,
  "language": "french",
  "lesson": {
    "id": 12,
    "cefr_level": "A1",
    "icon": "icon-key",
    "title_en": "Greetings and Introductions",
    "title_bn": "Bangla title",
    "title_lang": "Bonjour et salutations",
    "description_en": "Lesson description",
    "description_bn": "Bangla description",
    "tip_en": "Tip text",
    "tip_bn": "Bangla tip",
    "activity": null,
    "vocabulary_categories": ["greetings"],
    "grammar": {
      "intro_en": "Grammar intro",
      "intro_bn": "Bangla intro",
      "sections": []
    },
    "vocabulary": [
      {
        "word": "bonjour",
        "article": null,
        "english": "hello / good morning",
        "bengali": "Bangla gloss",
        "pronunciation": "bohn-ZHOOR",
        "example": "Bonjour! Comment allez-vous?",
        "example_en": "Hello! How are you?",
        "example_bn": "Bangla example",
        "category": "greetings"
      }
    ],
    "tts_lang_tag": "fr-FR",
    "progress": {
      "completed": false,
      "best_score": 0,
      "attempts": 0,
      "last_seen": "2026-03-15T22:01:00Z"
    },
    "previous_lesson_id": 11,
    "next_lesson_id": 13
  }
}
```

#### `POST /api/v1/languages/{lang}/lessons/{lesson_id}/touch`

Auth: required.

Record `last_seen` without marking completion. This mirrors the current `touch_lesson()` calls when users open lessons, quizzes, and flashcards. Future non-MVP dictation/speaking flows would reuse the same rule if added later.

Response `200`:

```json
{
  "ok": true,
  "last_seen": "2026-03-15T22:15:00Z"
}
```

### 2. Vocabulary

#### `GET /api/v1/languages/{lang}/vocabulary`

Auth: none.

Query params:

- `category` optional, default `all`
- `limit` optional, default `60`
- `offset` optional, default `0`

Response `200`:

```json
{
  "ok": true,
  "language": "french",
  "category": "greetings",
  "offset": 0,
  "limit": 60,
  "total": 160,
  "categories": [
    {
      "id": "greetings",
      "label": "Greetings",
      "count": 160
    }
  ],
  "items": [
    {
      "word": "bonjour",
      "article": null,
      "english": "hello / good morning",
      "bengali": "Bangla gloss",
      "pronunciation": "bohn-ZHOOR",
      "example": "Bonjour! Comment allez-vous?",
      "example_en": "Hello! How are you?",
      "example_bn": "Bangla example",
      "category": "greetings"
    }
  ]
}
```

### 3. Placement

The current placement test is generated from lesson grammar, lesson vocabulary, curated extras, and sentence-order tasks. The current browser result rule recommends the first CEFR level whose score is below `65%`; otherwise it recommends `B2`.

#### `POST /api/v1/languages/{lang}/placement/sessions`

Auth: required, matching the current `/placement/{lang}` route.

Request:

```json
{
  "questions_per_level": 10
}
```

Response `201`:

```json
{
  "ok": true,
  "session_id": "place_01",
  "language": "french",
  "questions_per_level": 10,
  "question_count": 40,
  "questions": [
    {
      "question_id": "q_001",
      "kind": "mcq",
      "mode": "placement",
      "mode_label": "Placement A1 Grammar",
      "category": "placement",
      "cefr": "A1",
      "prompt": {
        "en": "Choose the correct French for: Good evening.",
        "bn": "Bangla prompt"
      },
      "choices": ["Bonjour", "Bonsoir", "Bonne nuit", "Salut"],
      "tokens": null,
      "hint_bn": null,
      "tts": {
        "text": null,
        "lang_tag": "fr-FR"
      },
      "track_word": null
    }
  ]
}
```

#### `POST /api/v1/languages/{lang}/placement/sessions/{session_id}/submit`

Auth: required.

Request:

```json
{
  "answers": [
    {
      "question_id": "q_001",
      "answer": "Bonsoir"
    }
  ]
}
```

Notes:

- This endpoint is server-scored.
- It returns a recommendation only and does not write lesson completion, word progress, or daily activity.

Response `200`:

```json
{
  "ok": true,
  "language": "french",
  "overall_pct": 72,
  "recommended_level": "A2",
  "recommended_lesson_id": 17,
  "breakdown": {
    "A1": {
      "correct": 8,
      "total": 10,
      "pct": 80
    },
    "A2": {
      "correct": 7,
      "total": 10,
      "pct": 70
    },
    "B1": {
      "correct": 5,
      "total": 10,
      "pct": 50
    },
    "B2": {
      "correct": 4,
      "total": 10,
      "pct": 40
    }
  }
}
```

### 4. Lesson quiz

The current lesson quiz mixes:

- vocabulary MCQs built from lesson vocabulary
- grammar MCQs from `lesson.grammar.quiz_questions`

#### `POST /api/v1/languages/{lang}/lessons/{lesson_id}/quiz_sessions`

Auth: required, matching the current lesson quiz route.

Response `201`:

```json
{
  "ok": true,
  "session_id": "quiz_01",
  "language": "french",
  "lesson_id": 12,
  "question_count": 12,
  "questions": [
    {
      "question_id": "q_001",
      "kind": "mcq",
      "mode": "word_to_english",
      "mode_label": "Quiz",
      "category": "vocab",
      "cefr": "A1",
      "prompt": {
        "en": "What does \"bonjour\" mean in English?",
        "bn": "Bangla prompt"
      },
      "choices": ["hello", "goodbye", "please", "thank you"],
      "tokens": null,
      "hint_bn": null,
      "tts": {
        "text": "bonjour",
        "lang_tag": "fr-FR"
      },
      "track_word": "bonjour"
    }
  ]
}
```

#### `POST /api/v1/languages/{lang}/quiz_sessions/{session_id}/submit`

Auth: required.

Request:

```json
{
  "answers": [
    {
      "question_id": "q_001",
      "answer": "hello"
    }
  ]
}
```

Response `200`:

```json
{
  "ok": true,
  "language": "french",
  "lesson_id": 12,
  "progress_applied": true,
  "score_pct": 83,
  "correct_count": 10,
  "wrong_count": 2,
  "completion": {
    "completed": true,
    "best_score": 83,
    "attempts": 3,
    "last_seen": "2026-03-15T22:20:00Z"
  },
  "next_lesson_id": 13,
  "word_updates": [
    {
      "word": "bonjour",
      "box": 3,
      "next_due": "2026-03-19T22:20:00Z",
      "correct": 5,
      "incorrect": 1
    }
  ],
  "activity_today": {
    "xp_today": 88,
    "reviews_today": 12,
    "correct_today": 9,
    "wrong_today": 3,
    "streak_days": 6
  }
}
```

Notes:

- The backend should preserve the current lesson completion rule from `/api/complete`: mark the lesson completed, increment attempts, and keep the max best score.
- This endpoint is the canonical write for quiz results. The Android client must not send a second `/api/v1/progress/word_events` call for the same quiz answers.

### 5. Practice

Current daily practice builds a mixed question set from unlocked vocabulary, due SRS words, and optional resource sentences. The generated question modes currently include:

- `listen_to_english`
- `word_to_english`
- `english_to_word`
- `type_english_to_word`
- `order_sentence`
- `context_cloze`

#### `POST /api/v1/languages/{lang}/practice_sessions`

Auth: required. This endpoint depends on authenticated progress to choose due words, unlocked vocabulary, and recommendation-aware content.

Request:

```json
{
  "question_count": 12,
  "mode": "default"
}
```

`mode` values:

- `default`
- `resources` when `data/resource_sentences.json` exists and the backend allows it

Response `201`:

```json
{
  "ok": true,
  "session_id": "practice_01",
  "language": "french",
  "question_count": 12,
  "resource_mode_available": true,
  "questions": [
    {
      "question_id": "q_001",
      "kind": "mcq",
      "mode": "listen_to_english",
      "mode_label": "Listening",
      "category": "practice",
      "cefr": null,
      "prompt": {
        "en": "Listen and choose the correct meaning (English)",
        "bn": "Bangla prompt"
      },
      "choices": ["hello", "goodbye", "please", "thank you"],
      "tokens": null,
      "hint_bn": null,
      "tts": {
        "text": "bonjour",
        "lang_tag": "fr-FR"
      },
      "track_word": "bonjour"
    }
  ]
}
```

#### `POST /api/v1/languages/{lang}/practice_sessions/{session_id}/submit`

Auth: required.

Request:

```json
{
  "answers": [
    {
      "question_id": "q_001",
      "answer": "hello"
    }
  ]
}
```

Response `200`:

```json
{
  "ok": true,
  "language": "french",
  "progress_applied": true,
  "correct_count": 9,
  "wrong_count": 3,
  "xp_earned": 96,
  "word_updates": [
    {
      "word": "bonjour",
      "box": 3,
      "next_due": "2026-03-19T22:25:00Z",
      "correct": 5,
      "incorrect": 1
    }
  ],
  "activity_today": {
    "xp_today": 140,
    "reviews_today": 18,
    "correct_today": 14,
    "wrong_today": 4,
    "streak_days": 6
  }
}
```

Notes:

- This endpoint is the canonical write for practice results.
- The Android client must not send a second `/api/v1/progress/word_events` call for the same practice answers.

### 6. Review

The current review page supports:

- `due` review from SRS due words
- `weak` review from high-mistake words
- random fallback when there is no history

#### `POST /api/v1/languages/{lang}/review_sessions`

Auth: required. If anonymous review is ever allowed on Android, it should be device-local only, not stored in shared server tables.

Request:

```json
{
  "mode": "due",
  "limit": 40
}
```

Response `201`:

```json
{
  "ok": true,
  "session_id": "review_01",
  "language": "french",
  "mode": "due",
  "subtitle": "Due words (spaced repetition)",
  "items": [
    {
      "word": "bonjour",
      "article": null,
      "english": "hello / good morning",
      "bengali": "Bangla gloss",
      "pronunciation": "bohn-ZHOOR",
      "example": "Bonjour! Comment allez-vous?",
      "example_en": "Hello! How are you?",
      "example_bn": "Bangla example",
      "category": "greetings",
      "review_state": {
        "box": 2,
        "next_due": "2026-03-15T22:30:00Z",
        "correct": 3,
        "incorrect": 1
      }
    }
  ]
}
```

#### `POST /api/v1/progress/word_events`

Auth: required.

This endpoint is the minimum write surface for Android MVP flashcards and review only. It is not used after quiz or practice submit, because those submit endpoints already persist progress server-side.

Request:

```json
{
  "events": [
    {
      "language": "french",
      "word": "bonjour",
      "correct": true,
      "source": "review",
      "xp": 5
    },
    {
      "language": "french",
      "word": "merci",
      "correct": false,
      "source": "flashcards",
      "xp": 2
    }
  ]
}
```

Response `200`:

```json
{
  "ok": true,
  "updated": [
    {
      "word": "bonjour",
      "box": 3,
      "next_due": "2026-03-19T22:32:00Z",
      "correct": 4,
      "incorrect": 1
    },
    {
      "word": "merci",
      "box": 1,
      "next_due": "2026-03-16T04:32:00Z",
      "correct": 2,
      "incorrect": 3
    }
  ],
  "activity_today": {
    "xp_today": 147,
    "reviews_today": 20,
    "correct_today": 15,
    "wrong_today": 5,
    "streak_days": 6
  }
}
```

Notes:

- This preserves the current `/api/word_progress` data model but batches writes for mobile efficiency.
- The backend should still accept single-event payloads if the Android client wants fire-and-forget behavior.
- Allowed MVP `source` values are `flashcards` and `review`.
- Dictation and speaking are not part of Android MVP and should not write through this contract yet.

### 7. Progress

#### `GET /api/v1/progress`

Auth: required.

Query params:

- `include=summary,lessons` optional

Response `200`:

```json
{
  "ok": true,
  "today": {
    "xp_today": 147,
    "reviews_today": 20,
    "correct_today": 15,
    "wrong_today": 5,
    "streak_days": 6
  },
  "languages": {
    "french": {
      "completed": 12,
      "total": 50,
      "percent": 24,
      "recommended_lesson_id": 13,
      "last_seen_lesson_id": 12
    },
    "spanish": {
      "completed": 2,
      "total": 50,
      "percent": 4,
      "recommended_lesson_id": 3,
      "last_seen_lesson_id": 2
    }
  },
  "lessons": {
    "french": [
      {
        "lesson_id": 12,
        "completed": true,
        "best_score": 83,
        "attempts": 3,
        "last_seen": "2026-03-15T22:20:00Z"
      }
    ]
  }
}
```

### 8. Feedback

The current endpoint requires `name`, `email`, and `message`, even when the user is logged in. For Android MVP, keep the same request shape for parity, but allow the backend to ignore `name` and `email` when auth is present and a canonical user record exists.

#### `POST /api/v1/feedback`

Auth: optional. If auth is present, the backend should prefer the canonical stored user identity. If auth is absent, the request must include valid `name` and `email`.

Request:

```json
{
  "name": "Learner Name",
  "email": "learner@example.com",
  "category": "bug",
  "language": "french",
  "message": "Audio did not play on lesson 12.",
  "page": "lesson_detail"
}
```

Response `200`:

```json
{
  "ok": true,
  "feedback_id": 123,
  "sheets": {
    "enabled": true,
    "ok": true,
    "error": null
  }
}
```

### 9. Translation

This should stay close to the current `/api/translate` behavior.

#### `POST /api/v1/translate`

Auth: none.

Request:

```json
{
  "text": "bonjour",
  "source": "auto"
}
```

Accepted `source` values:

- `auto`
- `en`
- `fr`
- `es`
- `bn`

Response `200`:

```json
{
  "ok": true,
  "query": "bonjour",
  "source": "fr",
  "provider": "hybrid",
  "warnings": [],
  "results": {
    "en": {
      "text": "hello",
      "lang_tag": "en-US"
    },
    "fr": {
      "text": "bonjour",
      "lang_tag": "fr-FR"
    },
    "es": {
      "text": "hola",
      "lang_tag": "es-ES"
    },
    "bn": {
      "text": "Bangla translation",
      "lang_tag": "bn-BD"
    }
  }
}
```

Validation rules should match current behavior:

- `text` required
- max length `200`

### 10. TTS

This should stay close to the current `/api/tts` behavior.

#### `GET /api/v1/tts?lang=fr-FR&text=bonjour`

Auth: none.

Success:

- `200`
- content type `audio/mpeg`

Supported language tags should match current logic:

- `fr-FR`
- `es-ES`
- `en-US`
- `bn-BD`

Validation rules should match current behavior:

- `text` required
- max length `400`
- return `501` when TTS is disabled on the server

Error response example:

```json
{
  "ok": false,
  "error": {
    "code": "unsupported_language",
    "message": "Unsupported language (use en-US, fr-FR, es-ES, bn-BD)"
  }
}
```

## Current web route to mobile API mapping

| Current web behavior | Proposed Android API |
| --- | --- |
| `/login` and `/logout` | `/api/v1/auth/session`, `/api/v1/me` |
| `/language/<lang>` | `GET /api/v1/languages/{lang}/lessons` |
| `/lesson/<lang>/<lesson_id>` | `GET /api/v1/languages/{lang}/lessons/{lesson_id}` |
| `/vocabulary/<lang>` | `GET /api/v1/languages/{lang}/vocabulary` |
| `/placement/<lang>` | `POST /api/v1/languages/{lang}/placement/sessions` and submit endpoint |
| `/quiz/<lang>/<lesson_id>` plus `/api/complete` | quiz session create and submit endpoints |
| `/practice/<lang>` | practice session create and submit endpoints |
| `/review/<lang>` plus `/api/word_progress` | review session endpoint plus `/api/v1/progress/word_events` |
| `/progress` | `GET /api/v1/progress` |
| `/api/feedback` | `POST /api/v1/feedback` |
| `/api/translate` | `POST /api/v1/translate` |
| `/api/tts` | `GET /api/v1/tts` |

## Minimum API surface for Android MVP

These endpoints are enough to ship a functional Android MVP without HTML scraping:

- `POST /api/v1/auth/session`
- `GET /api/v1/me`
- `GET /api/v1/languages`
- `GET /api/v1/languages/{lang}/lessons`
- `GET /api/v1/languages/{lang}/lessons/{lesson_id}`
- `POST /api/v1/languages/{lang}/lessons/{lesson_id}/touch`
- `GET /api/v1/languages/{lang}/vocabulary`
- `POST /api/v1/languages/{lang}/placement/sessions`
- `POST /api/v1/languages/{lang}/placement/sessions/{session_id}/submit`
- `POST /api/v1/languages/{lang}/lessons/{lesson_id}/quiz_sessions`
- `POST /api/v1/languages/{lang}/quiz_sessions/{session_id}/submit`
- `POST /api/v1/languages/{lang}/practice_sessions`
- `POST /api/v1/languages/{lang}/practice_sessions/{session_id}/submit`
- `POST /api/v1/languages/{lang}/review_sessions`
- `POST /api/v1/progress/word_events`
- `GET /api/v1/progress`
- `POST /api/v1/feedback`
- `POST /api/v1/translate`
- `GET /api/v1/tts`

## Explicit non-MVP or follow-up items

These are present in the current web app but do not need to block Android MVP API delivery:

- lesson PDF download
- dictation and speaking are not in Android MVP; no dedicated dictation/speaking endpoints are part of this contract
- browser-based speech recognition parity for speaking
- dashboard resource insights
- Google Sheets admin/reporting APIs

## Backend constraints and blockers

1. Email-only auth is currently unverified. That is acceptable only for parity MVP or internal release.
2. Anonymous progress tables are global, not per-device or per-user. Android should not use them.
3. Current browser question flows score on the client and expose answers. The mobile API should score server-side.
4. SQLite is fine for one-instance MVP hosting but is not a multi-instance sync backend.
5. Current timestamps in the app are derived from app-local time helpers; `/api/v1` should normalize these before Android relies on them.
