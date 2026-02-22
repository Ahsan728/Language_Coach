#!/usr/bin/env python3
"""Clean the `reference` vocabulary category.

Only removes entries with clear data corruption:
- Word/english is empty or < 2 chars
- English ends with '?' while word does NOT (broken sentence split across fields)
- Either field is a bare number (page number artefact)
- Word and english are identical (no learning value)

Run from project root:
    python scripts/clean_reference.py [--dry-run]
"""
import json
import re
import sys
from pathlib import Path

VOCAB_PATH = Path('data/vocabulary.json')
DRY_RUN = '--dry-run' in sys.argv


def is_bad_entry(entry: dict) -> tuple[bool, str]:
    word = (entry.get('word') or '').strip()
    eng  = (entry.get('english') or '').strip()

    if not word or not eng:
        return True, 'empty field'
    if len(word) < 2 or len(eng) < 2:
        return True, 'too short'
    # Broken sentence split: the english field contains the tail of a question
    # e.g. word="ça dure combien de"  english="temps?"
    if eng.endswith('?') and not word.endswith('?') and not eng[0].isupper():
        return True, f'split sentence tail: {eng!r}'
    # Page-number artefact
    if re.fullmatch(r'\d+', eng) or re.fullmatch(r'\d+', word):
        return True, f'pure number: word={word!r} eng={eng!r}'
    # Duplicate (no translation value)
    if word.lower().strip("'") == eng.lower().strip("'"):
        return True, f'word == english: {word!r}'
    return False, ''


def clean(vocab: dict) -> dict:
    total_removed = 0
    for lang in ('french', 'spanish'):
        ref = vocab.get(lang, {}).get('reference', [])
        before = len(ref)
        good = []
        bad_entries = []
        for entry in ref:
            bad, reason = is_bad_entry(entry)
            if bad:
                bad_entries.append((reason, entry.get('word', ''), entry.get('english', '')))
            else:
                good.append(entry)

        vocab[lang]['reference'] = good
        removed = before - len(good)
        total_removed += removed
        print(f'{lang}/reference: {before} -> {len(good)} ({removed} removed)')
        if DRY_RUN and bad_entries:
            for reason, w, e in bad_entries[:20]:
                print(f'  REMOVE ({reason}): {w!r:35} -> {e!r}')

    print(f'Total removed: {total_removed}')
    return vocab


def main():
    print(f'Reading {VOCAB_PATH} ...')
    with open(VOCAB_PATH, encoding='utf-8') as f:
        vocab = json.load(f)

    vocab = clean(vocab)

    if DRY_RUN:
        print('[DRY RUN - no changes written]')
    else:
        print(f'Writing {VOCAB_PATH} ...')
        with open(VOCAB_PATH, 'w', encoding='utf-8') as f:
            json.dump(vocab, f, ensure_ascii=False, indent=2)
        print('Done.')


if __name__ == '__main__':
    main()
