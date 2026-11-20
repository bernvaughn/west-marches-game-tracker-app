/**
 * Loot row tools for the bulk award form.
 * - "Add item" appends an item row to one character (no limit in the UI).
 * - "Copy this loot to all picked characters" copies coins and item rows
 *   from one character to every other ticked character.
 * Without JavaScript the buttons stay hidden and the form keeps its 3 rows.
 */
(function () {
    'use strict';

    // Matches the formset index in names/ids, e.g. "items_5-2-item".
    var indexRe = /-(\d+)-/;

    function charPk(section) {
        return section.dataset.charPk;
    }

    function totalFormsInput(section) {
        return document.getElementById('id_items_' + charPk(section) + '-TOTAL_FORMS');
    }

    function rowsContainer(section) {
        return section.querySelector('.wm-item-rows');
    }

    function itemRows(section) {
        return rowsContainer(section).querySelectorAll('.wm-item-row');
    }

    function coinsInput(section) {
        return document.getElementById('coins_' + charPk(section));
    }

    function field(row, suffix) {
        return row.querySelector('input[name$="-' + suffix + '"]');
    }

    function clearRow(row) {
        row.querySelectorAll('input').forEach(function (input) {
            input.value = '';
        });
        var slot = row.querySelector('.wm-loot-slot');
        if (slot) {
            slot.replaceChildren();
            slot.hidden = true;
        }
    }

    function addRow(section) {
        var rows = itemRows(section);
        var total = totalFormsInput(section);
        if (!rows.length || !total) return null;
        // The next index is TOTAL_FORMS: the server reads rows 0..TOTAL_FORMS-1.
        var newIndex = parseInt(total.value, 10);
        if (isNaN(newIndex) || newIndex < rows.length) newIndex = rows.length;
        var clone = rows[rows.length - 1].cloneNode(true);
        clone.querySelectorAll('[name], [id], [for]').forEach(function (el) {
            ['name', 'id', 'for'].forEach(function (attr) {
                var val = el.getAttribute(attr);
                if (val) el.setAttribute(attr, val.replace(indexRe, '-' + newIndex + '-'));
            });
        });
        clearRow(clone);
        rowsContainer(section).appendChild(clone);
        total.value = newIndex + 1;
        return clone;
    }

    function readRows(section) {
        var result = [];
        itemRows(section).forEach(function (row) {
            var item = field(row, 'item');
            var data = {
                item: item ? item.value : '',
                itemId: (field(row, 'item_id') || {}).value || '',
                quantity: (field(row, 'quantity') || {}).value || '',
                valueOverride: (field(row, 'value_override') || {}).value || '',
            };
            if (data.item.trim() || data.itemId) result.push(data);
        });
        return result;
    }

    function writeRow(row, data) {
        var item = field(row, 'item');
        var itemId = field(row, 'item_id');
        var qty = field(row, 'quantity');
        var override = field(row, 'value_override');
        if (item) item.value = data.item;
        if (itemId) itemId.value = data.itemId;
        if (qty) qty.value = data.quantity;
        if (override) override.value = data.valueOverride;
        // Let bulk_award.js refresh the hidden item_id and the loot preview.
        if (item) item.dispatchEvent(new Event('input', { bubbles: true }));
    }

    function isTicked(section) {
        var box = document.getElementById('award-' + charPk(section));
        return !!(box && box.checked);
    }

    function copyLoot(source) {
        var coins = coinsInput(source);
        var coinsValue = coins ? coins.value : '';
        var rows = readRows(source);
        document.querySelectorAll('.wm-char-section').forEach(function (target) {
            if (target === source || !isTicked(target)) return;
            var targetCoins = coinsInput(target);
            if (targetCoins) targetCoins.value = coinsValue;
            while (itemRows(target).length < rows.length) {
                if (!addRow(target)) break;
            }
            var targetRows = itemRows(target);
            for (var i = 0; i < targetRows.length; i++) {
                if (i < rows.length) writeRow(targetRows[i], rows[i]);
                else clearRow(targetRows[i]);
            }
        });
    }

    function init() {
        document.querySelectorAll('[data-wm-add-item], [data-wm-copy-loot]').forEach(function (btn) {
            btn.hidden = false;
        });
        document.addEventListener('click', function (e) {
            var addBtn = e.target.closest('[data-wm-add-item]');
            var copyBtn = e.target.closest('[data-wm-copy-loot]');
            var section = (addBtn || copyBtn) && (addBtn || copyBtn).closest('.wm-char-section');
            if (!section) return;
            if (addBtn) {
                var row = addRow(section);
                var input = row && field(row, 'item');
                if (input) input.focus();
            } else {
                copyLoot(section);
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
