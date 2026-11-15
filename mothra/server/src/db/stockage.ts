// Storage access of the server (task 16.1, ADR 0006): the second connection, opened under the storage role only, whose search path is the
// schema mothra. It never reads a view: the views go through the first connection (base.ts), under the view-limited role. The two pools
// never share a role nor a secret; the secret comes from the configuration module, as a function, and is never logged.
import pg from "pg";

import { BaseIndisponible } from "./acces.ts";
import type { Configuration } from "../config/index.ts";
import type { TexteLibre } from "@mothra/contract";
import { FicheDejaPubliee, LIMITE_LISTE_FICHES } from "../fiches/depot.ts";
import type { ContenuFige, DepotFiches, DepotSeuils, DepotUtilisateurs, FicheListee, FicheStockee, SeuilStocke } from "../fiches/depot.ts";

// Upper bound of one query (milliseconds), set on the session by the driver.
export const DELAI_REQUETE_STOCKAGE_MS = 5000;

// The access the start-up holds (the test doubles of the start-up give only these two methods); the thresholds and the sheets come with
// `AccesStockageComplet`.
export interface AccesStockageComplet extends AccesStockage, DepotSeuils, DepotFiches, DepotUtilisateurs {}

export interface AccesStockage {
  // The role of the session, to check which connection is open. Any failure of the database gives BaseIndisponible, without detail.
  roleCourant(): Promise<string>;
  fermer(): Promise<void>;
}

export function parametresStockage(config: Configuration): pg.PoolConfig {
  return {
    host: config.stockage.hote,
    port: config.stockage.port,
    database: config.stockage.nom,
    user: config.stockage.utilisateur,
    password: config.stockage.motDePasse,
    options: "-c search_path=mothra",
    statement_timeout: DELAI_REQUETE_STOCKAGE_MS,
    max: 2,
    connectionTimeoutMillis: 3000,
    idleTimeoutMillis: 10000,
  };
}

// The pool opens its connections lazily, on the first query: creating the access object is not a connection.
export function creerAccesStockage(config: Configuration): AccesStockageComplet {
  const pool = new pg.Pool(parametresStockage(config));
  // An idle client failing must never crash the process nor print the driver's message.
  pool.on("error", () => {});
  return {
    async roleCourant(): Promise<string> {
      try {
        const resultat = await pool.query("SELECT current_user AS role");
        return String((resultat.rows[0] as { role: string }).role);
      } catch {
        throw new BaseIndisponible();
      }
    },
    // The threshold history, insertion and reading only (the role has no update and no delete on it). Parameters only, no text built from a value.
    async seuils(): Promise<SeuilStocke[]> {
      try {
        const resultat = await pool.query(
          "SELECT threshold_code AS code, value::float8 AS value, to_char(set_on, 'YYYY-MM-DD') AS \"setOn\", set_by AS \"setBy\" FROM threshold_history ORDER BY set_on, id",
        );
        return resultat.rows as SeuilStocke[];
      } catch {
        throw new BaseIndisponible();
      }
    },
    async ajouterSeuil(seuil: SeuilStocke): Promise<void> {
      try {
        await pool.query("INSERT INTO threshold_history (threshold_code, value, set_on, set_by) VALUES ($1, $2, $3, $4)", [
          seuil.code,
          seuil.value,
          seuil.setOn,
          seuil.setBy,
        ]);
      } catch {
        throw new BaseIndisponible();
      }
    },
    // The sheets (task 18.1, migrations 0024 and 0027). Parameters only. Any failure of the database, a refused value included, gives
    // BaseIndisponible without detail: the request forms are checked before (request schema), so a refusal here is a fault.
    async creer(entree: Parameters<DepotFiches["creer"]>[0]): Promise<string> {
      try {
        const resultat = await pool.query(
          "INSERT INTO sheets (kind, scope, data_date, management_question, effect_text, effect_lang, cause_text, cause_lang, created_by) " +
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING id::text AS id",
          [
            entree.chart,
            entree.scope,
            entree.dataDate,
            entree.managementQuestion ?? null,
            entree.effect?.text ?? null,
            entree.effect?.lang ?? null,
            entree.cause?.text ?? null,
            entree.cause?.lang ?? null,
            entree.createdBy,
          ],
        );
        return String((resultat.rows[0] as { id: string }).id);
      } catch {
        throw new BaseIndisponible();
      }
    },
    // The sheets of one state (A-04): identifier, kind, scope, data date, state; the newest first, bounded. Parameters only; the state is one of
    // the three of the table (the route checks it before). No written text and no published content is read. The order names the column
    // (`sheets.id`): a bare `id` would sort on the text alias of the output, "9" after "10" (tests/db/test_mothra_liste_fiches.py).
    async lister(etat: Parameters<DepotFiches["lister"]>[0]): Promise<FicheListee[]> {
      try {
        const resultat = await pool.query(
          "SELECT id::text AS id, kind, scope, to_char(data_date, 'YYYY-MM-DD') AS data_date, state FROM sheets WHERE state = $1 ORDER BY sheets.id DESC LIMIT $2",
          [etat, LIMITE_LISTE_FICHES],
        );
        return (resultat.rows as Array<Record<string, unknown>>).map((ligne) => ({
          id: String(ligne.id),
          chart: String(ligne.kind),
          scope: String(ligne.scope),
          dataDate: String(ligne.data_date),
          state: ligne.state as FicheListee["state"],
        }));
      } catch {
        throw new BaseIndisponible();
      }
    },
    async lire(id: string): Promise<FicheStockee | null> {
      // An identifier that is not a number is an unknown sheet, never a query.
      if (!/^[0-9]{1,18}$/.test(id)) return null;
      try {
        const resultat = await pool.query(
          "SELECT s.id::text AS id, s.kind, s.scope, to_char(s.data_date, 'YYYY-MM-DD') AS data_date, s.state, s.management_question, " +
            "s.effect_text, s.effect_lang, s.cause_text, s.cause_lang, s.created_by, s.reviewed_by, " +
            "v.version, v.content, v.fingerprint, v.published_by, to_char(v.published_at, 'YYYY-MM-DD') AS published_on " +
            "FROM sheets s LEFT JOIN LATERAL (SELECT * FROM published_versions p WHERE p.sheet_id = s.id ORDER BY p.version DESC LIMIT 1) v ON true " +
            "WHERE s.id = $1",
          [id],
        );
        const ligne = resultat.rows[0] as Record<string, unknown> | undefined;
        return ligne === undefined ? null : ficheDeLigne(ligne);
      } catch {
        throw new BaseIndisponible();
      }
    },
    // The day the sheet was created, `created_at` of the table (task 18.4, Q8): the first reading of its data.
    async creeeLe(id: string): Promise<string | null> {
      if (!/^[0-9]{1,18}$/.test(id)) return null;
      try {
        const resultat = await pool.query("SELECT to_char(created_at, 'YYYY-MM-DD') AS created_on FROM sheets WHERE id = $1", [id]);
        const ligne = resultat.rows[0] as { created_on: string } | undefined;
        return ligne === undefined ? null : ligne.created_on;
      } catch {
        throw new BaseIndisponible();
      }
    },
    // Only the fields given change (COALESCE keeps the others); a draft only. A text and its language move together (the table checks it).
    async modifier(id: string, changement: Parameters<DepotFiches["modifier"]>[1]): Promise<void> {
      try {
        await pool.query(
          "UPDATE sheets SET management_question = COALESCE($2, management_question), " +
            "effect_text = COALESCE($3, effect_text), effect_lang = COALESCE($4, effect_lang), " +
            "cause_text = COALESCE($5, cause_text), cause_lang = COALESCE($6, cause_lang), updated_at = now() " +
            "WHERE id = $1 AND state = 'draft'",
          [
            id,
            changement.managementQuestion ?? null,
            changement.effect?.text ?? null,
            changement.effect?.lang ?? null,
            changement.cause?.text ?? null,
            changement.cause?.lang ?? null,
          ],
        );
      } catch {
        throw new BaseIndisponible();
      }
    },
    // Whether the pseudonymous identifier is a user of the application. A malformed identifier never reaches the query.
    async utilisateurExiste(id: string): Promise<boolean> {
      if (!/^[a-z0-9][a-z0-9_-]{0,63}$/.test(id)) return false;
      try {
        const resultat = await pool.query("SELECT 1 FROM users WHERE id = $1", [id]);
        return resultat.rows.length > 0;
      } catch {
        throw new BaseIndisponible();
      }
    },
    async relire(id: string, reviewer: string): Promise<void> {
      try {
        await pool.query("UPDATE sheets SET state = 'reviewed', reviewed_by = $2, updated_at = now() WHERE id = $1 AND state = 'draft'", [id, reviewer]);
      } catch {
        throw new BaseIndisponible();
      }
    },
    // The freeze: the next version of the sheet is inserted (insert only, never changed) and the state becomes `published`, in one transaction.
    async publier(id: string, entree: Parameters<DepotFiches["publier"]>[1]): Promise<{ version: number; publishedOn: string }> {
      let client: pg.PoolClient;
      try {
        client = await pool.connect();
      } catch {
        throw new BaseIndisponible();
      }
      try {
        await client.query("BEGIN");
        // The state is checked again here, under the row lock of this UPDATE: only a reviewed sheet is frozen, and two requests cannot both
        // freeze it. No row: the sheet was published (or changed) in between, the transaction ends and the route answers VERSION_FROZEN.
        const etat = await client.query("UPDATE sheets SET state = 'published', updated_at = now() WHERE id = $1 AND state = 'reviewed' RETURNING id", [id]);
        if (etat.rows.length === 0) {
          await client.query("ROLLBACK");
          throw new FicheDejaPubliee();
        }
        const inseree = await client.query(
          "INSERT INTO published_versions (sheet_id, version, content, fingerprint, published_by) " +
            "SELECT $1::bigint, COALESCE(MAX(version), 0) + 1, $2::jsonb, $3::text, $4::text FROM published_versions WHERE sheet_id = $1::bigint " +
            "RETURNING version, to_char(published_at, 'YYYY-MM-DD') AS published_on",
          [id, JSON.stringify(entree.content), entree.fingerprint, entree.publishedBy],
        );
        await client.query("COMMIT");
        const ligne = inseree.rows[0] as { version: number; published_on: string };
        return { version: Number(ligne.version), publishedOn: ligne.published_on };
      } catch (erreur) {
        if (erreur instanceof FicheDejaPubliee) throw erreur;
        await client.query("ROLLBACK").catch(() => {});
        throw new BaseIndisponible();
      } finally {
        client.release();
      }
    },
    async fermer(): Promise<void> {
      await pool.end();
    },
  };
}

// A row of the join: the sheet and its latest published version, when there is one.
function ficheDeLigne(l: Record<string, unknown>): FicheStockee {
  const texte = (t: unknown, lang: unknown): TexteLibre | undefined =>
    typeof t === "string" && (lang === "fr" || lang === "en") ? { text: t, lang } : undefined;
  const fiche: FicheStockee = {
    id: String(l.id),
    chart: String(l.kind),
    scope: String(l.scope ?? ""),
    dataDate: String(l.data_date ?? ""),
    state: l.state as FicheStockee["state"],
    managementQuestion: (l.management_question ?? undefined) as FicheStockee["managementQuestion"],
    effect: texte(l.effect_text, l.effect_lang),
    cause: texte(l.cause_text, l.cause_lang),
    createdBy: String(l.created_by),
    reviewedBy: typeof l.reviewed_by === "string" ? l.reviewed_by : undefined,
  };
  if (l.version !== null && l.version !== undefined) {
    fiche.published = {
      version: Number(l.version),
      content: l.content as ContenuFige,
      fingerprint: String(l.fingerprint),
      publishedBy: String(l.published_by),
      publishedOn: String(l.published_on),
    };
  }
  return fiche;
}
