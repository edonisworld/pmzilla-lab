// The texts of the convictions that lot 3a shows, by catalogue key (mothra-demo-habillage D12, D13). The list of the convictions is the
// contract's closed list `GRAPHIQUES_DE_FICHE`: no conviction, order or statement is written in a component. Each kind has its statement,
// its one short name, read by the navigation, the card, the sheet list and the form (audit #629, A-10 point 5, R-20261109-08 Q1 (a)). Every key is written in full here, so that the catalogue test finds it; a kind
// without a statement key in a catalogue fails the test `conviction sans énoncé : <kind>`. The keys of the sheet page (insets, captions,
// bars) come with lot 3b.
// Replaces: nothing. Removal: permanent; the texts are validated by the author (Q130) before the train.
import type { GraphiqueDeFiche } from "@mothra/contract/listes-fiche";

import type { LienId } from "./api/fiche.ts";

export interface ClesConviction {
  enonce: string;
  nav: string;
}

// The hypothesis a sheet must be attached to for the page of each kind to show it (D6): a sheet whose `method.hypothesis` does not match the
// kind of the address is not shown. Closed on the contract's list. Replaces: nothing. Removal: permanent while a kind has one hypothesis.
export const HYPOTHESE_DU_GENRE: Record<GraphiqueDeFiche, LienId> = {
  lead_cycle_h1: "h1_first_half",
  lead_cycle_h5: "h5",
};

export const CLES_CONVICTION: Record<GraphiqueDeFiche, ClesConviction> = {
  lead_cycle_h1: {
    enonce: "conviction.statement.lead_cycle_h1",
    nav: "conviction.nav.lead_cycle_h1",
  },
  lead_cycle_h5: {
    enonce: "conviction.statement.lead_cycle_h5",
    nav: "conviction.nav.lead_cycle_h5",
  },
};
