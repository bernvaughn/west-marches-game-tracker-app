/* Live chance percentages for the downtime entries formset. */
(function () {
  var form = document.querySelector("[data-downtime-entries]");
  if (!form) return;
  var rows = Array.prototype.slice.call(form.querySelectorAll("[data-entry-row]"));
  function live(row) {
    var del = row.querySelector('input[type="checkbox"][name$="-DELETE"]');
    var label = row.querySelector('input[name$="-label"]');
    var weight = row.querySelector("[data-weight]");
    if (del && del.checked) return 0;
    if (label && !label.value.trim()) return 0;
    return Math.max(0, parseInt(weight && weight.value, 10) || 0);
  }
  function update() {
    var weights = rows.map(live);
    var total = weights.reduce(function (a, b) { return a + b; }, 0);
    rows.forEach(function (row, i) {
      var out = row.querySelector("[data-chance]");
      if (!out) return;
      out.textContent = weights[i] && total ? (weights[i] * 100 / total).toFixed(1) + "%" : "-";
    });
  }
  form.addEventListener("input", update);
  form.addEventListener("change", update);
  update();
})();
