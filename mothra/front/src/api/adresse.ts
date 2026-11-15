// The addresses of the conviction pages (mothra-demo-habillage D2): `#/conviction/<kind>` and `#/conviction/<kind>/<id>`. The kind is one of
// the contract's closed list; the identifier is an opaque sheet identifier. Anything else is not a conviction address (the home is shown).
// A pure reading of the fragment: no I/O, no storage.
import { GRAPHIQUES_DE_FICHE } from "@mothra/contract/listes-fiche";
import type { GraphiqueDeFiche } from "@mothra/contract/listes-fiche";

export const PREFIXE_CONVICTION = "#/conviction/";

// An opaque sheet identifier: letters, digits, underscores and hyphens, 64 characters at most. The address and the browser memory use the same
// pattern; it lives here so that the address module imports nothing of the memory (only the dashboard page touches the memory).
const MOTIF_FICHE = /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/;

export function identifiantFicheValide(valeur: string): boolean {
  return MOTIF_FICHE.test(valeur);
}

export interface AdresseConviction {
  genre: GraphiqueDeFiche;
  id?: string;
}

export function adresseConviction(genre: GraphiqueDeFiche, id?: string): string {
  return id === undefined ? PREFIXE_CONVICTION + genre : [PREFIXE_CONVICTION, genre, "/", id].join("");
}

// The life cycle of a sheet (audit #629, A-04): the list of the sheets in progress, `#/fiches`, and the screen of one sheet, `#/fiche/<id>`,
// where it is reviewed and published. The identifier is the opaque one of the conviction addresses; anything else is not a sheet address.
export const ADRESSE_FICHES = "#/fiches";
export const PREFIXE_FICHE = "#/fiche/";

export function adresseFiche(id: string): string {
  return PREFIXE_FICHE + id;
}

// The path of a fragment, without its query string.
function cheminDuHash(hash: string): string {
  const debut = hash.indexOf("?");
  return debut < 0 ? hash : hash.slice(0, debut);
}

export function ficheDuHash(hash: string): string | undefined {
  const chemin = cheminDuHash(hash);
  if (!chemin.startsWith(PREFIXE_FICHE)) return undefined;
  const id = chemin.slice(PREFIXE_FICHE.length);
  return identifiantFicheValide(id) ? id : undefined;
}

export function convictionDuHash(hash: string): AdresseConviction | undefined {
  const chemin = cheminDuHash(hash);
  if (!chemin.startsWith(PREFIXE_CONVICTION)) return undefined;
  const morceaux = chemin.slice(PREFIXE_CONVICTION.length).split("/");
  if (morceaux.length > 2) return undefined;
  const [genre, id] = morceaux;
  if (!(GRAPHIQUES_DE_FICHE as readonly string[]).includes(genre)) return undefined;
  if (id === undefined) return { genre: genre as GraphiqueDeFiche };
  return identifiantFicheValide(id) ? { genre: genre as GraphiqueDeFiche, id } : undefined;
}
