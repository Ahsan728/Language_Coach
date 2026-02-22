#!/usr/bin/env python3
"""
scripts/clean_vocabulary_extended.py
===================================
Clean up and de-noise `data/vocabulary_extended.json` (generated from the
visual dictionaries) and write a fixed version to:

  data/vocabulary_extended_clean.json

Why this exists
---------------
PDF text extraction is messy. Common failure modes:
- Multiple "foreign | english" pairs appear on one line.
- Page/index numbers get embedded in strings.
- A foreign line without accents gets mis-classified as English.

This script repairs many of those issues without re-running PDF extraction.

Usage:
  cd "d:/Software Dev/Language Coach"
  python scripts/clean_vocabulary_extended.py
  python scripts/merge_vocabulary.py
"""

import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

SRC = os.path.join(DATA_DIR, "vocabulary_extended.json")
DEST = os.path.join(DATA_DIR, "vocabulary_extended_clean.json")

FR_ARTICLE = re.compile(r"^(le |la |l'|les |un |une |des )", re.I)
ES_ARTICLE = re.compile(r"^(el |la |los |las |un |una |unos |unas )", re.I)

ACCENT_ANY = re.compile(r"[àâäéèêëîïôùûüçœæáíóúñÀÂÄÉÈÊËÎÏÔÙÛÜÇŒÆÁÍÓÚÑ]")
PAGE_NUM_RE = re.compile(r"\b\d{1,4}\b")


def _norm_line(s: str) -> str:
    return (
        (s or "")
        .replace("\u00A0", " ")
        .replace("’", "'")
        .replace("‘", "'")
        .strip()
    )


def _strip_page_nums(s: str) -> str:
    return PAGE_NUM_RE.sub("", s or "")


def _clean_text(s: str) -> str:
    s = _norm_line(s)
    s = re.sub(r"\([^)]{0,40}\)", "", s)  # remove short parenthetical notes
    s = s.replace("•", " ").replace("·", " ")
    s = _strip_page_nums(s)
    s = re.sub(r"\s+", " ", s).strip()
    s = s.strip(".,;:•|")
    return s


def _extract_inline_pairs(text: str, lang: str):
    """Extract one or more (foreign, english) pairs from a mixed line."""
    text = _norm_line(text)
    if "|" not in text:
        return []

    s = text.replace("•", " ").replace("·", " ")
    s = re.sub(r"\s+", " ", s).strip()
    s = _strip_page_nums(s)
    s = re.sub(r"\s+", " ", s).strip()

    art = FR_ARTICLE if lang == "french" else ES_ARTICLE
    matches = list(art.finditer(s))

    if not matches:
        parts = [p.strip() for p in s.split("|") if p.strip()]
        if len(parts) >= 2:
            foreign = _clean_text(parts[0])
            english = _clean_text(parts[1])
            if foreign and english and foreign != english:
                return [(foreign, english)]
        return []

    chunks = []
    for idx, m in enumerate(matches):
        start = m.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(s)
        chunks.append(s[start:end].strip())

    pairs = []
    for chunk in chunks:
        if "|" not in chunk:
            continue
        left, right = chunk.split("|", 1)
        foreign = _clean_text(left)
        english = _clean_text(right)
        if foreign and english and foreign != english:
            pairs.append((foreign, english))
    return pairs


def _load_bn_cache(lang: str) -> dict:
    path = os.path.join(DATA_DIR, f"_bn_cache_{lang}.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _should_keep_pair(foreign: str, english: str, lang: str) -> bool:
    if not foreign or not english or foreign == english:
        return False
    if "|" in foreign or "|" in english or "•" in foreign or "•" in english:
        return False
    if len(foreign) > 80 or len(english) > 80:
        return False

    art = FR_ARTICLE if lang == "french" else ES_ARTICLE
    # If the English side looks like another foreign entry, it was likely mis-paired.
    if art.match(english):
        return False

    # Guard against obvious index noise like "84, 262"
    if re.fullmatch(r"[\d,\s]+", foreign) or re.fullmatch(r"[\d,\s]+", english):
        return False

    # Avoid dropping real English with accents (rare) by being conservative.
    # (This primarily filters out broken pairs.)
    return True


def _make_entry(word: str, english: str, bengali: str, category: str) -> dict:
    return {
        "word": word,
        "english": english,
        "bengali": bengali,
        "category": category,
        "pronunciation": "",
        "example": f"{word}.",
        "example_en": f"{english}.",
        "example_bn": f"{bengali}।",
    }


def main() -> int:
    if not os.path.exists(SRC):
        print(f"ERROR: Missing {SRC}")
        return 2

    with open(SRC, encoding="utf-8") as f:
        src = json.load(f) or {}

    out = {}
    for lang in ("french", "spanish"):
        bn_map = _load_bn_cache(lang)
        out_lang = {}
        seen = set()
        total_in = 0
        total_out = 0

        for cat, items in (src.get(lang) or {}).items():
            total_in += len(items or [])
            for it in (items or []):
                raw_word = _norm_line(it.get("word", ""))
                raw_en = _norm_line(it.get("english", ""))

                pairs = []
                pairs.extend(_extract_inline_pairs(raw_word, lang))
                pairs.extend(_extract_inline_pairs(raw_en, lang))

                if not pairs:
                    w = _clean_text(raw_word)
                    en = _clean_text(raw_en)
                    if w and en and w != en:
                        pairs.append((w, en))

                for w, en in pairs:
                    w = _clean_text(w)
                    en = _clean_text(en)
                    if not _should_keep_pair(w, en, lang):
                        continue
                    key = (w.lower(), en.lower(), cat)
                    if key in seen:
                        continue
                    seen.add(key)

                    bn = bn_map.get(en) or en
                    out_lang.setdefault(cat, []).append(_make_entry(w, en, bn, cat))
                    total_out += 1

        out[lang] = out_lang
        print(f"{lang}: {total_in} -> {total_out} cleaned entries across {len(out_lang)} categories")

    with open(DEST, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"Output: {DEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

