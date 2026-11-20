/* Print sheet: open the browser print dialog and record the print.
   POSTs to the character detail endpoint to update last_printed_at without
   replacing the page. Inline/event-attribute handlers are avoided because the
   site's CSP (script-src 'self', no unsafe-eval) blocks them.
   The CSRF cookie is HttpOnly, so the token comes from the DOM. */
(function () {
  'use strict';

  function getCsrfToken(button) {
    if (button.dataset.csrfToken) {
      return button.dataset.csrfToken;
    }
    try {
      var headers = JSON.parse(document.body.getAttribute('hx-headers') || '{}');
      return headers['X-CSRFToken'] || '';
    } catch (e) {
      return '';
    }
  }

  function recordPrint(button) {
    var url = button.dataset.printSheetUrl;
    if (!url || !window.fetch) {
      return Promise.resolve();
    }
    return fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'X-CSRFToken': getCsrfToken(button),
        'Accept': 'application/json',
      },
    }).catch(function () {
      /* Recording the print is best effort; printing must still happen. */
    });
  }

  function initPrintSheet() {
    document.querySelectorAll('[data-print-sheet]').forEach(function (button) {
      if (button.dataset.printSheetBound) {
        return;
      }
      button.dataset.printSheetBound = '1';
      button.addEventListener('click', function () {
        recordPrint(button).then(function () {
          window.print();
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
