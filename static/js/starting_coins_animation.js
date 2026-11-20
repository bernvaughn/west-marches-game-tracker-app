/* Starting coin animation.
   Counts the starting coins up from zero on a new character sheet.
   Honours prefers-reduced-motion (instant final amount, no animation).
   Re-armed on htmx:afterSwap so a re-rendered sheet re-animates.
   Loaded with defer; CSP script-src 'self' compatible (no inline script).
 */
(function () {
  function formatCoins(cp) {
    if (cp === 0) return '0 cp';
    var sign = cp < 0 ? '-' : '';
    var absCp = Math.abs(cp);
    var CP_PER_SP = 10;
    var CP_PER_GP = 100;
    var CP_PER_PP = 1000;
    var pp = 0, gp = 0, sp = 0, copper = 0;
    if (absCp >= 10000 * CP_PER_GP) {
      pp = Math.floor(absCp / CP_PER_PP);
      var rest = absCp % CP_PER_PP;
      gp = Math.floor(rest / CP_PER_GP);
      rest = rest % CP_PER_GP;
      sp = Math.floor(rest / CP_PER_SP);
      copper = rest % CP_PER_SP;
    } else {
      gp = Math.floor(absCp / CP_PER_GP);
      var rest = absCp % CP_PER_GP;
      sp = Math.floor(rest / CP_PER_SP);
      copper = rest % CP_PER_SP;
    }
    var parts = [];
    if (pp) parts.push(pp.toLocaleString() + ' pp');
    if (gp) parts.push(gp.toLocaleString() + ' gp');
    if (sp) parts.push(sp.toLocaleString() + ' sp');
    if (copper) parts.push(copper.toLocaleString() + ' cp');
    return sign + (parts.length ? parts.join(' ') : '0 cp');
  }

  function animateCoins(container) {
    var targetCp = parseInt(container.dataset.coins, 10);
    if (isNaN(targetCp)) return;
    var display = container.querySelector('#starting-coins-display');
    if (!display) return;

    var prefersReduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReduced) {
      display.textContent = formatCoins(targetCp);
      return;
    }

    var DURATION = 2000;
    var startTime = null;
    function step(timestamp) {
      if (!startTime) startTime = timestamp;
      var progress = Math.min((timestamp - startTime) / DURATION, 1);
      var currentCp = Math.floor(progress * targetCp);
      display.textContent = formatCoins(currentCp);
      if (progress < 1) {
        requestAnimationFrame(step);
      } else {
        display.textContent = formatCoins(targetCp);
      }
    }
    requestAnimationFrame(step);
  }

  function init(root) {
    root.querySelectorAll('#starting-coins-animation').forEach(function (container) {
      if (container.dataset.started) return;
      container.dataset.started = '1';
      animateCoins(container);
    });
  }

  document.addEventListener('DOMContentLoaded', function () { init(document); });
  document.addEventListener('htmx:afterSwap', function (evt) { init(evt.detail.target || document); });
})();
