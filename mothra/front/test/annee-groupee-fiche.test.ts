// R-20261114-49, design D7 and D8: the label of the grouped row and the note of hypothesis 1 of a SHEET are chosen by the window limit code the sheet
// carries, never by the data. A sheet frozen before the change (`views_last_four_quarters`) keeps « Pooled year » and its former note (the tests of the frozen
// sheets are untouched: habillage-fiche-h1.test.ts, reserve-rapide-1.test.ts); a new sheet (`views_last_three_closed_quarters`) shows « Last three quarters »;
// a sheet that carries neither code, or both, is a caller error: the mention `tableau.panel.mentionMissing` and no grouped row, never a guessed label.
import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";

import type { ReponseFiche } from "../src/api/fiche.ts";
import { clesAnneeGroupee } from "../src/composants/annee-groupee.ts";
import { FicheConviction } from "../src/composants/FicheConviction.ts";
import { catalogues } from "../src/i18n/langue.ts";
import { ficheH1 } from "./fiches-h1.ts";
import { rendre, texte as texteBrut } from "./rendu.ts";

// The text of a page with the escaped apostrophes of the markup read back (the French note holds one).
const texte = (html: string): string => texteBrut(html).replaceAll("&#x27;", "'");

const en = catalogues.en;
const fr = catalogues.fr;

function page(f: ReponseFiche, langue: "en" | "fr" = "en"): string {
  return rendre(h(FicheConviction, { fiche: f, seuilMasquage: 5 }), langue);
}

function avecLimites(f: ReponseFiche, limites: string[]): ReponseFiche {
  return { ...f, method: { ...f.method, limits: limites } } as unknown as ReponseFiche;
}

test("a new sheet shows « Last three quarters » and its note, in both languages, and never the former label", () => {
  const nouvelle = ficheH1("confirmed", { limite: "neuve" });
  assert.ok(nouvelle.method.limits.includes("views_last_three_closed_quarters"));
  assert.ok(!nouvelle.method.limits.includes("views_last_four_quarters"));
  for (const [langue, c] of [["en", en], ["fr", fr]] as const) {
    const html = page(nouvelle, langue);
    assert.ok(texte(html).includes(c["tableau.quarter.lastThreeQuarters"]), langue);
    assert.match(html, /data-note="last-three-quarters"/);
    assert.ok(texte(html).includes(c["conviction.lastThreeQuartersNote"]), langue);
    assert.ok(!texte(html).includes(c["tableau.quarter.pooledYear"]), langue);
    assert.doesNotMatch(html, /data-note="pooled-year"/);
    assert.ok(texte(html).includes(c["conviction.figure.wait"].replace("{period}", c["tableau.quarter.lastThreeQuarters"])), langue);
  }
});

test("a frozen sheet keeps its former label and its former note, next to the new sheet above", () => {
  const figee = ficheH1("confirmed", { limite: "figee" });
  assert.ok(figee.method.limits.includes("views_last_four_quarters"));
  const html = page(figee);
  assert.ok(texte(html).includes(en["tableau.quarter.pooledYear"]));
  assert.match(html, /data-note="pooled-year"/);
  assert.ok(texte(html).includes(en["conviction.pooledYearNote"]));
  assert.ok(!texte(html).includes(en["tableau.quarter.lastThreeQuarters"]));
});

test("a sheet with neither window limit code, or with both, shows the missing mention and no grouped row, never a guessed label", () => {
  const base = ficheH1("confirmed", { limite: "neuve" });
  const sans = base.method.limits.filter((l) => l !== "views_last_three_closed_quarters");
  for (const limites of [sans, [...sans, "views_last_four_quarters", "views_last_three_closed_quarters"]]) {
    const html = page(avecLimites(base, limites));
    assert.match(html, /role="alert"/);
    assert.ok(texte(html).includes(en["tableau.panel.mentionMissing"]));
    assert.ok(!texte(html).includes(en["tableau.quarter.lastThreeQuarters"]));
    assert.ok(!texte(html).includes(en["tableau.quarter.pooledYear"]));
    assert.doesNotMatch(html, /data-note="(pooled-year|last-three-quarters)"/);
  }
});

test("the choice is a pure function of the codes: former, new, none, both", () => {
  assert.equal(clesAnneeGroupee(["views_last_four_quarters"])?.libelle, "tableau.quarter.pooledYear");
  assert.equal(clesAnneeGroupee(["views_last_three_closed_quarters"])?.libelle, "tableau.quarter.lastThreeQuarters");
  assert.equal(clesAnneeGroupee([]), null);
  assert.equal(clesAnneeGroupee(["views_last_four_quarters", "views_last_three_closed_quarters"]), null);
});

test("the catalogue texts of the window are those of the design, in both languages", () => {
  assert.equal(en["conviction.lastThreeQuartersNote"], "The last three quarters leave out the items created more than one year before their commitment.");
  assert.equal(fr["conviction.lastThreeQuartersNote"], "3 derniers trimestres, sans les éléments créés plus d'un an avant leur engagement.");
  assert.equal(en["fiche.limit.views_last_three_closed_quarters"], "the views cover the last three closed quarters only");
  assert.equal(fr["fiche.limit.views_last_three_closed_quarters"], "les vues ne couvrent que les trois derniers trimestres clos");
  assert.equal(en["error.RANGE_INVALID"], "This range is not valid: choose whole closed quarters, among the last three.");
  assert.equal(fr["error.RANGE_INVALID"], "Cette plage n'est pas valide : choisissez des trimestres clos entiers, parmi les trois derniers.");
  assert.equal("tableau.flag.first_quarter_truncated" in en, false);
  assert.equal("tableau.flag.first_quarter_truncated" in fr, false);
});
