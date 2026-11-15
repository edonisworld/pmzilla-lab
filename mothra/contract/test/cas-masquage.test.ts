// Player of the shared counter-examples of change masking-sums (contrats/cas-masquage.json), TypeScript side (relation T3, D17, task 13.1).
// The Python reader plays every case with `masquer_vue`. Here `masquerVue` ports the lead time and throughput view only (the relation T3,
// rule (b), reads the published weekly rows): a case on that view is played and compared; a case on a view the TypeScript masking does not
// port is checked to be refused (`masquage non porté`), never served with the primary rule alone. The rule (a) of T3 (withheld weekly rows) and
// the rules between the other views stay on the Python side (v_team_weekly_resolved is not served by Mothra).
// The list below holds every identifier of the file, between quotes: the Python suite (tests/flow_views/test_cas_masquage.py) refuses a TypeScript
// player that does not list each one, and the last test compares the list with the file.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { chargerContrat } from "../src/chargeur.ts";
import type { Cellule } from "../src/cellule.ts";
import type { CelluleLue } from "../src/lecture-vue.ts";
import { type LigneBrute, masquerVue } from "../src/masquage.ts";
import { tailleEchantillonH1 } from "../src/taille-echantillon.ts";
import type { Vue } from "../src/vues.ts";

const RACINE = new URL("../../../contrats/", import.meta.url);
const CONTRAT = chargerContrat(new URL("vues.json", RACINE));

interface Table {
  columns: string[];
  rows: Record<string, number | string | null>[];
}
interface CasPartage extends Table {
  id: string;
  kind: string;
  title: string;
  view: string;
  threshold: number;
  cells: string[];
  masked: [number, string][];
  related?: Record<string, Table>;
  sampleSize?: { row: number; lead: number | null; cycle: number | null }; // kind echantillon_h1 (task 22.1)
}

const FICHIER = JSON.parse(readFileSync(new URL("cas-masquage.json", RACINE), "utf8")) as { players: string[]; cases: CasPartage[] };

const IDENTIFIANTS = [
  "X1", "X1b", "X2", "X2b", "X2c", "X2d", "X2e", "X2f", "X3", "X4", "X5", "X6a", "X6b", "X7", "X8", "X8c", "X8b", "X9", "X10", "X11",
  "X12", "X12b", "X12c", "X12d", "X18", "X21", "X20", "X19", "X14", "X15", "X16", "X17",
  "X26a", "X26b", "X26c", "X26d", "X26e", "X26f", "X23",
  "X42a", "X42b", "X42c", "X42d", "X42e", "X42f", // the zero of items_old (R-20261106-39): renamed from X40a to X40f to follow the design (R-20261106 review 21.2)
  "X39", "X40", "X41", "H1a", "H1b", "H1c", // task 22.1 (D16): the statistics without the old items and the sample size of H1
];

function brutes(table: Table, colonnes: string[]): LigneBrute[] {
  return table.rows.map((ligne) => Object.fromEntries(colonnes.map((c) => [c, ligne[c] ?? null])));
}

function estMasquee(x: unknown): boolean {
  return typeof x === "object" && x !== null && (x as Cellule).state === "masked";
}

test("the shared file lists the npm player and the list of identifiers below is its list", () => {
  assert.ok(FICHIER.players.includes("npm"));
  assert.deepEqual([...IDENTIFIANTS].sort(), FICHIER.cases.map((c) => c.id).sort());
});

for (const cas of FICHIER.cases) {
  test(`shared case ${cas.id}: ${cas.title}`, () => {
    const vue = CONTRAT.views.find((v) => v.name === cas.view);
    if (vue === undefined || vue.name !== "v_team_lead_time_throughput") {
      // a view the TypeScript masking does not port: refused, whatever the rows
      const refusee: Vue = {
        name: cas.view,
        schema: "flow",
        roleKind: "flow",
        countColumns: cas.cells,
        plainColumns: cas.columns.filter((c) => !cas.cells.includes(c)),
      };
      assert.throws(() => masquerVue(refusee, [], cas.threshold), /masquage non porté/, cas.id);
      return;
    }
    const colonnes = [...vue.plainColumns, ...(vue.maskableColumns ?? []), ...vue.countColumns];
    const entree = brutes(cas, colonnes);
    const liee = cas.related?.["v_team_weekly_resolved"];
    const hebdo = liee === undefined ? undefined : brutes(liee, ["team", "type", "week_start", "tickets"]);
    const sortie = masquerVue(vue, entree, cas.threshold, hebdo);
    const masquees: [number, string][] = [];
    sortie.forEach((ligne, i) => {
      for (const col of cas.cells) {
        if (estMasquee(ligne[col])) {
          masquees.push([i, col]);
        } else {
          assert.deepEqual(ligne[col], { state: "value", value: entree[i][col] }, `${cas.id} ${i} ${col}`);
        }
      }
    });
    const ordre = (a: [number, string], b: [number, string]): number => a[0] - b[0] || a[1].localeCompare(b[1]);
    assert.deepEqual([...masquees].sort(ordre), [...cas.masked].sort(ordre), `${cas.id}: ${cas.title}`);
    if (cas.kind === "echantillon_h1") {
      // the sample size of H1 from the shown cells only (task 22.1, D16): the same sizes as the Python player
      const attendu = cas.sampleSize as NonNullable<CasPartage["sampleSize"]>;
      const cellules = sortie[attendu.row] as unknown as Record<string, CelluleLue>;
      assert.equal(tailleEchantillonH1("lead", cellules), attendu.lead, `${cas.id} lead`);
      assert.equal(tailleEchantillonH1("cycle", cellules), attendu.cycle, `${cas.id} cycle`);
    }
  });
}

test("a caller that passes no weekly array (the argument is optional) gets the earlier masking; the server always passes it", () => {
  const cas = FICHIER.cases.find((c) => c.id === "X26b") as CasPartage;
  const vue = CONTRAT.views.find((v) => v.name === cas.view) as Vue;
  const colonnes = [...vue.plainColumns, ...(vue.maskableColumns ?? []), ...vue.countColumns];
  const [ligne] = masquerVue(vue, brutes(cas, colonnes), cas.threshold);
  assert.deepEqual(ligne.throughput, { state: "value", value: 23 });
});

test("a weekly row without a readable date, or a quarter row without one, masks the throughput (review of T3, 1)", () => {
  const vue = CONTRAT.views.find((v) => v.name === "v_team_lead_time_throughput") as Vue;
  const colonnes = [...vue.plainColumns, ...(vue.maskableColumns ?? []), ...vue.countColumns];
  const ligne = (equipe: string, debut: string | null): LigneBrute => {
    const valeurs: Record<string, number | string | null> = { team: equipe, period: "quarter", quarter_start: debut, throughput: 40 };
    return Object.fromEntries(colonnes.map((c) => [c, valeurs[c] ?? null]));
  };
  for (const illisible of [null, "not a date"]) {
    const hebdo: LigneBrute[] = [
      { team: "A", type: "Story", week_start: illisible, tickets: 12 },
      { team: "B", type: "Story", week_start: "2026-04-06", tickets: 12 },
    ];
    const [a, b] = masquerVue(vue, [ligne("A", "2026-04-01"), ligne("B", "2026-04-01")], 5, hebdo);
    assert.equal(estMasquee(a.throughput), true, String(illisible));
    assert.equal(estMasquee(b.throughput), false, String(illisible));
  }
  const [sansDate] = masquerVue(vue, [ligne("A", null)], 5, [{ team: "A", type: "Story", week_start: "2026-04-06", tickets: 12 }]);
  assert.equal(estMasquee(sansDate.throughput), true);
});

test("the pooled year is masked as soon as a quarter is withheld by T3 (review of T3, B1)", () => {
  const vue = CONTRAT.views.find((v) => v.name === "v_team_lead_time_throughput") as Vue;
  const colonnes = [...vue.plainColumns, ...(vue.maskableColumns ?? []), ...vue.countColumns];
  const ligne = (period: string, debut: string | null, n: number): LigneBrute => {
    const valeurs: Record<string, number | string | null> = { team: "A", period, quarter_start: debut, throughput: n };
    return Object.fromEntries(colonnes.map((c) => [c, valeurs[c] ?? null]));
  };
  const lignes = [ligne("quarter", "2025-04-01", 1), ligne("quarter", "2025-07-01", 6), ligne("quarter", "2025-10-01", 30),
    ligne("quarter", "2026-01-01", 30), ligne("pooled_year", null, 67)];
  const hebdo: LigneBrute[] = [
    { team: "A", type: "Story", week_start: "2025-07-08", tickets: 5 },
    { team: "A", type: "Task", week_start: "2025-07-08", tickets: null },
  ];
  const sorties = masquerVue(vue, lignes, 5, hebdo);
  assert.deepEqual(sorties.map((s) => estMasquee(s.throughput)), [true, true, false, false, true]);
});

test("a throughput masked by rule (b) masks its headcounts and the pooled year follows the series rule", () => {
  const vue = CONTRAT.views.find((v) => v.name === "v_team_lead_time_throughput") as Vue;
  const colonnes = [...vue.plainColumns, ...(vue.maskableColumns ?? []), ...vue.countColumns];
  const base: Record<string, number | string | null> = { team: "A", period: "quarter", quarter_start: "2026-04-01", throughput: 25, items_lt: 25 };
  const annee: Record<string, number | string | null> = { team: "A", period: "pooled_year", quarter_start: null, throughput: 90, items_lt: 90 };
  const lignes: LigneBrute[] = [base, annee].map((l) => Object.fromEntries(colonnes.map((c) => [c, l[c] ?? null])));
  const hebdo: LigneBrute[] = [
    { team: "A", type: "Story", week_start: "2026-04-06", tickets: 12 },
    { team: "A", type: "Task", week_start: "2026-04-06", tickets: 11 },
    { team: "A", type: "Story", week_start: "2026-04-13", tickets: null },
    { team: "A", type: "Task", week_start: "2026-04-13", tickets: null },
  ];
  const [trimestre, an] = masquerVue(vue, lignes, 5, hebdo);
  assert.equal(estMasquee(trimestre.throughput), true);
  assert.equal(estMasquee(trimestre.items_lt), true);
  assert.equal(estMasquee(an.throughput), true); // one masked quarter: the pooled year would give it back by difference
});

test("a straddling week is read in the quarter or not: a reading that fails masks the throughput, a reading out of range is dropped", () => {
  const vue = CONTRAT.views.find((v) => v.name === "v_team_lead_time_throughput") as Vue;
  const colonnes = [...vue.plainColumns, ...(vue.maskableColumns ?? []), ...vue.countColumns];
  const hebdo: LigneBrute[] = [
    { team: "A", type: "Story", week_start: "2026-04-06", tickets: 12 },
    { team: "A", type: "Task", week_start: "2026-04-13", tickets: 10 },
    { team: "A", type: "Task", week_start: "2026-04-20", tickets: null },
    { team: "A", type: "Task", week_start: "2026-04-27", tickets: null },
    { team: "A", type: "Story", week_start: "2026-03-30", tickets: 7 }, // straddles the start of the quarter of 2026-04-01
  ];
  const ligne = (n: number): LigneBrute => {
    const valeurs: Record<string, number | string | null> = { team: "A", period: "quarter", quarter_start: "2026-04-01", throughput: n };
    return Object.fromEntries(colonnes.map((c) => [c, valeurs[c] ?? null]));
  };
  assert.equal(estMasquee(masquerVue(vue, [ligne(30)], 5, hebdo)[0].throughput), true); // with the week: S = 1 < k, dropped; without: k = 2, S = 8 = 4k
  assert.equal(estMasquee(masquerVue(vue, [ligne(34)], 5, hebdo)[0].throughput), false); // with the week: k = 2, S = 5; without: S = 12 > 8, dropped
});
