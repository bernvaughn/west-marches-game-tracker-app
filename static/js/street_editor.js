/* Street editor: drag club shops to reorder them on the street. */
(function () {
  var grid = document.getElementById("street-editor-grid");
  var orderInput = document.getElementById("shop-order-input");
  var form = document.getElementById("street-editor-form");
  if (!grid || !orderInput || !form) return;

  var dragged = null;

  grid.addEventListener("dragstart", function (evt) {
    var lot = evt.target.closest("[data-lot='shop']");
    if (!lot) {
      evt.preventDefault();
      return;
    }
    dragged = lot;
    lot.classList.add("wm-dragging");
    evt.dataTransfer.effectAllowed = "move";
    evt.dataTransfer.setData("text/plain", lot.dataset.shopId);
  });

  grid.addEventListener("dragend", function () {
    if (dragged) {
      dragged.classList.remove("wm-dragging");
    }
    dragged = null;
  });

  grid.addEventListener("dragover", function (evt) {
    evt.preventDefault();
    var over = evt.target.closest(".wm-street-lot");
    if (!over || over === dragged || over.dataset.lot !== "shop") {
      return;
    }
    var rect = over.getBoundingClientRect();
    var after = evt.clientY - rect.top > rect.height / 2;
    grid.insertBefore(dragged, after ? over.nextSibling : over);
  });

  form.addEventListener("submit", function () {
    orderInput.value = Array.from(grid.querySelectorAll("[data-lot='shop']"))
      .map(function (lot) {
        return lot.dataset.shopId;
      })
      .join(",");
  });
})();
