#!/usr/bin/env python3
"""Add vocabulary_categories to grammar-only lessons so students can
practise flashcards and dictation immediately after studying grammar.

Each grammar lesson is mapped to categories whose words best illustrate
the grammar concept taught.

Run from project root:
    python scripts/patch_grammar_lessons.py
"""
import json
from pathlib import Path

LESSONS_PATH = Path('data/lessons.json')

# lesson_id → vocabulary_categories to add (same for both languages)
GRAMMAR_VOCAB_PATCH = {
    # Articles & Gender (FR) / SER vs ESTAR (ES)
    11: ['family', 'body'],
    # Present Tense
    12: ['verbs', 'daily_activities'],
    # Past Tense
    13: ['verbs', 'food'],
    # Future Tense
    14: ['verbs', 'transport'],
    # Imparfait vs Passé Composé / Imperfect vs Preterite
    37: ['verbs', 'daily_activities'],
    # Conditional
    38: ['verbs', 'adjectives'],
    # Relative Clauses
    47: ['people', 'adjectives'],
    # Reported Speech
    48: ['phrases', 'verbs'],
}


def patch(lessons: dict) -> dict:
    total = 0
    for lang in ('french', 'spanish'):
        for lesson in lessons.get(lang, []):
            lid = lesson.get('id')
            if lid not in GRAMMAR_VOCAB_PATCH:
                continue
            cats = GRAMMAR_VOCAB_PATCH[lid]
            # Only add if currently empty to avoid overwriting intentional choices
            existing = lesson.get('vocabulary_categories', [])
            if existing:
                print(f'  [{lang}] lesson {lid}: already has categories {existing}, skipping')
                continue
            lesson['vocabulary_categories'] = cats
            # Cap each category at 20 words for grammar lessons (not overwhelming)
            lesson['vocab_limit_per_category'] = 20
            total += 1
            print(f'  [{lang}] lesson {lid} "{lesson.get("title_en","")[:40]}": added {cats}')
    print(f'Patched {total} grammar lessons.')
    return lessons


def main():
    print(f'Reading {LESSONS_PATH} ...')
    with open(LESSONS_PATH, encoding='utf-8') as f:
        lessons = json.load(f)

    lessons = patch(lessons)

    print(f'Writing {LESSONS_PATH} ...')
    with open(LESSONS_PATH, 'w', encoding='utf-8') as f:
        json.dump(lessons, f, ensure_ascii=False, indent=2)
    print('Done.')


if __name__ == '__main__':
    main()
