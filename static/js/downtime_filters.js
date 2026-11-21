/*
 * Downtime filter chips: keep the checkboxes in sync with the URL after an
 * htmx history restore (Back / Forward).
 *
 * htmx snapshots the DOM for history, but a checkbox's `checked` state is a DOM
 * property, not an attribute, so the snapshot loses it. After a restore, read
 * the filters from location.search and set each checkbox again.
 */
(function () {
  "use strict";

  function syncFilters() {
    var form = document.getElementById("downtime-filters");
    if (!form) return;
    var params = new URLSearchParams(window.location.search);
    form.querySelectorAll('input[type="checkbox"]').forEach(function (box) {
      box.checked = params.getAll(box.name).indexOf(box.value) !== -1;
    });
  }

  document.addEventListener("htmx:historyRestore", syncFilters);
})();
