# 🌍 Language Coach — ভাষা শিক্ষক

> **Learn French & Spanish through Bengali and English — locally, interactively, step by step.**
> বাংলা ও ইংরেজির মাধ্যমে ফরাসি ও স্প্যানিশ শিখুন — স্থানীয়ভাবে, ইন্টারেক্টিভ পদ্ধতিতে, ধাপে ধাপে।

---

## 📸 Overview

A fully local language learning web application built in Python (Flask). Designed for Bengali/English speakers learning French and Spanish — covering vocabulary, grammar, and tenses with explanations in both Bengali and English. Inspired by Duolingo, aligned with the CEFR framework (A1 → A2 → B1 → B2).

| Feature | Details |
|---------|---------|
| 🇧🇩 Teaching language | Bengali + English |
| 🇫🇷 Target 1 | French (Français) — 28 lessons, CEFR A1–B1 |
| 🇪🇸 Target 2 | Spanish (Español) — 28 lessons, CEFR A1–B1 |
| 📖 Vocabulary | ~946 words per language across 27 categories |
| 📚 Grammar | Articles, Tenses, SER vs ESTAR — explained in Bengali |
| 🃏 Flashcards | Interactive flip cards with SRS tracking |
| 🧠 Quizzes | Multiple-choice with instant feedback + scoring |
| ⚡ Daily Practice | Duolingo-like mix: 🔊 listening, ✅ MCQ, ⌨️ typing, 🧩 sentence ordering |
| 🎧 Dictation | Hear a word → type what you heard (accent-tolerant) |
| 🔁 Spaced Repetition | Leitner box SRS: due-words review, weak-word review |
| 🔊 Pronunciation | Browser Text-to-Speech — no server API, works offline |
| 🔥 Streak + XP | Daily activity tracking with streak counter |
| 📊 Progress | Saved locally in SQLite (auto-created on first run) |

---

## 🚀 Quick Start

### Option 1 — Double Click (Windows)
Simply double-click **`start.bat`** in the project folder.
The browser will open automatically at `http://localhost:5000`.

### Option 2 — Command Line
```bash
# Install dependencies (first time only)
pip install -r requirements.txt

# Run the app
python app.py
```
Then open your browser at **http://localhost:5000**

---

## 🗂️ Project Structure

```
Language Coach/
│
├── app.py                  # Flask backend — routes, quiz/practice logic, SRS API
├── requirements.txt        # Python dependencies (flask, pypdf)
├── start.bat               # One-click Windows launcher
│
├── data/
│   ├── vocabulary.json     # ~946 words per language: Bengali + English + pronunciation + examples
│   ├── lessons.json        # 28 lessons per language with CEFR levels, grammar + quiz questions
│   └── progress.db         # SQLite database (auto-created on first run; local per user)
│
├── templates/              # Jinja2 HTML templates
│   ├── base.html           # Navbar, layout, footer
│   ├── dashboard.html      # Home page with streak/XP/progress overview + CEFR roadmap
│   ├── language.html       # Lesson list grouped by CEFR level (A1 / A2 / B1 / B2)
│   ├── lesson.html         # Lesson content: vocabulary cards + grammar tables + TTS buttons
│   ├── flashcard.html      # Interactive flip-card practice with SRS tracking
│   ├── quiz.html           # Multiple-choice quiz with scoring
│   ├── practice.html       # Daily Practice (Duolingo-like: listen/MCQ/type/order)
│   ├── dictation.html      # Dictation: hear a word → type it (auto-plays TTS)
│   ├── vocabulary.html     # Full vocabulary explorer with search + category filter
│   ├── resources.html      # Curated external learning resources
│   └── progress.html       # Full progress table for both languages
│
├── static/
│   ├── css/style.css       # Custom styles (French blue / Spanish red + CEFR badge colours)
│   └── js/app.js           # All JS: flashcards, quiz, practice, dictation, TTS, vocab explorer
│
└── scripts/
    └── validate_content.py # Content validation for lessons/vocab JSON
```

---

## 📚 Lesson Plan — CEFR Structure

Lessons are organized by **CEFR level** and stored in `data/lessons.json`.

| Level | Lessons | Topics |
|-------|---------|--------|
| 🟢 **A1** — Elementary | 1–12, 15, 25–27 | Greetings, Numbers, Colors, Days, Family, Body, Food, Transport, Verbs, Adjectives, Grammar (Articles + Present), Phrases, Nationalities, Daily Activities, Hobbies |
| 🔵 **A2** — Pre-intermediate | 13, 14, 16–22, 24, 28 | Grammar (Past + Future Tenses), Health, Home, Sports, Nature, Work, Shopping, People, Travel, Emotions |
| 🟠 **B1** — Intermediate | 23 | Food & Cooking Advanced |
| 🔴 **B2** — Upper Intermediate | — | Coming soon |

Aligned with **DELF** (French) and **DELE** (Spanish) international exam frameworks.

Each lesson references vocabulary categories from `data/vocabulary.json`.
The app **auto-reloads JSON** when files change — edit content while the server is running.

---

## 🎯 How to Use

### 1. Start a Lesson
- Go to **🇫🇷 Français** or **🇪🇸 Español** from the navigation bar
- Lessons are grouped by CEFR level: 🟢 A1 → 🔵 A2 → 🟠 B1
- Click any lesson card to open it — vocabulary cards show TTS 🔊, English, Bengali, and example sentences

### 2. Daily Practice ⚡ (Duolingo-like)
- Click **⚡ Practice** from the lesson list or dashboard
- Mixed exercises drawn from your spaced-repetition due words:
  - 🔊 **Listening** — TTS auto-plays, choose the correct meaning
  - ✅ **Multiple Choice** — choose the right word or translation
  - ⌨️ **Typing** — type the target-language word from an English prompt
  - 🧩 **Sentence Ordering** — tap words to build the correct sentence
- Earn **XP** and track your daily **streak** 🔥

### 3. Dictation Practice 🎧 *(NEW)*
- Click **🎧 Dictation** from the lesson sidebar
- Each word **auto-plays via TTS** — listen, then type what you heard
- Press **L** to replay at any time; press **Enter** to submit
- Accents are optional: `e` = `é` — both accepted
- After answering, see the correct word with pronunciation, English, and Bengali
- Higher XP than other exercises (dictation is the hardest skill!)

### 4. Review Due Words 🔁
- Click **🃏 Review** from the lesson list or dashboard
- Uses **Leitner-box spaced repetition** — words resurface based on how well you know them
- Box 1 = review tomorrow | Box 5 = review in 2 weeks

### 5. Flashcards 🃏
- Click **Flashcards** from any lesson
- Flip cards to reveal translations — mark **"I Know It!"** ✓ or **"Need Review"** ✗
- Keyboard shortcuts: `Space`/`Enter` = flip · `→` = next · `K` = know · `J` = review
- Results feed the spaced repetition system

### 6. Quiz 🧠
- Click **Take Quiz** from any lesson
- Multiple-choice: word → English · English → word · word → Bengali · grammar questions
- Score is saved; lessons are marked complete at 60%+

### 7. Vocabulary Explorer 📖
- Click **📖 Vocabulary** from the lesson list
- Search across the full vocabulary (target language, English, বাংলা)
- Filter by category · TTS listen button on every word card

### 8. Track Your Progress 📊
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
```

---

## 🔧 Configuration

The app runs on `http://localhost:5000` by default.

- Change port: set the `PORT` environment variable.
  - PowerShell: `$env:PORT=8000`
  - cmd.exe: `set PORT=8000`

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

#### Step 6 — Reload & visit
Web tab → green **Reload** button → your app is live at `https://ahsan728.pythonanywhere.com`

---

### 🥈 Option B — Render (Easy GitHub Auto-Deploy)

**Why:** Pushes to GitHub auto-deploy · Free · Sleeps after 15 min inactivity (30–50s to wake)
> ⚠️ SQLite resets on sleep — vocabulary and lessons work perfectly; quiz scores don't persist between sessions.

| Setting | Value |
|---------|-------|
| **Runtime** | Python 3 |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn app:app` |
| **Instance Type** | Free |

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
