/**
 * Loot row manipulation for the bulk award form.
 * Adds "Add item" and "Copy this loot to all picked characters" functionality.
 */
(function () {
    'use strict';

    // Regex to match -<number>- in form field names/ids
    var indexRe = /-(\d+)-/;

    function updateTotalForms(container, delta) {
        var totalFormsInput = container.querySelector('input[name$="-TOTAL_FORMS"]');
        if (totalFormsInput) {
            var current = parseInt(totalFormsInput.value, 10) || 0;
            totalFormsInput.value = current + delta;
        }
    }

    function cloneRow(row, newIndex) {
        var clone = row.cloneNode(true);
        // Update all name, id, and for attributes
        clone.querySelectorAll('[name], [id], [for]').forEach(function (el) {
            ['name', 'id', 'for'].forEach(function (attr) {
                var val = el.getAttribute(attr);
                if (val) {
                    el.setAttribute(attr, val.replace(indexRe, '-' + newIndex + '-'));
                }
            });
        });
        // Clear input values (except hidden item_id which we'll set to empty)
        clone.querySelectorAll('input:not([type="hidden"])').forEach(function (input) {
            input.value = '';
        });
        clone.querySelectorAll('input[type="hidden"]').forEach(function (input) {
            input.value = '';
        });
        // Hide and clear loot preview slot
        var lootSlot = clone.querySelector('.wm-loot-slot');
        if (lootSlot) {
            lootSlot.replaceChildren();
            lootSlot.hidden = true;
        }
        return clone;
    }

    function getItemRows(container) {
        return container.querySelectorAll('.wm-item-row');
    }

    function getNonEmptyRows(container) {
        var rows = getItemRows(container);
        var result = [];
        rows.forEach(function (row) {
            var itemInput = row.querySelector('input[list="item-catalogue"]');
            var qtyInput = row.querySelector('input[name$="-quantity"]');
            var itemIdInput = row.querySelector('input[name$="-item_id"]');
            if (itemIdInput && itemIdInput.value) {
                result.push({
                    row: row,
                    itemId: itemIdInput.value,
                    itemText: itemInput ? itemInput.value : '',
                    quantity: qtyInput ? qtyInput.value : '',
                });
            }
        });
        return result;
    }

    function addRow(container) {
        var rows = getItemRows(container);
        var lastRow = rows[rows.length - 1];
        var lastIndex = 0;
        var match = lastRow.querySelector('[name]').getAttribute('name').match(indexRe);
        if (match) {
            lastIndex = parseInt(match[1], 10);
        }
        var newIndex = lastIndex + 1;
        var newRow = cloneRow(lastRow, newIndex);
        container.appendChild(newRow);
        updateTotalForms(container, 1);
        // Focus the new item input
        var itemInput = newRow.querySelector('input[list="item-catalogue"]');
        if (itemInput) {
            itemInput.focus();
        }
    }

    function copyLoot(sourceContainer, allContainers) {
        var sourceRows = getNonEmptyRows(sourceContainer);
        if (sourceRows.length === 0) {
            return; // Nothing to copy
        }
        var sourceCoins = document.querySelector('input[name^="coins_"][data-char-pk="' + sourceContainer.dataset.charPk + '"]');
        var sourceCoinsValue = sourceCoins ? sourceCoins.value : '';

        allContainers.forEach(function (targetContainer) {
            if (targetContainer === sourceContainer) return;
            // Only copy to checked characters
            var checkbox = document.querySelector('input[name="characters"][value="' + targetContainer.dataset.charPk + '"]');
            if (!checkbox || !checkbox.checked) return;

            // Copy coins
            var targetCoins = document.querySelector('input[name^="coins_"][data-char-pk="' + targetContainer.dataset.charPk + '"]');
            if (targetCoins) {
                targetCoins.value = sourceCoinsValue;
            }

            // Ensure target has enough rows
            var targetRows = getItemRows(targetContainer);
            while (targetRows.length < sourceRows.length) {
                addRow(targetContainer);
                targetRows = getItemRows(targetContainer);
            }

            // Copy item data
            sourceRows.forEach(function (src, i) {
                var targetRow = targetRows[i];
                var targetItemInput = targetRow.querySelector('input[list="item-catalogue"]');
                var targetItemIdInput = targetRow.querySelector('input[name$="-item_id"]');
                var targetQtyInput = targetRow.querySelector('input[name$="-quantity"]');
                var targetValueInput = targetRow.querySelector('input[name$="-value_override"]');

                if (targetItemInput) targetItemInput.value = src.itemText;
                if (targetItemIdInput) targetItemIdInput.value = src.itemId;
                if (targetQtyInput) targetQtyInput.value = src.quantity;
                // Note: value_override is not copied from source (source doesn't have it in getNonEmptyRows)
                // The user can edit it after copy.

                // Dispatch input event so the hidden item_id and preview update
                if (targetItemInput) {
                    targetItemInput.dispatchEvent(new Event('input', { bubbles: true }));
                }
            });

            // Blank out any extra rows beyond what was copied
            for (var i = sourceRows.length; i < targetRows.length; i++) {
                var extraRow = targetRows[i];
                var extraItemInput = extraRow.querySelector('input[list="item-catalogue"]');
                var extraItemIdInput = extraRow.querySelector('input[name$="-item_id"]');
                var extraQtyInput = extraRow.querySelector('input[name$="-quantity"]');
                var extraValueInput = extraRow.querySelector('input[name$="-value_override"]');
                if (extraItemInput) extraItemInput.value = '';
                if (extraItemIdInput) extraItemIdInput.value = '';
                if (extraQtyInput) extraQtyInput.value = '';
                if (extraValueInput) extraValueInput.value = '';
                var extraLootSlot = extraRow.querySelector('.wm-loot-slot');
                if (extraLootSlot) {
                    extraLootSlot.replaceChildren();
                    extraLootSlot.hidden = true;
                }
            }
        });
    }

    function init() {
        // Reveal the buttons (hidden by default for no-JS)
        document.querySelectorAll('[data-wm-add-item], [data-wm-copy-loot]').forEach(function (btn) {
            btn.hidden = false;
        });

        // Delegated click for "Add item"
        document.addEventListener('click', function (e) {
            var addBtn = e.target.closest('[data-wm-add-item]');
            if (addBtn) {
                var section = addBtn.closest('.wm-char-section');
                if (section) {
                    var container = section.querySelector('.wm-item-rows');
                    if (container) {
                        addRow(container);
                    }
                }
            }
        });

        // Delegated click for "Copy this loot to all picked characters"
        document.addEventListener('click', function (e) {
            var copyBtn = e.target.closest('[data-wm-copy-loot]');
            if (copyBtn) {
                var sourceSection = copyBtn.closest('.wm-char-section');
                if (sourceSection) {
                    var sourceContainer = sourceSection.querySelector('.wm-item-rows');
                    var allSections = document.querySelectorAll('.wm-char-section');
                    var allContainers = Array.from(allSections).map(function (s) {
                        return s.querySelector('.wm-item-rows');
                    }).filter(Boolean);
                    copyLoot(sourceContainer, allContainers);
                }
            }
        });
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();