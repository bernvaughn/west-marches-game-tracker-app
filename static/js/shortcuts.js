/* Keyboard shortcuts (Contract): standard web conventions.
   g = go to (command palette), i = inventory/character, m = map,
   h = home, c = character sheet, r = trades, j/k = next/prev
*/
document.addEventListener("DOMContentLoaded", function () {
  // Shortcut definitions
  const shortcuts = {
    // Global shortcuts (work everywhere)
    "KeyG": { meta: true, action: "commandPalette" },  // Cmd/Ctrl+G or Cmd/Ctrl+K
    "KeyK": { meta: true, action: "commandPalette" },
    "Slash": { meta: false, input: true, action: "commandPalette" },  // / when not in input
    
    // Navigation shortcuts (when not in input field)
    "KeyH": { meta: false, input: false, action: "nav", url: "/club/", label: "Home" },
    "KeyI": { meta: false, input: false, action: "nav", url: "/club/character/", label: "Inventory/Character" },
    "KeyM": { meta: false, input: false, action: "nav", url: "/club/map/", label: "Map" },
    "KeyR": { meta: false, input: false, action: "nav", url: "/club/trades/", label: "Trades" },
    "KeyC": { meta: false, input: false, action: "nav", url: "/club/character/", label: "Character" },
    "KeyQ": { meta: false, input: false, action: "nav", url: "/club/quests/", label: "Quests" },
    "KeyS": { meta: false, input: false, action: "nav", url: "/club/shops/", label: "Shops" },
    "KeyT": { meta: false, input: false, action: "nav", url: "/club/downtime/", label: "Downtime" },
    
    // Next/prev for lists
    "KeyJ": { meta: false, input: false, action: "nextItem" },
    "KeyK": { meta: false, input: false, action: "prevItem" },
  };

  // Check if element is an input-like element
  function isInputElement(el) {
    if (!el) return false;
    const tag = el.tagName.toLowerCase();
    return (
      tag === "input" ||
      tag === "textarea" ||
      tag === "select" ||
      el.isContentEditable ||
      el.closest('[contenteditable="true"]')
    );
  }

  // Get the club slug from the current URL
  function getClubSlug() {
    const match = window.location.pathname.match(/\/club\/([^/]+)/);
    return match ? match[1] : null;
  }

  // Build full URL with club slug
  function buildUrl(path) {
    const clubSlug = getClubSlug();
    if (clubSlug && !path.startsWith("http")) {
      return `/club/${clubSlug}${path}`;
    }
    return path;
  }

  // Handle keyboard events
  document.addEventListener("keydown", function (e) {
    // Don't trigger shortcuts in input fields (except for specific ones)
    const inInput = isInputElement(document.activeElement);
    
    // Build key identifier
    let key = e.code;
    if (e.metaKey || e.ctrlKey) {
      key = (e.metaKey ? "Meta+" : "Ctrl+") + key;
    }
    
    // Check for exact match first
    let shortcut = shortcuts[e.code];
    
    // Check for meta/ctrl combinations
    if (!shortcut && (e.metaKey || e.ctrlKey)) {
      shortcut = shortcuts[(e.metaKey ? "Meta+" : "Ctrl+") + e.code];
    }
    
    if (!shortcut) return;
    
    // Check input restrictions
    if (shortcut.input !== undefined && shortcut.input !== inInput) {
      return;
    }
    
    // Prevent default for navigation shortcuts
    if (shortcut.action === "nav") {
      e.preventDefault();
      window.location.href = buildUrl(shortcut.url);
      return;
    }
    
    if (shortcut.action === "commandPalette") {
      e.preventDefault();
      // Trigger Alpine command palette
      const palette = document.querySelector('[x-data*="wmCommandPalette"]');
      if (palette && palette._x_dataStack) {
        palette._x_dataStack[0].openPalette();
      }
      return;
    }
    
    if (shortcut.action === "nextItem") {
      e.preventDefault();
      focusNextItem();
      return;
    }
    
    if (shortcut.action === "prevItem") {
      e.preventDefault();
      focusPrevItem();
      return;
    }
  });

  // Focusable items for j/k navigation
  function getFocusableItems() {
    return Array.from(document.querySelectorAll(
      'a.wm-menu-link, .wm-card a, .table tbody tr td:first-child a, .wm-data-table tbody tr'
    )).filter(el => el.offsetParent !== null); // visible only
  }

  let currentFocusIndex = -1;
  
  function focusNextItem() {
    const items = getFocusableItems();
    if (items.length === 0) return;
    
    currentFocusIndex = (currentFocusIndex + 1) % items.length;
    items[currentFocusIndex].focus();
    items[currentFocusIndex].scrollIntoView({ behavior: "smooth", block: "center" });
  }
  
  function focusPrevItem() {
    const items = getFocusableItems();
    if (items.length === 0) return;
    
    currentFocusIndex = (currentFocusIndex - 1 + items.length) % items.length;
    items[currentFocusIndex].focus();
    items[currentFocusIndex].scrollIntoView({ behavior: "smooth", block: "center" });
  }

  // Reset focus index on click
  document.addEventListener("click", function () {
    currentFocusIndex = -1;
  });

  // Trade poll handler for navbar badge updates
  function initTradePoll() {
    const pollEl = document.getElementById('trade-poll');
    if (!pollEl) return;
    
    pollEl.addEventListener('htmx:afterRequest', function(evt) {
      if (!evt.detail.successful) return;
      try {
        const data = JSON.parse(evt.detail.xhr.responseText);
        updateApprovalsBadge('Trades', data.count);
      } catch (e) {
        // Ignore parse errors
      }
    });
  }

  function updateApprovalsBadge(label, count) {
    const menu = document.querySelector('.approvals-menu');
    if (!menu) return;
    
    let item = menu.querySelector('[data-approval-label="' + label + '"]');
    if (count > 0) {
      if (!item) {
        // Create new item
        const list = menu.querySelector('.dropdown-menu');
        if (list) {
          item = document.createElement('li');
          item.innerHTML = '<a class="dropdown-item d-flex justify-content-between gap-3" href="#">' + label + ' <span class="badge text-bg-secondary" data-approval-label="' + label + '">' + count + '</span></a>';
          list.appendChild(item);
        }
      } else {
        const badge = item.querySelector('.badge');
        if (badge) badge.textContent = count;
      }
      // Update total
      const totalBadge = menu.querySelector('.approvals-total');
      if (totalBadge) {
        const allBadges = menu.querySelectorAll('.badge[data-approval-label]');
        let total = 0;
        allBadges.forEach(function(b) { total += parseInt(b.textContent) || 0; });
        totalBadge.textContent = total;
        if (total === 0) {
          menu.style.display = 'none';
        } else {
          menu.style.display = '';
        }
      }
    } else if (item) {
      // Remove item if count is 0
      item.remove();
      updateApprovalsBadge(label, 0); // Recalculate total
    }
  }

  // Initialize trade poll
  initTradePoll();

  // Export for testing
  window.wmShortcuts = {
    getClubSlug,
    buildUrl,
    shortcuts,
  };
});