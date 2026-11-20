(function () {
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
      var isOpen = p === open;
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
  var POLL_INTERVAL = 5000;
  var timer = null;

  function stockEl() {
    return document.getElementById("stock");
  }

  function poll() {
    var el = stockEl();
    if (!el) return;
    if (document.visibilityState === "visible") {
      el.dispatchEvent(new Event("shopStockPoll"));
    }
  }

  function start() {
    stop();
    timer = setInterval(poll, POLL_INTERVAL);
  }

  function stop() {
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
  }

  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible") {
      poll();
    }
  });

  // (Re)start whenever the shop content is swapped, e.g. by the shop switcher,
  // so a detached #stock is never polled and a fresh #stock is picked up.
  document.body.addEventListener("htmx:afterSwap", function (e) {
    if (e.target.id === "stock" || e.target.id === "main" || e.target.querySelector("#stock")) {
      start();
    }
  });

  start();
})();
