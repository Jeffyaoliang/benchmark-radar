import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";

const html = readFileSync(process.argv[2], "utf8");
const script = html.match(/<script>\s*([\s\S]*?)<\/script>/g)?.at(-1)?.replace(/^<script>|<\/script>$/g, "");
assert.ok(script, "theme filter script is present");
const cards = [...html.matchAll(/<article class="theme-card"([^>]*)>/g)].map(([, attrs]) => {
  const attribute = (name) => attrs.match(new RegExp(`data-${name}="([^"]*)"`))?.[1];
  const card = {
    id: attribute("record").replaceAll("&#x27;", "'"),
    dataset: {
      categories: attribute("categories").replaceAll("&quot;", '"'),
      searchFields: attribute("search-fields").replaceAll("&quot;", '"'),
      name: attribute("name").replaceAll("&#x27;", "'"),
      record: attribute("record").replaceAll("&#x27;", "'"),
      completeness: attribute("completeness"),
    },
    hidden: false,
    style: { order: "" },
  };
  card.classList = { toggle: (_name, hidden) => { card.hidden = hidden; } };
  return card;
});
assert.ok(cards.length > 0);

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
search.value = process.argv[3] || "";
category.value = process.argv[4] || "";
search.listeners.input();
if (process.argv[5] === "invalid") {
  assert.match(nodes.get("theme-results").textContent, /Enter a search term/);
  assert.equal(nodes.get("theme-no-results").hidden, false);
}
console.log(JSON.stringify(cards.filter((card) => !card.hidden)
  .sort((a, b) => Number(a.style.order || 0) - Number(b.style.order || 0))
  .map((card) => card.id)));
