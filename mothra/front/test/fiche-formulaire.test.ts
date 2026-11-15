// Task 19.3 (rest, review B4): the creation form with the management question, the effect and the cause with their language, the
// refusal TEXT_REFUSED through the catalogue, the completion of a draft by PATCH (author only, never on a reviewed or published
// sheet) and the labels of the refusals of D29. Nothing here calls the network.
import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";

import { QUESTIONS_DE_DIRECTION } from "@mothra/contract/listes-fiche";
import { identifiantEquipe, scopeFiche } from "@mothra/contract/equipe";

import { RefusFiche } from "../src/api/fiche.ts";
import type { RefusTexte, ResultatCompletion } from "../src/api/fiche.ts";
import { champsDeValeurs, RefusTexteFiche, valeursVides } from "../src/composants/ChampsFiche.ts";
import { envoyerCompletion, Fiche, lancerCompletion } from "../src/composants/Fiche.ts";
import { catalogues } from "../src/i18n/langue.ts";
import type { Langue } from "../src/i18n/langue.ts";
import { ContenuTableau, ouvrirBrouillon } from "../src/pages/PageTableau.ts";
import { cleErreur } from "../src/pages/PageSquelette.ts";
import { ficheSimulee } from "./fiche-simulee.ts";
import { rendre, texte as texteDuMarquage } from "./rendu.ts";

const en = catalogues.en;
const fr = catalogues.fr;

function texte(html: string): string {
  return texteDuMarquage(html).replaceAll("&#x27;", "'");
}

const DATE = "2026-10-27";
const reponse = {
  threshold: 5,
  dataDate: DATE,
  product: [],
  teams: [{ team: "Team A", teamId: identifiantEquipe("Team A"), points: [] }],
};

function formulaire(langue: Langue, fiche: Parameters<typeof ContenuTableau>[0]["fiche"] = { genre: "formulaire" }): string {
  return rendre(
    h(ContenuTableau, { reponse, portee: "Team A", surPortee: () => undefined, fiche, surFaire: () => undefined, surCreer: () => undefined, simulee: false }),
    langue,
  );
}

// ---- the creation form ---------------------------------------------------------------------------------------------------------

test("the form offers the four management questions through their labels, none chosen, in each language", () => {
  const anglais = formulaire("en");
  assert.equal([...anglais.matchAll(/<option value="(scope_growth|scope_reachability|predictability|next_version_quality)"/g)].length, 4);
  assert.deepEqual(
    QUESTIONS_DE_DIRECTION.map((q) => en[`fiche.question.${q}`]),
    ["Scope growth during a release", "Reachability of the release scope", "Predictability", "Quality of the next version"],
  );
  for (const q of QUESTIONS_DE_DIRECTION) {
    assert.match(texte(anglais), new RegExp(en[`fiche.question.${q}`]));
    assert.match(texte(formulaire("fr")), new RegExp(fr[`fiche.question.${q}`]));
    assert.doesNotMatch(anglais, new RegExp(`<option value="${q}"[^>]*selected`));
  }
  assert.doesNotMatch(texte(anglais), /scope_growth|next_version_quality/);
});

test("the form holds the effect and the cause, each with the choice of its language, defaulting to the language of the screen", () => {
  const anglais = formulaire("en");
  assert.equal((anglais.match(/<textarea/g) ?? []).length, 2);
  assert.equal((anglais.match(/<select[^>]*data-champ-langue/g) ?? []).length, 2);
  assert.match(anglais, /<option value="en" selected="">English<\/option>/);
  assert.match(formulaire("fr"), /<option value="fr" selected="">Français<\/option>/);
  assert.match(texte(anglais), /Effect/);
  assert.match(texte(formulaire("fr")), /Effet/);
  assert.match(texte(formulaire("fr")), /Cause/);
});

test("the three fields are optional: a draft is created without them, and with them when written", async () => {
  const demandes: unknown[] = [];
  const creer = async (demande: unknown) => {
    demandes.push(demande);
    return { id: "d-1", state: "draft" as const };
  };
  const scope = scopeFiche({ kind: "team", team: identifiantEquipe("Team A") });
  await ouvrirBrouillon(creer, "Team A", DATE, "lead_cycle_h5");
  assert.deepEqual(demandes.at(-1), { chart: "lead_cycle_h5", scope, dataDate: DATE });
  await ouvrirBrouillon(creer, "Team A", DATE, "lead_cycle_h5", {});
  assert.deepEqual(demandes.at(-1), { chart: "lead_cycle_h5", scope, dataDate: DATE });
  await ouvrirBrouillon(creer, "Team A", DATE, "lead_cycle_h1", {
    managementQuestion: "predictability",
    effect: { text: "Un effet", lang: "fr" },
    cause: { text: "A cause", lang: "en" },
  });
  assert.deepEqual(demandes.at(-1), {
    chart: "lead_cycle_h1",
    scope,
    dataDate: DATE,
    managementQuestion: "predictability",
    effect: { text: "Un effet", lang: "fr" },
    cause: { text: "A cause", lang: "en" },
  });
});

test("the values of the form become request fields: an empty or blank text is absent, a text keeps the language chosen for it", () => {
  const vides = valeursVides("en");
  assert.deepEqual(champsDeValeurs(vides), {});
  assert.deepEqual(champsDeValeurs({ ...vides, effect: "   ", cause: "" }), {});
  assert.deepEqual(champsDeValeurs({ ...vides, question: "scope_growth", effect: " e ", effectLang: "fr", cause: "c", causeLang: "en" }), {
    managementQuestion: "scope_growth",
    effect: { text: "e", lang: "fr" },
    cause: { text: "c", lang: "en" },
  });
});

// ---- TEXT_REFUSED ------------------------------------------------------------------------------------------------------------------

test("a refused text shows the label of its reason in each language, with how to rephrase, never the refused value", async () => {
  const motifs: Array<RefusTexte["reason"]> = ["ticket_key", "email", "sensitive_name"];
  for (const reason of motifs) {
    const cle = `fiche.textRefused.${reason}`;
    assert.ok(en[cle] && fr[cle] && en[cle] !== fr[cle], cle);
    for (const langue of ["en", "fr"] as const) {
      const html = rendre(h(RefusTexteFiche, { refus: { field: "effect", reason } }), langue);
      assert.match(html, /role="alert"/);
      assert.match(texte(html), new RegExp((langue === "en" ? en : fr)[cle].slice(0, 20)));
    }
  }
  assert.match(texte(rendre(h(RefusTexteFiche, { refus: { field: "cause", reason: "ticket_key" } }), "en")), /ISO 9001/);
  const etat = await ouvrirBrouillon(
    async () => {
      throw new RefusFiche("TEXT_REFUSED", { field: "effect", reason: "email" });
    },
    "Team A",
    DATE,
    "lead_cycle_h5",
    { effect: { text: "write to jane@example.org", lang: "en" } },
  );
  assert.deepEqual(etat, { genre: "texte_refuse", refus: { field: "effect", reason: "email" } });
  const html = formulaire("en", etat);
  assert.match(texte(html), /holds an e-mail address/);
  assert.match(html, /<form/, "the form stays open");
  assert.doesNotMatch(html, /jane@example/);
});

test("the reason too_long shows its count and its maximum, in each language", () => {
  const refus: RefusTexte = { field: "cause", reason: "too_long", count: 612, max: 500 };
  assert.match(texte(rendre(h(RefusTexteFiche, { refus }), "en")), /text refused: 612 characters, 500 at most/i);
  assert.match(texte(rendre(h(RefusTexteFiche, { refus }), "fr")), /texte refusé : 612 caractères, 500 au plus/i);
  assert.match(en["fiche.textRefused.too_long"], /\{count\}.*\{max\}/);
});

test("a failure that is not a refusal shows the translated internal error; a known code of the service shows its own label", async () => {
  const brut = await ouvrirBrouillon(async () => Promise.reject(new Error("boom")), "Team A", DATE, "lead_cycle_h5");
  assert.deepEqual(brut, { genre: "erreur", code: "INTERNAL" });
  const connu = await ouvrirBrouillon(async () => Promise.reject(new RefusFiche("UNKNOWN_USER")), "Team A", DATE, "lead_cycle_h5");
  assert.deepEqual(connu, { genre: "erreur", code: "UNKNOWN_USER" });
  assert.match(texte(formulaire("en", connu)), /Unknown user/);
});

// ---- the labels of the refusals ----------------------------------------------------------------------------------------------------

test("the refusals of completion and of review have their label in both languages (D29)", () => {
  const attendus: Record<string, [RegExp, RegExp]> = {
    UNKNOWN_USER: [/unknown user/i, /utilisateur inconnu/i],
    NOT_AUTHOR: [/only the author of the draft can complete it/i, /seul l'auteur du brouillon peut le compléter/i],
    NOT_DRAFT: [/this sheet is reviewed: a change would cancel the review/i, /cette fiche est relue : une modification annulerait la relecture/i],
    EFFECT_OR_CAUSE_MISSING: [/review refused: write the effect and the cause first/i, /relecture refusée : écrivez d'abord l'effet et la cause/i],
    NO_MANAGEMENT_QUESTION: [/review refused: choose the management question first/i, /relecture refusée : choisissez d'abord la question de direction/i],
    VERSION_FROZEN: [/frozen/i, /figée/i],
  };
  for (const [code, [anglais, francais]] of Object.entries(attendus)) {
    assert.equal(cleErreur(code), `error.${code}`, code);
    assert.match(en[`error.${code}`], anglais);
    assert.match(fr[`error.${code}`], francais);
  }
});

test("a refused review shows its label through the sheet, never the code", () => {
  for (const code of ["EFFECT_OR_CAUSE_MISSING", "NO_MANAGEMENT_QUESTION"]) {
    const html = rendre(h(Fiche, { fiche: ficheSimulee({ state: "draft" }), onRelire: () => ({ ok: true as const }), refusInitial: code }), "fr");
    assert.match(texte(html), /Relecture refusée/);
    assert.doesNotMatch(texte(html), new RegExp(code));
  }
});

// ---- completion by PATCH ----------------------------------------------------------------------------------------------------------------

const COMPLETER = () => ({ ok: true }) as ResultatCompletion;

test("the completion of a draft is offered to its author only", () => {
  const brouillon = ficheSimulee({ state: "draft" });
  const auteur = rendre(h(Fiche, { fiche: brouillon, estAuteur: true, onCompleter: COMPLETER }), "en");
  assert.match(auteur, /data-completion="brouillon"/);
  assert.match(texte(auteur), /Complete the draft/);
  assert.equal((auteur.match(/<textarea/g) ?? []).length, 2);
  assert.doesNotMatch(rendre(h(Fiche, { fiche: brouillon, estAuteur: false, onCompleter: COMPLETER }), "en"), /data-completion/);
  assert.doesNotMatch(rendre(h(Fiche, { fiche: brouillon, onCompleter: COMPLETER }), "en"), /data-completion/);
  assert.doesNotMatch(rendre(h(Fiche, { fiche: brouillon, estAuteur: true }), "en"), /data-completion/);
});

test("no completion is offered on a reviewed or a published sheet, even to its author", () => {
  for (const state of ["reviewed", "published"] as const) {
    const html = rendre(h(Fiche, { fiche: ficheSimulee({ state, publishedOn: "2026-11-05" }), estAuteur: true, onCompleter: COMPLETER }), "en");
    assert.doesNotMatch(html, /data-completion|<textarea/, state);
  }
});

test("a draft without management question, effect or cause shows the missing-field label and offers to complete them", () => {
  const brouillon = ficheSimulee({ state: "draft", effect: undefined, cause: undefined, managementQuestion: undefined });
  const html = rendre(h(Fiche, { fiche: brouillon, estAuteur: true, onCompleter: COMPLETER }), "en");
  assert.ok((texte(html).match(/Not provided yet/g) ?? []).length >= 3);
  assert.match(html, /data-completion="brouillon"/);
});

test("the completion form starts from what the draft holds and keeps the language of each written text", () => {
  const brouillon = ficheSimulee({ state: "draft", effect: { text: "Un effet écrit", lang: "fr" }, managementQuestion: "predictability" });
  const html = rendre(h(Fiche, { fiche: brouillon, estAuteur: true, onCompleter: COMPLETER }), "en");
  assert.match(html, /<textarea[^>]*>Un effet écrit<\/textarea>/);
  assert.match(html, /<option value="fr" selected="">Français<\/option>/);
  assert.match(html, /<option value="predictability" selected="">/);
});

test("the completion hands the changed fields to the PATCH route and shows its refusal translated", async () => {
  const vus: Array<{ code: string; texte?: RefusTexte } | undefined> = [];
  await lancerCompletion(() => ({ ok: false, code: "NOT_AUTHOR" }), (r) => vus.push(r));
  await lancerCompletion(() => ({ ok: false, code: "TEXT_REFUSED", texte: { field: "cause", reason: "too_long", count: 700, max: 500 } }), (r) => vus.push(r));
  await lancerCompletion(() => Promise.reject(new Error("network")), (r) => vus.push(r));
  await lancerCompletion(() => ({ ok: true }), (r) => vus.push(r));
  assert.deepEqual(vus, [
    { code: "NOT_AUTHOR" },
    { code: "TEXT_REFUSED", texte: { field: "cause", reason: "too_long", count: 700, max: 500 } },
    { code: "INTERNAL" },
    undefined,
  ]);
});

// The test renderer has no DOM (no click can be simulated, no package may be added): the button's handler is `envoyerCompletion`, tested here.
test("the completion button sends the values of the form to onCompleter, and nothing for a blank field", async () => {
  const recus: unknown[] = [];
  const onCompleter = (m: unknown): ResultatCompletion => {
    recus.push(m);
    return { ok: true };
  };
  const vus: unknown[] = [];
  const valeurs = { ...valeursVides("en"), question: "next_version_quality" as const, effect: " un effet ", effectLang: "fr" as const, cause: "  " };
  await envoyerCompletion(valeurs, onCompleter, (r) => vus.push(r));
  assert.deepEqual(recus, [{ managementQuestion: "next_version_quality", effect: { text: "un effet", lang: "fr" } }]);
  assert.deepEqual(vus, [undefined]);
});

test("a refusal already received is shown in the completion panel, translated", () => {
  const html = rendre(
    h(Fiche, { fiche: ficheSimulee({ state: "draft" }), estAuteur: true, onCompleter: COMPLETER, refusCompletionInitial: { code: "NOT_DRAFT" } }),
    "fr",
  );
  assert.match(texte(html), /cette fiche est relue/i);
  const texteRefuse = rendre(
    h(Fiche, {
      fiche: ficheSimulee({ state: "draft" }),
      estAuteur: true,
      onCompleter: COMPLETER,
      refusCompletionInitial: { code: "TEXT_REFUSED", texte: { field: "effect", reason: "too_long", count: 501, max: 500 } },
    }),
    "en",
  );
  assert.match(texte(texteRefuse), /501 characters, 500 at most/);
});
