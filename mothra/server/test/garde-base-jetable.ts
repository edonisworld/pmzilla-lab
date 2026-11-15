// The rule that decides whether a database test may touch a server: the throwaway server of tools/dbtest.sh and no other. Pure functions,
// no connection, no driver import (so a unit test of the refusal runs without a database and is not taken for a database test). Same rule as
// tests/db/garde_base_jetable.py and as the session refusal of the server, except one point: host 127.0.0.1 only, DBTEST_PORT in strict
// decimal form (no sign, no space, no leading zero, 1 to 65535), different from 5432. PMZILLA_LAB_DB_PORT is compared to it only when set
// (author's decision), whereas the Python guard requires it; no effect under dbtest, which sets both.
// A refusal names the variable, never its value. The environment is received as a parameter: this module reads no environment itself.
import type { Environnement } from "../src/config/index.ts";

export const HOTE_JETABLE = "127.0.0.1";
export const PORT_STANDARD = 5432;
export const VARIABLE_PORT_JETABLE = "DBTEST_PORT";
export const VARIABLE_PORT_LAB = "PMZILLA_LAB_DB_PORT";
export const VARIABLE_HOTE = "MOTHRA_DB_HOST";
// The superuser password of the throwaway server, handed to each suite by tools/dbtest.sh.
export const VARIABLE_MOT_DE_PASSE_SUPER = "PMZILLA_LAB_DB_PASSWORD";

export class RefusBaseJetable extends Error {
  readonly variable: string;

  constructor(variable: string) {
    super(`base jetable refusée : ${variable}`);
    this.name = "RefusBaseJetable";
    this.variable = variable;
  }
}

// The one port rule: strict decimal form only, returned as a number; any other form gives null.
export function portDecimalStrict(texte: string | undefined): number | null {
  if (texte === undefined || !/^[1-9][0-9]{0,4}$/.test(texte)) {
    return null;
  }
  const nombre = Number(texte);
  return nombre <= 65535 ? nombre : null;
}

export interface ServeurJetable {
  hote: string;
  port: number;
  motDePasseSuper: string;
}

// Throws RefusBaseJetable (naming the variable) unless every condition holds; called BEFORE any connection.
export function verifierServeurJetable(env: Environnement): ServeurJetable {
  if (env[VARIABLE_HOTE] !== undefined && env[VARIABLE_HOTE] !== HOTE_JETABLE) {
    throw new RefusBaseJetable(VARIABLE_HOTE);
  }
  const port = portDecimalStrict(env[VARIABLE_PORT_JETABLE]);
  if (port === null || port === PORT_STANDARD) {
    throw new RefusBaseJetable(VARIABLE_PORT_JETABLE);
  }
  if (env[VARIABLE_PORT_LAB] !== undefined && portDecimalStrict(env[VARIABLE_PORT_LAB]) !== port) {
    throw new RefusBaseJetable(VARIABLE_PORT_LAB);
  }
  const motDePasseSuper = env[VARIABLE_MOT_DE_PASSE_SUPER];
  if (motDePasseSuper === undefined || motDePasseSuper === "") {
    throw new RefusBaseJetable(VARIABLE_MOT_DE_PASSE_SUPER);
  }
  return { hote: HOTE_JETABLE, port, motDePasseSuper };
}

// The skip reason of the tests that need the throwaway database: `false` when they can run. Skipped, never failed, when a variable is
// absent; the reason names the variable, never a value. A present but refused value is NOT a skip: the helper fails, naming the variable.
export function sautBaseJetable(env: Environnement): string | false {
  if ((env[VARIABLE_PORT_JETABLE] ?? "") === "") {
    return `${VARIABLE_PORT_JETABLE} absent : pas de base jetable`;
  }
  if ((env[VARIABLE_MOT_DE_PASSE_SUPER] ?? "") === "") {
    return `${VARIABLE_MOT_DE_PASSE_SUPER} absent : pas de base jetable`;
  }
  return false;
}
