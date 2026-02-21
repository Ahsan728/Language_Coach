#!/usr/bin/env python3
"""
scripts/merge_vocabulary.py
===========================
Merge vocabulary_extended.json (from PDFs) into the live data/vocabulary.json.

Strategy:
  - Keep all existing hand-crafted entries (they have good pronunciations).
  - For each NEW category from the PDFs, add the top N words, skipping
    any that are already in the existing vocabulary.
  - Skip "reference" (page headers / random vocab) and "general".
  - Cap each new category at MAX_PER_CAT words to keep the app snappy.

Usage:
    cd "d:/Software Dev/Language Coach"
    python scripts/merge_vocabulary.py
"""

import json, os, re, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')

SRC  = os.path.join(DATA_DIR, 'vocabulary_extended.json')
DEST = os.path.join(DATA_DIR, 'vocabulary.json')

# Categories to skip (too noisy from PDF headers)
SKIP_CATS = {'reference', 'general'}

# Max new words to add per category per language
MAX_PER_CAT = 60

# Map new category names → human-readable labels (English + Bengali)
CAT_LABELS = {
    'health'           : ('Health & Medical',         'স্বাস্থ্য ও চিকিৎসা'),
    'home'             : ('Home & Living',             'ঘর ও গৃহস্থালি'),
    'food_advanced'    : ('Food & Cooking',            'খাবার ও রান্না'),
    'sports'           : ('Sports & Leisure',          'খেলাধুলা ও অবসর'),
    'nature'           : ('Nature & Environment',      'প্রকৃতি ও পরিবেশ'),
    'work'             : ('Work & Career',             'কাজ ও পেশা'),
    'shopping'         : ('Shopping & Fashion',        'কেনাকাটা ও ফ্যাশন'),
    'appearance'       : ('Appearance & Clothing',     'চেহারা ও পোশাক'),
    'study'            : ('Study & Education',         'পড়াশোনা ও শিক্ষা'),
    'services'         : ('Services & Community',      'সেবা ও সমাজ'),
    'people'           : ('People & Society',          'মানুষ ও সমাজ'),
    'transport_advanced': ('Transport & Travel',       'যানবাহন ও ভ্রমণ'),
}

# Categories already covered by existing vocabulary — merge but don't duplicate
EXISTING_CATS = {
    'greetings', 'numbers', 'colors', 'time', 'family',
    'body', 'food', 'verbs', 'adjectives', 'transport', 'phrases',
}


def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def save_json(data, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def normalise(word):
    """Lowercase, strip articles for dedup check."""
    w = word.lower().strip()
    w = re.sub(r"^(le |la |l'|les |un |une |des |el |los |las |un |una |unos |unas )", '', w, flags=re.I)
    return w.strip()


def merge(lang, existing_grouped, extended_grouped):
    """
    existing_grouped: {category: [word_dicts]}   (current vocabulary.json shape)
    extended_grouped: {category: [word_dicts]}   (from build_vocabulary.py)
    Returns a merged dict in the same {category: [word_dicts]} shape.
    """
    # Flatten existing into dedup sets
    all_existing = [e for words in existing_grouped.values() for e in words]
    existing_norms   = {normalise(e['word'])           for e in all_existing}
    existing_english = {e['english'].lower()[:30]      for e in all_existing}

    existing_words_count = len(all_existing)
    added_total = 0

    # Start with a copy of the existing grouped dict
    result = {cat: list(words) for cat, words in existing_grouped.items()}

    for cat, words in sorted(extended_grouped.items()):
        if cat in SKIP_CATS:
            continue

        count = 0
        for entry in words:
            if count >= MAX_PER_CAT:
                break

            norm   = normalise(entry['word'])
            en_key = entry['english'].lower()[:30]

            if norm in existing_norms or en_key in existing_english:
                continue  # already have this word

            new_entry = {
                'word'         : entry['word'],
                'english'      : entry['english'],
                'bengali'      : entry['bengali'],
                'category'     : cat,
                'pronunciation': entry.get('pronunciation', ''),
                'example'      : entry.get('example', f"{entry['word']}."),
                'example_en'   : entry.get('example_en', f"{entry['english']}."),
                'example_bn'   : entry.get('example_bn', f"{entry['bengali']}।"),
            }
            result.setdefault(cat, []).append(new_entry)
            existing_norms.add(norm)
            existing_english.add(en_key)
            count += 1

        if count > 0:
            print(f"  [{lang}] {cat:25s}  +{count} words")
            added_total += count

    total_after = sum(len(v) for v in result.values())
    print(f"\n  [{lang}] {existing_words_count} existing + {added_total} new = {total_after} words total")
    return result


def main():
    print("Loading files …")
    existing = load_json(DEST)   # {"french": {cat: [...]}, "spanish": {cat: [...]}}
    extended = load_json(SRC)    # {"french": {cat: [...]}, "spanish": {cat: [...]}}

    result = {}
    for lang in ['french', 'spanish']:
        print(f"\n{'='*55}")
        print(f"  {lang.upper()}")
        print('='*55)
        result[lang] = merge(lang, existing[lang], extended[lang])

    save_json(result, DEST)

    fr_total = sum(len(v) for v in result['french'].values())
    es_total = sum(len(v) for v in result['spanish'].values())
    fr_cats  = sorted(result['french'].keys())
    es_cats  = sorted(result['spanish'].keys())

    print(f"\n{'='*55}")
    print(f"  DONE — vocabulary.json updated")
    print(f"  French  : {fr_total} words in {len(fr_cats)} categories")
    print(f"  Spanish : {es_total} words in {len(es_cats)} categories")
    print(f"\n  French categories  : {fr_cats}")
    print(f"  Spanish categories : {es_cats}")
    print('='*55)
    print("\n  Next step:")
    print("    python scripts/add_new_lessons.py")


if __name__ == '__main__':
    main()
