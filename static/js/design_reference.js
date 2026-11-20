/* Design system reference page behaviour.
   - [data-wm-test-toast] buttons trigger a demo toast via window.wmShowToast
     (empty value = success).
   - form[action="#"] samples never submit (replaces the inline onsubmit).
   Loaded with defer; CSP script-src 'self' compatible.
 */
(function () {
  'use strict';

  var messages = {
    success: 'Action completed successfully',
    warning: 'Request declined',
    danger: 'Operation cancelled',
    info: 'Choice confirmed. Choose what to do next.'
  };

  document.body.addEventListener('click', function (evt) {
    var btn = evt.target.closest('[data-wm-test-toast]');
    if (!btn || !window.wmShowToast) return;
    var type = btn.getAttribute('data-wm-test-toast') || 'success';
    window.wmShowToast(messages[type] || messages.success, type);
  });

  document.body.addEventListener('submit', function (evt) {
    if (evt.target.closest('form[action="#"]')) evt.preventDefault();
  });
})();
