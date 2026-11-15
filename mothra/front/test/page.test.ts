// Task 7.4: the view reader and the error messages of slice 0 (design D8), from the route GET /api/views/:view. The server is another package:
// it is simulated here by a fake fetch and a fake reader. The status by team page and section of the skeleton are removed (R-20261101-28);
// the tests that asserted them were removed with them.
import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";

import { CODES_ERREUR, ErreurApi, lireVue, optionsVue } from "../src/api/vue.ts";
import { SchemaReponseVue } from "@mothra/contract";
import type { ReponseVue } from "@mothra/contract";
import Value from "typebox/value";

import type { LecteurVue } from "../src/api/vue.ts";
import { ContenuVue } from "../src/pages/PageSquelette.ts";
import { rendre, texte } from "./rendu.ts";

const REPONSE: ReponseVue = {
  view: "v_team_status",
  threshold: 5,
  columns: ["team", "type", "status_category", "status", "tickets"],
  rows: [
    { team: "Team A", kind: "team", type: "story", status_category: "done", status: "closed", tickets: { state: "value", value: 14 } },
    { team: "Team A", kind: "team", type: "bug", status_category: "todo", status: "open", tickets: { state: "masked", threshold: 5 } },
    { team: "Team B", kind: "team", type: "story", status_category: "doing", status: "review", tickets: { state: "value", value: 5 } },
  ],
  sources: ["v_team_status"],
};

test("the fake answer of these tests is a well-formed answer of the contract, and a malformed one is refused by its schema", () => {
  assert.equal(Value.Check(SchemaReponseVue, REPONSE), true);
  assert.equal(Value.Check(SchemaReponseVue, { ...REPONSE, threshold: 4 }), false);
  assert.equal(Value.Check(SchemaReponseVue, { ...REPONSE, columns: [{ name: "team" }] }), false);
  assert.equal(Value.Check(SchemaReponseVue, { ...REPONSE, rows: [{ tickets: { state: "masked", threshold: 5, value: 3 } }] }), false);
});

function lecteurSimule(): { lire: LecteurVue; appels: string[] } {
  const appels: string[] = [];
  return {
    appels,
    lire: async (vue) => {
      appels.push(vue);
      return REPONSE;
    },
  };
}

test("each API error code is shown as its translated message, in both languages, and never as the code", () => {
  const attendus: Record<string, [string, string]> = {
    UNKNOWN_VIEW: ["This view is not available.", "Cette vue n'est pas disponible."],
    DATABASE_UNAVAILABLE: ["The data is temporarily unavailable.", "Les données sont momentanément indisponibles."],
    INTERNAL: ["Something went wrong.", "Une erreur s'est produite."],
    NOT_FOUND: ["This page does not exist.", "Cette page n'existe pas."],
    BUNDLE_MISSING: ["The application is not built yet.", "Application non construite pour le moment."],
    SELF_REVIEW_REFUSED: ["You cannot review your own sheet.", "Vous ne pouvez pas relire votre propre fiche."],
    NOT_REVIEWED: ["This sheet must be reviewed before it is published.", "Cette fiche doit être relue avant d'être publiée."],
    VERSION_FROZEN: ["A published version is frozen and cannot be changed.", "Une version publiée est figée et ne peut pas être modifiée."],
    UNKNOWN_USER: ["Unknown user.", "Utilisateur inconnu."],
    NOT_AUTHOR: ["Only the author of the draft can complete it.", "Seul l'auteur du brouillon peut le compléter."],
    NOT_DRAFT: ["This sheet is reviewed: a change would cancel the review.", "Cette fiche est relue : une modification annulerait la relecture."],
    EFFECT_OR_CAUSE_MISSING: ["Review refused: write the effect and the cause first.", "Relecture refusée : écrivez d'abord l&#x27;effet et la cause."],
    NO_MANAGEMENT_QUESTION: ["Review refused: choose the management question first.", "Relecture refusée : choisissez d'abord la question de direction."],
    INVALID_REQUEST: ["This request is not valid.", "Cette demande n'est pas valide."],
    UNKNOWN_SHEET: ["This sheet does not exist.", "Cette fiche n'existe pas."],
    THRESHOLDS_NOT_SET: ["No sheet: a threshold this sheet reads is not set yet.", "Pas de fiche : un seuil que lit cette fiche n'est pas encore fixé."],
    DATA_DATE_OUT_OF_RANGE: ["The data date must be today or earlier, in the current quarter (UTC).", "La date des données doit être aujourd'hui ou antérieure, dans le trimestre en cours (UTC)."],
    DATA_DATE_STALE: ["The data date is no longer in the current quarter: create a new sheet.", "La date des données n'est plus dans le trimestre en cours : créez une nouvelle fiche."],
  };
  for (const code of CODES_ERREUR) {
    const anglais = texte(rendre(h(ContenuVue, { etat: { genre: "erreur", code } }), "en"));
    const francais = texte(rendre(h(ContenuVue, { etat: { genre: "erreur", code } }), "fr")).replace("&#x27;", "'");
    assert.equal(anglais, attendus[code][0]);
    assert.equal(francais, attendus[code][1]);
  }
  assert.match(rendre(h(ContenuVue, { etat: { genre: "erreur", code: "X_UNKNOWN" } }), "en"), /role="alert"[^>]*>Something went wrong\./);
});

test("the reader calls the local route by a relative path, with the view name encoded", async () => {
  const demandes: string[] = [];
  const faux = (async (url: string) => {
    demandes.push(url);
    return new Response(JSON.stringify(REPONSE), { status: 200, headers: { "content-type": "application/json" } });
  }) as unknown as typeof fetch;
  const reponse = await lireVue("v_team_status", faux);
  assert.deepEqual(demandes, ["/api/views/v_team_status"]);
  assert.deepEqual(reponse, REPONSE);
  const fauxAutre = (async (url: string) => {
    demandes.push(url);
    return new Response(JSON.stringify({ ...REPONSE, view: "a/b?c" }), { status: 200, headers: { "content-type": "application/json" } });
  }) as unknown as typeof fetch;
  await lireVue("a/b?c", fauxAutre);
  assert.equal(demandes[1], "/api/views/a%2Fb%3Fc");
  assert.ok(demandes.every((d) => d.startsWith("/api/")));
});

test("the reader turns an error body into its code, and anything else into INTERNAL", async () => {
  const repondre = (statut: number, corps: string) => (async () => new Response(corps, { status: statut })) as unknown as typeof fetch;
  const code = async (faux: typeof fetch): Promise<string> => {
    try {
      await lireVue("v_team_status", faux);
    } catch (erreur) {
      assert.ok(erreur instanceof ErreurApi);
      return erreur.code;
    }
    return "AUCUNE";
  };
  assert.equal(await code(repondre(404, JSON.stringify({ error: "UNKNOWN_VIEW" }))), "UNKNOWN_VIEW");
  assert.equal(await code(repondre(503, JSON.stringify({ error: "DATABASE_UNAVAILABLE" }))), "DATABASE_UNAVAILABLE");
  assert.equal(await code(repondre(500, JSON.stringify({ error: "INTERNAL" }))), "INTERNAL");
  assert.equal(await code(repondre(500, JSON.stringify({ error: "SOMETHING_ELSE", detail: "x" }))), "INTERNAL");
  assert.equal(await code(repondre(502, "<html>not json</html>")), "INTERNAL");
  assert.equal(await code((async () => { throw new TypeError("network"); }) as unknown as typeof fetch), "INTERNAL");
});

test("a declared view is checked with its own schema: a count cell holding 3, a measure that is not a cell and a foreign column are refused", async () => {
  const repondre = (corps: unknown) => (async () => new Response(JSON.stringify(corps), { status: 200 })) as unknown as typeof fetch;
  const refuse = async (corps: unknown, vue: string): Promise<boolean> => {
    try {
      await lireVue(vue, repondre(corps));
    } catch (erreur) {
      return erreur instanceof ErreurApi && erreur.code === "INTERNAL";
    }
    return false;
  };
  const ligne = { team: "A", kind: "team", type: "story", status_category: "done", status: "closed" };
  // a count under the floor, shown as a value cell: refused (the generic union alone would accept it since the measure cell exists)
  assert.equal(await refuse({ ...REPONSE, rows: [{ ...ligne, tickets: { state: "value", value: 3 } }] }, "v_team_status"), true);
  const debit = {
    view: "v_team_lead_time_throughput",
    threshold: 5,
    columns: ["team", "period", "quarter_start", "lead_median_days", "lead_p85_days", "cycle_median_days", "cycle_p85_days", "throughput", "items_lt", "items_ct", "items_old", "items_without_commitment",
      // R-20261106-58 : les quatre colonnes de D16 (22.1), et elles seules, en fin de liste, masquées
      "lead_median_days_excl_old", "lead_p85_days_excl_old", "cycle_median_days_excl_old", "cycle_p85_days_excl_old"],
    sources: ["flow"],
    rows: [
      {
        team: "A", kind: "team", period: "quarter", quarter_start: "2026-01-01",
        lead_median_days: { state: "value", value: 3.5 }, lead_p85_days: { state: "masked", threshold: 5 },
        cycle_median_days: { state: "value", value: 4 }, cycle_p85_days: { state: "value", value: 8 },
        throughput: { state: "value", value: 20 }, items_lt: { state: "value", value: 20 }, items_ct: { state: "value", value: 20 },
        items_old: { state: "masked", threshold: 5 }, items_without_commitment: { state: "masked", threshold: 5 },
        lead_median_days_excl_old: { state: "masked", threshold: 5 }, lead_p85_days_excl_old: { state: "masked", threshold: 5 },
        cycle_median_days_excl_old: { state: "masked", threshold: 5 }, cycle_p85_days_excl_old: { state: "masked", threshold: 5 },
      },
    ],
  };
  assert.equal(await refuse(debit, "v_team_lead_time_throughput"), false);
  assert.equal(await refuse({ ...debit, rows: [{ ...debit.rows[0], throughput: { state: "value", value: 3 } }] }, "v_team_lead_time_throughput"), true);
  assert.equal(await refuse({ ...debit, rows: [{ ...debit.rows[0], lead_median_days: 3.5 }] }, "v_team_lead_time_throughput"), true);
  assert.equal(await refuse({ ...debit, rows: [{ ...debit.rows[0], extra: "x" }] }, "v_team_lead_time_throughput"), true);
});

test("an answer that is not the contract's, or is another view than the one asked, is an INTERNAL error", async () => {
  const repondre = (corps: unknown) => (async () => new Response(JSON.stringify(corps), { status: 200 })) as unknown as typeof fetch;
  const code = async (corps: unknown, vue = "v_team_status"): Promise<string> => {
    try {
      await lireVue(vue, repondre(corps));
    } catch (erreur) {
      assert.ok(erreur instanceof ErreurApi);
      return erreur.code;
    }
    return "AUCUNE";
  };
  assert.equal(await code({ state: "hidden" }), "INTERNAL");
  assert.equal(await code({ ...REPONSE, rows: [{ team: { objet: 1 }, tickets: { state: "value", value: 1 } }] }), "INTERNAL");
  assert.equal(await code({ ...REPONSE, view: "v_autre" }), "INTERNAL");
  assert.equal(await code(REPONSE), "AUCUNE");
});

test("the query options keep one key per view and do not retry an error answer", () => {
  const options = optionsVue("v_team_status", lecteurSimule().lire);
  assert.deepEqual(options.queryKey, ["view", "v_team_status"]);
  assert.equal(options.retry, false);
});
