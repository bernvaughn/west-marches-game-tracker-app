// Player Items Merge Form - HTMX modal interactions

(function () {
  function initMergeForm() {
    const form = document.getElementById('merge-form');
    if (!form) return;

    const modeRadios = form.querySelectorAll('input[name="mode"]');
    const mergeFields = document.getElementById('merge-mode-fields');
    const matchFields = document.getElementById('match-mode-fields');
    const unitNameField = document.getElementById('merge-unit-name-field');
    const isStackedCheckbox = form.querySelector('input[name="is_stacked"]');
    const nameInput = form.querySelector('input[name="name"]');

    function updateVisibility() {
      const mode = form.querySelector('input[name="mode"]:checked');
      if (!mode) return;
      if (mode.value === 'merge') {
        mergeFields.style.display = '';
        matchFields.style.display = 'none';
      } else {
        mergeFields.style.display = 'none';
        matchFields.style.display = '';
      }
    }

    function updateUnitNameVisibility() {
      if (isStackedCheckbox && isStackedCheckbox.checked) {
        unitNameField.style.display = '';
      } else {
        unitNameField.style.display = 'none';
      }
    }

    modeRadios.forEach((radio) => radio.addEventListener('change', updateVisibility));
    if (isStackedCheckbox) {
      isStackedCheckbox.addEventListener('change', updateUnitNameVisibility);
    }

    // Initial state
    updateVisibility();
    updateUnitNameVisibility();

    // Fetch suggestions when typing in name field
    let suggestionTimeout;
    const suggestUrl = form.dataset.suggestUrl || '';
    if (nameInput && suggestUrl) {
      nameInput.addEventListener('input', function () {
        clearTimeout(suggestionTimeout);
        suggestionTimeout = setTimeout(() => {
          const name = nameInput.value.trim();
          if (name.length >= 2) {
            fetch(`${suggestUrl}?name=${encodeURIComponent(name)}`, {
              headers: { 'HX-Request': 'true' },
            })
              .then((r) => r.text())
              .then((html) => {
                let container = document.getElementById('merge-suggestions');
                if (!container) {
                  container = document.createElement('div');
                  container.id = 'merge-suggestions';
                  container.className = 'mt-2';
                  nameInput.parentNode.appendChild(container);
                }
                container.innerHTML = html;
              });
          } else {
            const container = document.getElementById('merge-suggestions');
            if (container) container.remove();
          }
        }, 200);
      });
    }
  }

  // Initialize when the modal content is loaded
  document.addEventListener('DOMContentLoaded', initMergeForm);
  // Also handle HTMX swaps
  document.body.addEventListener('htmx:afterSwap', function (evt) {
    if (evt.detail.target.id === 'app-modal') {
      initMergeForm();
    }
  });
})();