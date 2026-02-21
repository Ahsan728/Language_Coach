#!/usr/bin/env python3
"""
scripts/validate_content.py
===========================
Quick consistency checks for content files:
  - data/lessons.json
  - data/vocabulary.json

Checks
------
- Unique lesson IDs per language
- Lessons reference existing vocabulary categories
- Minimal required fields exist
- Warns if a lesson has < 4 vocab words (quiz disabled for that lesson)

Usage
-----
    cd "d:/Software Dev/Language Coach"
    python scripts/validate_content.py
"""

import json
import os
import sys
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')

VOCAB_FILE = os.path.join(DATA_DIR, 'vocabulary.json')
LESSONS_FILE = os.path.join(DATA_DIR, 'lessons.json')


def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def main() -> int:
    try:
        vocab = load_json(VOCAB_FILE)
    except Exception as exc:  # noqa: BLE001 - CLI tool; show helpful errors
        print(f"ERROR: Could not load {VOCAB_FILE}\n  {exc}")
        return 2

    try:
        lessons = load_json(LESSONS_FILE)
    except Exception as exc:  # noqa: BLE001 - CLI tool; show helpful errors
        print(f"ERROR: Could not load {LESSONS_FILE}\n  {exc}")
        return 2

    langs = sorted(set(vocab.keys()) | set(lessons.keys()))
    errors = 0
    warnings = 0

    for lang in langs:
        print(f"\n{'='*60}")
        print(f"  {lang.upper()}")
        print('='*60)

        vocab_by_cat = vocab.get(lang) or {}
        lesson_list = lessons.get(lang) or []

        vocab_cats = set(vocab_by_cat.keys())
        print(f"  Categories : {len(vocab_cats)}")
        print(f"  Lessons    : {len(lesson_list)}")

        ids = [l.get('id') for l in lesson_list]
        id_counts = Counter(ids)
        dup_ids = [i for i, c in id_counts.items() if i is not None and c > 1]
        if dup_ids:
            errors += 1
            print(f"  ERROR: Duplicate lesson IDs: {sorted(dup_ids)}")

        for lesson in lesson_list:
            lid = lesson.get('id')

            # Required fields
            required = ['id', 'title_en', 'title_bn', 'cefr_level', 'vocabulary_categories']
            missing_fields = [k for k in required if k not in lesson]
            if missing_fields:
                errors += 1
                print(f"  ERROR: Lesson {lid} missing fields: {missing_fields}")
                continue

            if not isinstance(lesson.get('vocabulary_categories'), list):
                errors += 1
                print(f"  ERROR: Lesson {lid} vocabulary_categories must be a list")
                continue

            cats = lesson.get('vocabulary_categories') or []
            missing_cats = [c for c in cats if c not in vocab_cats]
            if missing_cats:
                errors += 1
                print(f"  ERROR: Lesson {lid} references missing categories: {missing_cats}")

            # Quiz readiness
            vocab_count = sum(len(vocab_by_cat.get(c, [])) for c in cats)
            if 0 < vocab_count < 4:
                warnings += 1
                print(f"  WARN : Lesson {lid} has only {vocab_count} vocab words (quiz needs 4)")

        # Basic vocab entry sanity (cheap)
        total_words = sum(len(words) for words in vocab_by_cat.values())
        if total_words == 0:
            warnings += 1
            print("  WARN : No vocabulary words found")

    print(f"\n{'='*60}")
    if errors:
        print(f"FAILED: {errors} error(s), {warnings} warning(s)")
        return 1
    print(f"OK: {warnings} warning(s)")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

