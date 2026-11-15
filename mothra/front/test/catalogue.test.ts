// Task 5.5: the catalogue of the components, `npm run catalogue -- <file>` (mothra-demo-habillage D17, R-20261031-77). Temporary folders are
// made by the tests. Lot 3a holds the components of the shell, the home and the empty state; the sheet pages computed by the contract come
// with lot 3b (task 6.0).
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, readdirSync, readFileSync, realpathSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import type { Jetons } from "../scripts/generer-jetons.ts";
import { ecrireCatalogue, genererCatalogue, RefusSortie } from "../scripts/catalogue.ts";
import { ETATS_BADGE } from "../src/composants/BadgeVerdict.ts";
import { catalogues } from "../src/i18n/langue.ts";
import { CAS_H1 } from "./fiches-h1.ts";

const FRONT = new URL("..", import.meta.url).pathname;
const SCRIPT = `${FRONT}scripts/catalogue.ts`;
const SOURCE = JSON.parse(readFileSync(`${FRONT}src/styles/tokens.json`, "utf8")) as Jetons;
const PAGE = genererCatalogue(SOURCE, "");

function dossierTemporaire(): string {
  return mkdtempSync(join(tmpdir(), "catalogue-"));
}

test("the page holds every state of the verdict badge, the banners, the card, the empty state and the three templates", () => {
  for (const etat of ETATS_BADGE) assert.ok(PAGE.includes(`data-etat="${etat}"`), `état absent : ${etat}`);
  for (const titre of ["Template: shell", "Template: sheet page", "Template: indicators page", "Explained empty state", "Side navigation", "Banner", "Conviction card", "Masked cell"]) {
    assert.ok(PAGE.includes(titre), titre);
  }
  assert.ok(PAGE.includes('data-jeu="synthetic"') && PAGE.includes('data-jeu="real"'));
  assert.ok(PAGE.includes('class="etat-vide"') && PAGE.includes('class="nav-laterale"') && PAGE.includes('class="carte-conviction"'));
});

test("the page shows the colour swatches of the former page pastilles", () => {
  for (const nom of ["state-insufficient", "verdict-confirmed", "series-lead", "data-wait"]) assert.ok(PAGE.includes(nom), nom);
  assert.ok(PAGE.includes("Colour swatches"));
});

// Every image of the page is the shipped logo embedded as a `data:` address: nothing else, so the check below can strip exactly those images
// and scan everything left. The embedded bytes are decoded and compared with the file of public/logos/, so that the logo is verified, not skipped.
const IMAGE_INTEGREE = /<img\b[^>]*\bsrc="data:image\/svg\+xml;base64,([A-Za-z0-9+/=]+)"[^>]*>/g;

// public/logos/ is excluded from the public edition: this case skips when the file is absent (R-20261114-107; the static test of tests/build_edition guards the skip).
const FICHIER_LOGO = `${FRONT}public/logos/mothra-logo-clair.svg`;
const SKIP_SANS_LOGO = existsSync(FICHIER_LOGO) ? false : "public/logos/mothra-logo-clair.svg absent (excluded from the public edition)";

test("the page embeds the shipped light logo, byte for byte, and no other image", { skip: SKIP_SANS_LOGO }, () => {
  const images = PAGE.match(/<img\b[^>]*>/g) ?? [];
  assert.ok(images.length > 0, "aucune image : le logo de la colonne latérale manque");
  const integrees = [...PAGE.matchAll(IMAGE_INTEGREE)];
  assert.equal(integrees.length, images.length, "une image n'est pas le logo intégré");
  const fichier = readFileSync(FICHIER_LOGO);
  for (const [, base64] of integrees) assert.deepEqual(Buffer.from(base64, "base64"), fichier);
  // The French specimens carry the French name: each image has the accessible name of one of the two catalogues, never none.
  const noms = [catalogues.en["logo.mothra.alt"], catalogues.fr["logo.mothra.alt"]];
  assert.ok(images.every((i) => noms.some((nom) => i.includes(`alt="${nom}"`))), "nom accessible du logo");
});

test("the page is self-contained: no external resource, no script, no font file", () => {
  const sansLogo = PAGE.replace(IMAGE_INTEGREE, "");
  assert.doesNotMatch(sansLogo, /<img\b/i);
  for (const motif of [/https?:/i, /\bsrc\s*=/i, /\bhref\s*=\s*"http/i, /url\(/i, /@import/i, /@font-face/i, /<link\b/i, /<script\b/i, /<iframe\b/i]) {
    assert.doesNotMatch(sansLogo, motif);
  }
  // The font variables name system stacks only: no Plex file is loaded by the page, as the swatch page does.
  assert.match(PAGE, /--font-family:-apple-system,system-ui,sans-serif/);
});

test("the navigation, the card and the empty state are shown in each state, in both languages", () => {
  for (const titre of [
    "home current",
    "conviction current",
    "dashboard current",
    "without a dashboard entry (source not given)",
    "without a conviction served",
    "home current (French)",
    "dashboard current (French)",
    "card 1 en",
    "card 1 fr",
    "with an action (French)",
    "without an action (French)",
  ]) {
    assert.ok(PAGE.includes(`<figcaption>${titre}</figcaption>`), `spécimen absent : ${titre}`);
  }
  // Neither French text holds a character that the renderer escapes, so the page holds them as they are written in the catalogue.
  assert.ok(PAGE.includes(catalogues.fr["tableau.form.teamRequired"]), "état vide en français");
  assert.ok(PAGE.includes(catalogues.fr["conviction.statement.lead_cycle_h1"]), "carte en français");
  assert.ok(PAGE.includes(catalogues.fr["nav.home"]), "navigation en français");
});

test("the page is written atomically to the given path, nothing else is left in the folder", () => {
  const dossier = dossierTemporaire();
  try {
    const cible = ecrireCatalogue(join(dossier, "c.html"), SOURCE, "", undefined);
    assert.equal(readFileSync(cible, "utf8"), PAGE);
    assert.deepEqual(readdirSync(dossier), ["c.html"]);
  } finally {
    rmSync(dossier, { recursive: true, force: true });
  }
});

test("a path inside a given root, or no path, is refused with the message of the script", () => {
  const dossier = dossierTemporaire();
  try {
    assert.throws(() => ecrireCatalogue(join(dossier, "c.html"), SOURCE, "", realpathSync(dossier)), RefusSortie);
    assert.throws(() => ecrireCatalogue(undefined, SOURCE, "", dossier), /chemin de sortie obligatoire : npm run catalogue -- <fichier\.html>/);
    assert.equal(existsSync(join(dossier, "c.html")), false);
  } finally {
    rmSync(dossier, { recursive: true, force: true });
  }
});

test("the script run without a path refuses and writes nothing; with a path outside the repository it writes the page", () => {
  const sans = spawnSync(process.execPath, [SCRIPT], { encoding: "utf8" });
  assert.notEqual(sans.status, 0);
  assert.match(sans.stderr, /chemin de sortie obligatoire : npm run catalogue -- <fichier\.html>/);
  const dossier = dossierTemporaire();
  try {
    const avec = spawnSync(process.execPath, [SCRIPT, join(dossier, "c.html")], { encoding: "utf8" });
    assert.equal(avec.status, 0, avec.stderr);
    assert.ok(readFileSync(join(dossier, "c.html"), "utf8").includes("Mothra component catalogue"));
  } finally {
    rmSync(dossier, { recursive: true, force: true });
  }
});

// Lot 3b, phase A (task 6.0): the sheet status, the competing explanations and the sheet pages computed by the contract (R-20261101-07), the
// published sheet in its reduced form among them. The parts bar comes with the bars of lot 1b (phase B).
test("the page holds the sheet status and the competing explanations in each of their states", () => {
  for (const titre of ["Sheet status", "Competing explanations"]) assert.ok(PAGE.includes(titre), titre);
  for (const etat of ["draft", "reviewed", "published"]) assert.ok(PAGE.includes(`data-etat-fiche="${etat}"`), `statut absent : ${etat}`);
  for (const etat of ["ruled_out", "not_ruled_out", "not_measurable"]) assert.ok(PAGE.includes(`data-etat-explication="${etat}"`), `explication absente : ${etat}`);
  for (const signal of ["shown", "not_raised", "masked"]) assert.ok(PAGE.includes(`data-signal="${signal}"`), `signal absent : ${signal}`);
  // The fallbacks of an unknown name, state and reason are drawn with their sentences, never with the raw code.
  assert.ok(PAGE.includes(catalogues.en["fiche.explanation.unknown"]) && PAGE.includes(catalogues.en["fiche.reason.unknown"]));
  assert.ok(!PAGE.includes("unknown_reason"), "le code brut d'un motif inconnu n'est pas affiché");
  for (const titre of ["status draft en", "status published with date, version and frozen statement fr", "explanations: attachment signal masked"]) {
    assert.ok(PAGE.includes(`<figcaption>${titre}</figcaption>`), `spécimen absent : ${titre}`);
  }
});

test("the page holds the sheet pages computed by the contract: every display state on the complete and the reduced answer, and the published reduced sheet", () => {
  assert.ok(PAGE.includes("Sheet pages computed by the contract (hypothesis 1)"));
  for (const cas of CAS_H1) {
    for (const forme of ["synthetic dataset", "real data, reduced form"]) assert.ok(PAGE.includes(`<figcaption>sheet page ${cas}, ${forme}</figcaption>`), `page de fiche absente : ${cas}, ${forme}`);
  }
  for (const titre of ["sheet page confirmed, published, real data, reduced form (French)", "sheet page draft without effect nor cause", "sheet page confirmed, real data, method face open"]) {
    assert.ok(PAGE.includes(`<figcaption>${titre}</figcaption>`), `spécimen absent : ${titre}`);
  }
  // The pages are the component's rendering of contract answers: the published statement, the ratios as text, the open method face.
  assert.ok(PAGE.includes('class="gabarit-fiche"') && PAGE.includes('data-rapport="median"') && PAGE.includes("fiche-methode"));
  // The published sheet is one pill with a lock (R-20261101-126, Q3 (a)): the line of the catalogue, the date in its long form.
  assert.ok(PAGE.includes(catalogues.en["fiche.status.publishedLine"].replace("{date}", "November 2, 2026").replace("{number}", "1")));
  assert.ok(PAGE.includes(catalogues.fr["fiche.status.publishedLine"].replace("{date}", "2 novembre 2026").replace("{number}", "1")));
  assert.ok(PAGE.includes('class="statut-fiche statut-publiee"') && PAGE.includes('data-icone="lock"'));
  // No count and no name of the invented team leaks into the page.
  assert.doesNotMatch(PAGE, /Equipe Temoin Zeta/);
});

// Lot 3b, phase B (task 6.0): the parts bar with threshold markers in every state, the composition by quarter, and the sheet pages that draw them.
test("the page holds the parts bar in every state, in both languages, and the composition by quarter", () => {
  assert.ok(PAGE.includes("Parts bar with threshold markers"));
  for (const etat of ["value", "masked", "insufficient_sample", "not_comparable"]) {
    assert.ok(PAGE.includes(`data-forme="barre" data-barre="median" data-etat="${etat}"`), `barre absente : ${etat}`);
    assert.ok(PAGE.includes(`data-forme="ligne" data-etat="${etat}"`), `ligne absente : ${etat}`);
  }
  for (const titre of [
    "bar with values, markers applicable",
    "bar with values, markers not applicable",
    "bar with values, a marker out of scale",
    "bar masked",
    "bar insufficient sample, dotted markers",
    "bar not comparable",
    "bar with values (French)",
    "row of the chart without markers",
    "composition by quarter, on the common axis",
    "composition by quarter, with a masked, an insufficient and a not comparable quarter",
  ]) {
    assert.ok(PAGE.includes(`<figcaption>${titre}</figcaption>`), `spécimen absent : ${titre}`);
  }
  assert.ok(PAGE.includes('class="repere-trait repere-pointille"') && PAGE.includes('class="bande-masquee"') && PAGE.includes('class="bande-insuffisante"'));
  assert.ok(PAGE.includes('class="cache-visuel"') && PAGE.includes(catalogues.fr["conviction.chart.title"]));
  // The sheet pages draw their bars from the contract's `waitShares`: the complete form its chart too, the reduced form its bars alone.
  assert.ok(PAGE.includes('data-barre="p85"') && PAGE.includes('class="composition-ligne"'));
  assert.ok(PAGE.includes("<figcaption>sheet page confirmed, real data, without waitShares (fallback of D4)</figcaption>"));
});

test("the script holds no hexadecimal colour literal", () => {
  assert.deepEqual(readFileSync(SCRIPT, "utf8").match(/#[0-9a-fA-F]{3,8}\b/g), null);
});
