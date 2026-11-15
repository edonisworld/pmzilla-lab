// The panels of the product-scope dashboard, inside the filter bar of the second screen (mothra-slices D35, task 37.2). Each panel names the
// hypothesis it serves, carries the mentions the contract decides (a blocked share without one of its two mentions is not shown), shows its
// cells as received (a masked cell is a masked cell, a masked total is a masked cell), shows the three closed quarters of the window, and signals a served
// scope different from the requested one. The blocked share is shown, and requested, only when a team is chosen (decision Q59). Never a time
// per segment, no panel of the versions (decision Q9). Every label comes from the catalogues; the front computes no total, share or state: it shows what the
// contract's functions returned.
// Each count panel is a table (the chart's equivalent). No "make it a sheet" action here: only the charts that have a served sheet keep it
// (author's decision R-20261031-51, Q92).
// Replaces: nothing. Removal: with the end of the exception F12 (review of task 44.1), if the panels leave the dashboard.
import { useQuery } from "@tanstack/react-query";
import { createElement as h } from "react";
import type { ReactElement } from "react";
import { useIntl } from "react-intl";

import type { Cellule, CodePanneau, PanneauBlockedShare, PanneauComplet, PanneauCorrectionShare, PanneauDefectsInout, PanneauStoriesInout } from "@mothra/contract";
import { CODES_PANNEAUX, MENTIONS_PANNEAUX } from "@mothra/contract/listes-fiche";

import type { FiltresEcran } from "../api/filtres.ts";
import { estRefusFiltres, estReduit, optionsPanneau, porteeDemandee, porteeServieDiffere } from "../api/panneaux.ts";
import type { CodeRefusFiltres, LecteurPanneau, ReponsePanneau } from "../api/panneaux.ts";
import { cleErreur } from "../api/vue.ts";
import { CelluleDeTableau, CelluleMasquee } from "./Cellule.ts";
import { Mentions } from "./FicheMentions.ts";
import { libelleTrimestre } from "./trimestre.ts";

// The catalogue keys, by literal (the catalogue test finds every key used in the sources).
const CLES_TITRE: Record<CodePanneau, string> = {
  "stories-inout": "tableau.panel.title.stories-inout",
  "correction-share": "tableau.panel.title.correction-share",
  "defects-inout": "tableau.panel.title.defects-inout",
  "blocked-share": "tableau.panel.title.blocked-share",
};
const CLES_HYPOTHESE = {
  h1_second_half: "tableau.hypothesis.h1_second_half",
  h3: "tableau.hypothesis.h3",
  dependencies_explanation: "tableau.hypothesis.dependencies_explanation",
} as const;
const CLES_REFUS_FILTRES: Record<CodeRefusFiltres, string> = { SCOPE_INVALID: "error.SCOPE_INVALID", RANGE_INVALID: "error.RANGE_INVALID" };

// The panels of the screen for the filters in force: the blocked share only when a team is chosen (decision Q59), so that on the product
// scope there is no panel and no request for it. The order is the contract's.
export function panneauxAffiches(filtres: FiltresEcran): readonly CodePanneau[] {
  return CODES_PANNEAUX.filter((code) => code !== "blocked-share" || filtres.team !== undefined);
}

function CelluleMesure({ cellule }: { cellule: Cellule }): ReactElement {
  const intl = useIntl();
  if (cellule.state === "masked") return h(CelluleMasquee);
  const part = intl.formatNumber(cellule.value, { maximumFractionDigits: 1 });
  return h("td", { className: "cellule cellule-valeur", "data-state": "value" }, intl.formatMessage({ id: "tableau.panel.shareFormat" }, { share: part }));
}

// The quarter cell of a panel row: its label only (the truncated-quarter flag is gone, R-20261114-49, design D9).
export function CelluleTrimestre({ trimestre }: { trimestre: string }): ReactElement {
  const intl = useIntl();
  const formater = (cle: string, valeurs: { year: string; quarter: string }): string => intl.formatMessage({ id: cle }, valeurs);
  return h("td", { className: "cellule" }, libelleTrimestre(trimestre, formater));
}

function Entete({ colonnes }: { colonnes: readonly string[] }): ReactElement {
  const intl = useIntl();
  return h("thead", null, h("tr", null, colonnes.map((cle) => h("th", { key: cle, scope: "col" }, intl.formatMessage({ id: cle })))));
}

// Created against done (stories, defects): one row per quarter and the range total the contract gave.
function TableauFlux({ reponse }: { reponse: PanneauStoriesInout | PanneauDefectsInout }): ReactElement {
  const intl = useIntl();
  return h(
    "table",
    { className: "tableau" },
    h(Entete, { colonnes: ["tableau.column.quarter", "tableau.panel.column.created", "tableau.panel.column.done"] }),
    h(
      "tbody",
      null,
      reponse.points.map((point) =>
        h("tr", { key: point.quarter }, h(CelluleTrimestre, { trimestre: point.quarter }), h(CelluleDeTableau, { valeur: point.created }), h(CelluleDeTableau, { valeur: point.done })),
      ),
      h(
        "tr",
        { className: "tableau-total" },
        h("th", { scope: "row" }, intl.formatMessage({ id: "tableau.panel.total" })),
        h(CelluleDeTableau, { valeur: reponse.total.created }),
        h(CelluleDeTableau, { valeur: reponse.total.done }),
      ),
    ),
  );
}

function TableauCorrection({ reponse }: { reponse: PanneauCorrectionShare }): ReactElement {
  return h(
    "table",
    { className: "tableau" },
    h(Entete, { colonnes: ["tableau.column.quarter", "tableau.panel.column.defectsDone", "tableau.panel.column.storiesDone", "tableau.panel.column.share"] }),
    h(
      "tbody",
      null,
      reponse.points.map((point) =>
        h(
          "tr",
          { key: point.quarter },
          h(CelluleTrimestre, { trimestre: point.quarter }),
          h(CelluleDeTableau, { valeur: point.defectsDone }),
          h(CelluleDeTableau, { valeur: point.storiesDone }),
          h(CelluleMesure, { cellule: point.share }),
        ),
      ),
    ),
  );
}

function TableauBloque({ reponse }: { reponse: PanneauBlockedShare }): ReactElement {
  return h(
    "table",
    { className: "tableau" },
    h(Entete, { colonnes: ["tableau.column.quarter", "tableau.panel.column.blocked", "tableau.panel.column.blockedN", "tableau.panel.column.share"] }),
    h(
      "tbody",
      null,
      reponse.points.map((point) =>
        h(
          "tr",
          { key: point.quarter },
          h(CelluleTrimestre, { trimestre: point.quarter }),
          h(CelluleDeTableau, { valeur: point.blocked }),
          h(CelluleDeTableau, { valeur: point.blockedN }),
          h(CelluleMesure, { cellule: point.share }),
        ),
      ),
    ),
  );
}

function Corps({ reponse }: { reponse: PanneauComplet }): ReactElement {
  if (reponse.panel === "correction-share") return h(TableauCorrection, { reponse });
  if (reponse.panel === "blocked-share") return h(TableauBloque, { reponse });
  return h(TableauFlux, { reponse });
}

// One panel from its answer. `demandee` is the scope the screen asked for: an answer for another scope (a product panel asked with a team)
// is signalled by the catalogue label `served_scope_differs`.
export function VuePanneau({ reponse, demandee }: { reponse: ReponsePanneau; demandee: string }): ReactElement {
  const intl = useIntl();
  const titre = h("h3", null, intl.formatMessage({ id: CLES_TITRE[reponse.panel] }));
  const mentions: readonly string[] = reponse.mentions;
  // The mentions are the contract's: a panel that arrives without one of them is not shown (a blocked share needs both of its two).
  if (MENTIONS_PANNEAUX[reponse.panel].some((code) => !mentions.includes(code))) {
    return h(
      "section",
      { className: "panneau", "data-panel": reponse.panel },
      titre,
      h("p", { role: "alert", className: "page-erreur" }, intl.formatMessage({ id: "tableau.panel.mentionMissing" })),
    );
  }
  return h(
    "section",
    { className: "panneau", "data-panel": reponse.panel },
    titre,
    h("p", { className: "tableau-hypothese", "data-hypothesis": reponse.hypothesis }, intl.formatMessage({ id: CLES_HYPOTHESE[reponse.hypothesis] })),
    h(Mentions, { codes: reponse.mentions }),
    reponse.dataset === "synthetic"
      ? // A plain paragraph: the one role=note of a screen is the banner of the shell (R-20261101-129).
        h("p", { className: "fiche-jeu-synthetique", "data-jeu": "synthetic" }, intl.formatMessage({ id: "fiche.syntheticNotice" }))
      : null,
    porteeServieDiffere(demandee, reponse.scope)
      ? h("p", { className: "tableau-date", "data-signal": "served_scope_differs" }, intl.formatMessage({ id: "tableau.signal.served_scope_differs" }))
      : null,
    estReduit(reponse)
      ? h("p", { className: "tableau-date" }, intl.formatMessage({ id: "fiche.limit.reduced_form" }))
      : h(
          "div",
          // The scrolling container is reached by the keyboard (A-85).
          { className: "tableau-conteneur", tabIndex: 0 },
          h("p", { className: "tableau-seuil" }, intl.formatMessage({ id: "tableau.threshold" }, { threshold: reponse.threshold })),
          h(Corps, { reponse }),
        ),
  );
}

function PanneauLu({ code, filtres, lire }: { code: CodePanneau; filtres: FiltresEcran; lire: LecteurPanneau }): ReactElement {
  const intl = useIntl();
  const requete = useQuery(optionsPanneau(code, filtres, lire));
  if (requete.data !== undefined) return h(VuePanneau, { reponse: requete.data, demandee: porteeDemandee(filtres) });
  const titre = h("h3", null, intl.formatMessage({ id: CLES_TITRE[code] }));
  if (requete.isError) {
    // The code of the service's refusal, shown through its catalogue key; any other failure is the internal error.
    const brut: unknown = requete.error;
    const refus = typeof brut === "object" && brut !== null && "code" in brut && typeof brut.code === "string" ? brut.code : "INTERNAL";
    // One code DATA_DATE_STALE, two texts (R-20261112-34): on a panel the quarter changed under the page, so the text asks for a reload.
    const cle = estRefusFiltres(refus) ? CLES_REFUS_FILTRES[refus] : refus === "DATA_DATE_STALE" ? "error.DATA_DATE_STALE_PANEL" : cleErreur(refus);
    return h("section", { className: "panneau", "data-panel": code }, titre, h("p", { role: "alert", className: "page-erreur" }, intl.formatMessage({ id: cle })));
  }
  return h("section", { className: "panneau", "data-panel": code }, titre, h("p", { role: "status" }, intl.formatMessage({ id: "page.loading" })));
}

export function SectionPanneaux({ lire, filtres }: { lire: LecteurPanneau; filtres: FiltresEcran }): ReactElement {
  const intl = useIntl();
  return h(
    "div",
    { className: "panneaux" },
    panneauxAffiches(filtres).map((code) => h(PanneauLu, { key: code, code, filtres, lire })),
    // The blocked share needs a team (decision Q59): on the product scope the screen says so, and asks nothing.
    filtres.team === undefined
      ? h("p", { className: "tableau-date", "data-note": "team-required" }, intl.formatMessage({ id: "tableau.panel.blocked-share.teamRequired" }))
      : null,
  );
}
