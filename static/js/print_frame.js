/* Print via hidden iframe.
   Handles forms with data-print-frame: POST the form, load the returned HTML
   into a hidden sandboxed srcdoc iframe, and call print() on that frame.
   The print view never shows on screen, and the page stays scrollable. */

(function () {
  'use strict';

  var BLOCKED_NOTE =
    'Your browser blocked the print dialog. Use the browser menu or press Ctrl+P (Cmd+P on Mac).';
  var FETCH_NOTE =
    'Could not prepare the print. Try again, or use the browser menu or press Ctrl+P (Cmd+P on Mac).';
  var FRAME_ATTR = 'data-print-frame-target';

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
    var alert = document.createElement('div');
    alert.className = 'alert alert-warning mt-2 mb-0';
    alert.setAttribute('role', 'alert');
    alert.textContent = message;
    slot.replaceChildren(alert);
  }

  function clearNote(form) {
    var slot = form.querySelector('[data-print-note]');
    if (slot) slot.replaceChildren();
  }

  function hideModal() {
    var modalEl = document.getElementById('app-modal');
    if (!modalEl || !window.bootstrap) return;
    var modal = window.bootstrap.Modal.getInstance(modalEl);
    if (modal) modal.hide();
  }

  function removeFrame(iframe) {
    if (iframe && iframe.parentNode) iframe.parentNode.removeChild(iframe);
  }

  function removeStaleFrames() {
    document.querySelectorAll('iframe[' + FRAME_ATTR + ']').forEach(removeFrame);
  }

  // The frame is sandboxed without allow-scripts, so its scripts cannot run.
  // Strip them so the browser does not log a blocked-script error for each.
  function stripScripts(html) {
    var doc = new DOMParser().parseFromString(html, 'text/html');
    doc.querySelectorAll('script').forEach(function (s) {
      s.remove();
    });
    return '<!DOCTYPE html>\n' + doc.documentElement.outerHTML;
  }

  function printInFrame(form, html) {
    var iframe = document.createElement('iframe');
    iframe.setAttribute(FRAME_ATTR, '');
    iframe.setAttribute('sandbox', 'allow-same-origin allow-modals');
    iframe.setAttribute('aria-hidden', 'true');
    iframe.setAttribute('tabindex', '-1');
    iframe.style.cssText =
      'position:fixed;top:-10000px;left:-10000px;width:1px;height:1px;border:0;';

    iframe.addEventListener('load', function () {
      var win = iframe.contentWindow;
      try {
        if (!win) throw new Error('No contentWindow');
        // The srcdoc document replaces the initial window, so listen here.
        // afterprint fires when the dialog closes (print or cancel).
        win.addEventListener('afterprint', function () {
          removeFrame(iframe);
        });
        win.focus();
        win.print();
      } catch (e) {
        showNote(form, BLOCKED_NOTE);
        removeFrame(iframe);
        return;
      }
      // Some browsers do not block in print(). Keep the frame until
      // afterprint, or until the next submit removes it.
      hideModal();
    });

    iframe.srcdoc = stripScripts(html);
    document.body.appendChild(iframe);
  }

  function handlePrintFormSubmit(event) {
    var form = event.target.closest('form[data-print-frame]');
    if (!form) return;

    event.preventDefault();
    removeStaleFrames();
    clearNote(form);

    var submitBtn = form.querySelector('button[type="submit"]');
    if (submitBtn) submitBtn.disabled = true;

    fetch(form.action, {
      method: 'POST',
      body: new FormData(form),
      credentials: 'same-origin',
      headers: { 'X-CSRFToken': getCsrfToken() },
    })
      .then(function (response) {
        if (!response.ok) throw new Error('Server returned ' + response.status);
        return response.text();
      })
      .then(function (html) {
        printInFrame(form, html);
      })
      .catch(function () {
        showNote(form, FETCH_NOTE);
      })
      .finally(function () {
        if (submitBtn) submitBtn.disabled = false;
      });
  }

  // Delegated listener: the modal form is loaded by htmx after page load.
  document.addEventListener('submit', handlePrintFormSubmit);
})();
