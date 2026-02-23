# 🌍 Language Coach — ভাষা শিক্ষক

> **Learn French & Spanish through Bengali and English — locally, interactively, step by step.**
> বাংলা ও ইংরেজির মাধ্যমে ফরাসি ও স্প্যানিশ শিখুন — স্থানীয়ভাবে, ইন্টারেক্টিভ পদ্ধতিতে, ধাপে ধাপে।

---

## 📸 Overview

A fully local language learning web application built in Python (Flask). Designed for Bengali/English speakers learning French and Spanish — covering vocabulary, grammar, and tenses with explanations in both Bengali and English. Inspired by Duolingo, aligned with the CEFR framework (A1 → A2 → B1 → B2).

| Feature | Details |
|---------|---------|
| 🇧🇩 Teaching language | Bengali + English |
| 🇫🇷 Target 1 | French (Français) — 50 lessons, CEFR A1–B2 |
| 🇪🇸 Target 2 | Spanish (Español) — 50 lessons, CEFR A1–B2 |
| 📖 Vocabulary | French: 4,394 words · Spanish: 4,120 words (28 categories each) |
| 📚 Grammar | CEFR‑aligned grammar + examples (Bengali + English explanations) |
| 🃏 Flashcards | Interactive flip cards with SRS tracking |
| 🧠 Quizzes | Multiple-choice with instant feedback + scoring |
| ⚡ Daily Practice | Duolingo-like mix: 🔊 listening, ✅ MCQ, ⌨️ typing, 🧩 sentence ordering |
| 🎧 Dictation | Hear a word → type what you heard (accent-tolerant) |
| 🎯 Placement Test | Quick CEFR-based test to estimate your level (A1–B2) |
| 🗣️ Speaking | Speak into your mic and match words/phrases (browser speech recognition) |
| 🔁 Spaced Repetition | Leitner box SRS: due-words review, weak-word review |
| 📄 Lesson PDFs | Download any lesson as a PDF (Bengali font-safe) |
| 🔊 Pronunciation | Browser TTS by default + optional server TTS (gTTS) for consistent accent online |
| 🔎 Translate & Listen | Mini dictionary/translator on the home page with audio |
| 💬 Feedback | Built-in feedback box (saved locally + optional Google Sheets logging) |
| 🌐 Resources | Curated external links + study notes |
| 🔥 Streak + XP | Daily activity tracking with streak counter |
| 📊 Progress | Saved locally in SQLite (auto-created on first run) |
| 🔐 Login | You can browse freely, but lessons + placement test require email-only sign-in (no password) |

---

## 🚀 Quick Start

### Option 1 — Double Click (Windows)
Simply double-click **`start.bat`** in the project folder.
The browser will open automatically at `http://localhost:5000`.

### Option 2 — Command Line
```bash
# Install dependencies (first time only)
pip install -r requirements.txt

# (Recommended) Install Chromium for PDF lesson downloads (best Bengali rendering)
python -m playwright install chromium

# Run the app
python app.py
```
Then open your browser at **http://localhost:5000**

> Note: PDF downloads use Playwright/Chromium by default. If you can’t install Chromium, set `PDF_ENGINE=reportlab` (PDF quality may be lower for Bengali text).

---

## Online Deployment (Server TTS)

To make pronunciation work for everyone online (even if a user has no Spanish/French voice installed), use server-side TTS:

- Procfile deployments: server TTS is enabled by default (gTTS).
- Other hosts: set `TTS_PROVIDER=gtts` in your environment variables.
- Optional (recommended): set `TTS_CACHE_DIR` to a writable (or persistent) folder to cache generated MP3s.

Notes:
- gTTS requires outbound internet access from your server and sends text to Google to generate audio.
- If server TTS fails, the app automatically falls back to browser TTS.

## Local Resources (PDFs + Links)

- Add your learning PDFs/links into `French Resources/` and `Spanish Resources/` (kept local; ignored by Git).
- Build the sentence index (optional, safe to re-run after adding new PDFs):
  - `python scripts/build_resource_sentences.py`
- This creates `data/resource_sentences.json` (local-only; ignored by Git).
- The app uses this file to power **Resource Drill** on the dashboard and extra **Context** questions in **Daily Practice** (your PDFs are not served in the web UI).

## Auto-push to GitHub (Optional)

Automatically commit + push whenever files change locally:

- Check what will be committed: `git status`
- Double-click (Windows): `scripts/auto_push.bat`
- Watch mode: `powershell -ExecutionPolicy Bypass -File scripts/auto_push.ps1`
- One-time sync: `powershell -ExecutionPolicy Bypass -File scripts/auto_push_once.ps1`
- Stop watch mode with `Ctrl+C`

Notes:
- Requires your GitHub auth to be set up for `git push` (HTTPS token or SSH).
- Resource folders and generated caches are ignored by default (see `.gitignore`).

## Google Sheets (Optional: Users + Feedback)

If you want to keep a live Google Spreadsheet of:

- Users (name/email + progress snapshot)
- Lesson completion events
- Feedback / problem reports

Set up the Apps Script webhook and env vars described in:

- `docs/google_sheets.md`

## 🗂️ Project Structure

```
Language Coach/
│
├── app.py                  # Flask backend — routes, lessons/quizzes/practice, PDFs, Sheets logging
├── requirements.txt        # Python dependencies
├── start.bat               # One-click Windows launcher
├── Procfile                # Gunicorn start command for some hosts
├── wsgi.py                 # PythonAnywhere entrypoint
├── .env.example            # Copy → .env (do not commit .env)
├── docs/
│   └── google_sheets.md    # Apps Script webhook setup (optional)
├── Dictionaries/           # (Ignored by Git) source PDF dictionaries (vocab extraction)
├── French Resources/       # (Ignored by Git) your French PDFs/links
├── Spanish Resources/      # (Ignored by Git) your Spanish PDFs/links
│
├── data/
│   ├── lessons.json        # 50 lessons per language (CEFR A1–B2)
│   ├── vocabulary.json     # 4k+ words per language (Bengali + English + pronunciation + examples)
│   ├── resource_sentences.json # (Optional, local-only) extracted sentences for Context practice
│   ├── progress.db         # (Local-only) SQLite database (auto-created on first run)
│   └── tts_cache/          # (Local-only) cached MP3s for server TTS
│
├── templates/              # Jinja2 HTML templates
│   ├── base.html           # Navbar, layout, footer
│   ├── dashboard.html      # Home page: streak/XP + translate + quick start
│   ├── login.html          # Email-only sign-in
│   ├── language.html       # Lesson list grouped by CEFR + placement promo
│   ├── placement.html      # Placement test (A1–B2)
│   ├── lesson.html         # Lesson content + PDF download + speaking/dictation/quiz links
│   ├── flashcard.html      # Flashcards + SRS tracking
│   ├── quiz.html           # Lesson quiz with scoring
│   ├── practice.html       # Daily Practice (listen/MCQ/type/order/context)
│   ├── dictation.html      # Dictation (TTS → type)
│   ├── speaking.html       # Speaking (mic → match)
│   ├── vocabulary.html     # Vocabulary explorer (search + categories)
│   ├── resources.html      # Curated external resources
│   └── progress.html       # Progress dashboard/table
│
├── static/
│   ├── css/style.css       # Custom styles (French blue / Spanish red + CEFR badge colours)
│   └── js/app.js           # All JS: flashcards, quiz, practice, dictation, speaking, TTS, UI
│
└── scripts/
    ├── build_resource_sentences.py # Build Context sentence index from PDFs
    ├── validate_content.py         # Content validation for lessons/vocab JSON
    ├── auto_push.ps1               # Auto commit+push (watch mode)
    ├── auto_push_once.ps1          # One-time sync
    └── auto_push.bat               # Windows helper (double-click)
```

---

## 📚 Lesson Plan — CEFR Structure

Lessons are organized by **CEFR level** and stored in `data/lessons.json`.

| Level | Lessons | Topics |
|-------|---------|--------|
| 🟢 **A1** — Elementary | 17 (per language) | Survival basics: alphabet/pronunciation, greetings, numbers, time, family, food, daily life, core grammar |
| 🔵 **A2** — Pre-intermediate | 11 (per language) | Practical topics: home, health, travel, shopping + past/future grammar foundations |
| 🟠 **B1** — Intermediate | 12 (per language) | Longer conversations: routines, opinions, stories + intermediate grammar and vocabulary |
| 🔴 **B2** — Upper Intermediate | 10 (per language) | More complex grammar and real‑life topics (upper‑intermediate practice) |

Aligned with **DELF** (French) and **DELE** (Spanish) international exam frameworks.

Each lesson references vocabulary categories from `data/vocabulary.json`.
The app **auto-reloads JSON** when files change — edit content while the server is running.

---

## 🎯 How to Use

### 0. Sign in (email-only)
- You can browse most pages without an account.
- When you open a **Lesson** or the **Placement Test**, the app asks you to sign in with **email only** (no password).
- This is required to save progress per user.

### 1. Take the Placement Test 🎯 (recommended)
- From a language page, click **Placement Test**.
- You’ll get an estimated CEFR level (A1–B2) and a **Start from my level** button.

### 2. Start a Lesson
- Open any lesson card to view **Vocabulary + Grammar** (Bengali + English explanations).
- Use the **PDF download** button to export the lesson.

### 3. Daily Practice ⚡ (Duolingo-like)
- Click **⚡ Practice** from the lesson list or dashboard
- Mixed exercises drawn from your spaced-repetition due words:
  - 🔊 **Listening** — TTS auto-plays, choose the correct meaning
  - ✅ **Multiple Choice** — choose the right word or translation
  - ⌨️ **Typing** — type the target-language word from an English prompt
  - 🧩 **Sentence Ordering** — tap words to build the correct sentence
  - 📚 **Context** — extra questions based on your local PDFs (if `data/resource_sentences.json` exists)
- Earn **XP** and track your daily **streak** 🔥

### 4. Speaking Practice 🗣️
- Click **🗣️ Speaking** from a lesson.
- Speak the word/phrase into your mic and match it.
  - Works best in **Chrome / Edge** (Web Speech API).
  - Microphone access requires **HTTPS** (or `localhost`).

### 5. Dictation Practice 🎧
- Click **🎧 Dictation** from a lesson
- Each word **auto-plays via TTS** — listen, then type what you heard
- Press **L** to replay at any time; press **Enter** to submit
- Accents are optional: `e` = `é` — both accepted
- After answering, see the correct word with pronunciation, English, and Bengali
- Higher XP than other exercises (dictation is the hardest skill!)

### 6. Review Due Words 🔁
- Click **🃏 Review** from the lesson list or dashboard
- Uses **Leitner-box spaced repetition** — words resurface based on how well you know them
- Box 1 = review tomorrow | Box 5 = review in 2 weeks

### 7. Flashcards 🃏
- Click **Flashcards** from any lesson
- Flip cards to reveal translations — mark **"I Know It!"** ✓ or **"Need Review"** ✗
- Keyboard shortcuts: `Space`/`Enter` = flip · `→` = next · `K` = know · `J` = review
- Results feed the spaced repetition system

### 8. Quiz 🧠
- Click **Take Quiz** from any lesson
- Multiple-choice: word → English · English → word · word → Bengali · grammar questions
- Score is saved; lessons are marked complete at 60%+

### 9. Vocabulary Explorer 📖
- Click **📖 Vocabulary** from the lesson list
- Search across the full vocabulary (target language, English, বাংলা)
- Filter by category · TTS listen button on every word card

### 10. Translate & Listen 🔎
- On the home page, use the built-in **Translate & Listen** box to quickly look up words and play audio.

### 11. Feedback 💬
- Use the **Feedback** button in the navbar to send suggestions/problems.
- Messages are saved locally and can be forwarded to Google Sheets (optional).

### 12. Track Your Progress 📊
- Click **Progress** in the navbar
- See completed lessons, best scores, attempt counts, and progress bars per language

---

## 🗣️ Language Notes

### French Tips
- `bonjour` = hello/good morning | `bonsoir` = good evening
- Numbers 70–99 are irregular: `soixante-dix` (70), `quatre-vingts` (80)
- Every noun has gender (masculine/feminine) — memorize with the article!
- Past tense uses `avoir` OR `être` as helper verb
- Nationalities never capitalize in French: `Je suis français`

### Spanish Tips
- **SER** = permanent identity (`Soy de Bangladesh` — I am from Bangladesh)
- **ESTAR** = temporary state (`Estoy cansado` — I am tired)
- `mañana` means BOTH "tomorrow" AND "morning" — context decides!
- Reflexive verbs for daily routine: `me levanto`, `me ducho`, `me acuesto`
- Gustar-type verbs: `Me gusta viajar` · `Me encantan los libros`

---

## 🛠️ Requirements

- **Python 3.8+** (Python 3.13 tested ✓)
- **Internet** — only for Bootstrap & fonts (CDN); all learning content works offline
- **Windows 10/11** recommended (for `start.bat`); works on Linux/Mac too

### Python packages
```
 flask>=3.0.0
 pypdf>=4.0.0
 cryptography>=3.1
 gunicorn>=21.0.0
 gTTS>=2.5.0
 reportlab>=4.0.0
 playwright>=1.42.0
```

---

## 🔧 Configuration

The app runs on `http://localhost:5000` by default.

### Recommended: use a `.env` file (local)

Create `.env` in the project root (same folder as `app.py`). See `.env.example`.

```env
# Security (required for real deployments)
SECRET_KEY=PASTE_A_RANDOM_SECRET_HERE

# Optional: Google Sheets logging (Apps Script webhook)
# SHEETS_WEBHOOK_URL=PASTE_WEB_APP_URL_HERE
# SHEETS_WEBHOOK_TOKEN=PASTE_TOKEN_HERE

# Optional: PDF engine ("chromium" or "reportlab")
# PDF_ENGINE=chromium
```

 - Change port: set the `PORT` environment variable.
    - PowerShell: `$env:PORT=8000`
    - cmd.exe: `set PORT=8000`

 - Server-side TTS (same pronunciation for everyone): set `TTS_PROVIDER=gtts`.
   - PowerShell: `$env:TTS_PROVIDER='gtts'`
   - cmd.exe: `set TTS_PROVIDER=gtts`
   - Audio is cached under `data/tts_cache/` (first play generates; next plays are instant).

 ---

## ☁️ Deployment — Share with Friends

Two recommended free options. **PythonAnywhere is the best choice** — always online, no sleep, SQLite data persists.

---

### 🥇 Option A — PythonAnywhere (Recommended — Free, Always On)

**Why:** Free forever · No spin-down · SQLite persists · 500 MB storage

#### Step 1 — Sign up
Go to [www.pythonanywhere.com](https://www.pythonanywhere.com) → **Create a Beginner account** (free)

#### Step 2 — Open a Bash console
Dashboard → **Consoles** → **Bash** → Start

#### Step 3 — Clone your repo
```bash
git clone https://github.com/Ahsan728/Language_Coach.git
cd Language_Coach
pip install -r requirements.txt --user
```
> If your repo is private, you must use a GitHub PAT/SSH so PythonAnywhere can clone it.

#### Step 4 — Create the Web App
Dashboard → **Web** → **Add a new web app** → **Manual configuration** → **Python 3.10**

#### Step 5 — Configure the WSGI file
Click the **WSGI configuration file** link and replace the contents with:
```python
import sys, os
project_home = '/home/ahsan728/Language_Coach'
if project_home not in sys.path:
    sys.path.insert(0, project_home)
from app import app as application
```
> ⚠️ Replace `ahsan728` with your actual PythonAnywhere username

#### Step 6 — Set environment variables (important)
Web tab → **Environment variables**:

- `SECRET_KEY` = *(required)* random long string (keeps login sessions secure)
- Optional:
  - `SHEETS_WEBHOOK_URL`, `SHEETS_WEBHOOK_TOKEN` (Google Sheets logging)
  - `TTS_PROVIDER=gtts` (server voice for everyone)
  - `PDF_ENGINE=reportlab` *(recommended on PythonAnywhere)* for lesson PDFs

#### Step 7 — Reload & visit
Web tab → green **Reload** button → your app is live at `https://ahsan728.pythonanywhere.com`

---

### 🥈 Option B — Render (Easy GitHub Auto-Deploy)

**Why:** Pushes to GitHub auto-deploy · Free · Sleeps after 15 min inactivity (30–50s to wake)
> ⚠️ On free tiers, storage may be ephemeral — vocabulary and lessons work perfectly, but quiz scores may not persist unless you add persistent storage or a real database.

| Setting | Value |
|---------|-------|
| **Runtime** | Python 3 |
| **Build Command** | `pip install -r requirements.txt && python -m playwright install chromium --with-deps` |
| **Start Command** | `gunicorn app:app` |
| **Instance Type** | Free |

Environment variables (Render dashboard):
- `SECRET_KEY` *(required)*
- Optional: `SHEETS_WEBHOOK_URL`, `SHEETS_WEBHOOK_TOKEN`, `TTS_PROVIDER=gtts`, `PDF_ENGINE=chromium|reportlab`

Every `git push` triggers an automatic redeploy.

---

### Comparison

| | PythonAnywhere | Render |
|--|---------------|--------|
| Cost | Free forever | Free |
| Always online | ✅ Yes | ⚠️ Sleeps 15 min |
| SQLite persists | ✅ Yes | ❌ Resets on sleep |
| Auto-deploy from GitHub | Manual pull | ✅ Automatic |
| Best for | Permanent sharing | Quick demos |

---

### 🔄 Updating the live app

**PythonAnywhere:**
```bash
cd ~/Language_Coach && git pull
```
Then reload from the **Web** tab.

**Render:** just `git push` — deploys automatically within ~2 minutes.

---

## 👨‍🎓 About This Project

Built for a Bengali-speaking PhD student in Spain learning French and Spanish.
Vocabulary sourced and curated from bilingual visual dictionaries and CEFR-aligned course materials.

**Teaching philosophy:**
Bengali → English bridge → French/Spanish target
বাংলা → ইংরেজি সেতু → ফরাসি/স্প্যানিশ লক্ষ্য

---

## 📄 License

This project is for personal educational use.

---

*Made with ❤️ for language learners — ভাষা শিক্ষার্থীদের জন্য তৈরি*
