import {readFileSync} from "node:fs";
import {commonCategories, filterCatalog, readCatalog} from "../site/assets/themes.js";
import {searchCatalogMatches} from "../site/assets/catalog-search.js";
const {payload, queries = [], category = ""} = JSON.parse(readFileSync(0, "utf8"));
try {
  const records = readCatalog(payload);
  console.log(JSON.stringify({
    keys: filterCatalog(records, "", "").map(({record}) => record.key),
    categories: commonCategories(records),
    queries: queries.map(query => ({
      query,
      actual: filterCatalog(records, query, category).map(({record}) => record.key),
      homepage: searchCatalogMatches(records, query).filter(({record}) => !category
        || record.categories.includes(category)).map(({record}) => record.key),
    })),
  }));
} catch (error) {
  console.log(JSON.stringify({error: error.message}));
}
