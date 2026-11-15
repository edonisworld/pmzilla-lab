// Task 15.3: the masking of the rows of a served view (masquerVue), played against the synthetic cases shared with the Python reader
// (contrats/cas-vues-tranche1.json), plus the properties no case can state: the floor, the structured cell, nothing of a masked value kept.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { chargerContrat } from "../src/chargeur.ts";
import { type Cellule, colonneAvecZero, SchemaCellule, SchemaCelluleAnciens, SchemaCelluleMesuree } from "../src/cellule.ts";
import { type LigneBrute, masquerVue } from "../src/masquage.ts";
import { PLANCHER } from "../src/plancher.ts";
import type { Vue } from "../src/vues.ts";
import Value from "typebox/value";

const RACINE = new URL("../../../contrats/", import.meta.url);
const CONTRAT = chargerContrat(new URL("vues.json", RACINE));

interface CasVueServie {
  id: string;
  title: string;
  view: string;
  threshold: number;
  cells: string[];
  rows: Record<string, number | string | null>[];
  masked: [number, string][];
}

const FICHIER = JSON.parse(readFileSync(new URL("cas-vues-tranche1.json", RACINE), "utf8")) as { players: string[]; cases: CasVueServie[] };

function vueDuContrat(nom: string): Vue {
  const vue = CONTRAT.views.find((v) => v.name === nom);
  assert.ok(vue, nom);
  return vue;
}

function brutes(vue: Vue, cas: CasVueServie): LigneBrute[] {
  const colonnes = [...vue.plainColumns, ...(vue.maskableColumns ?? []), ...vue.countColumns];
  return cas.rows.map((ligne) => Object.fromEntries(colonnes.map((c) => [c, ligne[c] ?? null])));
}

function estCelluleMasquee(x: unknown): boolean {
  return typeof x === "object" && x !== null && (x as Cellule).state === "masked";
}

test("the shared file lists both players and holds unique case identifiers", () => {
  assert.deepEqual([...FICHIER.players].sort(), ["npm", "python"]);
  const ids = FICHIER.cases.map((c) => c.id);
  assert.equal(new Set(ids).size, ids.length);
  assert.ok(ids.length > 0);
});

for (const cas of FICHIER.cases) {
  test(`shared case ${cas.id}: ${cas.title}`, () => {
    const vue = vueDuContrat(cas.view);
    const entree = brutes(vue, cas);
    const sortie = masquerVue(vue, entree, cas.threshold);
    assert.equal(sortie.length, entree.length);
    const masquees: [number, string][] = [];
    sortie.forEach((ligne, i) => {
      for (const col of cas.cells) {
        const cellule = ligne[col];
        const brut = entree[i][col];
        if (vue.countColumns.includes(col)) {
          // R-20261106-39, R-20261106-43 (Q2 (a)): items_old of the lead time view may hold the shown zero
          assert.ok(Value.Check(colonneAvecZero(vue.name, col) ? SchemaCelluleAnciens : SchemaCellule, cellule), `${cas.id} ${i} ${col} is a structured cell`);
          if (estCelluleMasquee(cellule)) {
            masquees.push([i, col]);
          } else {
            assert.deepEqual(cellule, { state: "value", value: brut }, `${cas.id} ${i} ${col}`);
          }
        } else if (vue.maskableColumns?.includes(col)) {
          assert.ok(Value.Check(SchemaCelluleMesuree, cellule), `${cas.id} ${i} ${col} is a structured cell`);
          if (estCelluleMasquee(cellule)) {
            masquees.push([i, col]);
          } else {
            assert.deepEqual(cellule, { state: "value", value: brut }, `${cas.id} ${i} ${col}`);
          }
        } else {
          assert.equal(cellule, brut, `${cas.id} ${i} ${col}: a plain value is never altered`);
        }
      }
    });
    const ordre = (a: [number, string], b: [number, string]): number => a[0] - b[0] || a[1].localeCompare(b[1]);
    assert.deepEqual([...masquees].sort(ordre), [...cas.masked].sort(ordre), `${cas.id}: ${cas.title}`);
  });
}

test("a threshold under the floor is raised to it: 4 is masked and the masked cell carries the floor", () => {
  const vue = vueDuContrat("v_team_status");
  const lignes: LigneBrute[] = [
    { team: "A", type: "Story", status_category: "Done", status: "Closed", tickets: 4 },
    { team: "A", type: "Story", status_category: "Done", status: "Open", tickets: 5 },
  ];
  const [a, b] = masquerVue(vue, lignes, 2);
  assert.deepEqual(a.tickets, { state: "masked", threshold: PLANCHER });
  assert.deepEqual(b.tickets, { state: "value", value: 5 });
});

test("a masked cell keeps nothing of the count: no value property, whatever the rule that masked it", () => {
  const vue = vueDuContrat("v_team_lead_time_throughput");
  const ligne: LigneBrute = {
    team: "A", period: "quarter", quarter_start: "2026-01-01", throughput: 20, items_lt: 15, lead_median_days: 3, lead_p85_days: 9,
    items_ct: 6, cycle_median_days: 4, cycle_p85_days: 8, items_old: 0, items_without_commitment: 14,
  };
  const [sortie] = masquerVue(vue, [ligne], 10);
  for (const col of vue.countColumns) {
    const cellule = sortie[col] as Cellule;
    if (cellule.state === "masked") {
      assert.deepEqual(Object.keys(cellule).sort(), ["state", "threshold"], col);
    }
  }
  assert.ok(!JSON.stringify(sortie).includes('"value":15'));
  assert.ok(!JSON.stringify(sortie).includes('"value":6'));
  assert.ok(!JSON.stringify(sortie).includes('"value":14'));
});

test("without the period column the series of the lead time view is entirely masked (fail-closed)", () => {
  const vue = vueDuContrat("v_team_lead_time_throughput");
  const sansPeriode: Vue = { ...vue, plainColumns: vue.plainColumns.filter((c) => c !== "period") };
  const ligne: LigneBrute = { team: "A", quarter_start: "2026-01-01", throughput: 80, items_lt: 80, items_ct: 80, items_old: 80, items_without_commitment: 80 };
  const [sortie] = masquerVue(sansPeriode, [ligne], 10);
  for (const col of vue.countColumns) {
    assert.equal(estCelluleMasquee(sortie[col]), true, col);
  }
});

test("the raised threshold never shows a value the floor-only rule would: grid of the simple count view from 0 to 14 at threshold 10", () => {
  const vue = vueDuContrat("v_team_ready_queue");
  for (let n = 0; n <= 14; n += 1) {
    const [sortie] = masquerVue(vue, [{ team: "A", quarter_start: "2026-01-01", ready: n }], 10);
    assert.equal(estCelluleMasquee(sortie.ready), n < 10, String(n));
  }
});

test("a view whose rules between views are not ported is refused, never served with the primary rule alone", () => {
  for (const nom of ["v_teams", "v_team_jira_ids", "v_team_fix_version_share", "v_team_fix_version_lag", "v_version_quality_photo", "issues"]) {
    const vue: Vue = { name: nom, schema: "flow", roleKind: "flow", countColumns: ["tickets"], plainColumns: ["team"] };
    assert.throws(() => masquerVue(vue, [{ team: "A", tickets: 40 }], 5), /masquage non porté/, nom);
  }
});

test("a count that is not a non-negative integer or NULL, and a threshold that is not an integer, are refused", () => {
  const vue = vueDuContrat("v_team_ready_queue");
  assert.throws(() => masquerVue(vue, [{ team: "A", quarter_start: "x", ready: 2.5 }], 5), TypeError);
  assert.throws(() => masquerVue(vue, [{ team: "A", quarter_start: "x", ready: "12" }], 5), TypeError);
  assert.throws(() => masquerVue(vue, [{ team: "A", quarter_start: "x", ready: -1 }], 5), TypeError);
  assert.throws(() => masquerVue(vue, [{ team: "A", quarter_start: "x", ready: 12 }], 5.5), TypeError);
});

test("a NULL measure is a masked cell even when its headcount is shown (stricter than the reader, TypeScript side only)", () => {
  const vue = vueDuContrat("v_team_lead_time_throughput");
  const ligne: LigneBrute = {
    team: "A", period: "quarter", quarter_start: "2026-01-01", throughput: 40, items_lt: 30, lead_median_days: null, lead_p85_days: 9,
    items_ct: 30, cycle_median_days: 4, cycle_p85_days: 8, items_old: 0, items_without_commitment: 10,
  };
  const [sortie] = masquerVue(vue, [ligne], 10);
  assert.deepEqual(sortie.lead_median_days, { state: "masked", threshold: 10 });
  assert.deepEqual(sortie.lead_p85_days, { state: "value", value: 9 });
});

test("a view unknown to the rules is refused by default, whatever its columns", () => {
  const vue: Vue = { name: "v_autre", schema: "flow", roleKind: "flow", countColumns: ["n"], plainColumns: ["a"] };
  assert.throws(() => masquerVue(vue, [{ a: "x", n: 12 }], 5), /masquage non porté/);
});

test("a maskable column no rule covers is always masked (fail-closed)", () => {
  const vue: Vue = { ...vueDuContrat("v_team_ready_queue"), maskableColumns: ["moyenne"] };
  const [sortie] = masquerVue(vue, [{ team: "A", quarter_start: "x", moyenne: 3.5, ready: 40 }], 5);
  assert.deepEqual(sortie.moyenne, { state: "masked", threshold: PLANCHER });
});

test("a statistic is a value cell holding the number when its headcount is shown, a masked cell otherwise", () => {
  const vue = vueDuContrat("v_team_lead_time_throughput");
  const ligne = (m: number): LigneBrute => ({
    team: "A", period: "quarter", quarter_start: "2026-01-01", throughput: 40, items_lt: m, lead_median_days: 3.5, lead_p85_days: 9,
    items_ct: 30, cycle_median_days: 4, cycle_p85_days: 8, items_old: 0, items_without_commitment: 10,
  });
  const [visible] = masquerVue(vue, [ligne(30)], 10);
  assert.deepEqual(visible.lead_median_days, { state: "value", value: 3.5 });
  const [masquee] = masquerVue(vue, [ligne(7)], 10);
  assert.deepEqual(masquee.lead_median_days, { state: "masked", threshold: 10 });
  assert.ok(!JSON.stringify(masquee).includes("3.5"));
});

// ---- Reproductions de l'audit #629 (chasse Kraken), attendues rouges au commit a98a3ffb ------------------------------------------------

test("L3-07 : une cellule masquée au plancher le reste à un seuil relevé (la relation T3 n'est pas monotone)", () => {
  // audit-kraken/lots/L3.md, constat 7 : ?threshold peut relever le seuil ; au plancher 5 le débit est retiré (S = k * borne haute), à 6 il passe
  const vue = vueDuContrat("v_team_lead_time_throughput");
  const ligne: LigneBrute = {
    team: "A", period: "quarter", quarter_start: "2024-01-01", throughput: 37, items_lt: null, lead_median_days: null, lead_p85_days: null,
    items_ct: null, cycle_median_days: null, cycle_p85_days: null, items_old: null, items_without_commitment: null,
  };
  // Trois semaines pleines du trimestre (le 1er janvier 2024 est un lundi, le 1er avril aussi) : deux cellules masquées (3 et 3) et une visible (29).
  // Au plancher, S = 37 - 29 = 8 = 2 * 4 (k fois la borne haute) : retiré. À 6, la borne haute vaut 5, S = 8 est dans l'intervalle strict : publié.
  const hebdo: LigneBrute[] = [
    { team: "A", type: "Story", week_start: "2024-01-01", tickets: 3 },
    { team: "A", type: "Story", week_start: "2024-01-08", tickets: 3 },
    { team: "A", type: "Story", week_start: "2024-01-15", tickets: 29 },
  ];
  const auPlancher = masquerVue(vue, [ligne], 5, hebdo)[0].throughput;
  const releve = masquerVue(vue, [ligne], 6, hebdo)[0].throughput;
  assert.equal(estCelluleMasquee(auPlancher), true, "précondition : le débit est masqué au plancher");
  assert.equal(estCelluleMasquee(releve), true, "masqué au plancher, il doit l'être à un seuil plus haut");
});

test("H-05 : la ligne (produit) du flux sans aucune autre ligne est masquée, comme côté Python", () => {
  // audit-kraken/lots/L5.md, H-05 : [].every() rend vrai, la ligne produit serait montrée
  const vue: Vue = { name: "v_team_flow_inout", schema: "flow", roleKind: "flow", countColumns: ["created", "done"], plainColumns: ["team", "quarter_start", "type_group"] };
  const [sortie] = masquerVue(vue, [{ team: "(produit)", quarter_start: "2026-01-01", type_group: "story", created: 100, done: 90 }], 5);
  assert.equal(estCelluleMasquee(sortie.created), true, "created");
  assert.equal(estCelluleMasquee(sortie.done), true, "done");
});
