/* Command Palette (Contract): Client-side only, indexes nav entries.
   Activated with Cmd/Ctrl+K. Searches navigation entries from the side menu.
*/
// Register before Alpine starts: alpine.min.js queues Alpine.start() in a
// microtask that runs right after it executes, before DOMContentLoaded.
// command_palette.js is ordered before alpine.min.js so this listener exists
// when alpine:init fires inside Alpine.start().
document.addEventListener("alpine:init", function () {
  if (!window.Alpine) {
    console.warn("Alpine.js not loaded; command palette disabled");
    return;
  }

  // Collect navigation entries from the side menu
  function collectNavEntries() {
    const entries = [];
    document.querySelectorAll(".wm-menu-link").forEach((link) => {
      const group = link.closest(".wm-menu-group");
      const heading = group ? group.querySelector(".wm-menu-heading") : null;
      entries.push({
        label: link.textContent.trim(),
        url: link.getAttribute("href"),
        group: heading ? heading.textContent.trim() : "",
        active: link.classList.contains("active"),
      });
    });
    return entries;
  }

  Alpine.data("wmCommandPalette", function () {
    return {
      open: false,
      query: "",
      entries: [],
      filtered: [],
      selectedIndex: 0,

      init() {
        this.entries = collectNavEntries();
        this.filtered = [...this.entries];

        // Keyboard shortcut: Cmd/Ctrl+K
        document.addEventListener("keydown", (e) => {
          if ((e.metaKey || e.ctrlKey) && e.key === "k") {
            e.preventDefault();
            this.openPalette();
          }
          if (this.open) {
            if (e.key === "Escape") {
              this.closePalette();
            } else if (e.key === "ArrowDown") {
              e.preventDefault();
              this.selectNext();
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              this.selectPrev();
            } else if (e.key === "Enter") {
              e.preventDefault();
              this.selectCurrent();
            }
          }
        });

        // Close on click outside
        document.addEventListener("click", (e) => {
          if (this.open && !e.target.closest(".wm-command-palette")) {
            this.closePalette();
          }
        });
      },

      openPalette() {
        this.open = true;
        this.query = "";
        this.filtered = [...this.entries];
        this.selectedIndex = 0;
        this.$nextTick(() => {
          const input = this.$refs.input;
          if (input) input.focus();
        });
        document.body.style.overflow = "hidden";
      },

      closePalette() {
        this.open = false;
        this.query = "";
        this.selectedIndex = 0;
        document.body.style.overflow = "";
      },

      filterEntries() {
        const q = this.query.toLowerCase().trim();
        if (!q) {
          this.filtered = [...this.entries];
        } else {
          this.filtered = this.entries.filter(
            (e) =>
              e.label.toLowerCase().includes(q) ||
              e.group.toLowerCase().includes(q)
          );
        }
        this.selectedIndex = 0;
      },

      selectNext() {
        if (this.selectedIndex < this.filtered.length - 1) {
          this.selectedIndex++;
        }
      },

      selectPrev() {
        if (this.selectedIndex > 0) {
          this.selectedIndex--;
        }
      },

      selectCurrent() {
        const entry = this.filtered[this.selectedIndex];
        if (entry) {
          window.location.href = entry.url;
        }
      },

      goTo(entry) {
        window.location.href = entry.url;
      },
    };
  });
});