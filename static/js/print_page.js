/* Print buttons.
   Clicking any [data-wm-print] button opens the browser print dialog.
   Loaded with defer from base.html; CSP script-src 'self' compatible.
 */
(function () {
  'use strict';
  document.body.addEventListener('click', function (evt) {
    var btn = evt.target.closest('[data-wm-print]');
    if (btn) window.print();
  });
})();
