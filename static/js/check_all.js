// Reveals "Select all" and "Clear" buttons and ticks or clears the character boxes in the same form.
document.querySelectorAll("[data-wm-check-all], [data-wm-check-none]").forEach(function (btn) {
  btn.hidden = false;
  btn.addEventListener("click", function () {
    var on = btn.hasAttribute("data-wm-check-all");
    btn.form.querySelectorAll("input[name=characters]").forEach(function (box) {
      box.checked = on;
    });
  });
});
