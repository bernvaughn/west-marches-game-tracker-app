// Player Items Review Page - checkbox and merge button handling

(function () {
  function initReviewPage() {
    const form = document.getElementById('review-form');
    if (!form) return;

    const selectAll = document.getElementById('select-all');
    const checkboxes = form.querySelectorAll('.group-checkbox');
    const mergeBtn = document.getElementById('merge-selected-btn');

    function updateMergeButton() {
      const checked = form.querySelectorAll('.group-checkbox:checked').length;
      if (mergeBtn) {
        mergeBtn.disabled = checked < 2;
      }
      if (selectAll) {
        selectAll.checked = checked === checkboxes.length && checkboxes.length > 0;
        selectAll.indeterminate = checked > 0 && checked < checkboxes.length;
      }
    }

    if (selectAll) {
      selectAll.addEventListener('change', function () {
        checkboxes.forEach((cb) => {
          cb.checked = selectAll.checked;
        });
        updateMergeButton();
      });
    }

    checkboxes.forEach((cb) => {
      cb.addEventListener('change', updateMergeButton);
    });

    // Initial state
    updateMergeButton();
  }

  // Initialize when the page loads
  document.addEventListener('DOMContentLoaded', initReviewPage);
})();