// Show each "Other" freetext input and flag only when "Other" is picked in its dropdown.
document.addEventListener("DOMContentLoaded", () => {
  const pairs = [
    ["id_char_class", "id_char_class_freetext"],
    ["id_species", "id_species_freetext"],
    ["id_background", "id_background_freetext"],
    ["id_pronouns", "id_pronouns_freetext"],
  ];
  for (const [selectId, freetextId] of pairs) {
    const select = document.getElementById(selectId);
    const freetext = document.getElementById(freetextId);
    if (!select || !freetext) {
      continue;
    }
    const wrapper = freetext.closest(".wm-field");
    const flag = document.querySelector(`[data-other-for="${selectId}"]`);
    const update = () => {
      const show = select.value === "Other";
      if (wrapper) {
        wrapper.style.display = show ? "" : "none";
      }
      if (flag) {
        flag.style.display = show ? "" : "none";
      }
    };
    select.addEventListener("change", update);
    update();
  }
});