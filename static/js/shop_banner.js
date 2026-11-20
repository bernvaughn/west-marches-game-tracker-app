(function () {
  // The shop switcher swaps the shop page into #main with htmx, and the
  // fragment loads this script again. Bind the delegated handlers only once,
  // or each click toggles twice and the box never opens.
  if (window.wmShopBannerBound) return;
  window.wmShopBannerBound = true;

  function activePairs() {
    return Array.prototype.slice.call(
      document.querySelectorAll(".wm-shop-banner [aria-controls]")
    )
      .map(function (button) {
        return { button: button, box: document.getElementById(button.getAttribute("aria-controls")) };
      })
      .filter(function (p) {
        return p.box;
      });
  }

  function show(open) {
    var pairs = activePairs();
    pairs.forEach(function (p) {
      var isOpen = open && p.button === open.button;
      p.box.hidden = !isOpen;
      p.button.setAttribute("aria-expanded", isOpen ? "true" : "false");
    });
  }

  show(null);

  document.body.addEventListener("click", function (e) {
    var button = e.target.closest(".wm-shop-banner [aria-controls]");
    if (!button) return;
    var pairs = activePairs();
    var matched = null;
    for (var i = 0; i < pairs.length; i++) {
      if (pairs[i].button === button) {
        matched = pairs[i];
        break;
      }
    }
    if (!matched) return;
    show(matched.box.hidden ? matched : null);
  });

  document.body.addEventListener("htmx:afterSwap", function (e) {
    if (e.target.id === "main" || e.target.querySelector(".wm-shop-banner")) {
      show(null);
    }
  });
})();

(function () {
  // Live refresh of the shop stock without reloading the page.
  // The CSP blocks Function() (no unsafe-eval), so the htmx [..] trigger filters
  // were removed from the template. The poll is driven from here instead: a
  // setInterval and a visibilitychange listener dispatch shopStockPoll on #stock,
  // which #stock's hx-trigger listens for. The refresh only runs while the tab
  // is visible.
  //
  // The shop switcher swaps the shop page into #main with htmx, and the fragment
  // loads this script again. Set up the poll only once per page, or each switch
  // adds another interval and another visibilitychange listener. Each tick looks
  // up #stock fresh, so a swapped-in #stock is picked up with no restart.
  if (window.wmShopStockPollBound) return;
  window.wmShopStockPollBound = true;

  var POLL_INTERVAL = 5000;

  function poll() {
    if (document.visibilityState !== "visible") return;
    var el = document.getElementById("stock");
    if (el) el.dispatchEvent(new Event("shopStockPoll"));
  }

  setInterval(poll, POLL_INTERVAL);

  document.addEventListener("visibilitychange", poll);
})();
