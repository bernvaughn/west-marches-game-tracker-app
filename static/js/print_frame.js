/* Print via hidden iframe.
   Handles forms with data-print-frame by fetching the HTML and printing it
   from a sandboxed srcdoc iframe. This avoids CSP issues with hx-on and
   the unscrollable body caused by modal overflow locks. */

(function () {
  'use strict';

  function getCsrfToken() {
    try {
      var headers = JSON.parse(document.body.getAttribute('hx-headers') || '{}');
      return headers['X-CSRFToken'] || '';
    } catch (e) {
      return '';
    }
  }

  function showNote(form, message) {
    var slot = form.querySelector('[data-print-note]');
    if (!slot) return;
    slot.innerHTML = '<div class="alert alert-warning" role="alert">' + message + '</div>';
  }

  function clearNote(form) {
    var slot = form.querySelector('[data-print-note]');
    if (slot) slot.innerHTML = '';
  }

  function getModalInstance() {
    var modalEl = document.getElementById('app-modal');
    if (!modalEl) return null;
    return bootstrap.Modal.getInstance(modalEl);
  }

  function handlePrintFormSubmit(event) {
    var form = event.target.closest('form[data-print-frame]');
    if (!form) return;

    event.preventDefault();

    var submitBtn = form.querySelector('button[type="submit"]');
    if (submitBtn) submitBtn.disabled = true;
    clearNote(form);

    var action = form.action || form.dataset.printFrameUrl;
    if (!action) {
      showNote(form, 'Print action URL is missing.');
      if (submitBtn) submitBtn.disabled = false;
      return;
    }

    var formData = new FormData(form);
    var csrfToken = getCsrfToken();

    fetch(action, {
      method: 'POST',
      body: formData,
      credentials: 'same-origin',
      headers: {
        'X-CSRFToken': csrfToken,
      },
    })
      .then(function (response) {
        if (!response.ok) {
          throw new Error('Server returned ' + response.status);
        }
        return response.text();
      })
      .then(function (html) {
        var iframe = document.createElement('iframe');
        iframe.setAttribute('sandbox', 'allow-same-origin allow-modals');
        iframe.setAttribute('aria-hidden', 'true');
        iframe.setAttribute('tabindex', '-1');
        iframe.srcdoc = html;
        iframe.style.cssText = 'position:fixed;top:-10000px;left:-10000px;width:1px;height:1px;border:none;';
        document.body.appendChild(iframe);

        var printed = false;
        var cleanupDone = false;

        function cleanup() {
          if (cleanupDone) return;
          cleanupDone = true;
          if (iframe.parentNode) iframe.parentNode.removeChild(iframe);
        }

        iframe.addEventListener('load', function () {
          try {
            var win = iframe.contentWindow;
            if (!win) throw new Error('No contentWindow');
            win.focus();
            win.print();
            printed = true;
          } catch (e) {
            showNote(form, 'Your browser blocked the print dialog. Use the browser menu or press Ctrl+P (Cmd+P on Mac).');
            if (submitBtn) submitBtn.disabled = false;
            cleanup();
          }
        });

        // afterprint fires when the print dialog closes (print or cancel)
        iframe.contentWindow.addEventListener('afterprint', function () {
          var modal = getModalInstance();
          if (modal) modal.hide();
          cleanup();
        });

        // Fallback: if afterprint doesn't fire within 5 seconds, clean up anyway
        setTimeout(function () {
          if (!cleanupDone) {
            var modal = getModalInstance();
            if (modal) modal.hide();
            cleanup();
          }
        }, 5000);
      })
      .catch(function (err) {
        showNote(form, 'Your browser blocked the print dialog. Use the browser menu or press Ctrl+P (Cmd+P on Mac).');
      })
      .finally(function () {
        if (submitBtn) submitBtn.disabled = false;
      });
  }

  // Delegated listener on document for htmx-loaded modal content
  document.addEventListener('submit', handlePrintFormSubmit);
})();