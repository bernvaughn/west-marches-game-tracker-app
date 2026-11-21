/**
 * Dashboard card auto-refresh.
 *
 * Listens for the questCompleted, junkChanged and downtimeSpent custom events
 * dispatched on document.body (sent as HX-Trigger headers by the turn-in,
 * sell-junk and downtime-spend change views) and re-fetches the matching card
 * partial, swapping its outerHTML. Cards are server-rendered on initial load,
 * so they work without JS; auto-refresh is the htmx enhancement.
 */
(function () {
  const EVENT_CARD = {
    questCompleted: ["quests"],
    junkChanged: ["quick_actions"],
    downtimeSpent: ["downtime"],
  };

  function refreshCard(key) {
    const keys = Array.isArray(key) ? key : [key];
    keys.forEach((k) => {
      const id = `dashboard-card-${k}`;
      const card = document.getElementById(id);
      if (!card) return;
      const url = card.dataset.refreshUrl;
      if (!url) return;
      htmx.ajax("GET", url, { target: `#${id}`, swap: "outerHTML" });
    });
  }

  Object.entries(EVENT_CARD).forEach(([eventName, keys]) => {
    document.body.addEventListener(eventName, () => refreshCard(keys));
  });
})();
