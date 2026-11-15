// Task 45.1 (design D35, "Team names on screen", R-20261104-36 N1 (a)): with the server's setting off the series of the dashboard answer carry
// no `team`; the dashboard page then works on the opaque identifier alone. With the setting on, the two selectors show the names in one order.
// Invented team names only.
import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";

import type { ReponseLeadCycle } from "@mothra/contract";
import { identifiantEquipe, scopeFiche } from "@mothra/contract/equipe";

import { BarreFiltres } from "../src/composants/BarreFiltres.ts";
import { ContenuTableau, ouvrirBrouillon } from "../src/pages/PageTableau.ts";
import { rendre } from "./rendu.ts";

const NOM = "Équipe Exemple";
const ID = identifiantEquipe(NOM);
const val = (v: number) => ({ state: "value" as const, value: v });

// An answer as the service layer serves it with the setting off: no `team` in the series.
const sansNom: ReponseLeadCycle = {
  threshold: 5,
  dataDate: "2026-10-27",
  dataset: "synthetic",
  product: [],
  teams: [{ teamId: ID, points: [{ quarter: "2026-Q2", lead: val(29), cycle: val(7), items: val(22) }] }],
};

function contenu(portee: string, donnees: ReponseLeadCycle): string {
  return rendre(h(ContenuTableau, { reponse: donnees, portee, surPortee: () => undefined, fiche: { genre: "aucune" }, surFaire: () => undefined, surCreer: () => undefined, simulee: true }), "en");
}

test("an answer without `team`: the selector offers the identifier, the chosen team's points are drawn, nothing throws", () => {
  const html = contenu(ID, sansNom);
  assert.match(html, new RegExp(`<option value="${ID}" selected="">${ID}</option>`));
  assert.ok(html.includes("29"), "the points of the team are shown");
  assert.ok(!html.includes(NOM));
});

test("a sheet is made for the identifier of the series when the answer holds no name: the scope is team.<identifier>", async () => {
  const demandes: unknown[] = [];
  const creer = async (demande: unknown) => {
    demandes.push(demande);
    return { id: "d-1", state: "draft" as const };
  };
  const etat = await ouvrirBrouillon(creer, ID, "2026-10-27", "lead_cycle_h1", {}, undefined, ID);
  assert.deepEqual(etat, { genre: "brouillon", id: "d-1" });
  assert.deepEqual(demandes, [{ chart: "lead_cycle_h1", scope: scopeFiche({ kind: "team", team: ID }), dataDate: "2026-10-27" }]);
  assert.ok(!JSON.stringify(demandes).includes(NOM));
});

// ---- the selectors: one order, the same in all of them (R-20261104-62 point 2) -----------------------------------------------------

const ID_1 = "aaaaaaaaaaaaaaaa";
const ID_2 = "bbbbbbbbbbbbbbbb";
const ID_3 = "cccccccccccccccc";
const POINTS = [{ quarter: "2026-Q2", lead: val(29), cycle: val(7), items: val(22) }];
// Invented names whose alphabetical order is not the order of the identifiers: Alpha (b), Mille (c), Zeta (a).
const NOMS: Record<string, string> = { [ID_1]: "Équipe Zeta", [ID_2]: "Équipe Alpha", [ID_3]: "Équipe Mille" };

function reponseDe(avecNoms: boolean): ReponseLeadCycle {
  return {
    threshold: 5,
    dataDate: "2026-10-27",
    dataset: "synthetic",
    product: [],
    teams: [ID_3, ID_1, ID_2].map((teamId) => ({ ...(avecNoms ? { team: NOMS[teamId] } : {}), teamId, points: POINTS })),
  };
}

const options = (html: string): string[][] => [...html.matchAll(/<option value="([^"]*)"[^>]*>([^<]*)<\/option>/g)].map((m) => [m[1], m[2]]);

function barre(donnees: ReponseLeadCycle): string[][] {
  const html = rendre(
    h(BarreFiltres, { equipes: donnees.teams.map((e) => e.teamId), trimestres: ["2026-Q2"], filtres: { team: undefined, from: undefined, to: undefined }, surFiltres: () => undefined, tableau: donnees }),
    "en",
  );
  return options(html).filter(([valeur]) => [ID_1, ID_2, ID_3].includes(valeur));
}

function selectHistorique(donnees: ReponseLeadCycle): string[][] {
  const premiere = donnees.teams.find((e) => e.teamId === ID_1);
  const portee = premiere?.team ?? ID_1;
  return options(contenu(portee, donnees)).filter((o) => o[0] !== "");
}

test("setting off: every selector is in the order of the identifiers and shows the identifiers", () => {
  const attendu = [[ID_1, ID_1], [ID_2, ID_2], [ID_3, ID_3]];
  assert.deepEqual(barre(reponseDe(false)), attendu);
  assert.deepEqual(selectHistorique(reponseDe(false)), attendu);
});

// R-20261104-69 Q2: the screen opens on the first team of the list shown (with the bar and an unknown scope), one test per state.
function ouverture(avecNoms: boolean): string {
  const valeurs: Record<string, number> = { [ID_1]: 111, [ID_2]: 222, [ID_3]: 333 };
  const donnees: ReponseLeadCycle = {
    ...reponseDe(avecNoms),
    teams: reponseDe(avecNoms).teams.map((e) => ({ ...e, points: [{ quarter: "2026-Q2", lead: val(valeurs[e.teamId]), cycle: val(7), items: val(22) }] })),
  };
  const html = rendre(
    h(ContenuTableau, { reponse: donnees, portee: "inconnue", surPortee: () => undefined, fiche: { genre: "aucune" }, surFaire: () => undefined, surCreer: () => undefined, simulee: true, barre: h("span") }),
    "en",
  );
  return html;
}

test("setting off: the screen opens on the first team in the order of the identifiers", () => {
  const html = ouverture(false);
  assert.ok(html.includes("111") && !html.includes("222") && !html.includes("333"));
});

test("setting on: the screen opens on the first team of the alphabetical list of the names", () => {
  const html = ouverture(true);
  assert.ok(html.includes("222") && !html.includes("111") && !html.includes("333"));
});

test("setting on: every selector is in the alphabetical order of the names, the value stays the identifier in the bar, the same order in all of them", () => {
  const donnees = reponseDe(true);
  assert.deepEqual(barre(donnees), [[ID_2, "Équipe Alpha"], [ID_3, "Équipe Mille"], [ID_1, "Équipe Zeta"]]);
  const historique = selectHistorique(donnees);
  assert.deepEqual(historique.map((o) => o[1]), ["Équipe Alpha", "Équipe Mille", "Équipe Zeta"]);
  assert.deepEqual(historique.map((o) => o[1]), barre(donnees).map((o) => o[1]));
});
