/**
 * Shop Favorites - Track recently used shops in session storage.
 * Updates session storage on successful buy/sell actions.
 */
(function () {
  const MAX_RECENT = 10;
  const STORAGE_KEY_PREFIX = "wm_recent_shops_";

  function getStorageKey() {
    const pk = window.wmCharacterPk;
    if (!pk) return null;
    return STORAGE_KEY_PREFIX + pk;
  }

  function getRecentShops() {
    const key = getStorageKey();
    if (!key) return [];
    try {
      const stored = sessionStorage.getItem(key);
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  }

  function setRecentShops(shops) {
    const key = getStorageKey();
    if (!key) return;
    try {
      sessionStorage.setItem(key, JSON.stringify(shops));
    } catch {
      // Ignore storage errors (e.g., private browsing, quota exceeded)
    }
  }

  function addRecentShop(shopId) {
    const shops = getRecentShops();
    // Remove if already exists
    const filtered = shops.filter((id) => id !== shopId);
    // Add to front
    filtered.unshift(shopId);
    // Limit to MAX_RECENT
    if (filtered.length > MAX_RECENT) {
      filtered.length = MAX_RECENT;
    }
    setRecentShops(filtered);
  }

  function extractShopIdFromUrl(url) {
    // Match /shops/<shop_id>/ or /shops/<shop_id>/buy/ or /shops/<shop_id>/sell/
    const match = url.match(/\/shops\/(\d+)\//);
    return match ? parseInt(match[1], 10) : null;
  }

  // Listen for HTMX requests that complete with a redirect to a shop detail page
  document.body.addEventListener("htmx:afterRequest", function (evt) {
    const xhr = evt.detail.xhr;
    if (!xhr) return;

    // Check for HX-Redirect header pointing to a shop detail page
    const redirect = xhr.getResponseHeader("HX-Redirect");
    if (!redirect) return;

    const shopId = extractShopIdFromUrl(redirect);
    if (shopId) {
      addRecentShop(shopId);
    }
  });

  // Also listen for form submissions on the shop detail page that might not use HTMX redirect
  // but we can catch the shop ID from the form action
  document.body.addEventListener("htmx:configRequest", function (evt) {
    const elt = evt.detail.elt;
    if (!elt) return;

    // Check if this is a buy or sell form
    const form = elt.closest("form");
    if (!form) return;

    const action = form.getAttribute("action") || form.getAttribute("hx-post") || form.getAttribute("hx-get");
    if (!action) return;

    const shopId = extractShopIdFromUrl(action);
    if (shopId) {
      // Store the shop ID on the form element so we can retrieve it after the request
      form.dataset.wmShopId = shopId;
    }
  });

  document.body.addEventListener("htmx:afterRequest", function (evt) {
    const xhr = evt.detail.xhr;
    const elt = evt.detail.elt;
    if (!xhr || !elt) return;

    // Check if this was a successful buy/sell form submission
    const form = elt.closest("form");
    if (!form) return;

    const shopId = form.dataset.wmShopId;
    if (!shopId) return;

    // Only track on successful responses (2xx) that are not redirects
    // (redirects are handled by the HX-Redirect listener above)
    if (xhr.status >= 200 && xhr.status < 300 && !xhr.getResponseHeader("HX-Redirect")) {
      addRecentShop(parseInt(shopId, 10));
    }
  });
})();