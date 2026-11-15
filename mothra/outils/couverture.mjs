// Coverage floor of a Mothra package (task 17.2, decision F10): Node's built-in test coverage, no package added.
// Usage, from the package folder: node ../outils/couverture.mjs <package>. It runs the package's tests with the line and branch
// floors of `planchers-couverture.json` and fails under them, naming the package ("plancher de couverture non atteint : <package>").
// Exit codes: 0 = tests pass and floors reached; 1 = tests failing, floor not reached, or no test / no file measured;
// 2 = the run could not be set up (floors file unreadable, unknown package, launch impossible).
// A failing test takes precedence over the floor: "tests en échec : <package>" is printed first, the floor message follows if also missed.
// Environment, for the test of this script only (replaces: nothing; removal: permanent, serves the tests of this script):
//   MOTHRA_COUVERTURE_PLANCHERS (path of a floors file), MOTHRA_COUVERTURE_NODE (executable to launch, to test a launch failure).
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ici = dirname(fileURLToPath(import.meta.url));
// replaces: nothing; removal: permanent, serves the tests of this script
const chemin = process.env.MOTHRA_COUVERTURE_PLANCHERS ?? resolve(ici, "planchers-couverture.json");
// replaces: nothing; removal: permanent, serves the tests of this script
const executable = process.env.MOTHRA_COUVERTURE_NODE ?? process.execPath;
const paquet = process.argv[2];

let config;
try {
  config = JSON.parse(readFileSync(chemin, "utf8")).paquets?.[paquet];
} catch {
  console.log(`couverture : fichier des planchers illisible : ${chemin}`);
  process.exit(2);
}
if (config === undefined) {
  console.log(`couverture : paquet inconnu : ${paquet}`);
  process.exit(2);
}

// A provisional floor (not yet measured) is 0 and says so on every run, until the author's session replaces it.
const lignes = config.provisoire === true ? 0 : config.lignes;
const branches = config.provisoire === true ? 0 : config.branches;
if (config.provisoire === true) console.log(`couverture : plancher provisoire non mesuré : ${paquet}`);

// The spec reporter is fixed so that the analysed output does not depend on the TTY.
const arguments_ = ["--test", "--test-reporter=spec", "--experimental-test-coverage", `--test-coverage-lines=${lignes}`, `--test-coverage-branches=${branches}`];
for (const motif of config.include) arguments_.push(`--test-coverage-include=${motif}`);
if (config.concurrence !== undefined) arguments_.push(`--test-concurrency=${config.concurrence}`);
arguments_.push(...config.tests);

// A test run started from inside a test must not believe it is a subtest.
const env = { ...process.env };
delete env.NODE_TEST_CONTEXT;

const resultat = spawnSync(executable, arguments_, { encoding: "utf8", env, maxBuffer: 512 * 1024 * 1024 });
if (resultat.error !== undefined || resultat.status === null) {
  console.log(`couverture : lancement impossible (${resultat.error?.message ?? resultat.signal})`);
  process.exit(2);
}
const sortie = `${resultat.stdout ?? ""}${resultat.stderr ?? ""}`;
process.stdout.write(sortie);

const compteur = (nom) => {
  const m = sortie.match(new RegExp(`^(?:ℹ|#) ${nom} (\\d+)`, "m"));
  return m === null ? undefined : Number(m[1]);
};
const echecs = compteur("fail");
const total = compteur("tests");
// A measured file is a row of the coverage report with a number after its name, other than the "all files" total.
const fichiersMesures = /^(?:ℹ|#)\s+(?!all files)\S.*?\|\s*\d[\d.]*\s*\|/m.test(sortie);

if (echecs !== undefined && echecs > 0) {
  console.log(`couverture : tests en échec : ${paquet}`);
  if (/does not meet threshold/.test(sortie)) console.log(`couverture : plancher de couverture non atteint : ${paquet}`);
  process.exit(1);
}
if (total === undefined || total === 0 || !fichiersMesures) {
  console.log(`couverture : aucun test ou aucun fichier mesuré : ${paquet}`);
  process.exit(1);
}
if (resultat.status === 0) process.exit(0);
if (/does not meet threshold/.test(sortie)) console.log(`couverture : plancher de couverture non atteint : ${paquet}`);
else console.log(`couverture : tests en échec : ${paquet}`);
process.exit(1);
