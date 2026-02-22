#!/usr/bin/env python3
"""
scripts/build_vocabulary.py
============================
Extract vocabulary from the bilingual visual PDF dictionaries,
auto-translate English → Bengali, group by topic, and save to
data/vocabulary_extended.json ready to merge into the app.

Usage:
    cd "d:/Software Dev/Language Coach"
    pip install deep_translator
    python scripts/build_vocabulary.py
"""

import json, re, time, os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR  = os.path.join(BASE_DIR, 'data')
DICT_DIR  = os.path.join(BASE_DIR, 'Dictionaries')

FR_PDF = os.path.join(DICT_DIR, 'French-English_Bilingual_Visual_Dictionary.pdf')
ES_PDF = os.path.join(DICT_DIR, 'Spanish-English_Bilingual_Visual_Dictionary_2nd_Edition.pdf')

# ── Category detection ────────────────────────────────────────────────────────
# Map English keywords (from section headers like "LES GENS • PEOPLE") to category names
SECTION_MAP = {
    'people'        : 'people',
    'appearance'    : 'appearance',
    'health'        : 'health',
    'home'          : 'home',
    'services'      : 'services',
    'shopping'      : 'shopping',
    'food'          : 'food_advanced',
    'eating'        : 'food_advanced',
    'study'         : 'study',
    'work'          : 'work',
    'transport'     : 'transport_advanced',
    'sports'        : 'sports',
    'environment'   : 'nature',
    'reference'     : 'reference',
}

def detect_section(line):
    """Return category name if line is a main section header (e.g. 'LES GENS • PEOPLE')."""
    if '•' not in line:
        return None
    parts = line.lower().split('•')
    # Check the English part (usually after •)
    for part in parts:
        part = part.strip()
        for keyword, cat in SECTION_MAP.items():
            if keyword in part:
                return cat
    return None

# ── Noise filters ─────────────────────────────────────────────────────────────
NOISE_RE = re.compile(
    r'(fran[cç]ais\s*[•·]\s*english'
    r'|espa[nñ]ol\s*[•·]\s*english'
    r'|^\d+$'           # bare page numbers
    r'|^[A-Z\s]{15,}$' # all-caps headers with no accent
    r')',
    re.I
)

FR_ARTICLE = re.compile(r"^(le |la |l'|les |un |une |des )", re.I)
ES_ARTICLE = re.compile(r'^(el |la |los |las |un |una |unos |unas )', re.I)
ACCENT_FR  = re.compile(r'[àâäéèêëîïôùûüçœæÀÂÄÉÈÊËÎÏÔÙÛÜÇŒÆ]')
ACCENT_ES  = re.compile(r'[áàâäéèêëíîïóôúùûüñÁÀÂÄÉÈÊËÍÎÏÓÔÚÙÛÜÑ]')
ACCENT_ANY = re.compile(r'[àâäéèêëîïôùûüçœæáíóúñÀÂÄÉÈÊËÎÏÔÙÛÜÇŒÆÁÍÓÚÑ]')

PAGE_NUM_RE = re.compile(r'\b\d{1,4}\b')

def _norm_line(s: str) -> str:
    return (
        (s or '')
        .replace('\u00A0', ' ')
        .replace('’', "'")
        .replace('‘', "'")
        .strip()
    )

def _strip_page_nums(s: str) -> str:
    return PAGE_NUM_RE.sub('', s or '')

def clean(word):
    word = _norm_line(word)
    word = re.sub(r'\([^)]{0,30}\)', '', word)   # remove (c alternative) notes
    word = re.sub(r'\s*\(v\)', '', word)         # remove verb markers
    word = word.replace('•', ' ').replace('|', ' ')
    word = _strip_page_nums(word)
    word = re.sub(r'\s+', ' ', word).strip()
    word = word.strip('.,;:•|')
    return word

def is_english(line, lang):
    """Heuristic: likely English label, not a foreign word line."""
    line = _norm_line(line)
    if not line:
        return False
    if NOISE_RE.search(line) or line.isupper() or len(line) > 70:
        return False
    # Avoid misclassifying foreign lines that don't have accents (very common in FR/ES).
    if lang == 'french' and FR_ARTICLE.match(line):
        return False
    if lang == 'spanish' and ES_ARTICLE.match(line):
        return False
    if '¿' in line or '¡' in line:
        return False
    return not ACCENT_ANY.search(line)

def _looks_foreign(line, lang):
    line = _norm_line(line)
    if not line:
        return False
    if lang == 'french':
        return (FR_ARTICLE.match(line) is not None) or (ACCENT_FR.search(line) is not None)
    return (ES_ARTICLE.match(line) is not None) or (ACCENT_ES.search(line) is not None)

def _extract_inline_pairs(line, lang):
    """Extract one or more (foreign, english) pairs from a single mixed line.

    Dictionaries sometimes render as:
      "la pharmacie | pharmacy 108 le fleuriste | florist 110"
    """
    if '|' not in line:
        return [], None

    s = _norm_line(line)
    s = s.replace('•', ' ').replace('·', ' ')
    s = re.sub(r'\s+', ' ', s).strip()
    s = _strip_page_nums(s)
    s = re.sub(r'\s+', ' ', s).strip()

    art = FR_ARTICLE if lang == 'french' else ES_ARTICLE
    matches = list(art.finditer(s))

    # If we can't find foreign-article anchors, fall back to first pipe split.
    if not matches:
        parts = [p.strip() for p in s.split('|') if p.strip()]
        if len(parts) >= 2:
            foreign = clean(parts[0])
            english = clean(parts[1])
            if foreign and english and foreign != english:
                return [(foreign, english)], None
        return [], None

    # Split into chunks starting at each foreign article.
    chunks = []
    for idx, m in enumerate(matches):
        start = m.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(s)
        chunks.append(s[start:end].strip())

    pairs = []
    leftover = None
    for chunk in chunks:
        if '|' in chunk:
            left, right = chunk.split('|', 1)
            foreign = clean(left)
            english = clean(right)
            if foreign and english and foreign != english:
                pairs.append((foreign, english))
        else:
            frag = clean(chunk)
            if frag and art.match(frag):
                leftover = frag

    return pairs, leftover

# ── PDF extraction ────────────────────────────────────────────────────────────
def extract_from_pdf(pdf_path, lang):
    from pypdf import PdfReader
    reader   = PdfReader(pdf_path)
    entries  = []      # list of dicts: {word, english, category}
    seen     = set()
    category = 'general'

    print(f"\nExtracting {lang} — {len(reader.pages)} pages …")

    for pg_num, page in enumerate(reader.pages):
        try:
            text = page.extract_text()
        except Exception:
            continue
        if not text or len(text.strip()) < 40:
            continue

        lines = [l.strip() for l in text.split('\n') if l.strip() and len(l.strip()) > 1]

        i = 0
        while i < len(lines):
            line = lines[i]
            line = _norm_line(line)

            # --- detect section header ---
            sec = detect_section(line)
            if sec:
                category = sec
                i += 1
                continue

            # --- skip pure noise ---
            if ('•' in line and '|' not in line) or NOISE_RE.search(line) or len(line) > 120:
                i += 1
                continue

            # --- inline pairs on the same line ---
            pairs, leftover = _extract_inline_pairs(line, lang)
            if pairs:
                for foreign, english in pairs:
                    key = (foreign.lower(), english.lower())
                    if foreign and english and foreign != english and key not in seen:
                        seen.add(key)
                        entries.append({'word': foreign, 'english': english, 'category': category})

                # Sometimes the last foreign fragment has its English label on the next line.
                if leftover and i + 1 < len(lines):
                    nxt = _norm_line(lines[i + 1])
                    if is_english(nxt, lang):
                        foreign = clean(leftover)
                        english = clean(nxt)
                        key = (foreign.lower(), english.lower())
                        if foreign and english and foreign != english and key not in seen:
                            seen.add(key)
                            entries.append({'word': foreign, 'english': english, 'category': category})
                        i += 2
                        continue

                i += 1
                continue

            # --- try to form a word pair with the next line ---
            if i + 1 < len(lines):
                nxt = _norm_line(lines[i + 1])
                if _looks_foreign(line, lang) and is_english(nxt, lang):
                    foreign = clean(line)
                    english = clean(nxt)
                    key = (foreign.lower(), english.lower())
                    if foreign and english and foreign != english and key not in seen:
                        seen.add(key)
                        entries.append({'word': foreign, 'english': english, 'category': category})
                    i += 2
                    continue

            i += 1

        if (pg_num + 1) % 60 == 0:
            print(f"  … page {pg_num+1}/{len(reader.pages)}  ({len(entries)} pairs)")

    print(f"  Done — {len(entries)} unique pairs extracted")
    return entries

# ── Bengali translation ───────────────────────────────────────────────────────
def translate_to_bengali(english_words, cache_path, delay=0.12):
    """Translate list of English words to Bengali using deep_translator.
    Uses a JSON cache so it can resume if interrupted."""
    cache = {}
    if os.path.exists(cache_path):
        with open(cache_path, encoding='utf-8') as f:
            cache = json.load(f)
        print(f"  Cache loaded — {len(cache)} existing translations")

    to_do = [w for w in english_words if w not in cache]
    if not to_do:
        print("  All words already translated (cache hit)")
        return cache

    print(f"  Translating {len(to_do)} words to Bengali …")

    try:
        from deep_translator import GoogleTranslator
        translator = GoogleTranslator(source='en', target='bn')
    except ImportError:
        print("  ERROR: run  pip install deep_translator  first")
        sys.exit(1)

    for idx, word in enumerate(to_do):
        try:
            cache[word] = translator.translate(word)
        except Exception as exc:
            print(f"    Warning: could not translate '{word}': {exc}")
            cache[word] = word          # fallback — keep English

        if (idx + 1) % 50 == 0:
            _save_json(cache, cache_path)
            pct = round((idx + 1) / len(to_do) * 100)
            print(f"    {idx+1}/{len(to_do)} ({pct}%)")

        time.sleep(delay)

    _save_json(cache, cache_path)
    print(f"  Translation complete — cache saved to {cache_path}")
    return cache

# ── Helpers ───────────────────────────────────────────────────────────────────
def _save_json(data, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def build_entries(raw_pairs, bengali_map):
    """Turn raw {word, english, category} dicts into full vocabulary entries."""
    entries   = []
    seen_word = set()

    for p in raw_pairs:
        w   = p['word']
        en  = p['english']
        cat = p['category']

        if w.lower() in seen_word:
            continue
        seen_word.add(w.lower())

        bn = bengali_map.get(en, en)

        entries.append({
            'word'        : w,
            'english'     : en,
            'bengali'     : bn,
            'category'    : cat,
            'pronunciation': '',
            'example'     : f'{w}.',
            'example_en'  : f'{en}.',
            'example_bn'  : f'{bn}।',
        })

    return entries

# ── Main ──────────────────────────────────────────────────────────────────────
def process(lang, pdf_path):
    print(f"\n{'='*60}")
    print(f"  {lang.upper()}")
    print('='*60)

    raw = extract_from_pdf(pdf_path, lang)

    cache_path   = os.path.join(DATA_DIR, f'_bn_cache_{lang}.json')
    english_set  = list({p['english'] for p in raw})
    bengali_map  = translate_to_bengali(english_set, cache_path)

    entries = build_entries(raw, bengali_map)

    # Group by category
    grouped = {}
    for e in entries:
        grouped.setdefault(e['category'], []).append(e)

    print(f"\n  Categories extracted:")
    for cat, words in sorted(grouped.items(), key=lambda x: -len(x[1])):
        print(f"    {cat:25s} {len(words):4d} words")

    return grouped


if __name__ == '__main__':
    os.makedirs(DATA_DIR, exist_ok=True)

    result = {}
    result['french']  = process('french',  FR_PDF)
    result['spanish'] = process('spanish', ES_PDF)

    out = os.path.join(DATA_DIR, 'vocabulary_extended.json')
    _save_json(result, out)

    fr_total = sum(len(v) for v in result['french'].values())
    es_total = sum(len(v) for v in result['spanish'].values())

    print(f"\n{'='*60}")
    print(f"  DONE")
    print(f"  French  : {fr_total} words across {len(result['french'])} categories")
    print(f"  Spanish : {es_total} words across {len(result['spanish'])} categories")
    print(f"  Output  : {out}")
    print(f"\n  Next step:")
    print(f"    python scripts/merge_vocabulary.py")
    print('='*60)
