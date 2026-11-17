// Reveals "Select all" and "Clear" buttons and ticks or clears the checkboxes in the same form.
// `data-wm-check-all-for` selects the input name; defaults to "characters" so the
// downtime/points_award and bulk_award keep working unchanged.
// Buttons use data-wm-check-all / data-wm-check-none. A master checkbox with
// data-wm-check-all applies its own checked state to all boxes of the named input.
document.querySelectorAll("[data-wm-check-all], [data-wm-check-none]").forEach(function (el) {
  el.hidden = false;
  var name = el.getAttribute("data-wm-check-all-for") || "characters";
  el.addEventListener("click", function () {
    var on = el.type === "checkbox" ? el.checked : el.hasAttribute("data-wm-check-all");
    el.form.querySelectorAll('input[name="' + name + '"]').forEach(function (box) {
      box.checked = on;
    });
  });
});

// Apply `on` to every input named `name` inside `form`. HTMX-safe: safe to call from
// inline handlers that survive outerHTML swaps (e.g. the inbox select-all checkbox).
window.wmSetCheckboxes = function (form, name, on) {
  form.querySelectorAll('input[name="' + name + '"]').forEach(function (box) {
    box.checked = on;
  });
};
