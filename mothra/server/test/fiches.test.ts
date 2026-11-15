// Tasks 18.1, 18.2 and the route side of 18.3 (design D20, D21, D29): the sheet and threshold routes on a fake storage, no database.
// The lists of names are two invented lists held here as test data, never the real files.
import assert from "node:assert/strict";
import { test } from "node:test";

import { lireNoms, motifsDeNoms } from "@mothra/contract";

import { construireServeur } from "../src/routes/serveur.ts";
import { BaseIndisponible } from "../src/db/acces.ts";
import { empreinte as empreinteDe } from "../src/fiches/depot.ts";
import { AccesFictif, SENTINELLE, contrat, journalCapture } from "./aide.ts";
import { DepotMemoire, corpsSynthetique } from "./depot-memoire.ts";

const LISTE_SENSIBLE = "Zorglub Martin\nabc\n";
const LISTE_EQUIPES = "Quentin Duval\n";
const motifsNoms = motifsDeNoms([...lireNoms(LISTE_SENSIBLE), ...lireNoms(LISTE_EQUIPES)]);

const AUTEUR = { "x-mothra-user": "agile-lead-1" };
const RELECTEUR = { "x-mothra-user": "agile-lead-2" };
const DEMANDE = { chart: "lead_cycle_h5", scope: "team-a", dataDate: "2026-10-01" };
// A sheet ready for review: a management question, an effect and a cause (decisions of 2026-10-29).
const COMPLETE = { ...DEMANDE, managementQuestion: "predictability", effect: { text: "Effect.", lang: "en" }, cause: { text: "Cause.", lang: "en" } };

// `aujourdhui`: the UTC day of the routes, fixed (A-66: a data date is bounded by the day and by its quarter, never the real clock).
function monter(depot = new DepotMemoire(), corps = () => corpsSynthetique(), journal = journalCapture(), aujourdhui: () => string = () => "2026-11-12") {
  const { app, routes } = construireServeur({
    contrat,
    acces: new AccesFictif([]),
    reglageSeuil: null,
    journal: { level: "info", stream: journal.stream },
    fiches: { depot, calculerCorps: async () => corps(), motifsNoms, reduite: false, aujourdhui },
  });
  return { app, routes, depot, journal };
}

async function appeler(app: ReturnType<typeof monter>["app"], method: "GET" | "POST" | "PATCH", url: string, headers: Record<string, string> = AUTEUR, payload?: unknown) {
  const r = await app.inject({ method, url, headers, payload: payload as object | undefined });
  return { statut: r.statusCode, corps: r.json() as Record<string, unknown>, brut: r.body };
}

test("a sheet from a chart gives a draft; the request declares no verdict and refuses any undeclared field", async () => {
  const { app, depot } = monter();
  const ok = await appeler(app, "POST", "/api/sheets", AUTEUR, DEMANDE);
  assert.equal(ok.statut, 200);
  assert.deepEqual(ok.corps, { id: "1", state: "draft" });
  const avecVerdict = await appeler(app, "POST", "/api/sheets", AUTEUR, { ...DEMANDE, verdict: "confirmed" });
  assert.equal(avecVerdict.statut, 400);
  assert.deepEqual(avecVerdict.corps, { error: "INVALID_REQUEST" });
  assert.equal(depot.fiches.size, 1, "nothing stored for the refused request");
  const sansDate = await appeler(app, "POST", "/api/sheets", AUTEUR, { chart: "x", scope: "y" });
  assert.equal(sansDate.statut, 400);
  await app.close();
});

test("a request without a valid caller identifier is refused", async () => {
  const { app, depot } = monter();
  for (const headers of [{} as Record<string, string>, { "x-mothra-user": "Not A User" }]) {
    const r = await appeler(app, "POST", "/api/sheets", headers, DEMANDE);
    assert.equal(r.statut, 400);
  }
  assert.equal(depot.fiches.size, 0);
  await app.close();
});

test("the written texts are stored and read back with their language", async () => {
  const { app } = monter();
  const effet = { text: "Delivery slowed down.", lang: "en" };
  const cause = { text: "Les relectures attendent.", lang: "fr" };
  const cree = await appeler(app, "POST", "/api/sheets", AUTEUR, { ...DEMANDE, effect: effet, cause });
  assert.equal(cree.statut, 200);
  const lu = await appeler(app, "GET", `/api/sheets/${String(cree.corps.id)}`);
  assert.equal(lu.statut, 200);
  assert.deepEqual(lu.corps.effect, effet);
  assert.deepEqual(lu.corps.cause, cause);
  assert.equal(lu.corps.state, "draft");
  assert.equal(lu.corps.verdict, "not_settled");
  await app.close();
});

test("a language other than fr or en, or a text without language, is refused by the request schema", async () => {
  const { app, depot } = monter();
  assert.equal((await appeler(app, "POST", "/api/sheets", AUTEUR, { ...DEMANDE, effect: { text: "x", lang: "de" } })).statut, 400);
  assert.equal((await appeler(app, "POST", "/api/sheets", AUTEUR, { ...DEMANDE, cause: { text: "x" } })).statut, 400);
  assert.equal(depot.fiches.size, 0);
  await app.close();
});

test("each refused content gives 422 TEXT_REFUSED with its field and reason, stores nothing and echoes neither the text nor the value", async () => {
  const cas: Array<[string, string, string]> = [
    ["effect", "see ABC-123 for details", "ticket_key"],
    ["cause", "ISO-9001 applies", "ticket_key"],
    ["effect", "write to someone@example.org", "email"],
    ["cause", "asked Zorglub Martin yesterday", "sensitive_name"],
    ["effect", "asked quentin duval yesterday", "sensitive_name"],
  ];
  for (const [champ, texte, raison] of cas) {
    const { app, depot, journal } = monter();
    const r = await appeler(app, "POST", "/api/sheets", AUTEUR, { ...DEMANDE, [champ]: { text: texte, lang: "en" } });
    assert.equal(r.statut, 422, texte);
    assert.deepEqual(r.corps, { error: "TEXT_REFUSED", field: champ, reason: raison }, texte);
    assert.equal(depot.fiches.size, 0);
    for (const interdit of ["ABC-123", "ISO-9001", "someone@example.org", "Zorglub", "Duval", texte]) {
      assert.ok(!r.brut.includes(interdit), `answer echoes ${interdit}`);
      assert.ok(!journal.texte().includes(interdit), `log echoes ${interdit}`);
    }
    await app.close();
  }
});

test("a name stuck to a letter is accepted, a three-character name keeps its case, a reference with a space is accepted", async () => {
  const { app } = monter();
  for (const texte of ["asked xZorglub Martin", "the note ABC", "compliant with ISO 9001"]) {
    const r = await appeler(app, "POST", "/api/sheets", AUTEUR, { ...DEMANDE, effect: { text: texte, lang: "en" } });
    assert.equal(r.statut, 200, texte);
  }
  await app.close();
});

test("500 characters are accepted, 501 refused with the count and the maximum, the spaces at the ends not counted", async () => {
  const { app } = monter();
  const a500 = await appeler(app, "POST", "/api/sheets", AUTEUR, { ...DEMANDE, effect: { text: ` ${"a".repeat(500)} `, lang: "en" } });
  assert.equal(a500.statut, 200);
  const a501 = await appeler(app, "POST", "/api/sheets", AUTEUR, { ...DEMANDE, cause: { text: "a".repeat(501), lang: "fr" } });
  assert.equal(a501.statut, 422);
  assert.deepEqual(a501.corps, { error: "TEXT_REFUSED", field: "cause", reason: "too_long", count: 501, max: 500 });
  await app.close();
});

test("an unknown sheet answers 404 UNKNOWN_SHEET", async () => {
  const { app } = monter();
  const r = await appeler(app, "GET", "/api/sheets/99");
  assert.equal(r.statut, 404);
  assert.deepEqual(r.corps, { error: "UNKNOWN_SHEET" });
  await app.close();
});

test("the author cannot review their own sheet; another Agile Lead can", async () => {
  const { app, depot } = monter();
  const { corps } = await appeler(app, "POST", "/api/sheets", AUTEUR, COMPLETE);
  const id = String(corps.id);
  const refus = await appeler(app, "POST", `/api/sheets/${id}/review`, AUTEUR);
  assert.equal(refus.statut, 403);
  assert.deepEqual(refus.corps, { error: "SELF_REVIEW_REFUSED" });
  assert.equal(depot.fiches.get(id)?.state, "draft");
  const ok = await appeler(app, "POST", `/api/sheets/${id}/review`, RELECTEUR);
  assert.equal(ok.statut, 200);
  assert.equal(ok.corps.state, "reviewed");
  await app.close();
});

test("the review is refused without a management question, then without an effect or a cause, and stores nothing", async () => {
  const { app, depot } = monter();
  const sansQuestion = await appeler(app, "POST", "/api/sheets", AUTEUR, { ...COMPLETE, managementQuestion: undefined });
  const r1 = await appeler(app, "POST", `/api/sheets/${String(sansQuestion.corps.id)}/review`, RELECTEUR);
  assert.equal(r1.statut, 422);
  assert.deepEqual(r1.corps, { error: "NO_MANAGEMENT_QUESTION" });
  const sansEffet = await appeler(app, "POST", "/api/sheets", AUTEUR, { ...COMPLETE, effect: undefined });
  const r2 = await appeler(app, "POST", `/api/sheets/${String(sansEffet.corps.id)}/review`, RELECTEUR);
  assert.equal(r2.statut, 422);
  assert.deepEqual(r2.corps, { error: "EFFECT_OR_CAUSE_MISSING" });
  const sansCause = await appeler(app, "POST", "/api/sheets", AUTEUR, { ...COMPLETE, cause: undefined });
  assert.deepEqual((await appeler(app, "POST", `/api/sheets/${String(sansCause.corps.id)}/review`, RELECTEUR)).corps, { error: "EFFECT_OR_CAUSE_MISSING" });
  assert.ok(!depot.appels.includes("relire"));
  // The drafts themselves stay possible without them.
  assert.equal(sansQuestion.statut, 200);
  await app.close();
});

test("the management question is a closed list of four codes, read back; any other value is refused at creation", async () => {
  const { app, depot } = monter();
  for (const question of ["scope_growth", "scope_reachability", "predictability", "next_version_quality"]) {
    const r = await appeler(app, "POST", "/api/sheets", AUTEUR, { ...DEMANDE, managementQuestion: question });
    assert.equal(r.statut, 200, question);
    assert.equal((await appeler(app, "GET", `/api/sheets/${String(r.corps.id)}`)).corps.managementQuestion, question);
  }
  const avant = depot.fiches.size;
  assert.equal((await appeler(app, "POST", "/api/sheets", AUTEUR, { ...DEMANDE, managementQuestion: "other" })).statut, 400);
  assert.equal(depot.fiches.size, avant);
  await app.close();
});

test("the chart, the scope and the date must have the form of a code and of a date", async () => {
  const { app, depot } = monter();
  for (const mauvais of [{ chart: "Lead Cycle" }, { scope: "Team A" }, { dataDate: "yesterday" }]) {
    assert.equal((await appeler(app, "POST", "/api/sheets", AUTEUR, { ...DEMANDE, ...mauvais })).statut, 400);
  }
  assert.equal(depot.fiches.size, 0);
  await app.close();
});

test("the texts are stored trimmed", async () => {
  const { app, depot } = monter();
  const r = await appeler(app, "POST", "/api/sheets", AUTEUR, { ...DEMANDE, effect: { text: "  Effect.  ", lang: "en" } });
  assert.equal(depot.fiches.get(String(r.corps.id))?.effect?.text, "Effect.");
  await app.close();
});

test("a well-formed identifier that names no user is refused with 403 UNKNOWN_USER on every route that reads the header, without echo", async () => {
  const { app, depot, journal } = monter();
  const inconnu = { "x-mothra-user": "ghost-user-7" };
  const { corps } = await appeler(app, "POST", "/api/sheets", AUTEUR, COMPLETE);
  const id = String(corps.id);
  const essais: Array<[string, "POST" | "PATCH", string, unknown]> = [
    ["create", "POST", "/api/sheets", DEMANDE],
    ["change", "PATCH", `/api/sheets/${id}`, { managementQuestion: "scope_growth" }],
    ["review", "POST", `/api/sheets/${id}/review`, undefined],
    ["publish", "POST", `/api/sheets/${id}/publish`, undefined],
  ];
  for (const [nom, methode, url, payload] of essais) {
    const r = await appeler(app, methode, url, inconnu, payload);
    assert.equal(r.statut, 403, nom);
    assert.deepEqual(r.corps, { error: "UNKNOWN_USER" }, nom);
    assert.ok(!r.brut.includes("ghost-user-7"), nom);
  }
  assert.ok(!journal.texte().includes("ghost-user-7"));
  assert.equal(depot.fiches.size, 1, "nothing stored");
  assert.ok(!depot.appels.includes("modifier") && !depot.appels.includes("relire") && !depot.appels.includes("publier"));
  await app.close();
});

test("the author completes a draft: the effect, the cause and the question, any of them, read back", async () => {
  const { app } = monter();
  const { corps } = await appeler(app, "POST", "/api/sheets", AUTEUR, DEMANDE);
  const id = String(corps.id);
  const r = await appeler(app, "PATCH", `/api/sheets/${id}`, AUTEUR, { managementQuestion: "next_version_quality", effect: { text: "  Quality dropped. ", lang: "en" } });
  assert.equal(r.statut, 200);
  assert.equal(r.corps.managementQuestion, "next_version_quality");
  assert.deepEqual(r.corps.effect, { text: "Quality dropped.", lang: "en" });
  assert.equal(r.corps.cause, undefined);
  const suite = await appeler(app, "PATCH", `/api/sheets/${id}`, AUTEUR, { cause: { text: "Peu de relectures.", lang: "fr" } });
  assert.deepEqual(suite.corps.cause, { text: "Peu de relectures.", lang: "fr" });
  assert.equal(suite.corps.managementQuestion, "next_version_quality", "a field not given keeps its value");
  // A draft completed in this way can be reviewed by another Agile Lead.
  assert.equal((await appeler(app, "POST", `/api/sheets/${id}/review`, RELECTEUR)).statut, 200);
  await app.close();
});

test("only the author changes a draft (403 NOT_AUTHOR); an empty change, a verdict or an unknown field is refused (400)", async () => {
  const { app, depot } = monter();
  const { corps } = await appeler(app, "POST", "/api/sheets", AUTEUR, DEMANDE);
  const id = String(corps.id);
  const autre = await appeler(app, "PATCH", `/api/sheets/${id}`, RELECTEUR, { managementQuestion: "scope_growth" });
  assert.equal(autre.statut, 403);
  assert.deepEqual(autre.corps, { error: "NOT_AUTHOR" });
  for (const mauvais of [{}, { verdict: "confirmed" }, { managementQuestion: "other" }, { chart: "x" }]) {
    assert.equal((await appeler(app, "PATCH", `/api/sheets/${id}`, AUTEUR, mauvais)).statut, 400, JSON.stringify(mauvais));
  }
  assert.equal((await appeler(app, "PATCH", "/api/sheets/99", AUTEUR, { managementQuestion: "scope_growth" })).statut, 404);
  assert.ok(!depot.appels.includes("modifier"));
  await app.close();
});

test("a published version is frozen (409 VERSION_FROZEN) and a reviewed sheet is no longer a draft (409 NOT_DRAFT)", async () => {
  const { app, depot } = monter();
  const { corps } = await appeler(app, "POST", "/api/sheets", AUTEUR, COMPLETE);
  const id = String(corps.id);
  await appeler(app, "POST", `/api/sheets/${id}/review`, RELECTEUR);
  // One review only: a second one answers 409 NOT_DRAFT.
  const seconde = await appeler(app, "POST", `/api/sheets/${id}/review`, { "x-mothra-user": "agile-lead-3" });
  assert.equal(seconde.statut, 409);
  assert.deepEqual(seconde.corps, { error: "NOT_DRAFT" });
  const revue = await appeler(app, "PATCH", `/api/sheets/${id}`, AUTEUR, { managementQuestion: "scope_growth" });
  assert.equal(revue.statut, 409);
  assert.deepEqual(revue.corps, { error: "NOT_DRAFT" });
  await appeler(app, "POST", `/api/sheets/${id}/publish`, AUTEUR);
  const figee = await appeler(app, "PATCH", `/api/sheets/${id}`, AUTEUR, { managementQuestion: "scope_growth" });
  assert.equal(figee.statut, 409);
  assert.deepEqual(figee.corps, { error: "VERSION_FROZEN" });
  assert.ok(!depot.appels.includes("modifier"));
  assert.equal(depot.fiches.get(id)?.managementQuestion, "predictability");
  await app.close();
});

test("a change goes through the same text check: 422 TEXT_REFUSED with its field and reason, nothing changed, no echo", async () => {
  const { app, depot, journal } = monter();
  const { corps } = await appeler(app, "POST", "/api/sheets", AUTEUR, DEMANDE);
  const id = String(corps.id);
  const cas: Array<[string, string, string]> = [
    ["effect", "see ABC-123", "ticket_key"],
    ["cause", "write to someone@example.org", "email"],
    ["effect", "asked Zorglub Martin", "sensitive_name"],
  ];
  for (const [champ, texte, raison] of cas) {
    const r = await appeler(app, "PATCH", `/api/sheets/${id}`, AUTEUR, { [champ]: { text: texte, lang: "en" } });
    assert.equal(r.statut, 422, texte);
    assert.deepEqual(r.corps, { error: "TEXT_REFUSED", field: champ, reason: raison }, texte);
    assert.ok(!r.brut.includes(texte) && !journal.texte().includes(texte));
  }
  const longue = await appeler(app, "PATCH", `/api/sheets/${id}`, AUTEUR, { cause: { text: "a".repeat(501), lang: "fr" } });
  assert.deepEqual(longue.corps, { error: "TEXT_REFUSED", field: "cause", reason: "too_long", count: 501, max: 500 });
  assert.ok(!depot.appels.includes("modifier"));
  await app.close();
});

test("the sheet routes now include the change route", () => {
  assert.ok(monter().routes.some((r) => r.method === "PATCH" && r.url === "/api/sheets/:id"));
});

test("publication of an unreviewed sheet answers 409 NOT_REVIEWED and freezes nothing", async () => {
  const { app, depot } = monter();
  const { corps } = await appeler(app, "POST", "/api/sheets", AUTEUR, DEMANDE);
  const r = await appeler(app, "POST", `/api/sheets/${String(corps.id)}/publish`, AUTEUR);
  assert.equal(r.statut, 409);
  assert.deepEqual(r.corps, { error: "NOT_REVIEWED" });
  assert.ok(!depot.appels.includes("publier"));
  await app.close();
});

test("a reviewed sheet is published and frozen with the fingerprint of its content; later computations do not change it", async () => {
  let corps = corpsSynthetique();
  const { app, depot } = monter(new DepotMemoire(), () => corps);
  const cree = await appeler(app, "POST", "/api/sheets", AUTEUR, COMPLETE);
  const id = String(cree.corps.id);
  await appeler(app, "POST", `/api/sheets/${id}/review`, RELECTEUR);
  const publie = await appeler(app, "POST", `/api/sheets/${id}/publish`, AUTEUR);
  assert.equal(publie.statut, 200);
  assert.equal(publie.corps.state, "published");
  assert.equal(publie.corps.publishedOn, "2026-11-09");
  const figee = depot.fiches.get(id)?.published;
  assert.match(figee?.fingerprint ?? "", /^[0-9a-f]{64}$/);
  // The effect, the cause and the question are part of the frozen content and of its fingerprint.
  assert.deepEqual(figee?.content.effect, { text: "Effect.", lang: "en" });
  assert.deepEqual(figee?.content.cause, { text: "Cause.", lang: "en" });
  assert.equal(figee?.content.managementQuestion, "predictability");
  assert.equal(figee?.fingerprint, empreinteDe(figee?.content));
  // The data moves on, and so does the table: the published version is read back as frozen, from its content alone.
  corps = corpsSynthetique({ verdict: "refuted" });
  const fiche = depot.fiches.get(id);
  if (fiche !== undefined) {
    fiche.effect = { text: "Changed after publication.", lang: "en" };
    fiche.managementQuestion = "scope_growth";
  }
  const relu = await appeler(app, "GET", `/api/sheets/${id}`);
  assert.equal(relu.corps.verdict, "not_settled");
  assert.deepEqual(relu.corps.effect, { text: "Effect.", lang: "en" });
  assert.equal(relu.corps.managementQuestion, "predictability");
  // A second publication or a review of the published version is refused.
  for (const url of [`/api/sheets/${id}/publish`, `/api/sheets/${id}/review`]) {
    const r = await appeler(app, "POST", url, RELECTEUR);
    assert.equal(r.statut, 409);
    assert.deepEqual(r.corps, { error: "VERSION_FROZEN" });
  }
  assert.equal(depot.appels.filter((a) => a === "publier").length, 1);
  await app.close();
});

test("the fingerprint depends on the content and on nothing else", async () => {
  const { empreinte } = await import("../src/fiches/depot.ts");
  assert.equal(empreinte({ b: 1, a: [1, 2] }), empreinte({ a: [1, 2], b: 1 }));
  assert.notEqual(empreinte({ a: 1 }), empreinte({ a: 2 }));
  assert.equal(empreinte({ a: 1, b: undefined }), empreinte({ a: 1 }));
});

test("a threshold without its date answers 422 THRESHOLD_INCOMPLETE and is not stored", async () => {
  const { app, depot } = monter();
  const r = await appeler(app, "POST", "/api/thresholds", AUTEUR, { code: "h5_band", value: 0.2 });
  assert.equal(r.statut, 422);
  assert.deepEqual(r.corps, { error: "THRESHOLD_INCOMPLETE" });
  assert.equal(depot.historique.length, 0);
  await app.close();
});

test("a complete threshold is added to the history with the user of the header as its author; no author nor attendees field is accepted in the body", async () => {
  const { app, depot } = monter();
  const vide = await appeler(app, "GET", "/api/thresholds");
  assert.deepEqual(vide.corps, { thresholds: [] });
  const r = await appeler(app, "POST", "/api/thresholds", AUTEUR, { code: "h5_band", value: 0.2, setOn: "2026-10-30" });
  assert.equal(r.statut, 200);
  // R-20261107-27 (A-94, decision 3 a): the response carries no author; the history keeps it in the store.
  assert.deepEqual(r.corps, { thresholds: [{ code: "h5_band", value: 0.2, setOn: "2026-10-30" }] });
  assert.ok(!r.brut.includes("setBy") && !r.brut.includes("agile-lead-1"), "the threshold response names no author");
  for (const corps of [
    { code: "h5_band", value: 0.3, setOn: "2026-10-31", setBy: "someone-else" },
    { code: "h5_band", value: 0.3, setOn: "2026-10-31", attendees: ["x"] },
  ]) {
    assert.equal((await appeler(app, "POST", "/api/thresholds", AUTEUR, corps)).statut, 400);
  }
  assert.equal(depot.historique.length, 1, "nothing stored for a body that names an author");
  await app.close();
});

test("the threshold route reads the header like the others: unknown user 403 UNKNOWN_USER, no valid header 400, nothing stored", async () => {
  const { app, depot, journal } = monter();
  const corps = { code: "h5_band", value: 0.2, setOn: "2026-10-30" };
  const inconnu = await appeler(app, "POST", "/api/thresholds", { "x-mothra-user": "ghost-user-7" }, corps);
  assert.equal(inconnu.statut, 403);
  assert.deepEqual(inconnu.corps, { error: "UNKNOWN_USER" });
  assert.ok(!inconnu.brut.includes("ghost-user-7") && !journal.texte().includes("ghost-user-7"));
  assert.equal((await appeler(app, "POST", "/api/thresholds", {} as Record<string, string>, corps)).statut, 400);
  assert.equal((await appeler(app, "POST", "/api/thresholds", { "x-mothra-user": "Not A User" }, corps)).statut, 400);
  assert.equal(depot.historique.length, 0);
  await app.close();
});

test("a date that does not exist is refused with 400, in the data date of a sheet and in the date of a threshold", async () => {
  // A-66 (R-20261112-30): the leap day is a real date only if it is not after the day; the day is injected (the data date is bounded by it).
  const { app, depot } = monter(undefined, undefined, undefined, () => "2028-03-01");
  for (const jour of ["2026-02-30", "2026-13-01", "2026-00-10", "2025-02-29"]) {
    assert.equal((await appeler(app, "POST", "/api/sheets", AUTEUR, { ...DEMANDE, dataDate: jour })).statut, 400, jour);
    assert.equal((await appeler(app, "POST", "/api/thresholds", AUTEUR, { code: "h5_band", value: 1, setOn: jour })).statut, 400, jour);
  }
  assert.equal((await appeler(app, "POST", "/api/sheets", AUTEUR, { ...DEMANDE, dataDate: "2028-02-29" })).statut, 200, "a leap day exists");
  assert.equal(depot.historique.length, 0);
  await app.close();
});

test("a body error of the framework answers 400 INVALID_REQUEST, never 500: malformed JSON, unsupported media type, empty body, body too large", async () => {
  const { app } = monter();
  const envois: Array<[string, Record<string, string>, string]> = [
    ["malformed JSON", { "content-type": "application/json", ...AUTEUR }, "{not json"],
    ["unsupported media type", { "content-type": "text/plain", ...AUTEUR }, "hello"],
    ["empty body", { "content-type": "application/json", ...AUTEUR }, ""],
    ["body too large", { "content-type": "application/json", ...AUTEUR }, JSON.stringify({ ...DEMANDE, effect: { text: "a".repeat(2_000_000), lang: "en" } })],
  ];
  for (const url of ["/api/sheets", "/api/thresholds"]) {
    for (const [nom, headers, payload] of envois) {
      const r = await app.inject({ method: "POST", url, headers, payload });
      assert.equal(r.statusCode, 400, `${url} ${nom}`);
      assert.deepEqual(r.json(), { error: "INVALID_REQUEST" }, `${url} ${nom}`);
    }
  }
  const patch = await app.inject({ method: "PATCH", url: "/api/sheets/1", headers: { "content-type": "application/json", ...AUTEUR }, payload: "{not json" });
  assert.equal(patch.statusCode, 400);
  assert.deepEqual(patch.json(), { error: "INVALID_REQUEST" });
  await app.close();
});

test("a header that is not an identifier is a schema violation answered 400 on every route that writes, and nothing is stored", async () => {
  const { app, depot } = monter();
  const { corps } = await appeler(app, "POST", "/api/sheets", AUTEUR, COMPLETE);
  const id = String(corps.id);
  const faux = { "x-mothra-user": "Not A User" };
  for (const [methode, url, payload] of [
    ["POST", "/api/sheets", DEMANDE],
    ["PATCH", `/api/sheets/${id}`, { managementQuestion: "scope_growth" }],
    ["POST", `/api/sheets/${id}/review`, undefined],
    ["POST", `/api/sheets/${id}/publish`, undefined],
  ] as const) {
    assert.equal((await appeler(app, methode, url, faux, payload)).statut, 400, url);
    assert.equal((await appeler(app, methode, url, {} as Record<string, string>, payload)).statut, 400, url);
  }
  assert.equal(depot.fiches.size, 1);
  assert.ok(!depot.appels.includes("modifier") && !depot.appels.includes("relire") && !depot.appels.includes("publier"));
  await app.close();
});

test("only the author publishes a reviewed sheet (403 NOT_AUTHOR); a reviewer, even a user, cannot", async () => {
  const { app, depot } = monter();
  const { corps } = await appeler(app, "POST", "/api/sheets", AUTEUR, COMPLETE);
  const id = String(corps.id);
  await appeler(app, "POST", `/api/sheets/${id}/review`, RELECTEUR);
  const refus = await appeler(app, "POST", `/api/sheets/${id}/publish`, RELECTEUR);
  assert.equal(refus.statut, 403);
  assert.deepEqual(refus.corps, { error: "NOT_AUTHOR" });
  assert.ok(!depot.appels.includes("publier"));
  assert.equal(depot.fiches.get(id)?.state, "reviewed");
  assert.equal((await appeler(app, "POST", `/api/sheets/${id}/publish`, AUTEUR)).statut, 200);
  await app.close();
});

test("an empty text, or one made of spaces, counts as absent at the review; the draft stores it as it is", async () => {
  const { app, depot } = monter();
  for (const [champ, texte] of [["effect", ""], ["effect", "   "], ["cause", "\t "]] as const) {
    const { corps } = await appeler(app, "POST", "/api/sheets", AUTEUR, { ...COMPLETE, [champ]: { text: texte, lang: "en" } });
    const id = String(corps.id);
    assert.ok(depot.fiches.get(id)?.[champ] !== undefined, "the draft holds the empty text");
    const r = await appeler(app, "POST", `/api/sheets/${id}/review`, RELECTEUR);
    assert.equal(r.statut, 422, `${champ} ${JSON.stringify(texte)}`);
    assert.deepEqual(r.corps, { error: "EFFECT_OR_CAUSE_MISSING" });
  }
  assert.ok(!depot.appels.includes("relire"));
  await app.close();
});

test("a sheet already frozen by another request at the moment of the freeze answers 409 VERSION_FROZEN", async () => {
  const depot = new DepotMemoire();
  const { app } = monter(depot);
  const { corps } = await appeler(app, "POST", "/api/sheets", AUTEUR, COMPLETE);
  const id = String(corps.id);
  await appeler(app, "POST", `/api/sheets/${id}/review`, RELECTEUR);
  // The other request wins the race: the sheet changes state between the read of the route and the freeze of the depot.
  const lire = depot.lire.bind(depot);
  depot.lire = async (i: string) => {
    const fiche = await lire(i);
    const f = depot.fiches.get(i);
    if (f !== undefined) f.state = "published";
    return fiche;
  };
  const r = await appeler(app, "POST", `/api/sheets/${id}/publish`, AUTEUR);
  assert.equal(r.statut, 409);
  assert.deepEqual(r.corps, { error: "VERSION_FROZEN" });
  await app.close();
});

test("a storage failure answers 503 DATABASE_UNAVAILABLE without detail", async () => {
  const depot = new DepotMemoire();
  depot.echec = new BaseIndisponible();
  const { app, journal } = monter(depot);
  const r = await appeler(app, "POST", "/api/sheets", AUTEUR, DEMANDE);
  assert.equal(r.statut, 503);
  assert.deepEqual(r.corps, { error: "DATABASE_UNAVAILABLE" });
  assert.equal((await appeler(app, "GET", "/api/thresholds")).statut, 503);
  assert.ok(!journal.texte().includes("database unavailable"));
  await app.close();
});

test("no real data reaches the sheet routes: a key, a title or a person held by a body beyond its schema is not serialized", async () => {
  const corps = () => corpsSynthetique({ ticketKey: `SENT-1 ${SENTINELLE}`, title: SENTINELLE, person: SENTINELLE });
  const { app, journal } = monter(new DepotMemoire(), corps);
  const cree = await appeler(app, "POST", "/api/sheets", AUTEUR, COMPLETE);
  const id = String(cree.corps.id);
  const lectures = [await appeler(app, "GET", `/api/sheets/${id}`), await appeler(app, "POST", `/api/sheets/${id}/review`, RELECTEUR), await appeler(app, "POST", `/api/sheets/${id}/publish`, AUTEUR), await appeler(app, "GET", `/api/sheets/${id}`)];
  for (const l of [cree, ...lectures]) {
    assert.ok(!l.brut.includes(SENTINELLE) && !l.brut.includes("SENT-1"), l.brut.slice(0, 80));
  }
  assert.ok(!journal.texte().includes(SENTINELLE));
  await app.close();
});

test("every route of the sheets has a response schema (the registration would fail otherwise) and the routes are registered only when given", () => {
  const avec = monter().routes.map((r) => `${r.method} ${r.url}`);
  for (const route of ["POST /api/sheets", "GET /api/sheets/:id", "POST /api/sheets/:id/review", "POST /api/sheets/:id/publish", "GET /api/thresholds", "POST /api/thresholds"]) {
    assert.ok(avec.includes(route), route);
  }
  const { routes } = construireServeur({ contrat, acces: new AccesFictif([]), reglageSeuil: null, journal: false });
  assert.ok(!routes.some((r) => r.url.startsWith("/api/sheets")));
});
