// ── quiz.js ───────────────────────────────────────────────────────────────────
// P0-2: Calls /resume on load — never /login.
// P0-5: Visible save states + 3-attempt retry with backoff.
// P0-6: WS fallback to polling; timer interpolated client-side.

const TOTAL_Q = 60;
const POLL_INTERVAL = 8000;   // ms — fallback polling interval

let currentQ   = 1;
let answered   = new Set();
let remainSecs = 0;
let wsAlive    = false;
let timerInterval = null;

// ── DOM refs ───────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const dom = {
  grid:       $('nav-grid'),
  counter:    $('q-counter'),
  timer:      $('timer'),
  saveStatus: $('save-status'),
  loading:    $('loading'),
  qPanel:     $('q-panel'),
  qNumber:    $('q-number'),
  qText:      $('q-text'),
  options:    $('options'),
  prevBtn:    $('prev-btn'),
  nextBtn:    $('next-btn'),
  submitBtn:  $('submit-btn'),
  toast:      $('toast'),
  modal:      $('submit-modal'),
  modalOk:    $('modal-confirm'),
  modalX:     $('modal-cancel'),
};

// ── Utilities ──────────────────────────────────────────────────────────────────
function toast(msg, isError = false, duration = 3000) {
  dom.toast.textContent = msg;
  dom.toast.className   = 'toast show' + (isError ? ' error' : '');
  clearTimeout(dom.toast._t);
  dom.toast._t = setTimeout(() => dom.toast.classList.remove('show'), duration);
}

function setSaveStatus(state) {
  // state: '' | 'saving' | 'saved' | 'failed'
  const labels = { saving: 'SAVING…', saved: 'SAVED ✓', failed: 'FAILED ✗' };
  dom.saveStatus.textContent  = labels[state] || '';
  dom.saveStatus.className    = 'save-status' + (state ? ` ${state}` : '');
}

function fmtTime(s) {
  if (s <= 0) return '00:00';
  const m = Math.floor(s / 60).toString().padStart(2, '0');
  const sec = (s % 60).toString().padStart(2, '0');
  return `${m}:${sec}`;
}

function applyTimerStyle(s) {
  dom.timer.textContent = fmtTime(s);
  dom.timer.className   = 'timer-display' + (s < 60 ? ' danger' : s < 300 ? ' warn' : '');
}

// ── Client-side clock interpolation ───────────────────────────────────────────
function startLocalTick() {
  if (timerInterval) clearInterval(timerInterval);
  timerInterval = setInterval(() => {
    remainSecs = Math.max(0, remainSecs - 1);
    applyTimerStyle(remainSecs);
    if (remainSecs === 0) {
      clearInterval(timerInterval);
      if (!wsAlive) handleExpired();  // WS wasn't alive to catch it
    }
  }, 1000);
}

// ── Navigator grid ─────────────────────────────────────────────────────────────
function buildGrid() {
  dom.grid.innerHTML = '';
  for (let i = 1; i <= TOTAL_Q; i++) {
    const btn = document.createElement('div');
    btn.className = 'nav-btn';
    btn.id = `nb-${i}`;
    btn.textContent = i;
    btn.onclick = () => loadQuestion(i);
    dom.grid.appendChild(btn);
  }
}

function updateGrid() {
  for (let i = 1; i <= TOTAL_Q; i++) {
    const btn = $(`nb-${i}`);
    if (!btn) continue;
    btn.className = 'nav-btn'
      + (answered.has(i) ? ' answered' : '')
      + (i === currentQ  ? ' current'  : '');
  }
  dom.counter.textContent = `Q ${currentQ}/${TOTAL_Q}`;
}

// ── Load question ──────────────────────────────────────────────────────────────
async function loadQuestion(n) {
  currentQ = n;
  dom.loading.classList.remove('hidden');
  dom.qPanel.classList.add('hidden');
  updateGrid();

  try {
    const res = await fetch(`/api/quiz/question/${n}`, { credentials: 'include' });
    if (res.status === 401 || res.status === 403) { redirectToLogin(); return; }
    const q = await res.json();
    renderQuestion(q);
  } catch (_) {
    toast('Network error loading question. Retrying…', true);
    setTimeout(() => loadQuestion(n), 2000);
  }
}

function renderQuestion(q) {
  dom.qNumber.textContent = `QUESTION ${q.no} / ${TOTAL_Q}`;
  dom.qText.textContent   = q.text;
  dom.options.innerHTML   = '';

  ['A', 'B', 'C', 'D'].forEach(key => {
    const item = document.createElement('div');
    item.className = 'option-item' + (q.your_answer === key ? ' selected' : '');
    item.innerHTML = `<span class="opt-key">${key}</span><span>${q.options[key]}</span>`;
    item.onclick = () => selectOption(q.no, key, item);
    dom.options.appendChild(item);
  });

  dom.prevBtn.disabled = q.no === 1;
  dom.nextBtn.disabled = q.no === TOTAL_Q;
  dom.loading.classList.add('hidden');
  dom.qPanel.classList.remove('hidden');
  updateGrid();
}

// ── Answer selection with retry ────────────────────────────────────────────────
async function selectOption(qNo, opt, el) {
  // Optimistic UI
  document.querySelectorAll('.option-item').forEach(e => e.classList.remove('selected'));
  el.classList.add('selected');
  setSaveStatus('saving');

  const wasAnswered = answered.has(qNo);
  answered.add(qNo);
  updateGrid();

  const saved = await saveWithRetry(qNo, opt);
  if (saved) {
    setSaveStatus('saved');
    setTimeout(() => setSaveStatus(''), 2000);
  } else {
    setSaveStatus('failed');
    // Roll back optimistic state
    el.classList.remove('selected');
    if (!wasAnswered) answered.delete(qNo);
    updateGrid();
    toast('Answer not saved. Check your connection.', true, 5000);
  }
}

async function saveWithRetry(qNo, opt, attempts = 3, delay = 500) {
  for (let i = 0; i < attempts; i++) {
    try {
      const res = await fetch('/api/quiz/answer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ question_no: qNo, option: opt }),
      });
      if (res.ok) {
        const data = await res.json();
        return data.saved === true;
      }
      if (res.status === 403) return false; // submitted / expired — don't retry
    } catch (_) { /* network error — retry */ }
    if (i < attempts - 1) await new Promise(r => setTimeout(r, delay * (i + 1)));
  }
  return false;
}

// ── Submit ────────────────────────────────────────────────────────────────────
async function doSubmit() {
  document.body.innerHTML = `
    <div class="submitted-screen">
      <h1>SUBMITTING</h1>
      <p style="color:var(--yellow);font-family:'IBM Plex Mono',monospace;">Please wait…</p>
    </div>`;

  for (let i = 0; i < 5; i++) {
    try {
      const res = await fetch('/api/quiz/submit', { method: 'POST', credentials: 'include' });
      if (res.ok) {
        document.body.innerHTML = `
          <div class="submitted-screen">
            <h1>SUBMITTED</h1>
            <p>Your responses have been recorded. Results will be announced by ACE Cybersecurity.</p>
            <p style="color:var(--dim);font-family:'IBM Plex Mono',monospace;font-size:0.75rem;">You may close this tab.</p>
          </div>`;
        return;
      }
    } catch (_) {}
    await new Promise(r => setTimeout(r, 1500 * (i + 1)));
  }
  document.body.innerHTML += `<p style="color:var(--red);font-family:monospace">Submission failed after retries. Please inform the invigilator immediately.</p>`;
}

function handleExpired() {
  doSubmit();
}

// ── WebSocket setup ────────────────────────────────────────────────────────────
function connectWS() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  let ws;
  try {
    ws = new WebSocket(`${proto}//${location.host}/ws/timer`);
  } catch (_) {
    startPollingFallback();
    return;
  }

  ws.onopen = () => { wsAlive = true; };

  ws.onmessage = ({ data }) => {
    const msg = JSON.parse(data);
    if (msg.type === 'tick') {
      remainSecs = msg.remaining;
      applyTimerStyle(remainSecs);
    } else if (msg.type === 'expired') {
      wsAlive = false;
      handleExpired();
    }
  };

  ws.onclose = ws.onerror = () => {
    wsAlive = false;
    startPollingFallback();
  };
}

// ── Fallback polling ───────────────────────────────────────────────────────────
let _pollTimer = null;
function startPollingFallback() {
  if (_pollTimer) return; // already polling
  startLocalTick();       // keep display ticking client-side
  _pollTimer = setInterval(async () => {
    try {
      const res = await fetch('/api/quiz/state', { credentials: 'include' });
      if (!res.ok) return;
      const data = await res.json();
      // Sync answered set from server
      data.answered_questions.forEach(n => answered.add(n));
      updateGrid();
      remainSecs = data.remaining_seconds;
      applyTimerStyle(remainSecs);
      if (data.has_submitted || data.remaining_seconds <= 0) {
        clearInterval(_pollTimer);
        handleExpired();
      }
    } catch (_) { /* network hiccup — keep polling */ }
  }, POLL_INTERVAL);
}

function redirectToLogin() { window.location.href = '/'; }

// ── Initialise ────────────────────────────────────────────────────────────────
(async () => {
  // P0-2: validate existing cookie without touching login
  try {
    const res = await fetch('/api/resume', { credentials: 'include' });
    if (!res.ok) { redirectToLogin(); return; }
    const data = await res.json();
    if (data.has_submitted) {
      document.body.innerHTML = `
        <div class="submitted-screen">
          <h1>SUBMITTED</h1>
          <p>You have already submitted this quiz.</p>
        </div>`;
      return;
    }
  } catch (_) { redirectToLogin(); return; }

  // Build UI
  buildGrid();

  // Fetch initial state
  try {
    const res = await fetch('/api/quiz/state', { credentials: 'include' });
    if (!res.ok) { redirectToLogin(); return; }
    const state = await res.json();
    state.answered_questions.forEach(n => answered.add(n));
    remainSecs = state.remaining_seconds;
    applyTimerStyle(remainSecs);

    if (state.has_submitted || remainSecs <= 0) { handleExpired(); return; }
  } catch (_) { redirectToLogin(); return; }

  // Start WS (with polling fallback)
  connectWS();

  // Load first question
  loadQuestion(1);

  // ── Nav button events
  dom.prevBtn.onclick = () => { if (currentQ > 1) loadQuestion(currentQ - 1); };
  dom.nextBtn.onclick = () => { if (currentQ < TOTAL_Q) loadQuestion(currentQ + 1); };

  // ── Submit button — never gated on WS
  dom.submitBtn.onclick = () => dom.modal.classList.add('active');
  dom.modalX.onclick    = () => dom.modal.classList.remove('active');
  dom.modalOk.onclick   = () => { dom.modal.classList.remove('active'); doSubmit(); };
})();
