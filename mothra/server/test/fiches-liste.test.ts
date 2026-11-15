// Audit #629, A-04: `GET /api/sheets?state=…`, the sheets of one state, so that a reviewer finds the drafts of someone else and an author the reviewed
// sheets. The route lists, it computes nothing: no written text, no verdict, no author. A fake storage, no database; invented identifiers.
import assert from "node:assert/strict";
import { test } from "node:test";

import { lireNoms, motifsDeNoms } from "@mothra/contract";

import { BaseIndisponible } from "../src/db/acces.ts";
import { LIMITE_LISTE_FICHES } from "../src/fiches/depot.ts";
import { construireServeur } from "../src/routes/serveur.ts";
import { AccesFictif, contrat, journalCapture } from "./aide.ts";
import { DepotMemoire, corpsSynthetique } from "./depot-memoire.ts";

const motifsNoms = motifsDeNoms([...lireNoms("Zorglub Martin\n")]);
const AUTEUR = { "x-mothra-user": "agile-lead-1" };
const RELECTEUR = { "x-mothra-user": "agile-lead-2" };
const COMPLETE = {
  chart: "lead_cycle_h5",
  scope: "team.0123456789abcdef",
  dataDate: "2026-10-01",
  managementQuestion: "predictability",
  effect: { text: "A written effect.", lang: "en" },
  cause: { text: "A written cause.", lang: "en" },
};

function monter(depot = new DepotMemoire(), options: { desactivees?: () => boolean } = {}) {
  const journal = journalCapture();
  const { app } = construireServeur({
    contrat,
    acces: new AccesFictif([]),
    reglageSeuil: null,
    journal: { level: "info", stream: journal.stream },
    fiches: { depot, calculerCorps: async () => corpsSynthetique(), motifsNoms, reduite: false, aujourdhui: () => "2026-11-12", ...options },
  });
  return { app, depot, journal };
}

async function appeler(app: ReturnType<typeof monter>["app"], method: "GET" | "POST", url: string, headers: Record<string, string> = {}, payload?: unknown) {
  const r = await app.inject({ method, url, headers, payload: payload as object | undefined });
  return { statut: r.statusCode, corps: r.json() as Record<string, unknown>, brut: r.body };
}

async function creer(app: ReturnType<typeof monter>["app"], surcharge: Record<string, unknown> = {}): Promise<string> {
  const r = await appeler(app, "POST", "/api/sheets", AUTEUR, { ...COMPLETE, ...surcharge });
  assert.equal(r.statut, 200);
  return String(r.corps.id);
}

test("the drafts are listed, the newest first, with the identifier, the kind, the scope, the data date and the state, and nothing else", async () => {
  const { app } = monter();
  const a = await creer(app);
  const b = await creer(app, { chart: "lead_cycle_h1", dataDate: "2026-10-02" });
  const liste = await appeler(app, "GET", "/api/sheets?state=draft");
  assert.equal(liste.statut, 200);
  assert.deepEqual(liste.corps, {
    sheets: [
      { id: b, chart: "lead_cycle_h1", scope: COMPLETE.scope, dataDate: "2026-10-02", state: "draft" },
      { id: a, chart: "lead_cycle_h5", scope: COMPLETE.scope, dataDate: "2026-10-01", state: "draft" },
    ],
  });
  await app.close();
});

test("a list holds no written text, no verdict, no author, no reviewer and no figure", async () => {
  const { app } = monter();
  await creer(app);
  const brut = (await appeler(app, "GET", "/api/sheets?state=draft")).brut;
  for (const interdit of ["A written effect", "A written cause", "verdict", "createdBy", "reviewedBy", "agile-lead", "predictability", "effect", "cause", "fingerprint"]) {
    assert.ok(!brut.includes(interdit), interdit);
  }
  await app.close();
});

test("a sheet moves from the list of the drafts to the list of the reviewed sheets to the list of the published ones, with its life cycle", async () => {
  const { app } = monter();
  const id = await creer(app);
  const etats = async (): Promise<Record<string, string[]>> => {
    const lire = async (etat: string): Promise<string[]> => ((await appeler(app, "GET", `/api/sheets?state=${etat}`)).corps.sheets as Array<{ id: string }>).map((f) => f.id);
    return { draft: await lire("draft"), reviewed: await lire("reviewed"), published: await lire("published") };
  };
  assert.deepEqual(await etats(), { draft: [id], reviewed: [], published: [] });
  assert.equal((await appeler(app, "POST", `/api/sheets/${id}/review`, RELECTEUR)).statut, 200);
  assert.deepEqual(await etats(), { draft: [], reviewed: [id], published: [] });
  assert.equal((await appeler(app, "POST", `/api/sheets/${id}/publish`, AUTEUR)).statut, 200);
  assert.deepEqual(await etats(), { draft: [], reviewed: [], published: [id] });
  await app.close();
});

test("reading a list needs no caller, as reading one sheet does not; an empty state is an empty list", async () => {
  const { app } = monter();
  const r = await appeler(app, "GET", "/api/sheets?state=reviewed");
  assert.equal(r.statut, 200);
  assert.deepEqual(r.corps, { sheets: [] });
  await app.close();
});

test("a state that is missing, unknown or not a word is an invalid request, and the storage is not asked", async () => {
  const { app, depot } = monter();
  for (const url of ["/api/sheets", "/api/sheets?state=", "/api/sheets?state=archived", "/api/sheets?state=DRAFT", "/api/sheets?state=draft&state=reviewed", "/api/sheets?state=%27%20OR%201=1"]) {
    const r = await appeler(app, "GET", url);
    assert.equal(r.statut, 400, url);
    assert.deepEqual(r.corps, { error: "INVALID_REQUEST" }, url);
  }
  assert.ok(!depot.appels.includes("lister"));
  await app.close();
});

test("a list is bounded: the newest sheets only", async () => {
  const depot = new DepotMemoire();
  const { app } = monter(depot);
  for (let i = 1; i <= LIMITE_LISTE_FICHES + 5; i += 1) {
    depot.fiches.set(String(i), { id: String(i), chart: "lead_cycle_h5", scope: COMPLETE.scope, dataDate: "2026-10-01", state: "draft", createdBy: "agile-lead-1" });
  }
  const r = await appeler(app, "GET", "/api/sheets?state=draft");
  const ids = (r.corps.sheets as Array<{ id: string }>).map((f) => f.id);
  assert.equal(ids.length, LIMITE_LISTE_FICHES);
  assert.equal(ids[0], String(LIMITE_LISTE_FICHES + 5));
  await app.close();
});

test("a failure of the storage is the unavailable database, without detail", async () => {
  const depot = new DepotMemoire();
  const { app, journal } = monter(depot);
  depot.echec = new BaseIndisponible();
  const r = await appeler(app, "GET", "/api/sheets?state=draft");
  assert.equal(r.statut, 503);
  assert.deepEqual(r.corps, { error: "DATABASE_UNAVAILABLE" });
  assert.ok(!journal.texte().includes("lister"));
  await app.close();
});

test("with the routes of the sheets switched off, the list answers the 404 of the application like the others", async () => {
  const { app, depot } = monter(new DepotMemoire(), { desactivees: () => true });
  const r = await appeler(app, "GET", "/api/sheets?state=draft");
  assert.equal(r.statut, 404);
  assert.deepEqual(r.corps, { error: "NOT_FOUND" });
  assert.ok(!depot.appels.includes("lister"));
  await app.close();
});
