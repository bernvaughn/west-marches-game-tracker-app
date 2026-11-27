/**
 * Item Picker - Progressive Enhancement
 *
 * Initializes on DOMContentLoaded. No inline scripts, CSP-safe.
 * Uses htmx for search requests.
 */

(function () {
  "use strict";

  const DEBOUNCE_MS = 200;
  const MAX_RESULTS = 30;

  function init() {
    document.querySelectorAll("[data-item-picker]").forEach(setupPicker);
  }

  function setupPicker(root) {
    const hiddenInput = root.querySelector('input[type="hidden"]');
    const searchInput = root.querySelector('input[type="search"]');
    const resultsContainer = root.querySelector("[role=listbox]");
    const isMulti = root.dataset.multi === "true";

    if (!hiddenInput || !searchInput || !resultsContainer) {
      return;
    }

    // Remove noscript fallbacks so they don't become real fields after htmx swap.
    // Without this, the <noscript><select> inside each picker row submits as a
    // real field and Django reads the last (empty) value, losing the picked item.
    root.querySelectorAll("noscript").forEach((n) => n.remove());

    let selectedIndex = -1;
    let resultButtons = [];
    let debounceTimer = null;

    // Parse current value(s)
    function getSelectedIds() {
      const val = hiddenInput.value.trim();
      if (!val) return [];
      return val.split(",").filter((v) => v).map((v) => parseInt(v, 10));
    }

    function setSelectedIds(ids) {
      hiddenInput.value = ids.join(",");
      hiddenInput.dispatchEvent(new Event("change", { bubbles: true }));
    }

    function addSelectedId(id) {
      const ids = getSelectedIds();
      if (!ids.includes(id)) {
        if (!isMulti) {
          setSelectedIds([id]);
        } else {
          setSelectedIds([...ids, id]);
        }
      }
    }

    function removeSelectedId(id) {
      const ids = getSelectedIds().filter((i) => i !== id);
      setSelectedIds(ids);
    }

    function toggleSelectedId(id) {
      const ids = getSelectedIds();
      if (ids.includes(id)) {
        removeSelectedId(id);
      } else {
        addSelectedId(id);
      }
    }

    function updateResultSelection() {
      const selectedIds = new Set(getSelectedIds());
      resultButtons.forEach((btn) => {
        const itemId = parseInt(btn.dataset.itemId, 10);
        if (selectedIds.has(itemId)) {
          btn.classList.add("selected");
          btn.setAttribute("aria-selected", "true");
        } else {
          btn.classList.remove("selected");
          btn.setAttribute("aria-selected", "false");
        }
      });
    }

    function refreshResultButtons() {
      resultButtons = Array.from(resultsContainer.querySelectorAll(".wm-item-picker-result"));
      updateResultSelection();
    }

    function showResults() {
      resultsContainer.classList.add("show");
      searchInput.setAttribute("aria-expanded", "true");
    }

    function hideResults() {
      resultsContainer.classList.remove("show");
      searchInput.setAttribute("aria-expanded", "false");
      selectedIndex = -1;
    }

    function highlightIndex(index) {
      resultButtons.forEach((btn, i) => {
        if (i === index) {
          btn.classList.add("active");
          btn.focus({ preventScroll: true });
        } else {
          btn.classList.remove("active");
        }
      });
      selectedIndex = index;
    }

    function pickHighlighted() {
      if (selectedIndex >= 0 && selectedIndex < resultButtons.length) {
        const btn = resultButtons[selectedIndex];
        const itemId = parseInt(btn.dataset.itemId, 10);
        if (isMulti) {
          toggleSelectedId(itemId);
          updateResultSelection();
        } else {
          addSelectedId(itemId);
          updateResultSelection();
          hideResults();
          searchInput.value = "";
          searchInput.blur();
        }
      }
    }

    function handleKeyDown(event) {
      if (!resultsContainer.classList.contains("show")) {
        return;
      }

      switch (event.key) {
        case "ArrowDown":
          event.preventDefault();
          if (selectedIndex < resultButtons.length - 1) {
            highlightIndex(selectedIndex + 1);
          }
          break;
        case "ArrowUp":
          event.preventDefault();
          if (selectedIndex > 0) {
            highlightIndex(selectedIndex - 1);
          }
          break;
        case "Enter":
          event.preventDefault();
          pickHighlighted();
          break;
        case "Escape":
          hideResults();
          searchInput.blur();
          break;
        case "Tab":
          // Let browser handle tab, but close results
          hideResults();
          break;
      }
    }

    function handleSearchInput() {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        // htmx will handle the request via hx-trigger
        // We just need to show results when they arrive
      }, DEBOUNCE_MS);
    }

    function handleClickOutside(event) {
      if (!root.contains(event.target)) {
        hideResults();
      }
    }

    function handleResultClick(event) {
      const btn = event.target.closest(".wm-item-picker-result");
      if (!btn) return;

      const itemId = parseInt(btn.dataset.itemId, 10);
      if (isMulti) {
        toggleSelectedId(itemId);
        updateResultSelection();
      } else {
        addSelectedId(itemId);
        updateResultSelection();
        hideResults();
        searchInput.value = "";
        searchInput.blur();
      }
    }

    // Listen for htmx:afterSwap on results container to update buttons
    resultsContainer.addEventListener("htmx:afterSwap", () => {
      refreshResultButtons();
      if (resultButtons.length > 0) {
        showResults();
        highlightIndex(0);
      } else {
        hideResults();
      }
    });

    // Listen for htmx:beforeSwap to know when new results are coming
    resultsContainer.addEventListener("htmx:beforeSwap", () => {
      selectedIndex = -1;
    });

    // Initial button scan
    refreshResultButtons();

    // Event listeners
    searchInput.addEventListener("input", handleSearchInput);
    searchInput.addEventListener("keydown", handleKeyDown);
    searchInput.addEventListener("focus", () => {
      if (resultButtons.length > 0) {
        showResults();
      }
    });
    resultsContainer.addEventListener("click", handleResultClick);
    document.addEventListener("click", handleClickOutside);

    // Cleanup on remove (for dynamic content)
    root._itemPickerCleanup = () => {
      document.removeEventListener("click", handleClickOutside);
    };
  }

  // Initialize on DOMContentLoaded
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  // Re-initialize for dynamically added content (htmx)
  document.body.addEventListener("htmx:afterSwap", (event) => {
    if (event.detail.target && event.detail.target.querySelectorAll) {
      event.detail.target.querySelectorAll("[data-item-picker]").forEach(setupPicker);
    }
  });
})();