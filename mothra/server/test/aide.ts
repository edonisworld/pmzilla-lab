// Shared fixtures of the server tests: the real contract, a fake database access that records its calls, a minimal valid environment.
import { fileURLToPath } from "node:url";

import { chargerContrat } from "@mothra/contract";
import type { Vue } from "@mothra/contract";

import { lireEnvironnement } from "../src/config/index.ts";
import type { Environnement } from "../src/config/index.ts";
import type { AccesVues, LigneBase } from "../src/db/acces.ts";

import { sautBaseJetable as sautDeLEnvironnement } from "./garde-base-jetable.ts";

export const CHEMIN_CONTRAT = new URL("../../../contrats/vues.json", import.meta.url);
export const CHEMIN_CAS_PARITE = new URL("../../../contrats/cas-parite.json", import.meta.url);

export const contrat = chargerContrat(CHEMIN_CONTRAT);

// Strings that must never appear in an answer, a log or a refusal phrase.
export const SENTINELLE = "SENTINELLE-NE-DOIT-JAMAIS-SORTIR";
export const SECRET_SENTINELLE = "secret-sentinelle-xyz-789";
// The secret of the storage role (task 16.1, D17): a second, distinct sentinel.
export const SECRET_STOCKAGE_SENTINELLE = "secret-stockage-sentinelle-abc-456";

export const LISTE_SENSIBLE_FICTIVE = fileURLToPath(new URL("./listes/noms-sensibles.txt", import.meta.url));
export const LISTE_EQUIPES_FICTIVE = fileURLToPath(new URL("./listes/equipes-lisibles.yaml", import.meta.url));

export function envMinimal(extra: Environnement = {}): Environnement {
  return {
    MOTHRA_DB_NAME: "mothra_test",
    MOTHRA_DATASET: "synthetic",
    PMZILLA_LAB_DB_PORT: "5432",
    PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA_VIEWS: SECRET_SENTINELLE,
    PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA: SECRET_STOCKAGE_SENTINELLE,
    // The two lists of names (task 18.3): fake lists of invented names held as test data, never the real files.
    MOTHRA_SENSITIVE_NAMES_FILE: LISTE_SENSIBLE_FICTIVE,
    MOTHRA_TEAM_NAMES_FILE: LISTE_EQUIPES_FICTIVE,
    ...extra,
  };
}

// The skip reason of the tests that need the throwaway database: `false` when they can run. Skipped, never failed, when the throwaway
// port or the superuser password of the throwaway server is absent; the reason names the variable, never a value. The rule is in
// garde-base-jetable.ts (no driver import: this module must not make every test a database test).
export function sautBaseJetable(): string | false {
  return sautDeLEnvironnement(lireEnvironnement());
}

// A fake access: records the views it was asked for and answers the rows it was given, or fails.
export class AccesFictif implements AccesVues {
  appels: string[] = [];
  lignes: LigneBase[];
  echec: Error | null;

  constructor(lignes: LigneBase[] = [], echec: Error | null = null) {
    this.lignes = lignes;
    this.echec = echec;
  }

  async lireVue(vue: Vue): Promise<LigneBase[]> {
    this.appels.push(vue.name);
    if (this.echec !== null) {
      throw this.echec;
    }
    return this.lignes;
  }
}

export function ligneStatut(equipe: string, compte: number | string | null, extra: LigneBase = {}): LigneBase {
  return { team: equipe, type: "Story", status_category: "In Progress", status: "In progress", tickets: compte, ...extra };
}

export function journalCapture(): { stream: { write(message: string): void }; texte(): string } {
  const morceaux: string[] = [];
  return {
    stream: {
      write(message: string): void {
        morceaux.push(message);
      },
    },
    texte: () => morceaux.join(""),
  };
}
