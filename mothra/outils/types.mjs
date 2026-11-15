// Type check of Mothra: `tsc --noEmit` on each project, every output line prefixed "types : " so a failure reads as a type failure.
// Without argument, the five projects of Mothra; with arguments, those project folders (used by the test of this script). Exit code 1 on any error.
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const PREFIXE = "types : ";
const racine = process.env.MOTHRA_TYPES_RACINE ?? resolve(dirname(fileURLToPath(import.meta.url)), "..");
const tsc = resolve(racine, "node_modules/typescript/bin/tsc");
const projets = process.argv.length > 2 ? process.argv.slice(2) : ["contract", "server", "front", "front/test", "test"].map((p) => resolve(racine, p));

if (!existsSync(tsc)) {
  console.log(`${PREFIXE}typescript absent, lancer npm ci`);
  process.exit(1);
}

let echecs = 0;
for (const projet of projets) {
  const resultat = spawnSync(process.execPath, [tsc, "--noEmit", "-p", projet], { encoding: "utf8" });
  const texte = `${resultat.stdout ?? ""}${resultat.stderr ?? ""}`.trimEnd();
  if (texte !== "") {
    for (const ligne of texte.split("\n")) console.log(`${PREFIXE}${ligne}`);
  }
  if (resultat.status !== 0) {
    echecs += 1;
    console.log(`${PREFIXE}ECHEC : ${projet}`);
  }
}
if (echecs === 0) console.log(`${PREFIXE}${projets.length} projet(s), aucune erreur de types`);
process.exit(echecs === 0 ? 0 : 1);
