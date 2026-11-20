/**
 * Bulk award loot preview functionality.
 * Handles showing container item previews when an item is selected in the bulk award form.
 */
(function () {
    'use strict';

    function initBulkAwardLootPreview() {
        // Handle item autocomplete: update hidden field with selected item ID
        document.querySelectorAll('input[list="item-catalogue"]').forEach(function (input) {
            input.addEventListener('input', function () {
                var hiddenField = document.getElementById(this.id.replace('-item', '-item_id'));
                var selectedOption = document.querySelector('#item-catalogue option[value="' + this.value + '"]');
                if (selectedOption) {
                    hiddenField.value = selectedOption.value;
                    // Show loot preview if this is a container item
                    showLootPreview(this, selectedOption.value);
                } else {
                    hiddenField.value = '';
                    // Hide loot preview
                    showLootPreview(this, null);
                }
            });
        });
    }

    function showLootPreview(inputElement, itemId) {
        // Each item row has its own preview slot.
        var row = inputElement.closest('.wm-item-row');
        var lootSlot = row ? row.querySelector('.wm-loot-slot') : null;
        if (!lootSlot) return;
        var template = itemId ? document.getElementById('loot-preview-' + itemId) : null;
        if (template) {
            lootSlot.replaceChildren(template.content.cloneNode(true));
            lootSlot.hidden = false;
        } else {
            lootSlot.replaceChildren();
            lootSlot.hidden = true;
        }
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initBulkAwardLootPreview);
    } else {
        initBulkAwardLootPreview();
    }
})();