#!/usr/bin/env python3
"""
scripts/cleanup_storage.py
=========================
Safe cleanup helpers for small free hosting tiers (e.g., PythonAnywhere).

What it cleans
--------------
1) gTTS MP3 cache under `data/tts_cache/` (or `TTS_CACHE_DIR`)
   - Deletes stale temp files (leftovers from crashes)
   - Deletes files older than `--tts-ttl-days`
   - Enforces `--tts-max-mb` and `--tts-max-files` caps (LRU-ish by atime/mtime)

2) Local debug artifacts under the project folder
   - `tmp_*.png`, `tmp_*.pdf`
   - `__pycache__/` and `*.pyc`

Usage
-----
    cd ~/Language_Coach
    python scripts/cleanup_storage.py --dry-run
    python scripts/cleanup_storage.py

Suggested PythonAnywhere Scheduled Task (daily)
----------------------------------------------
    python /home/<you>/Language_Coach/scripts/cleanup_storage.py
"""

import argparse
import os
import shutil
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _human(n: int) -> str:
    n = int(n or 0)
    units = ["B", "KB", "MB", "GB", "TB"]
    v = float(n)
    for u in units:
        if v < 1024 or u == units[-1]:
            return f"{v:.1f}{u}" if u != "B" else f"{int(v)}B"
        v /= 1024.0
    return f"{v:.1f}TB"


def _safe_unlink(path: Path, dry_run: bool) -> tuple[bool, int]:
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    if dry_run:
        return True, int(size or 0)
    try:
        path.unlink(missing_ok=True)
        return True, int(size or 0)
    except OSError:
        return False, 0


def _dir_size(path: Path) -> int:
    total = 0
    try:
        for p in path.rglob("*"):
            try:
                if p.is_file():
                    total += int(p.stat().st_size or 0)
            except OSError:
                continue
    except OSError:
        return total
    return total


def cleanup_tts_cache(
    cache_dir: Path,
    ttl_days: int,
    max_mb: int,
    max_files: int,
    min_age_sec: int,
    dry_run: bool,
) -> dict:
    now = time.time()
    ttl_sec = max(0, int(ttl_days)) * 86400
    max_bytes = max(0, int(max_mb)) * 1024 * 1024
    max_files = max(0, int(max_files))
    min_age_sec = max(0, int(min_age_sec))

    removed = 0
    removed_bytes = 0
    scanned = 0

    if not cache_dir.exists() or not cache_dir.is_dir():
        return {"ok": True, "scanned": 0, "removed": 0, "removed_bytes": 0, "path": str(cache_dir)}

    mp3_entries: list[tuple[float, int, Path]] = []  # (last_used, size, path)

    for p in cache_dir.iterdir():
        if not p.is_file():
            continue
        scanned += 1
        name = p.name.lower()
        try:
            st = p.stat()
        except OSError:
            continue
        mtime = float(st.st_mtime or 0.0)
        atime = float(getattr(st, "st_atime", 0.0) or 0.0)
        last_used = max(atime, mtime)
        age_m = now - mtime
        age_u = now - last_used

        if name.endswith(".tmp.mp3") or name.endswith(".tmp"):
            if age_m >= max(3600, min_age_sec):
                ok, freed = _safe_unlink(p, dry_run)
                if ok:
                    removed += 1
                    removed_bytes += freed
            continue

        if not name.endswith(".mp3"):
            continue

        if min_age_sec and age_u < min_age_sec:
            continue

        if ttl_sec and age_u > ttl_sec:
            ok, freed = _safe_unlink(p, dry_run)
            if ok:
                removed += 1
                removed_bytes += freed
            continue

        mp3_entries.append((last_used, int(st.st_size or 0), p))

    # Enforce caps (delete oldest first)
    mp3_entries.sort(key=lambda x: x[0])
    total_bytes = sum(s for _, s, __ in mp3_entries)
    total_files = len(mp3_entries)

    def over_caps(files: int, bytes_: int) -> bool:
        if max_files and files > max_files:
            return True
        if max_bytes and bytes_ > max_bytes:
            return True
        return False

    i = 0
    while i < len(mp3_entries) and over_caps(total_files, total_bytes):
        _, size, p = mp3_entries[i]
        ok, freed = _safe_unlink(p, dry_run)
        if ok:
            removed += 1
            removed_bytes += freed
            total_files -= 1
            total_bytes -= int(size or 0)
        i += 1

    return {
        "ok": True,
        "path": str(cache_dir),
        "scanned": scanned,
        "removed": removed,
        "removed_bytes": removed_bytes,
    }


def cleanup_project_debug_files(project_root: Path, dry_run: bool) -> dict:
    removed = 0
    removed_bytes = 0

    # Top-level tmp_* artifacts (kept out of git via .gitignore, but can fill server disk).
    for pat in ("tmp_*.png", "tmp_*.pdf"):
        for p in project_root.glob(pat):
            if not p.is_file():
                continue
            ok, freed = _safe_unlink(p, dry_run)
            if ok:
                removed += 1
                removed_bytes += freed

    # __pycache__ and *.pyc (project only)
    skip_dirs = {".git", "venv", ".venv", "env", "node_modules"}
    for root, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for d in list(dirs):
            if d == "__pycache__":
                path = Path(root) / d
                try:
                    size = _dir_size(path)
                except OSError:
                    size = 0
                if not dry_run:
                    try:
                        shutil.rmtree(path, ignore_errors=True)
                    except OSError:
                        pass
                removed += 1
                removed_bytes += int(size or 0)
        for f in files:
            if f.endswith(".pyc"):
                p = Path(root) / f
                ok, freed = _safe_unlink(p, dry_run)
                if ok:
                    removed += 1
                    removed_bytes += freed

    return {"ok": True, "path": str(project_root), "removed": removed, "removed_bytes": removed_bytes}


def main() -> int:
    parser = argparse.ArgumentParser(description="Cleanup TTS cache and local debug artifacts.")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be removed, but don't delete.")
    parser.add_argument("--project-root", default="", help="Project root (default: repo root).")
    parser.add_argument("--tts-cache-dir", default="", help="TTS cache dir (default: $TTS_CACHE_DIR or data/tts_cache).")
    parser.add_argument("--tts-ttl-days", type=int, default=45, help="Delete cached MP3s not used for N days (0 disables).")
    parser.add_argument("--tts-max-mb", type=int, default=80, help="Keep cache under N MB (0 disables).")
    parser.add_argument("--tts-max-files", type=int, default=5000, help="Keep at most N MP3 files (0 disables).")
    parser.add_argument("--tts-min-age-sec", type=int, default=120, help="Never delete files newer than N seconds.")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parents[1]
    project_root = Path(args.project_root).expanduser().resolve() if args.project_root else base_dir

    default_cache = os.environ.get("TTS_CACHE_DIR") or str(project_root / "data" / "tts_cache")
    cache_dir = Path(args.tts_cache_dir).expanduser().resolve() if args.tts_cache_dir else Path(default_cache).expanduser().resolve()

    print("== Cleanup ==")
    print(f"Dry run        : {bool(args.dry_run)}")
    print(f"Project root   : {project_root}")
    print(f"TTS cache dir  : {cache_dir}")
    print(f"TTS TTL days   : {args.tts_ttl_days}")
    print(f"TTS max MB     : {args.tts_max_mb}")
    print(f"TTS max files  : {args.tts_max_files}")
    print()

    tts_before = _dir_size(cache_dir) if cache_dir.exists() else 0
    tts = cleanup_tts_cache(
        cache_dir=cache_dir,
        ttl_days=args.tts_ttl_days,
        max_mb=args.tts_max_mb,
        max_files=args.tts_max_files,
        min_age_sec=args.tts_min_age_sec,
        dry_run=args.dry_run,
    )
    tts_after = _dir_size(cache_dir) if cache_dir.exists() else 0

    dbg = cleanup_project_debug_files(project_root=project_root, dry_run=args.dry_run)

    print("== Results ==")
    print(f"TTS cache: removed {tts['removed']} file(s), freed {_human(tts['removed_bytes'])}")
    if tts_before or tts_after:
        print(f"TTS cache: size {_human(tts_before)} -> {_human(tts_after)}")
    print(f"Project:  removed {dbg['removed']} item(s), freed {_human(dbg['removed_bytes'])}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

