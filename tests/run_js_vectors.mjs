import { createRequire } from "module";
import { readFileSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join } from "path";

const here = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const scoring = require(join(here, "..", "smw", "render", "static", "scoring.js"));
const vectors = JSON.parse(
  readFileSync(join(here, "fixtures", "scoring_vectors.json"), "utf8"));

let failures = 0;
for (const c of vectors) {
  const got = scoring.scorePlayer(c.ranked, c.dark_horses, c.finish);
  if (got !== c.expected) {
    console.log(`FAIL ${c.name}: js=${got} expected=${c.expected}`);
    failures += 1;
  }
}
if (failures > 0) process.exit(1);
console.log(`ok: ${vectors.length} vectors`);
