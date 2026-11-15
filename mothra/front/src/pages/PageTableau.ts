// The dashboard "lead time against cycle time" (design D19, D24): the second screen's first chart, for the product or for one team at a
// time, in a neutral order, with its table and the button "make it a sheet" (design D20, D29). The reader and the sheet route are
// injected (props), never imported: slice 1 gives it simulated ones from the entry of the bundle, the real ones come with group 18, and
// the notice "simulated data" follows the flag of the source. The chart and the table read the same points.
import { useQuery } from "@tanstack/react-query";
import { createElement as h, Fragment, useId, useState } from "react";
import type { ChangeEvent, FormEvent, ReactElement } from "react";
import { useIntl } from "react-intl";
import type { GraphiqueDeFiche, PointDeFiche, ReponseLeadCycle, ReponseLeadCycleReduite } from "@mothra/contract";
import { identifiantEquipe, scopeFiche } from "@mothra/contract/equipe";
import { GRAPHIQUES_DE_FICHE } from "@mothra/contract/listes-fiche";

import { adresseConviction } from "../api/adresse.ts";
import { ecrireDerniereFiche, lireDerniereFiche } from "../api/derniereFiche.ts";
import { RefusFiche } from "../api/fiche.ts";
import type { ModificationFiche, RefusTexte } from "../api/fiche.ts";
import type { StockageIdentifiant } from "../api/identifiant.ts";
import { optionsLeadCycle } from "../api/leadCycle.ts";
import type { CreerFiche, SourceLeadCycle } from "../api/leadCycle.ts";
import { cleErreur, ErreurApi, estCodeErreur } from "../api/vue.ts";
import { ChampsFiche, champsDeValeurs, valeursVides } from "../composants/ChampsFiche.ts";
import type { ValeursChamps } from "../composants/ChampsFiche.ts";
import { BarreFiltres } from "../composants/BarreFiltres.ts";
import { ChoixDesactive } from "../composants/ChoixDesactive.ts";
import { cleEquipe, libelleEquipe, ordreEquipes } from "../composants/libelleEquipe.ts";
import { Mentions, MENTIONS_CYCLE_TIME } from "../composants/FicheMentions.ts";
import { Graphique } from "../composants/Graphique.ts";
import { SectionPanneaux } from "../composants/PanneauxProduit.ts";
import { TableauLeadCycle } from "../composants/TableauLeadCycle.ts";
import { filtrerParPlage, plageEffective, SANS_FILTRES, trimestresDisponibles } from "../api/filtres.ts";
import type { FiltresEcran } from "../api/filtres.ts";
import type { SourcePanneaux } from "../api/panneaux.ts";

// The closed list of the charts a sheet can be made of (R-20261030-58, plan 18.4 Q3): one hypothesis per sheet, chosen in the form.
// The list is the contract's (subpath `./listes-fiche`, browser-safe): no copy.
export const GRAPHIQUES_FICHE = GRAPHIQUES_DE_FICHE;
// The scope of the screen: "" is the product, anything else is a team name.
const PRODUIT = "";

export type EtatFiche =
  | { genre: "aucune" }
  | { genre: "formulaire" }
  | { genre: "equipe_requise" }
  | { genre: "brouillon"; id: string }
  // The service refused a written text: the form stays open and shows the label of the reason (never the refused value).
  | { genre: "texte_refuse"; refus: RefusTexte }
  | { genre: "erreur"; code: string };

// The last sheet of a kind kept by this browser (D11, R-20261101-125 Q258 (a)): the one read of the browser memory, beside its one write below,
// both in this page. The application hands this function to the conviction page, which calls it only when its address holds no identifier.
export function fichePrecedenteRetenue(genre: GraphiqueDeFiche, memoire?: StockageIdentifiant): string | undefined {
  return memoire === undefined ? lireDerniereFiche(genre) : lireDerniereFiche(genre, memoire);
}

// The only button opens the creation form; no draft is created before the hypothesis is chosen (R-20261030-60, Q5.1).
export function ouvrirFormulaire(): EtatFiche {
  return { genre: "formulaire" };
}

// The scope sent to the sheet route (design D29: chart, scope, data date; no verdict field): `team.<opaque identifier>`, never the team
// name. There is no product scope: the server refuses it (400), so a sheet is asked for one team only.
// `identifiant`: the opaque identifier of the series when the answer holds one (always, in the answer; the name may be absent, D35); without
// it the identifier is derived from the name.
function codePortee(equipe: string, identifiant?: string): string {
  return scopeFiche({ kind: "team", team: identifiant ?? identifiantEquipe(equipe) });
}

function cleDe(serie: { team?: string; teamId: string } | undefined): string | undefined {
  return serie === undefined ? undefined : cleEquipe(serie);
}

// The management question, the effect and the cause are optional in the draft: a request without them carries none of the three fields.
// A draft just made is remembered for its conviction (D11): the opaque identifier only, in `memoire` (the browser's by default; a test gives
// its own).
export async function ouvrirBrouillon(
  creer: CreerFiche,
  portee: string,
  dataDate: string,
  graphique: GraphiqueDeFiche,
  champs: ModificationFiche = {},
  memoire?: StockageIdentifiant,
  identifiant?: string,
): Promise<EtatFiche> {
  // A sheet states the date of its data (design D29): no date, no request.
  if (dataDate.trim() === "") return { genre: "erreur", code: "INTERNAL" };
  // No product sheet: without a team, nothing is sent.
  if (portee === PRODUIT) return { genre: "equipe_requise" };
  try {
    const brouillon = await creer({ chart: graphique, scope: codePortee(portee, identifiant), dataDate, ...champs });
    ecrireDerniereFiche(graphique, brouillon.id, memoire);
    return { genre: "brouillon", id: brouillon.id };
  } catch (echec) {
    // A refusal of the service is shown through the catalogue (the detail of a refused text, or the label of a known code). Any other
    // failure is never shown as received: an internal error code, translated by the front.
    if (echec instanceof RefusFiche) {
      if (echec.texte !== undefined) return { genre: "texte_refuse", refus: echec.texte };
      if (estCodeErreur(echec.code)) return { genre: "erreur", code: echec.code };
    }
    return { genre: "erreur", code: "INTERNAL" };
  }
}

// The teams in the order of every selector (`ordreEquipes`: the identifiers with the setting off, the names with it on): an order that depends
// on no figure, so the screen ranks no team. The keys of the screen, with the label `libelleEquipe` gives.
function equipesTriees(reponse: ReponseLeadCycle | ReponseLeadCycleReduite): Array<{ cle: string; libelle: string }> {
  return ordreEquipes(reponse.teams.map((e) => e.teamId), reponse).flatMap((identifiant) =>
    reponse.teams.filter((e) => e.teamId === identifiant).map((e) => ({ cle: cleEquipe(e), libelle: libelleEquipe(identifiant, reponse) })),
  );
}

// The first team of the list shown (R-20261104-69 Q2, author's decision): the order of every selector, `ordreEquipes` (the identifiers with the
// setting off, the alphabetical order of the names with it on), an order that depends on no figure. The one function for the bar's default,
// the address that asks for the product and the fallback of the panel.
function premiereEquipe(reponse: ReponseLeadCycle | ReponseLeadCycleReduite): { team?: string; teamId: string } | undefined {
  const premier = ordreEquipes(reponse.teams.map((e) => e.teamId), reponse).at(0);
  return reponse.teams.find((e) => e.teamId === premier);
}

function pointsDe(reponse: ReponseLeadCycle | ReponseLeadCycleReduite, portee: string): readonly PointDeFiche[] {
  return reponse.teams.find((e) => cleEquipe(e) === portee)?.points ?? reponse.product;
}

// Complement of A-05: every cell of the view (lead time, cycle time and, when the answer holds it, the items) is a masked cell for the scope
// and the period shown. The service's states are read, nothing is computed, and no team or period is chosen from the data.
export function toutEstMasque(points: readonly PointDeFiche[]): boolean {
  return points.length > 0 && points.every((p) => [p.lead, p.cycle, p.items].every((cellule) => cellule === undefined || cellule.state === "masked"));
}

interface PropsContenu {
  // The complete answer (synthetic dataset) or the reduced one (real data, D34): the points of the second carry no count.
  reponse: ReponseLeadCycle | ReponseLeadCycleReduite;
  portee: string;
  surPortee: (portee: string) => void;
  fiche: EtatFiche;
  surFaire: () => void;
  // The form's submit: the hypothesis chosen, and the optional fields written.
  surCreer: (graphique: GraphiqueDeFiche, champs: ModificationFiche) => void;
  // Whether the answer comes from a simulated source: the only condition of the "simulated data" notice.
  simulee: boolean;
  // The filter bar of the second screen (task 31.3): when given, it takes the place of the scope selector of this panel and the panel carries
  // the cycle time mention (task 37.2). Absent: the panel is the one of slice 1, unchanged.
  barre?: ReactElement;
  // The hypothesis the open draft was made for: with the draft's identifier, it gives the link to the conviction page (D6).
  genreBrouillon?: GraphiqueDeFiche;
  // The kinds whose conviction page is shipped: the link to the page is offered only for one of them (injectable, a test gives its own list).
  convictionsLivrees?: readonly GraphiqueDeFiche[];
}

// The date of the data in the language of the page; a date that does not parse is shown as received.
function dateLisible(dataDate: string, formater: (date: Date) => string): string {
  const date = new Date(dataDate);
  return Number.isNaN(date.getTime()) ? dataDate : formater(date);
}

export function ContenuTableau({
  reponse,
  portee,
  surPortee,
  fiche,
  surFaire,
  surCreer,
  simulee,
  barre,
  genreBrouillon,
  convictionsLivrees = GRAPHIQUES_DE_FICHE, // R-20261103-24 Q4 (b): the contract's list, `CONVICTIONS_LIVREES` is removed
}: PropsContenu): ReactElement {
  const intl = useIntl();
  const idTableau = useId();
  const idSeuil = useId();
  // No date of the data: the screen says so and offers no sheet (a sheet states the date of its data, design D29).
  const sansDate = reponse.dataDate.trim() === "";
  const equipes = equipesTriees(reponse);
  // With the bar (the framework) there is no product option: an unknown scope falls to the first team in the order of the identifiers.
  const premiereSerie = premiereEquipe(reponse);
  const premiere = premiereSerie === undefined ? PRODUIT : cleEquipe(premiereSerie);
  const courante = equipes.some((e) => e.cle === portee) ? portee : barre === undefined ? PRODUIT : premiere;
  const points = pointsDe(reponse, courante);
  const choisir = (evenement: ChangeEvent<HTMLSelectElement>): void => surPortee(evenement.target.value);
  return h(
    "div",
    { className: "tableau-de-bord" },
    // The notice of the simulated data is the banner of the shell now (one banner per screen, R-20261101-23).
    // The notice of D34 of the synthetic dataset is a line of the same banner (R-20261101-129, Q268 (a)): one note per screen.
    h(
      "p",
      { className: "tableau-hypothese" },
      intl.formatMessage(
        { id: "tableau.hypothesis" },
        { h5: intl.formatMessage({ id: "conviction.nav.lead_cycle_h5" }), h1: intl.formatMessage({ id: "conviction.nav.lead_cycle_h1" }) },
      ),
    ),
    sansDate
      ? h("p", { role: "alert", className: "tableau-date page-erreur" }, intl.formatMessage({ id: "tableau.dataDate.missing" }))
      : h(
          "p",
          { className: "tableau-date" },
          intl.formatMessage(
            { id: "tableau.dataDate" },
            { date: dateLisible(reponse.dataDate, (d) => intl.formatDate(d, { dateStyle: "long", timeZone: "UTC" })) },
          ),
        ),
    // Audit #629, A-10 point 13: the button is next to the chart it makes a sheet of, in the head of the block, under the date line.
    h(
      "div",
      { className: "tableau-actions" },
      h("button", { type: "button", className: "bouton", disabled: sansDate, onClick: surFaire }, intl.formatMessage({ id: "tableau.makeSheet" })),
    ),
    barre ??
      h(
        "label",
        { className: "portee" },
        intl.formatMessage({ id: "tableau.scope.label" }),
        h(
          "select",
          { value: courante, onChange: choisir },
          h("option", { value: PRODUIT }, intl.formatMessage({ id: "tableau.scope.product" })),
          equipes.map((equipe) => h("option", { key: equipe.cle, value: equipe.cle }, equipe.libelle)),
        ),
      ),
    // R-20261108-03 Q9 (a): the sentence names a team, so it shows only when the current scope is a team, never the product.
    courante !== PRODUIT && toutEstMasque(points) ? h("p", { role: "note", className: "tableau-date", "data-etat": "all-masked" }, intl.formatMessage({ id: "tableau.allMasked" })) : null,
    h(Graphique, { points, idTableau, idSeuil }),
    h(TableauLeadCycle, { points, seuil: reponse.threshold, id: idTableau, idSeuil }),
    // The cycle time starts at the entry into the ready segment: the mention is next to the times, never only on a method face (D35).
    barre === undefined ? null : h("p", { className: "tableau-date" }, h(Mentions, { codes: MENTIONS_CYCLE_TIME })),
    h(PanneauFiche, { fiche, simulee, surCreer, sansEquipe: courante === PRODUIT, reel: reponse.dataset !== "synthetic", genreBrouillon, convictionsLivrees }),
  );
}

// The labels of the two convictions, by literal key (the catalogue test finds every key used in the sources): the name of the menu, the one
// name of each conviction (R-20261109-08 Q1 (a)).
const LIBELLES_HYPOTHESE: Record<GraphiqueDeFiche, "conviction.nav.lead_cycle_h5" | "conviction.nav.lead_cycle_h1"> = {
  lead_cycle_h5: "conviction.nav.lead_cycle_h5",
  lead_cycle_h1: "conviction.nav.lead_cycle_h1",
};

// The creation form: a choice of the hypothesis, none chosen at first; the draft button stays disabled until one is chosen.
// On real data the sheet of hypothesis 5 is not offered (author's decision R-20261031-19, Q48 (a): F-H5 is not validated by the oracle). The
// code `dataset` comes from the service. Removal: with the author's decision of 12 November (R-20261031-18), with the server's refusal.
// The form still draws a kind that is served but not offered, disabled with its reason (D18, lot 3d): never hidden, never enabled.
export function graphiquesOfferts(reel: boolean): readonly GraphiqueDeFiche[] {
  return reel ? GRAPHIQUES_FICHE.filter((g) => g !== "lead_cycle_h5") : GRAPHIQUES_FICHE;
}

// The reason shown under a kind that is served and not offered (the only such kind is hypothesis 5, on real data), by literal key.
const RAISON_NON_OFFERTE = "tableau.form.h5RealUnavailable";

// The kind the form asks the service for: the one chosen, when a team is chosen and the kind is offered; otherwise nothing is asked. The
// decision of the form, so that no request is ever made for a disabled choice (D18, Q48 (a)).
export function demandeDeFiche(choix: GraphiqueDeFiche | null, sansEquipe: boolean, reel: boolean): GraphiqueDeFiche | undefined {
  if (choix === null || sansEquipe || !graphiquesOfferts(reel).includes(choix)) return undefined;
  return choix;
}

function FormulaireFiche({
  surCreer,
  sansEquipe,
  reel,
  refus,
}: {
  surCreer: (graphique: GraphiqueDeFiche, champs: ModificationFiche) => void;
  sansEquipe: boolean;
  reel: boolean;
  refus?: RefusTexte;
}): ReactElement {
  const intl = useIntl();
  const nom = useId();
  const [choix, changerChoix] = useState<GraphiqueDeFiche | null>(null);
  const [valeurs, changerValeurs] = useState<ValeursChamps>(() => valeursVides(intl.locale));
  const envoyer = (evenement: FormEvent<HTMLFormElement>): void => {
    evenement.preventDefault();
    const demande = demandeDeFiche(choix, sansEquipe, reel);
    if (demande !== undefined) surCreer(demande, champsDeValeurs(valeurs));
  };
  return h(
    "form",
    { className: "fiche-formulaire", onSubmit: envoyer },
    h(
      "fieldset",
      null,
      h("legend", null, intl.formatMessage({ id: "tableau.form.legend" })),
      GRAPHIQUES_FICHE.map((graphique) =>
        graphiquesOfferts(reel).includes(graphique)
          ? h(
              "label",
              { key: graphique, className: "portee", htmlFor: `${nom}-${graphique}` },
              h("input", { id: `${nom}-${graphique}`, type: "radio", name: nom, value: graphique, checked: choix === graphique, onChange: () => changerChoix(graphique) }),
              intl.formatMessage({ id: LIBELLES_HYPOTHESE[graphique] }),
            )
          : h(ChoixDesactive, { key: graphique, nom, valeur: graphique, libelle: LIBELLES_HYPOTHESE[graphique], raison: RAISON_NON_OFFERTE }),
      ),
    ),
    h(ChampsFiche, { valeurs, surChangement: changerValeurs, refus }),
    sansEquipe ? h("p", { className: "tableau-date" }, intl.formatMessage({ id: "tableau.form.teamRequired" })) : null,
    h("button", { type: "submit", className: "bouton", disabled: choix === null || sansEquipe }, intl.formatMessage({ id: "tableau.form.create" })),
  );
}

function PanneauFiche({
  fiche,
  simulee,
  surCreer,
  sansEquipe,
  reel,
  genreBrouillon,
  convictionsLivrees,
}: {
  fiche: EtatFiche;
  simulee: boolean;
  surCreer: (graphique: GraphiqueDeFiche, champs: ModificationFiche) => void;
  sansEquipe: boolean;
  reel: boolean;
  genreBrouillon?: GraphiqueDeFiche;
  convictionsLivrees: readonly GraphiqueDeFiche[];
}): ReactElement | null {
  const intl = useIntl();
  if (fiche.genre === "aucune") return null;
  if (fiche.genre === "formulaire") return h(FormulaireFiche, { surCreer, sansEquipe, reel });
  if (fiche.genre === "texte_refuse") return h(FormulaireFiche, { surCreer, sansEquipe, reel, refus: fiche.refus });
  if (fiche.genre === "equipe_requise") {
    return h("p", { role: "alert", className: "page-erreur" }, intl.formatMessage({ id: "tableau.form.teamRequired" }));
  }
  if (fiche.genre === "erreur") {
    return h("p", { role: "alert", className: "page-erreur" }, intl.formatMessage({ id: cleErreur(fiche.code) }));
  }
  return h(
    "div",
    { role: "status", className: "fiche-brouillon" },
    h("p", null, intl.formatMessage({ id: "tableau.draft.opened" })),
    h("p", { className: "fiche-etat" }, intl.formatMessage({ id: "tableau.state.draft" })),
    simulee ? h("p", { className: "donnees-simulees" }, intl.formatMessage({ id: "tableau.draft.simulated" })) : null,
    // The link to the conviction page of the new draft (D6): one line, the kind it was made for and its opaque identifier. Offered only for a
    // kind whose page is shipped (none in lot 3a): a link to a page that does not exist would give the home.
    genreBrouillon === undefined || !convictionsLivrees.includes(genreBrouillon) ? null : h("a", { className: "lien", href: adresseConviction(genreBrouillon, fiche.id) }, intl.formatMessage({ id: "conviction.open" })),
  );
}

// The identifier of the team the framework shows: the one of the address when the answer holds it, else the first team. Without any team: none.
function choisirEquipeEffective(reponse: ReponseLeadCycle | ReponseLeadCycleReduite | undefined, demandee: string | undefined): string | undefined {
  if (reponse === undefined) return undefined;
  return demandee !== undefined && reponse.teams.some((e) => e.teamId === demandee) ? demandee : premiereEquipe(reponse)?.teamId;
}

interface PropsPage {
  source: SourceLeadCycle;
  // The second screen's framework (tasks 31.3 and 37.2): the source of the panels, and the filters of the address with the way to change them.
  // Without `panneaux` the page is the one of slice 1 (its own scope selector, no panel).
  panneaux?: SourcePanneaux;
  filtres?: FiltresEcran;
  surFiltres?: (filtres: FiltresEcran) => void;
  // The kinds whose conviction page is shipped (the shell's list); by default the closed list of `convictions.ts`.
  convictionsLivrees?: readonly GraphiqueDeFiche[];
}

export function PageTableau({ source, panneaux, filtres = SANS_FILTRES, surFiltres, convictionsLivrees }: PropsPage): ReactElement {
  const intl = useIntl();
  const { creer, simulee } = source;
  const requete = useQuery(optionsLeadCycle(source.lire));
  const [portee, changerPortee] = useState(PRODUIT);
  const [fiche, changerFiche] = useState<EtatFiche>({ genre: "aucune" });
  const [genreBrouillon, changerGenreBrouillon] = useState<GraphiqueDeFiche | undefined>(undefined);
  const dataDate = requete.data?.dataDate ?? "";
  // Inside the framework there is no product option (R-20261031-61, Q110 a): the screen opens on the first team in the neutral order of the
  // opaque identifier, and an address that asks for the product (or for an unknown identifier) falls back to it. The sheet is made for it.
  const equipeEffective = panneaux === undefined ? filtres.team : choisirEquipeEffective(requete.data, filtres.team);
  const porteeUtilisee = panneaux === undefined ? portee : (cleDe(requete.data?.teams.find((e) => e.teamId === equipeEffective)) ?? PRODUIT);
  const faire = (): void => changerFiche(ouvrirFormulaire());
  const creerBrouillon = (graphique: GraphiqueDeFiche, champs: ModificationFiche): void => {
    // A draft just made is remembered for its conviction by `ouvrirBrouillon` (D11): the identifier only.
    const identifiant = requete.data?.teams.find((e) => cleEquipe(e) === porteeUtilisee)?.teamId;
    void ouvrirBrouillon(creer, porteeUtilisee, dataDate, graphique, champs, undefined, identifiant).then((etat) => {
      changerGenreBrouillon(graphique);
      changerFiche(etat);
    });
  };
  const choisirPortee = (nouvelle: string): void => {
    changerPortee(nouvelle);
    changerFiche({ genre: "aucune" });
  };
  const changerFiltres = (nouveaux: FiltresEcran): void => {
    changerFiche({ genre: "aucune" });
    surFiltres?.(nouveaux);
  };
  let corps: ReactElement;
  if (requete.isError) {
    // The code of the service's refusal, shown through its catalogue key; any other failure is the internal error.
    const code = requete.error instanceof ErreurApi ? requete.error.code : "INTERNAL";
    corps = h("p", { role: "alert", className: "page-erreur" }, intl.formatMessage({ id: cleErreur(code) }));
  } else if (requete.data === undefined) {
    corps = h("p", { role: "status" }, intl.formatMessage({ id: "page.loading" }));
  } else if (panneaux === undefined) {
    corps = h(ContenuTableau, {
      reponse: requete.data,
      portee,
      surPortee: choisirPortee,
      fiche,
      surFaire: faire,
      surCreer: creerBrouillon,
      simulee,
      genreBrouillon,
      convictionsLivrees,
    });
  } else {
    // The bar offers the quarters of the answer; a bound left out is the oldest or the newest of them. Nothing is deduced from a clock.
    const disponibles = trimestresDisponibles(requete.data);
    const plage = plageEffective(filtres.from, filtres.to, disponibles);
    const effectifs: FiltresEcran = { team: equipeEffective, from: plage.from, to: plage.to };
    const barre = h(BarreFiltres, { equipes: requete.data.teams.map((e) => e.teamId), trimestres: disponibles, filtres: effectifs, surFiltres: changerFiltres, tableau: requete.data });
    corps = h(
      Fragment,
      null,
      h(ContenuTableau, {
        reponse: filtrerParPlage(requete.data, effectifs.from, effectifs.to),
        portee: porteeUtilisee,
        surPortee: choisirPortee,
        fiche,
        surFaire: faire,
        surCreer: creerBrouillon,
        simulee,
        barre,
        genreBrouillon,
        convictionsLivrees,
      }),
      // No quarter offered (no team in the answer): no panel, so no request without bounds (A-83).
      plage.from === undefined || plage.to === undefined ? null : h(SectionPanneaux, { lire: panneaux.lire, filtres: effectifs }),
    );
  }
  return h(
    "section",
    { className: "page", "aria-labelledby": "page-titre" },
    h("h1", { id: "page-titre" }, intl.formatMessage({ id: "tableau.title" })),
    corps,
  );
}
