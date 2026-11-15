// Entry of the front bundle: the query client, the application, the stylesheets. No address is written here. This is the only file
// that imports src/simule/: the dashboard reads the real routes when the server is present (task 19.7), and the simulated answers
// serve in development only (`import.meta.env.DEV`); in production a missing server shows an error and a retry.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement as h, StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { IntlProvider } from "react-intl";

import { Application } from "./Application.ts";
import { choisirSource, lireFicheHttp, sourceCycleFicheHttp, sourcePanneauxHttp } from "./api/http.ts";
import { ecrireIdentifiant, lireIdentifiant } from "./api/identifiant.ts";
import { catalogues, LANGUE_PAR_DEFAUT } from "./i18n/langue.ts";
import { PageDemarrage } from "./pages/PageDemarrage.ts";
import { SOURCE_SIMULEE } from "./simule/leadCycle.ts";
import { SOURCE_PANNEAUX_SIMULEE } from "./simule/panneaux.ts";
// Fonts (design D10): IBM Plex Sans (texts) and IBM Plex Serif (statement), licence OFL-1.1, served from the bundle by the local Fontsource
// packages, latin subset; nothing is loaded from another host at run time. The system stack of the font tokens is the fallback.
import "@fontsource/ibm-plex-sans/latin-400.css";
import "@fontsource/ibm-plex-sans/latin-500.css";
import "@fontsource/ibm-plex-sans/latin-600.css";
import "@fontsource/ibm-plex-sans/latin-700.css";
import "@fontsource/ibm-plex-serif/latin-500.css";
import "@fontsource/ibm-plex-serif/latin-600.css";
import "./styles/tokens.css";
import "./styles/styles.css";

const racine = document.getElementById("racine");
if (racine !== null) {
  const client = new QueryClient();
  const identifiant = { lire: () => lireIdentifiant(), ecrire: (valeur: string) => ecrireIdentifiant(valeur) };
  // The loading state, then the application (or the failure and its retry), in the default language until the application takes over.
  const demarrage = h(PageDemarrage, {
    sonder: () => choisirSource(SOURCE_SIMULEE, () => lireIdentifiant(), import.meta.env.DEV),
    // The panels follow the source of the dashboard: simulated with it, read from the routes of the panels otherwise. The conviction page reads
    // its sheet through the existing route of the sheet, injected as the dashboard source is; the simulated source has no sheet to read.
    application: (source) =>
      h(
        QueryClientProvider,
        { client },
        h(Application, {
          tableau: source,
          lireFiche: source.simulee ? undefined : (id: string) => lireFicheHttp(id),
          // The life cycle of the sheets (review and publication) has no simulated source: the screens are offered with the real server only (A-04).
          cycle: source.simulee ? undefined : sourceCycleFicheHttp(() => lireIdentifiant()),
          panneaux: source.simulee ? SOURCE_PANNEAUX_SIMULEE : sourcePanneauxHttp(),
          identifiant,
        }),
      ),
  });
  createRoot(racine).render(h(StrictMode, null, h(IntlProvider, { locale: LANGUE_PAR_DEFAUT, messages: catalogues[LANGUE_PAR_DEFAUT] }, demarrage)));
}
