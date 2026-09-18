// Historical command retained for CI: validate the current presentation owners.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
const read = (path) => readFileSync(fileURLToPath(new URL(`../${path}`, import.meta.url)), "utf8");
const home = read("apps/presentation/site/src/App.tsx");
const styles = read("apps/presentation/site/src/styles.css");
assert.doesNotMatch(home, /href=.[^\n]*(?:deprecated|frontstage\/)/, "homepage must not promote retired surfaces");
for (const destination of ["docs/guides/personal-workspace-user-guide/", "benchmarks/swe-marathon/", "benchmarks/lhtb/", "benchmarks/deepswe/behavior-discovery/", "benchmarks/deepswe-sol/", "docs/showcases/index", "developers/projections/"]) {
  assert.ok(home.includes(destination), `missing public destination: ${destination}`);
}
assert.ok(styles.includes("prefers-reduced-motion"));
assert.ok(styles.includes(":focus-visible"));
assert.doesNotMatch(read("apps/presentation/dashboard/src/styles.css"), /\.frontstage-(?:showcase|ops)-/, "retired presentation styles must not ship");
console.log("public presentation design boundary: ok");
