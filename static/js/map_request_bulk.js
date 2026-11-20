document.addEventListener("DOMContentLoaded", function () {
  var btn = document.getElementById("bulk-approve-btn");
  var allBox = document.getElementById("bulk-select-all");
  var boxes = document.querySelectorAll('input[name="requests"]');
  if (!btn || !boxes.length) return;
  function update() {
    var checked = document.querySelectorAll('input[name="requests"]:checked');
    btn.hidden = !checked.length;
    document.getElementById("bulk-count").textContent = checked.length;
    if (allBox) {
      allBox.checked = checked.length === boxes.length && boxes.length > 0;
    }
  }
  boxes.forEach(function (b) { b.addEventListener("change", update); });
  if (allBox) {
    allBox.addEventListener("change", function () {
      boxes.forEach(function (b) { b.checked = allBox.checked; });
      update();
    });
  }
  update();
  btn.addEventListener("click", function (e) {
    e.preventDefault();
    var ids = Array.from(document.querySelectorAll('input[name="requests"]:checked'))
      .map(function (b) { return b.value; });
    var url = btn.getAttribute("data-url") + "?" + ids.map(function (id) {
      return "requests=" + encodeURIComponent(id);
    }).join("&");
    htmx.ajax("get", url, { target: "#app-modal .modal-content" });
  });
  document.body.addEventListener("htmx:afterSwap", function (e) {
    var trigger = e.detail.xhr && e.detail.xhr.getResponseHeader("HX-Trigger");
    if (!trigger) return;
    try {
      var data = JSON.parse(trigger);
      if (data.refreshQueue) {
        location.reload();
      }
    } catch {}
  });
});
