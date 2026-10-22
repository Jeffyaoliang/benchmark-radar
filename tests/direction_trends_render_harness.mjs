// Run the Trends direction table's production render code against a small DOM
// stub: the weekly bars (printed for the Python seed to match), the seeded
// note and controls when the catalog fails, and binding before it loads.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync("site/assets/app.js", "utf8");
function fn(name) {
  const start = source.indexOf(`function ${name}(`);
  assert(start >= 0, name);
  return source.slice(start, source.indexOf("\n}\n", start) + 2);
}

class Node {
  constructor(tag) {
    this.tag = tag;
    this.attrs = [];
    this.children = [];
    this.dataset = {};
    this.listeners = {};
    this.textContent = "";
    this.disabled = false;
    this.value = "";
    this.classList = { add() {}, remove() {}, toggle() {} };
  }
  querySelector() {
    return null;
  }
  setAttribute(key, value) {
    this.attrs.push([key, String(value)]);
  }
  append(...children) {
    this.children.push(...children);
  }
  addEventListener(type, listener) {
    (this.listeners[type] ||= []).push(listener);
  }
  serialize() {
    const attrs = this.attrs.map(([key, value]) => ` ${key}="${value}"`).join("");
    const inner = this.children.length ? this.children.map((child) => child.serialize()).join("") : this.textContent;
    return `<${this.tag}${attrs}>${inner}</${this.tag}>`;
  }
}
const nodes = new Map();
const byId = (id) => {
  if (!nodes.has(id)) nodes.set(id, new Node(id === "direction-trends-body" ? "tbody" : "div"));
  return nodes.get(id);
};
globalThis.document = { createElementNS: (_ns, tag) => new Node(tag), addEventListener() {}, querySelectorAll: () => [] };

let releaseIndex;
const state = { data: {}, view: "trends", directionTrendWindow: 30, directionTrendGroup: "" };
const env = {
  state, byId,
  t: (key, params) => Object.entries(params || {}).reduce((text, [k, v]) => text.replaceAll(`{${k}}`, String(v)), key),
  formatDate: (value) => value,
  writeUrl: () => {},
  loadBenchmarkIndex: () => new Promise((resolve) => { releaseIndex = resolve; }),
  DIRECTION_TREND_WINDOWS: [30, 60, 90],
};
const { directionSparkline, directionFocusChart, renderDirectionTrends } = new Function(
  ...Object.keys(env),
  `${fn("directionTrendNote")}\n${fn("reconcileSeededDirectionFocus")}\n${fn("closeDirectionFocus")}\n${fn("directionSparkline")}\n${fn("directionFocusChart")}\n${fn("initDirectionTrends")}\n${fn("renderDirectionTrends")}\nreturn { directionSparkline, directionFocusChart, renderDirectionTrends };`,
)(...Object.values(env));

// The seeded window selector works while the catalog is still loading.
byId("direction-trends-body").children = [new Node("tr")];
Object.assign(byId("direction-trends-note").dataset, { anchor: "2026-10-14", window: "30", comparable: "1", since: "2026-05-18" });
byId("direction-trends-note").textContent = "seeded English text";
renderDirectionTrends();
assert.equal(byId("direction-trends-window").listeners.change.length, 1);

// The catalog fails: the seeded caveats stay, the failure is added, and the
// controls that can no longer change anything are disabled.
releaseIndex(null);
await new Promise((resolve) => setTimeout(resolve, 0));
// The caveats are rebuilt from the seeded facts through t(), so they follow
// the reader's language; the failure is a separate visible status.
assert.equal(byId("direction-trends-note").textContent,
  "New benchmark records by release date, 30 days to 2026-10-14. The latest days are still filling in as new papers are collected. "
  + "A record counts in every direction it is filed under, so rows overlap and do not add up to a total. "
  + "Undated counts every record in the direction that has no release date, whatever the window.");
assert.equal(byId("direction-trends-status").textContent, "The benchmark catalog could not be loaded.");
assert.equal(byId("direction-trends-window").disabled, true);
assert.equal(byId("direction-trends-group").disabled, true);
// Rendering again does not repeat the failure.
renderDirectionTrends();
assert.equal(byId("direction-trends-status").textContent.match(/could not be loaded/g).length, 1);

// A link to a direction other than the seeded one cannot be honoured without
// the catalog: the seeded panel is hidden and the status says so.
state.directionFocus = "law";
renderDirectionTrends();
assert.equal(byId("direction-focus").hidden, true);
assert.match(byId("direction-trends-status").textContent, /The linked view could not be shown\./);
state.directionFocus = "";

// A link to another window cannot be shown from the 30-day seed either.
state.directionTrendWindow = 90;
renderDirectionTrends();
assert.match(byId("direction-trends-status").textContent, /The linked view could not be shown\./);
assert.equal(byId("direction-focus").hidden, true);
state.directionTrendWindow = 30;

// Reached through the app with no seed, a failed catalog still leaves the
// section visible with the failure stated.
nodes.clear();
state.benchmarkIndexLoaded = true;
state.benchmarkIndex = null;
renderDirectionTrends();
assert.equal(byId("direction-trends").hidden, false);
assert.equal(byId("direction-trends-status").textContent, "The benchmark catalog could not be loaded.");

// The bars, serialized for test_direction_trends.py to compare with the seed.
const cases = JSON.parse(readFileSync(0, "utf8"));
process.stdout.write(JSON.stringify({
  sparklines: cases.map((weekly) => directionSparkline(weekly).serialize()),
  focusCharts: cases.map((weekly) => directionFocusChart(weekly).serialize()),
}));
