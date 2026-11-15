// SIMULATED answers of slice 1 (synthetic figures, not real data), until the routes of group 18 exist: the dashboard lead time against
// cycle time reads this module, and "make it a sheet" opens a draft through a simulated route. Nothing here calls the network and
// nothing is saved. The teams are generic names. The module holds the three kinds of cell on purpose: a value, a masked cell and an
// insufficient sample.
// Only the entry of the bundle (src/main.ts) imports this folder; the screens receive their source by injection.
import { identifiantEquipe } from "@mothra/contract/equipe";
import type { Brouillon, DemandeFiche, ReponseLeadCycle } from "@mothra/contract";

import type { SourceLeadCycle } from "../api/leadCycle.ts";

// A generic team identifier: a datum of the simulated answer, not a text of the interface (the real names come from the API).
function equipe(lettre: string): string {
  return `team-${lettre.toLowerCase()}`;
}

const REPONSE_SIMULEE: ReponseLeadCycle = {
  threshold: 5,
  dataDate: "2026-10-27",
  // Declared synthetic, so that the screen shows the notice of the synthetic dataset (D34) and offers both hypotheses.
  dataset: "synthetic",
  product: [
    { quarter: "2026-Q1", lead: { state: "value", value: 41 }, cycle: { state: "value", value: 9 }, items: { state: "value", value: 124 } },
    { quarter: "2026-Q2", lead: { state: "value", value: 38 }, cycle: { state: "value", value: 11 }, items: { state: "value", value: 131 } },
    { quarter: "2026-Q3", lead: { state: "value", value: 36 }, cycle: { state: "value", value: 10 }, items: { state: "value", value: 127 } },
  ],
  teams: [
    {
      team: equipe("A"),
      teamId: identifiantEquipe(equipe("A")),
      points: [
        { quarter: "2026-Q1", lead: { state: "insufficient_sample" }, cycle: { state: "insufficient_sample" }, items: { state: "value", value: 6 } },
        { quarter: "2026-Q2", lead: { state: "value", value: 49 }, cycle: { state: "value", value: 13 }, items: { state: "value", value: 27 } },
        { quarter: "2026-Q3", lead: { state: "value", value: 47 }, cycle: { state: "value", value: 12 }, items: { state: "value", value: 29 } },
      ],
    },
    {
      team: equipe("B"),
      teamId: identifiantEquipe(equipe("B")),
      points: [
        { quarter: "2026-Q1", lead: { state: "masked", threshold: 5 }, cycle: { state: "masked", threshold: 5 }, items: { state: "masked", threshold: 5 } },
        { quarter: "2026-Q2", lead: { state: "value", value: 22 }, cycle: { state: "value", value: 5 }, items: { state: "value", value: 19 } },
        { quarter: "2026-Q3", lead: { state: "value", value: 21 }, cycle: { state: "value", value: 6 }, items: { state: "value", value: 20 } },
      ],
    },
    {
      team: equipe("C"),
      teamId: identifiantEquipe(equipe("C")),
      points: [
        { quarter: "2026-Q1", lead: { state: "value", value: 31 }, cycle: { state: "value", value: 8 }, items: { state: "value", value: 23 } },
        { quarter: "2026-Q2", lead: { state: "value", value: 29 }, cycle: { state: "value", value: 7 }, items: { state: "value", value: 22 } },
        { quarter: "2026-Q3", lead: { state: "value", value: 30 }, cycle: { state: "value", value: 7 }, items: { state: "value", value: 25 } },
      ],
    },
  ],
};

export async function lireLeadCycleSimule(): Promise<ReponseLeadCycle> {
  return REPONSE_SIMULEE;
}

// The simulated route of "make it a sheet": always a draft with a fixed identifier, nothing stored, nothing sent.
export async function creerFicheSimulee(_demande: DemandeFiche): Promise<Brouillon> {
  return { id: "simulated-draft-1", state: "draft" };
}

export const SOURCE_SIMULEE: SourceLeadCycle = { lire: lireLeadCycleSimule, creer: creerFicheSimulee, simulee: true };
