/* Container fanfare animation (S2): items pop out of the opened container.
   - Container icon pops large in the middle.
   - Item icons pop out one by one (~250 ms apart) with small bounce along slightly different arcs.
   - Items settle into the row with name and quantity fading in.
   - "Replay" button replays the animation from the same stored data (never calls the server).
   - Sound toggle (off by default), choice remembered in localStorage key "containerFanfareSound".
   - Honours prefers-reduced-motion (final row shown immediately, no animation).
   - Empty result: shows a short, friendly message and no animation.
   - Uses CSS animations and Web Animations API only. No libraries. No inline script/style (CSP compliant).
 */
(function () {
  var FANFARE_ATTR = "data-fanfare";
  var CONTAINER_ICON_ATTR = "data-container-icon";
  var CONTAINER_ICON_CLASS = "wm-fanfare-container-icon";
  var REVEAL_ATTR = "data-wm-reveal";
  var REVEAL_ITEM_ATTR = "data-wm-reveal-item";
  var LIVE_ATTR = "data-wm-live";
  var REPLAY_ATTR = "data-wm-fanfare-replay";
  var SOUND_TOGGLE_ATTR = "data-wm-fanfare-sound";
  var ARMED_CLASS = "wm-fanfare--armed";
  var SOUND_KEY = "containerFanfareSound";
  var REDUCED_MQ = "(prefers-reduced-motion: reduce)";
  var STAGGER_MS = 250;
  var RUN_ATTR = "data-wm-fanfare-run";
  var IN_FLIGHT = new Map(); // root => {timer, items, handler} for the in-flight run
  var AUDIO_CTX = null;
  var mq = window.matchMedia && window.matchMedia(REDUCED_MQ);

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
  function playPop() {
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
      osc.frequency.setValueAtTime(660, t);
      osc.frequency.exponentialRampToValueAtTime(1320, t + 0.08);
      gain.gain.setValueAtTime(0.12, t);
      gain.gain.exponentialRampToValueAtTime(0.001, t + 0.15);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(t);
      osc.stop(t + 0.15);
    } catch (e) { /* audio blocked or unavailable */ }
  }
  function playSettle() {
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
      osc.frequency.exponentialRampToValueAtTime(440, t + 0.12);
      gain.gain.setValueAtTime(0.1, t);
      gain.gain.exponentialRampToValueAtTime(0.001, t + 0.18);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(t);
      osc.stop(t + 0.18);
    } catch (e) { /* audio blocked or unavailable */ }
  }

  function liveText(root, text) {
    var live = root.querySelector("[" + LIVE_ATTR + "]");
    if (live) live.textContent = text;
  }

  function messageFor(root) {
    var items = Array.from(root.querySelectorAll("[" + REVEAL_ITEM_ATTR + "]"));
    var heading = root.querySelector("h2");
    var parts = [];
    if (heading && heading.textContent) parts.push(heading.textContent.trim());
    if (items.length) {
      parts.push("You received: " + items.map(function (item) { return item.textContent.trim(); }).join(", ") + ".");
    } else {
      parts.push("Nothing was inside.");
    }
    return parts.join(" ");
  }

  function showFinalRow(root) {
    root.classList.remove(ARMED_CLASS);
    var items = root.querySelectorAll("[" + REVEAL_ITEM_ATTR + "]");
    items.forEach(function (item) {
      item.style.opacity = "";
      item.style.transform = "";
      item.style.removeProperty("--wm-fanfare-i");
      item.style.removeProperty("--wm-fanfare-angle");
      item.style.removeProperty("--wm-fanfare-distance");
    });
    var containerIcon = root.querySelector("." + CONTAINER_ICON_CLASS);
    if (containerIcon) containerIcon.style.display = "none";
    var reveal = root.querySelector("[" + REVEAL_ATTR + "]");
    if (reveal) reveal.style.display = "";
  }

  function cancelFanfareRun(root) {
    var run = IN_FLIGHT.get(root);
    if (!run) return;
    clearTimeout(run.timer);
    run.items.forEach(function (item) {
      item.removeEventListener("animationend", run.handler);
    });
    IN_FLIGHT.delete(root);
  }

  function animateFanfare(root) {
    var reveal = root.querySelector("[" + REVEAL_ATTR + "]");
    var items = Array.from(reveal ? reveal.querySelectorAll("[" + REVEAL_ITEM_ATTR + "]") : []);
    var containerIconEl = root.querySelector("." + CONTAINER_ICON_CLASS);

    if (!items.length) {
      liveText(root, messageFor(root));
      return;
    }

    /* Reduced motion: instant reveal, no animation. */
    if (mq && mq.matches) {
      showFinalRow(root);
      liveText(root, messageFor(root));
      return;
    }

    /* Cancel any in-flight run on this root so Replay during a run restarts
       cleanly: its listeners and timer are dropped. */
    cancelFanfareRun(root);

    /* Guard each run with a counter on root so it settles only once per run. */
    var run = (parseInt(root.getAttribute(RUN_ATTR) || "0", 10) || 0) + 1;
    root.setAttribute(RUN_ATTR, String(run));

    /* Prepare the stage: show container icon large in middle.
       Do NOT hide the reveal row: items inside a `display: none` parent never
       animate, so animationend never fires and showFinalRow() is never called.
       Items are position: absolute while armed, so the reveal box collapses
       by itself while they pop out. */
    if (containerIconEl) {
      containerIconEl.style.display = "block";
      containerIconEl.style.fontSize = "clamp(4rem, 15vw, 8rem)";
    }

    /* Arm for animation (CSS animations will run). */
    root.classList.remove(ARMED_CLASS);
    root.offsetHeight; // force reflow for replay
    items.forEach(function (item, index) {
      item.style.setProperty("--wm-fanfare-i", index);
      // Slightly different arc for each item
      var angle = -60 + (index * 25) % 120; // -60 to +60 degrees spread
      var distance = 180 + (index * 30) % 100; // 180-280px spread
      item.style.setProperty("--wm-fanfare-angle", angle + "deg");
      item.style.setProperty("--wm-fanfare-distance", distance + "px");
      item.style.opacity = "";
      item.style.transform = "";
    });
    root.classList.add(ARMED_CLASS);

    /* Animate items one by one with stagger. Only the pop animation ending
       on the item itself counts: the settle animation also fires animationend,
       and child elements bubble it up. */
    var pending = items.length;
    var settled = false;
    var timer = null;

    function finish() {
      if (settled) return;
      if (root.getAttribute(RUN_ATTR) != String(run)) return;
      settled = true;
      cancelFanfareRun(root);
      showFinalRow(root);
      liveText(root, messageFor(root));
      playSettle();
    }

    function onItemEnd(event) {
      if (settled) return;
      if (root.getAttribute(RUN_ATTR) != String(run)) return;
      if (event.target !== event.currentTarget) return;
      if (event.animationName !== "wm-fanfare-item-pop") return;
      pending -= 1;
      if (pending <= 0) finish();
    }

    items.forEach(function (item) {
      item.addEventListener("animationend", onItemEnd, { once: true });
    });

    /* Timer fallback: settle even if an animationend is lost (tab in
       background, Firefox). Fires after the last staggered pop would end. */
    timer = setTimeout(finish, (items.length - 1) * STAGGER_MS + 500 + 150);

    IN_FLIGHT.set(root, { timer: timer, items: items, handler: onItemEnd });

    /* Trigger pop sounds with stagger. */
    items.forEach(function (item, index) {
      setTimeout(playPop, index * STAGGER_MS);
    });
  }

  function addReplayButton(root) {
    if (root.querySelector("[" + REPLAY_ATTR + "]")) return;
    var button = document.createElement("button");
    button.type = "button";
    button.className = "btn btn-outline-secondary wm-fanfare-replay";
    button.setAttribute(REPLAY_ATTR, "");
    button.textContent = "Replay";
    button.addEventListener("click", function () {
      animateFanfare(root);
    });
    var reveal = root.querySelector("[" + REVEAL_ATTR + "]");
    if (reveal) reveal.after(button);
    else root.append(button);
  }

  function addSoundToggle(root) {
    if (root.querySelector("[" + SOUND_TOGGLE_ATTR + "]")) return;
    var button = document.createElement("button");
    button.type = "button";
    button.className = "btn btn-outline-secondary wm-fanfare-sound ms-2";
    button.setAttribute(SOUND_TOGGLE_ATTR, "");
    button.setAttribute("aria-pressed", soundOn() ? "true" : "false");
    button.setAttribute("aria-label", "Toggle fanfare sound");
    button.textContent = soundOn() ? "🔊" : "🔇";
    button.addEventListener("click", function () {
      var on = !soundOn();
      setSound(on);
      button.textContent = on ? "🔊" : "🔇";
      button.setAttribute("aria-pressed", on ? "true" : "false");
      if (on) ensureAudio(); // user gesture enables audio context
    });
    var replayBtn = root.querySelector("[" + REPLAY_ATTR + "]");
    if (replayBtn) replayBtn.after(button);
    else {
      var reveal = root.querySelector("[" + REVEAL_ATTR + "]");
      if (reveal) reveal.after(button);
      else root.append(button);
    }
  }

  function init(root) {
    if (!root) return;
    Array.from(root.querySelectorAll("[" + FANFARE_ATTR + "]")).forEach(function (container) {
      if (container.hasAttribute("data-wm-fanfare-init")) return;
      container.setAttribute("data-wm-fanfare-init", "true");

      var reveal = container.querySelector("[" + REVEAL_ATTR + "]");
      if (!reveal) return;

      var items = Array.from(reveal.querySelectorAll("[" + REVEAL_ITEM_ATTR + "]"));
      if (!items.length) {
        liveText(container, messageFor(container));
        return;
      }

      addReplayButton(container);
      addSoundToggle(container);

      var start = function () {
        animateFanfare(container);
      };

      var modal = document.getElementById("app-modal");
      if (modal && !modal.classList.contains("show")) {
        modal.addEventListener("shown.bs.modal", start, { once: true });
      } else {
        start();
      }
    });
  }

  /* Listen for reduced-motion changes mid-animation. */
  if (mq && mq.addEventListener) {
    mq.addEventListener("change", function (event) {
      if (!event.matches) return;
      document.querySelectorAll("[" + FANFARE_ATTR + "]." + ARMED_CLASS).forEach(function (root) {
        showFinalRow(root);
        liveText(root, messageFor(root));
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    init(document);
  });
  document.body.addEventListener("htmx:afterSwap", function (evt) {
    init(evt.detail.target || document);
  });
  document.body.addEventListener("htmx:afterSettle", function (evt) {
    init(evt.detail.target || document);
  });
})();