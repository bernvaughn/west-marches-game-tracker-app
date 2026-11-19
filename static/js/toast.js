/**
 * Toast notifications triggered via HTMX HX-Trigger header or Django messages.
 * Usage: response["HX-Trigger"] = json.dumps({"toast": {"message": "Saved", "type": "success"}})
 * Django messages with tags 'toast-success', 'toast-warning', 'toast-danger', 'toast-info' are shown as toasts.
 *
 * Global API: window.wmShowToast(message, type)
 */
(function () {
  const container = document.getElementById("wm-toast-container");
  if (!container) return;

  function showToast(message, type = "info") {
    const toast = document.createElement("div");
    toast.className = `wm-toast wm-toast-${type}`;
    toast.setAttribute("role", "alert");
    toast.setAttribute("aria-live", "assertive");

    const icons = {
      success: "check-circle-fill",
      warning: "exclamation-triangle-fill",
      danger: "x-circle-fill",
      info: "info-circle-fill",
    };
    const icon = icons[type] || icons.info;

    // Static parts (icon, close button) are safe HTML. The user-controlled
    // message is assigned with textContent so it is never parsed as HTML.
    toast.innerHTML = `
      <svg class="wm-toast-icon" aria-hidden="true"><use href="#${icon}"></use></svg>
      <span class="wm-toast-message"></span>
      <button type="button" class="wm-toast-close" aria-label="Dismiss">&times;</button>
    `;
    toast.querySelector(".wm-toast-message").textContent = message;

    container.appendChild(toast);

    toast.querySelector(".wm-toast-close").addEventListener("click", () => toast.remove());

    setTimeout(() => {
      toast.classList.add("wm-toast-hide");
      setTimeout(() => toast.remove(), 200);
    }, 5000);
  }

  function showToastsFromMessages() {
    const messages = document.querySelectorAll(".wm-message-toast");
    messages.forEach((el) => {
      const message = el.dataset.message;
      const type = el.dataset.type || "info";
      showToast(message, type);
      el.remove();
    });
  }

  // HTMX-triggered toasts
  document.body.addEventListener("htmx:afterSwap", (e) => {
    const trigger = e.detail.xhr?.getResponseHeader("HX-Trigger");
    if (!trigger) return;
    try {
      const data = JSON.parse(trigger);
      if (data.toast) {
        showToast(data.toast.message, data.toast.type);
      }
    } catch {
      // Ignore invalid JSON
    }
  });

  // Django messages rendered as toasts
  document.addEventListener("DOMContentLoaded", showToastsFromMessages);
  document.body.addEventListener("htmx:afterSwap", showToastsFromMessages);

  // Expose global API
  window.wmShowToast = showToast;
})();