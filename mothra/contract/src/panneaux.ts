// The answers and the pure functions of the four count panels of the product-scope dashboard (mothra-slices D35, task 37.1, contract part;
// author's decision R-20261031-01, Q5 (a): one route and one schema per panel). One data layer (task 18.0): the server and the front import
// these types from the contract package only. Codes only, no text (invariant 11); labels belong to the catalogues of the front (task 37.2).
// No collection indexed by team: an answer holds the one scope that was served. No verdict of hypothesis 3 nor of the second half of
// hypothesis 1 is written here (D35, "Indirect indicators only"). No ranking.
// The input rows are the output of the masking function of task 15.3 (cells), never raw counts: the range total and the share rest on it.
// Replaces: nothing. Removal: with the end of the exception F12 (review of task 44.1), if the panels leave the dashboard.
import Type from "typebox";
import type { Static } from "typebox";

import { SchemaCellule, SchemaCelluleMesuree, cellule } from "./cellule.ts";
import type { Cellule } from "./cellule.ts";
import { MOTIF_IDENTIFIANT_EQUIPE, scopeFiche } from "./equipe.ts";
import { totalDePlage } from "./filtres.ts";
import type { ResultatFiltres } from "./filtres.ts";
import { PLANCHER } from "./plancher.ts";

// The panel codes, their hypotheses and their mentions live in `codes-panneaux.ts` (browser-safe, no import); re-exported here under the same
// names. The truncated-quarter flag is removed (R-20261114-49, design D9): no `flags` field, no `premierTrimestreRetenu`.
export { CODES_PANNEAUX, HYPOTHESES_PANNEAUX, MENTIONS_PANNEAUX } from "./codes-panneaux.ts";
export type { CodePanneau } from "./codes-panneaux.ts";

// ---- inputs (already masked) -------------------------------------------------------------------------------------------------------
export type GroupeType = "story" | "defect";
// One masked row of `v_team_flow_inout` for the scope served: a quarter label, the type group, the two counts as cells.
export interface EntreeFlux {
  quarter: string;
  group: GroupeType;
  created: Cellule;
  done: Cellule;
}
// One masked row of the blocked share view of slice 1 for the scope served.
export interface EntreeBloque {
  quarter: string;
  blocked: Cellule;
  blockedN: Cellule;
  share: Cellule;
}

// ---- schemas -----------------------------------------------------------------------------------------------------------------------
const Dataset = Type.Optional(Type.Union([Type.Literal("synthetic"), Type.Literal("real")]));
const Portee = Type.String({ pattern: `^(product|team\\.${MOTIF_IDENTIFIANT_EQUIPE.source.slice(1, -1)})$` });

const base = {
  scope: Portee,
  from: Type.String(),
  to: Type.String(),
  threshold: Type.Integer({ minimum: PLANCHER }),
  dataDate: Type.String(),
  dataset: Dataset,
};
// The mentions are fixed per panel (tuples): a list missing one of its codes fails the schema (blocked share without both mentions).
const MentionsIndirect = Type.Tuple([Type.Literal("indirect_indicator")]);
const MentionsProduit = Type.Tuple([Type.Literal("indirect_indicator"), Type.Literal("product_level")]);
const MentionsBloque = Type.Tuple([Type.Literal("indirect_indicator"), Type.Literal("blocked_share_current_links")]);
const entetePanneau = {
  "stories-inout": { ...base, panel: Type.Literal("stories-inout"), hypothesis: Type.Literal("h1_second_half"), mentions: MentionsIndirect },
  "correction-share": { ...base, panel: Type.Literal("correction-share"), hypothesis: Type.Literal("h3"), mentions: MentionsProduit },
  "defects-inout": { ...base, panel: Type.Literal("defects-inout"), hypothesis: Type.Literal("h3"), mentions: MentionsProduit },
  "blocked-share": { ...base, panel: Type.Literal("blocked-share"), hypothesis: Type.Literal("dependencies_explanation"), mentions: MentionsBloque },
} as const;

const PointFlux = Type.Object(
  { quarter: Type.String(), created: SchemaCellule, done: SchemaCellule },
  { additionalProperties: false },
);
const TotalFlux = Type.Object({ created: SchemaCellule, done: SchemaCellule }, { additionalProperties: false });

export const SchemaPanneauStoriesInout = Type.Object(
  { ...entetePanneau["stories-inout"], points: Type.Array(PointFlux), total: TotalFlux },
  { additionalProperties: false },
);
export const SchemaPanneauDefectsInout = Type.Object(
  { ...entetePanneau["defects-inout"], points: Type.Array(PointFlux), total: TotalFlux },
  { additionalProperties: false },
);
export const SchemaPanneauCorrectionShare = Type.Object(
  {
    ...entetePanneau["correction-share"],
    points: Type.Array(
      Type.Object(
        { quarter: Type.String(), defectsDone: SchemaCellule, storiesDone: SchemaCellule, share: SchemaCelluleMesuree },
        { additionalProperties: false },
      ),
    ),
  },
  { additionalProperties: false },
);
export const SchemaPanneauBlockedShare = Type.Object(
  {
    ...entetePanneau["blocked-share"],
    points: Type.Array(
      Type.Object(
        { quarter: Type.String(), blocked: SchemaCellule, blockedN: SchemaCellule, share: SchemaCelluleMesuree },
        { additionalProperties: false },
      ),
    ),
  },
  { additionalProperties: false },
);

// The reduced form of any panel on real data (D34 point 7): the header and the reduced_form code, no point, no total, no count and
// no share of a count. Chosen at the registration of the route; the explained empty state is the front's.
export const SchemaPanneauReduit = Type.Object(
  {
    panel: Type.Union([
      Type.Literal("stories-inout"),
      Type.Literal("correction-share"),
      Type.Literal("defects-inout"),
      Type.Literal("blocked-share"),
    ]),
    scope: Portee,
    from: Type.String(),
    to: Type.String(),
    threshold: Type.Integer({ minimum: PLANCHER }),
    dataDate: Type.String(),
    hypothesis: Type.Union([Type.Literal("h1_second_half"), Type.Literal("h3"), Type.Literal("dependencies_explanation")]),
    mentions: Type.Array(
      Type.Union([Type.Literal("indirect_indicator"), Type.Literal("product_level"), Type.Literal("blocked_share_current_links")]),
    ),
    limits: Type.Tuple([Type.Literal("reduced_form")]),
    dataset: Dataset,
  },
  { additionalProperties: false },
);

export type PanneauStoriesInout = Static<typeof SchemaPanneauStoriesInout>;
export type PanneauDefectsInout = Static<typeof SchemaPanneauDefectsInout>;
export type PanneauCorrectionShare = Static<typeof SchemaPanneauCorrectionShare>;
export type PanneauBlockedShare = Static<typeof SchemaPanneauBlockedShare>;
export type PanneauReduit = Static<typeof SchemaPanneauReduit>;
export type PanneauComplet = PanneauStoriesInout | PanneauDefectsInout | PanneauCorrectionShare | PanneauBlockedShare;

// The refusal of the blocked share panel on the product scope (author's decision R-20261031-28, Q59): a typed error of the contract, which
// the route turns into 422 with the existing code SCOPE_INVALID (D35). Deliberately not a TypeError (a caller error).
export class PorteeProduitRefusee extends Error {
  readonly code = "SCOPE_INVALID" as const;
  readonly status = 422 as const;
  constructor() {
    super("panneau : portée produit non servie");
    this.name = "PorteeProduitRefusee";
  }
}

// ---- functions ---------------------------------------------------------------------------------------------------------------------
type FiltresOk = Extract<ResultatFiltres, { ok: true }>;
type JeuDeDonnees = "synthetic" | "real";

// The share of throughput in correction, in percent: done defects over done defects plus done stories, from the product row. Given only
// when neither term is masked, otherwise the masked cell of the highest threshold met; nothing of a masked term is estimated.
export function partDeDebitEnCorrection(defautsFinis: Cellule, histoiresFinies: Cellule): Cellule | { state: "value"; value: number } {
  if (defautsFinis.state === "masked" || histoiresFinies.state === "masked") {
    const seuils = [defautsFinis, histoiresFinies].map((c) => (c.state === "masked" ? c.threshold : PLANCHER));
    return { state: "masked", threshold: Math.max(...seuils) };
  }
  // Rounded to one decimal, like `share_percent` of the views (author's decision R-20261031-28, Q60).
  return { state: "value", value: Math.round((1000 * defautsFinis.value) / (defautsFinis.value + histoiresFinies.value)) / 10 };
}

// A quarter without a row is the masked cell of the threshold: nothing is estimated for an absent row.
const absente = (seuil: number): Cellule => cellule(null, seuil);

const MOTIF_ETIQUETTE = /^\d{4}-Q[1-4]$/;

// The rows by quarter label. A label outside `AAAA-Qn` (a raw date from the adapter, say) or a quarter twice is a caller error: nothing
// is silently overwritten (a team row could otherwise be served under the product) nor silently masked.
function parTrimestre<T extends { quarter: string }>(lignes: readonly T[]): Map<string, T> {
  const carte = new Map<string, T>();
  for (const l of lignes) {
    if (!MOTIF_ETIQUETTE.test(l.quarter)) throw new TypeError("panneau : trimestre AAAA-Qn attendu");
    if (carte.has(l.quarter)) throw new TypeError("panneau : trimestre en double");
    carte.set(l.quarter, l);
  }
  return carte;
}

// The common fields of an answer, the panel-specific ones being literals of each builder.
function commun(f: FiltresOk, portee: string, dataDate: string, seuil: number, dataset?: JeuDeDonnees) {
  return {
    scope: portee,
    from: f.from,
    to: f.to,
    threshold: seuil,
    dataDate,
    ...(dataset === undefined ? {} : { dataset }),
  };
}

function pointsFlux(lignes: readonly EntreeFlux[], groupe: GroupeType, f: FiltresOk, seuil: number) {
  for (const l of lignes) {
    if (!MOTIF_ETIQUETTE.test(l.quarter)) throw new TypeError("panneau : trimestre AAAA-Qn attendu");
  }
  const parTrimestreDuGroupe = parTrimestre(lignes.filter((l) => l.group === groupe));
  const points = f.periods.map((q) => {
    const l = parTrimestreDuGroupe.get(q);
    return { quarter: q, created: l?.created ?? absente(seuil), done: l?.done ?? absente(seuil) };
  });
  // The strict function of group 31, reused, never copied: a total only when no quarter of the range is masked.
  const total = {
    created: totalDePlage(points.map((p) => ({ period: p.quarter, count: p.created })), f.from, f.to),
    done: totalDePlage(points.map((p) => ({ period: p.quarter, count: p.done })), f.from, f.to),
  };
  return { points, total };
}

// Stories created against done: the scope served is the requested one (one team or the product).
export function panneauStoriesInout(lignes: readonly EntreeFlux[], f: FiltresOk, dataDate: string, seuil: number, dataset?: JeuDeDonnees): PanneauStoriesInout {
  return {
    ...commun(f, scopeFiche(f.scope), dataDate, seuil, dataset),
    panel: "stories-inout",
    hypothesis: "h1_second_half",
    mentions: ["indirect_indicator"],
    ...pointsFlux(lignes, "story", f, seuil),
  };
}

// Defects created against resolved: product level only while defects carry no team (D33): the scope served is always the product.
export function panneauDefectsInout(lignes: readonly EntreeFlux[], f: FiltresOk, dataDate: string, seuil: number, dataset?: JeuDeDonnees): PanneauDefectsInout {
  return {
    ...commun(f, "product", dataDate, seuil, dataset),
    panel: "defects-inout",
    hypothesis: "h3",
    mentions: ["indirect_indicator", "product_level"],
    ...pointsFlux(lignes, "defect", f, seuil),
  };
}

// Share of throughput in correction, from the product row (done defects and done stories), product level only.
export function panneauCorrectionShare(lignes: readonly EntreeFlux[], f: FiltresOk, dataDate: string, seuil: number, dataset?: JeuDeDonnees): PanneauCorrectionShare {
  const defauts = pointsFlux(lignes, "defect", f, seuil).points;
  const histoires = pointsFlux(lignes, "story", f, seuil).points;
  const points = f.periods.map((q, i) => ({
    quarter: q,
    defectsDone: defauts[i].done,
    storiesDone: histoires[i].done,
    share: partDeDebitEnCorrection(defauts[i].done, histoires[i].done),
  }));
  return {
    ...commun(f, "product", dataDate, seuil, dataset),
    panel: "correction-share",
    hypothesis: "h3",
    mentions: ["indirect_indicator", "product_level"],
    points,
  };
}

// Share of done items blocked by another team (the "dependencies" explanation): rows of the slice 1 view for the scope served.
export function panneauBlockedShare(lignes: readonly EntreeBloque[], f: FiltresOk, dataDate: string, seuil: number, dataset?: JeuDeDonnees): PanneauBlockedShare {
  // The view of slice 1 has no product row, and a sum of masked cells is not allowed: the product scope is refused (Q59); the route
  // answers 422 with `code`.
  if (f.scope.kind === "product") throw new PorteeProduitRefusee();
  const parLigne = parTrimestre(lignes);
  const points = f.periods.map((q) => {
    const l = parLigne.get(q);
    return {
      quarter: q,
      blocked: l?.blocked ?? absente(seuil),
      blockedN: l?.blockedN ?? absente(seuil),
      share: l?.share ?? absente(seuil),
    };
  });
  return {
    ...commun(f, scopeFiche(f.scope), dataDate, seuil, dataset),
    panel: "blocked-share",
    hypothesis: "dependencies_explanation",
    mentions: ["indirect_indicator", "blocked_share_current_links"],
    points,
  };
}

// D34 point 7: the reduced answer of a panel on real data (called by reduceToStatistics).
export function reduirePanneau(p: PanneauComplet): PanneauReduit {
  return {
    panel: p.panel,
    scope: p.scope,
    from: p.from,
    to: p.to,
    threshold: p.threshold,
    dataDate: p.dataDate,
    hypothesis: p.hypothesis,
    mentions: [...p.mentions],
    limits: ["reduced_form"],
    ...(p.dataset === undefined ? {} : { dataset: p.dataset }),
  };
}
