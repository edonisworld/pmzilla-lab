// The mentions of the cycle time and of the blocked share (design D35, author's decision R-20261029-09 Q1 and Q3): wherever the sheet
// shows the cycle time, `cycle_time_includes_ready_queue` is next to it; wherever it shows the blocked share,
// `blocked_share_current_links` and `indirect_indicator` are next to it, never only on the method face. The labels come from the
// catalogues; the front decides nothing here but where the measure is shown.
import { createElement as h } from "react";
import type { ReactElement } from "react";
import { useIntl } from "react-intl";

import type { ColonneMesure } from "@mothra/contract/listes-fiche";

export const CLES_MENTION = {
  cycle_time_includes_ready_queue: "fiche.mention.cycle_time_includes_ready_queue",
  blocked_share_current_links: "fiche.mention.blocked_share_current_links",
  indirect_indicator: "fiche.mention.indirect_indicator",
  // The two defect panels of the product-scope dashboard (D35, task 37.2): a product measure, attributed to no team.
  product_level: "fiche.mention.product_level",
} as const;
export type CodeMention = keyof typeof CLES_MENTION;

export const MENTIONS_CYCLE_TIME: readonly CodeMention[] = ["cycle_time_includes_ready_queue"];
// The two labels go together: one never replaces the other.
export const MENTIONS_PART_BLOQUEE: readonly CodeMention[] = ["blocked_share_current_links", "indirect_indicator"];

const COLONNES_CYCLE_TIME: readonly ColonneMesure[] = ["cycle_median_days", "cycle_p85_days"];

// The mentions a measure column of the body carries.
export function mentionsDeColonne(colonne: string): readonly CodeMention[] {
  if ((COLONNES_CYCLE_TIME as readonly string[]).includes(colonne)) return MENTIONS_CYCLE_TIME;
  if (colonne === "blocked_share") return MENTIONS_PART_BLOQUEE;
  return [];
}

export function Mentions({ codes }: { codes: readonly CodeMention[] }): ReactElement | null {
  const intl = useIntl();
  if (codes.length === 0) return null;
  return h(
    "span",
    { className: "fiche-mentions" },
    // A space between two small texts, so that the copied text keeps them apart.
    codes.flatMap((code, rang) => [
      rang === 0 ? null : " ",
      h("small", { key: code, className: "fiche-mention", "data-mention": code }, intl.formatMessage({ id: CLES_MENTION[code] })),
    ]),
  );
}
