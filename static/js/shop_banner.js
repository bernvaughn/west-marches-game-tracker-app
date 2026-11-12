(function () {
  var button = document.querySelector(".wm-shop-about-toggle");
  var box = document.getElementById("shop-about");
  if (!button || !box) return;
  function set(open) {
    box.hidden = !open;
    button.setAttribute("aria-expanded", open ? "true" : "false");
    button.textContent = open ? "Hide description" : "Show description";
  }
  button.hidden = false;
  set(false);
  button.addEventListener("click", function () {
    set(box.hidden);
  });
})();
