// Shared tooltips (U59). Add data-wm-tooltip and a title to any element; U60 can reuse it.
// Bootstrap shows the tooltip on hover and keyboard focus. Re-run after htmx swaps.
(function () {
  function init(root) {
    if (!root || !root.querySelectorAll || !window.bootstrap) return;
    var els = Array.prototype.slice.call(root.querySelectorAll('[data-wm-tooltip]'));
    if (root.matches && root.matches('[data-wm-tooltip]')) els.push(root);
    els.forEach(function (el) {
      window.bootstrap.Tooltip.getOrCreateInstance(el, { trigger: 'hover focus' });
    });
  }
  function dispose(root) {
    if (!root || !root.querySelectorAll || !window.bootstrap) return;
    root.querySelectorAll('[data-wm-tooltip]').forEach(function (el) {
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
