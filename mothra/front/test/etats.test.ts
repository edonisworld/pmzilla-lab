// Tasks 24.4 and 24.5: state and verdict colours are distinct from the brand amber and never alone; they do not judge (design D32).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import type { Jetons } from "../scripts/generer-jetons.ts";
import { catalogues as vrais } from "../src/i18n/langue.ts";
import { controlerEtats } from "./jetons.ts";
import type { Catalogues } from "./jetons.ts";

const FRONT = new URL("..", import.meta.url).pathname;

const CATALOGUES: Catalogues = {
  en: { "verdict.a": "settled", "verdict.b": "other", "state.err": "error" },
  fr: { "verdict.a": "tranchée", "verdict.b": "autre", "state.err": "erreur" },
};

function source(light: Record<string, string>, states: Jetons["states"]): Jetons {
  return {
    raw: { amber: "#D98A1C", gold: "#F2B630", dot: "#FBE3A0" },
    derived: { "amber-strong": "#9A5B0B" },
    light,
    scale: {},
    pairs: [],
    states,
  };
}

const ETAT = (label: string) => ({ label, icon: "check", outline: "solid" });

test("a clean set of verdicts and one error passes", () => {
  const s = source(
    { "verdict-a": "#0E6E63", "verdict-b": "#5B3FA0", "state-error": "#B42318" },
    { "verdict-a": ETAT("verdict.a"), "verdict-b": ETAT("verdict.b"), "state-error": ETAT("state.err") },
  );
  assert.deepEqual(controlerEtats(s, CATALOGUES), []);
});

test("a state or verdict token valued in the amber and gold family fails, through a name or a value", () => {
  for (const [nom, valeur] of [["amber", "amber"], ["gold", "gold"], ["amber-strong", "amber-strong"], ["dot", "dot"], ["hex", "#D98A1C"]]) {
    const s = source({ "verdict-a": valeur }, { "verdict-a": ETAT("verdict.a") });
    assert.deepEqual(controlerEtats(s, CATALOGUES), ["couleur d'état prise à l'ambre ou à l'or : verdict-a"], nom);
  }
  const erreur = source({ "state-error": "gold" }, { "state-error": ETAT("state.err") });
  assert.deepEqual(controlerEtats(erreur, CATALOGUES), ["couleur d'état prise à l'ambre ou à l'or : state-error"]);
});

test("two verdict tokens, or a verdict token and state-error, with the same value fail", () => {
  const deux = source({ "verdict-a": "#0E6E63", "verdict-b": "verdict-a" }, { "verdict-a": ETAT("verdict.a"), "verdict-b": ETAT("verdict.b") });
  assert.deepEqual(controlerEtats(deux, CATALOGUES), ["couleurs confondues : verdict-a et verdict-b"]);
  const erreur = source({ "verdict-a": "#B42318", "state-error": "#B42318" }, { "verdict-a": ETAT("verdict.a"), "state-error": ETAT("state.err") });
  assert.deepEqual(controlerEtats(erreur, CATALOGUES), ["couleurs confondues : verdict-a et state-error"]);
});

test("an entry without its label key, its icon or its pattern fails and names what is missing", () => {
  const sansIcone = source({ "verdict-a": "#0E6E63" }, { "verdict-a": { label: "verdict.a", icon: "", outline: "solid" } });
  assert.deepEqual(controlerEtats(sansIcone, CATALOGUES), ["couleur seule : verdict-a (manque : icône)"]);
  const sansMotif = source({ "verdict-a": "#0E6E63" }, { "verdict-a": { label: "verdict.a", icon: "check" } as never });
  assert.deepEqual(controlerEtats(sansMotif, CATALOGUES), ["couleur seule : verdict-a (manque : motif)"]);
  const sansLibelle = source({ "verdict-a": "#0E6E63" }, { "verdict-a": { label: "verdict.absent", icon: "check", outline: "solid" } });
  assert.deepEqual(controlerEtats(sansLibelle, CATALOGUES), ["couleur seule : verdict-a (manque : libellé)"]);
  const absentDuFrancais = { en: CATALOGUES.en, fr: { ...CATALOGUES.fr, "verdict.a": undefined as never } };
  delete (absentDuFrancais.fr as Record<string, string>)["verdict.a"];
  const s = source({ "verdict-a": "#0E6E63" }, { "verdict-a": ETAT("verdict.a") });
  assert.deepEqual(controlerEtats(s, absentDuFrancais), ["couleur seule : verdict-a (manque : libellé)"]);
});

test("a verdict token name or catalogue label holding a judgement word fails", () => {
  const nom = source({ "verdict-favourable": "#0E6E63" }, { "verdict-favourable": ETAT("verdict.a") });
  assert.deepEqual(controlerEtats(nom, CATALOGUES), ["verdict jugé : verdict-favourable"]);
  for (const mot of ["favourable", "Unfavourable", "favorable", "DÉFAVORABLE"]) {
    const libelle: Catalogues = { en: { ...CATALOGUES.en, "verdict.a": `${mot} reading` }, fr: { ...CATALOGUES.fr, "verdict.a": `lecture ${mot}` } };
    const s = source({ "verdict-a": "#0E6E63" }, { "verdict-a": ETAT("verdict.a") });
    assert.deepEqual(controlerEtats(s, libelle), ["verdict jugé : verdict.a"], mot);
  }
});

test("a colour token of a state or verdict without an entry in states fails, an entry without a colour token too", () => {
  const sansEntree = source({ "verdict-a": "#0E6E63", "state-extra": "#112233" }, { "verdict-a": ETAT("verdict.a") });
  assert.deepEqual(controlerEtats(sansEntree, CATALOGUES), ["couleur seule : state-extra (manque : libellé, icône, motif)"]);
  const sansCouleur = source({ "verdict-a": "#0E6E63" }, { "verdict-a": ETAT("verdict.a"), "state-ghost": ETAT("state.err") });
  assert.deepEqual(controlerEtats(sansCouleur, CATALOGUES), ["état sans jeton de couleur : state-ghost"]);
  // tints, backgrounds and borders are not states of their own
  const teintes = source(
    { "verdict-a": "#0E6E63", "verdict-a-tint": "#DDEFEA", "state-masked-bg": "#E4E6DF", "state-masked-border": "#5D6F65" },
    { "verdict-a": ETAT("verdict.a") },
  );
  assert.deepEqual(controlerEtats(teintes, CATALOGUES), []);
});

test("the amber check and the confusion check also cover the tints and the masked background", () => {
  const teinte = source({ "verdict-a": "#0E6E63", "verdict-a-tint": "gold" }, { "verdict-a": ETAT("verdict.a") });
  assert.deepEqual(controlerEtats(teinte, CATALOGUES), ["couleur d'état prise à l'ambre ou à l'or : verdict-a-tint"]);
  const fond = source({ "verdict-a": "#0E6E63", "state-masked-bg": "amber" }, { "verdict-a": ETAT("verdict.a") });
  assert.deepEqual(controlerEtats(fond, CATALOGUES), ["couleur d'état prise à l'ambre ou à l'or : state-masked-bg"]);
  const confondues = source(
    { "verdict-a": "#0E6E63", "verdict-a-tint": "#DDEFEA", "state-masked-bg": "#DDEFEA" },
    { "verdict-a": ETAT("verdict.a") },
  );
  assert.deepEqual(controlerEtats(confondues, CATALOGUES), ["couleurs confondues : verdict-a-tint et state-masked-bg"]);
});

// ---- the real source and catalogues ------------------------------------------------------------------------------------------

test("the real states and verdicts pass, with the labels of D29 in both catalogues", () => {
  const reel = JSON.parse(readFileSync(`${FRONT}src/styles/tokens.json`, "utf8")) as Jetons;
  assert.deepEqual(controlerEtats(reel, vrais), []);
  assert.deepEqual(
    [vrais.en["verdict.confirmed"], vrais.en["verdict.refuted"], vrais.en["verdict.not_settled"], vrais.en["state.insufficient_sample"]],
    ["confirmed", "refuted", "not settled", "insufficient sample"],
  );
  assert.deepEqual(
    [vrais.fr["verdict.confirmed"], vrais.fr["verdict.refuted"], vrais.fr["verdict.not_settled"], vrais.fr["state.insufficient_sample"]],
    ["confirmée", "réfutée", "non tranchée", "échantillon insuffisant"],
  );
  assert.equal(reel.light["verdict-refuted"], "#3B2470");
});
