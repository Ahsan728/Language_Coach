# 🌍 Language Coach — ভাষা শিক্ষক

> **Learn French & Spanish through Bengali and English — locally, interactively, step by step.**
> বাংলা ও ইংরেজির মাধ্যমে ফরাসি ও স্প্যানিশ শিখুন — স্থানীয়ভাবে, ইন্টারেক্টিভ পদ্ধতিতে, ধাপে ধাপে।

---

## 📸 Overview

A fully local language learning web application built in Python (Flask). Designed for Bengali/English speakers learning French and Spanish — covering vocabulary, grammar, and tenses with explanations in both Bengali and English.

| Feature | Details |
|---------|---------|
| 🇧🇩 Teaching language | Bengali + English |
| 🇫🇷 Target 1 | French (Français) — 28+ lessons (CEFR-aligned) |
| 🇪🇸 Target 2 | Spanish (Español) — 28+ lessons (CEFR-aligned) |
| 📖 Vocabulary | 900+ words per language (Bengali + English + pronunciation + examples) |
| 📚 Grammar | Articles, Tenses, SER vs ESTAR |
| 🃏 Flashcards | Interactive flip cards |
| 🧠 Quizzes | Multiple-choice with instant feedback |
| ⚡ Daily Practice | Duolingo-like mix: listening, MCQ, typing, sentence ordering |
| 🧠 Spaced Repetition | “Due words” review (Leitner boxes) |
| 🔊 Pronunciation | Browser Text-to-Speech (no server API required) |
| 🔥 Streak + XP | Daily activity tracking |
| 📊 Progress | Saved locally in SQLite |

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
├── app.py                  # Flask backend — routes, quiz logic, progress API
├── requirements.txt        # Python dependencies (flask, pypdf)
├── start.bat               # One-click Windows launcher
│
├── data/
│   ├── vocabulary.json     # All words: French + Spanish with Bengali & English
│   ├── lessons.json        # Lessons (CEFR-aligned) with grammar + quiz questions
│   └── progress.db         # SQLite database (auto-created on first run; per-user)
│
├── templates/              # Jinja2 HTML templates
│   ├── base.html           # Navbar, layout, footer
│   ├── dashboard.html      # Home page with progress overview
│   ├── language.html       # Lesson list for French or Spanish
│   ├── lesson.html         # Lesson content: vocabulary cards + grammar tables
│   ├── flashcard.html      # Interactive flip-card practice
│   ├── quiz.html           # Multiple-choice quiz with scoring
│   ├── practice.html       # Daily Practice (Duolingo-like)
│   ├── vocabulary.html     # Vocabulary explorer (search + categories)
│   ├── resources.html      # Curated external learning resources
│   └── progress.html       # Full progress table for both languages
│
├── static/
│   ├── css/style.css       # Custom styles (French blue / Spanish red themes)
│   └── js/app.js           # Flashcards + quiz + daily practice + TTS
│
├── scripts/
│   └── validate_content.py # Content validation for lessons/vocab JSON
│
└── Dictionaries/           # Reference PDFs (not used in runtime)
    ├── French-English_Bilingual_Visual_Dictionary.pdf
    └── Spanish-English_Bilingual_Visual_Dictionary_2nd_Edition.pdf
```

---

## 📚 Lesson Plan

Lessons are organized by **CEFR level (A1 → A2 → B1)** and stored in `data/lessons.json`.
Each lesson references one or more vocabulary categories from `data/vocabulary.json`.

This project is designed to evolve day by day:
- Edit `data/lessons.json` / `data/vocabulary.json` while the server is running — the app auto-reloads JSON when files change.
- Validate your edits with: `python scripts/validate_content.py`

---

## 🎯 How to Use

### 1. Start a Lesson
- Go to **🇫🇷 Français** or **🇪🇸 Español** from the navigation bar
- Lessons are organized by CEFR level: A1 → A2 → B1 (more coming)
- Click any lesson card to open it

### 2. Daily Practice ⚡ (Duolingo-like)
- Click **Practice → Daily Practice**
- Mixed exercises: 🔊 listening, ✅ choices, ⌨️ typing, 🧩 sentence ordering
- Earn **XP** and keep your **streak**

### 3. Review Due Words 🧠
- Click **Practice → Review**
- Uses spaced repetition (Leitner boxes) to bring back words you’re due to review

### 4. Study Vocabulary
- Each lesson shows **vocabulary cards** with:
  - The word in French/Spanish
  - Pronunciation guide (e.g. `bohn-ZHOOR`)
  - 🇬🇧 English translation
  - 🇧🇩 Bengali translation
  - Example sentence in all 3 languages

### 5. Practice with Flashcards 🃏
- Click **Flashcards** from any vocabulary lesson
- Click the card to flip and see the translation
- Mark each card as **"I Know It!"** ✓ or **"Need Review"** ✗
- Use **Shuffle** to randomize the order

### 6. Test Yourself with Quiz 🧠
- Click **Take Quiz** from any lesson
- Answer multiple-choice questions:
  - Word → English meaning
  - English → French/Spanish word
  - Word → Bengali meaning
  - Grammar fill-in-the-blank questions
- See your score percentage at the end
- Results are saved automatically

### 7. Vocabulary Explorer 📖
- Click **Practice → Vocabulary**
- Search across French/Spanish, English, and বাংলা

### 8. Track Your Progress 📊
- Click **Progress** in the navbar
- See completed lessons, best scores, and attempt counts
- Progress bars show overall completion per language

---

## 🗣️ Key Language Notes

### French Tips
- `bonjour` = hello/good morning | `bonsoir` = good evening
- Numbers 70–99 are irregular: `soixante-dix` (70), `quatre-vingts` (80)
- Every noun has gender (masculine/feminine) — memorize with the article!
- Past tense uses `avoir` OR `être` as helper verb

### Spanish Tips
- **SER** = permanent identity (`Soy de Bangladesh` — I am from Bangladesh)
- **ESTAR** = temporary state (`Estoy cansado` — I am tired)
- `mañana` means BOTH "tomorrow" AND "morning" — context decides!
- Present tense: `yo` always ends in `-o` (hablo, como, vivo)

---

## 🛠️ Requirements

- **Python 3.8+** (Python 3.13 tested ✓)
- **Internet** — only needed to load Bootstrap & fonts (CSS/JS CDN)
- **Windows 10/11** recommended (for `start.bat`)
- Works on Linux/Mac too — just run `python app.py`

### Python packages
```
flask>=3.0.0
pypdf>=4.0.0
```

---

## 🔧 Configuration

The app runs on `http://localhost:5000` by default.

- Change port (recommended): set the `PORT` environment variable.
  - PowerShell: `$env:PORT=8000`
  - cmd.exe: `set PORT=8000`
- Or edit the `port` value in `app.py`.

---

---

## ☁️ Deployment — Share with Friends

Two recommended free options. **PythonAnywhere is the best choice** — always online, no sleep, SQLite data persists.

---

### 🥇 Option A — PythonAnywhere (Recommended — Free, Always On)

**Why:** Free forever · No spin-down · SQLite persists · 500 MB storage · Perfect for small groups

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
Dashboard → **Web** → **Add a new web app** →
- Click **Next** → choose **Manual configuration** → choose **Python 3.10**

#### Step 5 — Configure the WSGI file
In the Web tab, click the **WSGI configuration file** link (e.g. `/var/www/ahsan728_pythonanywhere_com_wsgi.py`)

**Delete everything** in that file and replace with:
```python
import sys, os
project_home = '/home/ahsan728/Language_Coach'
if project_home not in sys.path:
    sys.path.insert(0, project_home)
from app import app as application
```
> ⚠️ Replace `ahsan728` with your actual PythonAnywhere username

#### Step 6 — Reload & visit
Back in the **Web** tab → click the green **Reload** button

Your app will be live at:
```
https://ahsan728.pythonanywhere.com
```
Share this URL with your friends! 🎉

---

### 🥈 Option B — Render (Easy GitHub Auto-Deploy)

**Why:** Pushes to GitHub auto-deploy · Free · But sleeps after 15 min inactivity (30s to wake up)
> ⚠️ SQLite resets on sleep — friends' quiz progress won't be saved between sessions. Vocabulary and lessons work perfectly.

#### Step 1 — Sign up
Go to [render.com](https://render.com) → **Sign up with GitHub**

#### Step 2 — Create a Web Service
Dashboard → **New +** → **Web Service** → Connect **Ahsan728/Language_Coach**

#### Step 3 — Configure
| Setting | Value |
|---------|-------|
| **Runtime** | Python 3 |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn app:app` |
| **Instance Type** | Free |

#### Step 4 — Deploy
Click **Create Web Service** — Render builds and deploys automatically.

Your app URL will be:
```
https://language-coach.onrender.com   (or similar)
```

#### Auto-deploy on every push
Every time you run `git push`, Render **automatically redeploys** your app. No manual steps needed.

---

### Comparison

| | PythonAnywhere | Render |
|--|---------------|--------|
| Cost | Free forever | Free |
| Always online | ✅ Yes | ⚠️ Sleeps 15 min |
| SQLite persists | ✅ Yes | ❌ Resets on sleep |
| Auto-deploy from GitHub | Manual pull | ✅ Automatic |
| Custom domain | Paid plan | Free `.onrender.com` |
| Best for | Permanent sharing | Quick demos |

---

### 🔄 Updating the live app after code changes

**PythonAnywhere** — open a Bash console and run:
```bash
cd ~/Language_Coach
git pull
```
Then reload the web app from the **Web** tab.

**Render** — just push to GitHub:
```bash
git add .
git commit -m "your change"
git push
```
Render deploys automatically within ~2 minutes.

---

## 📈 Roadmap / Future Features

- [ ] Audio pronunciation (text-to-speech)
- [ ] Spaced repetition system (SRS) for vocabulary review
- [ ] More vocabulary categories (health, shopping, emotions)
- [ ] Sentence construction exercises
- [ ] Dictation practice
- [ ] Export progress report as PDF

---

## 👨‍🎓 About This Project

Built for a Bengali-speaking PhD student in Spain learning French and Spanish.
The app uses vocabulary sourced and curated from bilingual visual dictionaries.

**Teaching philosophy:**
Bengali → English bridge → French/Spanish target
বাংলা → ইংরেজি সেতু → ফরাসি/স্প্যানিশ লক্ষ্য

---

## 📄 License

This project is for personal educational use.

---

*Made with ❤️ for language learners — ভাষা শিক্ষার্থীদের জন্য তৈরি*
