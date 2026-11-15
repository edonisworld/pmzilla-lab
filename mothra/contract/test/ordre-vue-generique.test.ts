// Audit #629, A-79 residue (Q238, R-20261107-30, R-20261109-20, R-20261109-21): on the generic route, names off, the rows come with the product
// row first, then the row without a team, then the teams in the order of their opaque identifiers, never of the names (the column `team` is
// left out, so an alphabetical order would betray the names). Every row of a by-team view carries `kind`. Names on: the order given by the
// database (R-20261104-69 Q2), untouched. Invented teams.
import assert from "node:assert/strict";
import { test } from "node:test";

import Value from "typebox/value";

import { chargerContrat } from "../src/chargeur.ts";
import { identifiantEquipe, LIBELLE_PRODUIT, LIBELLE_SANS_EQUIPE } from "../src/equipe.ts";
import { servirVue } from "../src/reduction.ts";
import { schemaReponseDeVue } from "../src/reponse.ts";
import type { LigneReponse, ReponseVue } from "../src/reponse.ts";
import type { Vue } from "../src/vues.ts";

// Two teams whose alphabetical order of names is the inverse of the order of their identifiers (checked below, not assumed).
function deuxEquipes(): [string, string] {
  for (let i = 0; i < 200; i += 1) {
    const a = `alpha-${i}`;
    const b = `beta-${i}`;
    if (identifiantEquipe(a) > identifiantEquipe(b)) return [a, b];
  }
  throw new Error("aucune paire trouvée");
}

// `note` tells the rows apart once `team` is gone: the first letter of the team stands for it, the digit for the period.
function lignesDe(team: string, lettre: string): LigneReponse[] {
  return [
    { team, period: "2026-Q1", note: `${lettre}1` },
    { team, period: "2026-Q2", note: `${lettre}2` },
  ];
}

function reponse(rows: LigneReponse[], columns = ["team", "period", "note"]): ReponseVue {
  return { view: "v_x", threshold: 5, columns, rows, sources: [] };
}

const notes = (r: ReponseVue): unknown[] => r.rows.map((l) => l.note);
const genres = (r: ReponseVue): unknown[] => r.rows.map((l) => l.kind);

test("names off: the rows follow the order of the opaque identifiers, not of the names, and keep their order inside a team", () => {
  const [a, b] = deuxEquipes();
  assert.ok(a < b && identifiantEquipe(a) > identifiantEquipe(b), "précondition : ordre des noms inverse de l'ordre des identifiants");
  // The database gives the alphabetical order of the names: a, then b.
  const servie = servirVue(reponse([...lignesDe(a, "x"), ...lignesDe(b, "y")]), { afficherNoms: false });
  assert.deepEqual(servie.columns, ["period", "note"]);
  // b comes first (its identifier is the smaller), then a; each team keeps Q1 then Q2.
  assert.deepEqual(notes(servie), ["y1", "y2", "x1", "x2"]);
});

test("names off: the order of the rows is the same whichever order the database gave", () => {
  const [a, b] = deuxEquipes();
  const dansUnSens = servirVue(reponse([...lignesDe(a, "x"), ...lignesDe(b, "y")]), { afficherNoms: false });
  const dansLautre = servirVue(reponse([...lignesDe(b, "y"), ...lignesDe(a, "x")]), { afficherNoms: false });
  assert.deepEqual(notes(dansUnSens), ["y1", "y2", "x1", "x2"]);
  assert.deepEqual(dansUnSens.rows, dansLautre.rows);
});

test("names off: the product row first, then the row without a team, then the teams by identifier, whatever the order of the database", () => {
  const [a, b] = deuxEquipes();
  const base = [
    ...lignesDe(LIBELLE_PRODUIT, "p"),
    ...lignesDe(LIBELLE_SANS_EQUIPE, "s"),
    ...lignesDe(a, "x"),
    ...lignesDe(b, "y"),
  ];
  const attendu = ["p1", "p2", "s1", "s2", "y1", "y2", "x1", "x2"];
  // The database orders by name: "(produit)" and "(sans équipe)" sit among the teams by collation. Tried in several orders.
  const groupesInverses = [...lignesDe(b, "y"), ...lignesDe(a, "x"), ...lignesDe(LIBELLE_SANS_EQUIPE, "s"), ...lignesDe(LIBELLE_PRODUIT, "p")];
  for (const rows of [base, groupesInverses, [...lignesDe(a, "x"), ...lignesDe(LIBELLE_SANS_EQUIPE, "s"), ...lignesDe(b, "y"), ...lignesDe(LIBELLE_PRODUIT, "p")]]) {
    const servie = servirVue(reponse(rows), { afficherNoms: false });
    assert.deepEqual(notes(servie), attendu);
    assert.deepEqual(genres(servie), ["product", "product", "no_team", "no_team", "team", "team", "team", "team"]);
  }
});

test("names off: `kind` is on every row, is one of the three values and holds no name", () => {
  const [a, b] = deuxEquipes();
  const servie = servirVue(reponse([...lignesDe(LIBELLE_PRODUIT, "p"), ...lignesDe(LIBELLE_SANS_EQUIPE, "s"), ...lignesDe(a, "x"), ...lignesDe(b, "y")]), { afficherNoms: false });
  for (const ligne of servie.rows) {
    assert.ok(["product", "no_team", "team"].includes(ligne.kind as string), JSON.stringify(ligne));
    assert.ok(!("team" in ligne));
  }
  assert.ok(!JSON.stringify(servie).includes(a) && !JSON.stringify(servie).includes(b));
});

test("names off: the product row masked and absent (H-05): the first row is the one without a team or a team, and `kind` says which", () => {
  const [a, b] = deuxEquipes();
  const sansProduit = servirVue(reponse([...lignesDe(LIBELLE_SANS_EQUIPE, "s"), ...lignesDe(a, "x"), ...lignesDe(b, "y")]), { afficherNoms: false });
  assert.deepEqual(genres(sansProduit), ["no_team", "no_team", "team", "team", "team", "team"]);
  assert.equal(sansProduit.rows[0].kind, "no_team");
  const equipesSeules = servirVue(reponse([...lignesDe(a, "x"), ...lignesDe(b, "y")]), { afficherNoms: false });
  assert.deepEqual(genres(equipesSeules), ["team", "team", "team", "team"]);
  assert.equal(equipesSeules.rows[0].kind, "team");
});

test("names on: the order of the database is kept, and `kind` is there too", () => {
  const [a, b] = deuxEquipes();
  const plein = reponse([...lignesDe(LIBELLE_PRODUIT, "p"), ...lignesDe(a, "x"), ...lignesDe(LIBELLE_SANS_EQUIPE, "s"), ...lignesDe(b, "y")]);
  const servie = servirVue(plein, { afficherNoms: true });
  assert.deepEqual(servie.columns, ["team", "period", "note"]);
  assert.deepEqual(notes(servie), ["p1", "p2", "x1", "x2", "s1", "s2", "y1", "y2"]);
  assert.deepEqual(servie.rows.map((r) => r.team), [LIBELLE_PRODUIT, LIBELLE_PRODUIT, a, a, LIBELLE_SANS_EQUIPE, LIBELLE_SANS_EQUIPE, b, b]);
  assert.deepEqual(genres(servie), ["product", "product", "team", "team", "no_team", "no_team", "team", "team"]);
});

test("a view with no column `team`: no `kind`, the rows keep the order of the database, names on or off", () => {
  const rows: LigneReponse[] = [
    { quarter_start: "2026-04-01", x: 2 },
    { quarter_start: "2026-01-01", x: 1 },
    { quarter_start: "2026-07-01", x: 3 },
  ];
  for (const afficherNoms of [false, true]) {
    const servie = servirVue(reponse(rows, ["quarter_start", "x"]), { afficherNoms });
    assert.deepEqual(servie.rows, rows);
    assert.ok(servie.rows.every((r) => !("kind" in r)));
    assert.deepEqual(servie.columns, ["quarter_start", "x"]);
  }
});

test("a `team` that is NULL is a row without a team: it comes before the teams and keeps the order of the database among its kind", () => {
  const [a, b] = deuxEquipes();
  const rows: LigneReponse[] = [
    { team: a, period: "p", note: "x" },
    { team: null, period: "p", note: "n1" },
    { team: b, period: "p", note: "y" },
    { team: LIBELLE_SANS_EQUIPE, period: "p", note: "n2" },
  ];
  const servie = servirVue(reponse(rows), { afficherNoms: false });
  assert.deepEqual(notes(servie), ["n1", "n2", "y", "x"]);
  assert.deepEqual(genres(servie), ["no_team", "no_team", "team", "team"]);
});

// R-20261109-22: `kind` is REQUIRED in the schema of a by-team view (names shown or not) and absent from a view with no column `team`.
const VUE_PAR_EQUIPE: Vue = { name: "v_x", schema: "flow", roleKind: "flow", countColumns: ["n"], plainColumns: ["team", "period"] };
const VUE_SANS_EQUIPE: Vue = { name: "v_y", schema: "flow", roleKind: "flow", countColumns: ["n"], plainColumns: ["period"] };
const CELLULE = { state: "value", value: 12 };

function reponseDe(vue: Vue, rows: Array<Record<string, unknown>>) {
  return { view: vue.name, threshold: 5, columns: [], rows, sources: [] };
}

test("a row of a by-team view without `kind` is refused by the schema, names shown or not; with a valid `kind` it is accepted", () => {
  for (const sansNom of [false, true]) {
    const schema = schemaReponseDeVue(VUE_PAR_EQUIPE, { sansNom });
    const base: Record<string, unknown> = sansNom ? { period: "p", n: CELLULE } : { team: "A", period: "p", n: CELLULE };
    assert.equal(Value.Check(schema, reponseDe(VUE_PAR_EQUIPE, [base])), false, `sans kind, sansNom=${sansNom}`);
    for (const genre of ["product", "no_team", "team"]) {
      assert.equal(Value.Check(schema, reponseDe(VUE_PAR_EQUIPE, [{ ...base, kind: genre }])), true, `${genre}, sansNom=${sansNom}`);
    }
    assert.equal(Value.Check(schema, reponseDe(VUE_PAR_EQUIPE, [{ ...base, kind: "autre" }])), false, `kind inconnu, sansNom=${sansNom}`);
    assert.equal(Value.Check(schema, reponseDe(VUE_PAR_EQUIPE, [{ ...base, kind: "team" }, { ...base }])), false, `une ligne sans kind, sansNom=${sansNom}`);
  }
});

test("a view with no column `team` carries no `kind`: a row with one is refused, a row without is accepted", () => {
  const schema = schemaReponseDeVue(VUE_SANS_EQUIPE);
  assert.equal(Value.Check(schema, reponseDe(VUE_SANS_EQUIPE, [{ period: "p", n: CELLULE }])), true);
  assert.equal(Value.Check(schema, reponseDe(VUE_SANS_EQUIPE, [{ period: "p", n: CELLULE, kind: "team" }])), false);
});

test("in the contract, the two views with no column `team` have no `kind`, every other view with one requires it", () => {
  const contrat = chargerContrat(new URL("../../../contrats/vues.json", import.meta.url));
  const sansEquipe = contrat.views.filter((v) => !v.plainColumns.includes("team")).map((v) => v.name);
  assert.ok(sansEquipe.includes("v_task_without_team_share") && sansEquipe.includes("v_unplanned_share"));
  for (const vue of contrat.views) {
    const proprietes = (schemaReponseDeVue(vue) as unknown as { properties: { rows: { items: { properties: Record<string, unknown>; required: string[] } } } })
      .properties.rows.items;
    if (vue.plainColumns.includes("team")) {
      assert.ok("kind" in proprietes.properties && proprietes.required.includes("kind"), vue.name);
    } else {
      assert.ok(!("kind" in proprietes.properties), vue.name);
    }
  }
});
