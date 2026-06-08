// Sidebar toggle
function toggleSidebar() {
  const s = document.getElementById('sidebar');
  const m = document.querySelector('.main-content');
  if (s) {
    s.classList.toggle('collapsed');
    if (m) {
      m.style.marginLeft = s.classList.contains('collapsed') ? '70px' : '260px';
    }
  }
}

// Delete dropdown
function openDelMenu(id) {
  const menu = document.getElementById('del-menu-' + id);
  if (!menu) return;
  const isOpen = menu.classList.contains('open');
  document.querySelectorAll('.del-menu.open').forEach(function (m) { m.classList.remove('open'); });
  if (!isOpen) menu.classList.add('open');
}
document.addEventListener('click', function (e) {
  if (!e.target.closest('.del-wrap')) {
    document.querySelectorAll('.del-menu.open').forEach(function (m) { m.classList.remove('open'); });
  }
});

// Current date in topbar
(function () {
  const el = document.getElementById('current-date');
  if (el) {
    el.textContent = new Date().toLocaleDateString('en-IN', {
      weekday: 'short', day: 'numeric', month: 'short', year: 'numeric'
    });
  }
})();

// Auto-dismiss flash messages after 4s
(function () {
  setTimeout(function () {
    document.querySelectorAll('.flash').forEach(function (el) {
      el.style.transition = 'opacity .4s';
      el.style.opacity = '0';
      setTimeout(function () { el.remove(); }, 400);
    });
  }, 4000);
})();

// Confirm delete
document.addEventListener('click', function (e) {
  const btn = e.target.closest('[data-confirm]');
  if (btn) {
    if (!confirm(btn.dataset.confirm || 'Are you sure?')) {
      e.preventDefault();
    }
  }
});

// Submit filter form on select change
document.addEventListener('change', function (e) {
  if (e.target.matches('.auto-submit')) {
    e.target.closest('form').submit();
  }
});

// Toggle password visibility
function togglePw() {
  const pw = document.getElementById('password');
  if (pw) {
    pw.type = pw.type === 'password' ? 'text' : 'password';
  }
}

