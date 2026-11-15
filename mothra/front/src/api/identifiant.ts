// The identifier of the caller (design D29, "Caller identity"): a pseudonym or a role, never a person's name, in the format of
// `mothra.users.id` (a lowercase letter or digit, then at most 63 lowercase letters, digits, underscores or hyphens). It is kept by the
// browser under one key, read and written in a try/catch (a private window or blocked data refuses), checked before it is stored, shown in
// its field only and never logged. The storage is injected, so that the tests touch no browser.
export const CLE_IDENTIFIANT = "mothra-user";
const MOTIF_IDENTIFIANT = /^[a-z0-9][a-z0-9_-]{0,63}$/;

// What the field needs of a browser storage.
export interface StockageIdentifiant {
  getItem(cle: string): string | null;
  setItem(cle: string, valeur: string): void;
  removeItem(cle: string): void;
}

export function identifiantValide(valeur: string): boolean {
  return MOTIF_IDENTIFIANT.test(valeur);
}

function stockageDuNavigateur(): StockageIdentifiant | undefined {
  try {
    return window.localStorage;
  } catch {
    return undefined;
  }
}

// The stored identifier when there is one and it is well formed; otherwise none.
export function lireIdentifiant(stockage: StockageIdentifiant | undefined = stockageDuNavigateur()): string | undefined {
  try {
    const valeur = stockage?.getItem(CLE_IDENTIFIANT) ?? undefined;
    return valeur !== undefined && identifiantValide(valeur) ? valeur : undefined;
  } catch {
    return undefined;
  }
}

export type IssueEnregistrement = "saved" | "invalid" | "unavailable";

// Checks the format, then stores: an empty value clears the identifier. A value that fails the format is never stored.
export function ecrireIdentifiant(valeur: string, stockage: StockageIdentifiant | undefined = stockageDuNavigateur()): IssueEnregistrement {
  const propre = valeur.trim();
  if (propre !== "" && !identifiantValide(propre)) return "invalid";
  try {
    if (stockage === undefined) return "unavailable";
    if (propre === "") stockage.removeItem(CLE_IDENTIFIANT);
    else stockage.setItem(CLE_IDENTIFIANT, propre);
    return "saved";
  } catch {
    return "unavailable";
  }
}
