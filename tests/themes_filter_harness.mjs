import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";

const html = readFileSync(process.argv[2], "utf8");
const decode = value => value.replaceAll("&quot;", '\"').replaceAll("&#x27;", "'")
  .replaceAll("&lt;", "<").replaceAll("&gt;", ">").replaceAll("&amp;", "&");
const script = html.match(/<script>\s*([\s\S]*?)<\/script>/g)?.at(-1)?.replace(/^<script>|<\/script>$/g, "");
assert.ok(script);
const cards = [...html.matchAll(/<article class="theme-card"([^>]*)>/g)].map(([, attrs]) => {
  const attribute = name => decode(attrs.match(new RegExp(`data-${name}="([^\"]*)"`))[1]);
  const card = {id: attribute("record"), dataset: {categories: attribute("categories")}, hidden: false};
  card.classList = {toggle: (_name, hidden) => {card.hidden = hidden;}};
  return card;
});
const nodes = new Map();
for (const id of ["theme-category", "theme-results", "theme-no-results"]) {
  nodes.set(id, {value: "", hidden: false, listeners: {},
    addEventListener(event, callback) {this.listeners[event] = callback;}});
}
const document = {getElementById: id => nodes.get(id), querySelectorAll: () => cards};
runInNewContext(script, {document});
const category = nodes.get("theme-category");
category.value = process.argv[3] || "";
category.listeners.change();
const result = cards.filter(card => !card.hidden).map(card => card.id);
assert.equal(nodes.get("theme-no-results").hidden, result.length > 0);
assert.equal(nodes.get("theme-results").textContent, `Showing ${result.length} of ${cards.length} benchmark records`);
category.value = "";
category.listeners.change();
assert.ok(cards.every(card => !card.hidden));
console.log(JSON.stringify(result));
