/* =============================================
   Language Coach — Main JavaScript
   ============================================= */

/* ===============================================
   PRONUNCIATION (TTS)
   =============================================== */

// Cache voices once they're available (Chrome loads them async)
let _ttsVoices = [];

function _loadVoices() {
  const vs = window.speechSynthesis ? window.speechSynthesis.getVoices() : [];
  if (vs.length) _ttsVoices = vs;
}

if ('speechSynthesis' in window) {
  _loadVoices();
  window.speechSynthesis.addEventListener('voiceschanged', _loadVoices);
}

function speakText(text, langTag) {
  if (!text) return;
  const synth = window.speechSynthesis;
  if (!synth) return;

  // Chrome bug: after inactivity the engine gets stuck in "paused" state.
  // resume() first, then cancel(), then speak() — this order is reliable.
  try { synth.resume(); } catch { /* noop */ }
  synth.cancel();

  const u = new SpeechSynthesisUtterance(String(text));
  u.rate = 0.9;

  if (langTag) {
    u.lang = langTag;
    // Explicitly pick the best available voice so Chrome doesn't fall back
    // to the wrong language or stay silent
    if (_ttsVoices.length) {
      const prefix = langTag.split('-')[0];
      u.voice = _ttsVoices.find(v => v.lang === langTag)
             || _ttsVoices.find(v => v.lang.startsWith(prefix))
             || null;
    }
  }

  // Small delay so cancel() fully clears before the next utterance starts
  setTimeout(() => {
    try { synth.speak(u); } catch { /* noop */ }
  }, 50);
}

function langToTtsTag(lang) {
  if (lang === 'french') return 'fr-FR';
  if (lang === 'spanish') return 'es-ES';
  return '';
}

/* ===============================================
   FLASHCARD MODULE
   =============================================== */
let cards = [];
let currentIdx = 0;
let isFlipped = false;
let knownCount = 0;
let unknownCount = 0;
let results = [];

function initFlashcards() {
  if (typeof VOCAB === 'undefined') return;
  cards = [...VOCAB];
  currentIdx = 0;
  knownCount = 0;
  unknownCount = 0;
  results = new Array(cards.length).fill(null);
  showCard(0);
}

function showCard(idx) {
  if (!cards || cards.length === 0) return;
  const card = cards[idx];
  const fc = document.getElementById('flashcard');
  if (!fc) return;

  // Reset flip
  isFlipped = false;
  fc.classList.remove('flipped');
  document.getElementById('flashActions').style.display = 'none';

  // Front
  document.getElementById('cardWord').textContent = card.word;
  document.getElementById('cardPron').textContent = card.pronunciation || '';

  // Back
  document.getElementById('cardEnglish').textContent = card.english;
  document.getElementById('cardBengali').textContent = card.bengali;
  const exDiv = document.getElementById('cardExample');
  if (card.example) {
    exDiv.innerHTML = `<em>${card.example}</em><br><small>${card.example_en}</small><br><small class="bengali-text">${card.example_bn}</small>`;
  } else {
    exDiv.innerHTML = '';
  }

  // Counter
  document.getElementById('cardCounter').textContent = `Card ${idx + 1} of ${cards.length}`;
  document.getElementById('flashProgress').style.width = `${Math.round((idx / cards.length) * 100)}%`;
  document.getElementById('prevBtn').disabled = idx === 0;
  document.getElementById('knownCount').textContent = `✓ ${knownCount} Known`;
  document.getElementById('unknownCount').textContent = `✗ ${unknownCount} Review`;

  // Completion check
  const allAnswered = results.every(r => r !== null);
  document.getElementById('completionBox').style.display = allAnswered ? 'block' : 'none';
}

function flipCard() {
  const fc = document.getElementById('flashcard');
  if (!fc) return;
  isFlipped = !isFlipped;
  fc.classList.toggle('flipped', isFlipped);
  document.getElementById('flashActions').style.display = isFlipped ? 'flex' : 'none';
}

function listenFlashcard() {
  if (!cards || !cards[currentIdx]) return;
  const tag = (typeof LANG !== 'undefined') ? langToTtsTag(LANG) : '';
  speakText(cards[currentIdx].word, tag);
}

function markCard(known) {
  if (results[currentIdx] === null) {
    if (known) knownCount++;
    else unknownCount++;
  } else if (results[currentIdx] === true && !known) {
    knownCount--;
    unknownCount++;
  } else if (results[currentIdx] === false && known) {
    unknownCount--;
    knownCount++;
  }
  results[currentIdx] = known;

  // Track word progress
  if (typeof LANG !== 'undefined') {
    const xp = known ? 5 : 2;
    fetch('/api/word_progress', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({language: LANG, word: cards[currentIdx].word, correct: known ? 1 : 0, source: 'flashcards', xp})
    });
  }

  nextCard();
}

function nextCard() {
  if (currentIdx < cards.length - 1) {
    currentIdx++;
    showCard(currentIdx);
  } else {
    showCard(currentIdx);
    const all = results.every(r => r !== null);
    document.getElementById('completionBox').style.display = all ? 'block' : 'none';
  }
}

function prevCard() {
  if (currentIdx > 0) {
    currentIdx--;
    showCard(currentIdx);
  }
}

function shuffleCards() {
  cards = [...cards].sort(() => Math.random() - 0.5);
  results = new Array(cards.length).fill(null);
  knownCount = 0;
  unknownCount = 0;
  currentIdx = 0;
  showCard(0);
  document.getElementById('completionBox').style.display = 'none';
}

function restartCards() {
  cards = [...VOCAB];
  results = new Array(cards.length).fill(null);
  knownCount = 0;
  unknownCount = 0;
  currentIdx = 0;
  showCard(0);
  document.getElementById('completionBox').style.display = 'none';
}

/* ===============================================
   QUIZ MODULE
   =============================================== */
let quizIdx = 0;
let correctTotal = 0;
let wrongTotal = 0;
let currentQuizQuestion = null;
let quizTtsText = null;
let quizTtsLang = null;

function quizListen() {
  speakText(quizTtsText, quizTtsLang);
}

function initQuiz() {
  if (typeof QUESTIONS === 'undefined' || QUESTIONS.length === 0) return;
  quizIdx = 0;
  correctTotal = 0;
  wrongTotal = 0;
  showQuestion(0);
}

function showQuestion(idx) {
  const q = QUESTIONS[idx];
  if (!q) return;
  currentQuizQuestion = q;

  quizTtsText = q.tts_text || null;
  quizTtsLang = q.tts_lang || (typeof LANG !== 'undefined' ? langToTtsTag(LANG) : null);
  const listenBtn = document.getElementById('quizListenBtn');
  if (listenBtn) listenBtn.style.display = quizTtsText ? '' : 'none';

  document.getElementById('quizCard').style.display = '';
  document.getElementById('resultsCard').style.display = 'none';
  document.getElementById('feedbackBox').style.display = 'none';

  document.getElementById('qCounter').textContent = `Question ${idx + 1} of ${TOTAL_Q}`;
  document.getElementById('quizProgress').style.width = `${Math.round((idx / TOTAL_Q) * 100)}%`;
  document.getElementById('questionEn').innerHTML = q.question_en;
  document.getElementById('questionBn').innerHTML = q.question_bn;
  document.getElementById('qNum').textContent = `Question ${idx + 1}`;
  document.getElementById('scoreDisplay').textContent = `Score: ${correctTotal}`;

  const grid = document.getElementById('choicesGrid');
  grid.innerHTML = '';
  q.choices.forEach(choice => {
    const btn = document.createElement('button');
    btn.className = 'choice-btn';
    btn.innerHTML = choice;
    btn.onclick = () => selectAnswer(choice, q.correct, btn);
    grid.appendChild(btn);
  });
}

function selectAnswer(chosen, correct, btn) {
  // Disable all buttons
  document.querySelectorAll('.choice-btn').forEach(b => { b.disabled = true; });

  const q = currentQuizQuestion || {};
  const isCorrect = chosen === correct;
  const fb = document.getElementById('feedbackBox');
  fb.style.display = 'block';

  if (isCorrect) {
    btn.classList.add('correct');
    correctTotal++;
    fb.className = 'feedback-box correct-fb';
    document.getElementById('feedbackIcon').textContent = '✅';
    document.getElementById('feedbackText').innerHTML = `<strong>সঠিক! Correct!</strong> <br><span class="small text-muted">${correct}</span>`;
  } else {
    btn.classList.add('wrong');
    // Highlight correct answer
    document.querySelectorAll('.choice-btn').forEach(b => {
      if (b.innerHTML === correct) b.classList.add('revealed');
    });
    wrongTotal++;
    fb.className = 'feedback-box wrong-fb';
    document.getElementById('feedbackIcon').textContent = '❌';
    document.getElementById('feedbackText').innerHTML = `<strong>ভুল হয়েছে! Wrong!</strong><br><span class="small">Correct answer: <strong>${correct}</strong></span>`;
  }

  document.getElementById('scoreDisplay').textContent = `Score: ${correctTotal}`;

  // Track word progress for vocab questions
  if (q.kind === 'vocab' && q.word && typeof LANG !== 'undefined') {
    const xp = isCorrect ? 8 : 1;
    fetch('/api/word_progress', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({language: LANG, word: q.word, correct: isCorrect ? 1 : 0, source: 'quiz', xp})
    });
  }

  // Show next button
  const nextBtn = document.getElementById('nextQBtn');
  if (nextBtn) {
    if (quizIdx >= TOTAL_Q - 1) {
      nextBtn.textContent = 'See Results 🏆';
    } else {
      nextBtn.textContent = 'Next Question →';
    }
  }
}

function nextQuestion() {
  quizIdx++;
  if (quizIdx >= TOTAL_Q) {
    showResults();
  } else {
    showQuestion(quizIdx);
  }
}

function showResults() {
  document.getElementById('quizCard').style.display = 'none';
  const res = document.getElementById('resultsCard');
  res.style.display = 'block';
  res.scrollIntoView({behavior: 'smooth', block: 'start'});

  const total = correctTotal + wrongTotal;
  const pct = total > 0 ? Math.round((correctTotal / total) * 100) : 0;

  let emoji, title, titleBn;
  if (pct >= 90)       { emoji = '🏆'; title = 'Excellent!';   titleBn = 'অসাধারণ! আপনি দারুণ করেছেন!'; }
  else if (pct >= 70)  { emoji = '🎉'; title = 'Great Job!';   titleBn = 'চমৎকার! আরও একটু চেষ্টা করুন!'; }
  else if (pct >= 50)  { emoji = '👍'; title = 'Good Effort!'; titleBn = 'ভালো চেষ্টা! আবার অভ্যাস করুন।'; }
  else                 { emoji = '📚'; title = 'Keep Practicing!'; titleBn = 'আরও অভ্যাস করুন — আপনি পারবেন!'; }

  document.getElementById('resultEmoji').textContent = emoji;
  document.getElementById('resultTitle').textContent = title;
  document.getElementById('resultBn').textContent = titleBn;
  document.getElementById('finalScore').innerHTML = `<span class="${pct >= 70 ? 'text-success' : pct >= 50 ? 'text-warning' : 'text-danger'}">${pct}%</span>`;
  document.getElementById('correctCount').textContent = correctTotal;
  document.getElementById('wrongCount').textContent = wrongTotal;
  document.getElementById('totalCount').textContent = total;

  // Save progress
  if (typeof LANG !== 'undefined' && typeof LESSON_ID !== 'undefined') {
    fetch('/api/complete', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({language: LANG, lesson_id: LESSON_ID, score: pct})
    });
  }
}

function restartQuiz() {
  quizIdx = 0;
  correctTotal = 0;
  wrongTotal = 0;
  showQuestion(0);
  document.getElementById('resultsCard').style.display = 'none';
  document.getElementById('quizCard').style.display = '';
}

/* ===============================================
   PRACTICE MODULE (Duolingo-like)
   =============================================== */
let practiceIdx = 0;
let practiceHearts = 3;
let practiceXp = 0;
let practiceCorrect = 0;
let practiceWrong = 0;
let currentPracticeQuestion = null;
let practiceTtsText = null;
let practiceTtsLang = null;
let practiceAnswered = false;
let practiceOrderAnswer = [];

function practiceListen() {
  speakText(practiceTtsText, practiceTtsLang);
}

function normalizeAnswer(str) {
  return String(str || '')
    .toLowerCase()
    .trim()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function answerVariants(answer) {
  const a = String(answer || '').trim();
  const out = new Set([a]);

  // Handle gender variants like "argentino/a" -> ["argentino", "argentina"]
  const m = a.match(/^(.+?)([oa])\/([oa])$/i);
  if (m) {
    out.add(m[1] + m[2]);
    out.add(m[1] + m[3]);
  }

  return Array.from(out).map(normalizeAnswer).filter(Boolean);
}

function renderPractice(idx) {
  if (typeof PRACTICE_QUESTIONS === 'undefined' || PRACTICE_QUESTIONS.length === 0) return;
  const q = PRACTICE_QUESTIONS[idx];
  if (!q) return;
  currentPracticeQuestion = q;
  practiceAnswered = false;
  practiceOrderAnswer = [];

  const total = PRACTICE_QUESTIONS.length;
  document.getElementById('practiceCounter').textContent = `Question ${idx + 1} of ${total}`;
  document.getElementById('practiceProgress').style.width = `${Math.round((idx / total) * 100)}%`;

  const heartsEl = document.getElementById('practiceHearts');
  heartsEl.textContent = '♥'.repeat(Math.max(0, practiceHearts));

  document.getElementById('practiceXp').textContent = `XP: ${practiceXp}`;
  document.getElementById('practiceMode').textContent = q.mode_label || q.mode || '';
  document.getElementById('practicePromptEn').textContent = q.prompt_en || '';
  document.getElementById('practicePromptBn').textContent = q.prompt_bn || '';

  practiceTtsText = q.tts_text || null;
  const lang = (typeof PRACTICE_LANG !== 'undefined') ? PRACTICE_LANG : null;
  practiceTtsLang = q.tts_lang || (lang ? langToTtsTag(lang) : null);
  const listenBtn = document.getElementById('practiceListenBtn');
  if (listenBtn) listenBtn.style.display = practiceTtsText ? '' : 'none';

  // Reset UI
  document.getElementById('practiceFeedback').style.display = 'none';
  const choices = document.getElementById('practiceChoices');
  choices.innerHTML = '';
  const typeWrap = document.getElementById('practiceTypeWrap');
  typeWrap.style.display = 'none';
  document.getElementById('practiceHintBn').textContent = '';
  const orderWrap = document.getElementById('practiceOrderWrap');
  orderWrap.style.display = 'none';
  document.getElementById('practiceOrderAnswer').innerHTML = '';
  document.getElementById('practiceOrderBank').innerHTML = '';

  // Auto-play TTS for listening exercises
  if (q.mode === 'listen_to_english' && practiceTtsText) {
    setTimeout(() => speakText(practiceTtsText, practiceTtsLang), 400);
  }

  if (q.kind === 'type') {
    typeWrap.style.display = 'block';
    const input = document.getElementById('practiceTypeInput');
    input.value = '';
    input.focus();
    if (q.hint_bn) document.getElementById('practiceHintBn').textContent = `Hint (বাংলা): ${q.hint_bn}`;
    return;
  }

  if (q.kind === 'order') {
    orderWrap.style.display = 'block';

    const answerEl = document.getElementById('practiceOrderAnswer');
    const bankEl = document.getElementById('practiceOrderBank');
    answerEl.innerHTML = `<span class="text-muted small">Tap words to build the sentence…</span>`;

    (q.tokens || []).forEach((tok, i) => {
      const btn = document.createElement('button');
      btn.className = 'btn btn-sm btn-light border';
      btn.type = 'button';
      btn.textContent = tok;
      btn.dataset.tokenIndex = String(i);
      btn.onclick = () => {
        if (practiceAnswered) return;
        btn.disabled = true;
        practiceOrderAnswer.push({i, tok});
        renderPracticeOrderAnswer();
      };
      bankEl.appendChild(btn);
    });

    return;
  }

  // MCQ choices
  (q.choices || []).forEach((choice) => {
    const btn = document.createElement('button');
    btn.className = 'choice-btn';
    btn.textContent = choice;
    btn.onclick = () => practiceSelect(choice, btn);
    choices.appendChild(btn);
  });
}

function practiceShowFeedback(isCorrect, correctAnswer) {
  const fb = document.getElementById('practiceFeedback');
  fb.style.display = 'block';
  fb.className = `feedback-box ${isCorrect ? 'correct-fb' : 'wrong-fb'}`;

  document.getElementById('practiceFeedbackIcon').textContent = isCorrect ? '✅' : '❌';
  const extra = currentPracticeQuestion && currentPracticeQuestion.hint_bn ? `<br><small class="bengali-text text-muted">বাংলা: ${currentPracticeQuestion.hint_bn}</small>` : '';
  document.getElementById('practiceFeedbackText').innerHTML =
    isCorrect
      ? `<strong>Correct!</strong>${extra}`
      : `<strong>Wrong.</strong><br><span class="small">Correct answer: <strong>${correctAnswer}</strong></span>${extra}`;

  const nextBtn = document.getElementById('practiceNextBtn');
  const last = practiceIdx >= PRACTICE_QUESTIONS.length - 1;
  nextBtn.textContent = last ? 'See Results 🏁' : 'Next →';
}

function practiceRecord(isCorrect) {
  const q = currentPracticeQuestion || {};
  const lang = (typeof PRACTICE_LANG !== 'undefined') ? PRACTICE_LANG : null;
  const xpCorrect = Number.isFinite(q.xp_correct) ? q.xp_correct : 10;
  const xpWrong = Number.isFinite(q.xp_wrong) ? q.xp_wrong : 2;
  const xpDelta = isCorrect ? xpCorrect : xpWrong;

  if (isCorrect) {
    practiceCorrect++;
    practiceXp += xpDelta;
  } else {
    practiceWrong++;
    practiceHearts = Math.max(0, practiceHearts - 1);
    practiceXp += xpDelta;
  }

  document.getElementById('practiceXp').textContent = `XP: ${practiceXp}`;
  document.getElementById('practiceHearts').textContent = '♥'.repeat(Math.max(0, practiceHearts));

  if (lang && q.word) {
    fetch('/api/word_progress', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({language: lang, word: q.word, correct: isCorrect ? 1 : 0, source: 'practice', xp: xpDelta})
    });
  }
}

function practiceSelect(choice, btn) {
  if (practiceAnswered) return;
  practiceAnswered = true;

  const q = currentPracticeQuestion || {};
  const isCorrect = choice === q.answer;

  // Disable all buttons + color
  document.querySelectorAll('#practiceChoices .choice-btn').forEach(b => { b.disabled = true; });
  btn.classList.add(isCorrect ? 'correct' : 'wrong');
  document.querySelectorAll('#practiceChoices .choice-btn').forEach(b => {
    if (b.textContent === q.answer) b.classList.add('revealed');
  });

  practiceRecord(isCorrect);
  practiceShowFeedback(isCorrect, q.answer);
}

function practiceSubmitType() {
  if (practiceAnswered) return;
  practiceAnswered = true;

  const q = currentPracticeQuestion || {};
  const input = document.getElementById('practiceTypeInput');
  const got = normalizeAnswer(input.value);
  const expected = answerVariants(q.answer);
  const isCorrect = expected.includes(got);

  practiceRecord(isCorrect);
  practiceShowFeedback(isCorrect, q.answer);
}

function renderPracticeOrderAnswer() {
  const answerEl = document.getElementById('practiceOrderAnswer');
  if (!answerEl) return;
  if (practiceOrderAnswer.length === 0) {
    answerEl.innerHTML = `<span class="text-muted small">Tap words to build the sentence…</span>`;
    return;
  }
  answerEl.innerHTML = '';
  practiceOrderAnswer.forEach(({i, tok}) => {
    const chip = document.createElement('button');
    chip.type = 'button';
    chip.className = 'btn btn-sm btn-light border';
    chip.textContent = tok;
    chip.onclick = () => {
      if (practiceAnswered) return;
      // remove this token and re-enable in bank
      practiceOrderAnswer = practiceOrderAnswer.filter(x => x.i !== i);
      const bankBtn = document.querySelector(`#practiceOrderBank button[data-token-index="${i}"]`);
      if (bankBtn) bankBtn.disabled = false;
      renderPracticeOrderAnswer();
    };
    answerEl.appendChild(chip);
  });
}

function practiceOrderClear() {
  if (practiceAnswered) return;
  practiceOrderAnswer = [];
  document.querySelectorAll('#practiceOrderBank button').forEach(b => { b.disabled = false; });
  renderPracticeOrderAnswer();
}

function practiceSubmitOrder() {
  if (practiceAnswered) return;
  practiceAnswered = true;

  const q = currentPracticeQuestion || {};
  const got = practiceOrderAnswer.map(x => x.tok).join(' ');
  const gotNorm = normalizeAnswer(got);
  const expectedNorm = normalizeAnswer(q.answer || q.sentence || '');
  const isCorrect = gotNorm === expectedNorm;

  // Disable bank
  document.querySelectorAll('#practiceOrderBank button').forEach(b => { b.disabled = true; });

  practiceRecord(isCorrect);
  practiceShowFeedback(isCorrect, q.answer || q.sentence || '');
}

function practiceNext() {
  if (practiceHearts <= 0) {
    showPracticeResults();
    return;
  }

  practiceIdx++;
  if (practiceIdx >= PRACTICE_QUESTIONS.length) {
    showPracticeResults();
  } else {
    renderPractice(practiceIdx);
  }
}

function showPracticeResults() {
  document.getElementById('practiceCard').style.display = 'none';
  const res = document.getElementById('practiceResults');
  res.style.display = 'block';
  res.scrollIntoView({behavior: 'smooth', block: 'start'});

  const total = practiceCorrect + practiceWrong;
  const pct = total > 0 ? Math.round((practiceCorrect / total) * 100) : 0;

  let emoji = '🎉';
  let title = 'Great job!';
  let titleBn = 'দারুণ! প্রতিদিন একটু করে প্র্যাকটিস করুন।';
  if (practiceHearts <= 0) {
    emoji = '❤️';
    title = 'Out of hearts';
    titleBn = 'হার্ট শেষ — তবে আপনি ভালোই চেষ্টা করেছেন!';
  } else if (pct >= 90) {
    emoji = '🏆';
    title = 'Excellent!';
    titleBn = 'অসাধারণ!';
  } else if (pct >= 70) {
    emoji = '🎉';
    title = 'Great!';
    titleBn = 'চমৎকার!';
  }

  document.getElementById('practiceResultEmoji').textContent = emoji;
  document.getElementById('practiceResultTitle').textContent = title;
  document.getElementById('practiceResultBn').textContent = titleBn;
  document.getElementById('practiceResultScore').innerHTML =
    `<span class="${pct >= 70 ? 'text-success' : pct >= 50 ? 'text-warning' : 'text-danger'}">${pct}%</span><div class="small text-muted mt-2">${practiceCorrect}/${total} correct • XP ${practiceXp}</div>`;
}

function initPractice() {
  if (typeof PRACTICE_QUESTIONS === 'undefined' || PRACTICE_QUESTIONS.length === 0) return;
  practiceIdx = 0;
  practiceHearts = 3;
  practiceXp = 0;
  practiceCorrect = 0;
  practiceWrong = 0;
  currentPracticeQuestion = null;
  renderPractice(0);

  document.addEventListener('keydown', (e) => {
    const tag = (e.target && e.target.tagName) ? e.target.tagName.toLowerCase() : '';
    if (tag === 'input' || tag === 'textarea' || e.isComposing) return;

    if (e.key.toLowerCase() === 'l') {
      practiceListen();
      return;
    }

    const feedback = document.getElementById('practiceFeedback');
    const feedbackVisible = feedback && feedback.style.display !== 'none';
    if (feedbackVisible && e.key === 'Enter') {
      e.preventDefault();
      practiceNext();
      return;
    }

    const q = currentPracticeQuestion || {};
    if (q.kind === 'type' && e.key === 'Enter') {
      e.preventDefault();
      practiceSubmitType();
      return;
    }
    if (q.kind === 'order' && e.key === 'Enter') {
      e.preventDefault();
      practiceSubmitOrder();
      return;
    }

    const n = parseInt(e.key, 10);
    if (!Number.isFinite(n) || n < 1 || n > 4) return;
    const buttons = Array.from(document.querySelectorAll('#practiceChoices .choice-btn'));
    const btn = buttons[n - 1];
    if (btn && !btn.disabled) {
      e.preventDefault();
      btn.click();
    }
  });
}

/* ===============================================
   DICTATION MODULE
   =============================================== */
let dictationIdx = 0;
let dictationCorrect = 0;
let dictationWrong = 0;
let dictationAnswered = false;
let currentDictationItem = null;

function dictationListen() {
  if (!currentDictationItem) return;
  speakText(currentDictationItem.tts_text, currentDictationItem.tts_lang);
}

function renderDictation(idx) {
  if (typeof DICTATION_ITEMS === 'undefined' || DICTATION_ITEMS.length === 0) return;
  const item = DICTATION_ITEMS[idx];
  if (!item) return;
  currentDictationItem = item;
  dictationAnswered = false;

  const total = DICTATION_ITEMS.length;
  document.getElementById('dictationCounter').textContent = `Word ${idx + 1} of ${total}`;
  document.getElementById('dictationProgress').style.width = `${Math.round((idx / total) * 100)}%`;

  document.getElementById('dictationWordReveal').style.display = 'none';
  document.getElementById('dictationFeedback').style.display = 'none';

  const input = document.getElementById('dictationInput');
  if (input) { input.value = ''; input.disabled = false; input.focus(); }

  const submitBtn = document.getElementById('dictationSubmitBtn');
  if (submitBtn) submitBtn.disabled = false;

  // Auto-play TTS after a short delay so the page has settled
  setTimeout(() => dictationListen(), 350);
}

function dictationSubmit() {
  if (dictationAnswered) return;
  dictationAnswered = true;

  const item = currentDictationItem || {};
  const input = document.getElementById('dictationInput');
  const got = normalizeAnswer(input ? input.value : '');
  const expected = answerVariants(item.word);
  const isCorrect = expected.includes(got);

  if (isCorrect) dictationCorrect++;
  else dictationWrong++;

  if (input) input.disabled = true;
  const submitBtn = document.getElementById('dictationSubmitBtn');
  if (submitBtn) submitBtn.disabled = true;

  // Feedback
  const fb = document.getElementById('dictationFeedback');
  fb.style.display = 'block';
  fb.className = `feedback-box mt-4 ${isCorrect ? 'correct-fb' : 'wrong-fb'}`;
  document.getElementById('dictationFeedbackIcon').textContent = isCorrect ? '✅' : '❌';
  document.getElementById('dictationFeedbackText').innerHTML = isCorrect
    ? `<strong>Correct!</strong> — <strong>${item.word}</strong>`
    : `<strong>Wrong.</strong> The word was: <strong>${item.word}</strong>`;

  // Reveal word details
  document.getElementById('dictationWordReveal').style.display = 'block';
  document.getElementById('dictationRevealWord').textContent = item.word;
  document.getElementById('dictationRevealPron').textContent = item.pronunciation || '';
  document.getElementById('dictationRevealEn').textContent = item.english || '';
  document.getElementById('dictationRevealBn').textContent = item.bengali || '';

  // Update score badge
  const total = dictationCorrect + dictationWrong;
  document.getElementById('dictationScore').textContent = `${dictationCorrect} / ${total}`;

  // SRS tracking — dictation is the hardest exercise so XP is higher
  const lang = (typeof DICTATION_LANG !== 'undefined') ? DICTATION_LANG : null;
  if (lang && item.word) {
    const xp = isCorrect ? 15 : 3;
    fetch('/api/word_progress', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({language: lang, word: item.word, correct: isCorrect ? 1 : 0, source: 'dictation', xp})
    });
  }

  const nextBtn = document.getElementById('dictationNextBtn');
  const last = dictationIdx >= DICTATION_ITEMS.length - 1;
  if (nextBtn) nextBtn.textContent = last ? 'See Results 🏁' : 'Next →';
}

function dictationNext() {
  dictationIdx++;
  if (dictationIdx >= DICTATION_ITEMS.length) {
    showDictationResults();
  } else {
    renderDictation(dictationIdx);
  }
}

function showDictationResults() {
  document.getElementById('dictationCard').style.display = 'none';
  const res = document.getElementById('dictationResults');
  res.style.display = 'block';
  res.scrollIntoView({behavior: 'smooth', block: 'start'});

  const total = dictationCorrect + dictationWrong;
  const pct = total > 0 ? Math.round((dictationCorrect / total) * 100) : 0;

  let emoji, title, titleBn;
  if (pct >= 90)      { emoji = '🏆'; title = 'Perfect Ear!';      titleBn = 'অসাধারণ! আপনার শোনার দক্ষতা দারুণ!'; }
  else if (pct >= 70) { emoji = '🎉'; title = 'Great Listening!';  titleBn = 'চমৎকার! আরও একটু চেষ্টা করুন।'; }
  else if (pct >= 50) { emoji = '👂'; title = 'Keep Listening!';   titleBn = 'ভালো চেষ্টা! আরও শুনুন ও অভ্যাস করুন।'; }
  else                { emoji = '📻'; title = 'Practice More!';     titleBn = 'আরও শুনুন — কান তৈরি হবে!'; }

  document.getElementById('dictationResultEmoji').textContent = emoji;
  document.getElementById('dictationResultTitle').textContent = title;
  document.getElementById('dictationResultBn').textContent = titleBn;
  document.getElementById('dictationResultScore').innerHTML =
    `<span class="${pct >= 70 ? 'text-success' : pct >= 50 ? 'text-warning' : 'text-danger'}">${pct}%</span>` +
    `<div class="small text-muted mt-2">${dictationCorrect}/${total} correct</div>`;
}

function initDictation() {
  if (typeof DICTATION_ITEMS === 'undefined' || DICTATION_ITEMS.length === 0) return;
  dictationIdx = 0;
  dictationCorrect = 0;
  dictationWrong = 0;
  dictationAnswered = false;
  renderDictation(0);

  document.addEventListener('keydown', (e) => {
    const tag = (e.target && e.target.tagName) ? e.target.tagName.toLowerCase() : '';
    if (e.isComposing) return;

    // L = replay (even inside input)
    if (e.key.toLowerCase() === 'l' && tag !== 'input') {
      dictationListen();
      return;
    }

    const feedback = document.getElementById('dictationFeedback');
    const feedbackVisible = feedback && feedback.style.display !== 'none';

    // Enter on feedback → go to next word
    if (feedbackVisible && e.key === 'Enter' && tag !== 'input') {
      e.preventDefault();
      dictationNext();
      return;
    }

    // Enter inside input → submit
    if (!dictationAnswered && tag === 'input' && e.key === 'Enter') {
      e.preventDefault();
      dictationSubmit();
    }
  });
}

/* ===============================================
   LESSON VOCAB FILTER
   =============================================== */
function filterLessonVocab() {
  const input = document.getElementById('vocabSearchInput');
  if (!input) return;

  const q = (input.value || '').trim().toLowerCase();
  const items = document.querySelectorAll('[data-vocab-item]');
  let visible = 0;

  items.forEach(item => {
    const hay = (item.getAttribute('data-vocab-search') || item.textContent || '').toLowerCase();
    const match = !q || hay.includes(q);
    item.style.display = match ? '' : 'none';
    if (match) visible++;
  });

  const countEl = document.getElementById('vocabSearchCount');
  if (countEl) {
    countEl.textContent = q ? `${visible} matching` : `${items.length} words`;
  }
}

/* ===============================================
   VOCABULARY EXPLORER
   =============================================== */
let vocabExplorerShowAll = false;

function escapeHtml(str) {
  return String(str || '').replace(/[&<>"']/g, m => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  }[m]));
}

function updatePracticeLink() {
  const select = document.getElementById('vocabCategory');
  const link = document.getElementById('practiceLink');
  if (!select || !link) return;

  const cat = select.value;
  if (!cat || cat === 'all') {
    link.classList.add('disabled');
    link.setAttribute('aria-disabled', 'true');
    link.href = '#';
    link.title = 'Select a category to practice';
    return;
  }

  link.classList.remove('disabled');
  link.removeAttribute('aria-disabled');
  link.title = '';

  if (typeof PRACTICE_URL_TEMPLATE !== 'undefined') {
    link.href = PRACTICE_URL_TEMPLATE.replace('__CAT__', encodeURIComponent(cat));
  } else if (typeof LANG !== 'undefined') {
    link.href = `/flashcards/category/${encodeURIComponent(LANG)}/${encodeURIComponent(cat)}`;
  }
}

function renderVocabExplorer() {
  if (typeof VOCAB_ALL === 'undefined') return;

  const listEl = document.getElementById('vocabList');
  const emptyEl = document.getElementById('vocabEmpty');
  const countEl = document.getElementById('vocabCount');
  const showAllWrap = document.getElementById('vocabShowAllWrap');
  const showAllBtn = document.getElementById('vocabShowAllBtn');
  const searchEl = document.getElementById('vocabSearch');
  const catEl = document.getElementById('vocabCategory');

  if (!listEl || !searchEl || !catEl) return;

  const q = (searchEl.value || '').trim().toLowerCase();
  const cat = catEl.value || 'all';
  const langClass = (typeof LANG !== 'undefined' && LANG === 'french') ? 'text-french' : 'text-spanish';

  let filtered = Array.isArray(VOCAB_ALL) ? VOCAB_ALL : [];
  if (cat !== 'all') filtered = filtered.filter(w => w.category === cat);
  if (q) {
    filtered = filtered.filter(w => {
      const hay = `${w.word || ''} ${w.english || ''} ${w.bengali || ''} ${w.pronunciation || ''}`.toLowerCase();
      return hay.includes(q);
    });
  }

  const total = filtered.length;
  const limit = vocabExplorerShowAll ? total : Math.min(total, 200);
  const shown = filtered.slice(0, limit);

  listEl.innerHTML = shown.map(w => {
    const word = escapeHtml(w.word);
    const english = escapeHtml(w.english);
    const bengali = escapeHtml(w.bengali);
    const pron = escapeHtml(w.pronunciation);
    const catLabel = escapeHtml((w.category || '').replace(/_/g, ' '));

    return `
      <div class="col-md-6 col-lg-4">
        <div class="vocab-card card border-0 shadow-sm h-100">
          <div class="card-body p-3">
            <div class="d-flex justify-content-between align-items-start">
              <div class="vocab-word fw-bold fs-5 ${langClass}">${word}</div>
              <div class="d-flex gap-2 align-items-start">
                <button class="btn btn-sm btn-light border btn-listen vocab-listen" type="button" title="Listen" aria-label="Listen"
                        data-tts="${word}">
                  <i class="fas fa-volume-up"></i>
                </button>
                ${pron ? `<span class="pron-badge">${pron}</span>` : `<span></span>`}
              </div>
            </div>
            <div class="vocab-english mt-1">🇬🇧 ${english}</div>
            <div class="vocab-bengali bengali-text mt-1">🇧🇩 ${bengali}</div>
            ${catLabel ? `<div class="mt-2"><span class="badge text-bg-light border">${catLabel}</span></div>` : ``}
          </div>
        </div>
      </div>
    `;
  }).join('');

  // Attach listen buttons (re-render replaces elements, so this stays cheap)
  const tag = (typeof LANG !== 'undefined') ? langToTtsTag(LANG) : '';
  listEl.querySelectorAll('.vocab-listen').forEach(btn => {
    btn.onclick = () => speakText(btn.dataset.tts, tag);
  });

  if (emptyEl) emptyEl.style.display = total === 0 ? 'block' : 'none';

  if (showAllWrap) {
    showAllWrap.style.display = (!vocabExplorerShowAll && total > limit) ? 'block' : 'none';
  }
  if (showAllBtn) {
    showAllBtn.textContent = `Show all results (${total})`;
  }

  if (countEl) {
    if (!q && cat === 'all') countEl.textContent = `${VOCAB_ALL.length} total words`;
    else if (total === 0) countEl.textContent = 'No matches';
    else if (!vocabExplorerShowAll && total > limit) countEl.textContent = `Showing ${limit} of ${total}`;
    else countEl.textContent = `Showing ${total}`;
  }
}

function initVocabExplorer() {
  if (typeof VOCAB_ALL === 'undefined') return;
  const searchEl = document.getElementById('vocabSearch');
  const catEl = document.getElementById('vocabCategory');
  const showAllBtn = document.getElementById('vocabShowAllBtn');

  if (!searchEl || !catEl) return;

  vocabExplorerShowAll = false;
  updatePracticeLink();
  renderVocabExplorer();

  searchEl.addEventListener('input', () => {
    vocabExplorerShowAll = false;
    renderVocabExplorer();
  });
  catEl.addEventListener('change', () => {
    vocabExplorerShowAll = false;
    updatePracticeLink();
    renderVocabExplorer();
  });
  if (showAllBtn) {
    showAllBtn.addEventListener('click', () => {
      vocabExplorerShowAll = true;
      renderVocabExplorer();
    });
  }
}

/* ===============================================
   KEYBOARD SHORTCUTS
   =============================================== */
function attachFlashcardShortcuts() {
  if (!document.getElementById('flashcard')) return;

  document.addEventListener('keydown', (e) => {
    const tag = (e.target && e.target.tagName) ? e.target.tagName.toLowerCase() : '';
    if (tag === 'input' || tag === 'textarea' || e.isComposing) return;

    if (e.key === ' ' || e.key === 'Enter') {
      e.preventDefault();
      flipCard();
    } else if (e.key === 'ArrowRight') {
      e.preventDefault();
      nextCard();
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      prevCard();
    } else if (e.key.toLowerCase() === 'k') {
      e.preventDefault();
      markCard(true);
    } else if (e.key.toLowerCase() === 'j') {
      e.preventDefault();
      markCard(false);
    }
  });
}

function attachQuizShortcuts() {
  if (!document.getElementById('choicesGrid')) return;

  document.addEventListener('keydown', (e) => {
    const tag = (e.target && e.target.tagName) ? e.target.tagName.toLowerCase() : '';
    if (tag === 'input' || tag === 'textarea' || e.isComposing) return;

    const feedback = document.getElementById('feedbackBox');
    const feedbackVisible = feedback && feedback.style.display !== 'none';

    if (feedbackVisible && e.key === 'Enter') {
      e.preventDefault();
      nextQuestion();
      return;
    }

    const n = parseInt(e.key, 10);
    if (!Number.isFinite(n) || n < 1 || n > 4) return;

    const buttons = Array.from(document.querySelectorAll('.choice-btn'));
    const btn = buttons[n - 1];
    if (btn && !btn.disabled) {
      e.preventDefault();
      btn.click();
    }
  });
}

/* ===============================================
   INIT on page load
   =============================================== */
document.addEventListener('DOMContentLoaded', () => {
  // Flashcards page
  if (typeof VOCAB !== 'undefined') initFlashcards();
  // Quiz page
  if (typeof QUESTIONS !== 'undefined' && QUESTIONS.length > 0) initQuiz();
  // Practice page
  initPractice();
  // Dictation page
  initDictation();
  // Lesson vocab filter
  filterLessonVocab();
  // Vocabulary explorer page
  initVocabExplorer();
  // Keyboard shortcuts (only activate on relevant pages)
  attachFlashcardShortcuts();
  attachQuizShortcuts();

  // Animate progress bars on dashboard
  document.querySelectorAll('.progress-bar').forEach(bar => {
    const target = bar.style.width;
    bar.style.width = '0%';
    setTimeout(() => { bar.style.width = target; }, 300);
  });
});
