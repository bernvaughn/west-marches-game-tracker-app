/* Shop Street keyboard shortcuts:
   1-9 = select shop by position
   b = open buy modal for selected shop
   s = open sell modal for selected shop
*/
(function () {
  var selectedShopIndex = -1;
  var shopLots = [];

  function init() {
    // Only run on shop street page
    var street = document.querySelector(".wm-street");
    if (!street) return;

    shopLots = Array.prototype.slice.call(
      document.querySelectorAll(".wm-street-lot:not(.wm-street-lot--stall)")
    ).filter(function (lot) {
      return lot.querySelector(".wm-street-link");
    });

    document.addEventListener("keydown", handleKeydown);
  }

  function handleKeydown(e) {
    // Don't trigger shortcuts in input fields
    var tag = (document.activeElement && document.activeElement.tagName.toLowerCase()) || "";
    var inInput = tag === "input" || tag === "textarea" || tag === "select" || document.activeElement.isContentEditable;
    if (inInput) return;

    // Number keys 1-9 for shop selection
    if (e.key >= "1" && e.key <= "9") {
      e.preventDefault();
      var index = parseInt(e.key, 10) - 1;
      if (index < shopLots.length) {
        selectShop(index);
      }
      return;
    }

    // 'b' for buy, 's' for sell
    if (e.key === "b" || e.key === "B") {
      e.preventDefault();
      openBuyModal();
      return;
    }

    if (e.key === "s" || e.key === "S") {
      e.preventDefault();
      openSellModal();
      return;
    }
  }

  function selectShop(index) {
    // Remove previous selection
    shopLots.forEach(function (lot, i) {
      lot.classList.remove("wm-street-lot--selected");
      if (i === index) {
        lot.classList.add("wm-street-lot--selected");
      }
    });
    selectedShopIndex = index;
    
    // Scroll into view
    var lot = shopLots[index];
    if (lot) {
      lot.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }

  function openBuyModal() {
    if (selectedShopIndex < 0 || selectedShopIndex >= shopLots.length) return;
    
    var link = shopLots[selectedShopIndex].querySelector(".wm-street-link");
    if (!link) return;
    
    // Navigate to shop detail page to buy
    window.location.href = link.href;
  }

  function openSellModal() {
    if (selectedShopIndex < 0 || selectedShopIndex >= shopLots.length) return;
    
    var link = shopLots[selectedShopIndex].querySelector(".wm-street-link");
    if (!link) return;
    
    // Navigate to shop detail page to sell
    window.location.href = link.href;
  }

  // Initialize on DOM ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();