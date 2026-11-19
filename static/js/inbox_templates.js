/* Quick template buttons for the "Message the admins" form.
   Works for the full page and for the form swapped into the shared htmx modal.
   Clicking a button fills the body textarea with the template text,
   replacing {character} with the selected character's name, and focuses it.
   The "Other" button clears the textarea. The text stays editable. */
(function () {
  var TEMPLATE_ATTR = "data-template";
  var TEXT_ATTR = "data-template-text";
  var BUTTONS_CONTAINER = "#template-buttons";

  function findTextarea() {
    return document.querySelector("textarea[name='body'], #id_body");
  }

  function characterName() {
    var container = document.querySelector(BUTTONS_CONTAINER);
    if (container) {
      return container.getAttribute("data-character-name") || "";
    }
    return "";
  }

  document.addEventListener(
    "click",
    function (event) {
      var button = event.target.closest("[" + TEMPLATE_ATTR + "]");
      if (!button) {
        return;
      }
      var textarea = findTextarea();
      if (!textarea) {
        return;
      }
      var text = button.getAttribute(TEXT_ATTR) || "";
      textarea.value = text.replace("{character}", characterName());
      textarea.focus();
      event.preventDefault();
    },
    { capture: true }
  );
})();
