/**
 * Bulk award loot preview functionality.
 * Handles showing container item previews when an item is selected in the bulk award form.
 * Uses delegated event listener so cloned/copied rows also work.
 */
(function () {
    'use strict';

    function handleItemInput(input) {
        var hiddenField = document.getElementById(input.id.replace('-item', '-item_id'));
        var selectedOption = document.querySelector('#item-catalogue option[value="' + input.value + '"]');
        if (selectedOption) {
            hiddenField.value = selectedOption.value;
            showLootPreview(input, selectedOption.value);
        } else {
            hiddenField.value = '';
            showLootPreview(input, null);
        }
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

    // Delegated listener for item autocomplete inputs (works for dynamically added rows)
    document.addEventListener('input', function (e) {
        var input = e.target.closest('input[list="item-catalogue"]');
        if (input) {
            handleItemInput(input);
        }
    });
})();