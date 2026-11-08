/* ============================================================
   main.js — Aurora Dark Finance Tracker
   Shared UI Helpers, Modals, Toasts & Chart.js Defaults
   (All charts are dynamically fed by Flask templates with real CSV data)
============================================================ */

// ══════════════════════════════════════════
// GLOBAL UTILITIES & FORMATTERS
// ══════════════════════════════════════════

/** Format number as Indian Rupee currency */
function formatCurrency(n) {
  return '₹' + Number(n).toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
}

/** Format date string to readable form */
function formatDate(d) {
  if (!d) return '';
  return new Date(d).toLocaleDateString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric'
  });
}

/** Show toast notification */
function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  if (!container) return;
  const icons = { success: '✅', error: '❌', info: 'ℹ️' };
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span class="toast-icon">${icons[type] || 'ℹ️'}</span>
                     <span class="toast-msg">${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(60px)';
    toast.style.transition = '0.3s';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

/** Open modal dialog */
function openModal(id) {
  const el = document.getElementById(id);
  if (el) {
    el.classList.add('open');
    document.body.style.overflow = 'hidden';
  }
}

/** Close modal dialog */
function closeModal(id) {
  const el = document.getElementById(id);
  if (el) {
    el.classList.remove('open');
    document.body.style.overflow = '';
  }
}

/** Sidebar toggle for mobile responsive drawer */
function toggleSidebar() {
  const sb = document.querySelector('.sidebar');
  const overlay = document.querySelector('.sidebar-overlay');
  if (sb) sb.classList.toggle('open');
  if (overlay) overlay.classList.toggle('open');
}

// ══════════════════════════════════════════
// EVENT LISTENERS & DOM SETUP
// ══════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
  // Close sidebar when overlay is clicked
  const overlay = document.querySelector('.sidebar-overlay');
  if (overlay) overlay.addEventListener('click', toggleSidebar);

  // Update date in topbar
  const dateEl = document.getElementById('topbarDate');
  if (dateEl) {
    const now = new Date();
    dateEl.textContent = now.toLocaleDateString('en-IN', {
      weekday: 'short', day: '2-digit', month: 'long', year: 'numeric'
    });
  }

  // Tab controls
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const group = btn.dataset.tabGroup || btn.closest('.tabs')?.dataset.group;
      const target = btn.dataset.tab;
      document.querySelectorAll(`.tab-btn[data-tab-group="${group}"]`).forEach(b => b.classList.remove('active'));
      document.querySelectorAll(`.tab-pane[data-tab-group="${group}"]`).forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      const pane = document.querySelector(`.tab-pane[data-tab="${target}"][data-tab-group="${group}"]`);
      if (pane) pane.classList.add('active');
    });
  });

  // Modal close on backdrop click
  document.querySelectorAll('.modal-overlay').forEach(overlayEl => {
    overlayEl.addEventListener('click', e => {
      if (e.target === overlayEl) closeModal(overlayEl.id);
    });
  });

  // Toggle password visibility
  document.querySelectorAll('.toggle-password').forEach(btn => {
    btn.addEventListener('click', () => {
      const inp = btn.previousElementSibling;
      if (!inp) return;
      inp.type = inp.type === 'password' ? 'text' : 'password';
      btn.innerHTML = inp.type === 'password' ? '👁️' : '🙈';
    });
  });

  // Animate any progress bars on page load
  animateProgressBars();
});

// ══════════════════════════════════════════
// CHART.JS GLOBAL CONFIGURATION (Aurora Dark)
// ══════════════════════════════════════════

if (typeof Chart !== 'undefined') {
  Chart.defaults.color = '#94A3B8';
  Chart.defaults.font.family = "'Inter', 'Segoe UI', system-ui, sans-serif";
  Chart.defaults.font.size = 12;
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.pointStyleWidth = 10;
  Chart.defaults.plugins.tooltip.backgroundColor = '#17213B';
  Chart.defaults.plugins.tooltip.titleColor = '#F8FAFC';
  Chart.defaults.plugins.tooltip.bodyColor = '#94A3B8';
  Chart.defaults.plugins.tooltip.borderColor = 'rgba(255,255,255,0.08)';
  Chart.defaults.plugins.tooltip.borderWidth = 1;
  Chart.defaults.plugins.tooltip.padding = 12;
  Chart.defaults.plugins.tooltip.cornerRadius = 10;
  Chart.defaults.plugins.tooltip.callbacks.label = function(ctx) {
    const val = ctx.parsed.y ?? ctx.parsed;
    if (typeof val === 'number') return ' ₹' + val.toLocaleString('en-IN');
    return ctx.label || '';
  };
}

// ══════════════════════════════════════════
// LIVE TRANSACTION SEARCH & FILTER
// ══════════════════════════════════════════

function filterTransactions() {
  const search = document.getElementById('txSearch')?.value.toLowerCase() || '';
  const type   = document.getElementById('txTypeFilter')?.value.toLowerCase() || '';
  const rows   = document.querySelectorAll('.tx-row');
  rows.forEach(row => {
    const text = row.textContent.toLowerCase();
    const matchSearch = !search || text.includes(search);
    const rowType = row.dataset.type || '';
    const matchType = !type || rowType === type;
    row.style.display = matchSearch && matchType ? '' : 'none';
  });
}

// ══════════════════════════════════════════
// PROGRESS BARS ANIMATION
// ══════════════════════════════════════════

function animateProgressBars() {
  document.querySelectorAll('.progress-bar-fill[data-pct]').forEach(bar => {
    const pct = parseFloat(bar.dataset.pct);
    bar.style.width = '0%';
    requestAnimationFrame(() => {
      setTimeout(() => { bar.style.width = Math.min(pct, 100) + '%'; }, 200);
    });
    // Dynamically adjust color thresholds
    if (pct > 100) {
      bar.classList.remove('progress-teal', 'progress-income', 'progress-warn');
      bar.classList.add('progress-danger');
    } else if (pct > 75) {
      bar.classList.remove('progress-teal', 'progress-income', 'progress-danger');
      bar.classList.add('progress-warn');
    }
  });
}
