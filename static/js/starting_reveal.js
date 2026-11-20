/* Starting gear reveal.
   Shows the saved 'Starting equipment' ledger entry: the items one by one,
   then the starting coins counting up, then auto-advance to the character
   sheet. Never rolls and never fetches; Replay re-plays the same DOM.
   Honours prefers-reduced-motion (everything at once, no auto-advance).
   Keyboard/screen-reader friendly: the result is announced once in an
   aria-live region. Loaded with defer; CSP script-src 'self' compatible.
 */
(function () {
  var ROOT_ATTR = "data-wm-starting-reveal";
  var SHEET_URL_ATTR = "data-sheet-url";
  var COINS_ATTR = "data-coins";
  var ITEM_ATTR = "data-wm-reveal-item";
  var LIVE_ATTR = "data-wm-live";
  var COINS_BLOCK_ATTR = "data-wm-coins";
  var COINS_DISPLAY_ATTR = "data-wm-coins-display";
  var REVEALED_ATTR = "data-wm-revealed";
  var REPLAY_ATTR = "data-wm-replay";
  var ARMED_CLASS = "wm-reveal--armed";
  var REVEALED_CLASS = "is-revealed";
  var REDUCED_MQ = "(prefers-reduced-motion: reduce)";
  var ITEM_GAP_MS = 600;
  var AFTER_COINS_MS = 2500;

  var mq = matchMedia(REDUCED_MQ);

  function init() {
    document.querySelectorAll("[" + ROOT_ATTR + "]").forEach(setup);
  }

  function setup(root) {
    if (root.hasAttribute(REVEALED_ATTR)) return;
    root.setAttribute(REVEALED_ATTR, "true");

    var sheetUrl = root.getAttribute(SHEET_URL_ATTR);
    var coinsCp = parseInt(root.getAttribute(COINS_ATTR), 10) || 0;
    var items = Array.from(root.querySelectorAll("[" + ITEM_ATTR + "]"));
    var live = root.querySelector("[" + LIVE_ATTR + "]");
    var coinsBlock = root.querySelector("[" + COINS_BLOCK_ATTR + "]");
    var coinsDisplay = root.querySelector("[" + COINS_DISPLAY_ATTR + "]");
    var replayButton = root.querySelector("[" + REPLAY_ATTR + "]");

    var timers = [];
    var finished = false;
    var armed = false;

    function addTimer(fn, ms) {
      var handle = setTimeout(fn, ms);
      timers.push(handle);
    }

    function clearTimers() {
      timers.forEach(clearTimeout);
      timers = [];
    }

    function announce(text) {
      if (live) live.textContent = text;
    }

    function announcementText() {
      var texts = items.map(function (item) {
        return item.textContent.trim();
      });
      var parts = [];
      if (texts.length) {
        parts.push("You received: " + texts.join(", ") + ".");
      } else {
        parts.push("No items, only coins.");
      }
      if (coinsCp > 0 && typeof window.wmFormatCoins === "function") {
        parts.push("Starting coins: " + window.wmFormatCoins(coinsCp) + ".");
      }
      return parts.join(" ");
    }

    function showItems() {
      items.forEach(function (item) {
        item.classList.add(REVEALED_CLASS);
      });
    }

    function hideItems() {
      items.forEach(function (item) {
        item.classList.remove(REVEALED_CLASS);
      });
    }

    function showCoins() {
      if (coinsBlock) coinsBlock.hidden = false;
    }

    function hideCoins() {
      if (coinsBlock) coinsBlock.hidden = true;
    }

    function resetCoinsDisplay() {
      if (coinsDisplay) coinsDisplay.textContent = "0 cp";
    }

    function showReplay() {
      if (replayButton) replayButton.hidden = false;
    }

    function hideReplay() {
      if (replayButton) replayButton.hidden = true;
    }

    function finish() {
      if (finished) return;
      finished = true;
      armed = false;
      clearTimers();
      root.classList.remove(ARMED_CLASS);
      showCoins();
      announce(announcementText());
      showReplay();
      if (!mq.matches) {
        addTimer(function () {
          location.assign(sheetUrl);
        }, AFTER_COINS_MS);
      }
    }

    function playMotion() {
      armed = true;
      root.classList.add(ARMED_CLASS);
      resetCoinsDisplay();

      var index = 0;
      function showNext() {
        if (finished) return;
        if (index >= items.length) {
          startCoins();
          return;
        }
        items[index].classList.add(REVEALED_CLASS);
        index += 1;
        addTimer(showNext, ITEM_GAP_MS);
      }
      showNext();

      function startCoins() {
        if (finished) return;
        showCoins();
        if (
          coinsCp === 0 ||
          !coinsDisplay ||
          typeof window.wmAnimateCoins !== "function"
        ) {
          finish();
          return;
        }
        window.wmAnimateCoins(root, coinsDisplay, coinsCp, finish);
      }
    }

    function playReduced() {
      showItems();
      showCoins();
      finish();
    }

    function replay() {
      clearTimers();
      finished = false;
      armed = false;
      root.classList.remove(ARMED_CLASS);
      hideItems();
      resetCoinsDisplay();
      hideCoins();
      if (live) live.textContent = "";
      hideReplay();
      if (mq.matches) {
        playReduced();
      } else {
        playMotion();
      }
    }

    if (replayButton) {
      replayButton.addEventListener("click", replay);
    }

    root.addEventListener("click", clearTimers);

    document.addEventListener("visibilitychange", function () {
      if (document.hidden) clearTimers();
    });

    mq.addEventListener("change", function (event) {
      if (!event.matches || finished || !armed) return;
      clearTimers();
      armed = false;
      root.classList.remove(ARMED_CLASS);
      showItems();
      showCoins();
      announce(announcementText());
      showReplay();
      finished = true;
    });

    if (mq.matches) {
      playReduced();
    } else {
      playMotion();
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
