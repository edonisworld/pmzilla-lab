// Task 18.4 (design D20, D30, D33): the computed body of a sheet on the real views of the throwaway database loaded with the dataset of
// slice 1 (tests/mothra_donnees/tranche1.py), under the view role, with the thresholds inserted by the storage role. Skipped, never failed,
// without DBTEST_PORT. Written for the author's run (tools/dbtest.sh), never run by a session. DEPENDS ON TASK 15.3 (the masking of
// statistics and shares). The dataset dates everything from "now": the assertions are relative (a set of allowed outcomes, equalities
// between the sheet and the dashboard), never fixed figures. Invented teams ("équipe E" and following), no real data.
import assert from "node:assert/strict";
import { after, before, test } from "node:test";

import { celluleDe, etiquetteTrimestre, lireCodeMesure, mesureDeStatistique, tableauLeadCycle, tailleEchantillonH1 } from "@mothra/contract";
import { identifiantEquipe } from "@mothra/contract/equipe";

import { lireEnvironnement } from "../../src/config/index.ts";
import { creerAccesPostgres } from "../../src/db/base.ts";
import { creerAccesStockage } from "../../src/db/stockage.ts";
import { VUES_DE_LA_FICHE, creerCalculCorps } from "../../src/fiches/corps.ts";
import { lireVueMasquee } from "../../src/service.ts";
import { contrat, sautBaseJetable } from "../aide.ts";
import { creerBaseJetable } from "./base-jetable.ts";
import type { BaseJetable } from "./base-jetable.ts";

const saut = sautBaseJetable();
let base: BaseJetable | null = null;

before(async () => {
  if (saut === false) {
    base = await creerBaseJetable(lireEnvironnement(), undefined, { tranche1: true });
  }
});

after(async () => {
  await base?.supprimer();
});

// The real team identifier of the contract (review of 18.4, A1).
const identifiant = identifiantEquipe;

// The values of the synthetic runs (test/depart.ts of the contract); the real values come from the author's history.
const SEUILS: Array<[string, number]> = [
  ["h5_band", 0.2],
  ["h5_double_band", 0.4],
  ["h5_run_rises", 2],
  ["h5_run_min_cumulative_rise", 0.1],
  ["h5_floor", 0.8],
  ["h5_low_floor", 0.6],
  ["h1_lower", 1.5],
  ["h1_upper", 3],
  ["attachment_threshold_points", 10],
  ["sample_median_min_items", 10],
  ["sample_p85_min_items", 20],
];

// The median sample size is read from the thresholds above, not written a second time.
const TAILLE_MEDIANE = SEUILS.find(([code]) => code === "sample_median_min_items")?.[1] ?? Number.NaN;

const VERDICTS = ["refuted", "not_settled", "confirmed", "insufficient_sample"];

// First of the file: the history of the throwaway database is still empty (the next test inserts the thresholds).
test("without a threshold in the history, no body is computed", { skip: saut }, async () => {
  assert.ok(base !== null, "the throwaway database was not created");
  const config = base.configuration();
  const acces = creerAccesPostgres(config);
  const stockage = creerAccesStockage(config);
  try {
    assert.deepEqual(await stockage.seuils(), []);
    const calcul = creerCalculCorps({ acces, contrat, seuil: 5, depot: stockage, identifiantEquipe: identifiant, mode: { jeu: "synthetic", comptesAutorises: false } });
    await assert.rejects(calcul.verifierCreation({ chart: "lead_cycle_h5", scope: "team.0123456789abcdef" }), (e: unknown) => e instanceof Error && e.name === "SeuilsNonFixes");
  } finally {
    await stockage.fermer();
    await acces.fermer();
  }
});

test("the body of both kinds, for every team of the dataset: allowed verdicts, masked cells structured, chart equal to the dashboard", { skip: saut }, async () => {
  assert.ok(base !== null, "the throwaway database was not created");
  const config = base.configuration();
  const acces = creerAccesPostgres(config);
  const stockage = creerAccesStockage(config);
  try {
    for (const [code, value] of SEUILS) await stockage.ajouterSeuil({ code, value, setOn: "2026-10-27", setBy: "author-1" });
    const calcul = creerCalculCorps({ acces, contrat, seuil: 5, depot: stockage, identifiantEquipe: identifiant, mode: { jeu: "synthetic", comptesAutorises: false } });
    const dataDate = new Date().toISOString().slice(0, 10);
    const vueLead = contrat.views.find((v) => v.name === VUES_DE_LA_FICHE.leadCycle);
    assert.ok(vueLead !== undefined);
    const reponse = await lireVueMasquee(acces, vueLead, 5);
    const equipes = [...new Set(reponse.rows.map((r) => r.team).filter((t): t is string => typeof t === "string"))];
    assert.ok(equipes.length > 0, "the dataset of slice 1 holds teams in the lead time view");
    const tableau = tableauLeadCycle(reponse, { medianMinItems: TAILLE_MEDIANE, p85MinItems: 20 }, dataDate, identifiant);
    let cellulesVerifiees = 0;
    for (const equipe of equipes) {
      for (const chart of ["lead_cycle_h5", "lead_cycle_h1"]) {
        const scope = `team.${identifiant(equipe)}`;
        const id = await stockage.creer({ chart, scope, dataDate, createdBy: "agile-lead-1" });
        const corps = await calcul.calculerCorps({ id, chart, scope, dataDate });
        assert.ok(VERDICTS.includes(corps.verdict), `${chart}: ${corps.verdict}`);
        assert.equal(corps.explanations.find((e) => e.name === "unplanned_work")?.reason, "defects_without_team");
        for (const m of corps.method.maskedCells) assert.deepEqual(m.cell, { state: "masked", threshold: 5 });
        const serie = tableau.teams.find((s) => s.team === equipe);
        for (const point of corps.chart?.quarters ?? []) assert.deepEqual(point, serie?.points.find((p) => p.quarter === point.quarter));
        const pointAnnee = serie?.points.find((p) => p.quarter === "pooled_year");
        const ligneAnnee = reponse.rows.find((r) => r.team === equipe && r.period === "pooled_year");
        // R-20261108-08 : H1 lit l'année groupée sans les anciens (H-01, D16 de masking-sums) ; exception à l'égalité fiche = tableau de bord de D30.
        // H5 : égalité stricte avec le point pooled_year du tableau de bord. H1 : les colonnes *_excl_old de la ligne pooled_year de la vue masquée,
        // lues par celluleDe, avec l'effectif sans les anciens de tailleEchantillonH1 (masqué avant échantillon insuffisant, par mesureDeStatistique).
        if (chart === "lead_cycle_h1" && ligneAnnee !== undefined && pointAnnee !== undefined) {
          const sansAnciens = (colonne: string, genre: "lead" | "cycle", taille: number) => {
            const effectif = tailleEchantillonH1(genre, { items_lt: celluleDe(ligneAnnee, "items_lt"), items_ct: celluleDe(ligneAnnee, "items_ct"), items_old: celluleDe(ligneAnnee, "items_old") });
            return mesureDeStatistique(celluleDe(ligneAnnee, colonne), effectif === null ? null : { state: "value", value: effectif }, taille, 5);
          };
          const attendu = { ...pointAnnee, lead: sansAnciens("lead_median_days_excl_old", "lead", TAILLE_MEDIANE), cycle: sansAnciens("cycle_median_days_excl_old", "cycle", TAILLE_MEDIANE) };
          assert.deepStrictEqual(corps.chart?.pooledYear, attendu);
        } else if (corps.chart?.pooledYear !== undefined) {
          assert.deepEqual(corps.chart.pooledYear, pointAnnee);
        }
        // A cell the sheet declares masked is never shown by its chart (audit #629, H-01): the charted measures are the lead and cycle medians.
        // The P85 codes (lead_p85_days, cycle_p85_days) are checked the same way against corps.p85 (quarters and pooledYear, points with lead and cycle).
        for (const m of corps.method.maskedCells) {
          const code = lireCodeMesure(m.measure);
          assert.ok(code !== null, `unreadable measure code: ${m.measure}`);
          const mediane = code.column === "lead_median_days" ? "lead" : code.column === "cycle_median_days" ? "cycle" : null;
          const p85 = code.column === "lead_p85_days" ? "lead" : code.column === "cycle_p85_days" ? "cycle" : null;
          const champ = mediane ?? p85;
          if (champ === null) continue;
          const source = mediane !== null ? corps.chart : corps.p85;
          const point = code.when === "pooled_year" ? source?.pooledYear : source?.quarters.find((p) => p.quarter === etiquetteTrimestre(code.when));
          if (point === undefined) continue;
          cellulesVerifiees += 1;
          assert.equal(point[champ].state, "masked", `${chart}: ${m.measure} is declared masked but shown by ${mediane !== null ? "the chart" : "the P85"}`);
        }
        assert.match(corps.method.fingerprint, /^[0-9a-f]{64}$/);
      }
    }
    assert.ok(cellulesVerifiees > 0, "no masked cell of a chart measure was checked: the loop on maskedCells proves nothing on this dataset");
  } finally {
    await stockage.fermer();
    await acces.fermer();
  }
});

