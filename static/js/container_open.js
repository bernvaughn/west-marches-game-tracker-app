/* Container opening animation (slice C).
   Plays a short shake, lid pop and staggered item reveal for a stored open
   result. Never rolls and never fetches; Replay re-plays the same DOM.
   Honours prefers-reduced-motion (instant reveal, no shake, no particles).
   Keyboard/screen-reader friendly: result is announced in an aria-live region.
 */
(function () {
  var OPEN_RESULT_ATTR = "data-wm-open-result";
  var REVEAL_ATTR = "data-wm-reveal";
  var REVEALED_ATTR = "data-wm-revealed";
  var ITEM_ATTR = "data-wm-reveal-item";
  var LIVE_ATTR = "data-wm-live";
  var REPLAY_ATTR = "data-wm-replay";
  var ARMED_CLASS = "wm-reveal--armed";
  var MODAL_ID = "app-modal";
  var REDUCED_MQ = "(prefers-reduced-motion: reduce)";
  var STAGGER_MS = 120;
  var FALLBACK_MS = 2000;

  var mq = matchMedia(REDUCED_MQ);
  var armedRoots = new Set();

  function liveText(root, text) {
    var live = root.querySelector("[" + LIVE_ATTR + "]");
    if (live) live.textContent = text;
  }

  function messageFor(root) {
    var items = Array.from(root.querySelectorAll("[" + ITEM_ATTR + "]"));
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

  function showAll(root) {
    root.classList.remove(ARMED_CLASS);
    armedRoots.delete(root);
    Array.from(root.querySelectorAll("[" + ITEM_ATTR + "]")).forEach(function (item) {
      item.style.opacity = "1";
      item.style.transform = "none";
      item.style.removeProperty("--wm-i");
    });
    var chest = root.querySelector(".wm-chest");
    if (chest) chest.style.display = "none";
  }

  function finish(root) {
    root.classList.remove(ARMED_CLASS);
    armedRoots.delete(root);
    var live = root.querySelector("[" + LIVE_ATTR + "]");
    if (live && !live.textContent) liveText(root, messageFor(root));
  }

  function animateReveal(root) {
    var items = Array.from(root.querySelectorAll("[" + ITEM_ATTR + "]"));

    /* Reduced motion: instant reveal, no animation. */
    if (mq.matches) {
      showAll(root);
      liveText(root, messageFor(root));
      return;
    }

    var chest = root.querySelector(".wm-chest");
    if (chest) chest.style.display = "block";

    /* Reset for (re)play, then re-arm so CSS animations restart. */
    root.classList.remove(ARMED_CLASS);
    root.offsetHeight; /* force reflow so a re-play restarts the animations */
    items.forEach(function (item) {
      item.style.opacity = "";
      item.style.transform = "";
      item.style.removeProperty("--wm-i");
    });
    root.classList.add(ARMED_CLASS);
    armedRoots.add(root);
    items.forEach(function (item, index) {
      item.style.setProperty("--wm-i", index);
    });

    var pending = items.length;
    var settled = false;
    var finishReveal = function () {
      if (settled) return;
      settled = true;
      items.forEach(function (item) {
        item.removeEventListener("animationend", onItemEnd);
      });
      finish(root);
    };
    var onItemEnd = function () {
      pending -= 1;
      if (pending <= 0) finishReveal();
    };
    items.forEach(function (item) {
      item.addEventListener("animationend", onItemEnd, { once: true });
    });
    setTimeout(finishReveal, FALLBACK_MS);
  }

  /* Flip to reduce mid-animation: finish every armed reveal at once. */
  mq.addEventListener("change", function (event) {
    if (!event.matches) return;
    armedRoots.forEach(function (root) {
      showAll(root);
      liveText(root, messageFor(root));
    });
  });

  function addReplayButton(root) {
    if (root.querySelector("[" + REPLAY_ATTR + "]")) return;
    var button = document.createElement("button");
    button.type = "button";
    button.className = "btn btn-outline-secondary wm-replay";
    button.setAttribute(REPLAY_ATTR, "");
    button.textContent = "Replay";
    button.addEventListener("click", function () {
      animateReveal(root);
    });
    var reveal = root.querySelector("[" + REVEAL_ATTR + "]");
    if (reveal) reveal.after(button);
    else root.append(button);
  }

  function init(root) {
    if (!root) return;
    Array.from(root.querySelectorAll("[" + OPEN_RESULT_ATTR + "]")).forEach(function (container) {
      if (container.hasAttribute(REVEALED_ATTR)) return;
      var reveal = container.querySelector("[" + REVEAL_ATTR + "]");
      if (!reveal) return;
      container.setAttribute(REVEALED_ATTR, "true");

      var start = function () {
        var items = Array.from(reveal.querySelectorAll("[" + ITEM_ATTR + "]"));
        if (!items.length) {
          /* Nothing to animate; still announce the stored result. */
          liveText(container, messageFor(container));
          return;
        }
        addReplayButton(container);
        animateReveal(container);
      };

      var modal = document.getElementById(MODAL_ID);
      if (modal && !modal.classList.contains("show")) {
        modal.addEventListener("shown.bs.modal", start, { once: true });
      } else {
        start();
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    init(document);
  });
  /* htmx swaps the result into #app-modal .modal-content; hook both swap and
   * settle so the reveal is armed regardless of swap timing. */
  document.body.addEventListener("htmx:afterSwap", function () {
    init(document);
  });
  document.body.addEventListener("htmx:afterSettle", function () {
    init(document);
  });
})();
