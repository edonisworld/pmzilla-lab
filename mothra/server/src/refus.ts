// Start refusals of the server (mothra-slices D7 and D17): one code, one exit status, one console phrase.
// The phrase holds the code and, for a configuration refusal, the variable's name: never a value, never a path, never a file's content.
export type CodeContrat = "CONTRACT_MISSING" | "CONTRACT_INVALID" | "CONTRACT_FLOOR";
export type CodeEnvironnement = "NOT_LOOPBACK" | "SESSION_WITHOUT_THROWAWAY_DB" | "DATASET_MISMATCH";
export type CodeConfiguration = "SECRET_MISSING" | "SETTING_MISSING" | "SETTING_INVALID";
export type CodeRefus = CodeContrat | CodeEnvironnement | CodeConfiguration;

export const SORTIE_USAGE = 2;
export const SORTIE_CONTRAT = 3;
export const SORTIE_ENVIRONNEMENT = 4;
export const SORTIE_CONFIGURATION = 5;

// The one table of the start refusals: each phrase maps to one exit code only (author's decision of 2026-10-28, design D17; the uniqueness
// test is test/refus.test.ts). DATASET_MISMATCH is an environment check (4); SETTING_MISSING and SETTING_INVALID, the dataset setting
// included, are configuration refusals (5).
export const CODES_DE_SORTIE: Record<CodeRefus, number> = {
  CONTRACT_MISSING: SORTIE_CONTRAT,
  CONTRACT_INVALID: SORTIE_CONTRAT,
  CONTRACT_FLOOR: SORTIE_CONTRAT,
  NOT_LOOPBACK: SORTIE_ENVIRONNEMENT,
  SESSION_WITHOUT_THROWAWAY_DB: SORTIE_ENVIRONNEMENT,
  DATASET_MISMATCH: SORTIE_ENVIRONNEMENT,
  SECRET_MISSING: SORTIE_CONFIGURATION,
  SETTING_MISSING: SORTIE_CONFIGURATION,
  SETTING_INVALID: SORTIE_CONFIGURATION,
};

export function codeDeSortie(code: CodeRefus): number {
  return CODES_DE_SORTIE[code];
}

export class RefusDemarrage extends Error {
  code: CodeRefus;
  variable: string | undefined;

  constructor(code: CodeRefus, variable?: string) {
    super(variable === undefined ? `mothra: refused (${code})` : `mothra: refused (${code}) ${variable}`);
    this.name = "RefusDemarrage";
    this.code = code;
    this.variable = variable;
  }

  get sortie(): number {
    return codeDeSortie(this.code);
  }

  // The console phrase: the message itself.
  get phrase(): string {
    return this.message;
  }
}
