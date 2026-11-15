// The four panels of the product-scope dashboard for real (mothra-slices D35, task 37.1, routes part): the implementation of the port
// `calculerPanneau` of the panel routes. It reads the view of the panel through the one masked path of the service (`lireVueMasquee`:
// `masquerVue` over the whole view, never `cellule()` over raw rows), keeps ONE row per quarter and group for the scope served, turns the
// rows into the neutral inputs of the contract and hands them to the panel functions of the contract, which alone compute a total or a share.
// Nothing is computed here. The reduction on real data is NOT done here: it is `servirPanneau` of the service layer, called by the route.
// Rows kept (review of 37.1 contract, section "L'adaptateur"): a team scope keeps the rows whose team gives the requested identifier; the
// product keeps the row `(produit)` only, never the row without a team, never a sum of teams. `defects-inout` and `correction-share`
// always read the product row (defects carry no team yet, D33).
import { celluleDe, etiquetteTrimestre } from "@mothra/contract";
import type {
  CodeJeuDeDonnees,
  Contrat,
  EntreeBloque,
  EntreeFlux,
  CodePanneau,
  PanneauComplet,
  Portee,
  ResultatFiltres,
  ReponseVue,
  Vue,
} from "@mothra/contract";
import { PorteeProduitRefusee, panneauBlockedShare, panneauCorrectionShare, panneauDefectsInout, panneauStoriesInout } from "@mothra/contract";
import { LIBELLE_PRODUIT, LIBELLE_SANS_EQUIPE } from "@mothra/contract/equipe";

import type { AccesVues } from "../db/acces.ts";
import { lireVueMasquee } from "../service.ts";
import { verifierFenetre } from "./fenetre.ts";

export const VUE_FLUX = "v_team_flow_inout";
export const VUE_BLOQUE = "v_team_blocked_share";
// The label of the product row of `v_team_flow_inout` (task 36.1); source: the contract (equipe.ts), not a copy.
export const LIGNE_PRODUIT = LIBELLE_PRODUIT;
// The label of the row of items without a team (SANS_EQUIPE of tools/flow_views.py): never served, whatever the scope, even for a scope forged
// from this very label; source: the contract (equipe.ts), not a copy.
export const LIGNE_SANS_EQUIPE = LIBELLE_SANS_EQUIPE;
// A team scope whose identifier is given by two different names in the rows read: a collision that appeared after the start check (A-68).
// The request is refused, never served as a mix of two teams nor as a 500; the error carries no name and no identifier.
// Replaces: nothing. Removal condition: falls with the start check (fiches/equipes.ts), when the identifier comes from a column of the view.
export class CollisionDIdentifiantsEquipe extends Error {}

export interface DependancesPanneaux {
  acces: AccesVues;
  contrat: Contrat;
  seuil: number; // the effective threshold of the views
  identifiantEquipe: (nom: string) => string;
}

type FiltresValides = Extract<ResultatFiltres, { ok: true }>;

function vueDuContrat(contrat: Contrat, nom: string): Vue {
  const vue = contrat.views.find((v) => v.name === nom);
  if (vue === undefined) {
    throw new Error(`vue absente du contrat : ${nom}`);
  }
  return vue;
}

function texte(valeur: unknown, colonne: string): string {
  if (typeof valeur !== "string") {
    throw new TypeError(`texte attendu dans la colonne ${colonne}`);
  }
  return valeur;
}

// Whether a row belongs to the scope served: the team column of a plain value (a row without a team is never kept).
function retenue(equipe: unknown, portee: Portee, identifiantEquipe: (nom: string) => string): boolean {
  if (typeof equipe !== "string" || equipe === LIGNE_SANS_EQUIPE) return false;
  if (portee.kind === "product") return equipe === LIGNE_PRODUIT;
  return equipe !== LIGNE_PRODUIT && identifiantEquipe(equipe) === portee.team;
}

function lignesDeFlux(reponse: ReponseVue, portee: Portee, identifiantEquipe: (nom: string) => string): EntreeFlux[] {
  const sortie: EntreeFlux[] = [];
  const noms = new Set<string>();
  for (const ligne of reponse.rows) {
    if (!retenue(ligne.team, portee, identifiantEquipe)) continue;
    noms.add(ligne.team as string);
    const groupe = ligne.type_group;
    if (groupe !== "story" && groupe !== "defect") {
      throw new TypeError("groupe de type attendu : story ou defect");
    }
    const crees = celluleDe(ligne, "created");
    const finis = celluleDe(ligne, "done");
    if (crees === null || finis === null) {
      throw new TypeError("cellules attendues");
    }
    sortie.push({ quarter: etiquetteTrimestre(texte(ligne.quarter_start, "quarter_start")), group: groupe, created: crees, done: finis });
  }
  if (portee.kind === "team" && noms.size > 1) throw new CollisionDIdentifiantsEquipe();
  return sortie;
}

function lignesDeBlocage(reponse: ReponseVue, portee: Portee, identifiantEquipe: (nom: string) => string): EntreeBloque[] {
  const sortie: EntreeBloque[] = [];
  const noms = new Set<string>();
  for (const ligne of reponse.rows) {
    if (!retenue(ligne.team, portee, identifiantEquipe)) continue;
    noms.add(ligne.team as string);
    const bloques = celluleDe(ligne, "blocked");
    const sur = celluleDe(ligne, "blocked_n");
    const part = celluleDe(ligne, "share_percent");
    if (bloques === null || sur === null || part === null) {
      throw new TypeError("cellules attendues");
    }
    sortie.push({ quarter: etiquetteTrimestre(texte(ligne.quarter_start, "quarter_start")), blocked: bloques, blockedN: sur, share: part });
  }
  if (portee.kind === "team" && noms.size > 1) throw new CollisionDIdentifiantsEquipe();
  return sortie;
}

export function creerCalculPanneaux(dep: DependancesPanneaux): {
  calculerPanneau(code: CodePanneau, filtres: FiltresValides, aujourdhui: string, jeu: CodeJeuDeDonnees): Promise<PanneauComplet>;
} {
  const produit: Portee = { kind: "product" };
  return {
    async calculerPanneau(code, f, aujourdhui, jeu) {
      // `aujourdhui` is the one date of the route: it fixes the three closed quarters of `f`.
      if (code === "blocked-share") {
        // The refusal comes before any reading: nothing is read for a scope the panel does not serve.
        if (f.scope.kind === "product") throw new PorteeProduitRefusee();
        const reponse = await lireVueMasquee(dep.acces, vueDuContrat(dep.contrat, VUE_BLOQUE), dep.seuil);
        verifierFenetre(reponse, aujourdhui);
        return panneauBlockedShare(lignesDeBlocage(reponse, f.scope, dep.identifiantEquipe), f, aujourdhui, dep.seuil, jeu);
      }
      const reponse = await lireVueMasquee(dep.acces, vueDuContrat(dep.contrat, VUE_FLUX), dep.seuil);
      // A66 (R-20261112-30): the rows read are those of the window of the day of the route (race at a quarter change).
      verifierFenetre(reponse, aujourdhui);
      if (code === "stories-inout") {
        return panneauStoriesInout(lignesDeFlux(reponse, f.scope, dep.identifiantEquipe), f, aujourdhui, dep.seuil, jeu);
      }
      // Defects and the share in correction: the product row, whatever the scope asked.
      const lignes = lignesDeFlux(reponse, produit, dep.identifiantEquipe);
      return code === "defects-inout"
        ? panneauDefectsInout(lignes, f, aujourdhui, dep.seuil, jeu)
        : panneauCorrectionShare(lignes, f, aujourdhui, dep.seuil, jeu);
    },
  };
}
