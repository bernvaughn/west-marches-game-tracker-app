/* Downtime wheel (D3): spin to the slice the server already chose.
   In the shared modal the spin waits for shown.bs.modal: a CSS transition
   does not run while the modal is still display:none.
   Enhancements: replay, near-miss glow, particle burst, sound toggle. */
(function () {
  var DURATION = 4000;
  var PARTICLES = 30;
  var PARTICLE_MS = 800;
  var NEAR_MISS_MS = 500;
  var SOUND_KEY = "downtimeSound";
  var REDUCED = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var AUDIO_CTX = null;

  function soundOn() {
    try { return localStorage.getItem(SOUND_KEY) === "on"; } catch (e) { return false; }
  }
  function setSound(on) {
    try { localStorage.setItem(SOUND_KEY, on ? "on" : "off"); } catch (e) {}
  }
  function ensureAudio() {
    if (AUDIO_CTX) return AUDIO_CTX;
    var Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return null;
    try { AUDIO_CTX = new Ctx(); } catch (e) { return null; }
    return AUDIO_CTX;
  }
  function playDing() {
    if (!soundOn()) return;
    var ctx = ensureAudio();
    if (!ctx) return;
    try {
      if (ctx.state === "suspended") ctx.resume();
      if (ctx.state !== "running") return;
      var t = ctx.currentTime;
      var osc = ctx.createOscillator();
      var gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(880, t);
      gain.gain.setValueAtTime(0.15, t);
      gain.gain.exponentialRampToValueAtTime(0.001, t + 0.2);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(t);
      osc.stop(t + 0.2);
    } catch (e) { /* audio blocked or unavailable */ }
  }

  function spin(disc, data, result) {
    var s = data.slices[data.chosen];
    var jitter = (Math.random() * 0.7 - 0.35) * s.angle;
    var done = false;
    function finish() {
      if (done) return;
      done = true;
      result.hidden = false;
      result.focus({ preventScroll: true });
      nearMiss(data);
      burst(data);
      playDing();
    }
    disc.style.transition = "none";
    disc.style.transform = "rotate(0deg)";
    void disc.getBoundingClientRect();
    disc.style.transition = "transform " + DURATION / 1000 + "s cubic-bezier(.15,.85,.25,1)";
    disc.style.transform = "rotate(" + (360 * 5 + data.final_rotation + jitter) + "deg)";
    disc.addEventListener("transitionend", finish);
    setTimeout(finish, DURATION + 1000);
  }

  function nearMiss(data) {
    if (REDUCED) return;
    var fig = document.querySelector("[data-downtime-wheel]");
    if (!fig) return;
    var chosen = data.chosen;
    var indices = (fig.dataset.nearMiss || "").split(/\s+/).map(Number).filter(Number.isFinite);
    var paths = fig.querySelectorAll(".wm-wheel-disc path");
    indices.forEach(function (i) {
      if (i === chosen) return;
      var p = paths[i];
      if (p) p.classList.add("wm-wheel-slice-near-miss");
    });
    setTimeout(function () {
      indices.forEach(function (i) {
        var p = paths[i];
        if (p) p.classList.remove("wm-wheel-slice-near-miss");
      });
    }, NEAR_MISS_MS);
  }

  function burst(data) {
    if (REDUCED) return;
    var fig = document.querySelector("[data-downtime-wheel]");
    if (!fig) return;
    var canvas = fig.querySelector(".wm-wheel-particles");
    if (!canvas) return;
    var c = canvas.getContext("2d");
    if (!c) return;
    var dpr = window.devicePixelRatio || 1;
    var w = canvas.offsetWidth || 220;
    var h = canvas.offsetHeight || 220;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    c.scale(dpr, dpr);
    var cx = w / 2;
    var cy = h / 2;
    var particles = [];
    for (var i = 0; i < PARTICLES; i++) {
      var angle = Math.random() * Math.PI * 2;
      var speed = 0.4 + Math.random() * 2.6;
      particles.push({
        x: cx, y: cy,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        size: 1 + Math.random() * 3,
        color: "hsl(45, 100%, 70%)"
      });
    }
    var start = performance.now();
    function frame(now) {
      var t = Math.min((now - start) / PARTICLE_MS, 1);
      c.clearRect(0, 0, w, h);
      particles.forEach(function (p) {
        c.globalAlpha = 1 - t;
        c.fillStyle = p.color;
        c.beginPath();
        c.arc(p.x + p.vx * t * 70, p.y + p.vy * t * 70, p.size * (1 - t), 0, Math.PI * 2);
        c.fill();
      });
      if (t < 1) requestAnimationFrame(frame);
      else c.clearRect(0, 0, w, h);
    }
    requestAnimationFrame(frame);
  }

  function setupSound(root) {
    root.querySelectorAll("[data-sound-toggle]").forEach(function (btn) {
      if (btn.dataset.soundSetup) return;
      btn.dataset.soundSetup = "1";
      btn.textContent = soundOn() ? "🔊" : "🔇";
      btn.addEventListener("click", function () {
        var on = soundOn();
        setSound(!on);
        btn.textContent = soundOn() ? "🔊" : "🔇";
        if (!on) ensureAudio(); // user gesture: enable audio context
      });
    });
  }

  function init(root) {
    root.querySelectorAll("[data-downtime-wheel]").forEach(function (fig) {
      if (fig.dataset.started) return;
      fig.dataset.started = "1";
      if (REDUCED) return;
      var disc = fig.querySelector(".wm-wheel-disc");
      var script = fig.querySelector('script[type="application/json"]');
      var scope = fig.parentElement;
      var result = scope && scope.querySelector("[data-wheel-result]");
      if (!disc || !script || !result) return;
      var data = JSON.parse(script.textContent);
      result.hidden = true;
      var modal = fig.closest(".modal");
      if (modal && !modal.classList.contains("show")) {
        modal.addEventListener("shown.bs.modal", function () { spin(disc, data, result); }, { once: true });
      } else {
        spin(disc, data, result);
      }
    });
    setupSound(root);
  }
  document.addEventListener("DOMContentLoaded", function () { init(document); });
  document.addEventListener("htmx:afterSwap", function (evt) { init(evt.detail.target || document); });
})();
