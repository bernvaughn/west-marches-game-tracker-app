/* Downtime wheel (D3): spin to the slice the server already chose. */
(function () {
  var DURATION = 4000;
  function init(root) {
    root.querySelectorAll("[data-downtime-wheel]").forEach(function (fig) {
      if (fig.dataset.started) return;
      fig.dataset.started = "1";
      if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
      var disc = fig.querySelector(".wm-wheel-disc");
      var script = fig.querySelector('script[type="application/json"]');
      var scope = fig.parentElement;
      var result = scope && scope.querySelector("[data-wheel-result]");
      if (!disc || !script || !result) return;
      var data = JSON.parse(script.textContent);
      var s = data.slices[data.chosen];
      var jitter = (Math.random() * 0.7 - 0.35) * s.angle;
      var done = false;
      function finish() {
        if (done) return;
        done = true;
        result.hidden = false;
        result.focus({ preventScroll: true });
      }
      result.hidden = true;
      disc.style.transition = "none";
      disc.style.transform = "rotate(0deg)";
      void disc.getBoundingClientRect();
      disc.style.transition = "transform " + DURATION / 1000 + "s cubic-bezier(.15,.85,.25,1)";
      disc.style.transform = "rotate(" + (360 * 5 + data.final_rotation + jitter) + "deg)";
      disc.addEventListener("transitionend", finish);
      setTimeout(finish, DURATION + 1000);
    });
  }
  document.addEventListener("DOMContentLoaded", function () { init(document); });
  document.addEventListener("htmx:afterSwap", function (evt) { init(evt.detail.target || document); });
})();
