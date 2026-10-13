import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";

const html = readFileSync(process.argv[2], "utf8");
const script = html.match(/<script>\s*([\s\S]*?)<\/script>/g)?.at(-1)?.replace(/^<script>|<\/script>$/g, "");
assert.ok(script, "theme filter script is present");
const cards = [...html.matchAll(/<article class="theme-card"([^>]*)>/g)].map(([, attrs]) => {
  const attribute = (name) => attrs.match(new RegExp(`data-${name}="([^"]*)"`))?.[1];
  const card = {
    id: attribute("record"),
    dataset: {
      categories: attribute("categories").replaceAll("&quot;", '"'),
      search: attribute("search"),
    },
    hidden: false,
  };
  card.classList = { toggle: (_name, hidden) => { card.hidden = hidden; } };
  return card;
});
assert.equal(cards.length, 2);
const visibility = () => Object.fromEntries(cards.map((card) => [card.id, card.hidden]));

const nodes = new Map();
for (const id of ["theme-filter", "theme-category", "theme-results", "theme-no-results"]) {
  nodes.set(id, { value: "", hidden: false, listeners: {}, addEventListener(event, callback) { this.listeners[event] = callback; } });
}
const document = {
  getElementById: (id) => nodes.get(id),
  querySelectorAll: () => cards,
};
runInNewContext(script, { document });
const search = nodes.get("theme-filter");
const category = nodes.get("theme-category");
search.value = "HLE";
search.listeners.input();
assert.deepEqual(visibility(), { "llm-stats:other": true, "llm-stats:agent-bench": false });
assert.match(nodes.get("theme-results").textContent, /Showing 1 of 2/);
category.value = "__uncategorized__";
category.listeners.change();
assert.deepEqual(visibility(), { "llm-stats:other": true, "llm-stats:agent-bench": true });
search.value = "Other";
search.listeners.input();
assert.deepEqual(visibility(), { "llm-stats:other": false, "llm-stats:agent-bench": true });
