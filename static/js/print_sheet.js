/* Print sheet: record the print, then open the browser print dialog.
   POSTs to the character detail endpoint to update last_printed_at without
   replacing the page. Inline/event-attribute handlers are avoided because the
   site's CSP (script-src 'self', no unsafe-eval) blocks them. */
(function () {
  'use strict';

  function getCsrfToken() {
    var match = document.cookie.match(/(?:^|; )\s*csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
  }

  function initPrintSheet() {
    document.querySelectorAll('[data-print-sheet]').forEach(function (button) {
      button.addEventListener('click', function () {
        var url = button.dataset.printSheetUrl;
        if (!url) {
          return;
        }
        fetch(url, {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'X-CSRFToken': getCsrfToken(),
            'Accept': 'application/json',
          },
        }).then(function (response) {
          if (response.ok) {
            window.print();
          }
        });
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPrintSheet);
  } else {
    initPrintSheet();
  }
})();
