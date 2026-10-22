import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const source = readFileSync("site/assets/route-recovery.js", "utf8");
const recover = (address) => {
  const url = new URL(address, "https://benchmark-radar.org");
  const replacements = [];
  vm.runInNewContext(source, {
    URL,
    window: { location: {
      pathname: url.pathname, origin: url.origin, search: url.search, hash: url.hash,
      replace: (target) => replacements.push(target),
    } },
  });
  return replacements;
};

for (const path of ["/models", "/models/"]) {
  assert.deepEqual(recover(path), ["https://benchmark-radar.org/?view=models"]);
}
const recovered = new URL(recover(
  "/models/?lab=OpenAI&mq=GPT%205&msort=newest&msrc=llm_stats&mshared=1&mpage=3&view=today#contact",
)[0]);
assert.equal(recovered.pathname, "/");
assert.equal(recovered.searchParams.get("view"), "models");
assert.equal(recovered.searchParams.get("lab"), "OpenAI");
assert.equal(recovered.searchParams.get("mq"), "GPT 5");
assert.equal(recovered.searchParams.get("mpage"), "3");
assert.equal(recovered.hash, "#contact");
for (const path of ["/", "/404.html", "/models/missing/", "/missing/", "/benchmarks/missing/"]) {
  assert.deepEqual(recover(path), [], `${path} must not redirect or loop`);
}
