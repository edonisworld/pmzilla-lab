// The browser memory of the last sheet of each conviction (mothra-demo-habillage D11, R-20261101-42): one opaque sheet identifier per
// conviction kind, written when a draft is created or a sheet is opened, read by the conviction page only (the navigation and the home read
// nothing from it). No reference team is kept: the abandoned reference team of the first design is not stored. Nothing else is stored: no
// text, no team, no verdict. A value that is not of that shape is ignored and erased. The storage is injected, so that the tests touch no
// browser. Stored form: `{"fiches": {"<kind>": "<id>"}}`.
// Replaces: nothing. Removal: falls with a route that lists the sheets (after the demo).
import { GRAPHIQUES_DE_FICHE } from "@mothra/contract/listes-fiche";
import type { GraphiqueDeFiche } from "@mothra/contract/listes-fiche";

import { identifiantFicheValide } from "./adresse.ts";
import type { StockageIdentifiant } from "./identifiant.ts";

export const CLE_DERNIERE_FICHE = "mothra-derniere-fiche";

function stockageDuNavigateur(): StockageIdentifiant | undefined {
  try {
    return window.localStorage;
  } catch {
    return undefined;
  }
}

function estGenre(valeur: unknown): valeur is GraphiqueDeFiche {
  return typeof valeur === "string" && (GRAPHIQUES_DE_FICHE as readonly string[]).includes(valeur);
}

interface Memoire {
  fiches: Partial<Record<GraphiqueDeFiche, string>>;
}

function effacer(stockage: StockageIdentifiant | undefined): void {
  try {
    stockage?.removeItem(CLE_DERNIERE_FICHE);
  } catch {
    // The browser refuses: nothing to erase.
  }
}

// The whole memory: only the kinds of the contract list, only well-formed identifiers. Anything else is erased on the way.
function lireMemoire(stockage: StockageIdentifiant | undefined): Memoire {
  const vide: Memoire = { fiches: {} };
  try {
    const brut = stockage?.getItem(CLE_DERNIERE_FICHE) ?? null;
    if (brut === null) return vide;
    const objet: unknown = JSON.parse(brut);
    if (typeof objet !== "object" || objet === null || Array.isArray(objet)) throw new Error("forme");
    const { fiches, ...reste } = objet as Record<string, unknown>;
    if (Object.keys(reste).length > 0 || typeof fiches !== "object" || fiches === null || Array.isArray(fiches)) throw new Error("forme");
    const propre: Memoire = { fiches: {} };
    for (const [genre, valeur] of Object.entries(fiches as Record<string, unknown>)) {
      if (!estGenre(genre) || typeof valeur !== "string" || !identifiantFicheValide(valeur)) throw new Error("forme");
      propre.fiches[genre] = valeur;
    }
    return propre;
  } catch {
    effacer(stockage);
    return vide;
  }
}

export function lireDerniereFiche(genre: GraphiqueDeFiche, stockage: StockageIdentifiant | undefined = stockageDuNavigateur()): string | undefined {
  return lireMemoire(stockage).fiches[genre];
}

// Writes the identifier of the kind; an identifier that is not well formed is not stored. Never raises.
export function ecrireDerniereFiche(genre: GraphiqueDeFiche, id: string, stockage: StockageIdentifiant | undefined = stockageDuNavigateur()): boolean {
  if (!identifiantFicheValide(id)) return false;
  try {
    const memoire = lireMemoire(stockage);
    memoire.fiches[genre] = id;
    stockage?.setItem(CLE_DERNIERE_FICHE, JSON.stringify(memoire));
    return stockage !== undefined;
  } catch {
    return false;
  }
}
