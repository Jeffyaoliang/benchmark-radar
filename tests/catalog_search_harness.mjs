// Run the website's catalog search over records and queries read from stdin,
// and print each query's ranked record keys and the keys that match every
// query word. The Python parity test compares both with QueryService.
import { readFileSync } from "node:fs";
import { searchCatalogMatches } from "../site/assets/catalog-search.js";

const { records, queries } = JSON.parse(readFileSync(0, "utf8"));
const ranked = {};
for (const query of queries) {
  const matches = searchCatalogMatches(records, query);
  ranked[query] = {
    keys: matches.map((match) => match.record.key),
    full: matches.filter((match) => !match.missing.length).map((match) => match.record.key),
  };
}
process.stdout.write(JSON.stringify(ranked));
