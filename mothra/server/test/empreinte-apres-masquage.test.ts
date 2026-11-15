// Audit #629, A-96 (R-20261109-19): anchoring test. The fingerprint published on a sheet body is computed on the views AFTER masking, never on the
// raw rows. A set with one cell under the threshold shows it: the published fingerprint equals the one of the masked views, differs from the one
// of the raw rows, and changing the raw value of a masked cell does not change it. Green from the start: no code changes. Invented team and
// figures; no database.
// Complements server/test/corps.test.ts:104-126 (equality only), which stays the source of the equality; this test adds the difference with the raw
// rows and the invariance to the raw value of a masked cell. Remplace : rien. Retrait : permanent, tant que l'empreinte publiée existe (R-20261109-19).
import assert from "node:assert/strict";
import { test } from "node:test";

import type { Vue } from "@mothra/contract";
import { identifiantEquipe, scopeFiche } from "@mothra/contract/equipe";

import type { AccesVues, LigneBase } from "../src/db/acces.ts";
import { VUES_DE_LA_FICHE, creerCalculCorps } from "../src/fiches/corps.ts";
import { empreinte } from "../src/fiches/depot.ts";
import { lireVueMasquee } from "../src/service.ts";
import { SENTINELLE, contrat } from "./aide.ts";
import { DepotMemoire } from "./depot-memoire.ts";

const DATE = "2026-10-05";
const DEBUTS = ["2026-01-01", "2026-04-01", "2026-07-01"]; // the three closed quarters (R-20261114-49)
const JUGE = DEBUTS[2];
const SEUIL = 5;
const SCOPE = scopeFiche({ kind: "team", team: identifiantEquipe("team-a") });

class Acces implements AccesVues {
  lignes = new Map<string, LigneBase[]>();
  async lireVue(vue: Vue): Promise<LigneBase[]> {
    return this.lignes.get(vue.name) ?? [];
  }
}

function brute(debut: string | null, debit: number): LigneBase {
  return {
    team: "team-a",
    period: debut === null ? "pooled_year" : "quarter",
    quarter_start: debut,
    throughput: debit,
    items_lt: 30,
    items_ct: 30,
    items_old: 5,
    items_without_commitment: 0,
    lead_median_days: 15,
    lead_p85_days: 30,
    cycle_median_days: 10,
    cycle_p85_days: 20,
    lead_median_days_excl_old: 15,
    lead_p85_days_excl_old: 30,
    cycle_median_days_excl_old: 10,
    cycle_p85_days_excl_old: 20,
    ticket_key: SENTINELLE,
  };
}

// The latest quarter has `debitMasque` tickets: under the threshold, so its throughput cell is masked.
function acces(debitMasque: number): Acces {
  const a = new Acces();
  a.lignes.set("v_team_lead_time_throughput", [...DEBUTS.map((d, i) => brute(d, i === 2 ? debitMasque : 30)), brute(null, 30)]);
  a.lignes.set("v_task_without_team_share", DEBUTS.map((d) => ({ quarter_start: d, tasks_done: 30, tasks_without_team: 6, share_percent: 20 })));
  a.lignes.set("v_unplanned_share", DEBUTS.map((d) => ({ quarter_start: d, unplanned: 10, unplanned_n: 80, share_percent: 12.5 })));
  a.lignes.set("v_team_ready_queue", [{ team: "team-a", quarter_start: JUGE, ready: 12 }]);
  a.lignes.set("v_team_blocked_share", [{ team: "team-a", quarter_start: JUGE, blocked_n: 30, blocked: 9, share_percent: 30 }]);
  return a;
}

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

async function empreintePubliee(a: Acces): Promise<string> {
  const depot = new DepotMemoire();
  for (const [code, value] of SEUILS) await depot.ajouterSeuil({ code, value, setOn: "2026-10-27", setBy: "author-1" });
  const calcul = creerCalculCorps({
    acces: a,
    contrat,
    seuil: SEUIL,
    depot,
    identifiantEquipe,
    mode: { jeu: "synthetic", comptesAutorises: false },
  });
  const id = await depot.creer({ chart: "lead_cycle_h5", scope: SCOPE, dataDate: DATE, createdBy: "agile-lead-1" });
  const corps = await calcul.calculerCorps({ id, chart: "lead_cycle_h5", scope: SCOPE, dataDate: DATE });
  assert.ok(
    corps.method.maskedCells.some((m) => m.measure === `throughput@${JUGE}` && m.cell.state === "masked"),
    "the set must hold at least one masked cell",
  );
  return corps.method.fingerprint;
}

test("the published fingerprint is the one of the masked views, not of the raw rows, and a masked raw value does not move it", async () => {
  const a = acces(3);
  const publiee = await empreintePubliee(a);

  const nomsDesVues = Object.entries(VUES_DE_LA_FICHE) as Array<[string, string]>;
  const masquees = Object.fromEntries(
    await Promise.all(nomsDesVues.map(async ([cle, nom]) => [cle, await lireVueMasquee(a, contrat.views.find((v) => v.name === nom) as Vue, SEUIL)])),
  );
  const brutes = Object.fromEntries(nomsDesVues.map(([cle, nom]) => [cle, a.lignes.get(nom) ?? []]));

  assert.equal(publiee, empreinte(masquees));
  assert.notEqual(publiee, empreinte(brutes));

  // The raw value of the masked cell changes (3 to 2, still under the threshold): the published fingerprint does not.
  assert.equal(await empreintePubliee(acces(2)), publiee);
});
