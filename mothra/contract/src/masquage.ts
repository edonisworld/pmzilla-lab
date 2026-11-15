// The masking of the rows of a served view (mothra-slices D2 and tasks 15.2 and 15.3): one pure function, applied by the server to every
// view it serves. It never shows a cell that the view masks, at the floor of five or at a raised threshold.
//
// Source of the rules: `masquer_vue`, `_masque_debit`, `STATS_TRANCHE_1` and `PARTS_TRANCHE_1` of tools/flow_views.py (R-20261030-28). This file
// is the TypeScript copy; a gap between the two is detected by the shared synthetic cases of contrats/cas-vues-tranche1.json, played by the
// npm suite (mothra/contract/test/masquage.test.ts) and by the Python suite (tests/flow_views/test_cas_vues_tranche1.py). Permanent: two
// languages, one rule.
// Deliberate gap, stricter than the reader: a NULL measure (statistic or share) is a masked cell here, where masquer_vue gives
// {"value": None} unmasked. That case cannot enter the shared file; it is tested on the TypeScript side only.
//
// Ported: the primary rule (a count under the threshold or NULL is masked, a zero included), the pairs and the series rule of
// v_team_lead_time_throughput, the statistics masked with their headcount, the shares masked with their part, their whole and their rest.
// Not ported (group 7 of masking-sums, T1 to T13, outside the demo path, R-20261029-37): the relations between views of the teams
// (v_teams, v_team_jira_ids), of the fix-version share and lag, and of the version quality photo. Refusal by default (R-20261030-49): a
// view that is not in VUES_PORTEES is refused, never served with the primary rule alone.
import { cellule, celluleMesure, colonneAvecZero } from "./cellule.ts";
import { LIBELLE_PRODUIT } from "./equipe.ts";
import { PLANCHER } from "./plancher.ts";
import type { LigneReponse } from "./reponse.ts";
import type { Vue } from "./vues.ts";

// A row of a view as read from the database, counts already turned into numbers or null.
export type LigneBrute = Record<string, number | string | null>;

// The views whose rules are ported here: the status view (primary rule only) and the five views of slice 1. Any other name is refused.
// Falls when the rules of the other views of masking-sums (group 7) are ported.
const VUES_PORTEES: readonly string[] = [
  "v_team_status",
  "v_team_lead_time_throughput",
  "v_task_without_team_share",
  "v_team_ready_queue",
  "v_team_blocked_share",
  "v_unplanned_share",
  // Task 37.1 (routes): the product-scope panels view of task 36.1: counts `created` and `done` per team or product row, closed quarter
  // and type group. Ported: the primary rule and rule D3 of the product row (see LIGNE_PRODUIT_FLUX below). NOT ported: the relations D5
  // of masking-sums (weekly resolved against `done`, the total against stories plus defects, created minus done against the change of the
  // open stock); on real data they are covered by the reduced form (D34 point 7) and by the precautions of local reading (Q33 and Q57).
  // Removal condition: group 7 of masking-sums (T13). The
  // shared cases of contrats/ and the Python side of the parity come with the view (36.1): until then the cases are the TypeScript ones
  // of test/flux-inout-masquage.test.ts.
  "v_team_flow_inout",
];

const VUE_DEBIT = "v_team_lead_time_throughput";
// Lower bound of a masked items_old whose items_ct of the row is shown (R-20261106-39, D2 and D16): 1, since the zero is then shown. The reader needs it for
// the width of a masked cell; this copy names it for the static test that compares it with `LO_ANCIENS_SI_CT_MONTRE` of tools/flow_views.py and with the
// head comment of migration 0037. Removal: permanent while the view publishes items_old.
export const LO_ANCIENS_SI_CT_MONTRE = 1;
// Rule D3 of the product row of the panels view (model: `_masque_part` of tools/flow_views.py): per (quarter_start, type_group) and per count
// column, the cell of the row `(produit)` is shown only when every other row of the same column, `(sans équipe)` included, is shown.
const VUE_FLUX = "v_team_flow_inout";
const LIGNE_PRODUIT_FLUX = LIBELLE_PRODUIT;
// n, m, c, g (= n - c), o
const SERIE_DEBIT = ["throughput", "items_lt", "items_ct", "items_without_commitment", "items_old"] as const;
type CleDebit = "n" | "m" | "c" | "g" | "o";
const CLES_DEBIT: readonly CleDebit[] = ["n", "m", "c", "g", "o"];
type Drapeaux = Record<CleDebit, boolean>;

// A statistic is masked with its headcount column; a share with its part, its whole and the rest (whole - part): { statistic: headcount }
// and { share: [part, whole] }.
const STATS_TRANCHE_1: Record<string, Record<string, string>> = {
  v_team_lead_time_throughput: {
    lead_median_days: "items_lt",
    lead_p85_days: "items_lt",
    cycle_median_days: "items_ct",
    cycle_p85_days: "items_ct",
    // D16, "Grouped year without the old items" (task 22.1, R-20261105-30): four columns added at the end of the view (migration 0038), read by the report of H1
    // only; masked with their headcount, and by STATS_SANS_ANCIENS below.
    lead_median_days_excl_old: "items_lt",
    lead_p85_days_excl_old: "items_lt",
    cycle_median_days_excl_old: "items_ct",
    cycle_p85_days_excl_old: "items_ct",
  },
};
// The statistics without the old items are masked unless items_old of the row is shown and their headcount minus items_old reaches the threshold: the reader
// cannot see m - o otherwise, so it fails closed (D16). Same rule as STATS_SANS_ANCIENS of tools/flow_views.py.
// Replaces: nothing (new columns; the rule of the first 0038, with no condition on items_old, leaked: R-20261106-59). Removal: permanent while the view publishes them.
const STATS_SANS_ANCIENS: readonly string[] = [
  "lead_median_days_excl_old",
  "lead_p85_days_excl_old",
  "cycle_median_days_excl_old",
  "cycle_p85_days_excl_old",
];
const PARTS_TRANCHE_1: Record<string, Record<string, [string, string]>> = {
  v_task_without_team_share: { share_percent: ["tasks_without_team", "tasks_done"] },
  v_team_blocked_share: { share_percent: ["blocked", "blocked_n"] },
  v_unplanned_share: { share_percent: ["unplanned", "unplanned_n"] },
};

function compteDeLigne(valeur: number | string | null | undefined): number | null {
  if (valeur === null || valeur === undefined) {
    return null;
  }
  if (typeof valeur !== "number" || !Number.isInteger(valeur) || valeur < 0) {
    throw new TypeError("compte : entier positif ou NULL attendu");
  }
  return valeur;
}

function brute(valeur: number | string | null | undefined): number | string | null {
  return valeur === undefined ? null : valeur;
}

// Relation T3 (masking-sums D17, R-20261031-07): a quarter's throughput is the sum of the Story and Task weekly cells of the quarter. Rule (b),
// the only rule with a TypeScript side (v_team_weekly_resolved is not served, so rule (a) has none): when the throughput is visible, the masked
// weekly rows are published only if the remainder pins nothing; otherwise the throughput is masked. Same rule as `_t3_lectures_passent` of
// tools/flow_views.py and as flow.v_t3_withheld; the two lines below are identical in the three files (a static test compares them).
// T3-READINGS: the two weeks straddling a quarter limit are each counted in the quarter or not (four readings); a reading whose S is outside [k * lo, k * hi] is dropped as inconsistent; the rows are published only when every reading left passes.
// T3-CONDITIONS: publish only when k >= 2 and S >= T and S != k * lo and S != k * hi, with S = n - the visible weekly cells, k the masked rows, lo and hi from BORNES.
const VUE_HEBDO = "v_team_weekly_resolved";
const TYPES_DEBIT: readonly string[] = ["story", "task"];
const LO_HEBDO = 1; // BORNES["v_team_weekly_resolved"]["tickets"] = (1, False): a weekly row exists only for a count of at least 1
const JOUR_MS = 86_400_000;

// Day number of an ISO date text (YYYY-MM-DD), or null.
function jourDe(valeur: number | string | null | undefined): number | null {
  if (typeof valeur !== "string") {
    return null;
  }
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(valeur);
  return m === null ? null : Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])) / JOUR_MS;
}

// First day of the quarter that follows the quarter starting on the given day.
function debutSuivant(jour: number): number {
  const d = new Date(jour * JOUR_MS);
  return Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 3, 1) / JOUR_MS;
}

function lecturesPassent(n: number, rangs: Array<[string, number | null]>, seuil: number): boolean {
  const hi = seuil - 1; // BORNES: no complement flag, so the upper bound of a masked row is the threshold minus one
  for (const avecDebut of [false, true]) {
    for (const avecFin of [false, true]) {
      const retenues = rangs.filter(([position]) => position === "in" || (position === "start" && avecDebut) || (position === "end" && avecFin));
      const visibles = retenues.filter(([, v]) => v !== null && v >= seuil);
      const k = retenues.length - visibles.length;
      const s = n - visibles.reduce((somme, [, v]) => somme + (v as number), 0);
      if (k === 0 || !(k * LO_HEBDO <= s && s <= k * hi)) {
        continue;
      }
      if (!(k >= 2 && s >= seuil && s !== k * LO_HEBDO && s !== k * hi)) {
        return false;
      }
    }
  }
  return true;
}

// The keys `team|quarter day` of the quarters whose throughput the rule (b) masks. `hebdo`: the weekly rows as published (a NULL is a masked row).
// Only a quarter row with a visible throughput is judged here; a throughput that is already masked is masked by the primary rule.
function retiresT3(lignes: LigneBrute[], hebdo: LigneBrute[], seuil: number): Set<string> {
  const semaines = new Map<string, Array<[number, number | null]>>();
  const illisibles = new Set<string>(); // teams with a Story or Task weekly row without a readable date: their throughputs are masked (review of T3, 1)
  for (const r of hebdo) {
    if (typeof r.type !== "string" || !TYPES_DEBIT.includes(r.type.toLowerCase())) {
      continue;
    }
    const cle = String(brute(r.team));
    const jour = jourDe(r.week_start);
    if (jour === null) {
      illisibles.add(cle);
      continue;
    }
    const rang: [number, number | null] = [jour, compteDeLigne(r.tickets)];
    semaines.set(cle, [...(semaines.get(cle) ?? []), rang]);
  }
  const retires = new Set<string>();
  for (const r of lignes) {
    if (r.period === "pooled_year") {
      continue;
    }
    const debut = jourDe(r.quarter_start);
    const n = compteDeLigne(r.throughput);
    if (debut === null || illisibles.has(String(brute(r.team)))) {
      retires.add(`${String(brute(r.team))}|${debut}`); // an unreadable date: the throughput is masked
      continue;
    }
    if (n === null || n < seuil) {
      continue;
    }
    const fin = debutSuivant(debut);
    const rangs: Array<[string, number | null]> = [];
    for (const [semaine, valeur] of semaines.get(String(brute(r.team))) ?? []) {
      if (!(semaine + 7 > debut && semaine < fin)) {
        continue;
      }
      rangs.push([semaine < debut ? "start" : semaine + 7 > fin ? "end" : "in", valeur]);
    }
    if (!lecturesPassent(n, rangs, seuil)) {
      retires.add(`${String(brute(r.team))}|${debut}`);
    }
  }
  return retires;
}

// Monotony of the relation T3 (audit #629, A-78 / L3-07): the rule (b) alone is not monotone in the threshold (at the floor the remainder pins
// a count and the throughput is withdrawn, at a higher threshold the same remainder pins nothing and it would be published). A quarter withdrawn
// at any threshold from the floor up to the effective one stays withdrawn at the effective one, so that raising the threshold never publishes a
// cell the floor masks. Above the largest throughput no quarter is judged, so the loop stops there.
// Python is aligned (S3): `_t3_retires_monotone` of tools/flow_views.py is a copy of this function, tested by twin tests (L3-07 of masquage.test.ts and
// tests/flow_views/test_t3_monotone.py). flow.v_t3_withheld is the evaluation at the floor, the first term of this union; the higher thresholds are applied
// only here and in the Python reader, never in the database.
// Replaces: the single evaluation of retiresT3 at the effective threshold. Removal: when the rule (b) itself is made monotone (`_t3_lectures_passent`
// of tools/flow_views.py, flow.v_t3_withheld and retiresT3 together), the loop then adds nothing.
function retiresT3Monotone(lignes: LigneBrute[], hebdo: LigneBrute[], seuil: number): Set<string> {
  let plusGrand = PLANCHER;
  for (const r of lignes) {
    const n = compteDeLigne(r.throughput);
    if (n !== null && n > plusGrand) {
      plusGrand = n;
    }
  }
  const retires = new Set<string>();
  for (let s = PLANCHER; s <= Math.min(seuil, plusGrand); s += 1) {
    for (const cle of retiresT3(lignes, hebdo, s)) {
      retires.add(cle);
    }
  }
  if (seuil > plusGrand) {
    for (const cle of retiresT3(lignes, hebdo, seuil)) {
      retires.add(cle);
    }
  }
  return retires;
}

// Rules between the cells of the lead time and throughput view (_masque_debit). `visibles` gives, per row, the visibility of each of the
// five counts; only published values count, a NULL is an unknown value. `retires`: the keys of the quarters masked by the relation T3.
function visibiliteDebit(lignes: LigneBrute[], seuil: number, avecPeriode: boolean, retires: Set<string>): Drapeaux[] {
  const tous = (v: boolean): Drapeaux => ({ n: v, m: v, c: v, g: v, o: v });
  if (!avecPeriode) {
    return lignes.map(() => tous(false)); // fail-closed: without `period`, a year cannot be told from a quarter
  }
  const atteint = (v: number | null): v is number => v !== null && v >= seuil;
  const ecartOk = (d: number): boolean => d === 0 || d >= seuil;
  const valeurs = (r: LigneBrute): Record<CleDebit, number | null> => ({
    n: compteDeLigne(r[SERIE_DEBIT[0]]),
    m: compteDeLigne(r[SERIE_DEBIT[1]]),
    c: compteDeLigne(r[SERIE_DEBIT[2]]),
    g: compteDeLigne(r[SERIE_DEBIT[3]]),
    o: compteDeLigne(r[SERIE_DEBIT[4]]),
  });
  const retiree = (r: LigneBrute): boolean => {
    const debut = jourDe(r.quarter_start);
    return r.period !== "pooled_year" && retires.has(`${String(brute(r.team))}|${debut}`);
  };
  const drapeaux = (r: LigneBrute, f: Drapeaux): Drapeaux => {
    const { n, m, c, g, o } = valeurs(r);
    const dn = atteint(n) && !f.n && !retiree(r);
    const dm = atteint(m) && dn && !f.m && ecartOk(Math.abs((n as number) - m));
    const dc =
      atteint(c) && dn && !f.c && !f.g && ecartOk(Math.abs((n as number) - c)) && (!dm || ecartOk(Math.abs((m as number) - c)));
    const dg = atteint(g) && dn && !f.g && (dc || (c === null && g === n));
    // R-20261106-39: a zero of items_old is shown when items_ct is shown (the year at 0 only when no quarter of its series is masked: f.o); the rest
    // is the earlier rule. A masked items_old with items_ct shown has a lower bound of 1 (the zero is shown), as LO_ANCIENS_SI_CT_MONTRE in Python.
    const dO = dc && !f.o && (o === 0 || (atteint(o) && ecartOk(Math.abs((c as number) - o))));
    return { n: dn, m: dm, c: dc, g: dg, o: dO };
  };

  const aucun = tous(false);
  const serieMasquee = new Map<string | number | null, Drapeaux>();
  const serieDe = (equipe: string | number | null): Drapeaux => {
    let s = serieMasquee.get(equipe);
    if (s === undefined) {
      s = { ...aucun };
      serieMasquee.set(equipe, s);
    }
    return s;
  };
  const resultats: (Drapeaux | null)[] = [];
  const equipesAvecTrimestres = new Set<string | number | null>();
  for (const r of lignes) {
    if (r.period !== "pooled_year") {
      equipesAvecTrimestres.add(brute(r.team));
    }
  }
  for (const r of lignes) {
    if (r.period === "pooled_year") {
      resultats.push(null);
      continue;
    }
    const d = drapeaux(r, aucun);
    resultats.push(d);
    // g = 0 reads from n and c, both visible: not a leak
    const zeroDeductible = valeurs(r).g === 0 && d.c;
    for (const k of CLES_DEBIT) {
      if (!d[k] && !(k === "g" && zeroDeductible)) {
        serieDe(brute(r.team))[k] = true;
      }
    }
  }
  return lignes.map((r, i) => {
    const equipe = brute(r.team);
    const deja = resultats[i];
    if (deja === null && !equipesAvecTrimestres.has(equipe)) {
      return { ...aucun }; // a year without the quarters of its series: all masked
    }
    return deja ?? drapeaux(r, serieDe(equipe));
  });
}

// The rows of a served view, as the structured answer: a count column becomes a cell (value, or masked with the effective threshold), a plain
// column stays a plain value, and a maskable column (a statistic or a share) becomes a cell, masked with its count. No masked value is kept.
//
// `hebdo` (relation T3, masking-sums D17): the rows of `v_team_weekly_resolved` as the view publishes them (columns team, type, week_start,
// tickets), passed by the server for the lead time and throughput view. Without them the rule (b) is not applied.
export function masquerVue(vue: Vue, lignes: LigneBrute[], seuil: number, hebdo?: LigneBrute[]): LigneReponse[] {
  if (!Number.isInteger(seuil) || seuil < 0) {
    throw new TypeError("seuil : entier positif attendu");
  }
  if (!VUES_PORTEES.includes(vue.name)) {
    throw new Error(`masquage non porté pour la vue ${vue.name}`);
  }
  const effectif = Math.max(PLANCHER, seuil);
  const comptes = vue.countColumns;
  const mesurables = vue.maskableColumns ?? [];
  const colonnes = [...vue.plainColumns, ...mesurables, ...comptes];

  // visibility of each count of each row: the primary rule, then the rules between cells
  const visibles = lignes.map((r) => {
    const v: Record<string, boolean> = {};
    for (const col of comptes) {
      const valeur = compteDeLigne(r[col]);
      v[col] = valeur !== null && valeur >= effectif;
    }
    return v;
  });
  if (vue.name === VUE_DEBIT) {
    const retires = hebdo === undefined ? new Set<string>() : retiresT3Monotone(lignes, hebdo, effectif);
    const flags = visibiliteDebit(lignes, effectif, colonnes.includes("period"), retires);
    lignes.forEach((_, i) => {
      CLES_DEBIT.forEach((k, j) => {
        const col = SERIE_DEBIT[j];
        if (comptes.includes(col)) {
          visibles[i][col] = flags[i][k];
        }
      });
    });
  }

  if (vue.name === VUE_FLUX) {
    const groupes = new Map<string, number[]>();
    lignes.forEach((r, i) => {
      if (r.team === LIGNE_PRODUIT_FLUX) return;
      const cle = JSON.stringify([brute(r.quarter_start), brute(r.type_group)]);
      groupes.set(cle, [...(groupes.get(cle) ?? []), i]);
    });
    lignes.forEach((r, i) => {
      if (r.team !== LIGNE_PRODUIT_FLUX) return;
      const autres = groupes.get(JSON.stringify([brute(r.quarter_start), brute(r.type_group)])) ?? [];
      // A product line with no team line in its group is masked, as in flow_views.py (`_masque_flux`, "not groupe"): `[].every()` would show it
      // (audit #629, H-05). Replaces: nothing. Removal: permanent while the Python and the TypeScript masking both exist (parity).
      for (const col of comptes) {
        if (autres.length === 0 || !autres.every((t) => visibles[t][col])) visibles[i][col] = false;
      }
    });
  }

  // statistics and shares (maskable columns) masked with their headcount; a maskable column no rule covers is always masked (fail-closed)
  const regleStat = STATS_TRANCHE_1[vue.name] ?? {};
  const reglePart = PARTS_TRANCHE_1[vue.name] ?? {};
  const forcees = lignes.map(() => new Set<string>());
  lignes.forEach((r, i) => {
    for (const col of mesurables) {
      if (!(col in regleStat) && !(col in reglePart)) {
        forcees[i].add(col);
      }
    }
    for (const [stat, effectifCol] of Object.entries(regleStat)) {
      if (mesurables.includes(stat) && !(visibles[i][effectifCol] ?? false)) {
        forcees[i].add(stat);
      } else if (mesurables.includes(stat) && STATS_SANS_ANCIENS.includes(stat)) {
        const effectifValeur = compteDeLigne(r[effectifCol]);
        const anciensValeur = compteDeLigne(r.items_old);
        const reste = effectifValeur === null || anciensValeur === null ? null : effectifValeur - anciensValeur;
        if (!(visibles[i].items_old ?? false) || reste === null || reste < effectif) {
          forcees[i].add(stat);
        }
      }
    }
    for (const [part, [partie, tout]] of Object.entries(reglePart)) {
      if (!mesurables.includes(part)) {
        continue;
      }
      const p = compteDeLigne(r[partie]);
      const t = compteDeLigne(r[tout]);
      if (p === null || t === null || p < effectif || t - p < effectif || t < effectif) {
        visibles[i][partie] = false; // the part, the rest or the whole under the threshold: the share would be read back
        forcees[i].add(part);
      }
    }
  });

  return lignes.map((r, i) => {
    const sortie: LigneReponse = {};
    for (const col of vue.plainColumns) {
      sortie[col] = brute(r[col]);
    }
    for (const col of mesurables) {
      const valeur = r[col];
      if (valeur !== null && valeur !== undefined && typeof valeur !== "number") {
        throw new TypeError("mesure : nombre ou NULL attendu");
      }
      sortie[col] = celluleMesure(valeur ?? null, !forcees[i].has(col), effectif);
    }
    for (const col of comptes) {
      const valeur = compteDeLigne(r[col]);
      // a count the rules hide is shown as the masked cell: the value handed to `cellule` is NULL, so nothing of it is kept
      sortie[col] = cellule(visibles[i][col] ? valeur : null, effectif, colonneAvecZero(vue.name, col));
    }
    return sortie;
  });
}
