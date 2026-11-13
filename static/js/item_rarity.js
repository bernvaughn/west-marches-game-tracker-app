(function () {
  if (window.wmRarityHint) return;
  window.wmRarityHint = true;
  function update(select) {
    var form = select.form;
    if (!form) return;
    var hint = form.querySelector("[data-rarity-hint]");
    if (!hint) return;
    hint.querySelectorAll("[data-rarity-item]").forEach(function (el) {
      el.hidden = !!select.value && el.getAttribute("data-rarity-item") !== select.value;
    });
  }
  function init() {
    document.querySelectorAll("select[data-rarity-select]").forEach(update);
  }
  document.addEventListener("change", function (e) {
    if (e.target.matches && e.target.matches("select[data-rarity-select]")) update(e.target);
  });
  document.addEventListener("DOMContentLoaded", init);
  document.body && document.body.addEventListener("htmx:afterSettle", init);
  document.addEventListener("htmx:afterSettle", init);
  init();
})();
