# /// script
# requires-python = ">=3.11"
# dependencies = ["psycopg[binary]", "numpy"]
# ///
"""
PMZilla Lab — état de la veille et du pré-tri dans la base PostgreSQL (schéma knowledge, migration 0007).

Ce module remplace les deux anciens fichiers d'état locaux : `WatchStore` (articles collectés, passages de collecte, liens cités) et `TriageStore`
(références, notes, sauvetages, exclusions, partages, sélections du jour, notes en ombre, calibration) s'appuient sur une connexion
psycopg et rendent des valeurs Python simples (dates, booléens, dict, vecteurs numpy float32), jamais des objets du pilote : le code de
décision de watch_lab.py et de watch_triage.py ne dépend pas du stockage.

Rôles : les commandes qui écrivent se connectent par le chemin de l'indexeur (db.connect puis SET ROLE pmzilla_knowledge) ; les
lectures (`readonly=True`) sous pmzilla_knowledge_ro. Une autre base de l'instance peut être désignée par
PMZILLA_LAB_KNOWLEDGE_DBNAME (bases jetables des tests).

Erreurs : une base qui ne répond pas devient WatchDatabaseUnavailable, des tables absentes WatchTablesMissing. Aucun message ne porte de
mot de passe, d'adresse avec identifiants ni de message du pilote (le type de l'erreur seulement).

Pas de repli : ce module n'a aucun autre stockage que la base. L'outil de copie lit les anciens fichiers à part.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys

import numpy as np

WRITE_ROLE = "pmzilla_knowledge"
READ_ROLE = "pmzilla_knowledge_ro"
DBNAME_VARIABLE = "PMZILLA_LAB_KNOWLEDGE_DBNAME"

TABLES = ("watch_articles", "watch_source_runs", "watch_article_links", "triage_references", "triage_scores", "triage_forced",
          "triage_excluded", "triage_shared", "triage_daily_picks", "triage_shadow_scores", "triage_calibration")


EXIT_UNAVAILABLE = 4
EXIT_TABLES_MISSING = 5
MESSAGE_UNAVAILABLE = "Base de données injoignable : démarrer la base (bash tools/db_up.sh), puis relancer."
MESSAGE_TABLES_MISSING = "Tables de la veille absentes : appliquer les migrations (uv run tools/db.py migrate)."


class WatchDatabaseUnavailable(Exception):
    """La base ne répond pas. Le message est un type d'erreur, jamais un secret."""


class WatchTablesMissing(Exception):
    """Les tables de la veille sont absentes : migrations à appliquer."""


def stop(error: Exception) -> None:
    """Fin de commande sur une erreur de base : message sur l'erreur standard (ni mot de passe ni texte du pilote), code 4 ou 5."""
    if isinstance(error, WatchTablesMissing):
        print(MESSAGE_TABLES_MISSING, file=sys.stderr)
        raise SystemExit(EXIT_TABLES_MISSING) from None
    print(MESSAGE_UNAVAILABLE, file=sys.stderr)
    raise SystemExit(EXIT_UNAVAILABLE) from None


# ---------------------------------------------------------------------------
# Valeurs
# ---------------------------------------------------------------------------

def as_date(value) -> dt.date | None:
    """Date d'un texte AAAA-MM-JJ (début d'un horodatage accepté), d'une date ou d'un datetime ; vide : None."""
    if value is None or value == "":
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value)[:10])


def as_moment(value) -> dt.datetime | None:
    """Instant d'un texte ISO, d'un datetime naïf (heure locale de la machine) ou d'un datetime avec fuseau."""
    if value is None or value == "":
        return None
    if isinstance(value, str):
        value = dt.datetime.fromisoformat(value)
    return value.astimezone() if value.tzinfo is None else value


def local(value: dt.datetime | None) -> dt.datetime | None:
    return None if value is None else value.astimezone()


def start_of(day: dt.date) -> dt.datetime:
    """Minuit local de `day` (comparaison d'horodatages à une date)."""
    return dt.datetime.combine(day, dt.time.min).astimezone()


def halfvec_literal(vector) -> str:
    """Littéral halfvec exact d'un vecteur (9 chiffres significatifs ramènent la valeur float16 telle quelle)."""
    return "[" + ",".join("%.9g" % float(v) for v in np.asarray(vector, dtype=np.float16).astype(np.float32)) + "]"


def parse_vector(text) -> np.ndarray:
    return np.array(json.loads(text) if isinstance(text, str) else list(text), dtype=np.float32)


def as_json(value) -> str | None:
    return None if value is None else json.dumps(value, ensure_ascii=False)


SCORE_COLUMNS = ("file", "url", "title", "source", "published", "collected", "complete", "criteria", "substance", "summary", "why",
                 "model", "scored_at", "location", "justifications", "is_compilation", "in_themes", "is_promo")
SHADOW_COLUMNS = ("url", "language", "model", "prompts_hash", "criteria", "substance", "is_compilation", "in_themes", "is_promo",
                  "scored_at")
CALIBRATION_COLUMNS = ("file", "exported_at", "verdict", "relevance", "substance", "in_themes", "is_compilation", "is_promo",
                       "missing", "opinion", "opinion_at")
OPINION_OF = {"keep": True, "discard": False}


def normalize_score(score: dict) -> dict:
    """Valeurs d'une note telles que les rendent les deux implémentations (dates, instants, vecteur float32)."""
    row = {name: score.get(name) for name in SCORE_COLUMNS}
    row["location"] = row["location"] or "watch"
    row["published"] = as_date(row["published"])
    row["collected"] = as_moment(row["collected"])
    row["scored_at"] = as_moment(row["scored_at"])
    row["embedding"] = np.asarray(score["embedding"], dtype=np.float16).astype(np.float32)
    return row


def normalize_shadow(row: dict) -> dict:
    out = {name: row.get(name) for name in SHADOW_COLUMNS}
    out["scored_at"] = as_moment(out["scored_at"])
    return out


# ---------------------------------------------------------------------------
# Connexion
# ---------------------------------------------------------------------------

def open_connection(readonly: bool = False, dbname: str | None = None, connect=None):
    """Connexion prête à l'emploi (rôle d'écriture ou de lecture seule) après contrôle des onze tables.

    `connect(role, dbname)` remplace db.connect (tests). Lève WatchDatabaseUnavailable ou WatchTablesMissing."""
    dbname = dbname or os.environ.get(DBNAME_VARIABLE) or None
    try:
        if connect is not None:
            conn = connect(READ_ROLE if readonly else None, dbname)
        else:
            import db
            conn = db.connect(role=READ_ROLE, dbname=dbname) if readonly else db.connect(dbname=dbname)
        if not readonly:
            conn.execute(f"SET ROLE {WRITE_ROLE}")
            conn.commit()      # le rôle reste pour la session, après chaque validation ou annulation
    except Exception as error:     # aucun message du pilote : il peut nommer le serveur
        raise WatchDatabaseUnavailable(type(error).__name__) from None
    try:
        present = [row[0] for row in conn.execute(
            "SELECT t FROM unnest(%s::text[]) AS t WHERE to_regclass('knowledge.' || t) IS NOT NULL", (list(TABLES),)).fetchall()]
        conn.rollback()
    except Exception as error:
        _close_quietly(conn)
        raise WatchDatabaseUnavailable(type(error).__name__) from None
    if set(present) != set(TABLES):
        _close_quietly(conn)
        raise WatchTablesMissing(", ".join(sorted(set(TABLES) - set(present))))
    return conn


def _close_quietly(conn) -> None:
    try:
        conn.close()
    except Exception:
        pass


def open_watch_store(readonly: bool = False, dbname: str | None = None, connect=None) -> "WatchStore":
    return WatchStore(open_connection(readonly, dbname, connect))


def open_triage_store(readonly: bool = False, dbname: str | None = None, connect=None) -> "TriageStore":
    return TriageStore(open_connection(readonly, dbname, connect))


class _Base:
    def __init__(self, conn) -> None:
        self.conn = conn

    def _run(self, sql: str, params=()):
        try:
            return self.conn.execute(sql, params)
        except Exception as error:
            if type(error).__module__.startswith("psycopg") and type(error).__name__ in ("OperationalError", "InterfaceError"):
                raise WatchDatabaseUnavailable(type(error).__name__) from None
            raise

    def _all(self, sql: str, params=()) -> list:
        return self._run(sql, params).fetchall()

    def _one(self, sql: str, params=()):
        return self._run(sql, params).fetchone()

    def commit(self) -> None:
        try:
            self.conn.commit()
        except Exception as error:
            if type(error).__module__.startswith("psycopg"):
                raise WatchDatabaseUnavailable(type(error).__name__) from None
            raise

    def rollback(self) -> None:
        try:
            self.conn.rollback()
        except Exception:
            pass

    def close(self) -> None:
        _close_quietly(self.conn)


# ---------------------------------------------------------------------------
# Collecte
# ---------------------------------------------------------------------------

class WatchStore(_Base):
    """Articles collectés, dernier passage de chaque source, liens cités."""

    def article_exists(self, url: str) -> bool:
        return self._one("SELECT 1 FROM knowledge.watch_articles WHERE url = %s", (url,)) is not None

    def earlier_duplicate(self, source: str, title: str, published: dt.date, before_day: dt.date) -> bool:
        """Même source, même titre, même date de publication, collecté un jour avant `before_day`."""
        return self._one("SELECT 1 FROM knowledge.watch_articles WHERE source = %s AND title = %s AND published = %s AND collected < %s",
                         (source, title, as_date(published), start_of(before_day))) is not None

    def add_article(self, url, source, title, file, published, complete, collected, links_extracted: bool = False) -> None:
        self._run("INSERT INTO knowledge.watch_articles (url, source, title, file, published, complete, collected, links_extracted) "
                  "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                  (url, source, title, file, as_date(published), bool(complete), as_moment(collected), bool(links_extracted)))

    def add_links(self, article_url: str, links) -> None:
        """Liens cités par l'article (sans doublon) ; l'article est marqué « liens relevés »."""
        for link in sorted(links):
            self._run("INSERT INTO knowledge.watch_article_links (article_url, target_url) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                      (article_url, link))
        self._run("UPDATE knowledge.watch_articles SET links_extracted = true WHERE url = %s", (article_url,))

    def record_run_ok(self, source: str, when) -> None:
        self._run("INSERT INTO knowledge.watch_source_runs (source, last_try, last_ok, error) VALUES (%s, %s, %s, NULL) "
                  "ON CONFLICT (source) DO UPDATE SET last_try = EXCLUDED.last_try, last_ok = EXCLUDED.last_ok, error = NULL",
                  (source, as_moment(when), as_moment(when)))

    def record_run_error(self, source: str, when, error: str) -> None:
        self._run("INSERT INTO knowledge.watch_source_runs (source, last_try, last_ok, error) VALUES (%s, %s, NULL, %s) "
                  "ON CONFLICT (source) DO UPDATE SET last_try = EXCLUDED.last_try, error = EXCLUDED.error",
                  (source, as_moment(when), error))

    def source_runs(self) -> dict[str, dict]:
        return {r[0]: {"last_try": local(r[1]), "last_ok": local(r[2]), "error": r[3]}
                for r in self._all("SELECT source, last_try, last_ok, error FROM knowledge.watch_source_runs ORDER BY source")}

    def links_todo(self) -> list[tuple[str, str]]:
        """(adresse, titre) des articles dont les liens n'ont pas été relevés, du plus ancien au plus récent."""
        return [(r[0], r[1]) for r in self._all(
            "SELECT url, title FROM knowledge.watch_articles WHERE NOT links_extracted AND url LIKE 'http%%' ORDER BY collected, url")]

    def articles_collected_since(self, since: dt.date) -> list[tuple]:
        """(source, titre, adresse, date de publication, complet, fichier) des articles collectés depuis `since`."""
        return [(r[0], r[1], r[2], r[3], r[4], r[5]) for r in self._all(
            "SELECT source, title, url, published, complete, file FROM knowledge.watch_articles WHERE collected >= %s "
            "ORDER BY source, published DESC NULLS LAST, url", (start_of(since),))]

    def all_links(self) -> list[tuple[str, str]]:
        return [(r[0], r[1]) for r in self._all(
            "SELECT article_url, target_url FROM knowledge.watch_article_links ORDER BY article_url, target_url")]

    def articles(self) -> list[dict]:
        """Tous les articles (lecture de l'outil de copie et de la parité), par adresse."""
        return [{"url": r[0], "source": r[1], "title": r[2], "file": r[3], "published": r[4], "complete": r[5],
                 "collected": local(r[6]), "links_extracted": r[7]}
                for r in self._all("SELECT url, source, title, file, published, complete, collected, links_extracted "
                                   "FROM knowledge.watch_articles ORDER BY url")]


# ---------------------------------------------------------------------------
# Pré-tri
# ---------------------------------------------------------------------------

class TriageStore(_Base):
    """Références, notes, sauvetages, exclusions, partages, sélections du jour, notes en ombre, calibration."""

    # -- références ------------------------------------------------------

    def replace_references(self, refs: list[tuple]) -> None:
        """Remplace les références qui ne viennent pas des partages (les partages restent). refs : (url, titre, origine, vecteur)."""
        self._run("DELETE FROM knowledge.triage_references WHERE origin IS DISTINCT FROM 'partage'")
        for ref in refs:
            self.put_reference(*ref)

    def put_reference(self, url, title, origin, embedding) -> None:
        self._run("INSERT INTO knowledge.triage_references (url, title, origin, embedding) VALUES (%s, %s, %s, %s::halfvec) "
                  "ON CONFLICT (url) DO UPDATE SET title = EXCLUDED.title, origin = EXCLUDED.origin, embedding = EXCLUDED.embedding",
                  (url, title, origin, halfvec_literal(embedding)))

    def reference_vectors(self) -> list[np.ndarray]:
        return [parse_vector(r[0]) for r in self._all("SELECT embedding::text FROM knowledge.triage_references ORDER BY url")]

    # -- notes -----------------------------------------------------------

    def put_score(self, **score) -> None:
        """Insère ou remplace la note d'un article (toute la ligne, l'emplacement revient à « watch » sauf indication)."""
        row = normalize_score(score)
        columns = list(SCORE_COLUMNS)
        values = [row[c] for c in columns]
        for name in ("criteria", "justifications"):
            values[columns.index(name)] = as_json(row[name])
        placeholders = ", ".join("%s::jsonb" if c in ("criteria", "justifications") else "%s" for c in columns)
        updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in columns + ["embedding"] if c != "file")
        self._run(f"INSERT INTO knowledge.triage_scores ({', '.join(columns)}, embedding) VALUES ({placeholders}, %s::halfvec) "
                  f"ON CONFLICT (file) DO UPDATE SET {updates}", (*values, halfvec_literal(row["embedding"])))

    def all_scores(self) -> list[dict]:
        """Toutes les notes, par nom de fichier."""
        rows = self._all(f"SELECT {', '.join(SCORE_COLUMNS)}, embedding::text FROM knowledge.triage_scores ORDER BY file")
        out = []
        for r in rows:
            row = dict(zip(SCORE_COLUMNS, r))
            row["embedding"] = parse_vector(r[len(SCORE_COLUMNS)])
            row["collected"], row["scored_at"] = local(row["collected"]), local(row["scored_at"])
            out.append(row)
        return out

    def score_files(self) -> set[str]:
        return {r[0] for r in self._all("SELECT file FROM knowledge.triage_scores")}

    def flagged_files(self, flag: str) -> set[str]:
        """Fichiers notés avec `is_compilation` ou `is_promo` vrai."""
        column = {"compilation": "is_compilation", "promo": "is_promo"}[flag]
        return {r[0] for r in self._all(f"SELECT file FROM knowledge.triage_scores WHERE {column}")}

    def weak_files(self, max_substance: int) -> set[str]:
        return {r[0] for r in self._all("SELECT file FROM knowledge.triage_scores WHERE substance IS NOT NULL AND substance <= %s",
                                        (max_substance,))}

    def location_of(self, file: str) -> str | None:
        row = self._one("SELECT location FROM knowledge.triage_scores WHERE file = %s", (file,))
        return None if row is None else row[0]

    def set_location(self, file: str, location: str) -> None:
        self._run("UPDATE knowledge.triage_scores SET location = %s WHERE file = %s", (location, file))

    def score_urls(self) -> list[tuple[str, str, np.ndarray]]:
        """(fichier, adresse, vecteur) des notes qui ont une adresse."""
        return [(r[0], r[1], parse_vector(r[2])) for r in self._all(
            "SELECT file, url, embedding::text FROM knowledge.triage_scores WHERE url IS NOT NULL AND url <> '' ORDER BY file")]

    # -- sauvetages, exclusions ------------------------------------------

    def forced_files(self) -> set[str]:
        return {r[0] for r in self._all("SELECT file FROM knowledge.triage_forced")}

    def excluded_files(self) -> set[str]:
        return {r[0] for r in self._all("SELECT file FROM knowledge.triage_excluded")}

    def exclude(self, file: str, day) -> None:
        self._run("DELETE FROM knowledge.triage_forced WHERE file = %s", (file,))
        self._run("INSERT INTO knowledge.triage_excluded (file, since) VALUES (%s, %s) "
                  "ON CONFLICT (file) DO UPDATE SET since = EXCLUDED.since", (file, as_date(day)))

    def restore(self, file: str, day) -> None:
        self._run("DELETE FROM knowledge.triage_excluded WHERE file = %s", (file,))
        self._run("INSERT INTO knowledge.triage_forced (file, since) VALUES (%s, %s) "
                  "ON CONFLICT (file) DO UPDATE SET since = EXCLUDED.since", (file, as_date(day)))
        self.set_location(file, "watch")

    # -- partages, sélections du jour -----------------------------------

    def shared_files(self) -> set[str]:
        return {r[0] for r in self._all("SELECT file FROM knowledge.triage_shared")}

    def add_share(self, file: str, url: str, post_date, found) -> None:
        self._run("INSERT INTO knowledge.triage_shared (file, url, post_date, found) VALUES (%s, %s, %s, %s)",
                  (file, url, as_date(post_date), as_date(found)))

    def share_total(self) -> int:
        return self._one("SELECT count(*) FROM knowledge.triage_shared")[0]

    def shared_found_since(self, since: dt.date) -> list[tuple[str, dt.date]]:
        return [(r[0], r[1]) for r in self._all(
            "SELECT file, found FROM knowledge.triage_shared WHERE found >= %s ORDER BY file", (as_date(since),))]

    def picked_on_or_before(self, file: str, day: dt.date) -> bool:
        return self._one("SELECT 1 FROM knowledge.triage_daily_picks WHERE file = %s AND day <= %s", (file, as_date(day))) is not None

    def add_picks(self, day, files) -> None:
        for file in files:
            self._run("INSERT INTO knowledge.triage_daily_picks (day, file) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                      (as_date(day), file))

    def pick_days(self) -> list[tuple[dt.date, str]]:
        return [(r[0], r[1]) for r in self._all("SELECT day, file FROM knowledge.triage_daily_picks ORDER BY day, file")]

    # -- notes en ombre --------------------------------------------------

    def put_shadow(self, **row) -> None:
        values = normalize_shadow(row)
        columns = list(SHADOW_COLUMNS)
        args = [values[c] for c in columns]
        args[columns.index("criteria")] = as_json(values["criteria"])
        placeholders = ", ".join("%s::jsonb" if c == "criteria" else "%s" for c in columns)
        updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in columns if c not in ("url", "language"))
        self._run(f"INSERT INTO knowledge.triage_shadow_scores ({', '.join(columns)}) VALUES ({placeholders}) "
                  f"ON CONFLICT (url, language) DO UPDATE SET {updates}", args)

    def shadow_rows(self) -> list[dict]:
        rows = self._all(f"SELECT {', '.join(SHADOW_COLUMNS)} FROM knowledge.triage_shadow_scores ORDER BY url, language")
        return [{**dict(zip(SHADOW_COLUMNS, r)), "scored_at": local(r[-1])} for r in rows]

    def shadow_candidates(self, language: str, current_hash: str) -> list[dict]:
        """Articles notés en français (grille remplie, article complet) sans note en ombre pour `language` ou avec une autre
        empreinte de prompts, par nom de fichier : file, location, title."""
        rows = self._all(
            "SELECT s.file, s.location, s.title FROM knowledge.triage_scores s LEFT JOIN knowledge.triage_shadow_scores h "
            "ON h.url = COALESCE(NULLIF(s.url, ''), s.file) AND h.language = %s "
            "WHERE s.criteria IS NOT NULL AND s.complete AND (h.url IS NULL OR h.prompts_hash IS DISTINCT FROM %s) ORDER BY s.file",
            (language, current_hash))
        return [{"file": r[0], "location": r[1], "title": r[2]} for r in rows]

    def shadow_pairs(self, language: str) -> list[dict]:
        """Articles notés dans les deux langues : file, title, source, fr et en (substance, criteria, flags), par fichier."""
        rows = self._all(
            "SELECT s.file, s.title, s.source, s.criteria, s.substance, s.is_compilation, s.in_themes, s.is_promo, "
            "h.criteria, h.substance, h.is_compilation, h.in_themes, h.is_promo "
            "FROM knowledge.triage_scores s JOIN knowledge.triage_shadow_scores h "
            "ON h.url = COALESCE(NULLIF(s.url, ''), s.file) AND h.language = %s "
            "WHERE s.criteria IS NOT NULL AND h.criteria IS NOT NULL ORDER BY s.file", (language,))
        return [{"file": r[0], "title": r[1], "source": r[2],
                 "fr": {"criteria": r[3], "substance": r[4], "is_compilation": r[5], "in_themes": r[6], "is_promo": r[7]},
                 "en": {"criteria": r[8], "substance": r[9], "is_compilation": r[10], "in_themes": r[11], "is_promo": r[12]}}
                for r in rows]

    # -- calibration -----------------------------------------------------

    def refresh_calibration(self, entries: list[dict], exported_at) -> None:
        """Met à jour les valeurs exportées de chaque article (une ligne par article) ; les avis déjà saisis sont gardés, y compris
        pour un article qui n'est plus noté (sa ligne garde ses dernières valeurs)."""
        moment = as_moment(exported_at)
        for e in entries:
            self._run(
                "INSERT INTO knowledge.triage_calibration (file, exported_at, verdict, relevance, substance, in_themes, "
                "is_compilation, is_promo, missing) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (file) DO UPDATE SET exported_at = EXCLUDED.exported_at, verdict = EXCLUDED.verdict, "
                "relevance = EXCLUDED.relevance, substance = EXCLUDED.substance, in_themes = EXCLUDED.in_themes, "
                "is_compilation = EXCLUDED.is_compilation, is_promo = EXCLUDED.is_promo, missing = EXCLUDED.missing",
                (e["file"], moment, e["verdict"], e.get("relevance"), e.get("substance"), e.get("in_themes"),
                 e.get("is_compilation"), e.get("is_promo"), e.get("missing")))

    def apply_opinions(self, opinions: dict[str, bool | None], when=None) -> dict[str, int]:
        """Enregistre des avis (True garder, False écarter, None effacer l'avis existant) ; un fichier absent de la table est compté
        et ignoré."""
        moment = as_moment(when) or dt.datetime.now().astimezone()
        counts = {"keep": 0, "discard": 0, "cleared": 0, "unknown": 0}
        for file, keep in opinions.items():
            if self._one("SELECT 1 FROM knowledge.triage_calibration WHERE file = %s", (file,)) is None:
                counts["unknown"] += 1
                continue
            if keep is None:      # une cellule vide n'efface que l'avis qui existait
                cursor = self._run("UPDATE knowledge.triage_calibration SET opinion = NULL, opinion_at = NULL "
                                   "WHERE file = %s AND opinion IS NOT NULL", (file,))
                counts["cleared"] += cursor.rowcount
            else:
                self._run("UPDATE knowledge.triage_calibration SET opinion = %s, opinion_at = %s WHERE file = %s",
                          ("keep" if keep else "discard", moment, file))
                counts["keep" if keep else "discard"] += 1
        return counts

    def calibration_entries(self) -> list[dict]:
        """Toutes les lignes de calibration, par fichier, avec le titre de la note s'il y en a une (sinon le nom du fichier)."""
        rows = self._all(
            "SELECT c.file, COALESCE(s.title, c.file), c.exported_at, c.verdict, c.relevance, c.substance, c.in_themes, "
            "c.is_compilation, c.is_promo, c.missing, c.opinion, c.opinion_at "
            "FROM knowledge.triage_calibration c LEFT JOIN knowledge.triage_scores s ON s.file = c.file ORDER BY c.file")
        return [{"file": r[0], "title": r[1], "exported_at": local(r[2]), "verdict": r[3], "relevance": r[4], "substance": r[5],
                 "in_themes": r[6], "is_compilation": r[7], "is_promo": r[8], "missing": r[9], "opinion": r[10],
                 "opinion_at": local(r[11])} for r in rows]

    def calibration_opinions(self) -> dict[str, bool]:
        return {r[0]: OPINION_OF[r[1]] for r in self._all(
            "SELECT file, opinion FROM knowledge.triage_calibration WHERE opinion IS NOT NULL ORDER BY file")}
