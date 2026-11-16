// Shared tooltips (U59). Add data-wm-tooltip and a title to any element; U60 can reuse it.
// Bootstrap shows the tooltip on hover and keyboard focus. Re-run after htmx swaps.
// Character preview tooltips (S3): fetch preview on shown.bs.tooltip for [data-wm-preview-url].
(function () {
  function init(root) {
    if (!root || !root.querySelectorAll || !window.bootstrap) return;
    var els = Array.prototype.slice.call(root.querySelectorAll('[data-wm-tooltip]'));
    if (root.matches && root.matches('[data-wm-tooltip]')) els.push(root);
    els.forEach(function (el) {
      window.bootstrap.Tooltip.getOrCreateInstance(el, { trigger: 'hover focus' });
    });
    // Character preview tooltips
    var previewEls = Array.prototype.slice.call(root.querySelectorAll('[data-wm-preview-url]'));
    previewEls.forEach(function (el) {
      var tooltip = window.bootstrap.Tooltip.getOrCreateInstance(el, {
        trigger: 'hover focus',
        html: true,
        title: 'Loading…',
      });
      // Fetch preview data when tooltip is shown
      el.addEventListener('shown.bs.tooltip', function onShow() {
        if (el.dataset.wmPreviewLoaded === 'true') return;
        var url = el.dataset.wmPreviewUrl;
        fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
          .then(function (r) {
            if (!r.ok) throw new Error('Failed to load preview');
            return r.json();
          })
          .then(function (data) {
            var html = buildPreviewHtml(data);
            tooltip.setContent({ '.tooltip-inner': html });
            el.dataset.wmPreviewLoaded = 'true';
          })
          .catch(function () {
            tooltip.setContent({ '.tooltip-inner': '<div class="text-danger small">Failed to load preview</div>' });
          });
      });
      // Reset loaded flag when tooltip hides so it refreshes next time
      el.addEventListener('hide.bs.tooltip', function () {
        el.dataset.wmPreviewLoaded = 'false';
      });
    });
  }
  function buildPreviewHtml(data) {
    var coins = data.coins_available || '—';
    var junkCount = data.junk_count || 0;
    var junkValue = data.junk_value || 0;
    var downtime = data.downtime || 0;
    var openTrades = data.open_trades || 0;
    var level = data.level ? 'Level ' + data.level : '—';
    var charClass = data.class || '—';
    var species = data.species || '—';
    return `
      <div class="wm-preview-card p-2" style="min-width: 220px;">
        <div class="d-flex align-items-center gap-2 mb-2">
          <span class="wm-avatar wm-avatar-sm" aria-hidden="true">${data.name ? data.name[0].toUpperCase() : '?'}</span>
          <div>
            <div class="fw-bold small">${escapeHtml(data.name)}</div>
            <div class="text-muted small">${escapeHtml(level)} · ${escapeHtml(charClass)} · ${escapeHtml(species)}</div>
          </div>
        </div>
        <div class="row g-1 text-center small">
          <div class="col-6"><div class="fw-bold">${escapeHtml(coins)}</div><div class="text-muted">Coins</div></div>
          <div class="col-6"><div class="fw-bold">${junkCount}</div><div class="text-muted">Junk</div></div>
          <div class="col-6"><div class="fw-bold">${downtime}</div><div class="text-muted">Downtime</div></div>
          <div class="col-6"><div class="fw-bold">${openTrades}</div><div class="text-muted">Open Trades</div></div>
        </div>
      </div>
    `;
  }
  function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
  function dispose(root) {
    if (!root || !root.querySelectorAll || !window.bootstrap) return;
    root.querySelectorAll('[data-wm-tooltip]').forEach(function (el) {
      var t = window.bootstrap.Tooltip.getInstance(el);
      if (t) t.dispose();
    });
    root.querySelectorAll('[data-wm-preview-url]').forEach(function (el) {
      var t = window.bootstrap.Tooltip.getInstance(el);
      if (t) t.dispose();
    });
  }
  document.addEventListener('DOMContentLoaded', function () { init(document); });
  document.addEventListener('htmx:load', function (e) { init(e.detail.elt); });
  document.addEventListener('htmx:beforeSwap', function (e) { dispose(e.detail.target); });
  document.addEventListener('show.bs.dropdown', function (e) {
    var t = window.bootstrap && window.bootstrap.Tooltip.getInstance(e.target);
    if (t) t.hide();
  });
})();

// Character selector dropdown item click handler
(function () {
  function init(root) {
    if (!root || !root.querySelectorAll) return;
    root.querySelectorAll('.wm-character-dropdown .dropdown-item[data-character-pk]').forEach(function (item) {
      item.addEventListener('click', function (e) {
        e.preventDefault();
        var pk = this.dataset.characterPk;
        var form = this.closest('form.character-selector');
        if (!form) return;
        var hidden = form.querySelector('#id_character_selector');
        if (hidden) hidden.value = pk;
        if (form.requestSubmit) {
          form.requestSubmit();
        } else {
          form.submit();
        }
      });
    });
  }
  document.addEventListener('DOMContentLoaded', function () { init(document); });
  document.addEventListener('htmx:load', function (e) { init(e.detail.elt); });
})();
