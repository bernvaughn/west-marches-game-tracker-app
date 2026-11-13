(function () {
  var toggles = Array.prototype.slice.call(
    document.querySelectorAll(".wm-shop-banner [aria-controls]")
  );
  var pairs = toggles
    .map(function (button) {
      return { button: button, box: document.getElementById(button.getAttribute("aria-controls")) };
    })
    .filter(function (p) {
      return p.box;
    });
  if (!pairs.length) return;
  function show(open) {
    pairs.forEach(function (p) {
      var isOpen = p === open;
      p.box.hidden = !isOpen;
      p.button.setAttribute("aria-expanded", isOpen ? "true" : "false");
    });
  }
  show(null);
  pairs.forEach(function (p) {
    p.button.addEventListener("click", function () {
      show(p.box.hidden ? p : null);
    });
  });
})();
