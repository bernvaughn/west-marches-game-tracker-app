/* Quick template buttons for the "Message the admins" form.
   Works for the full page and for the form swapped into the shared htmx modal.
   Clicking a button fills the body textarea with the template text,
   replacing {character} with the selected character's name, focuses it,
   and selects the first bracketed placeholder. The "Other" button clears the textarea.
   The text stays editable. */
(function () {
  var TEMPLATE_ATTR = "data-template";
  var TEXT_ATTR = "data-template-text";
  var BUTTONS_CONTAINER = "#template-buttons";
  var PLACEHOLDER_RE = /\[[^\]]*\]/;

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

  function selectFirstPlaceholder(textarea) {
    var text = textarea.value;
    var match = text.match(PLACEHOLDER_RE);
    if (match) {
      textarea.setSelectionRange(match.index, match.index + match[0].length);
    } else {
      var len = text.length;
      textarea.setSelectionRange(len, len);
    }
  }

  function clearInvalid(textarea) {
    textarea.classList.remove("is-invalid");
    textarea.removeAttribute("aria-invalid");
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
      selectFirstPlaceholder(textarea);
      clearInvalid(textarea);
      textarea.dispatchEvent(new Event("input", { bubbles: true }));
      event.preventDefault();
    },
    { capture: true }
  );
})();
