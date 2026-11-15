// Reproductions de l'audit #629 (chasse Kraken), lot L5 : elles reproduisent H-07 à H-12 et passent au vert avec le correctif du groupe F2.
// Rendu serveur sans navigateur, comme tableau.test.ts et rendu.ts ; les requêtes sont préremplies dans le cache. Valeurs fictives seulement.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement as h, isValidElement } from "react";
import type { ReactElement } from "react";

import { identifiantEquipe } from "@mothra/contract/equipe";
import type { ReponseLeadCycle } from "@mothra/contract";

import { optionsFiche } from "../src/api/ficheLecture.ts";
import type { LecteurFiche } from "../src/api/ficheLecture.ts";
import type { FiltresEcran } from "../src/api/filtres.ts";
import { optionsLeadCycle } from "../src/api/leadCycle.ts";
import type { SourceLeadCycle } from "../src/api/leadCycle.ts";
import type { SourcePanneaux } from "../src/api/panneaux.ts";
import { ErreurApi } from "../src/api/vue.ts";
import { BarreFiltres } from "../src/composants/BarreFiltres.ts";
import { catalogues } from "../src/i18n/langue.ts";
import { PageConviction } from "../src/pages/PageConviction.ts";
import { PageTableau } from "../src/pages/PageTableau.ts";
import { rendre } from "./rendu.ts";

const valeur = (n: number) => ({ state: "value" as const, value: n });
const point = (trimestre: string) => ({ quarter: trimestre, lead: valeur(20), cycle: valeur(8), items: valeur(30) });

const REPONSE: ReponseLeadCycle = {
  threshold: 5,
  dataDate: "2026-10-27",
  dataset: "synthetic",
  product: [],
  teams: [{ team: "team-a", teamId: identifiantEquipe("team-a"), points: [point("2026-Q1"), point("2026-Q2")] }],
};

const SANS_FILTRES: FiltresEcran = { team: undefined, from: undefined, to: undefined };

function page(filtres: FiltresEcran, reponse: ReponseLeadCycle = REPONSE): string {
  const client = new QueryClient();
  const source: SourceLeadCycle = { lire: async () => reponse, creer: async () => ({ id: "x-1", state: "draft" }), simulee: false };
  client.setQueryData(optionsLeadCycle(source.lire).queryKey, reponse);
  const panneaux: SourcePanneaux = {
    lire: async () => {
      throw new Error("jamais appelé par un rendu serveur");
    },
    simulee: false,
  };
  return rendre(h(QueryClientProvider, { client }, h(PageTableau, { source, panneaux, filtres })), "en");
}

// ---- H-07 : une adresse dont le trimestre n'est pas dans la barre ------------------------------------------------------------------------

test("H-07 : un trimestre de l'adresse absent de la barre est ramené à un trimestre offert", () => {
  // audit-kraken/lots/L5.md, H-07 : la valeur est gardée telle quelle, les panneaux répondent ensuite 422
  const selecteur = (html: string): string => /<select name="from"[^>]*>([\s\S]*?)<\/select>/.exec(html)?.[1] ?? "";
  const nombreChoisi = (html: string): number => (selecteur(html).match(/selected=""/g) ?? []).length;
  assert.equal(nombreChoisi(page(SANS_FILTRES)), 1, "précondition : sans adresse, un trimestre est choisi");
  assert.equal(nombreChoisi(page({ ...SANS_FILTRES, from: "2020-Q1" })), 1, "un trimestre hors de la barre ne laisse aucun choix");
});

// ---- H-08 : une plage inversée acceptée par la barre ------------------------------------------------------------------------------

interface Gestionnaire {
  onChange: (evenement: unknown) => void;
}

function chercherSelect(noeud: unknown, nom: string): Gestionnaire | undefined {
  if (Array.isArray(noeud)) {
    for (const enfant of noeud) {
      const trouve = chercherSelect(enfant, nom);
      if (trouve !== undefined) return trouve;
    }
    return undefined;
  }
  if (!isValidElement(noeud)) return undefined;
  const props = noeud.props as { name?: string; onChange?: (evenement: unknown) => void; children?: unknown };
  if (noeud.type === "select" && props.name === nom && props.onChange !== undefined) return { onChange: props.onChange };
  return chercherSelect(props.children, nom);
}

test("H-08 : la barre ne produit pas une plage inversée (début après la fin)", () => {
  // audit-kraken/lots/L5.md, H-08 : choisir un début après la fin appelle surFiltres avec une plage que les panneaux refusent (422)
  const appels: FiltresEcran[] = [];
  let arbre: unknown = null;
  const proprietes = {
    equipes: [identifiantEquipe("team-a")],
    trimestres: ["2026-Q1", "2026-Q2", "2026-Q3"],
    filtres: { team: undefined, from: "2026-Q1", to: "2026-Q2" } as FiltresEcran,
    surFiltres: (f: FiltresEcran): void => {
      appels.push(f);
    },
  };
  // Le composant est appelé dans le rendu d'un composant pour que ses hooks aient leur contexte ; on garde l'arbre qu'il rend.
  const Espion = (): ReactElement => {
    arbre = BarreFiltres(proprietes);
    return h("div");
  };
  rendre(h(Espion), "en");
  const debut = chercherSelect(arbre, "from");
  assert.ok(debut !== undefined, "le sélecteur du début est dans l'arbre");
  debut.onChange({ target: { value: "2026-Q3" } });
  for (const f of appels) {
    assert.ok(f.from === undefined || f.to === undefined || f.from <= f.to, `plage inversée : ${String(f.from)} > ${String(f.to)}`);
  }
});

// ---- H-09 : aucune équipe, donc aucun trimestre offert -----------------------------------------------------------------------------

test("H-09 : sans équipe ni trimestre dans la réponse, aucun panneau n'est monté (donc aucune requête sans bornes)", () => {
  // audit-kraken/lots/L5.md, H-09 : from et to sont omis (api/http.ts), le serveur répond 400 et la page affiche une erreur interne
  const html = page(SANS_FILTRES, { ...REPONSE, teams: [], product: [] });
  assert.ok(!html.includes("data-panel="), "aucun panneau sans trimestre à demander");
});

// ---- H-10 : import dynamique sans catch ------------------------------------------------------------------------------------------

test("H-10 : l'import dynamique d'ECharts a un traitement de rejet (test statique : le rejet n'est pas atteignable sans navigateur)", () => {
  // audit-kraken/lots/L5.md, H-10 : void import(...).then(...) sans catch, rejet non géré et zone vide
  const source = readFileSync(new URL("../src/composants/Graphique.ts", import.meta.url), "utf8");
  assert.ok(source.includes('import("./echarts.ts")'), "précondition : l'import dynamique est dans le fichier");
  assert.match(source, /\.catch\s*\(|\bcatch\s*[({]/);
});

// ---- H-12 : une conviction sur une fiche disparue --------------------------------------------------------------------------------

test("H-12 : une fiche disparue (UNKNOWN_SHEET) donne l'état vide, pas une alerte d'erreur", () => {
  // audit-kraken/lots/L5.md, H-12 : PageConviction affiche l'erreur du service au lieu de l'état vide expliqué
  const client = new QueryClient();
  const erreur = new ErreurApi("UNKNOWN_SHEET");
  const lire: LecteurFiche = async () => {
    throw erreur;
  };
  // Le cache contient déjà la réponse d'erreur de cette fiche : le rendu serveur la lit sans rien demander.
  client.getQueryCache().build(
    client,
    optionsFiche(lire, "x-42") as never,
    {
      data: undefined,
      dataUpdateCount: 0,
      dataUpdatedAt: 0,
      error: erreur,
      errorUpdateCount: 1,
      errorUpdatedAt: Date.now(),
      fetchFailureCount: 1,
      fetchFailureReason: erreur,
      fetchMeta: null,
      isInvalidated: false,
      status: "error",
      fetchStatus: "idle",
    } as never,
  );
  const html = rendre(h(QueryClientProvider, { client }, h(PageConviction, { conviction: { genre: "lead_cycle_h1", id: "x-42" }, lire })), "en");
  assert.ok(!html.includes(catalogues.en["page.loading"]), "précondition : l'état du cache a été lu, la page n'est pas restée en chargement");
  assert.ok(!html.includes('role="alert"'), "pas d'alerte pour une fiche qui n'existe plus");
});
