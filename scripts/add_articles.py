#!/usr/bin/env python3
"""Add `article` field to noun vocabulary entries in vocabulary.json.

Adds definite articles (le/la/l'/el/la) to family, body, food, and transport
words so learners see gender alongside each word — e.g. "le pain", "la tête".

Run from the project root:
    python scripts/add_articles.py
"""

import json
from pathlib import Path

VOCAB_PATH = Path('data/vocabulary.json')

# French definite articles — original noun categories (bare words, no article yet)
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

# Spanish definite articles — original noun categories
# Note: "el agua" — agua is grammatically feminine but takes el in singular
# "la mano" — mano is feminine despite -o ending
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
    # food (agua takes el despite being feminine)
    'pan': 'el', 'leche': 'la', 'agua': 'el', 'café': 'el',
    'té': 'el', 'arroz': 'el', 'carne': 'la', 'pollo': 'el',
    'pescado': 'el', 'fruta': 'la', 'verdura': 'la', 'huevo': 'el',
    'queso': 'el', 'azúcar': 'el', 'sal': 'la', 'sopa': 'la',
    # transport
    'coche': 'el', 'autobús': 'el', 'tren': 'el', 'avión': 'el',
    'bicicleta': 'la', 'taxi': 'el', 'metro': 'el', 'estación': 'la',
    'aeropuerto': 'el', 'billete': 'el',
}

NOUN_CATEGORIES = {'family', 'body', 'food', 'transport'}
ARTICLES = {'french': FR_ARTICLES, 'spanish': ES_ARTICLES}


def add_articles(vocab: dict) -> dict:
    added = 0
    skipped = 0
    no_match = []

    for lang in ('french', 'spanish'):
        art_map = ARTICLES[lang]
        lang_data = vocab.get(lang, {})
        for cat in NOUN_CATEGORIES:
            for entry in lang_data.get(cat, []):
                w = entry.get('word', '')
                if 'article' in entry:
                    skipped += 1
                    continue
                if w in art_map:
                    entry['article'] = art_map[w]
                    added += 1
                else:
                    no_match.append(f'{lang}/{cat}/{w!r}')

    print(f'Added articles : {added}')
    print(f'Already had    : {skipped}')
    if no_match:
        print(f'No match ({len(no_match)}):')
        for m in no_match:
            print(f'  {m}')
    else:
        print('All noun words matched — no gaps.')

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
