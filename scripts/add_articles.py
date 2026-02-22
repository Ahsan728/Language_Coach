#!/usr/bin/env python3
"""Add `article` field to all noun vocabulary entries in vocabulary.json.

Pass 1 — Original categories (bare words): uses a hardcoded article map.
Pass 2 — Extended categories (article already in word field like "le médecin"):
          extracts the article prefix, stores it in `article`, and strips it
          from `word` so display code can style them separately.

Run from the project root:
    python scripts/add_articles.py
"""

import json
import re
from pathlib import Path

VOCAB_PATH = Path('data/vocabulary.json')

# ── Pass 1: hardcoded articles for original bare-word categories ──────────────

FR_ARTICLES = {
    # family
    'père': 'le', 'mère': 'la', 'frère': 'le', 'sœur': 'la',
    'fils': 'le', 'fille': 'la', 'grand-père': 'le', 'grand-mère': 'la',
    'oncle': "l'", 'tante': 'la', 'mari': 'le', 'femme': 'la',
    'enfant': "l'", 'famille': 'la',
    # body
    'tête': 'la', 'visage': 'le', 'œil': "l'", 'nez': 'le',
    'bouche': 'la', 'oreille': "l'", 'cou': 'le', 'épaule': "l'",
    'bras': 'le', 'main': 'la', 'dos': 'le', 'jambe': 'la',
    'pied': 'le', 'genou': 'le', 'doigt': 'le',
    # food
    'pain': 'le', 'lait': 'le', 'eau': "l'", 'café': 'le',
    'thé': 'le', 'riz': 'le', 'viande': 'la', 'poulet': 'le',
    'poisson': 'le', 'fruit': 'le', 'légume': 'le', 'œuf': "l'",
    'fromage': 'le', 'sucre': 'le', 'sel': 'le', 'soupe': 'la',
    # transport
    'voiture': 'la', 'bus': 'le', 'train': 'le', 'avion': "l'",
    'vélo': 'le', 'taxi': 'le', 'métro': 'le', 'gare': 'la',
    'aéroport': "l'", 'billet': 'le',
}

ES_ARTICLES = {
    # family
    'padre': 'el', 'madre': 'la', 'hermano': 'el', 'hermana': 'la',
    'hijo': 'el', 'hija': 'la', 'abuelo': 'el', 'abuela': 'la',
    'tío': 'el', 'tía': 'la', 'esposo': 'el', 'esposa': 'la',
    'familia': 'la',
    # body
    'cabeza': 'la', 'cara': 'la', 'ojo': 'el', 'nariz': 'la',
    'boca': 'la', 'oreja': 'la', 'cuello': 'el', 'hombro': 'el',
    'brazo': 'el', 'mano': 'la', 'espalda': 'la', 'pierna': 'la',
    'pie': 'el', 'rodilla': 'la', 'dedo': 'el',
    # food ("el agua" — feminine but takes el; "la mano" — feminine despite -o)
    'pan': 'el', 'leche': 'la', 'agua': 'el', 'café': 'el',
    'té': 'el', 'arroz': 'el', 'carne': 'la', 'pollo': 'el',
    'pescado': 'el', 'fruta': 'la', 'verdura': 'la', 'huevo': 'el',
    'queso': 'el', 'azúcar': 'el', 'sal': 'la', 'sopa': 'la',
    # transport
    'coche': 'el', 'autobús': 'el', 'tren': 'el', 'avión': 'el',
    'bicicleta': 'la', 'taxi': 'el', 'metro': 'el', 'estación': 'la',
    'aeropuerto': 'el', 'billete': 'el',
}

HARDCODED_CATS = {'family', 'body', 'food', 'transport'}

# ── Pass 2: extract article prefix from extended-category words ───────────────

# Order matters: longer prefixes first so "les " doesn't match "le " early
FR_PREFIXES = ["l'", "les ", "le ", "la "]
ES_PREFIXES = ["los ", "las ", "el ", "la "]
LANG_PREFIXES = {'french': FR_PREFIXES, 'spanish': ES_PREFIXES}

# Categories to skip entirely (no articles for verbs, adjectives, phrases, etc.)
SKIP_CATS = {
    'greetings', 'numbers', 'colors', 'time', 'verbs',
    'adjectives', 'phrases', 'nationalities', 'daily_activities',
    'emotions', 'reference',
}


def _extract_article(word: str, prefixes: list[str]) -> tuple[str, str]:
    """Return (article, bare_word) by stripping a leading article prefix.
    Returns ('', word) if no article found.
    """
    low = word.lower()
    for p in prefixes:
        if low.startswith(p):
            art = p.rstrip()   # "le", "la", "l'", "les", "el", "los", "las"
            bare = word[len(p):]
            return art, bare
    return '', word


def add_articles(vocab: dict) -> dict:
    p1_added = p1_skipped = p1_no_match = 0
    p2_added = p2_skipped = 0

    for lang in ('french', 'spanish'):
        lang_data = vocab.get(lang, {})
        prefixes = LANG_PREFIXES[lang]

        for cat, words in lang_data.items():
            # ── Pass 1: original bare-word categories ─────────────────────────
            if cat in HARDCODED_CATS:
                art_map = FR_ARTICLES if lang == 'french' else ES_ARTICLES
                for entry in words:
                    if 'article' in entry:
                        p1_skipped += 1
                        continue
                    w = entry.get('word', '')
                    if w in art_map:
                        entry['article'] = art_map[w]
                        p1_added += 1
                    else:
                        p1_no_match += 1

            # ── Pass 2: extended categories with embedded article in word ─────
            elif cat not in SKIP_CATS:
                for entry in words:
                    if 'article' in entry:
                        p2_skipped += 1
                        continue
                    w = entry.get('word', '')
                    art, bare = _extract_article(w, prefixes)
                    if art:
                        entry['article'] = art
                        entry['word'] = bare   # store bare word only
                        p2_added += 1

    print(f'Pass 1 (hardcoded): added={p1_added}, skipped={p1_skipped}, unmatched={p1_no_match}')
    print(f'Pass 2 (extracted): added={p2_added}, skipped={p2_skipped}')
    return vocab


def main():
    print(f'Reading {VOCAB_PATH} …')
    with open(VOCAB_PATH, encoding='utf-8') as f:
        vocab = json.load(f)

    vocab = add_articles(vocab)

    print(f'Writing {VOCAB_PATH} …')
    with open(VOCAB_PATH, 'w', encoding='utf-8') as f:
        json.dump(vocab, f, ensure_ascii=False, indent=2)

    print('Done.')


if __name__ == '__main__':
    main()
