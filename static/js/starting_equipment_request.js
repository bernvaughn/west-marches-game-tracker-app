/**
 * Starting equipment request modal functionality.
 * Handles quantity limits and loot preview for container items.
 */
(function () {
    'use strict';

    function initStartingEquipmentRequestModal() {
        const itemSelect = document.getElementById('id_item');
        const quantityInput = document.getElementById('id_quantity');
        const helpText = document.getElementById('quantity-help');

        if (!itemSelect || !quantityInput) return;

        function updateQuantityMax() {
            const selectedOption = itemSelect.options[itemSelect.selectedIndex];
            const max = selectedOption ? parseInt(selectedOption.dataset.max, 10) : 1;
            // The blank option ("Select a magic item...") has no data-max.
            // Never write "NaN" to the max attribute or the help text: clear
            // the limit instead until a real item is chosen.
            if (!Number.isFinite(max) || max < 1) {
                quantityInput.removeAttribute("max");
                helpText.textContent = "";
                return;
            }
            quantityInput.max = max;
            if (quantityInput.valueAsNumber > max) {
                quantityInput.value = max;
            }
            helpText.textContent = `Maximum per character: ${max}`;
        }

        const previewContainer = document.getElementById('loot-preview-container');
        const previewContent = document.getElementById('loot-preview-content');

        function updateLootPreview() {
            if (!previewContainer || !previewContent) return;
            const tpl = itemSelect.value ? document.getElementById('loot-preview-' + itemSelect.value) : null;
            if (tpl) {
                previewContent.replaceChildren(tpl.content.cloneNode(true));
                previewContainer.hidden = false;
            } else {
                previewContent.replaceChildren();
                previewContainer.hidden = true;
            }
        }

        itemSelect.addEventListener('change', updateQuantityMax);
        itemSelect.addEventListener('change', updateLootPreview);
        // Initialize on load
        updateQuantityMax();
        updateLootPreview();
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initStartingEquipmentRequestModal);
    } else {
        initStartingEquipmentRequestModal();
    }
})();