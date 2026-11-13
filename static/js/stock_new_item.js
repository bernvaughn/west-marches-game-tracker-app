// Adds an item created in the modal to the stock form's item picker and selects it.
document.body.addEventListener("itemCreated", (evt) => {
  const select = document.querySelector('select[name="item"]');
  if (!select) return;
  const { id, name } = evt.detail;
  select.add(new Option(name, id, true, true));
  select.value = String(id);
  select.dispatchEvent(new Event("change", { bubbles: true }));
});
