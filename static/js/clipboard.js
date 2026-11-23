/**
 * Clipboard copy button handler.
 * Buttons with data-wm-copy-target="#input-id" will copy the target input's value.
 */
(function () {
  function initClipboardButtons() {
    document.querySelectorAll("[data-wm-copy-target]").forEach(function (btn) {
      var targetSelector = btn.getAttribute("data-wm-copy-target");
      var target = document.querySelector(targetSelector);
      if (!target) return;

      btn.addEventListener("click", function () {
        var text = target.value;
        if (!text) return;

        navigator.clipboard.writeText(text).then(function () {
          var originalText = btn.textContent;
          btn.textContent = "Copied!";
          btn.disabled = true;
          setTimeout(function () {
            btn.textContent = originalText;
            btn.disabled = false;
          }, 2000);
        }).catch(function () {
          // Fallback for browsers without clipboard API
          target.select();
          document.execCommand("copy");
          var originalText = btn.textContent;
          btn.textContent = "Copied!";
          btn.disabled = true;
          setTimeout(function () {
            btn.textContent = originalText;
            btn.disabled = false;
          }, 2000);
        });
      });
    });
  }

  document.addEventListener("DOMContentLoaded", initClipboardButtons);
  document.body.addEventListener("htmx:afterSwap", initClipboardButtons);
})();