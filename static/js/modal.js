/* Shared modal (U33). A link with data-app-modal and hx-get loads into
   #app-modal .modal-content. The server closes it with HX-Trigger: appModalClose. */
document.addEventListener("DOMContentLoaded", function () {
  var modalEl = document.getElementById("app-modal");
  if (!modalEl) return;
  var content = modalEl.querySelector(".modal-content");
  document.body.addEventListener("htmx:afterSwap", function (evt) {
    if (evt.detail.target === content) {
      bootstrap.Modal.getOrCreateInstance(modalEl).show();
    }
  });
  document.body.addEventListener("appModalClose", function () {
    var instance = bootstrap.Modal.getInstance(modalEl);
    if (instance) instance.hide();
  });
  modalEl.addEventListener("hidden.bs.modal", function () {
    content.innerHTML = "";
  });
});
