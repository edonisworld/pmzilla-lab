// The codes of the four count panels of the product-scope dashboard (mothra-slices D35, tasks 37.1 and 37.2): the panel codes, the hypothesis
// each serves and the mentions each carries. Codes only, no text (invariant 11). No import at all, so that the front takes them through the
// browser-safe subpath `@mothra/contract/listes-fiche`, which re-exports them (the package entry re-exports node-only loaders, and the front
// admits no other subpath), and `panneaux.ts` re-exports them too: one source, no copy.
// Replaces: nothing (the three tables moved here from `panneaux.ts`, unchanged). Removal: with `panneaux.ts`, at the end of the exception
// F12 (review of task 44.1), if the panels leave the dashboard.

// The four panels, named as the last segment of their route `GET /api/panels/<code>`.
export const CODES_PANNEAUX = ["stories-inout", "correction-share", "defects-inout", "blocked-share"] as const;
export type CodePanneau = (typeof CODES_PANNEAUX)[number];

// The hypothesis a panel serves (table of D35): codes, translated by the front.
export const HYPOTHESES_PANNEAUX = {
  "stories-inout": "h1_second_half",
  "correction-share": "h3",
  "defects-inout": "h3",
  "blocked-share": "dependencies_explanation",
} as const satisfies Record<CodePanneau, string>;

// The mentions every answer carries with its measure (D35 and D29): decided here, never by a component. The blocked share carries both of
// its mentions together; one never replaces the other.
export const MENTIONS_PANNEAUX = {
  "stories-inout": ["indirect_indicator"],
  "correction-share": ["indirect_indicator", "product_level"],
  "defects-inout": ["indirect_indicator", "product_level"],
  "blocked-share": ["indirect_indicator", "blocked_share_current_links"],
} as const satisfies Record<CodePanneau, readonly string[]>;

// The truncated-quarter flag (`first_quarter_truncated`, decision M5) is gone: the three closed quarters shown are whole (R-20261114-49, design D9).
