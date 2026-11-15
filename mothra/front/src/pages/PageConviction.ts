// The conviction page (mothra-demo-habillage D2, D6, D11): the statement of the kind and, under it, the sheet it reads. Which sheet: the
// identifier of the address, else the last sheet of that kind that the caller remembers (the memory is given by the caller, never read here),
// else the explained empty state with the link to the dashboard. A sheet attached to another hypothesis than the kind of the address is not
// shown (the empty state). The page calls the existing route of the sheet only, through the reader the caller gives; it holds no field to
// type a verdict and no action of the life cycle (those stay on the workflow screen).
// Lot 3b: the kind hypothesis 1; lot 3c: the kind hypothesis 5 too (a sheet of the other hypothesis gets the empty state).
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createElement as h } from "react";
import type { ReactElement } from "react";
import { useIntl } from "react-intl";

import type { GraphiqueDeFiche } from "@mothra/contract/listes-fiche";

import { adresseFiche } from "../api/adresse.ts";
import type { AdresseConviction } from "../api/adresse.ts";
import { cleErreur, ErreurApi } from "../api/vue.ts";
import { optionsFiche } from "../api/ficheLecture.ts";
import type { LecteurFiche } from "../api/ficheLecture.ts";
import { ADRESSE_TABLEAU } from "../api/filtres.ts";
import { CLE_LEAD_CYCLE } from "../api/leadCycle.ts";
import type { TableauEnMemoire } from "../composants/libelleEquipe.ts";
import { EtatVide } from "../composants/EtatVide.ts";
import { FicheConviction } from "../composants/FicheConviction.ts";
import { CLES_CONVICTION, HYPOTHESE_DU_GENRE } from "../convictions.ts";
import { GabaritFiche } from "../gabarits/GabaritFiche.ts";

// The kinds whose sheet this page reads: lot 3c adds the kind hypothesis 5 (R-20261103-14 Q1 (a)); on real data the application never opens it.
// Replaces: nothing. Removal: with the closing of the list of kinds (D1); `CONVICTIONS_LIVREES` is removed (R-20261103-24 Q4 (b)).
const GENRES_LUS: readonly GraphiqueDeFiche[] = ["lead_cycle_h1", "lead_cycle_h5"];

// A reader that is never called (the query is not enabled without a sheet to read and a reader).
const SANS_LECTEUR: LecteurFiche = () => Promise.reject(new ErreurApi("INTERNAL"));

export interface PropsPageConviction {
  conviction: AdresseConviction;
  // The reader of one sheet, injected by the entry of the bundle (`lireFicheHttp`); without it no sheet can be opened.
  lire?: LecteurFiche;
  // The identifier of the last sheet of a kind, remembered by the caller (D11); used only when the address holds no identifier.
  fichePrecedente?: (genre: GraphiqueDeFiche) => string | undefined;
  // The masking threshold of the dashboard answer, for the footer.
  seuilMasquage?: number;
  // Whether the dashboard is offered (its source is given): the empty state and the sheet link to it only then.
  avecTableau?: boolean;
  // Whether the life cycle screens are offered (their source is given): the page then links a sheet in progress to its screen (A-04).
  avecCycle?: boolean;
}

function SansFiche({ genre, avecTableau }: { genre: GraphiqueDeFiche; avecTableau: boolean }): ReactElement {
  return h(GabaritFiche, {
    enonce: CLES_CONVICTION[genre].enonce,
    preuve: h(EtatVide, { phrase: "conviction.empty", action: avecTableau ? { cle: "nav.dashboard", adresse: ADRESSE_TABLEAU } : undefined }),
  });
}

export function PageConviction({ conviction, lire, fichePrecedente, seuilMasquage, avecTableau = true, avecCycle = false }: PropsPageConviction): ReactElement {
  const intl = useIntl();
  const tableau = useQueryClient().getQueryData<TableauEnMemoire>(CLE_LEAD_CYCLE);
  const genre = conviction.genre;
  const lisible = GENRES_LUS.includes(genre);
  const id = lisible ? (conviction.id ?? fichePrecedente?.(genre)) : undefined;
  const requete = useQuery({ ...optionsFiche(lire ?? SANS_LECTEUR, id ?? ""), enabled: lire !== undefined && id !== undefined });
  if (id === undefined || lire === undefined) return h(SansFiche, { genre, avecTableau });
  if (requete.isError) {
    const code = requete.error instanceof ErreurApi ? requete.error.code : "INTERNAL";
    // A-98 (author's decision of 2026-11-08, question 22): an unknown or vanished sheet is an empty state, not a failure; permanent (a real outage keeps its alert).
    if (code === "UNKNOWN_SHEET") return h(SansFiche, { genre, avecTableau });
    return h(GabaritFiche, { enonce: CLES_CONVICTION[genre].enonce, preuve: h("p", { role: "alert", className: "page-erreur" }, intl.formatMessage({ id: cleErreur(code) })) });
  }
  const fiche = requete.data;
  if (fiche === undefined) {
    return h(GabaritFiche, { enonce: CLES_CONVICTION[genre].enonce, preuve: h("p", { role: "status" }, intl.formatMessage({ id: "page.loading" })) });
  }
  if (fiche.method.hypothesis !== HYPOTHESE_DU_GENRE[genre]) return h(SansFiche, { genre, avecTableau });
  // N2 (a): the dashboard answer in memory (the cache key of the application), if any; `libelleEquipe` takes the name from it, else shows the
  // opaque identifier. No request is made here.
  // A-04: a sheet in progress (draft or reviewed) links to its life cycle screen, where it is reviewed and published; a published one is frozen.
  const adresseCycle = avecCycle && fiche.state !== "published" ? adresseFiche(fiche.id) : undefined;
  return h(FicheConviction, { fiche, seuilMasquage, avecTableau, tableau, adresseCycle });
}
