// Task 45.1 (design D17 and D35, "Team names on screen", author's decisions R-20261104-33, -35 and -36 N1 (a)): the setting
// MOTHRA_SHOW_TEAM_NAMES (absent or false: off; true: on; any other value refused at start, exit 5, SETTING_INVALID naming the variable
// only), and the omission of `team` by the service layer (`servirTableau`) when it is off, on the complete and on the reduced answer.
// Invented team name only; no database.
import assert from "node:assert/strict";
import { test } from "node:test";

import { motifsDeNoms } from "@mothra/contract";
import type { ReponseLeadCycle, Vue } from "@mothra/contract";
import { identifiantEquipe, scopeFiche } from "@mothra/contract/equipe";

import { VARIABLES, chargerConfiguration } from "../src/config/index.ts";
import type { AccesVues, LigneBase } from "../src/db/acces.ts";
import { preparer } from "../src/demarrage.ts";
import type { OptionsDemarrage } from "../src/demarrage.ts";
import { creerCalculCorps } from "../src/fiches/corps.ts";
import { RefusDemarrage } from "../src/refus.ts";
import { construireServeur } from "../src/routes/serveur.ts";
import { servirTableau } from "../src/service.ts";
import type { ModeDonnees } from "../src/service.ts";
import { AccesFictif, CHEMIN_CONTRAT, contrat, envMinimal } from "./aide.ts";
import { DepotMemoire } from "./depot-memoire.ts";

const NOM = "Équipe Exemple";
const DEBUTS = ["2026-01-01", "2026-04-01", "2026-07-01"]; // the three closed quarters (R-20261114-49)

// ---- the setting ----------------------------------------------------------------------------------------------------------------

test("the setting has its own variable name", () => {
  assert.equal(VARIABLES.afficherNomsEquipes, "MOTHRA_SHOW_TEAM_NAMES");
});

test("absent: off (the default); false: off; true: on", () => {
  assert.equal(chargerConfiguration(envMinimal()).afficherNomsEquipes, false);
  assert.equal(chargerConfiguration(envMinimal({ [VARIABLES.afficherNomsEquipes]: "false" })).afficherNomsEquipes, false);
  assert.equal(chargerConfiguration(envMinimal({ [VARIABLES.afficherNomsEquipes]: "true" })).afficherNomsEquipes, true);
});

test("any other value is refused at start: exit 5, SETTING_INVALID, the variable named, the value never echoed", () => {
  for (const valeur of ["yes", "1", "TRUE", "False", " true", "oui", "valeur-sentinelle-xyz"]) {
    let refus: RefusDemarrage | null = null;
    try {
      chargerConfiguration(envMinimal({ [VARIABLES.afficherNomsEquipes]: valeur }));
    } catch (erreur) {
      assert.ok(erreur instanceof RefusDemarrage, "a start refusal was expected");
      refus = erreur;
    }
    assert.ok(refus !== null, `refused: ${valeur}`);
    assert.equal(refus.code, "SETTING_INVALID");
    assert.equal(refus.sortie, 5);
    assert.equal(refus.phrase, "mothra: refused (SETTING_INVALID) MOTHRA_SHOW_TEAM_NAMES");
    assert.ok(!refus.phrase.includes(valeur.trim()) || valeur.trim() === "", "no value in the refusal");
  }
});

// ---- the service layer ----------------------------------------------------------------------------------------------------------

function plein(): ReponseLeadCycle {
  return {
    threshold: 5,
    dataDate: "2026-10-05",
    product: [],
    teams: [
      {
        team: NOM,
        teamId: identifiantEquipe(NOM),
        points: [{ quarter: "2026-Q3", lead: { state: "value", value: 15 }, cycle: { state: "insufficient_sample" }, items: { state: "value", value: 12 } }],
      },
    ],
  };
}

const MODES: Array<[string, Omit<ModeDonnees, "afficherNoms">]> = [
  ["synthetic (complete answer)", { jeu: "synthetic", comptesAutorises: false }],
  ["real (reduced answer)", { jeu: "real", comptesAutorises: false }],
  ["real with counts allowed (complete again)", { jeu: "real", comptesAutorises: true }],
];

test("setting off or absent: no series carries `team`, complete or reduced; the identifier stays", () => {
  for (const [nom, mode] of MODES) {
    for (const reglage of [undefined, false]) {
      const servie = servirTableau(plein(), reglage === undefined ? mode : { ...mode, afficherNoms: reglage });
      for (const serie of servie.teams) {
        assert.ok(!("team" in serie), `${nom}, setting ${String(reglage)}: team is left out`);
        assert.equal(serie.teamId, identifiantEquipe(NOM));
      }
      assert.ok(!JSON.stringify(servie).includes(NOM), `${nom}: the name is not in the answer`);
    }
  }
});

test("setting on: the series carry `team` as before, complete or reduced", () => {
  for (const [nom, mode] of MODES) {
    const servie = servirTableau(plein(), { ...mode, afficherNoms: true });
    assert.equal(servie.teams[0].team, NOM, nom);
    assert.equal(servie.teams[0].teamId, identifiantEquipe(NOM), nom);
  }
});

// ---- the route, from the setting of the environment to the answer ---------------------------------------------------------------

function ligne(debut: string | null, effectif: number) {
  return {
    team: NOM,
    period: debut === null ? "pooled_year" : "quarter",
    quarter_start: debut,
    throughput: effectif,
    items_lt: effectif,
    items_ct: effectif,
    items_old: 0, // R-20261106-66 : valait l'effectif, donc une taille de H1 nulle
    items_without_commitment: effectif,
    lead_median_days: 15,
    lead_p85_days: 30,
    cycle_median_days: 10,
    cycle_p85_days: 20,
    // R-20261106-61 : les quatre colonnes sans anciens reprennent à l'identique les statistiques avec anciens de la même ligne
    lead_median_days_excl_old: 15,
    lead_p85_days_excl_old: 30,
    cycle_median_days_excl_old: 10,
    cycle_p85_days_excl_old: 20,
  };
}

async function options(): Promise<OptionsDemarrage> {
  const depot = new DepotMemoire();
  await depot.ajouterSeuil({ code: "sample_median_min_items", value: 10, setOn: "2026-10-27", setBy: "author-1" });
  await depot.ajouterSeuil({ code: "sample_p85_min_items", value: 20, setOn: "2026-10-27", setBy: "author-1" });
  return {
    cheminContrat: CHEMIN_CONTRAT,
    creerAcces: () => new AccesFictif([...DEBUTS.map((d) => ligne(d, 40)), ligne(null, 120)]),
    creerStockage: () => Object.assign(depot, { roleCourant: async () => "x", fermer: async () => {} }),
    lireMarqueur: async () => true,
    journal: false,
    avertir: () => {},
    aujourdhui: () => "2026-10-05",
  };
}

async function reponseDuTableau(env: Record<string, string | undefined>): Promise<string> {
  const serveur = preparer(env, await options());
  const r = await serveur.app.inject({ method: "GET", url: "/api/dashboards/lead_cycle" });
  await serveur.app.close();
  assert.equal(r.statusCode, 200);
  return r.body;
}

test("the route, setting absent or false: the invented name is not in the answer, on the synthetic and on the real dataset", async () => {
  for (const jeu of ["synthetic", "real"]) {
    for (const extra of [{}, { [VARIABLES.afficherNomsEquipes]: "false" }]) {
      const corps = await reponseDuTableau(envMinimal({ MOTHRA_DATASET: jeu, ...extra }));
      assert.ok(!corps.includes(NOM), `${jeu}: no name`);
      assert.ok(!corps.includes('"team":'), `${jeu}: no team field`);
      assert.ok(corps.includes(identifiantEquipe(NOM)), `${jeu}: the identifier is served`);
    }
  }
});

test("the route, setting true: the series carry the invented name, on the synthetic and on the real dataset", async () => {
  for (const jeu of ["synthetic", "real"]) {
    const corps = await reponseDuTableau(envMinimal({ MOTHRA_DATASET: jeu, [VARIABLES.afficherNomsEquipes]: "true" }));
    assert.equal((JSON.parse(corps) as ReponseLeadCycle).teams[0].team, NOM, jeu);
  }
});

// ---- setting on: a name never enters a scope, a stored draft, a frozen version, an answer, a log or an error ----------------------------
// Server spec, scenario "A name never enters a scope nor a stored text" (task 45.1, D35 "The identifier stays the only key").
class AccesParVue implements AccesVues {
  lignes = new Map<string, LigneBase[]>();
  async lireVue(vue: Vue): Promise<LigneBase[]> {
    return this.lignes.get(vue.name) ?? [];
  }
}

const SEUILS: Array<[string, number]> = [
  ["h5_band", 0.2], ["h5_double_band", 0.4], ["h5_run_rises", 2], ["h5_run_min_cumulative_rise", 0.1], ["h5_floor", 0.8],
  ["h5_low_floor", 0.6], ["h1_lower", 1.5], ["h1_upper", 3], ["attachment_threshold_points", 10], ["sample_median_min_items", 10],
  ["sample_p85_min_items", 20],
];

test("setting on: a sheet created, reviewed and published on the invented team keeps team.<identifier>; no draft, frozen version, answer, log or error holds the name", async () => {
  const acces = new AccesParVue();
  acces.lignes.set("v_team_lead_time_throughput", [...DEBUTS.map((d) => ligne(d, 40)), ligne(null, 120)]);
  acces.lignes.set("v_task_without_team_share", DEBUTS.map((d) => ({ quarter_start: d, tasks_done: 40, tasks_without_team: 8, share_percent: 20 })));
  acces.lignes.set("v_unplanned_share", DEBUTS.map((d) => ({ quarter_start: d, unplanned: 5, unplanned_n: 40, share_percent: 12.5 })));
  acces.lignes.set("v_team_ready_queue", [{ team: NOM, quarter_start: DEBUTS[2], ready: 12 }]);
  acces.lignes.set("v_team_blocked_share", [{ team: NOM, quarter_start: DEBUTS[2], blocked_n: 40, blocked: 8, share_percent: 20 }]);
  const depot = new DepotMemoire();
  for (const [code, value] of SEUILS) await depot.ajouterSeuil({ code, value, setOn: "2026-10-27", setBy: "author-1" });
  const mode: ModeDonnees = { jeu: "synthetic", comptesAutorises: false, afficherNoms: true };
  const journal: string[] = [];
  const calcul = creerCalculCorps({ acces, contrat, seuil: 5, depot, identifiantEquipe, mode });
  const { app } = construireServeur({
    contrat,
    acces,
    reglageSeuil: null,
    journal: { level: "info", stream: { write: (m: string) => void journal.push(m) } },
    fiches: { depot, calculerCorps: calcul.calculerCorps, verifierCreation: calcul.verifierCreation, motifsNoms: motifsDeNoms([NOM]), reduite: false, aujourdhui: () => "2026-11-12" },
  });
  const scope = scopeFiche({ kind: "team", team: identifiantEquipe(NOM) });
  const auteur = { "x-mothra-user": "agile-lead-1" };
  const relecteur = { "x-mothra-user": "agile-lead-2" };
  const corps = { chart: "lead_cycle_h1", scope, dataDate: "2026-10-05", managementQuestion: "predictability", effect: { text: "Effect.", lang: "en" }, cause: { text: "Cause.", lang: "en" } };
  // An effect holding the name is refused, and the refusal does not echo it (D20 unchanged).
  const refus = await app.inject({ method: "POST", url: "/api/sheets", headers: auteur, payload: { ...corps, effect: { text: `${NOM} waits.`, lang: "en" } } });
  assert.equal(refus.statusCode, 422);
  assert.equal((refus.json() as { error: string }).error, "TEXT_REFUSED");
  const cree = await app.inject({ method: "POST", url: "/api/sheets", headers: auteur, payload: corps });
  assert.equal(cree.statusCode, 200);
  const id = (cree.json() as { id: string }).id;
  const relue = await app.inject({ method: "POST", url: `/api/sheets/${id}/review`, headers: relecteur });
  const publiee = await app.inject({ method: "POST", url: `/api/sheets/${id}/publish`, headers: auteur });
  const lue = await app.inject({ method: "GET", url: `/api/sheets/${id}` });
  assert.equal(relue.statusCode, 200);
  assert.equal(publiee.statusCode, 200);
  assert.equal(lue.statusCode, 200);
  const stockee = depot.fiches.get(id);
  assert.ok(stockee?.published !== undefined, "the sheet is frozen");
  assert.equal((lue.json() as { method: { scope: { id: string } } }).method.scope.id, scope);
  for (const [quoi, texte] of [
    ["refusal", refus.body], ["creation", cree.body], ["review", relue.body], ["publication", publiee.body], ["reading", lue.body],
    ["stored draft and frozen version", JSON.stringify(stockee)], ["log", journal.join("\n")],
  ] as const) {
    assert.ok(!texte.includes(NOM), `${quoi}: no name`);
  }
  assert.ok(journal.length > 0, "the log was written to (otherwise this check would pass empty)");
  await app.close();
});
