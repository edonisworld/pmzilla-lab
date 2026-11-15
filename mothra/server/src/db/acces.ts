// What the server needs from the database: the rows of one view of the contract, nothing else. The service layer never sees a driver.
import type { Vue } from "@mothra/contract";

export type LigneBase = Record<string, unknown>;

export interface AccesVues {
  // Reads the rows of a view. The name comes from the contract (a view of the closed list), except one: the service also reads
  // `v_team_weekly_resolved`, a constant of service.ts that is never served, for the relation T3 (masking-sums D17).
  lireVue(vue: Vue): Promise<LigneBase[]>;
}

// Any failure of the database (refused connection, timeout, privilege): no detail is kept, the answer is DATABASE_UNAVAILABLE.
export class BaseIndisponible extends Error {
  constructor() {
    super("database unavailable");
    this.name = "BaseIndisponible";
  }
}
