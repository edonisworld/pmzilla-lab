// R-20261109-21 through the real route: the response schema of a by-team view declares `kind` (a field the schema does not declare is not
// serialized), names off or on; the product row first, then the row without a team, then the teams by opaque identifier. Invented teams.
import assert from "node:assert/strict";
import { test } from "node:test";

import { identifiantEquipe } from "@mothra/contract";

import { construireServeur } from "../src/routes/serveur.ts";
import { AccesFictif, contrat } from "./aide.ts";

const VUE = "v_team_ready_queue";

function equipes(): [string, string] {
  for (let i = 0; i < 200; i += 1) {
    const a = `alpha-${i}`;
    const b = `beta-${i}`;
    if (identifiantEquipe(a) > identifiantEquipe(b)) return [a, b];
  }
  throw new Error("aucune paire trouvée");
}

async function lire(rows: Array<Record<string, string | number>>, afficherNoms: boolean) {
  const acces = new AccesFictif(rows);
  const { app } = construireServeur({ contrat, acces, reglageSeuil: null, journal: false, afficherNoms, vuesServies: [VUE] });
  const reponse = await app.inject({ method: "GET", url: `/api/views/${VUE}` });
  await app.close();
  assert.equal(reponse.statusCode, 200);
  return { corps: reponse.json() as { columns: string[]; rows: Array<Record<string, unknown>> }, brut: reponse.body };
}

const ligne = (team: string, ready: number) => ({ team, quarter_start: "2026-01-01", ready });

test("names off: `kind` is served on every row, the product row then the row without a team then the teams by identifier, and no name", async () => {
  const [a, b] = equipes();
  const { corps, brut } = await lire([ligne("(produit)", 20), ligne("(sans équipe)", 20), ligne(a, 12), ligne(b, 14)], false);
  assert.ok(!corps.columns.includes("team"));
  assert.deepEqual(corps.rows.map((r) => r.kind), ["product", "no_team", "team", "team"]);
  assert.deepEqual(corps.rows.map((r) => (r.ready as { value: number }).value), [20, 20, 14, 12]);
  assert.ok(corps.rows.every((r) => !("team" in r)));
  assert.ok(!brut.includes(a) && !brut.includes(b));
});

test("names off, the product row absent: the first row is the one without a team or a team, and `kind` says which", async () => {
  const [a, b] = equipes();
  const sansProduit = await lire([ligne("(sans équipe)", 20), ligne(a, 12), ligne(b, 14)], false);
  assert.deepEqual(sansProduit.corps.rows.map((r) => r.kind), ["no_team", "team", "team"]);
  const equipesSeules = await lire([ligne(a, 12), ligne(b, 14)], false);
  assert.deepEqual(equipesSeules.corps.rows.map((r) => r.kind), ["team", "team"]);
});

test("names on: `kind` is served too and the order of the database is kept", async () => {
  const [a, b] = equipes();
  const { corps } = await lire([ligne(a, 12), ligne("(produit)", 20), ligne(b, 14)], true);
  assert.ok(corps.columns.includes("team"));
  assert.deepEqual(corps.rows.map((r) => r.team), [a, "(produit)", b]);
  assert.deepEqual(corps.rows.map((r) => r.kind), ["team", "product", "team"]);
});
