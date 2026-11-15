// Start check of the team identifiers (author's decision R-20261030-61): two team names of the views must not give the same opaque
// identifier. Replaces: nothing. Removal condition: falls when the identifier comes from a column of the view instead of a hash (the
// decision's option b), which cannot collide.
import type { Contrat } from "@mothra/contract";
import { LIBELLE_PRODUIT, LIBELLE_SANS_EQUIPE } from "@mothra/contract/equipe";

import type { AccesVues } from "../db/acces.ts";
import { lireVueMasquee } from "../service.ts";

// The identifiers shared by two different names, sorted; never the names themselves.
export function collisionsDIdentifiants(noms: readonly string[], identifiant: (nom: string) => string): string[] {
  const parIdentifiant = new Map<string, Set<string>>();
  for (const nom of noms) {
    const id = identifiant(nom);
    const ensemble = parIdentifiant.get(id) ?? new Set<string>();
    ensemble.add(nom);
    parIdentifiant.set(id, ensemble);
  }
  return [...parIdentifiant.entries()].filter(([, ensemble]) => ensemble.size > 1).map(([id]) => id).sort();
}

// The team names of every served view that has a team column (A-68, audit #629): the list of views is drawn from the contract (the views
// whose `plainColumns` hold `team`), never copied, so a by-team view added to the contract is checked without a change here. The labels of
// the product row and of the row without a team are not teams. The contract has no list of teams view; v_teams is not served.
// Replaces: the reading of the lead time view alone (R-20261030-61, first version of this check). Removal condition: falls with the check
// itself, when the identifier comes from a column of the view instead of a hash.
export async function nomsDEquipes(acces: AccesVues, contrat: Contrat, seuil: number): Promise<string[]> {
  const noms = new Set<string>();
  for (const vue of contrat.views.filter((v) => v.plainColumns.includes("team"))) {
    const reponse = await lireVueMasquee(acces, vue, seuil);
    for (const ligne of reponse.rows) {
      const nom = ligne.team;
      if (typeof nom === "string" && nom !== LIBELLE_PRODUIT && nom !== LIBELLE_SANS_EQUIPE) {
        noms.add(nom);
      }
    }
  }
  return [...noms];
}

// The sentence of the server log when the sheet routes are not served: no name, no identifier.
export const PHRASE_COLLISION_EQUIPES = "Mothra: two teams give the same identifier, the sheet routes are not served.";
