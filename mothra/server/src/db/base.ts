// PostgreSQL access of the server: one pool, opened under the flow view-limited role only (invariant 1, D7 point 6), reading the views
// of the contract. The identifiers come from the contract (already validated against a strict pattern); no client text reaches the SQL.
import type { Vue } from "@mothra/contract";
import pg from "pg";

import { BaseIndisponible } from "./acces.ts";
import type { AccesVues, LigneBase } from "./acces.ts";
import type { Configuration } from "../config/index.ts";

const IDENTIFIANT = /^[a-z][a-z0-9_]*$/;

// Upper bound of one query (milliseconds), set on the session by the driver: a view read that runs longer is cancelled by the server.
export const DELAI_REQUETE_MS = 5000;

function identifiant(nom: string): string {
  if (!IDENTIFIANT.test(nom)) {
    throw new TypeError("identifiant refusé");
  }
  return `"${nom}"`;
}

export function parametresConnexion(config: Configuration): pg.PoolConfig {
  return {
    host: config.base.hote,
    port: config.base.port,
    database: config.base.nom,
    user: config.base.utilisateur,
    password: config.base.motDePasse,
    statement_timeout: DELAI_REQUETE_MS,
    max: 2,
    connectionTimeoutMillis: 3000,
    idleTimeoutMillis: 10000,
  };
}

export function requeteDeVue(vue: Vue): string {
  const colonnes = [...vue.plainColumns, ...(vue.maskableColumns ?? []), ...vue.countColumns].map(identifiant).join(", ");
  const tri = vue.plainColumns.length === 0 ? "" : ` ORDER BY ${vue.plainColumns.map(identifiant).join(", ")}`;
  return `SELECT ${colonnes} FROM ${identifiant(vue.schema)}.${identifiant(vue.name)}${tri}`;
}

// The marker of the synthetic dataset (design D17, D34): a catalogue lookup of the function the loader creates in its throwaway database,
// never a table read. It is made under the view-limited role, with the view connection's parameters.
export const REQUETE_MARQUEUR = "SELECT to_regprocedure('flow.synthetic_dataset_marker()') IS NOT NULL AS present";

// Whether the marker exists. One short connection, closed at once; any failure of the database gives BaseIndisponible, without detail.
export async function marqueurPostgres(config: Configuration): Promise<boolean> {
  const client = new pg.Client(parametresConnexion(config));
  try {
    await client.connect();
    const resultat = await client.query(REQUETE_MARQUEUR);
    return (resultat.rows[0] as { present: boolean }).present === true;
  } catch {
    throw new BaseIndisponible();
  } finally {
    await client.end().catch(() => undefined);
  }
}

export function creerAccesPostgres(config: Configuration): AccesVues & { fermer(): Promise<void> } {
  const pool = new pg.Pool(parametresConnexion(config));
  // An idle client failing must never crash the process nor print the driver's message.
  pool.on("error", () => {});
  return {
    async lireVue(vue: Vue): Promise<LigneBase[]> {
      try {
        const resultat = await pool.query(requeteDeVue(vue));
        return resultat.rows as LigneBase[];
      } catch {
        throw new BaseIndisponible();
      }
    },
    async fermer(): Promise<void> {
      await pool.end();
    },
  };
}
