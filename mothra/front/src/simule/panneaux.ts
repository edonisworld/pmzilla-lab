// SIMULATED answers of the four panels of the product-scope dashboard (synthetic figures, not real data), for the development server and the
// tests of the front, until the routes read the views on a database. Nothing here calls the network. The module holds the cases on purpose:
// a value, a masked count, a masked total and a masked share, a product panel asked with a team (served for the
// product), and the refusal of the blocked share on the product scope. The totals are written out per range, as the server gives them:
// the front computes none.
// Only the entry of the bundle (src/main.ts) imports this folder; the screens receive their source by injection.
import { scopeFiche } from "@mothra/contract/equipe";
import type { Cellule, PanneauBlockedShare, PanneauCorrectionShare, PanneauDefectsInout, PanneauStoriesInout } from "@mothra/contract";

import { dansPlage } from "../api/filtres.ts";
import type { FiltresEcran } from "../api/filtres.ts";
import { RefusPanneau } from "../api/panneaux.ts";
import type { LecteurPanneau, SourcePanneaux } from "../api/panneaux.ts";

const PREMIER = "2026-Q1";      // the three closed quarters 2026-Q1 to 2026-Q3 (R-20261114-49)
const DERNIER = "2026-Q3";
const ENTETE = { threshold: 5, dataDate: "2026-10-27", dataset: "synthetic" } as const;

const valeur = (v: number): Cellule => ({ state: "value", value: v });
const masquee: Cellule = { state: "masked", threshold: 5 };

// Created and done by quarter (stories, then defects): the figures of the simulated product.
const HISTOIRES: ReadonlyArray<[string, Cellule, Cellule]> = [
  ["2026-Q1", valeur(130), valeur(110)],
  ["2026-Q2", valeur(125), valeur(115)],
  ["2026-Q3", valeur(140), valeur(120)],
];
const DEFAUTS: ReadonlyArray<[string, Cellule, Cellule]> = [
  ["2026-Q1", valeur(38), valeur(36)],
  ["2026-Q2", masquee, valeur(37)],
  ["2026-Q3", valeur(35), valeur(34)],
];
// The share of throughput in correction of each quarter, given as the contract's function would give it (the front computes none).
const PARTS_CORRECTION: ReadonlyArray<[string, Cellule, Cellule, number]> = [
  ["2026-Q1", valeur(36), valeur(110), 24.7],
  ["2026-Q2", valeur(37), valeur(115), 24.3],
  ["2026-Q3", valeur(34), valeur(120), 22.1],
];
const BLOQUE: ReadonlyArray<[string, Cellule, Cellule, number | null]> = [
  ["2026-Q1", masquee, valeur(35), null],
  ["2026-Q2", valeur(7), valeur(38), 18.4],
  ["2026-Q3", valeur(6), valeur(36), 16.7],
];

// The range totals, written out for each range of the three quarters (the front computes none). As the server does, a total is given when no
// quarter of the range is masked, otherwise it is the masked cell: a range with no entry in a table holds a masked quarter of that column.
const TOTAUX_HISTOIRES: Readonly<Record<string, readonly [number, number]>> = {
  "2026-Q1/2026-Q1": [130, 110],
  "2026-Q1/2026-Q2": [255, 225],
  "2026-Q1/2026-Q3": [395, 345],
  "2026-Q2/2026-Q2": [125, 115],
  "2026-Q2/2026-Q3": [265, 235],
  "2026-Q3/2026-Q3": [140, 120],
};
const TOTAUX_DEFAUTS_CREES: Readonly<Record<string, number>> = {
  "2026-Q1/2026-Q1": 38,
  "2026-Q3/2026-Q3": 35,
};
const TOTAUX_DEFAUTS_RESOLUS: Readonly<Record<string, number>> = {
  "2026-Q1/2026-Q1": 36,
  "2026-Q1/2026-Q2": 73,
  "2026-Q1/2026-Q3": 107,
  "2026-Q2/2026-Q2": 37,
  "2026-Q2/2026-Q3": 71,
  "2026-Q3/2026-Q3": 34,
};

const cleDePlage = (filtres: FiltresEcran): string => [filtres.from ?? PREMIER, filtres.to ?? DERNIER].join("/");
function totauxHistoires(cle: string): { created: Cellule; done: Cellule } {
  const total = TOTAUX_HISTOIRES[cle];
  return total === undefined ? { created: masquee, done: masquee } : { created: valeur(total[0]), done: valeur(total[1]) };
}
function totalOuMasque(table: Readonly<Record<string, number>>, cle: string): Cellule {
  const total = table[cle];
  return total === undefined ? masquee : valeur(total);
}

function entete(filtres: FiltresEcran, portee: string) {
  return { ...ENTETE, scope: portee, from: filtres.from ?? PREMIER, to: filtres.to ?? DERNIER };
}

function stories(filtres: FiltresEcran): PanneauStoriesInout {
  const portee = filtres.team === undefined ? "product" : scopeFiche({ kind: "team", team: filtres.team });
  return {
    ...entete(filtres, portee),
    panel: "stories-inout",
    hypothesis: "h1_second_half",
    mentions: ["indirect_indicator"],
    points: HISTOIRES.filter(([q]) => dansPlage(q, filtres.from, filtres.to)).map(([quarter, created, done]) => ({ quarter, created, done })),
    total: totauxHistoires(cleDePlage(filtres)),
  };
}

// Defects carry no team: the product row is served whatever the scope asked for (decision R-20261031-28), and the screen says so.
function defauts(filtres: FiltresEcran): PanneauDefectsInout {
  return {
    ...entete(filtres, "product"),
    panel: "defects-inout",
    hypothesis: "h3",
    mentions: ["indirect_indicator", "product_level"],
    points: DEFAUTS.filter(([q]) => dansPlage(q, filtres.from, filtres.to)).map(([quarter, created, done]) => ({ quarter, created, done })),
    total: { created: totalOuMasque(TOTAUX_DEFAUTS_CREES, cleDePlage(filtres)), done: totalOuMasque(TOTAUX_DEFAUTS_RESOLUS, cleDePlage(filtres)) },
  };
}

function correction(filtres: FiltresEcran): PanneauCorrectionShare {
  return {
    ...entete(filtres, "product"),
    panel: "correction-share",
    hypothesis: "h3",
    mentions: ["indirect_indicator", "product_level"],
    points: PARTS_CORRECTION.filter(([q]) => dansPlage(q, filtres.from, filtres.to)).map(([quarter, defectsDone, storiesDone, part]) => ({
      quarter,
      defectsDone,
      storiesDone,
      share: { state: "value" as const, value: part },
    })),
  };
}

function bloquee(filtres: FiltresEcran): PanneauBlockedShare {
  // The product scope is refused by the server (decision Q59): the simulated route refuses it too.
  if (filtres.team === undefined) throw new RefusPanneau("SCOPE_INVALID");
  return {
    ...entete(filtres, scopeFiche({ kind: "team", team: filtres.team })),
    panel: "blocked-share",
    hypothesis: "dependencies_explanation",
    mentions: ["indirect_indicator", "blocked_share_current_links"],
    points: BLOQUE.filter(([q]) => dansPlage(q, filtres.from, filtres.to)).map(([quarter, blocked, blockedN, part]) => ({
      quarter,
      blocked,
      blockedN,
      share: part === null ? { state: "masked" as const, threshold: 5 } : { state: "value" as const, value: part },
    })),
  };
}

export const lirePanneauSimule: LecteurPanneau = async (code, filtres) => {
  if (code === "stories-inout") return stories(filtres);
  if (code === "defects-inout") return defauts(filtres);
  if (code === "correction-share") return correction(filtres);
  return bloquee(filtres);
};

export const SOURCE_PANNEAUX_SIMULEE: SourcePanneaux = { lire: lirePanneauSimule, simulee: true };
