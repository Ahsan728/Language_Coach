/* =============================================
   Language Coach — Main JavaScript
   ============================================= */

/* ===============================================
   PRONUNCIATION (TTS)
   =============================================== */

// Cache voices once they're available (Chrome loads them async)
let _ttsVoices = [];
let _ttsWarnedLangs = new Set();
let _ttsServerWarnedLangs = new Set();
let _ttsAutoplayWarned = false;

function _normalizeLangTag(tag) {
  return String(tag || '')
    .trim()
    .replace(/_/g, '-')
    .toLowerCase();
}

function _loadVoices() {
  const vs = window.speechSynthesis ? window.speechSynthesis.getVoices() : [];
  if (vs.length) _ttsVoices = vs;
}

if ('speechSynthesis' in window) {
  _loadVoices();
  window.speechSynthesis.onvoiceschanged = _loadVoices;
}

function _showTtsWarning(langName) {
  if (_ttsWarnedLangs.has(langName)) return;
  _ttsWarnedLangs.add(langName);

  // Only show once per language (per page load)
  const existing = document.getElementById('tts-warning-banner');
  if (existing) existing.remove();

  const banner = document.createElement('div');
  banner.id = 'tts-warning-banner';
  banner.style.cssText = [
    'position:fixed', 'bottom:1rem', 'left:50%', 'transform:translateX(-50%)',
    'z-index:9999', 'max-width:520px', 'width:calc(100% - 2rem)',
    'background:#fff3cd', 'border:1px solid #ffc107', 'border-radius:10px',
    'padding:.85rem 1.1rem', 'box-shadow:0 4px 20px rgba(0,0,0,.15)',
    'font-size:.875rem', 'line-height:1.5'
  ].join(';');

  banner.innerHTML = `
    <strong>🔇 No ${langName} voice installed</strong>
    <button onclick="this.closest('#tts-warning-banner').remove()"
            style="float:right;background:none;border:none;font-size:1.1rem;cursor:pointer;line-height:1">×</button>
    <div class="mt-1">
      Windows doesn't include French/Spanish voices by default, so your browser may fall back to English.<br>
      To fix: <strong>Settings → Time &amp; Language → Language &amp; Region
      → Add a language → pick ${langName} → tick "Text-to-speech"</strong>
      then restart the browser.
    </div>`;

  document.body.appendChild(banner);
}

function _showAutoplayWarning() {
  if (_ttsAutoplayWarned) return;
  _ttsAutoplayWarned = true;

  const existing = document.getElementById('tts-autoplay-banner');
  if (existing) existing.remove();

  const banner = document.createElement('div');
  banner.id = 'tts-autoplay-banner';
  banner.style.cssText = [
    'position:fixed', 'bottom:1rem', 'left:50%', 'transform:translateX(-50%)',
    'z-index:9999', 'max-width:520px', 'width:calc(100% - 2rem)',
    'background:#e7f1ff', 'border:1px solid #0d6efd', 'border-radius:10px',
    'padding:.85rem 1.1rem', 'box-shadow:0 4px 20px rgba(0,0,0,.15)',
    'font-size:.875rem', 'line-height:1.5'
  ].join(';');

  banner.innerHTML = `
    <strong>Audio autoplay blocked</strong>
    <button onclick="this.closest('#tts-autoplay-banner').remove()"
            style="float:right;background:none;border:none;font-size:1.1rem;cursor:pointer;line-height:1">Ã—</button>
    <div class="mt-1">
      Your browser blocked automatic audio playback. Click a <strong>ðŸ”Š Listen</strong> button (or press <strong>L</strong>) to play.
    </div>`;

  document.body.appendChild(banner);
}

let _ttsAudio = null;
let _ttsAudioObjectUrl = null;
let _serverTtsBackoffUntil = 0;

function _getTtsProvider() {
  return 'gtts';
}

function _hasBrowserVoiceFor(langTag) {
  const want = langTag ? _normalizeLangTag(langTag) : '';
  const wantPrefix = want.split('-')[0];
  if (!wantPrefix) return true;

  const synth = window.speechSynthesis;
  if (!synth) return false;

  // Refresh voice cache now (cheap, sync).
  try {
    const fresh = synth.getVoices();
    if (fresh.length) _ttsVoices = fresh;
  } catch { /* noop */ }

  return _ttsVoices.some(v => _normalizeLangTag(v.lang).startsWith(wantPrefix));
}

async function _speakTextServer(text, langTag) {
  const url = `/api/tts?lang=${encodeURIComponent(langTag || '')}&text=${encodeURIComponent(text || '')}`;
  const res = await fetch(url, {cache: 'force-cache'});
  if (!res.ok) {
    let detail = '';
    try { detail = (await res.text()) || ''; } catch { /* noop */ }
    const msg = detail ? `TTS HTTP ${res.status}: ${detail}` : `TTS HTTP ${res.status}`;
    throw new Error(msg);
  }

  const blob = await res.blob();

  if (_ttsAudioObjectUrl) {
    try { URL.revokeObjectURL(_ttsAudioObjectUrl); } catch { /* noop */ }
    _ttsAudioObjectUrl = null;
  }
  _ttsAudioObjectUrl = URL.createObjectURL(blob);

  if (!_ttsAudio) _ttsAudio = new Audio();
  try { _ttsAudio.pause(); _ttsAudio.currentTime = 0; } catch { /* noop */ }
  _ttsAudio.src = _ttsAudioObjectUrl;
  await _ttsAudio.play();
}

function _showServerTtsError(langName, details) {
  if (_ttsServerWarnedLangs.has(langName)) return;
  _ttsServerWarnedLangs.add(langName);

  const existing = document.getElementById('tts-server-banner');
  if (existing) existing.remove();

  const banner = document.createElement('div');
  banner.id = 'tts-server-banner';
  banner.style.cssText = [
    'position:fixed', 'bottom:1rem', 'left:50%', 'transform:translateX(-50%)',
    'z-index:9999', 'max-width:560px', 'width:calc(100% - 2rem)',
    'background:#f8d7da', 'border:1px solid #dc3545', 'border-radius:10px',
    'padding:.85rem 1.1rem', 'box-shadow:0 4px 20px rgba(0,0,0,.15)',
    'font-size:.875rem', 'line-height:1.5'
  ].join(';');

  const safeDetails = details ? escapeHtml(details) : '';
  banner.innerHTML = `
    <strong>🔊 Server TTS failed (${escapeHtml(langName)})</strong>
    <button onclick="this.closest('#tts-server-banner').remove()"
            style="float:right;background:none;border:none;font-size:1.1rem;cursor:pointer;line-height:1">×</button>
    <div class="mt-1">
      ${safeDetails ? `<div class="small text-muted">${safeDetails}</div>` : ``}
      If this keeps happening: check server internet access (gTTS), or install a local ${escapeHtml(langName)} voice.
    </div>`;

  document.body.appendChild(banner);
}

async function speakText(text, langTag, retryOnce = true) {
  if (!text) return;

  const provider = _getTtsProvider();
  const hasVoice = _hasBrowserVoiceFor(langTag);
  const wantPrefix = _normalizeLangTag(langTag || '').split('-')[0];
  const langName = wantPrefix === 'fr' ? 'French'
                 : wantPrefix === 'es' ? 'Spanish'
                 : (langTag || 'this language');

  const now = Date.now();
  const tryServer = async () => {
    const t = Date.now();
    if (t < _serverTtsBackoffUntil) return {ok: false, error: null};
    try {
      // Stop any in-progress browser speech to avoid overlap.
      if (window.speechSynthesis) window.speechSynthesis.cancel();
      await _speakTextServer(text, langTag);
      return {ok: true, error: null};
    } catch (e) {
      const name = (e && e.name) ? String(e.name) : '';
      if (name === 'NotAllowedError') {
        _showAutoplayWarning();
        return {ok: false, error: e};
      }
      console.warn('Server TTS failed:', e);
      _serverTtsBackoffUntil = Date.now() + 30000;
      return {ok: false, error: e};
    }
  };

  if (provider === 'browser') {
    _speakTextBrowser(text, langTag, retryOnce);
    return;
  }

  // Auto mode: use browser if a matching voice exists; otherwise use server TTS.
  if (provider === 'auto') {
    if (hasVoice) {
      _speakTextBrowser(text, langTag, retryOnce);
      return;
    }
    const res = await tryServer();
    if (res.ok) return;
    _showServerTtsError(langName, res.error ? String(res.error.message || res.error) : '');
    _showTtsWarning(langName);
    return;
  }

  // Server mode (gtts): prefer server; only fall back to browser if the browser has a matching voice.
  if (now >= _serverTtsBackoffUntil) {
    const res = await tryServer();
    if (res.ok) return;

    if (hasVoice) {
      _speakTextBrowser(text, langTag, retryOnce);
      return;
    }
    _showServerTtsError(langName, res.error ? String(res.error.message || res.error) : '');
    _showTtsWarning(langName);
    return;
  }

  // Backoff window: try browser voice if available, otherwise show a helpful message.
  if (hasVoice) {
    _speakTextBrowser(text, langTag, retryOnce);
    return;
  }
  _showServerTtsError(langName, 'Temporarily backing off after server TTS errors.');
  _showTtsWarning(langName);
}

function _speakTextBrowser(text, langTag, retryOnce = true) {
  if (!text) return;
  const synth = window.speechSynthesis;
  if (!synth) return;

  // Chrome gets stuck in "paused" after inactivity — resume first
  try { synth.resume(); } catch { /* noop */ }
  synth.cancel();

  // Refresh voice cache right now — getVoices() is synchronous and cheap.
  // This fixes the race where voices hadn't loaded yet when _loadVoices()
  // was first called but ARE available by the time the user clicks.
  const fresh = synth.getVoices();
  if (fresh.length) _ttsVoices = fresh;

  const want = langTag ? _normalizeLangTag(langTag) : '';
  const wantPrefix = want.split('-')[0];

  // If voices haven't loaded yet, retry once shortly to avoid falling back to English.
  if (langTag && wantPrefix && !_ttsVoices.length && retryOnce) {
    setTimeout(() => _speakTextBrowser(text, langTag, false), 250);
    return;
  }

  const u = new SpeechSynthesisUtterance(String(text));
  u.rate = 0.9;

  if (langTag) {
    u.lang = langTag;

    if (wantPrefix && _ttsVoices.length) {
      const candidates = _ttsVoices.filter(v => _normalizeLangTag(v.lang).startsWith(wantPrefix));
      const voice = candidates.find(v => _normalizeLangTag(v.lang) === want)
                 || candidates.find(v => v.default)
                 || candidates[0];
      if (voice) {
        u.voice = voice;
        // Some browsers behave better when utterance.lang matches the selected voice.
        if (voice.lang) u.lang = voice.lang;
      } else {
        const name = wantPrefix === 'fr' ? 'French'
                   : wantPrefix === 'es' ? 'Spanish' : langTag;
        _showTtsWarning(name);
      }
    }
  }

  try { synth.speak(u); } catch(e) { console.warn('TTS:', e); }
}

function langToTtsTag(lang) {
  if (lang === 'french') return 'fr-FR';
  if (lang === 'spanish') return 'es-ES';
  return '';
}

/* ===============================================
   SPEECH RECOGNITION (STT)
   =============================================== */
function _speechRecognitionCtor() {
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

let _lcMicPreflightOk = false;

function speechSupportStatus() {
  const Ctor = _speechRecognitionCtor();
  if (!Ctor) return { ok: false, reason: 'unsupported' };

  const secure = (typeof window.isSecureContext === 'boolean') ? window.isSecureContext : true;
  if (!secure) return { ok: false, reason: 'insecure' };

  return { ok: true, reason: 'ok' };
}

function speechSupportHint(reason) {
  if (reason === 'insecure') {
    const host = (typeof location !== 'undefined' && location.host) ? location.host : 'this site';
    return `Microphone needs HTTPS (or localhost). Open via https:// or http://localhost (not http://${host}).`;
  }
  return 'Speech recognition works best in Chrome/Edge. If you are on Firefox/Safari, mic will not work here.';
}

function isSpeechRecognitionSupported() {
  return speechSupportStatus().ok;
}

function speechErrorHint(err) {
  const raw = String((err && (err.code || err.message)) || '').trim().toLowerCase();
  const code = raw || 'error';

  if (code.includes('not-allowed') || code.includes('service-not-allowed') || code.includes('denied')) {
    return 'Mic blocked — click the lock icon → Microphone → Allow, then reload.';
  }
  if (code.includes('audio-capture') || code.includes('not-found')) {
    return 'No microphone found (or it is being used by another app).';
  }
  if (code.includes('network')) {
    return 'Network error — speech recognition needs internet access.';
  }
  if (code.includes('no-audio')) {
    return 'No audio input detected — check your mic is selected/unmuted (Windows Sound settings + browser site settings).';
  }
  if (code.includes('no-speech')) {
    return 'No speech detected — try again (speak closer / louder). If it still fails, check mic is selected/unmuted.';
  }
  if (code.includes('timeout')) {
    return 'Timed out — try again.';
  }
  if (code.includes('insecure')) {
    return 'Microphone requires HTTPS (or localhost).';
  }
  return `Mic error: ${code}`;
}

function speechToTextOnce(langTag, timeoutMs = 9000) {
  return new Promise((resolve, reject) => {
    const Ctor = _speechRecognitionCtor();
    if (!Ctor) {
      const err = new Error('speech-recognition-unsupported');
      err.code = 'unsupported';
      reject(err);
      return;
    }

    let done = false;
    let timer = null;
    let gotResult = false;
    let hasAudio = false;
    let hasSpeech = false;

    const rec = new Ctor();
    rec.lang = String(langTag || 'en-US');
    rec.continuous = true;
    rec.interimResults = false;
    rec.maxAlternatives = 3;

    const mapGumErrorCode = (e) => {
      const name = String((e && e.name) ? e.name : '').toLowerCase();
      if (name.includes('notallowed') || name.includes('permissiondenied')) return 'not-allowed';
      if (name.includes('notfound') || name.includes('devicesnotfound')) return 'audio-capture';
      if (name.includes('notreadable') || name.includes('trackstart')) return 'audio-capture';
      if (name.includes('overconstrained')) return 'audio-capture';
      return 'error';
    };

    const finish = (fn, arg) => {
      if (done) return;
      done = true;
      if (timer) clearTimeout(timer);
      try { rec.onresult = rec.onerror = rec.onend = rec.onaudiostart = rec.onspeechstart = null; } catch { /* noop */ }
      try { rec.stop(); } catch { /* noop */ }
      fn(arg);
    };

    rec.onaudiostart = () => { hasAudio = true; };
    rec.onspeechstart = () => { hasSpeech = true; };

    rec.onresult = (e) => {
      gotResult = true;
      const res = e.results && e.results[0] && e.results[0][0];
      const transcript = res ? String(res.transcript || '').trim() : '';
      const confidence = (res && typeof res.confidence === 'number') ? res.confidence : null;
      finish(resolve, { transcript, confidence });
    };

    rec.onerror = (e) => {
      const err = new Error(String(e && e.error ? e.error : 'speech-recognition-error'));
      err.code = (e && e.error) ? e.error : 'error';
      finish(reject, err);
    };

    rec.onend = () => {
      if (done) return;
      if (gotResult) return;
      const err = new Error(hasAudio ? 'speech-recognition-no-speech' : 'speech-recognition-no-audio');
      err.code = hasAudio ? 'no-speech' : 'no-audio';
      err.hasAudio = hasAudio;
      err.hasSpeech = hasSpeech;
      finish(reject, err);
    };

    // Preflight mic permission/device selection via getUserMedia (helps when SpeechRecognition doesn't prompt).
    try {
      if (!_lcMicPreflightOk && navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        navigator.mediaDevices.getUserMedia({ audio: true })
          .then(stream => {
            _lcMicPreflightOk = true;
            try { stream.getTracks().forEach(t => t.stop()); } catch { /* noop */ }
          })
          .catch(e => {
            if (done) return;
            const err = new Error('getUserMedia-failed');
            err.code = mapGumErrorCode(e);
            finish(reject, err);
            try { rec.abort(); } catch { /* noop */ }
          });
      }
    } catch { /* noop */ }

    try {
      rec.start();
    } catch (e) {
      const err = new Error(String(e && e.message ? e.message : 'speech-recognition-start-failed'));
      err.code = 'start-failed';
      finish(reject, err);
      return;
    }

    timer = setTimeout(() => {
      try { rec.stop(); } catch { /* noop */ }
      const err = new Error('speech-recognition-timeout');
      err.code = 'timeout';
      finish(reject, err);
    }, Math.max(1000, timeoutMs));
  });
}

function levenshteinDistance(a, b) {
  const s = String(a || '');
  const t = String(b || '');
  const n = s.length;
  const m = t.length;
  if (!n) return m;
  if (!m) return n;

  const v0 = new Array(m + 1);
  const v1 = new Array(m + 1);
  for (let i = 0; i <= m; i++) v0[i] = i;

  for (let i = 0; i < n; i++) {
    v1[0] = i + 1;
    for (let j = 0; j < m; j++) {
      const cost = s[i] === t[j] ? 0 : 1;
      v1[j + 1] = Math.min(
        v1[j] + 1,       // insertion
        v0[j + 1] + 1,   // deletion
        v0[j] + cost     // substitution
      );
    }
    for (let j = 0; j <= m; j++) v0[j] = v1[j];
  }
  return v0[m];
}

function stringSimilarity(a, b) {
  const s = String(a || '');
  const t = String(b || '');
  if (!s || !t) return 0;
  if (s === t) return 1;
  const dist = levenshteinDistance(s, t);
  const maxLen = Math.max(s.length, t.length);
  return maxLen ? (1 - dist / maxLen) : 0;
}

function matchScore(normHeard, normExpected) {
  const h = String(normHeard || '').trim();
  const e = String(normExpected || '').trim();
  if (!h || !e) return 0;
  if (h === e) return 1;

  const padH = ` ${h} `;
  const padE = ` ${e} `;
  if (padH.includes(` ${e} `) || padE.includes(` ${h} `)) {
    return Math.max(stringSimilarity(h, e), 0.92);
  }
  return stringSimilarity(h, e);
}

function _minSpeakThreshold(normExpected) {
  const len = String(normExpected || '').length;
  if (len <= 3) return 0.92;
  if (len <= 6) return 0.86;
  if (len <= 10) return 0.82;
  if (len <= 20) return 0.78;
  return 0.72;
}

function bestTextMatch(normQuery, options) {
  const q = String(normQuery || '').trim();
  const opts = Array.isArray(options) ? options : [];
  let best = null;
  for (const raw of opts) {
    const norm = normalizeAnswer(raw);
    if (!norm) continue;
    const score = matchScore(q, norm);
    if (!best || score > best.score) best = { raw, norm, score };
  }
  return best;
}

function initTtsProviderMenu() {
  const menu = document.getElementById('ttsProviderMenu');
  if (!menu) return;

  const current = _getTtsProvider();
  const serverDefault = String((window && window.TTS_PROVIDER) ? window.TTS_PROVIDER : 'auto').trim().toLowerCase() || 'auto';
  let override = '';
  try { override = String(localStorage.getItem('lc_tts_provider') || '').trim().toLowerCase(); } catch { /* noop */ }

  menu.querySelectorAll('[data-tts-provider]').forEach(btn => {
    const p = String(btn.dataset.ttsProvider || '').trim().toLowerCase();
    if (p === current) btn.classList.add('active');
    btn.addEventListener('click', () => {
      try { localStorage.setItem('lc_tts_provider', p); } catch { /* noop */ }
      location.reload();
    });
  });

  const status = document.getElementById('ttsProviderStatus');
  if (status) {
    let txt = `Using: ${current}`;
    if (override) txt += ' (override)';
    txt += ` • Server default: ${serverDefault}`;
    status.textContent = txt;
  }
}

function initThemeMenu() {
  const menu = document.getElementById('themeMenu');
  if (!menu) return;

  const allowed = new Set(['purple', 'lime']);
  const current = String((document.documentElement && document.documentElement.dataset)
    ? (document.documentElement.dataset.theme || '') : '').trim().toLowerCase();

  menu.querySelectorAll('[data-theme]').forEach(btn => {
    const t = String(btn.dataset.theme || '').trim().toLowerCase();
    if (!allowed.has(t)) return;
    if (t === current) btn.classList.add('active');

    btn.addEventListener('click', () => {
      try { localStorage.setItem('lc_theme', t); } catch { /* noop */ }
      try { document.documentElement.dataset.theme = t; } catch { /* noop */ }
      location.reload();
    });
  });
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
let quizSpeakLang = null;

function quizListen() {
  speakText(quizTtsText, quizTtsLang);
}

function quizSpeakLangForQuestion(q) {
  if (!q) return null;
  // Only enable speech answering when the expected answer is in the target language.
  if (q.kind === 'vocab' && q.mode === 'english_to_word') {
    return (typeof LANG !== 'undefined') ? langToTtsTag(LANG) : null;
  }
  return null;
}

async function quizSpeak() {
  const q = currentQuizQuestion || null;
  if (!q) return;

  const fb = document.getElementById('feedbackBox');
  const alreadyAnswered = fb && fb.style.display !== 'none';
  if (alreadyAnswered) return;

  const langTag = quizSpeakLang || quizSpeakLangForQuestion(q);
  if (!langTag) return;

  const speakBtn = document.getElementById('quizSpeakBtn');
  const status = document.getElementById('qAccuracy');
  if (status) status.textContent = 'Listening…';
  if (speakBtn) {
    speakBtn.disabled = true;
    speakBtn.classList.add('lc-mic-active');
  }

  try {
    const { transcript } = await speechToTextOnce(langTag, 9000);
    const heard = String(transcript || '').trim();
    const normHeard = normalizeAnswer(heard);

    if (!heard || !normHeard) {
      if (status) status.textContent = 'Heard: —';
      return;
    }

    const choices = Array.isArray(q.choices) ? q.choices : [];
    const best = bestTextMatch(normHeard, choices);
    if (!best) {
      if (status) status.textContent = `Heard: ${heard} (no match)`;
      return;
    }

    const threshold = _minSpeakThreshold(best.norm);
    const pct = Math.round(best.score * 100);
    if (best.score < threshold) {
      if (status) status.textContent = `Heard: ${heard} (match ${pct}% — try again)`;
      return;
    }

    if (status) status.textContent = `Heard: ${heard} (match ${pct}%)`;

    const buttons = Array.from(document.querySelectorAll('#choicesGrid .choice-btn'));
    const btn = buttons.find(b => normalizeAnswer(b.textContent) === normalizeAnswer(best.raw));
    if (btn && !btn.disabled) btn.click();
  } catch (e) {
    if (status) status.textContent = speechErrorHint(e);
  } finally {
    if (speakBtn) {
      speakBtn.disabled = false;
      speakBtn.classList.remove('lc-mic-active');
    }
  }
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

  quizSpeakLang = quizSpeakLangForQuestion(q);
  const speakBtn = document.getElementById('quizSpeakBtn');
  if (speakBtn) speakBtn.style.display = (quizSpeakLang && isSpeechRecognitionSupported()) ? '' : 'none';

  document.getElementById('quizCard').style.display = '';
  document.getElementById('resultsCard').style.display = 'none';
  document.getElementById('feedbackBox').style.display = 'none';

  document.getElementById('qCounter').textContent = `Question ${idx + 1} of ${TOTAL_Q}`;
  document.getElementById('quizProgress').style.width = `${Math.round((idx / TOTAL_Q) * 100)}%`;
  document.getElementById('questionEn').innerHTML = q.question_en;
  document.getElementById('questionBn').innerHTML = q.question_bn;
  document.getElementById('qNum').textContent = `Question ${idx + 1}`;
  document.getElementById('scoreDisplay').textContent = `Score: ${correctTotal}`;
  const qAcc = document.getElementById('qAccuracy');
  if (qAcc) qAcc.textContent = '';

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
let practicePlacementLog = [];

function practiceListen() {
  speakText(practiceTtsText, practiceTtsLang);
}

function normalizeAnswer(str) {
  return String(str || '')
    .toLowerCase()
    .trim()
    .replace(/œ/g, 'oe')
    .replace(/æ/g, 'ae')
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
  const placementMode = (typeof PLACEMENT_MODE !== 'undefined') && !!PLACEMENT_MODE;
  const lang = (typeof PRACTICE_LANG !== 'undefined') ? PRACTICE_LANG : null;
  const xpCorrect = Number.isFinite(q.xp_correct) ? q.xp_correct : 10;
  const xpWrong = Number.isFinite(q.xp_wrong) ? q.xp_wrong : 2;
  const xpDelta = isCorrect ? xpCorrect : xpWrong;

  if (placementMode) {
    const lvl = String(q.cefr || '').trim().toUpperCase();
    practicePlacementLog.push({cefr: lvl, correct: !!isCorrect});
  }

  if (isCorrect) {
    practiceCorrect++;
    practiceXp += xpDelta;
  } else {
    practiceWrong++;
    if (!placementMode) practiceHearts = Math.max(0, practiceHearts - 1);
    practiceXp += xpDelta;
  }

  const xpEl = document.getElementById('practiceXp');
  if (xpEl) xpEl.textContent = `XP: ${practiceXp}`;
  const heartsEl = document.getElementById('practiceHearts');
  if (heartsEl) heartsEl.textContent = '♥'.repeat(Math.max(0, practiceHearts));

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

  const placementMode = (typeof PLACEMENT_MODE !== 'undefined') && !!PLACEMENT_MODE;
  const total = practiceCorrect + practiceWrong;
  const pct = total > 0 ? Math.round((practiceCorrect / total) * 100) : 0;

  if (placementMode) {
    const levels = ['A1', 'A2', 'B1', 'B2'];
    const stats = {};
    levels.forEach(l => { stats[l] = {correct: 0, total: 0, pct: 0}; });

    (practicePlacementLog || []).forEach(r => {
      const lvl = String((r && r.cefr) || '').toUpperCase();
      if (!stats[lvl]) return;
      stats[lvl].total += 1;
      if (r.correct) stats[lvl].correct += 1;
    });
    levels.forEach(l => {
      stats[l].pct = stats[l].total > 0 ? Math.round((stats[l].correct / stats[l].total) * 100) : 0;
    });

    const threshold = 65;
    let recommended = levels[levels.length - 1];
    for (const l of levels) {
      if (stats[l].total === 0 || stats[l].pct < threshold) { recommended = l; break; }
    }

    const levelBn = {
      A1: 'A1 — প্রাথমিক (শুরু থেকে শুরু করুন)',
      A2: 'A2 — প্রি-ইন্টারমিডিয়েট (A1 জানা থাকলে এখান থেকে শুরু করুন)',
      B1: 'B1 — ইন্টারমিডিয়েট (কথোপকথন ও ব্যাকরণ শক্ত করুন)',
      B2: 'B2 — আপার ইন্টারমিডিয়েট (উন্নত ব্যাকরণ ও সাবলীলতা)',
    };

    document.getElementById('practiceResultEmoji').textContent = '🎯';
    document.getElementById('practiceResultTitle').textContent = `Recommended starting level: ${recommended}`;
    document.getElementById('practiceResultBn').textContent = 'স্কোর দেখে আপনার শেখা শুরু করার লেভেল নির্বাচন করা হয়েছে।';
    document.getElementById('practiceResultScore').innerHTML =
      `<span class="${pct >= 70 ? 'text-success' : pct >= 50 ? 'text-warning' : 'text-danger'}">${pct}%</span>` +
      `<div class="small text-muted mt-2">${practiceCorrect}/${total} correct</div>`;

    const badgeEl = document.getElementById('placementLevelBadge');
    if (badgeEl) badgeEl.textContent = recommended;
    const bnEl = document.getElementById('placementLevelBn');
    if (bnEl) bnEl.textContent = levelBn[recommended] || '';

    const breakdownEl = document.getElementById('placementBreakdown');
    if (breakdownEl) {
      breakdownEl.innerHTML = levels
        .map(l => `• <strong>${l}</strong>: ${stats[l].correct}/${stats[l].total} (${stats[l].pct}%)`)
        .join('<br>');
    }

    const wrap = document.getElementById('placementRecoWrap');
    if (wrap) wrap.style.display = '';

    const startBtn = document.getElementById('placementStartBtn');
    if (startBtn && typeof PLACEMENT_START_URLS !== 'undefined' && PLACEMENT_START_URLS) {
      startBtn.href = PLACEMENT_START_URLS[recommended] || startBtn.href;
    }

    const lang = (typeof PRACTICE_LANG !== 'undefined') ? PRACTICE_LANG : '';
    try {
      if (lang) {
        localStorage.setItem(`placement_${lang}`, JSON.stringify({
          level: recommended,
          overall_pct: pct,
          breakdown: Object.fromEntries(levels.map(l => [l, {pct: stats[l].pct, correct: stats[l].correct, total: stats[l].total}])),
          at: new Date().toISOString(),
        }));
      }
    } catch (e) { /* ignore */ }

    return;
  }

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
  practicePlacementLog = [];
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
   SPEAKING TEST MODULE
   =============================================== */
let speakingIdx = 0;
let speakingCorrect = 0;
let speakingWrong = 0;
let speakingAnswered = false;
let currentSpeakingItem = null;

function speakingListen() {
  if (!currentSpeakingItem) return;
  speakText(currentSpeakingItem.tts_text, currentSpeakingItem.tts_lang);
}

function renderSpeaking(idx) {
  if (typeof SPEAKING_ITEMS === 'undefined' || SPEAKING_ITEMS.length === 0) return;
  const item = SPEAKING_ITEMS[idx];
  if (!item) return;
  currentSpeakingItem = item;
  speakingAnswered = false;

  const total = SPEAKING_ITEMS.length;
  document.getElementById('speakingCounter').textContent = `Item ${idx + 1} of ${total}`;
  document.getElementById('speakingProgress').style.width = `${Math.round((idx / total) * 100)}%`;
  document.getElementById('speakingScore').textContent = `${speakingCorrect} / ${idx}`;

  document.getElementById('speakingTarget').textContent = item.full_word || item.word || '';
  document.getElementById('speakingPron').textContent = item.pronunciation || '';
  document.getElementById('speakingEn').textContent = item.english || '';
  document.getElementById('speakingBn').textContent = item.bengali || '';
  document.getElementById('speakingHeard').textContent = '—';

  const fb = document.getElementById('speakingFeedback');
  if (fb) fb.style.display = 'none';

  const speakBtn = document.getElementById('speakingSpeakBtn');
  const noSupport = document.getElementById('speakingNoSupport');
  const support = speechSupportStatus();
  if (noSupport) {
    noSupport.textContent = support.ok ? '' : speechSupportHint(support.reason);
    noSupport.style.display = support.ok ? 'none' : '';
  }
  if (speakBtn) speakBtn.disabled = !support.ok;

  const nextBtn = document.getElementById('speakingNextBtn');
  if (nextBtn) nextBtn.textContent = (idx >= total - 1) ? 'See Results 🏁' : 'Next →';
}

async function speakingSpeak() {
  if (speakingAnswered || !currentSpeakingItem) return;
  if (!isSpeechRecognitionSupported()) return;

  const btn = document.getElementById('speakingSpeakBtn');
  if (btn) {
    btn.disabled = true;
    btn.classList.add('lc-mic-active');
  }
  document.getElementById('speakingHeard').textContent = 'Listening…';

  try {
    const { transcript } = await speechToTextOnce(currentSpeakingItem.tts_lang, 10000);
    const heard = String(transcript || '').trim();
    document.getElementById('speakingHeard').textContent = heard || '—';

    const expected = [
      currentSpeakingItem.word,
      currentSpeakingItem.full_word
    ].filter(Boolean);
    const normHeard = normalizeAnswer(heard);
    const best = bestTextMatch(normHeard, expected);

    const fb = document.getElementById('speakingFeedback');
    const icon = document.getElementById('speakingFeedbackIcon');
    const text = document.getElementById('speakingFeedbackText');
    if (!fb || !icon || !text) return;

    const score = best ? best.score : 0;
    const pct = Math.round(score * 100);
    const threshold = best ? _minSpeakThreshold(best.norm) : 1;
    const isCorrect = best && score >= threshold;

    speakingAnswered = true;
    fb.style.display = 'block';

    if (isCorrect) {
      speakingCorrect++;
      fb.className = 'feedback-box correct-fb';
      icon.textContent = '✅';
      text.innerHTML = `<strong>Great!</strong> Match ${pct}%<br><span class="small text-muted">Expected: <strong>${escapeHtml(currentSpeakingItem.full_word || currentSpeakingItem.word || '')}</strong></span>`;
    } else {
      speakingWrong++;
      fb.className = 'feedback-box wrong-fb';
      icon.textContent = '❌';
      text.innerHTML = `<strong>Try again.</strong> Match ${pct}%<br><span class="small">Correct: <strong>${escapeHtml(currentSpeakingItem.full_word || currentSpeakingItem.word || '')}</strong></span>`;
    }

    document.getElementById('speakingScore').textContent = `${speakingCorrect} / ${speakingCorrect + speakingWrong}`;

    // SRS tracking
    const lang = (typeof SPEAKING_LANG !== 'undefined') ? SPEAKING_LANG : null;
    const wordKey = currentSpeakingItem.word || currentSpeakingItem.full_word || '';
    if (lang && wordKey) {
      const xp = isCorrect ? 12 : 3;
      fetch('/api/word_progress', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({language: lang, word: wordKey, correct: isCorrect ? 1 : 0, source: 'speaking', xp})
      });
    }
  } catch (e) {
    document.getElementById('speakingHeard').textContent = speechErrorHint(e);
  } finally {
    const btn2 = document.getElementById('speakingSpeakBtn');
    if (btn2) {
      btn2.disabled = speakingAnswered || !isSpeechRecognitionSupported();
      btn2.classList.remove('lc-mic-active');
    }
  }
}

function speakingNext() {
  speakingIdx++;
  if (speakingIdx >= SPEAKING_ITEMS.length) {
    showSpeakingResults();
  } else {
    renderSpeaking(speakingIdx);
  }
}

function showSpeakingResults() {
  document.getElementById('speakingCard').style.display = 'none';
  const res = document.getElementById('speakingResults');
  res.style.display = 'block';
  res.scrollIntoView({behavior: 'smooth', block: 'start'});

  const total = speakingCorrect + speakingWrong;
  const pct = total > 0 ? Math.round((speakingCorrect / total) * 100) : 0;

  let emoji = '🎉';
  let title = 'Great job!';
  let titleBn = 'দারুণ! আরও একটু বলার অনুশীলন করুন।';
  if (pct >= 90) {
    emoji = '🏆';
    title = 'Excellent!';
    titleBn = 'অসাধারণ!';
  } else if (pct >= 70) {
    emoji = '🎉';
    title = 'Great!';
    titleBn = 'চমৎকার!';
  } else if (pct >= 50) {
    emoji = '🗣️';
    title = 'Keep going!';
    titleBn = 'চালিয়ে যান!';
  } else {
    emoji = '🎙️';
    title = 'Practice more!';
    titleBn = 'আরও অনুশীলন করুন!';
  }

  document.getElementById('speakingResultEmoji').textContent = emoji;
  document.getElementById('speakingResultTitle').textContent = title;
  document.getElementById('speakingResultBn').textContent = titleBn;
  document.getElementById('speakingResultScore').innerHTML =
    `<span class="${pct >= 70 ? 'text-success' : pct >= 50 ? 'text-warning' : 'text-danger'}">${pct}%</span>` +
    `<div class="small text-muted mt-2">${speakingCorrect}/${total} correct</div>`;
}

function initSpeakingTest() {
  if (typeof SPEAKING_ITEMS === 'undefined' || SPEAKING_ITEMS.length === 0) return;
  speakingIdx = 0;
  speakingCorrect = 0;
  speakingWrong = 0;
  speakingAnswered = false;
  renderSpeaking(0);

  document.addEventListener('keydown', (e) => {
    const tag = (e.target && e.target.tagName) ? e.target.tagName.toLowerCase() : '';
    if (e.isComposing) return;
    if (tag === 'input' || tag === 'textarea') return;

    if (e.key.toLowerCase() === 'l') {
      speakingListen();
      return;
    }
    if (e.key.toLowerCase() === 'm') {
      speakingSpeak();
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
   LESSON SPEAK & MATCH
   =============================================== */
function initLessonSpeakMatch() {
  const root = document.getElementById('lcSpeakMatch');
  if (!root) return;

  const btn = document.getElementById('lcSpeakMatchBtn');
  const listenBtn = document.getElementById('lcSpeakMatchListenBtn');
  const noSupport = document.getElementById('lcSpeakMatchNoSupport');
  const emptyEl = document.getElementById('lcSpeakMatchEmpty');

  const heardEl = document.getElementById('lcSpeakMatchHeard');
  const resEl = document.getElementById('lcSpeakMatchResult');
  const wordEl = document.getElementById('lcSpeakMatchWord');
  const pronEl = document.getElementById('lcSpeakMatchPron');
  const enEl = document.getElementById('lcSpeakMatchEn');
  const bnEl = document.getElementById('lcSpeakMatchBn');
  const scoreEl = document.getElementById('lcSpeakMatchScore');
  const noteEl = document.getElementById('lcSpeakMatchNote');
  const suggEl = document.getElementById('lcSpeakMatchSuggestions');

  if (!btn || !heardEl || !resEl) return;

  const items = (typeof LESSON_SPEAK_MATCH_ITEMS !== 'undefined') ? LESSON_SPEAK_MATCH_ITEMS : [];
  const support = speechSupportStatus();

  if (noSupport) {
    noSupport.textContent = support.ok ? '' : speechSupportHint(support.reason);
    noSupport.style.display = support.ok ? 'none' : '';
  }

  if (!Array.isArray(items) || items.length === 0) {
    if (emptyEl) emptyEl.style.display = '';
    btn.disabled = true;
    if (listenBtn) listenBtn.style.display = 'none';
    return;
  }
  if (emptyEl) emptyEl.style.display = 'none';

  if (!support.ok) {
    btn.disabled = true;
    if (listenBtn) listenBtn.style.display = 'none';
    return;
  }

  const lang = (typeof LESSON_SPEAK_MATCH_LANG !== 'undefined') ? LESSON_SPEAK_MATCH_LANG : '';
  const langTag = langToTtsTag(lang) || 'en-US';

  let selected = null;

  function renderMatch(entry, ranked) {
    if (!entry || !entry.item) return;
    const it = entry.item;
    selected = it;

    const label = it.full_word || it.word || '';
    if (wordEl) wordEl.textContent = label;
    if (pronEl) pronEl.textContent = it.pronunciation || '';
    if (enEl) enEl.textContent = it.english || '';
    if (bnEl) bnEl.textContent = it.bengali || '';

    const pct = Math.round((entry.score || 0) * 100);
    if (scoreEl) scoreEl.textContent = `Match: ${pct}%`;

    const thresh = _minSpeakThreshold(normalizeAnswer(label));
    if (noteEl) {
      noteEl.textContent = entry.score >= thresh ? 'Looks matched' : 'Not sure — pick from suggestions';
    }

    if (listenBtn) listenBtn.style.display = label ? '' : 'none';

    if (suggEl) {
      suggEl.innerHTML = '';
      const top = Array.isArray(ranked) ? ranked.slice(0, 4) : [];
      if (top.length > 1) {
        const p = document.createElement('div');
        p.textContent = 'Did you mean:';
        suggEl.appendChild(p);

        const wrap = document.createElement('div');
        wrap.className = 'mt-2 d-flex flex-wrap gap-2 lc-speak-suggestions';
        top.forEach(r => {
          const t = r.item ? (r.item.full_word || r.item.word || '') : '';
          if (!t) return;
          const b = document.createElement('button');
          b.type = 'button';
          b.className = 'btn btn-sm btn-light border';
          b.textContent = t;
          b.addEventListener('click', () => renderMatch(r, ranked));
          wrap.appendChild(b);
        });
        suggEl.appendChild(wrap);
      }
    }

    resEl.style.display = '';
  }

  function rankMatches(normHeard) {
    const wantExamples = (String(normHeard || '').split(' ').filter(Boolean).length >= 3);
    const ranked = items.map(it => {
      const candidates = [];
      if (it.full_word) candidates.push(it.full_word);
      if (it.word && it.word !== it.full_word) candidates.push(it.word);
      if (wantExamples && it.example) candidates.push(it.example);

      let best = 0;
      for (const c of candidates) {
        const norm = normalizeAnswer(c);
        if (!norm) continue;
        best = Math.max(best, matchScore(normHeard, norm));
      }
      return { item: it, score: best };
    });
    ranked.sort((a, b) => (b.score || 0) - (a.score || 0));
    return ranked;
  }

  btn.addEventListener('click', async () => {
    btn.disabled = true;
    btn.classList.add('lc-mic-active');
    heardEl.textContent = 'Listening…';
    resEl.style.display = 'none';

    try {
      const { transcript } = await speechToTextOnce(langTag, 10000);
      const heard = String(transcript || '').trim();
      heardEl.textContent = heard || '—';
      const normHeard = normalizeAnswer(heard);
      if (!normHeard) return;

      const ranked = rankMatches(normHeard);
      if (!ranked.length) return;
      renderMatch(ranked[0], ranked);
    } catch (e) {
      heardEl.textContent = speechErrorHint(e);
      resEl.style.display = 'none';
    } finally {
      btn.disabled = false;
      btn.classList.remove('lc-mic-active');
    }
  });

  if (listenBtn) {
    listenBtn.addEventListener('click', () => {
      if (!selected) return;
      const txt = selected.tts_text || selected.full_word || selected.word || '';
      const tag = selected.tts_lang || langTag;
      speakText(txt, tag);
    });
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
    const article = w.article || '';
    const sep = (article && article.endsWith("'")) ? '' : ' ';
    const word = escapeHtml(w.word);
    const english = escapeHtml(w.english);
    const bengali = escapeHtml(w.bengali);
    const pron = escapeHtml(w.pronunciation);
    const catLabel = escapeHtml((w.category || '').replace(/_/g, ' '));
    const displayWord = article
      ? `<span class="vocab-article">${escapeHtml(article)}</span>${sep}${word}`
      : word;
    const ttsWord = article ? (article + sep + w.word) : w.word;

    return `
      <div class="col-md-6 col-lg-4">
        <div class="vocab-card card border-0 shadow-sm h-100">
          <div class="card-body p-3">
            <div class="d-flex justify-content-between align-items-start">
              <div class="vocab-word fw-bold fs-5 ${langClass}">${displayWord}</div>
              <div class="d-flex gap-2 align-items-start">
                <button class="btn btn-sm btn-light border btn-listen vocab-listen" type="button" title="Listen" aria-label="Listen"
                        data-tts="${escapeHtml(ttsWord)}">
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
   FEEDBACK MODAL
   =============================================== */
function initFeedbackForm() {
  const modalEl = document.getElementById('feedbackModal');
  const form = document.getElementById('feedbackForm');
  if (!modalEl || !form) return;

  const nameEl = document.getElementById('feedbackName');
  const emailEl = document.getElementById('feedbackEmail');
  const categoryEl = document.getElementById('feedbackCategory');
  const messageEl = document.getElementById('feedbackMessage');
  const langEl = document.getElementById('feedbackLanguage');
  const pageEl = document.getElementById('feedbackPage');
  const errEl = document.getElementById('feedbackError');
  const okEl = document.getElementById('feedbackOk');
  const submitBtn = document.getElementById('feedbackSubmitBtn');

  function showError(text) {
    if (okEl) okEl.style.display = 'none';
    if (errEl) {
      errEl.textContent = text || 'Something went wrong.';
      errEl.style.display = '';
    }
  }

  function showOk(text) {
    if (errEl) errEl.style.display = 'none';
    if (okEl) {
      okEl.textContent = text || 'Thanks!';
      okEl.style.display = '';
    }
  }

  function clearAlerts() {
    if (errEl) { errEl.textContent = ''; errEl.style.display = 'none'; }
    if (okEl) { okEl.textContent = ''; okEl.style.display = 'none'; }
  }

  function prefillFromStorage() {
    try {
      const savedName = localStorage.getItem('lc_fb_name') || '';
      const savedEmail = localStorage.getItem('lc_fb_email') || '';
      if (nameEl && !nameEl.value.trim() && savedName) nameEl.value = savedName;
      if (emailEl && !emailEl.value.trim() && savedEmail) emailEl.value = savedEmail;
    } catch (e) { /* ignore */ }
  }

  function saveToStorage() {
    try {
      const n = nameEl ? nameEl.value.trim() : '';
      const e = emailEl ? emailEl.value.trim() : '';
      if (n) localStorage.setItem('lc_fb_name', n);
      if (e) localStorage.setItem('lc_fb_email', e);
    } catch (e) { /* ignore */ }
  }

  // Bootstrap modal lifecycle
  modalEl.addEventListener('show.bs.modal', () => {
    clearAlerts();
    prefillFromStorage();
    if (messageEl) setTimeout(() => messageEl.focus(), 120);
  });

  form.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    clearAlerts();

    const name = nameEl ? nameEl.value.trim() : '';
    const email = emailEl ? emailEl.value.trim() : '';
    const category = categoryEl ? categoryEl.value : '';
    const message = messageEl ? messageEl.value.trim() : '';
    const language = langEl ? (langEl.value || '') : '';
    const page = pageEl ? (pageEl.value || '') : '';

    if (!name) return showError('Name is required.');
    if (!email || !email.includes('@')) return showError('Please enter a valid email.');
    if (!message) return showError('Message is required.');

    saveToStorage();

    if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = 'Sending…'; }
    try {
      const res = await fetch('/api/feedback', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name, email, category, language, message, page}),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data || !data.ok) {
        showError((data && data.error) ? String(data.error) : 'Failed to send feedback.');
        return;
      }

      const sheets = (data && typeof data === 'object') ? data.sheets : null;
      if (sheets && sheets.enabled && sheets.ok === false) {
        const err = sheets.error ? String(sheets.error) : 'unknown error';
        showError(`Saved, but Google Sheets sync failed (${err}). Please try again later.`);
        return;
      }

      if (sheets && sheets.enabled === false) {
        showOk('Thanks! Your message has been received. (Note: Google Sheets sync is not configured on the server yet.)');
      } else {
        showOk('Thanks! Your message has been received.');
      }
      if (messageEl) messageEl.value = '';
      setTimeout(() => {
        try {
          if (window.bootstrap) {
            const inst = window.bootstrap.Modal.getInstance(modalEl);
            if (inst) inst.hide();
          }
        } catch (e) { /* ignore */ }
      }, 900);
    } catch (e) {
      showError('Network error — please try again.');
    } finally {
      if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = 'Send'; }
    }
  });
}

/* ===============================================
   PLACEMENT PROMO (Language page)
   =============================================== */
function initPlacementPromo() {
  const startLink = document.getElementById('placementStartLink');
  if (!startLink) return;

  const baseHref = startLink.dataset.baseHref || startLink.getAttribute('href') || '';
  const estimateEl = document.getElementById('placementEstimate');
  const estimateBnEl = document.getElementById('placementEstimateBn');
  const lastEl = document.getElementById('placementLastResult');
  const resumeLink = document.getElementById('placementResumeLink');

  const lang = (startLink.dataset.lang || '').trim().toLowerCase();
  const key = lang ? `placement_${lang}` : '';

  function getSelectedPer() {
    const sel = document.querySelector('input[name="placementPer"]:checked');
    const n = sel ? parseInt(sel.value, 10) : 10;
    if (!Number.isFinite(n) || n <= 0) return 10;
    return Math.max(6, Math.min(16, n));
  }

  function updateEstimateAndLink() {
    const per = getSelectedPer();
    const total = per * 4; // A1–B2
    const minMins = Math.max(6, Math.round(total * 0.25));
    const maxMins = Math.max(minMins + 2, Math.round(total * 0.375));

    if (estimateEl) estimateEl.textContent = `≈ ${total} questions • ${minMins}–${maxMins} minutes`;
    if (estimateBnEl) estimateBnEl.textContent = `≈ ${total}টি প্রশ্ন • ${minMins}–${maxMins} মিনিট`;

    const href = per ? `${baseHref}?per=${per}` : baseHref;
    startLink.href = href;
  }

  // Attach radio listeners
  document.querySelectorAll('input[name="placementPer"]').forEach(r => {
    r.addEventListener('change', updateEstimateAndLink);
  });
  updateEstimateAndLink();

  // Show last placement result if available
  if (key && lastEl && resumeLink) {
    try {
      const raw = localStorage.getItem(key);
      if (raw) {
        const data = JSON.parse(raw);
        const level = String((data && data.level) || '').toUpperCase();
        const pct = Number.isFinite(data && data.overall_pct) ? Math.round(data.overall_pct) : null;
        const at = (data && data.at) ? new Date(data.at) : null;
        const atStr = (at && !Number.isNaN(at.getTime())) ? at.toLocaleDateString() : '';

        const levelOk = ['A1','A2','B1','B2'].includes(level);
        if (levelOk) {
          const href =
            level === 'A1' ? resumeLink.dataset.startA1 :
            level === 'A2' ? resumeLink.dataset.startA2 :
            level === 'B1' ? resumeLink.dataset.startB1 :
            level === 'B2' ? resumeLink.dataset.startB2 :
            '';
          if (href) resumeLink.href = href;

          resumeLink.style.display = '';
          lastEl.style.display = '';

          const pctTxt = (pct === null) ? '' : ` (${pct}%)`;
          const dateTxt = atStr ? ` • ${atStr}` : '';
          lastEl.innerHTML =
            `<div>Last result: <strong>${escapeHtml(level)}</strong>${escapeHtml(pctTxt)}${escapeHtml(dateTxt)}</div>` +
            `<div class="bengali-text">শেষ ফলাফল: <strong>${escapeHtml(level)}</strong>${escapeHtml(pctTxt)}${escapeHtml(dateTxt)}</div>`;
        }
      }
    } catch (e) { /* ignore */ }
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
   DIACRITICS INPUT HELPER
   =============================================== */
const DIACRITICS_FR = ['à','â','ä','é','è','ê','ë','î','ï','ô','ù','û','ü','ç','œ','æ'];
const DIACRITICS_ES = ['á','é','í','ó','ú','ü','ñ','¿','¡'];

function buildDiacriticBar(barEl, inputEl, lang) {
  if (!barEl || !inputEl) return;
  const chars = lang === 'french' ? DIACRITICS_FR : DIACRITICS_ES;
  barEl.innerHTML = '';
  chars.forEach(ch => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn btn-sm btn-outline-secondary diacritic-btn';
    btn.textContent = ch;
    btn.title = 'Insert ' + ch;
    btn.addEventListener('mousedown', e => {
      e.preventDefault(); // keep focus in input
      const start = inputEl.selectionStart;
      const end   = inputEl.selectionEnd;
      inputEl.value = inputEl.value.slice(0, start) + ch + inputEl.value.slice(end);
      inputEl.selectionStart = inputEl.selectionEnd = start + ch.length;
      inputEl.focus();
    });
    barEl.appendChild(btn);
  });
}

function initDiacriticBars() {
  const lang =
    ((typeof LANG !== 'undefined' && LANG) ? LANG : '') ||
    ((typeof PRACTICE_LANG !== 'undefined' && PRACTICE_LANG) ? PRACTICE_LANG : '') ||
    ((typeof DICTATION_LANG !== 'undefined' && DICTATION_LANG) ? DICTATION_LANG : '');
  if (!lang) return;
  buildDiacriticBar(
    document.getElementById('practiceDiacriticBar'),
    document.getElementById('practiceTypeInput'), lang);
  buildDiacriticBar(
    document.getElementById('dictationDiacriticBar'),
    document.getElementById('dictationInput'), lang);
}

/* ===============================================
   KEYBOARD SHORTCUTS HELP
   =============================================== */
function initShortcutsHelp() {
  const btn = document.getElementById('shortcutsBtn');
  if (!btn) return;

  // Detect which interactive page we're on
  const isFlashcard  = typeof VOCAB !== 'undefined';
  const isQuiz       = typeof QUESTIONS !== 'undefined' && QUESTIONS.length > 0;
  const isPractice   = typeof PRACTICE_QUESTIONS !== 'undefined' && PRACTICE_QUESTIONS.length > 0;
  const isDictation  = typeof DICTATION_ITEMS !== 'undefined';

  if (!isFlashcard && !isQuiz && !isPractice && !isDictation) return;

  // Show the floating ? button
  btn.style.display = 'flex';
  btn.style.alignItems = 'center';
  btn.style.justifyContent = 'center';

  // Show relevant shortcut sections in the modal
  if (isFlashcard) {
    const el = document.getElementById('sc-flashcards');
    if (el) el.style.display = '';
  }
  if (isQuiz) {
    const el = document.getElementById('sc-quiz');
    if (el) el.style.display = '';
  }
  if (isPractice) {
    const el = document.getElementById('sc-practice');
    if (el) el.style.display = '';
  }
  if (isDictation) {
    const el = document.getElementById('sc-dictation');
    if (el) el.style.display = '';
  }
}

/* ===============================================
   INIT on page load
   =============================================== */
document.addEventListener('DOMContentLoaded', () => {
  initThemeMenu();
  initTtsProviderMenu();
  // Flashcards page
  if (typeof VOCAB !== 'undefined') initFlashcards();
  // Quiz page
  if (typeof QUESTIONS !== 'undefined' && QUESTIONS.length > 0) initQuiz();
  // Practice page
  initPractice();
  // Dictation page
  initDictation();
  // Speaking test page
  initSpeakingTest();
  // Feedback modal
  initFeedbackForm();
  // Placement promo on language page
  initPlacementPromo();
  // Lesson vocab filter
  filterLessonVocab();
  // Lesson speak & match
  initLessonSpeakMatch();
  // Vocabulary explorer page
  initVocabExplorer();
  // Diacritics input helper (practice + dictation pages)
  initDiacriticBars();
  // Keyboard shortcuts (only activate on relevant pages)
  attachFlashcardShortcuts();
  attachQuizShortcuts();
  initShortcutsHelp();

  // Lesson page vocab TTS buttons (data-tts / data-lang attributes)
  document.querySelectorAll('.lesson-page .btn-listen[data-tts]').forEach(btn => {
    btn.addEventListener('click', () => speakText(btn.dataset.tts, btn.dataset.lang || ''));
  });

  // Global ? key → open shortcuts modal
  document.addEventListener('keydown', e => {
    if (e.key === '?' && !['INPUT','TEXTAREA'].includes(document.activeElement.tagName)) {
      const btn = document.getElementById('shortcutsBtn');
      if (btn && btn.style.display !== 'none') btn.click();
    }
  });

  // Animate progress bars on dashboard
  document.querySelectorAll('.progress-bar').forEach(bar => {
    const target = bar.style.width;
    bar.style.width = '0%';
    setTimeout(() => { bar.style.width = target; }, 300);
  });
});
