// Task 7.2: the front catalogues (design D6, invariant 11): same keys in French and English, every user-visible text in the
// catalogues, the API codes translated by the front, the default language set in one place.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { genererCatalogue } from "../scripts/catalogue.ts";
import type { Jetons } from "../scripts/generer-jetons.ts";
import { CODES_ERREUR } from "../src/api/vue.ts";
import { catalogues, CLES_LANGUE, LANGUE_PAR_DEFAUT, LANGUES } from "../src/i18n/langue.ts";
import { CLES_ERREUR, cleErreur } from "../src/pages/PageSquelette.ts";
import { analyser, classesDeCss, ressembleATexte, sources, texteDuHtml, textesVisibles } from "./statique.ts";

const FRONT = new URL("..", import.meta.url).pathname;
const fr = catalogues.fr;
const en = catalogues.en;

function parametres(message: string): string[] {
  return [...message.matchAll(/\{\s*(\w+)/g)].map((m) => m[1]).sort();
}

test("the two catalogues hold the same keys, and the failure names the missing key", () => {
  const manquantes = [
    ...Object.keys(fr).filter((k) => !(k in en)).map((k) => `absente de en.json : ${k}`),
    ...Object.keys(en).filter((k) => !(k in fr)).map((k) => `absente de fr.json : ${k}`),
  ];
  assert.deepEqual(manquantes, []);
});

test("no message is empty and both catalogues use the same ICU parameters", () => {
  for (const cle of Object.keys(en)) {
    assert.ok(en[cle].trim() !== "", `message vide (en) : ${cle}`);
    assert.ok(fr[cle].trim() !== "", `message vide (fr) : ${cle}`);
    assert.deepEqual(parametres(fr[cle]), parametres(en[cle]), `paramètres différents : ${cle}`);
  }
});

test("the catalogue files are flat objects of strings", () => {
  for (const nom of ["fr", "en"]) {
    const contenu = JSON.parse(readFileSync(`${FRONT}src/i18n/${nom}.json`, "utf8"));
    for (const [cle, valeur] of Object.entries(contenu)) {
      assert.equal(typeof valeur, "string", `valeur non textuelle : ${nom}.json ${cle}`);
    }
  }
});

test("every column of every view of the contract has a column.<code> key in both catalogues", () => {
  const contrat = JSON.parse(readFileSync(new URL("../../../contrats/vues.json", import.meta.url), "utf8")) as {
    views: Array<{ name: string; countColumns: string[]; plainColumns: string[] }>;
  };
  assert.ok(contrat.views.length > 0);
  const manquantes: string[] = [];
  for (const vue of contrat.views) {
    for (const colonne of [...vue.plainColumns, ...vue.countColumns]) {
      for (const [nom, catalogue] of [["en.json", en], ["fr.json", fr]] as const) {
        if (!(`column.${colonne}` in catalogue)) manquantes.push(`${nom} : column.${colonne} (${vue.name})`);
      }
    }
  }
  assert.deepEqual(manquantes, []);
});

test("the states and the API error codes are translated in both languages", () => {
  assert.equal(en["cellState.masked"], "masked");
  assert.equal(fr["cellState.masked"], "masqué");
  assert.ok(en["cellState.value"] && fr["cellState.value"]);
  for (const code of CODES_ERREUR) {
    const cle = CLES_ERREUR[code];
    assert.ok(en[cle] && fr[cle], `code d'erreur sans traduction : ${code}`);
    assert.notEqual(en[cle], code);
    assert.notEqual(fr[cle], code);
  }
  assert.deepEqual(Object.keys(CLES_ERREUR).sort(), [...CODES_ERREUR].sort());
});

test("an unknown error code is shown as the internal error, never as a raw code", () => {
  assert.equal(cleErreur("NOT_A_CODE"), CLES_ERREUR.INTERNAL);
  assert.equal(cleErreur("UNKNOWN_VIEW"), "error.UNKNOWN_VIEW");
});

test("the default language is English and the only place that sets it is the languages module", () => {
  assert.equal(LANGUE_PAR_DEFAUT, "en");
  assert.deepEqual([...LANGUES].sort(), ["en", "fr"]);
  assert.deepEqual(Object.keys(CLES_LANGUE).sort(), ["en", "fr"]);
  const ailleurs = sources(FRONT, "src", [".ts", ".tsx"])
    .filter((s) => s.nom !== "src/i18n/langue.ts")
    .flatMap((s) => analyser(s.contenu).litteraux.filter((l) => l.texte === "en" || l.texte === "fr").map((l) => `${s.nom}:${l.ligne}`));
  assert.deepEqual(ailleurs, []);
});

test("every catalogue key used in the sources exists, and every catalogue key is used", () => {
  const prefixes = /^(app|logo|language|page|column|cellState|table|error|tableau|fiche|banner|nav|conviction|home)\./;
  const utilisees = new Set<string>();
  for (const s of sources(FRONT, "src", [".ts", ".tsx"])) {
    for (const l of analyser(s.contenu).litteraux) if (prefixes.test(l.texte)) utilisees.add(l.texte);
  }
  // The label keys of the states and verdicts are held by the token source (task 24.2), not by a component yet.
  const jetons = JSON.parse(readFileSync(`${FRONT}src/styles/tokens.json`, "utf8")) as { states: Record<string, { label: string }> };
  for (const etat of Object.values(jetons.states)) utilisees.add(etat.label);
  assert.deepEqual([...utilisees].filter((k) => !(k in en)).sort(), [], "clé utilisée et absente du catalogue");
  assert.deepEqual(Object.keys(en).filter((k) => !utilisees.has(k)).sort(), [], "clé du catalogue jamais utilisée");
});

test("the checker names the file and the line of a visible literal text", () => {
  assert.deepEqual(textesVisibles("a.ts", 'const a = 1;\nconst b = h("p", null, "Loading");'), ["a.ts:2"]);
  assert.deepEqual(textesVisibles("a.ts", 'h("p", null, "no rows here");'), ["a.ts:1"]);
  assert.deepEqual(textesVisibles("a.ts", 'h("p", null, "Chargement…");'), ["a.ts:1"]);
  assert.deepEqual(textesVisibles("a.ts", 'h("p", { title: "Close" });'), ["a.ts:1"]);
  assert.deepEqual(textesVisibles("a.ts", 'h("button", { "aria-label": "close" });'), ["a.ts:1"]);
});

test("in a .tsx file the checker sees the JSX text and the visible attributes, with file and line", () => {
  assert.deepEqual(textesVisibles("a.tsx", "const A = () => (\n  <p>Status by team</p>\n);"), ["a.tsx:2"]);
  assert.deepEqual(textesVisibles("a.tsx", 'const A = () => <button aria-label="close"/>;'), ["a.tsx:1"]);
  assert.deepEqual(textesVisibles("a.tsx", 'const A = () => (\n  <p>\n    {t("a")} and more\n  </p>\n);'), ["a.tsx:3"]);
  assert.deepEqual(textesVisibles("a.tsx", 'const A = () => <p>{t("cle")}</p>;'), []);
  assert.deepEqual(textesVisibles("a.tsx", 'const A = () => <p className="x" />;'), []);
  assert.deepEqual(textesVisibles("a.tsx", 'const A = () => <p title={t("cle")}>{t("a")}</p>;'), []);
});

test("codes, keys, paths, class names defined in the stylesheet and comments are not visible text", () => {
  const classes = new Set(["cellule", "cellule-vide"]);
  assert.equal(ressembleATexte("UNKNOWN_VIEW"), false);
  assert.equal(ressembleATexte("page.statusByTeam.title"), false);
  assert.equal(ressembleATexte("/api/views/${v}"), false);
  assert.equal(ressembleATexte("ErreurApi"), false);
  assert.equal(ressembleATexte("cellule cellule-vide", classes), false);
  assert.equal(ressembleATexte("cellule inconnue", classes), true);
  assert.deepEqual(textesVisibles("a.ts", "// Loading the view\n/* a sentence\nover lines */\nconst a = 1;"), []);
  assert.deepEqual(textesVisibles("a.ts", 'h("td", { className: "cellule cellule-vide", title: "" });', classes), []);
});

test("no source of the front holds a visible literal text", () => {
  const classes = classesDeCss(readFileSync(`${FRONT}src/styles/styles.css`, "utf8"));
  const trouves = sources(FRONT, "src", [".ts", ".tsx"]).flatMap((s) => textesVisibles(s.nom, s.contenu, classes));
  assert.deepEqual(trouves, []);
});

test("the generated catalogue page: the id attributes are unique and every aria-describedby points to an id of its own specimen", () => {
  const source = JSON.parse(readFileSync(`${FRONT}src/styles/tokens.json`, "utf8")) as Jetons;
  const page = genererCatalogue(source, "");
  const ids = [...page.matchAll(/\sid="([^"]*)"/g)].map((m) => m[1]);
  assert.ok(ids.length > 0);
  const doublons = ids.filter((id, rang) => ids.indexOf(id) !== rang);
  assert.deepEqual([...new Set(doublons)], [], "attribut id en double dans la page");
  const specimens = page.split('<figure class="specimen">').slice(1);
  let references = 0;
  for (const specimen of specimens) {
    const propres = new Set([...specimen.matchAll(/\sid="([^"]*)"/g)].map((m) => m[1]));
    for (const m of specimen.matchAll(/\saria-describedby="([^"]*)"/g)) {
      for (const cible of m[1].split(/\s+/).filter((c) => c !== "")) {
        references += 1;
        assert.ok(propres.has(cible), `aria-describedby vers un id absent du spécimen : ${cible}`);
      }
    }
  }
  assert.ok(references >= 2, "les spécimens du choix désactivé (en et fr) portent un aria-describedby");
});

test("the HTML page holds no text of its own: the title and the language are set from the catalogue", () => {
  const html = readFileSync(`${FRONT}index.html`, "utf8");
  assert.equal(texteDuHtml(html), "");
  assert.doesNotMatch(html, /\blang\s*=/);
});
