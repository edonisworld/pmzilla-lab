// Visual check page of the state, verdict and series colours (control 24.6, colour filters of the system).
// Run by the npm script `pastilles` of the front package: `npm run pastilles -- <output file>`. The page is written outside the
// bundle and outside the repository; a path inside the repository is refused. Values are resolved from tokens.json (palette
// references followed), never copied here. No package, no network, no external resource in the page.
import { existsSync, readFileSync, realpathSync, renameSync, writeFileSync } from "node:fs";
import { basename, dirname, join, resolve } from "node:path";

import { valeurJeton } from "./generer-jetons.ts";
import type { Jetons } from "./generer-jetons.ts";
import { dansLe, racineGit } from "./sortie.ts";

export interface Couleur {
  nom: string;
  valeur: string;
}

// "data-" holds the bar colours renamed by role from "series-" (decision 13, R-20261031-77, R-20261031-78): they stay on the colour filter page.
const PREFIXES = ["state-", "verdict-", "series-", "data-"];
const NOMS_EXACTS = ["info"];

export function couleursControlees(source: Jetons): Couleur[] {
  return Object.keys(source.light)
    .filter((nom) => NOMS_EXACTS.includes(nom) || PREFIXES.some((p) => nom.startsWith(p)))
    .map((nom) => {
      const valeur = valeurJeton(source, nom);
      if (valeur === undefined) throw new Error(`jeton sans valeur : ${nom}`);
      return { nom, valeur };
    });
}

// Background tints: shown in their own section with the ordinary ink on them, not as coloured text.
export function estFond(nom: string): boolean {
  return nom.endsWith("-tint") || nom.endsWith("-bg");
}

function echapper(texte: string): string {
  return texte.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function jeton(source: Jetons, nom: string): string {
  const valeur = valeurJeton(source, nom);
  if (valeur === undefined) throw new Error(`jeton sans valeur : ${nom}`);
  return valeur;
}

export function genererPage(source: Jetons): string {
  const fond = jeton(source, "bg");
  const surface = jeton(source, "surface");
  const encre = jeton(source, "text");
  const bordure = jeton(source, "border");
  const couleurs = couleursControlees(source);

  const aplats = couleurs
    .map(
      (c) =>
        `<div class="sw"><div class="c" style="background:${c.valeur}"></div><div class="l">${echapper(c.nom)}<br>${c.valeur}</div></div>`,
    )
    .join("\n");
  const pastilles = couleurs
    .map(
      (c) =>
        `<span class="chip" style="border:2px solid ${c.valeur}"><span class="dot" style="background:${c.valeur}"></span>${echapper(c.nom)} ${c.valeur}</span>`,
    )
    .join("\n");
  const textes = couleurs
    .filter((c) => !estFond(c.nom))
    .map((c) => `<span style="color:${c.valeur}">${echapper(c.nom)} ${c.valeur}</span>`)
    .join(" · \n");
  const fonds = couleurs
    .filter((c) => estFond(c.nom))
    .map((c) => `<div class="fond" style="background:${c.valeur}">Texte ordinaire (encre) sur ${echapper(c.nom)} ${c.valeur}</div>`)
    .join("\n");

  return `<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Couleurs d'état et de verdict</title>
<style>
body{margin:0;background:${fond};color:${encre};font-family:-apple-system,system-ui,sans-serif;padding:24px}
h1{font-size:20px;font-weight:600;margin:0 0 4px}
h2{font-size:16px;font-weight:600;margin:24px 0 4px}
p{margin:0 0 20px;font-size:14px}
.row{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:28px}
.sw{width:150px;border-radius:8px;overflow:hidden;background:${surface};border:1px solid ${bordure}}
.c{height:90px}
.l{padding:8px 10px;font-size:13px}
.chips{display:flex;flex-wrap:nowrap;overflow-x:auto;gap:8px;padding-bottom:8px}
.chip{display:inline-flex;align-items:center;gap:8px;padding:6px 12px;border-radius:999px;font-size:14px;white-space:nowrap;background:${surface}}
.dot{width:14px;height:14px;border-radius:50%}
.texte{font-size:15px;line-height:1.9}
.fond{padding:12px 16px;border-radius:8px;margin-bottom:8px;font-size:15px;border:1px solid ${bordure}}
</style></head><body>
<h1>Couleurs d'état et de verdict (24.6)</h1>
<p>Ouvre cette page, puis active tour à tour les filtres de couleur de macOS (protanopie, deutéranopie, tritanopie). Les couleurs de verdict, d'état et de séries doivent rester distinguables entre elles. Valeurs lues dans tokens.json.</p>
<h2>Aplats</h2>
<div class="row">
${aplats}
</div>
<h2>Pastilles côte à côte</h2>
<p>Toutes les couleurs sur une même rangée, pour les comparer sous filtre.</p>
<div class="chips">
${pastilles}
</div>
<h2>Texte coloré</h2>
<p>Chaque couleur en texte, précédée du texte ordinaire (encre : ${encre}).</p>
<div class="texte">
<span>Texte ordinaire (encre) ${encre}</span> ·
${textes}
</div>
<h2>Fonds</h2>
<p>Les teintes de fond, avec du texte à l'encre ordinaire dessus, comme dans l'interface.</p>
<div class="fonds">
${fonds}
</div>
</body></html>
`;
}

export class RefusSortie extends Error {}

// The root of the repository and the "inside a folder" test are shared with the catalogue script (`sortie.ts`); still exported from here.
export { dansLe, racineGit };

// Writes the page to `sortie`, atomically (temporary file then rename). Refuses without a path, or inside the repository.
export function ecrirePage(sortie: string | undefined, source: Jetons, racine: string | undefined): string {
  if (sortie === undefined || sortie.trim() === "") throw new RefusSortie("chemin de sortie obligatoire : npm run pastilles -- <fichier.html>");
  const absolu = resolve(sortie);
  const parent = dirname(absolu);
  if (!existsSync(parent)) throw new RefusSortie(`dossier de sortie introuvable : ${parent}`);
  const cible = join(realpathSync(parent), basename(absolu));
  if (racine !== undefined && dansLe(racine, cible)) throw new RefusSortie(`sortie refusée, le chemin est dans le dépôt : ${cible}`);
  const page = genererPage(source);
  const temporaire = `${cible}.tmp-${process.pid}`;
  writeFileSync(temporaire, page);
  renameSync(temporaire, cible);
  return cible;
}

if (import.meta.main) {
  const source = JSON.parse(readFileSync(new URL("../src/styles/tokens.json", import.meta.url), "utf8")) as Jetons;
  try {
    const cible = ecrirePage(process.argv[2], source, racineGit(new URL(".", import.meta.url).pathname));
    console.log(`page écrite : ${cible}`);
  } catch (e) {
    if (!(e instanceof RefusSortie)) throw e;
    console.error(e.message);
    process.exitCode = 2;
  }
}
