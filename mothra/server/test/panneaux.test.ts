// Task 37.1 (routes): the four routes `GET /api/panels/<code>` of the product-scope dashboard. Doubles of the access (the view
// `v_team_flow_inout` arrives with task 36.1, in another branch); the contract of the double is declared here by a literal. Raw rows with
// distinctive counts and a column the contract does not list; the mode is injected; no database.
import assert from "node:assert/strict";
import { test } from "node:test";

import { identifiantEquipe } from "@mothra/contract/equipe";
import type { Contrat, PanneauComplet, Vue } from "@mothra/contract";

import type { AccesVues, LigneBase } from "../src/db/acces.ts";
import { creerCalculPanneaux } from "../src/fiches/panneaux.ts";
import { construireServeur } from "../src/routes/serveur.ts";
import { servirPanneau } from "../src/service.ts";
import type { ModeDonnees } from "../src/service.ts";
import { AccesFictif, SENTINELLE, contrat } from "./aide.ts";
import { controler } from "./controle.ts";

const VUE_FLUX: Vue = {
  name: "v_team_flow_inout",
  schema: "flow",
  roleKind: "flow",
  countColumns: ["created", "done"],
  plainColumns: ["team", "quarter_start", "type_group"],
};
const CONTRAT: Contrat = { ...contrat, views: [...contrat.views, VUE_FLUX] };

const DEBUTS = ["2026-01-01", "2026-04-01", "2026-07-01"]; // the three closed quarters of the reading day (R-20261114-49)
const AUJOURDHUI = "2026-11-19";
const PLAGE = "from=2026-Q1&to=2026-Q3";
const REEL: ModeDonnees = { jeu: "real", comptesAutorises: false };
const SYNTHETIQUE: ModeDonnees = { jeu: "synthetic", comptesAutorises: false };
const ID_A = identifiantEquipe("team-a");
const CODES = ["stories-inout", "correction-share", "defects-inout", "blocked-share"] as const;
// A count of the row without a team: it must never be served, under any scope.
const SANS_EQUIPE = 9001;
// The real label of the row of items without a team in the view of task 36.1.
const LIBELLE_SANS_EQUIPE = "(sans équipe)";

type Modif = (ligne: LigneBase) => LigneBase;

function ligneFlux(equipe: string | null, debut: string, groupe: "story" | "defect", crees: number | null, finis: number | null): LigneBase {
  return { team: equipe, quarter_start: debut, type_group: groupe, created: crees, done: finis, ticket_key: SENTINELLE };
}

function lignesFlux(modif: Modif = (l) => l): LigneBase[] {
  const lignes: LigneBase[] = [];
  DEBUTS.forEach((d, i) => {
    lignes.push(ligneFlux("(produit)", d, "story", 100 + i, 60 - i));
    lignes.push(ligneFlux("(produit)", d, "defect", 30 + i, 20 + i));
    // H-05: the defect group has a team row too (rule of the product row, tools/flow_views.py:444); permanent, as long as that rule stands.
    lignes.push(ligneFlux("team-a", d, "defect", 10 + i, 8 + i));
    lignes.push(ligneFlux("team-a", d, "story", 50 + i, 40 + i));
    lignes.push(ligneFlux("team-b", d, "story", 70 + i, 45 + i));
    lignes.push(ligneFlux(LIBELLE_SANS_EQUIPE, d, "story", SANS_EQUIPE, SANS_EQUIPE));
  });
  return lignes.map(modif);
}

function lignesBloque(): LigneBase[] {
  const lignes: LigneBase[] = [];
  DEBUTS.forEach((d, i) => {
    lignes.push({ team: "team-a", quarter_start: d, blocked_n: 40, blocked: 12 + i, share_percent: 30 + i, ticket_key: SENTINELLE });
    lignes.push({ team: "team-b", quarter_start: d, blocked_n: 50, blocked: 20 + i, share_percent: 40 + i, ticket_key: SENTINELLE });
  });
  return lignes;
}

class AccesPanneaux implements AccesVues {
  appels: string[] = [];
  flux: LigneBase[];
  echec: Error | null;
  constructor(flux: LigneBase[] = lignesFlux(), echec: Error | null = null) {
    this.flux = flux;
    this.echec = echec;
  }
  async lireVue(vue: Vue): Promise<LigneBase[]> {
    this.appels.push(vue.name);
    if (this.echec !== null) throw this.echec;
    if (vue.name === "v_team_flow_inout") return this.flux;
    if (vue.name === "v_team_blocked_share") return lignesBloque();
    return [];
  }
}

function monter(mode: ModeDonnees, acces: AccesVues = new AccesPanneaux(), desactivees?: () => boolean) {
  const calcul = creerCalculPanneaux({ acces, contrat: CONTRAT, seuil: 5, identifiantEquipe });
  const { app } = construireServeur({
    contrat: CONTRAT,
    acces,
    reglageSeuil: null,
    journal: false,
    panneaux: { ...calcul, mode, aujourdhui: () => AUJOURDHUI, ...(desactivees === undefined ? {} : { desactivees }) },
  });
  return app;
}

// The parts of an answer the tests read (a refusal holds only `error`; the cast is the test's reading, the routes check their schemas).
interface Corps {
  error?: string;
  panel: string;
  scope: string;
  dataset: string;
  hypothesis: string;
  mentions: string[];
  limits: string[];
  points: Array<{ quarter: string } & Record<string, unknown>>;
  total: Record<string, unknown>;
}

const lire = async (app: ReturnType<typeof monter>, url: string) => {
  const r = await app.inject({ method: "GET", url });
  return { statut: r.statusCode, corps: r.json() as Corps, texte: r.body };
};

test("stories-inout, product: the product row, a total from the range, no flag on any point, no sentinel", async () => {
  const app = monter(SYNTHETIQUE);
  const { statut, corps, texte } = await lire(app, `/api/panels/stories-inout?${PLAGE}`);
  assert.equal(statut, 200);
  assert.equal(corps.panel, "stories-inout");
  assert.equal(corps.scope, "product");
  assert.equal(corps.dataset, "synthetic");
  assert.equal(corps.hypothesis, "h1_second_half");
  assert.deepEqual(corps.mentions, ["indirect_indicator"]);
  assert.deepEqual(corps.points.map((p) => p.quarter), ["2026-Q1", "2026-Q2", "2026-Q3"]);
  assert.deepEqual(corps.points[0].created, { state: "value", value: 100 });
  assert.ok(corps.points.every((p) => !("flags" in p)), "the truncated-quarter flag is gone");
  // The product is never a sum of teams, nor the row without a team: 100 + 101 + 102 = 303 (R-20261114-49; before: four quarters, 406).
  assert.deepEqual(corps.total.created, { state: "value", value: 303 });
  assert.ok(!texte.includes(String(SANS_EQUIPE)));
  assert.ok(!texte.includes(SENTINELLE));
  await app.close();
});

test("stories-inout, a team: only the rows whose team gives the requested identifier", async () => {
  const app = monter(SYNTHETIQUE);
  const { statut, corps } = await lire(app, `/api/panels/stories-inout?team=${ID_A}&${PLAGE}`);
  assert.equal(statut, 200);
  assert.equal(corps.scope, `team.${ID_A}`);
  assert.deepEqual(corps.points[0].created, { state: "value", value: 50 });
  assert.deepEqual(corps.total.created, { state: "value", value: 50 + 51 + 52 });      // 153 (before: four quarters, 206)
  await app.close();
});

test("stories-inout, a team without rows: every point is a masked cell, nothing is estimated", async () => {
  const app = monter(SYNTHETIQUE);
  const { statut, corps } = await lire(app, `/api/panels/stories-inout?team=${identifiantEquipe("team-z")}&${PLAGE}`);
  assert.equal(statut, 200);
  assert.deepEqual(corps.points[2].created, { state: "masked", threshold: 5 });
  assert.deepEqual(corps.total.created, { state: "masked", threshold: 5 });
  await app.close();
});

test("a scope forged from the label of the row without a team gives masked points: that row is never served", async () => {
  const app = monter(SYNTHETIQUE);
  const { statut, corps, texte } = await lire(app, `/api/panels/stories-inout?team=${identifiantEquipe(LIBELLE_SANS_EQUIPE)}&${PLAGE}`);
  assert.equal(statut, 200);
  assert.deepEqual(corps.points[0].created, { state: "masked", threshold: 5 });
  assert.deepEqual(corps.total.created, { state: "masked", threshold: 5 });
  assert.ok(!texte.includes(String(SANS_EQUIPE)));
  await app.close();
});

test("a NULL count of the view is a masked cell and the range total is masked with it", async () => {
  const sansUn = (l: LigneBase): LigneBase =>
    l.team === "(produit)" && l.type_group === "story" && l.quarter_start === "2026-04-01" ? { ...l, created: null } : l;
  const app = monter(SYNTHETIQUE, new AccesPanneaux(lignesFlux(sansUn)));
  const { corps } = await lire(app, `/api/panels/stories-inout?${PLAGE}`);
  assert.deepEqual(corps.points[1].created, { state: "masked", threshold: 5 });      // 2026-Q2 is the second of the three quarters (the third of four before)
  assert.deepEqual(corps.total.created, { state: "masked", threshold: 5 });
  assert.deepEqual(corps.total.done, { state: "value", value: 60 + 59 + 58 });      // 177 (before: four quarters, 234)
  await app.close();
});

test("defects-inout: the product row, whatever the team asked", async () => {
  const app = monter(SYNTHETIQUE);
  const { statut, corps } = await lire(app, `/api/panels/defects-inout?team=${ID_A}&${PLAGE}`);
  assert.equal(statut, 200);
  assert.equal(corps.panel, "defects-inout");
  assert.equal(corps.scope, "product");
  assert.deepEqual(corps.mentions, ["indirect_indicator", "product_level"]);
  assert.deepEqual(corps.points[0].created, { state: "value", value: 30 });
  assert.deepEqual(corps.points[0].done, { state: "value", value: 20 });
  await app.close();
});

test("correction-share: the share of the product row, given only when neither term is masked", async () => {
  const app = monter(SYNTHETIQUE);
  const { statut, corps } = await lire(app, `/api/panels/correction-share?${PLAGE}`);
  assert.equal(statut, 200);
  assert.equal(corps.scope, "product");
  assert.deepEqual(corps.points[0].share, { state: "value", value: 25 }); // 20 / (20 + 60)
  await app.close();
  const sansDefaut = (l: LigneBase): LigneBase =>
    l.team === "(produit)" && l.type_group === "defect" && l.quarter_start === "2026-01-01" ? { ...l, done: null } : l;
  const masque = monter(SYNTHETIQUE, new AccesPanneaux(lignesFlux(sansDefaut)));
  const m = await lire(masque, `/api/panels/correction-share?${PLAGE}`);
  assert.deepEqual(m.corps.points[0].share, { state: "masked", threshold: 5 });      // 2026-Q1 is the first of the three quarters (the second of four before)
  assert.ok(!JSON.stringify(m.corps.points[0]).includes("defectsDone\":{\"state\":\"value\""));
  await masque.close();
});

test("blocked-share, a team: the rows of the view for the team, with both mentions", async () => {
  const app = monter(SYNTHETIQUE);
  const { statut, corps } = await lire(app, `/api/panels/blocked-share?team=${ID_A}&${PLAGE}`);
  assert.equal(statut, 200);
  assert.equal(corps.scope, `team.${ID_A}`);
  assert.deepEqual(corps.mentions, ["indirect_indicator", "blocked_share_current_links"]);
  assert.deepEqual(corps.points[0].blocked, { state: "value", value: 12 });
  assert.deepEqual(corps.points[0].blockedN, { state: "value", value: 40 });
  assert.deepEqual(corps.points[0].share, { state: "value", value: 30 });
  await app.close();
});

test("blocked-share on the product scope: 422 SCOPE_INVALID, nothing is read", async () => {
  const acces = new AccesPanneaux();
  const app = monter(SYNTHETIQUE, acces);
  const { statut, corps } = await lire(app, `/api/panels/blocked-share?${PLAGE}`);
  assert.equal(statut, 422);
  assert.deepEqual(corps, { error: "SCOPE_INVALID" });
  assert.deepEqual(acces.appels, []);
  await app.close();
});

test("every route: outside the schema 400 INVALID_REQUEST; a bad scope or range 422 with the code of the filters", async () => {
  const app = monter(SYNTHETIQUE);
  for (const code of CODES) {
    const base = `/api/panels/${code}`;
    for (const url of [`${base}?${PLAGE}&sort=team`, `${base}?from=2025-Q4`, `${base}`, `${base}?${PLAGE}&extra=1`]) {
      const r = await lire(app, url);
      assert.equal(r.statut, 400, url);
      assert.deepEqual(r.corps, { error: "INVALID_REQUEST" }, url);
    }
    const equipeMalformee = await lire(app, `${base}?team=A%20B&${PLAGE}`);
    assert.equal(equipeMalformee.statut, 422, code);
    assert.deepEqual(equipeMalformee.corps, { error: "SCOPE_INVALID" }, code);
    const deuxEquipes = await lire(app, `${base}?team=${ID_A}&team=${ID_A}&${PLAGE}`);
    assert.equal(deuxEquipes.statut, 422, code);
    assert.deepEqual(deuxEquipes.corps, { error: "SCOPE_INVALID" }, code);
    const plageEnCours = await lire(app, `${base}?team=${ID_A}&from=2026-Q4&to=2026-Q4`);
    assert.equal(plageEnCours.statut, 422, code);
    assert.deepEqual(plageEnCours.corps, { error: "RANGE_INVALID" }, code);
  }
  await app.close();
});

test("a database failure is answered 503 DATABASE_UNAVAILABLE, a fault 500 INTERNAL, codes only", async () => {
  for (const code of CODES) {
    const equipe = code === "blocked-share" ? `team=${ID_A}&` : "";
    const indisponible = monter(SYNTHETIQUE, new AccesPanneaux(lignesFlux(), new Error("details that must not come out")));
    const r = await lire(indisponible, `/api/panels/${code}?${equipe}${PLAGE}`);
    assert.equal(r.statut, 503, code);
    assert.deepEqual(r.corps, { error: "DATABASE_UNAVAILABLE" }, code);
    await indisponible.close();
    // A fault of the service itself (a row the view cannot give): not a database failure.
    const defaut = monter(SYNTHETIQUE, new AccesPanneaux(lignesFlux((l) => ({ ...l, type_group: "epic" }))));
    if (code !== "blocked-share") {
      const p = await lire(defaut, `/api/panels/${code}?${PLAGE}`);
      assert.equal(p.statut, 500, code);
      assert.deepEqual(p.corps, { error: "INTERNAL" }, code);
    }
    await defaut.close();
  }
});

test("real dataset, counts not allowed: the reduced form for the four panels, no point, no total, no count, no sentinel", async () => {
  const app = monter(REEL);
  for (const code of CODES) {
    const equipe = code === "blocked-share" ? `team=${ID_A}&` : "";
    const { statut, corps, texte } = await lire(app, `/api/panels/${code}?${equipe}${PLAGE}`);
    assert.equal(statut, 200, code);
    assert.equal(corps.dataset, "real", code);
    assert.deepEqual(corps.limits, ["reduced_form"], code);
    assert.equal(corps.panel, code);
    for (const cle of ["points", "total"]) assert.ok(!(cle in corps), `${code} ${cle}`);
    for (const nombre of ["100", "303", "9001", "12", "40"]) {
      assert.ok(!new RegExp(`(?<![0-9.])${nombre}(?![0-9])`).test(texte), `${code} ${nombre}`);
    }
    assert.ok(!texte.includes("created") && !texte.includes("done") && !texte.includes("\"share\":"), code);
  }
  await app.close();
});

test("servirPanneau: the reduction is the service's; once the counts are allowed on real data the panel is complete again", () => {
  const plein = {
    panel: "stories-inout",
    scope: "product",
    from: "2026-Q1",
    to: "2026-Q3",
    threshold: 5,
    dataDate: AUJOURDHUI,
    hypothesis: "h1_second_half",
    mentions: ["indirect_indicator"],
    points: [],
    total: { created: { state: "masked", threshold: 5 }, done: { state: "masked", threshold: 5 } },
    dataset: "real",
  } satisfies PanneauComplet;
  assert.ok(!("points" in servirPanneau(plein, REEL)));
  assert.deepEqual(servirPanneau(plein, { jeu: "real", comptesAutorises: true }), plein);
  assert.deepEqual(servirPanneau(plein, SYNTHETIQUE), plein);
});

test("the no real data walk of tasks 6.7 and 18.2 extended to the four routes: no key, no sentinel, in either mode", async () => {
  for (const mode of [SYNTHETIQUE, REEL]) {
    const app = monter(mode);
    for (const code of CODES) {
      const equipe = code === "blocked-share" ? `team=${ID_A}&` : "";
      const r = await app.inject({ method: "GET", url: `/api/panels/${code}?${equipe}${PLAGE}` });
      assert.equal(r.statusCode, 200, code);
      assert.deepEqual(controler(`GET /api/panels/${code}`, r.json(), [], [SENTINELLE]), [], code);
    }
    await app.close();
  }
});

test("the routes are cut after a collision of identifiers, like the sheets: the existing 404", async () => {
  const acces = new AccesPanneaux();
  const app = monter(SYNTHETIQUE, acces, () => true);
  for (const code of CODES) {
    const r = await lire(app, `/api/panels/${code}?${PLAGE}`);
    assert.equal(r.statut, 404, code);
    assert.deepEqual(r.corps, { error: "NOT_FOUND" }, code);
  }
  assert.deepEqual(acces.appels, []);
  await app.close();
});

test("an access double of the generic kind is never asked for a view outside the panel", async () => {
  const acces = new AccesFictif([]);
  const app = monter(SYNTHETIQUE, acces);
  await lire(app, `/api/panels/stories-inout?${PLAGE}`);
  assert.deepEqual(acces.appels, ["v_team_flow_inout"]);
  await app.close();
});
