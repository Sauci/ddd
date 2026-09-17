// Writes the licence of every package bundled into the compiled pages beside them, and refuses a
// licence outside the ones this project accepts. Only production dependencies are bundled, so
// only they are listed.
import { execSync } from "node:child_process";
import { readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const ALLOWED = new Set(["MIT", "ISC", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause"]);
const tree = JSON.parse(execSync("npm ls --omit=dev --all --long --json", { encoding: "utf8" }));

const packages = new Map();
const visit = (dependencies) => {
  for (const [name, entry] of Object.entries(dependencies ?? {})) {
    const key = `${name}@${entry.version}`;
    if (!packages.has(key)) {
      packages.set(key, { name, version: entry.version, path: entry.path });
      visit(entry.dependencies);
    }
  }
};
visit(tree.dependencies);

const sections = [];
const refused = [];
for (const { name, version, path } of [...packages.values()].sort((a, b) =>
  a.name.localeCompare(b.name),
)) {
  const manifest = JSON.parse(readFileSync(join(path, "package.json"), "utf8"));
  const licence = typeof manifest.license === "string" ? manifest.license : "UNKNOWN";
  if (!ALLOWED.has(licence)) refused.push(`${name}@${version}: ${licence}`);
  const file = readdirSync(path).find((entry) => /^(licen[cs]e|copying)(\.|$)/i.test(entry));
  const text = file
    ? readFileSync(join(path, file), "utf8").trim()
    : `${licence} (no licence file)`;
  sections.push(`${name} ${version}\n${licence}\n\n${text}`);
}
if (refused.length > 0) {
  console.error(`bundled packages under a licence outside ${[...ALLOWED].join(", ")}:`);
  for (const entry of refused) console.error(`  ${entry}`);
  process.exit(1);
}
const out = join("..", "src", "ddd", "gui", "static", "third-party-licenses.txt");
writeFileSync(out, `${sections.join("\n\n----------------------------------------\n\n")}\n`);
console.log(`wrote the licences of ${sections.length} bundled packages to ${out}`);
