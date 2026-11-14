// M19: size the fitted hex map to the space left in the window.
// Sets --hexmap-offset to the page height above and below the map SVG.
// Content beside the map (the side column on wide screens) does not count.
// Without JS, the CSS fallback offset in map.css applies.
(function () {
  function fit() {
    var svg = document.querySelector(".hexmap--fit svg");
    if (!svg) return;
    var box = svg.parentElement;
    var rect = svg.getBoundingClientRect();
    var top = rect.top + window.scrollY;
    // Measure content, not scrollHeight: a short page still has the window height.
    var end = 0;
    var kids = document.body.children;
    for (var k = 0; k < kids.length; k++) {
      var pos = window.getComputedStyle(kids[k]).position;
      if (pos === "fixed" || pos === "absolute") continue;
      var kr = kids[k].getBoundingClientRect();
      if (kr.height) end = Math.max(end, kr.bottom + window.scrollY);
    }
    var below = end - (top + rect.height);
    // A side item taller than the map makes the page taller; leave that out.
    var extra = 0;
    var layout = box.parentElement;
    for (var i = 0; layout && i < layout.children.length; i++) {
      var item = layout.children[i];
      if (item === box) continue;
      var r = item.getBoundingClientRect();
      if (r.top < rect.bottom && r.bottom > rect.top) {
        extra = Math.max(extra, r.bottom - rect.bottom);
      }
    }
    var offset = Math.max(0, Math.ceil(top + below - extra));
    box.style.setProperty("--hexmap-offset", offset + "px");
  }
  var timer;
  function later() {
    clearTimeout(timer);
    timer = setTimeout(fit, 100);
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", fit);
  } else {
    fit();
  }
  window.addEventListener("resize", later);
})();
