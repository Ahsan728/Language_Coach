/* =============================================
   Language Coach — Main JavaScript
   ============================================= */

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
    fetch('/api/word_progress', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({language: LANG, word: cards[currentIdx].word, correct: known ? 1 : 0})
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
   INIT on page load
   =============================================== */
document.addEventListener('DOMContentLoaded', () => {
  // Flashcards page
  if (typeof VOCAB !== 'undefined') initFlashcards();
  // Quiz page
  if (typeof QUESTIONS !== 'undefined' && QUESTIONS.length > 0) initQuiz();

  // Animate progress bars on dashboard
  document.querySelectorAll('.progress-bar').forEach(bar => {
    const target = bar.style.width;
    bar.style.width = '0%';
    setTimeout(() => { bar.style.width = target; }, 300);
  });
});
