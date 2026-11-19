/**
 * Shop favorites handling.
 * The star button uses htmx for server-side toggle.
 * This module provides optional visual feedback during the toggle.
 */
(function () {
  // Add visual feedback during favorite toggle
  document.body.addEventListener("htmx:beforeRequest", (e) => {
    const target = e.detail.elt;
    if (target.closest(".wm-favorite-form")) {
      const btn = target.querySelector(".wm-favorite-btn");
      if (btn) {
        btn.classList.add("wm-favorite-btn--loading");
        btn.disabled = true;
      }
    }
  });

  document.body.addEventListener("htmx:afterSwap", (e) => {
    const target = e.detail.elt;
    if (target.closest(".wm-favorite-form")) {
      const btn = target.querySelector(".wm-favorite-btn");
      if (btn) {
        btn.classList.remove("wm-favorite-btn--loading");
        btn.disabled = false;
      }
    }
  });

  // Handle errors on favorite toggle
  document.body.addEventListener("htmx:responseError", (e) => {
    const target = e.detail.elt;
    if (target.closest(".wm-favorite-form")) {
      const btn = target.querySelector(".wm-favorite-btn");
      if (btn) {
        btn.classList.remove("wm-favorite-btn--loading");
        btn.disabled = false;
      }
      // Error toast is handled by the toast.js via HX-Trigger
    }
  });
})();