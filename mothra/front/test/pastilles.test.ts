// Visual check page of the colours (control 24.6): `npm run pastilles -- <file>`. Temporary folders are made by the tests.
import assert from "node:assert/strict";
import { existsSync, mkdtempSync, readdirSync, readFileSync, realpathSync, rmSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import type { Jetons } from "../scripts/generer-jetons.ts";
import { valeurJeton } from "../scripts/generer-jetons.ts";
import { couleursControlees, ecrirePage, estFond, genererPage, RefusSortie } from "../scripts/page-pastilles.ts";

const FRONT = new URL("..", import.meta.url).pathname;
const SCRIPT = `${FRONT}scripts/page-pastilles.ts`;
const SOURCE = JSON.parse(readFileSync(`${FRONT}src/styles/tokens.json`, "utf8")) as Jetons;

function dossierTemporaire(): string {
  return mkdtempSync(join(tmpdir(), "pastilles-"));
}

test("the page holds every state, verdict and series token with its resolved value, and the page colours", () => {
  const page = genererPage(SOURCE);
  const attendus = Object.keys(SOURCE.light).filter((n) => n === "info" || /^(state-|verdict-|series-|data-)/.test(n));
  assert.ok(attendus.includes("series-lead") && attendus.includes("series-cycle") && attendus.includes("info"));
  assert.ok(attendus.some((n) => n.startsWith("state-")) && attendus.some((n) => n.startsWith("verdict-")));
  assert.deepEqual(couleursControlees(SOURCE).map((c) => c.nom), attendus);
  for (const nom of attendus) {
    const valeur = valeurJeton(SOURCE, nom);
    assert.ok(valeur !== undefined && /^#[0-9A-F]{6}$/.test(valeur), nom);
    assert.ok(page.includes(nom), `jeton absent : ${nom}`);
    assert.ok(page.includes(`background:${valeur}`), `aplat absent : ${nom}`);
    if (!estFond(nom)) assert.ok(page.includes(`color:${valeur}`), `texte absent : ${nom}`);
    assert.ok(page.includes(`border:2px solid ${valeur}`), `pastille absente : ${nom}`);
  }
  // a reference followed: state-insufficient is written as the name of another token
  assert.equal(SOURCE.light["state-insufficient"], "ink-muted");
  assert.ok(page.includes(`state-insufficient ${valeurJeton(SOURCE, "ink-muted")}`));
  assert.ok(page.includes(`background:${valeurJeton(SOURCE, "bg")};color:${valeurJeton(SOURCE, "text")}`));
});

test("no tint in the coloured text section; each tint in the backgrounds section with the ordinary ink", () => {
  const page = genererPage(SOURCE);
  const section = (titre: string): string => {
    const debut = page.indexOf(`<h2>${titre}</h2>`);
    assert.notEqual(debut, -1, titre);
    const fin = page.indexOf("<h2>", debut + 1);
    return page.slice(debut, fin === -1 ? undefined : fin);
  };
  const texte = section("Texte coloré");
  const fonds = section("Fonds");
  const teintes = Object.keys(SOURCE.light).filter((n) => n.endsWith("-tint") || n === "state-masked-bg");
  assert.ok(teintes.length >= 3);
  for (const nom of teintes) {
    const valeur = valeurJeton(SOURCE, nom);
    assert.ok(estFond(nom), nom);
    assert.ok(!texte.includes(nom) && !texte.includes(valeur as string), `teinte dans le texte coloré : ${nom}`);
    const bloc = fonds.split("\n").find((l) => l.includes(`background:${valeur}`) && l.includes(nom));
    assert.ok(bloc !== undefined, `fond absent : ${nom}`);
    assert.ok(bloc.includes(`>Texte ordinaire (encre) sur ${nom} ${valeur}<`), nom);
    assert.ok(!bloc.includes("color:"), `encre ordinaire attendue : ${nom}`);
  }
  assert.doesNotMatch(fonds, /color:/);
  assert.match(page, new RegExp(`body\\{[^}]*;color:${valeurJeton(SOURCE, "text")};`));
});

test("the script holds no hexadecimal colour literal", () => {
  const texte = readFileSync(SCRIPT, "utf8");
  assert.deepEqual(texte.match(/#[0-9a-fA-F]{3,8}\b/g), null);
});

test("the page is self-contained: no external resource", () => {
  const page = genererPage(SOURCE);
  for (const motif of [/https?:/i, /\bsrc\s*=/i, /\bhref\s*=/i, /url\(/i, /@import/i, /<link\b/i, /<script\b/i, /<img\b/i, /<iframe\b/i]) {
    assert.doesNotMatch(page, motif);
  }
});

test("the page is written atomically to the given path, nothing else is left in the folder", () => {
  const dossier = dossierTemporaire();
  try {
    const cible = ecrirePage(join(dossier, "p.html"), SOURCE, undefined);
    assert.equal(readFileSync(cible, "utf8"), genererPage(SOURCE));
    assert.deepEqual(readdirSync(dossier), ["p.html"]);
  } finally {
    rmSync(dossier, { recursive: true, force: true });
  }
});

test("the script run without argument refuses and writes nothing", () => {
  const r = spawnSync(process.execPath, [SCRIPT], { encoding: "utf8" });
  assert.notEqual(r.status, 0);
  assert.match(r.stderr, /obligatoire/);
});

test("the script refuses a path inside the repository and writes nothing", () => {
  const cible = `${FRONT}pastilles-refus.html`;
  const r = spawnSync(process.execPath, [SCRIPT, cible], { encoding: "utf8" });
  assert.notEqual(r.status, 0);
  assert.match(r.stderr, /dépôt/);
  assert.equal(existsSync(cible), false);
});

test("a path inside a given root is refused, a path outside is accepted", () => {
  const dossier = dossierTemporaire();
  try {
    assert.throws(() => ecrirePage(join(dossier, "p.html"), SOURCE, realpathSync(dossier)), RefusSortie);
    assert.equal(existsSync(join(dossier, "p.html")), false);
    assert.throws(() => ecrirePage(undefined, SOURCE, dossier), RefusSortie);
    assert.throws(() => ecrirePage(join(dossier, "absent", "p.html"), SOURCE, undefined), RefusSortie);
  } finally {
    rmSync(dossier, { recursive: true, force: true });
  }
});

test("the script run with a path outside the repository writes the page", () => {
  const dossier = dossierTemporaire();
  try {
    const r = spawnSync(process.execPath, [SCRIPT, join(dossier, "p.html")], { encoding: "utf8" });
    assert.equal(r.status, 0, r.stderr);
    assert.ok(readFileSync(join(dossier, "p.html"), "utf8").includes("series-lead"));
  } finally {
    rmSync(dossier, { recursive: true, force: true });
  }
});
