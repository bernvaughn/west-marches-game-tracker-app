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

    // Step timers drive the reveal. The advance timer only navigates to the
    // sheet. Page clicks and a hidden tab cancel the advance timer only, so
    // the reveal itself always completes. Each play has a run id; callbacks
    // from an older run (timers, coin count-up) do nothing.
    var stepTimers = [];
    var advanceTimer = null;
    var cancelCoins = null;
    var runId = 0;
    var finished = false;
    // Set when the player clicks the page or hides the tab during a run:
    // the reveal still completes, but it does not leave the page.
    var stayOnPage = false;

    function addStep(fn, ms) {
      stepTimers.push(setTimeout(fn, ms));
    }

    function clearSteps() {
      stepTimers.forEach(clearTimeout);
      stepTimers = [];
      if (cancelCoins) {
        cancelCoins();
        cancelCoins = null;
      }
    }

    function cancelAdvance() {
      stayOnPage = true;
      if (advanceTimer !== null) {
        clearTimeout(advanceTimer);
        advanceTimer = null;
      }
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

    function setItemsRevealed(on) {
      items.forEach(function (item) {
        item.classList.toggle(REVEALED_CLASS, on);
      });
    }

    function setCoinsHidden(on) {
      if (coinsBlock) coinsBlock.hidden = on;
    }

    function setCoinsDisplay(cp) {
      if (!coinsDisplay) return;
      coinsDisplay.textContent =
        typeof window.wmFormatCoins === "function"
          ? window.wmFormatCoins(cp)
          : cp + " cp";
    }

    function setReplayHidden(on) {
      if (replayButton) replayButton.hidden = on;
    }

    // Show the final state: all items, final coins, announcement, Replay.
    function finish(autoAdvance) {
      if (finished) return;
      finished = true;
      clearSteps();
      root.classList.remove(ARMED_CLASS);
      setItemsRevealed(true);
      setCoinsDisplay(coinsCp);
      setCoinsHidden(false);
      announce(announcementText());
      setReplayHidden(false);
      if (autoAdvance && !stayOnPage && !mq.matches) {
        advanceTimer = setTimeout(function () {
          advanceTimer = null;
          location.assign(sheetUrl);
        }, AFTER_COINS_MS);
      }
    }

    function resetForRun() {
      clearSteps();
      cancelAdvance();
      runId += 1;
      finished = false;
      stayOnPage = false;
      root.classList.remove(ARMED_CLASS);
      setItemsRevealed(false);
      setCoinsHidden(true);
      setCoinsDisplay(0);
      announce("");
      setReplayHidden(true);
      return runId;
    }

    function playMotion() {
      var run = resetForRun();
      root.classList.add(ARMED_CLASS);
      var index = 0;

      function current() {
        return run === runId && !finished;
      }

      function startCoins() {
        setCoinsHidden(false);
        if (
          coinsCp === 0 ||
          !coinsDisplay ||
          typeof window.wmAnimateCoins !== "function"
        ) {
          finish(true);
          return;
        }
        var cancel = window.wmAnimateCoins(root, coinsDisplay, coinsCp, function () {
          if (current()) finish(true);
        });
        if (current() && typeof cancel === "function") cancelCoins = cancel;
      }

      function showNext() {
        if (!current()) return;
        if (index >= items.length) {
          startCoins();
          return;
        }
        items[index].classList.add(REVEALED_CLASS);
        index += 1;
        addStep(showNext, ITEM_GAP_MS);
      }
      showNext();
    }

    function playReduced() {
      resetForRun();
      finish(false);
    }

    function play() {
      if (mq.matches) {
        playReduced();
      } else {
        playMotion();
      }
    }

    if (replayButton) {
      replayButton.addEventListener("click", function (event) {
        event.stopPropagation();
        play();
      });
    }

    // A click on the page means the player is engaged: stay on this page.
    root.addEventListener("click", function (event) {
      if (replayButton && replayButton.contains(event.target)) return;
      cancelAdvance();
    });

    document.addEventListener("visibilitychange", function () {
      if (document.hidden) cancelAdvance();
    });

    mq.addEventListener("change", function (event) {
      if (!event.matches) return;
      cancelAdvance();
      finish(false);
    });

    play();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
