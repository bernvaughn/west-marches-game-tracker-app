/* Behaviour harness for static/js/starting_reveal.js.
   Runs both reveal scripts against a tiny fake DOM with a fake clock, then
   plays one scenario and prints the final state as JSON.
   Usage: node starting_reveal_harness.js <static_dir> <scenario> <reduced 0|1>
 */
"use strict";
var fs = require("fs");
var path = require("path");
var vm = require("vm");

var staticDir = process.argv[2];
var scenario = process.argv[3];
var reduced = process.argv[4] === "1";

// ---- fake clock (setTimeout + requestAnimationFrame share one queue) ----
var now = 0;
var seq = 0;
var queue = [];
function schedule(fn, ms, isFrame) {
  var id = ++seq;
  queue.push({ id: id, at: now + (ms || 0), fn: fn, frame: isFrame });
  return id;
}
function cancel(id) {
  queue = queue.filter(function (t) { return t.id !== id; });
}
function advance(ms) {
  var end = now + ms;
  for (;;) {
    queue.sort(function (a, b) { return a.at - b.at || a.id - b.id; });
    if (!queue.length || queue[0].at > end) break;
    var t = queue.shift();
    now = t.at;
    t.frame ? t.fn(now) : t.fn();
  }
  now = end;
}

// ---- fake DOM ----
function Listeners() { this.map = {}; }
Listeners.prototype.add = function (type, fn) {
  (this.map[type] = this.map[type] || []).push(fn);
};
Listeners.prototype.fire = function (type, event) {
  (this.map[type] || []).slice().forEach(function (fn) { fn(event); });
};

function El(attrs, parent) {
  this.attrs = attrs || {};
  this.children = [];
  this.parent = parent || null;
  this.hidden = false;
  this.textContent = "";
  this.listeners = new Listeners();
  var cls = {};
  this.classList = {
    add: function (c) { cls[c] = true; },
    remove: function (c) { delete cls[c]; },
    toggle: function (c, on) { if (on) cls[c] = true; else delete cls[c]; },
    contains: function (c) { return !!cls[c]; },
  };
  if (parent) parent.children.push(this);
}
El.prototype.hasAttribute = function (n) { return n in this.attrs; };
El.prototype.getAttribute = function (n) { return n in this.attrs ? this.attrs[n] : null; };
El.prototype.setAttribute = function (n, v) { this.attrs[n] = String(v); };
El.prototype.addEventListener = function (t, fn) { this.listeners.add(t, fn); };
El.prototype.contains = function (other) {
  for (var e = other; e; e = e.parent) if (e === this) return true;
  return false;
};
El.prototype.all = function () {
  var out = [];
  this.children.forEach(function (c) { out.push(c); out = out.concat(c.all()); });
  return out;
};
function attrOf(sel) { return sel.replace(/^\[|\]$/g, ""); }
El.prototype.querySelectorAll = function (sel) {
  var a = attrOf(sel);
  return this.all().filter(function (e) { return e.hasAttribute(a); });
};
El.prototype.querySelector = function (sel) {
  return this.querySelectorAll(sel)[0] || null;
};
// Dispatch a click that bubbles from this element to the document.
El.prototype.click = function () {
  var stopped = false;
  var event = { target: this, stopPropagation: function () { stopped = true; } };
  for (var e = this; e && !stopped; e = e.parent) e.listeners.fire("click", event);
};

var doc = new El({});
doc.hidden = false;
var root = new El({
  "data-wm-starting-reveal": "",
  "data-sheet-url": "/sheet/",
  "data-coins": "1500",
}, doc);
var list = new El({ "data-wm-reveal": "" }, root);
["+1 Backpack", "+2 Rations", "+1 Rope"].forEach(function (t) {
  var li = new El({ "data-wm-reveal-item": "" }, list);
  li.textContent = t;
});
var coinsBlock = new El({ "data-wm-coins": "" }, root);
var coinsDisplay = new El({ "data-wm-coins-display": "" }, coinsBlock);
coinsDisplay.textContent = "15 gp";
var live = new El({ "data-wm-live": "" }, root);
var replay = new El({ "data-wm-replay": "" }, root);
replay.hidden = true;
var docListeners = new Listeners();
doc.addEventListener = function (t, fn) { docListeners.add(t, fn); };

var mqListeners = new Listeners();
var mq = {
  matches: reduced,
  addEventListener: function (t, fn) { mqListeners.add(t, fn); },
};

var navigations = [];
var sandbox = {
  document: doc,
  setTimeout: function (fn, ms) { return schedule(fn, ms, false); },
  clearTimeout: cancel,
  requestAnimationFrame: function (fn) { return schedule(fn, 16, true); },
  matchMedia: function () { return mq; },
  location: { assign: function (u) { navigations.push(u); } },
  Array: Array,
  parseInt: parseInt,
  isNaN: isNaN,
};
sandbox.window = sandbox;
vm.createContext(sandbox);
["starting_coins_animation.js", "starting_reveal.js"].forEach(function (f) {
  vm.runInContext(fs.readFileSync(path.join(staticDir, "js", f), "utf8"), sandbox);
});
docListeners.fire("DOMContentLoaded", {});

function snapshot() {
  return {
    revealed: root.querySelectorAll("[data-wm-reveal-item]").map(function (li) {
      return li.classList.contains("is-revealed");
    }),
    armed: root.classList.contains("wm-reveal--armed"),
    coinsHidden: coinsBlock.hidden,
    coinsText: coinsDisplay.textContent,
    live: live.textContent,
    replayHidden: replay.hidden,
    navigations: navigations.slice(),
  };
}

var result = {};
switch (scenario) {
  case "first-play":
    result.start = snapshot();
    advance(1300);
    result.midCoins = snapshot();
    advance(2000);
    result.end = snapshot();
    advance(1000);
    result.after = snapshot();
    advance(5000);
    result.later = snapshot();
    break;
  case "replay":
    advance(4000);
    replay.click();
    result.afterClick = snapshot();
    advance(4000);
    result.end = snapshot();
    break;
  case "replay-during-coins":
    advance(2500); // items shown, coins mid count-up
    replay.click();
    advance(1500); // old count-up would have ended by now
    result.mid = snapshot();
    advance(3000);
    result.end = snapshot();
    break;
  case "click-item-during-play":
    advance(100);
    root.querySelector("[data-wm-reveal-item]").click();
    advance(8000);
    result.end = snapshot();
    break;
  case "tab-hidden-during-play":
    advance(100);
    doc.hidden = true;
    docListeners.fire("visibilitychange", {});
    doc.hidden = false;
    docListeners.fire("visibilitychange", {});
    advance(8000);
    result.end = snapshot();
    break;
  case "click-after-finish":
    advance(4000);
    root.querySelector("[data-wm-reveal-item]").click();
    advance(5000);
    result.end = snapshot();
    break;
  case "reduced-motion-turned-on":
    advance(100);
    mq.matches = true;
    mqListeners.fire("change", { matches: true });
    advance(8000);
    result.end = snapshot();
    break;
  default:
    throw new Error("unknown scenario " + scenario);
}
process.stdout.write(JSON.stringify(result));
