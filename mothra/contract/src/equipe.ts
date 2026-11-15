// The opaque team identifier (R-20261030-60 and -61), in its own module so that the front imports it through the browser-safe subpath
// `@mothra/contract/equipe` (the package entry re-exports node-only loaders). No import at runtime.
import type { Portee } from "./filtres.ts";

// The one definition of its shape, shared by the filters, the sheet scope and the lead-cycle answer. 59 characters at most so that
// `team.<identifier>` fits the 64 of a sheet scope (`^[a-z0-9_.-]{1,64}$`).
export const MOTIF_IDENTIFIANT_EQUIPE = /^[a-z0-9_-]{1,59}$/;

// The identifier derived from a team name: 16 hexadecimal characters of a short hash in pure JS (no node:crypto: the front
// imports this module). Deterministic, stable from one `--rebuild` to the next (the name is unique). LIMITS: a pseudonym, not an
// anonymisation (whoever holds the list of names can find the identifier); a team renamed in Jira gets a new identifier (frozen sheets
// keep the old one); while the name travels in the same answer the opacity is a matter of display only. The collision check is the
// server's (task 18.4).
export function identifiantEquipe(nom: string): string {
  // cyrb64: two 32-bit lanes mixed over the UTF-16 units of the name.
  let h1 = 0xdeadbeef;
  let h2 = 0x41c6ce57;
  for (let i = 0; i < nom.length; i += 1) {
    const c = nom.charCodeAt(i);
    h1 = Math.imul(h1 ^ c, 2654435761);
    h2 = Math.imul(h2 ^ c, 1597334677);
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  const hex = (n: number) => (n >>> 0).toString(16).padStart(8, "0");
  return `${hex(h2)}${hex(h1)}`;
}

// The labels of the two rows that are not a team in the `team` column of the views (the product row of the panels view, the row of the
// items without a team). They are fixed texts of the views, never a team name: the generic route recognises them to give a row its `kind`.
// Source: the SQL views of db/migrations (`coalesce(..., '(sans équipe)')`, `'(produit)'::text AS team`); a gap is detected by
// contract/test/libelles-vues.test.ts. Remplace : rien. Retrait : permanent tant que les vues portent ces libellés.
export const LIBELLE_PRODUIT = "(produit)";
export const LIBELLE_SANS_EQUIPE = "(sans équipe)";

// The scope of a sheet: `product`, or `team.<identifier>`.
export function scopeFiche(portee: Portee): string {
  return portee.kind === "product" ? "product" : `team.${portee.team}`;
}

// The inverse of `scopeFiche` (task 18.4, review A1): the scope of a sheet read as `product` or `team.<identifier>`; any other text, a
// team name included, is not a scope (null).
export function porteeDeScope(scope: string): Portee | null {
  if (scope === "product") {
    return { kind: "product" };
  }
  if (scope.startsWith("team.")) {
    const identifiant = scope.slice("team.".length);
    return MOTIF_IDENTIFIANT_EQUIPE.test(identifiant) ? { kind: "team", team: identifiant } : null;
  }
  return null;
}
