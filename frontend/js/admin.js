let refreshJob = null;

const $ = id => document.getElementById(id);

$('admin-login-btn').addEventListener('click', async () => {
  const secret = $('admin-secret').value;
  const res = await fetch('/api/admin/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ secret }),
  });
  if (res.ok) {
    $('login-view').classList.add('hidden');
    $('dash-view').classList.remove('hidden');
    loadDash();
    refreshJob = setInterval(loadDash, 15000); // auto-refresh every 15s
  } else {
    const err = $('admin-alert');
    err.textContent = 'Wrong secret.';
    err.classList.remove('hidden');
  }
});

$('refresh-btn').onclick  = loadDash;
$('export-btn').onclick   = () => { window.location.href = '/api/admin/export'; };

async function loadDash() {
  try {
    const [statsRes, resultsRes] = await Promise.all([
      fetch('/api/admin/stats',   { credentials: 'include' }),
      fetch('/api/admin/results', { credentials: 'include' }),
    ]);
    if (!statsRes.ok || !resultsRes.ok) return;

    const stats   = await statsRes.json();
    const results = await resultsRes.json();

    $('s-reg').textContent = stats.total_registered;
    $('s-sub').textContent = stats.total_submitted;
    $('s-not').textContent = stats.not_started;
    $('s-avg').textContent = stats.avg_score;

    const tbody = $('results-body');
    tbody.innerHTML = '';
    results.forEach(r => {
      const tr = document.createElement('tr');
      const badge = r.has_submitted
        ? '<span class="badge badge-submitted">SUBMITTED</span>'
        : '<span class="badge badge-progress">IN PROGRESS</span>';
      const score = r.has_submitted ? `<strong style="color:var(--yellow)">${r.score}</strong>` : '—';
      tr.innerHTML = `
        <td class="mono-cell">${r.reg_no}</td>
        <td>${r.name}</td>
        <td>${r.branch}</td>
        <td>${r.year}</td>
        <td>${badge}</td>
        <td class="mono-cell">${score}</td>
        <td style="display:flex;gap:0.5rem;">
          <button class="btn btn-sm" onclick="extendTime('${r.reg_no}')" title="Grant +10 min">+10m</button>
          <button class="btn btn-sm btn-danger" onclick="resetSession('${r.reg_no}')" title="Full reset">RESET</button>
        </td>`;
      tbody.appendChild(tr);
    });
  } catch (e) {
    console.error('Admin load error:', e);
  }
}

async function extendTime(reg_no) {
  const mins = parseInt(prompt(`Minutes to add for ${reg_no}:`, '10'));
  if (!mins || isNaN(mins)) return;
  const res = await fetch(`/api/admin/session/${reg_no}/extend`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ minutes: mins }),
  });
  if (res.ok) {
    alert(`✓ Added ${mins} minutes for ${reg_no}.`);
    loadDash();
  } else {
    alert('Failed — session may already be submitted.');
  }
}

async function resetSession(reg_no) {
  if (!confirm(`⚠ FULL RESET for ${reg_no}?\nThis deletes ALL answers and session. Cannot be undone.`)) return;
  const res = await fetch(`/api/admin/session/${reg_no}`, {
    method: 'DELETE',
    credentials: 'include',
  });
  if (res.ok) {
    alert(`Session for ${reg_no} has been reset.`);
    loadDash();
  }
}
