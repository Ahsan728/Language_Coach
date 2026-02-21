#!/usr/bin/env python3
"""
scripts/build_resource_sentences.py
==================================
Extract short example sentences from local PDF resources under:
  - French Resources/
  - Spanish Resources/

Output:
  - data/resource_sentences.json

This enables the "Context" question type inside Daily Practice (/practice/<lang>).

Usage
-----
    cd "d:/Software Dev/Language Coach"
    python scripts/build_resource_sentences.py

    # Faster test run
    python scripts/build_resource_sentences.py --max-pages 3 --max-sentences 200
"""

import argparse
import json
import os
import re
import sys
import unicodedata
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')

RESOURCE_DIRS = {
    'french': os.path.join(BASE_DIR, 'French Resources'),
    'spanish': os.path.join(BASE_DIR, 'Spanish Resources'),
}

SENT_SPLIT_RE = re.compile(r'(?<=[.!?])\s+')
WORD_RE = re.compile(r"[A-Za-zÀ-ÿ]+(?:'[A-Za-zÀ-ÿ]+)?")


def _strip_accents(text: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')


def _norm_sentence(text: str) -> str:
    s = _strip_accents((text or '').lower().strip())
    s = s.replace("'", ' ')
    s = re.sub(r'[^a-z0-9]+', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def _is_good_sentence(s: str) -> bool:
    s = (s or '').strip()
    if not s:
        return False
    if len(s) < 24 or len(s) > 220:
        return False
    if re.match(r'^\s*[\-\u2022•]\s+\w+', s):
        return False
    if re.search(r'https?://|www\.', s, flags=re.I):
        return False
    if 'copyright' in s.lower() or 'all rights reserved' in s.lower():
        return False
    if sum(ch.isdigit() for ch in s) > 6:
        return False

    words = WORD_RE.findall(s)
    if len(words) < 4 or len(words) > 30:
        return False
    if max((len(w) for w in words), default=0) > 26:
        return False

    alpha_ratio = sum(ch.isalpha() for ch in s) / max(1, len(s))
    if alpha_ratio < 0.55:
        return False

    # Prefer real sentences, but allow some clean line-based extracts.
    if not s.endswith(('.', '!', '?', '…')) and len(words) < 8:
        return False

    return True


def iter_pdfs(resource_dir: str):
    if not resource_dir or not os.path.isdir(resource_dir):
        return
    for root, _, files in os.walk(resource_dir):
        for name in sorted(files):
            if name.lower().endswith('.pdf'):
                yield os.path.join(root, name)


def extract_sentences_from_pdf(pdf_path: str, max_pages: int):
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("Missing dependency: pypdf. Run: pip install -r requirements.txt") from exc

    try:
        reader = PdfReader(pdf_path)
    except Exception as exc:  # noqa: BLE001 - CLI tool; continue with best effort
        print(f"  WARN: Could not read PDF: {os.path.basename(pdf_path)} ({exc})")
        return []

    if getattr(reader, "is_encrypted", False):
        try:
            reader.decrypt("")  # best-effort for "no-password" encryption
        except Exception:
            pass

    try:
        total_pages = len(reader.pages)
    except Exception as exc:  # noqa: BLE001 - pypdf may error on encrypted/unsupported PDFs
        name = os.path.basename(pdf_path)
        msg = str(exc).strip().splitlines()[0] if str(exc).strip() else exc.__class__.__name__
        print(f"  WARN: Skipping PDF (unreadable pages): {name} ({msg})")
        print("        Tip: if it's AES-encrypted, install: pip install cryptography")
        return []

    n_pages = min(total_pages, max_pages)
    out = []
    for i in range(n_pages):
        try:
            text = reader.pages[i].extract_text() or ''
        except Exception:
            continue

        text = text.replace('\u00ad', '')  # soft hyphen
        text = text.replace('\x00', ' ')
        text = text.replace('\r', '\n')
        if len(text) < 40:
            continue

        for chunk in re.split(r'\n{1,}', text):
            chunk = re.sub(r'\s+', ' ', chunk).strip()
            if len(chunk) < 24:
                continue
            for sent in SENT_SPLIT_RE.split(chunk):
                sent = re.sub(r'\s+', ' ', sent).strip()
                if not _is_good_sentence(sent):
                    continue
                out.append({'text': sent, 'page': i + 1})

    return out


def build(lang: str, max_pages: int, max_sentences: int):
    resource_dir = RESOURCE_DIRS.get(lang)
    if not resource_dir or not os.path.isdir(resource_dir):
        print(f"  WARN: Resource folder not found for {lang}: {resource_dir}")
        return []

    sentences = []
    seen = set()

    pdfs = list(iter_pdfs(resource_dir))
    if not pdfs:
        print(f"  WARN: No PDFs found in {resource_dir}")
        return []

    for idx, pdf in enumerate(pdfs, start=1):
        base = os.path.basename(pdf)
        print(f"[{lang}] {idx}/{len(pdfs)} {base}")
        extracted = extract_sentences_from_pdf(pdf, max_pages=max_pages)
        kept = 0
        for s in extracted:
            s_text = s.get('text') or ''
            norm = _norm_sentence(s_text)
            if not norm or norm in seen:
                continue
            seen.add(norm)
            sentences.append({
                'text': s_text,
                'source': base,
                'page': s.get('page'),
            })
            kept += 1
            if len(sentences) >= max_sentences:
                print(f"  Reached max sentences ({max_sentences}) for {lang}.")
                return sentences
        print(f"  +{kept} sentences")

    return sentences


def main() -> int:
    parser = argparse.ArgumentParser(description="Build data/resource_sentences.json from local PDF resources.")
    parser.add_argument('--lang', choices=['all', 'french', 'spanish'], default='all', help="Language to process.")
    parser.add_argument('--max-pages', type=int, default=40, help="Max pages to read per PDF (default: 40).")
    parser.add_argument('--max-sentences', type=int, default=5000, help="Max sentences per language (default: 5000).")
    parser.add_argument('--out', default=os.path.join(DATA_DIR, 'resource_sentences.json'), help="Output JSON path.")
    args = parser.parse_args()

    os.makedirs(DATA_DIR, exist_ok=True)

    langs = ['french', 'spanish'] if args.lang == 'all' else [args.lang]
    payload = {
        '_meta': {
            'generated_at': datetime.now().isoformat(timespec='seconds'),
            'max_pages_per_pdf': args.max_pages,
            'max_sentences_per_lang': args.max_sentences,
        }
    }

    for lang in langs:
        payload[lang] = build(lang, max_pages=args.max_pages, max_sentences=args.max_sentences)

    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"\nSaved: {args.out}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
