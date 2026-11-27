/**
 * Quest-specific JavaScript.
 * The toast handling is done in toast.js via HX-Trigger.
 * This file handles quest board refresh on questCompleted trigger.
 *
 * The turn-in celebration reuses the container loot fanfare
 * (static/js/container_fanfare.js, static/css/container_fanfare.css). That
 * script waits for a shown.bs.modal event on #app-modal before animating, but
 * that event only fires when a modal opens. On the quest board there is no
 * modal, so dispatch the event once here when a celebration panel is on the
 * page. base.html renders #app-modal on every page.
 */
(function () {
  // The quest board refresh is handled declaratively via htmx attributes
  // on the .wm-board element in index.html (hx-trigger="questCompleted from:body").
  document.addEventListener("DOMContentLoaded", function () {
    if (!document.querySelector("[data-fanfare]")) return;
    var modal = document.getElementById("app-modal");
    if (!modal) return;
    modal.dispatchEvent(new Event("shown.bs.modal"));
  });
})();
