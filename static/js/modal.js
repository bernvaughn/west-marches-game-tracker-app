/* Shared modal (U33). A link with data-app-modal and hx-get loads into
   #app-modal .modal-content. The server closes it with HX-Trigger: appModalClose. */
/* htmx cancels the click on an HTML <a>, but not on an SVG <a> (hex map tiles).
   Cancel it here so the browser does not navigate. Do not use hx-on: the CSP blocks it. */
document.addEventListener("click", function (evt) {
  var link = evt.target instanceof Element && evt.target.closest("a[data-app-modal]");
  if (link && link.hasAttribute("hx-get")) evt.preventDefault();
});
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
