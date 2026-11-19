// Writes the licence of every package bundled into the compiled pages beside them, and refuses a
// licence outside the ones this project accepts. Only production dependencies are bundled, so
// only they are listed.
import { execSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

// The zero-clause BSD licence (0BSD) grants everything BSD-2-Clause does and asks for less - not
// even the notice - so it is within "the BSD licences" spec 6.8 of the web GUI design allows;
// tslib (a dependency of React Aria's @swc/helpers) is the package that brought it.
const ALLOWED = new Set(["MIT", "ISC", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "0BSD"]);
const tree = JSON.parse(execSync("npm ls --omit=dev --all --long --json", { encoding: "utf8" }));

// The paths `npm ls` prints have anything token-shaped starred out (a uuid in a directory name is
// enough), so no directory is taken from `npm ls`: each package's directory is read off the lock
// file's own keys, which are relative to the page's root.
const root = join(import.meta.dirname, "..");
const lock = JSON.parse(readFileSync(join(root, "package-lock.json"), "utf8"));
const locked = new Map();
for (const [key, entry] of Object.entries(lock.packages)) {
  if (key === "" || entry.dev) continue;
  const name = key.slice(key.lastIndexOf("node_modules/") + "node_modules/".length);
  const directory = join(root, key);
  if (existsSync(directory)) locked.set(`${name}@${entry.version}`, directory);
}

const packages = new Map();
const unlocked = [];
const visit = (dependencies) => {
  for (const [name, entry] of Object.entries(dependencies ?? {})) {
    // An unmet optional peer dependency (zustand's `immer`, unused by @xyflow/react) is listed
    // by `npm ls --all` as a pathless stub: nothing is installed there, so nothing is bundled.
    if (entry.path === undefined) continue;
    const key = `${name}@${entry.version}`;
    if (locked.has(key)) packages.set(key, { name, version: entry.version, path: locked.get(key) });
    else unlocked.push(key);
    // `npm ls` prints a package's dependencies once, below the first entry it meets, and shows
    // the later entries for the same package without them: every entry is visited, whether or
    // not its key is known, and the map keeps each package once for the output.
    visit(entry.dependencies);
  }
};
visit(tree.dependencies);

// The tree is the walk's source, and the lock file is what it is checked against: a production
// package that is installed and not listed would ship without its notice and skip the gate.
const missing = [...locked.keys()].filter((key) => !packages.has(key));
if (missing.length > 0 || unlocked.length > 0) {
  console.error("the walk of `npm ls` disagrees with package-lock.json:");
  for (const key of missing)
    console.error(`  not listed, a production package of the lock file: ${key}`);
  for (const key of unlocked) console.error(`  not in the lock file: ${key}`);
  process.exit(1);
}

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
