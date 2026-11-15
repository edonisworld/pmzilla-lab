// The codes of the page "preparation of a cycle" (mothra-slices D35, tasks 40.1 and 40.2): constants and types only, no schema. This module
// imports nothing, so the pure module (`pur.ts`) can reach the front without typebox. Codes only, no text (invariant 11).
// Replaces: nothing. Removal: with the end of the exception F12 (review of task 44.1), if the page leaves the product.

// The six state codes of design D35 (codes of the page, translated by the front).
export const CODES_ETAT_PAGE = [
  "mapping_not_validated",
  "no_cycle_configured",
  "no_epic_for_cycle",
  "no_label_history",
  "ready_source_label",
  "ready_source_column",
] as const;
export type CodeEtatPage = (typeof CODES_ETAT_PAGE)[number];

// The explained empty state of a domain of fewer than three teams (author's decision R-20261031-17, Q46). It is not one of the six codes of D35.
export const CODE_DOMAINE_TROP_PETIT = "domain_too_small";

// Real data, counts not shown (author's answer R-20261031-58; D34 point 7). Chosen by the service of task 40.3 from the dataset; the contract
// holds no dataset logic beyond the explicit input `realCountsHidden` of `choisirEtats`.
export const CODE_COMPTES_REELS_MASQUES = "real_counts_not_shown";

// The blocking states: the page shows the explained empty state and no count. Their labels (domain_too_small, no_cycle_configured,
// real_counts_not_shown) belong to the catalogue D29 (a spec branch), not to the contract.
export const CODES_ETAT_VIDE = [
  "no_cycle_configured",
  "no_epic_for_cycle",
  "no_label_history",
  CODE_DOMAINE_TROP_PETIT,
  CODE_COMPTES_REELS_MASQUES,
] as const;
export type CodeEtatVide = (typeof CODES_ETAT_VIDE)[number];

// The only state that comes with a page that is shown: the columns are not computed (`no_label_history` is an empty state in every case).
export const CODES_AVIS = ["mapping_not_validated"] as const;
export type CodeAvis = (typeof CODES_AVIS)[number];

// The cycle key: lower-case letters, digits and hyphens, 1 to 32 characters. Removal condition: tightened or widened to the pattern of task
// 35.3 (referential of cycles). Limit: the pattern bounds the characters, not the content (a key may still hold a name or a title written
// in these characters); the neutrality of the key is the referential's, not this pattern's.
export const MOTIF_CLE_CYCLE = /^[a-z0-9-]{1,32}$/;

export const CODES_SOURCE_READY = ["ready_source_label", "ready_source_column"] as const;
export type CodeSourceReady = (typeof CODES_SOURCE_READY)[number];

// The refusals (422, codes only): a cycle key outside the upcoming and running cycles, and a team scope. SCOPE_INVALID is the code of the
// shared filters (task 31.1): reused, never a second definition of its meaning.
export const CODES_REFUS_PAGE = ["CYCLE_UNKNOWN", "SCOPE_INVALID"] as const;
export type CodeRefusPage = (typeof CODES_REFUS_PAGE)[number];
