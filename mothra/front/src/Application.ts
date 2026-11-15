// The application shell: the language (English by default, changeable by the user), the side navigation, the one information banner of the
// screen, the screen. The QueryClient is provided by the caller. The shell is drawn by the shell template (D1, D17): the side navigation with
// the served convictions, the identifier field and the language selector at its bottom, one banner per screen whose text follows the dataset
// code of the dashboard answer (one cache key, no second request).
import { useQuery } from "@tanstack/react-query";
import { createElement as h, Fragment, useEffect, useState } from "react";
import type { ChangeEvent, ReactElement } from "react";
import { IntlProvider, useIntl } from "react-intl";

import { ADRESSE_FICHES, convictionDuHash, ficheDuHash } from "./api/adresse.ts";
import type { AdresseConviction } from "./api/adresse.ts";
import type { SourceCycleFiche } from "./api/cycleFiche.ts";
import { ADRESSE_TABLEAU, ecrireFiltresAdresse, lireFiltresAdresse, SANS_FILTRES } from "./api/filtres.ts";
import type { FiltresEcran } from "./api/filtres.ts";
import type { IssueEnregistrement } from "./api/identifiant.ts";
import { optionsFiche } from "./api/ficheLecture.ts";
import type { LecteurFiche } from "./api/ficheLecture.ts";
import { optionsLeadCycle } from "./api/leadCycle.ts";
import type { SourceLeadCycle } from "./api/leadCycle.ts";
import type { SourcePanneaux } from "./api/panneaux.ts";
import { ErreurApi } from "./api/vue.ts";
import type { GraphiqueDeFiche } from "@mothra/contract/listes-fiche";
import type { JeuDeDonnees } from "./composants/Banniere.ts";
import { ChampIdentifiant } from "./composants/ChampIdentifiant.ts";
import { NavigationLaterale } from "./composants/NavigationLaterale.ts";
import { GRAPHIQUES_DE_FICHE } from "@mothra/contract/listes-fiche";
import { Coquille } from "./gabarits/Coquille.ts";
import { catalogues, CLES_LANGUE, estLangue, LANGUE_PAR_DEFAUT, LANGUES } from "./i18n/langue.ts";
import type { Langue } from "./i18n/langue.ts";
import { MARQUE } from "./marque.ts";
import { PageConviction } from "./pages/PageConviction.ts";
import { PageFiche } from "./pages/PageFiche.ts";
import { PageFiches } from "./pages/PageFiches.ts";
import { PageSquelette } from "./pages/PageSquelette.ts";
import { fichePrecedenteRetenue, graphiquesOfferts, PageTableau } from "./pages/PageTableau.ts";

// The screens: the home (named `squelette`), the dashboard, the conviction page, and the two screens of the life cycle of the sheets (A-04 of
// the audit #629): the list of the sheets in progress (`fiches`) and one sheet to review or publish (`fiche`). The address fragment chooses one;
// the home chain of group 19.4 will replace the first.
export type Ecran = "squelette" | "tableau" | "conviction" | "fiches" | "fiche";

// The address may carry the filters of the second screen after a question mark (`#/tableau?team=…&from=…&to=…`, task 31.3): the screen is
// chosen from what comes before it. `#/conviction/<kind>` and `#/conviction/<kind>/<id>` give the conviction screen (D2); a kind outside the
// contract's list, or an identifier that is not an opaque one, gives the home. `#/fiches` and `#/fiche/<id>` give the life cycle screens.
export function ecranDuHash(hash: string): Ecran {
  const debut = hash.indexOf("?");
  const chemin = debut < 0 ? hash : hash.slice(0, debut);
  if (chemin === ADRESSE_TABLEAU) return "tableau";
  if (chemin === ADRESSE_FICHES) return "fiches";
  if (ficheDuHash(hash) !== undefined) return "fiche";
  return convictionDuHash(hash) === undefined ? "squelette" : "conviction";
}

// The identity of the screen an address shows (A-15): the screen, and for a conviction page its kind and its sheet. The filters of the
// dashboard are not part of it: changing a filter stays on the same screen.
export function cleEcran(hash: string): string {
  const conviction = convictionDuHash(hash);
  return conviction === undefined ? ecranDuHash(hash) : ["conviction", conviction.genre, conviction.id ?? ""].join("/");
}

// A change of screen puts the page back at the top, instead of keeping the scroll position of the screen left (A-15). A change of filters
// on the same screen does not. Pure: the scroll is the caller's function; returns whether it was called.
export function remonterSiEcranChange(avant: string, apres: string, defiler: () => void): boolean {
  if (cleEcran(avant) === cleEcran(apres)) return false;
  defiler();
  return true;
}

function ecranCourant(): Ecran {
  return typeof window === "undefined" ? "squelette" : ecranDuHash(window.location.hash);
}

function convictionCourante(): AdresseConviction | undefined {
  return typeof window === "undefined" ? undefined : convictionDuHash(window.location.hash);
}

function ficheCourante(): string | undefined {
  return typeof window === "undefined" ? undefined : ficheDuHash(window.location.hash);
}

function filtresCourants(): FiltresEcran {
  return typeof window === "undefined" ? SANS_FILTRES : lireFiltresAdresse(window.location.hash);
}

// The caller's identifier: read and saved by the entry of the bundle (browser storage); without it the side column shows no field.
export interface IdentifiantInjecte {
  lire: () => string | undefined;
  ecrire: (valeur: string) => IssueEnregistrement;
}

// The kinds served on a dataset (D2, D17): the contract's list filtered by the dataset (`graphiquesOfferts`: hypothesis 5 is absent on real
// data), then by a list a test may give (by default the contract's list: `CONVICTIONS_LIVREES` is removed, R-20261103-24 Q4 (b), D1 and
// task 7.1). Pure; the contract's order is kept, one entry per kind.
export function convictionsServies(reel: boolean, livrees: readonly GraphiqueDeFiche[] = GRAPHIQUES_DE_FICHE): readonly GraphiqueDeFiche[] {
  return graphiquesOfferts(reel).filter((g) => livrees.includes(g));
}

// The banner follows the dataset code of the answer: only `synthetic` and `real` give one. An answer that carries no code, or a code the
// front does not know, shows no banner (never the banner of the other code).
export function jeuDeDonnees(code: string | undefined): JeuDeDonnees | undefined {
  return code === "synthetic" || code === "real" ? code : undefined;
}

// A query that is never enabled has a reader that fails (the hooks are called whatever the props).
const SANS_TABLEAU = (): Promise<never> => Promise.reject(new ErreurApi("INTERNAL"));
const SANS_FICHE = (): Promise<never> => Promise.reject(new ErreurApi("INTERNAL"));

interface PropsCorps {
  identifiant?: IdentifiantInjecte;
  langue: Langue;
  changer: (langue: Langue) => void;
  ecran: Ecran;
  conviction?: AdresseConviction;
  tableau?: SourceLeadCycle;
  lireFiche?: LecteurFiche;
  panneaux?: SourcePanneaux;
  filtres: FiltresEcran;
  surFiltres: (filtres: FiltresEcran) => void;
  livrees: readonly GraphiqueDeFiche[];
  // The life cycle of the sheets: its source, and the sheet the screen `fiche` is on.
  cycle?: SourceCycleFiche;
  fiche?: string;
}

function Corps({ langue, changer, ecran, conviction, tableau, lireFiche, panneaux, filtres, surFiltres, identifiant, livrees, cycle, fiche }: PropsCorps): ReactElement {
  const intl = useIntl();
  const titre = intl.formatMessage({ id: MARQUE.nom });
  useEffect(() => {
    document.documentElement.lang = langue;
    document.title = titre;
  }, [langue, titre]);
  const choisir = (evenement: ChangeEvent<HTMLSelectElement>): void => {
    if (estLangue(evenement.target.value)) changer(evenement.target.value);
  };
  // The dashboard answer gives the dataset code and the served convictions (one cache key, no second request).
  const requeteTableau = useQuery({ ...optionsLeadCycle(tableau?.lire ?? SANS_TABLEAU), enabled: tableau !== undefined });
  const donnees = requeteTableau.data;
  // The kinds served: the contract's list, filtered by the dataset (graphiquesOfferts) and by the closed list of the kinds whose page is shipped.
  const servies = donnees === undefined ? [] : convictionsServies(donnees.dataset !== "synthetic", livrees);
  // A kind that is not served on this dataset gives the home (D2); until the dashboard answer is known the kind of the address is kept.
  const servi = conviction !== undefined && (donnees === undefined ? livrees.includes(conviction.genre) : servies.includes(conviction.genre));
  const voulu = ecran === "conviction" && !servi ? "squelette" : ecran;
  // The dashboard is shown only when its source is given; otherwise the home is.
  // The life cycle screens (A-04) are shown only when their source is given (and the screen of a sheet only with a sheet to open); otherwise the home is.
  const demande = voulu === "tableau" && tableau === undefined ? "squelette" : voulu;
  const sansSourceDuCycle = (demande === "fiches" || demande === "fiche") && cycle === undefined;
  const sansFiche = demande === "fiche" && fiche === undefined;
  const sur: Ecran = sansSourceDuCycle || sansFiche ? "squelette" : demande;
  // On the conviction screen, and on the screen of a sheet, the banner follows the dataset code of the sheet answer once it is known (D1): the page
  // reads the same cache entry (one key per sheet, no second request); until then, or without a sheet to read, the code of the dashboard answer.
  const idFiche = sur === "conviction" ? conviction?.id : sur === "fiche" ? fiche : undefined;
  const requeteFiche = useQuery({ ...optionsFiche(lireFiche ?? SANS_FICHE, idFiche ?? ""), enabled: lireFiche !== undefined && idFiche !== undefined });
  const jeu = jeuDeDonnees(requeteFiche.data?.dataset ?? donnees?.dataset);
  const bas = h(
    Fragment,
    null,
    h(
      "label",
      { className: "langue" },
      intl.formatMessage({ id: "language.label" }),
      h(
        "select",
        { value: langue, onChange: choisir },
        LANGUES.map((code) => h("option", { key: code, value: code }, intl.formatMessage({ id: CLES_LANGUE[code] }))),
      ),
    ),
    identifiant === undefined ? null : h(ChampIdentifiant, { lire: identifiant.lire, ecrire: identifiant.ecrire }),
  );
  const navigation = h(NavigationLaterale, {
    accueilCourant: sur === "squelette",
    convictions: servies.map((genre) => ({ genre, courante: sur === "conviction" && conviction?.genre === genre })),
    tableau: tableau === undefined ? undefined : { courant: sur === "tableau" },
    fiches: cycle === undefined ? undefined : { courant: sur === "fiches" || sur === "fiche" },
    bas,
  });
  let page: ReactElement;
  if (sur === "tableau" && tableau !== undefined) {
    page = h(PageTableau, { source: tableau, panneaux, filtres, surFiltres, convictionsLivrees: livrees });
  } else if (sur === "conviction" && conviction !== undefined) {
    // The kind is served here (`servi`): the page of the sheet. A kind that is not served has already given the home (D2).
    page = h(PageConviction, {
      conviction,
      lire: lireFiche,
      fichePrecedente: fichePrecedenteRetenue,
      seuilMasquage: donnees?.threshold,
      avecTableau: tableau !== undefined,
      avecCycle: cycle !== undefined,
    });
  } else if (sur === "fiches" && cycle !== undefined) {
    page = h(PageFiches, { cycle });
  } else if (sur === "fiche" && cycle !== undefined && fiche !== undefined) {
    page = h(PageFiche, { id: fiche, lire: lireFiche, cycle });
  } else {
    page = h(PageSquelette, { convictions: servies });
  }
  return h(Coquille, { navigation, jeu }, page);
}

interface PropsApplication {
  langueInitiale?: Langue;
  ecranInitial?: Ecran;
  // The conviction screen an initial screen `conviction` opens on (a test fixes it); by default the address's.
  convictionInitiale?: AdresseConviction;
  // The source of the dashboard, injected by the entry of the bundle; without it the second screen is not offered.
  tableau?: SourceLeadCycle;
  // The reader of one sheet, injected by the entry of the bundle as the dashboard source is; without it the conviction page opens no sheet.
  lireFiche?: LecteurFiche;
  // The source of the panels of the second screen (task 37.2), injected by the entry of the bundle; without it the screen has no filter bar
  // and no panel.
  panneaux?: SourcePanneaux;
  // The filters the screen starts with (a test fixes them); by default the address's.
  filtresInitiaux?: FiltresEcran;
  identifiant?: IdentifiantInjecte;
  // The kinds served before the dataset filter (D1, R-20261103-24 Q4 (b)): by default the contract's list; a test gives its own list to
  // exercise the filters (dataset, one card per kind, link of the draft panel).
  convictionsLivrees?: readonly GraphiqueDeFiche[];
  // The source of the life cycle of the sheets (A-04), injected by the entry of the bundle; without it the list, the screen of a sheet and the
  // navigation entry are not offered.
  cycle?: SourceCycleFiche;
  // The sheet an initial screen `fiche` opens on (a test fixes it); by default the address's.
  ficheInitiale?: string;
}

export function Application({
  langueInitiale = LANGUE_PAR_DEFAUT,
  ecranInitial,
  convictionInitiale,
  tableau,
  lireFiche,
  panneaux,
  filtresInitiaux,
  identifiant,
  convictionsLivrees = GRAPHIQUES_DE_FICHE,
  cycle,
  ficheInitiale,
}: PropsApplication): ReactElement {
  const [langue, changer] = useState<Langue>(langueInitiale);
  const [ecran, changerEcran] = useState<Ecran>(ecranInitial ?? ecranCourant());
  const [conviction, changerConviction] = useState<AdresseConviction | undefined>(convictionInitiale ?? convictionCourante());
  const [fiche, changerFiche] = useState<string | undefined>(ficheInitiale ?? ficheCourante());
  const [filtres, changerFiltres] = useState<FiltresEcran>(filtresInitiaux ?? filtresCourants());
  useEffect(() => {
    let precedent = window.location.hash;
    const suivre = (): void => {
      remonterSiEcranChange(precedent, window.location.hash, () => window.scrollTo(0, 0));
      precedent = window.location.hash;
      changerEcran(ecranCourant());
      changerConviction(convictionCourante());
      changerFiche(ficheCourante());
      changerFiltres(filtresCourants());
    };
    window.addEventListener("hashchange", suivre);
    return () => window.removeEventListener("hashchange", suivre);
  }, []);
  // The filters are kept in the address: writing them there is what changes them (the listener above reads them back).
  const surFiltres = (nouveaux: FiltresEcran): void => {
    changerFiltres(nouveaux);
    window.location.hash = ecrireFiltresAdresse(nouveaux);
  };
  return h(
    IntlProvider,
    { locale: langue, messages: catalogues[langue] },
    h(Corps, { langue, changer, ecran, conviction, tableau, lireFiche, panneaux, filtres, surFiltres, identifiant, livrees: convictionsLivrees, cycle, fiche }),
  );
}
