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
