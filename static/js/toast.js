/* Toast system (Contract): HTMX hx-trigger="toast" + Alpine.js.
   Server sends HX-Trigger: {"toast": "message"} or {"toast": {"message": "...", "type": "success|warning|danger|info"}}
*/
document.addEventListener("DOMContentLoaded", function () {
  if (!window.Alpine) {
    console.warn("Alpine.js not loaded; toast system disabled");
    return;
  }

  Alpine.data("wmToast", function () {
    return {
      toasts: [],
      init() {
        this.$watch("toasts", (val) => {
          if (val.length > 0) {
            this.$nextTick(() => {
              const el = this.$refs.container;
              if (el) el.scrollTop = el.scrollHeight;
            });
          }
        });
      },
      add(message, type = "info", timeout = 5000) {
        const id = Date.now() + Math.random();
        this.toasts.push({ id, message, type });
        if (timeout > 0) {
          setTimeout(() => this.remove(id), timeout);
        }
      },
      remove(id) {
        const idx = this.toasts.findIndex((t) => t.id === id);
        if (idx > -1) this.toasts.splice(idx, 1);
      },
    };
  });

  // Listen for HTMX toast triggers
  document.body.addEventListener("htmx:afterProcessNode", function (evt) {
    if (!evt.detail.elt || !evt.detail.elt.hasAttribute) return;
    const elt = evt.detail.elt;
    if (elt.hasAttribute("hx-trigger") && elt.getAttribute("hx-trigger").includes("toast")) {
      // This is handled by htmx:afterSwap below when HX-Trigger header is present
    }
  });

  document.body.addEventListener("htmx:afterSwap", function (evt) {
    if (evt.detail.xhr) {
      const trigger = evt.detail.xhr.getResponseHeader("HX-Trigger");
      if (trigger) {
        try {
          const data = JSON.parse(trigger);
          if (data.toast) {
            const toastEl = document.querySelector('[x-data*="wmToast"]');
            if (toastEl && toastEl._x_dataStack) {
              const toastData = toastEl._x_dataStack[0];
              if (typeof data.toast === "string") {
                toastData.add(data.toast, "info");
              } else if (data.toast.message) {
                toastData.add(data.toast.message, data.toast.type || "info", data.toast.timeout);
              }
            }
          }
        } catch (e) {
          // Not JSON, ignore
        }
      }
    }
  });
});