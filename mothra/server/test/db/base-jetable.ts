// Throwaway database helper of the server tests (slice 0, M4). A test that imports this module is a test WITH a database: the runner of
// group 3 recognises it by that import.
//
// It connects only to the throwaway server of tools/dbtest.sh: host 127.0.0.1, port DBTEST_PORT (rule of ../garde-base-jetable.ts, checked
// before any connection, the refusal names the variable and never its value). On that server it creates its own database
// pmzilla_test_<hex>, applies the repository migrations, loads the synthetic dataset, sets a random password on the role
// pmzilla_mothra_views just before use, and hands back the typed server configuration. It drops its database (and un-logs the role) at the end.
//
// Same sources as the Python suites, no SQL duplicated here besides CREATE/DROP DATABASE and ALTER ROLE:
//   - migrations: `tools/db.py migrate` (db.lister_migrations / db.migrer over db/migrations/), on the new database;
//   - dataset: tests/mothra_donnees/jeu_synthetique.py (its own guard, role pmzilla_flow, refuses a copy of real data).
// The files that use this helper run one after the other (--test-concurrency=1 in the server test script): the role pmzilla_mothra_views is
// shared by the whole server (its password, its LOGIN, and the CREATE ROLE of the migrations), so two databases at once would collide.
// Both run through `uv run --no-project --with psycopg[binary] python`, with a minimal environment built here (never the process one).
import { spawnSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import { fileURLToPath } from "node:url";

import pg from "pg";

import { ROLE_DES_VUES, ROLE_DE_STOCKAGE, VARIABLES, chargerConfiguration } from "../../src/config/index.ts";
import type { Configuration, Environnement } from "../../src/config/index.ts";
import { LISTE_EQUIPES_FICTIVE, LISTE_SENSIBLE_FICTIVE } from "../aide.ts";
import { VARIABLE_MOT_DE_PASSE_SUPER, VARIABLE_PORT_LAB, verifierServeurJetable } from "../garde-base-jetable.ts";

export { RefusBaseJetable } from "../garde-base-jetable.ts";

const RACINE = fileURLToPath(new URL("../../../../", import.meta.url));
const BASE_ADMIN = "pmzilla";   // POSTGRES_DB of the container of tools/dbtest.sh
const UTILISATEUR_SUPER = "postgres";
const DELAI_ETAPE_MS = 180000;
const VARIABLES_TRANSMISES = ["PATH", "HOME", "TMPDIR", "LANG", "UV_CACHE_DIR", "UV_PYTHON_INSTALL_DIR", "UV_OFFLINE", "XDG_CACHE_HOME"] as const;

export interface BaseJetable {
  // Name of the throwaway database and secret of the view role, as put in the configuration object.
  nom: string;
  secret: string;
  // Secret of the storage role (task 16.1), set on this throwaway server only.
  secretStockage: string;
  port: number;
  // The typed configuration for the server (no process environment): view role, this database, this secret, this port.
  configuration(): Configuration;
  // Drops the database; never throws.
  supprimer(): Promise<void>;
  // Drops the dataset marker of this throwaway database, to play a database without it (task 16.2 review).
  retirerMarqueur(): Promise<void>;
}

type CreerClient = (parametres: pg.ClientConfig) => Pick<pg.Client, "connect" | "query" | "end">;

function masquer(texte: string, secret: string): string {
  return secret === "" ? texte : texte.split(secret).join("***");
}

function etape(nom: string, args: string[], env: Record<string, string>, secretSuper: string): void {
  const fait = spawnSync("uv", ["run", "--no-project", "--with", "psycopg[binary]", "python", "-B", ...args], {
    cwd: RACINE,
    env,
    encoding: "utf8",
    timeout: DELAI_ETAPE_MS,
    stdio: ["ignore", "pipe", "pipe"],
  });
  if (fait.status !== 0) {
    const fin = masquer(String(fait.stderr ?? ""), secretSuper).trim().split("\n").slice(-5).join("\n");
    throw new Error(`base jetable : l'étape « ${nom} » a échoué (code ${String(fait.status)})${fin === "" ? "" : `\n${fin}`}`);
  }
}

async function avecAdmin<T>(creerClient: CreerClient, hote: string, port: number, motDePasse: string, action: (c: Pick<pg.Client, "query">) => Promise<T>): Promise<T> {
  const client = creerClient({ host: hote, port, user: UTILISATEUR_SUPER, password: motDePasse, database: BASE_ADMIN, connectionTimeoutMillis: 5000 });
  try {
    await client.connect();
  } catch {
    // The driver's message is not echoed: it is not needed to name the cause (server absent or refusing).
    throw new Error("base jetable : connexion au serveur jetable impossible");
  }
  try {
    return await action(client);
  } finally {
    await client.end().catch(() => undefined);
  }
}

export interface OptionsBaseJetable {
  // Loads the dataset of slice 1 (tests/mothra_donnees/tranche1.py, which adds to slice 0's) instead of slice 0's alone (task 18.4).
  // Default false: the existing tests keep the slice 0 dataset.
  tranche1?: boolean;
}

export async function creerBaseJetable(
  env: Environnement,
  creerClient: CreerClient = (parametres) => new pg.Client(parametres),
  options: OptionsBaseJetable = {},
): Promise<BaseJetable> {
  // Refused BEFORE any connection or process: host, port rule, superuser password present.
  const { hote, port, motDePasseSuper } = verifierServeurJetable(env);
  const nom = `pmzilla_test_${randomBytes(6).toString("hex")}`;
  const secret = randomBytes(16).toString("hex");
  const secretStockage = randomBytes(16).toString("hex");
  const admin = <T>(action: (c: Pick<pg.Client, "query">) => Promise<T>): Promise<T> => avecAdmin(creerClient, hote, port, motDePasseSuper, action);

  const supprimer = async (): Promise<void> => {
    try {
      await admin(async (c) => {
        await c.query(`DROP DATABASE IF EXISTS "${nom}" WITH (FORCE)`);
        await c.query(`ALTER ROLE "${ROLE_DES_VUES}" NOLOGIN PASSWORD NULL`);
        await c.query(`ALTER ROLE "${ROLE_DE_STOCKAGE}" NOLOGIN PASSWORD NULL`);
      });
    } catch {
      // Best effort: the container is removed at the end of the dbtest run.
    }
  };

  await admin((c) => c.query(`CREATE DATABASE "${nom}"`));
  try {
    const enfant: Record<string, string> = {};
    for (const variable of VARIABLES_TRANSMISES) {
      const valeur = env[variable];
      if (valeur !== undefined) {
        enfant[variable] = valeur;
      }
    }
    Object.assign(enfant, {
      PMZILLA_LAB_DB_URL: `postgresql://${UTILISATEUR_SUPER}@${hote}:${port}/${nom}`,
      [VARIABLE_MOT_DE_PASSE_SUPER]: motDePasseSuper,
      [VARIABLE_PORT_LAB]: String(port),
      DBTEST_PORT: String(port),
      PMZILLA_LAB_DB_SECURITY_BIN: "false",   // the real keychain is never asked (the command fails, the password variable is used)
    });
    etape("migrations", ["tools/db.py", "migrate"], enfant, motDePasseSuper);
    etape("jeu synthétique", ["-I", options.tranche1 === true ? "tests/mothra_donnees/tranche1.py" : "tests/mothra_donnees/jeu_synthetique.py"], enfant, motDePasseSuper);
    // Hex only: safe in a literal. The password of the view role is set just before use, on this throwaway server only. It goes in clear in
    // ALTER ROLE (random value, container destroyed), whereas tools/db.py computes the SCRAM fingerprint client side: acceptable here.
    await admin((c) => c.query(`ALTER ROLE "${ROLE_DES_VUES}" LOGIN PASSWORD '${secret}'`));
    await admin((c) => c.query(`ALTER ROLE "${ROLE_DE_STOCKAGE}" LOGIN PASSWORD '${secretStockage}'`));
  } catch (erreur) {
    await supprimer();
    throw erreur;
  }

  const reglages: Environnement = {
    MOTHRA_DB_HOST: hote,
    MOTHRA_DB_NAME: nom,
    MOTHRA_DATASET: "synthetic",
    DBTEST_PORT: String(port),
    [VARIABLES.secretBase]: secret,
    [VARIABLES.secretStockage]: secretStockage,
    // The two lists of names (task 18.3): the fake lists of invented names, the same files as tools/dbtest.sh gives the e2e server.
    [VARIABLES.nomsSensibles]: LISTE_SENSIBLE_FICTIVE,
    [VARIABLES.nomsEquipes]: LISTE_EQUIPES_FICTIVE,
  };
  if (env[VARIABLE_PORT_LAB] !== undefined) {
    reglages[VARIABLE_PORT_LAB] = env[VARIABLE_PORT_LAB];
  }
  // Drops the marker of the synthetic dataset in this throwaway database only (superuser, this database), to play a database without it.
  const retirerMarqueur = async (): Promise<void> => {
    const client = creerClient({ host: hote, port, user: UTILISATEUR_SUPER, password: motDePasseSuper, database: nom, connectionTimeoutMillis: 5000 });
    await client.connect();
    try {
      await client.query("DROP FUNCTION IF EXISTS flow.synthetic_dataset_marker()");
    } finally {
      await client.end().catch(() => undefined);
    }
  };
  return { nom, secret, secretStockage, port, configuration: () => chargerConfiguration(reglages), supprimer, retirerMarqueur };
}
