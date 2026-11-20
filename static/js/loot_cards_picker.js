/* Loot cards picker copies switch.
   Toggles "One card per item type" / "One card per item" and stores the
   choice in #id_copies. Loaded with defer; CSP script-src 'self' compatible.
 */
(function () {
  'use strict';

  const typeBtn = document.getElementById('btn-copies-type');
  const itemBtn = document.getElementById('btn-copies-item');
  const copiesInput = document.getElementById('id_copies');

  if (!typeBtn || !itemBtn || !copiesInput) return;

  function setActive(value) {
    copiesInput.value = value;
    if (value === 'item') {
      itemBtn.classList.add('active');
      typeBtn.classList.remove('active');
    } else {
      typeBtn.classList.add('active');
      itemBtn.classList.remove('active');
    }
  }

  typeBtn.addEventListener('click', function () { setActive('type'); });
  itemBtn.addEventListener('click', function () { setActive('item'); });

  // Initialise the active button from the current input value.
  setActive(copiesInput.value || 'type');
})();
