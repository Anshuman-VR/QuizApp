// ── login.js ─────────────────────────────────────────────────────────────────
// P0-2: On page load, silently call /resume.
// If valid & not submitted → redirect to quiz.
// If valid & submitted    → show "already submitted" message.
// Otherwise              → show the login form normally.
//
// ── 👁 ACE{y0u_f0und_1t} ──────────────────────────────────────────────────────
// Interesting. Now POST it to /api/recon. You'll know what to put in the body.
// ─────────────────────────────────────────────────────────────────────────────

(async () => {
  try {
    const res = await fetch('/api/resume', { credentials: 'include' });
    if (res.ok) {
      const data = await res.json();
      if (data.has_submitted) {
        showAlert('You have already submitted the quiz. Results will be announced by ACE.', false);
      } else {
        window.location.href = '/quiz.html';
      }
      return;
    }
  } catch (_) { /* no cookie or network error — show the form */ }
})();

// ── DOM refs ──────────────────────────────────────────────────────────────────
const form        = document.getElementById('login-form');
const regInput    = document.getElementById('reg_no');
const regHint     = document.getElementById('reg-hint');
const branchSel   = document.getElementById('branch');
const otherGroup  = document.getElementById('other-group');
const otherInput  = document.getElementById('branch-other');
const submitBtn   = document.getElementById('submit-btn');
const alertBox    = document.getElementById('alert');

function showAlert(msg, isError = true) {
  alertBox.textContent = msg;
  alertBox.className = 'alert-box' + (isError ? '' : ' success');
  alertBox.classList.remove('hidden');
}

// ── Branch dropdown logic ─────────────────────────────────────────────────────
branchSel.addEventListener('change', () => {
  if (branchSel.value === 'Others') {
    otherGroup.classList.remove('hidden');
    otherInput.required = true;
  } else {
    otherGroup.classList.add('hidden');
    otherInput.required = false;
  }
});

// ── Reg no live validation ────────────────────────────────────────────────────
const REG_RE = /^1\d{8}$/;
regInput.addEventListener('input', () => {
  const v = regInput.value.trim();
  if (!v) { regHint.textContent = ''; return; }
  if (REG_RE.test(v)) {
    regHint.textContent = '✓ Valid format';
    regHint.style.color = 'var(--green)';
  } else {
    regHint.textContent = '✗ Must be exactly 9 digits starting with 1';
    regHint.style.color = 'var(--red)';
  }
});

// ── Form submit ───────────────────────────────────────────────────────────────
form.addEventListener('submit', async (e) => {
  e.preventDefault();
  alertBox.classList.add('hidden');

  const reg_no = regInput.value.trim();
  if (!REG_RE.test(reg_no)) {
    showAlert('Invalid registration number. Must be 9 digits starting with 1.');
    return;
  }

  let branch = branchSel.value;
  if (branch === 'Others') {
    branch = otherInput.value.trim();
    if (!branch) { showAlert('Please specify your branch.'); return; }
  }

  const payload = {
    reg_no,
    name:   document.getElementById('name').value.trim(),
    year:   parseInt(document.getElementById('year').value),
    branch,
  };

  submitBtn.disabled = true;
  submitBtn.textContent = 'INITIALIZING...';

  try {
    const res = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (res.ok) {
      window.location.href = '/quiz.html';
    } else {
      showAlert(data.detail || 'Login failed. Try again.');
      submitBtn.disabled = false;
      submitBtn.textContent = 'INITIALIZE SESSION';
    }
  } catch (_) {
    showAlert('Network error. Could not reach the server. Check your connection.');
    submitBtn.disabled = false;
    submitBtn.textContent = 'INITIALIZE SESSION';
  }
});
