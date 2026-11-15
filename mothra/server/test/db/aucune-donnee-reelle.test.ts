// Task 6.7: the permanent "no real data" test of the API. It walks every registered route on witness data (counts 1 to 4, exactly 5,
// a NULL, sentinel strings and a ticket-key shape in columns no view exposes) and fails naming the route and the kind of finding,
// never the value. The same walk runs on the synthetic dataset of the throwaway database when DBTEST_PORT is set.
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { after, before, test } from "node:test";

import { lireEnvironnement } from "../../src/config/index.ts";
import { creerAccesPostgres } from "../../src/db/base.ts";
import { construireServeur } from "../../src/routes/serveur.ts";
import { AccesFictif, SENTINELLE, contrat, ligneStatut, sautBaseJetable } from "../aide.ts";
import { controler } from "../controle.ts";
import type { Constat } from "../controle.ts";
import { creerBaseJetable } from "./base-jetable.ts";
import type { BaseJetable } from "./base-jetable.ts";

const saut = sautBaseJetable();
let base: BaseJetable | null = null;

before(async () => {
  if (saut === false) {
    base = await creerBaseJetable(lireEnvironnement());
  }
});

after(async () => {
  await base?.supprimer();
});

const colonnesDeCompte = contrat.views.flatMap((v) => v.countColumns);

function fauxDossierBundle(): string {
  const dossier = mkdtempSync(join(tmpdir(), "mothra-donnee-"));
  writeFileSync(join(dossier, "index.html"), "<!doctype html><title>faux bundle</title><div id=racine></div>");
  return dossier;
}

async function parcourirRoutes(
  acces: { lireVue: AccesFictif["lireVue"] },
  sentinelles: readonly string[],
  afficherNoms = false,
): Promise<{ constats: Constat[]; visitees: string[] }> {
  // A fake bundle folder (a page of plain markup), never mothra/front/dist: the walk does not depend on the built front.
  const { app, routes } = construireServeur({ contrat, acces, reglageSeuil: null, journal: false, dossierBundle: fauxDossierBundle(), afficherNoms });
  const constats: Constat[] = [];
  const visitees: string[] = [];
  for (const route of routes) {
    const urls = route.url.includes(":view") ? contrat.views.map((v) => route.url.replace(":view", v.name)) : [route.url];
    for (const url of urls) {
      const reponse = await app.inject({ method: route.method as "GET", url });
      visitees.push(`${route.method} ${url}`);
      // The bundle routes answer a page (text) or a code (JSON, bundle not built): the walk looks at the body as it is.
      // A page is looked at for sentinels only: a ticket-key shape in markup ("UTF-8") is no finding; the bundle test of task 7.5 owns it.
      let corps: unknown;
      let page = false;
      try {
        corps = reponse.json();
      } catch {
        corps = { texte: reponse.body };
        page = true;
      }
      constats.push(
        ...controler(`${route.method} ${route.url}`, corps, colonnesDeCompte, sentinelles).filter(
          (c) => !(page && c.kind === "forme de clé de ticket"),
        ),
      );
    }
  }
  await app.close();
  return { constats, visitees };
}

const TEMOINS = [
  ligneStatut("Team A", 12),
  ligneStatut("Team B", 5),
  ligneStatut("Team C", 4, { champ_hors_vue: SENTINELLE }),
  ligneStatut("Team D", 3, { key: "ABC-123", title: SENTINELLE }),
  ligneStatut("Team E", 2),
  ligneStatut("Team F", 1),
  ligneStatut("Team G", null),
  ligneStatut("Team H", "0"),
];

test("the checker names the route and the kind of a value under the threshold, a ticket key shape and a sentinel, never the value", () => {
  const route = "GET /api/views/v_team_status";
  const sous = controler(route, { threshold: 5, rows: [{ tickets: { state: "value", value: 3 } }] }, ["tickets"], []);
  assert.deepEqual(sous, [{ route, kind: "valeur sous le seuil" }]);
  const cle = controler(route, { threshold: 5, rows: [{ team: "ABC-123" }] }, ["tickets"], []);
  assert.deepEqual(cle, [{ route, kind: "forme de clé de ticket" }]);
  const sentinelle = controler(route, { threshold: 5, rows: [{ team: `x ${SENTINELLE}` }] }, ["tickets"], [SENTINELLE]);
  assert.deepEqual(sentinelle, [{ route, kind: "sentinelle" }]);
  const masqueeAvecValeur = controler(route, { threshold: 5, rows: [{ tickets: { state: "masked", threshold: 5, value: 3 } }] }, ["tickets"], []);
  assert.deepEqual(masqueeAvecValeur, [{ route, kind: "valeur sous le seuil" }]);
  for (const constat of [...sous, ...cle, ...sentinelle]) {
    assert.deepEqual(Object.keys(constat).sort(), ["kind", "route"]);
  }
});

test("a value cell at the threshold and a masked cell are not findings", () => {
  const corps = { threshold: 5, rows: [{ tickets: { state: "value", value: 5 } }, { tickets: { state: "masked", threshold: 5 } }] };
  assert.deepEqual(controler("r", corps, ["tickets"], []), []);
});

test("every registered route, walked on the witness data, holds no value under the threshold, no ticket key and no sentinel", async () => {
  const acces = new AccesFictif(TEMOINS);
  const { constats, visitees } = await parcourirRoutes(acces, [SENTINELLE]);
  assert.deepEqual(constats, []);
  // The walk visits every view of the contract: the served one, then the five aggregated views of slice 1 (task 15.2), which answer UNKNOWN_VIEW
  // as long as the server serves slice 0 only.
  assert.deepEqual(visitees, [
    "GET /api/views/v_team_status",
    "GET /api/views/v_team_lead_time_throughput",
    "GET /api/views/v_task_without_team_share",
    "GET /api/views/v_team_ready_queue",
    "GET /api/views/v_team_blocked_share",
    "GET /api/views/v_unplanned_share",
    "GET /api/views/v_team_flow_inout",
    "GET /",
    "GET /*",
  ]);
});

test("the witness with 3 resolved tickets is masked in its count column", async () => {
  const acces = new AccesFictif([ligneStatut("Team A", 3)]);
  const { app } = construireServeur({ contrat, acces, reglageSeuil: null, journal: false });
  const reponse = await app.inject({ method: "GET", url: "/api/views/v_team_status" });
  await app.close();
  const rows = (reponse.json() as { rows: Array<Record<string, unknown>> }).rows;
  assert.deepEqual(rows[0].tickets, { state: "masked", threshold: 5 });
});

test("a defect copying a sentinel into an answer is caught, naming the route and the finding", async () => {
  // The sentinel rides in the team name, which the generic route serves only with the team-name setting on (R-20261104-69 Q1):
  // the checker is exercised on that path; with the setting off the name is not served at all.
  const acces = new AccesFictif([ligneStatut(`Team ${SENTINELLE}`, 12)]);
  const { constats } = await parcourirRoutes(acces, [SENTINELLE], true);
  assert.deepEqual(constats, [{ route: "GET /api/views/:view", kind: "sentinelle" }]);
  // Setting off: the same defect cannot copy the sentinel into an answer, since the name is removed by the service layer.
  const { constats: horsReglage } = await parcourirRoutes(acces, [SENTINELLE]);
  assert.deepEqual(horsReglage, []);
});

test("on the synthetic dataset of the throwaway database, every route holds no finding", { skip: saut }, async () => {
  assert.ok(base !== null, "the throwaway database was not created");
  const acces = creerAccesPostgres(base.configuration());
  try {
    const { constats } = await parcourirRoutes(acces, [SENTINELLE, "SENTINELLE", "SENTINEL"]);
    assert.deepEqual(constats, []);
  } finally {
    await acces.fermer();
  }
});
