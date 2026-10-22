"""
PMZilla Lab : la bibliothèque lue dans PostgreSQL (schéma knowledge), seule voie de lecture du serveur MCP.

`PostgresLibrary` porte l'interface que les quatre outils MCP appellent : `search`, `read`, `collections`, `books`, `check_types`,
`refresh`. Les formes de réponse sont figées par les tests sur la bibliothèque inventée (tests/fixtures_library/demo_expected.py).

Connexion : `db.connect(role="pmzilla_knowledge_ro")` (lecture seule ; mot de passe lu dans le Trousseau, service
pmzilla-lab-db-pmzilla_knowledge_ro, ou dans PMZILLA_LAB_DB_PASSWORD_PMZILLA_KNOWLEDGE_RO ; jamais affiché), sur la base de
l'installation, ou sur celle que nomme PMZILLA_LAB_KNOWLEDGE_DBNAME (la même variable que l'indexeur ; base jetable du jeu d'essai,
tests). Si la base ne répond pas, le serveur s'arrête avec le message de db.py suivi du remède : il n'y a aucune voie de repli, ni vers
un fichier, ni d'une base nommée vers celle de l'installation. La question est transformée en vecteur par `pmzilla_lab_library.embed`
(bge-m3 par Ollama) ; la recherche elle-même est celle de hybrid_search.py.
"""
from __future__ import annotations

import datetime as dt
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hybrid_search  # noqa: E402
import pmzilla_lab_library as library  # noqa: E402  (embed, KINDS, constantes)
import private_collections  # noqa: E402  (organisation-context, D3 : les collections cherchées seulement quand on les nomme)

# Champs d'une note de contexte rendus avec chaque passage (D5) : la date de la note, sa nature, sa date de revue (+ « source », déjà dans
# les métadonnées) et la marque « stale » calculée à l'appel. Jamais d'auteur ni d'URL.
CONTEXT_FIELDS = ("note_date", "nature", "source", "review_date", "stale")
PARIS = "Europe/Paris"

PG_KINDS = library.STORE_KINDS          # « texte » est stocké « text » ; une seule définition, celle de l'indexeur
STORE_NAMES = library.KIND_NAMES        # et retour : « text » est rendu « texte »
NAMES_SQL = ("ARRAY(SELECT co.name FROM knowledge.book_collections bc JOIN knowledge.collections co ON co.id = bc.collection_id "
             "WHERE bc.book_id = b.id)")


DBNAME_VARIABLE = "PMZILLA_LAB_KNOWLEDGE_DBNAME"     # base à lire à la place de celle de l'installation (jeu d'essai, tests)


NO_FALLBACK = ("The library is served from PostgreSQL only, with no fallback: start the database with bash tools/db_up.sh, "
               "then restart the session.")


def default_connect():
    import db
    try:
        return db.connect(role="pmzilla_knowledge_ro", dbname=os.environ.get(DBNAME_VARIABLE) or None)
    except db.ErreurBase as error:
        raise SystemExit(f"{error} {NO_FALLBACK}") from None


class PostgresLibrary:
    def __init__(self, connect=None, embed=None, scan: str = hybrid_search.DEFAULT_SCAN, fulltext: str = "bm25", today: dt.date | None = None,
                 rank_norm: int | None = None, spec: hybrid_search.HybridSpec = hybrid_search.LIBRARY_SPEC,
                 ef_search: int = hybrid_search.EF_SEARCH) -> None:
        self._connect = connect or default_connect
        self._embed = embed
        self.scan, self.fulltext, self.today, self.spec = scan, fulltext, today, spec
        self.rank_norm, self.ef_search = rank_norm, ef_search
        self._conn = None
        self.connection()      # échoue tout de suite, avec un message clair, si la base ne répond pas

    # -- connexion -----------------------------------------------------------

    def connection(self):
        if self._conn is None or getattr(self._conn, "closed", False):
            self._conn = self._connect()
        return self._conn

    def _query(self, sql: str, params=()):
        """Une lecture ; une seule reprise si la connexion est tombée."""
        for attempt in (1, 2):
            conn = self.connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute(sql, params)
                    return cursor.fetchall()
            except Exception as error:
                if attempt == 2 or type(error).__name__ != "OperationalError":      # connexion perdue : une reprise
                    raise
                self._conn = None
            finally:
                try:
                    conn.rollback()
                except Exception:
                    pass
        return []

    # -- interface de la bibliothèque ------------------------------------------

    @staticmethod
    def check_types(types):
        return library.check_types(types)

    def refresh(self) -> None:
        """La base est toujours à jour : rien à recharger."""

    def _embedding(self, query: str):
        return (self._embed or library.embed)([query])[0]

    def search(self, query: str, collections: list[str] | None, limit: int, since: str | None = None,
               types: list[str] | None = None, component: str = "hybrid") -> list[dict]:
        kinds = self.check_types(types)
        wanted = None
        if collections:
            wanted = sorted(set(collections))
        pg_kinds = None if set(kinds) == set(library.KINDS) else [PG_KINDS[k] for k in kinds]
        # D5 : sans collection nommée, les collections privées restent hors de la recherche
        excluded = None if wanted else sorted(private_collections.PRIVATE_COLLECTIONS)
        vector = self._embedding(query)
        for attempt in (1, 2):
            try:
                found = hybrid_search.hybrid_search(
                    self.connection(), self.spec, query=query, vector=vector, limit=limit, collections=wanted,
                    since=since, kinds=pg_kinds, today=self.today, scan=self.scan, fulltext=self.fulltext,
                    rank_norm=self.rank_norm, component=component, ef_search=self.ef_search, exclude_collections=excluded)
                break
            except Exception as error:
                if attempt == 2 or type(error).__name__ != "OperationalError":      # connexion perdue : une seule reprise
                    raise
                self._conn = None
        described = self._describe_many([chunk_id for chunk_id, _ in found])
        return [self._mark_stale(self._shape(described[chunk_id], score=round(score, 4))) for chunk_id, score in found]

    def _paris_today(self) -> dt.date:
        """La date du jour à Paris, calculée à l'appel ; `today` (injectable) la remplace dans les tests."""
        if self.today is not None:
            return self.today
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo(PARIS)).date()

    def _mark_stale(self, shaped: dict) -> dict:
        """Une note de contexte (elle porte une date de revue) reçoit `stale` : vrai quand la revue est antérieure à aujourd'hui (Paris),
        ou quand la date est illisible. Les autres passages ne changent pas."""
        review = shaped.get("review_date")
        if review:
            try:
                shaped["stale"] = dt.date.fromisoformat(str(review)[:10]) < self._paris_today()
            except ValueError:
                shaped["stale"] = True
        return shaped

    def read(self, passage_id: int, before: int, after: int) -> dict:
        rows = self._query("SELECT book_id, position FROM knowledge.chunks WHERE id = %s", (passage_id,))
        if not rows:
            return {"error": f"Unknown passage_id {passage_id}. Use an id returned by search_library."}
        book_id, position = rows[0]
        ids = [row[0] for row in self._query(
            "SELECT id FROM knowledge.chunks WHERE book_id = %s AND position BETWEEN %s AND %s ORDER BY position, id",
            (book_id, position - before, position + after))]
        described = self._describe_many(ids)
        passages = [self._mark_stale(self._shape(described[i])) for i in ids]
        context = "review_date" in passages[0]          # une note de contexte : ses champs d'en-tête, sans auteur ni URL
        return {
            "book": passages[0]["book"],
            **{k: passages[0][k] for k in library.META_FIELDS + (CONTEXT_FIELDS if context else ()) if k in passages[0]},
            "file": passages[0]["file"],
            "passages": [{k: p[k] for k in ("passage_id", "kind", "section", "position", "ref", "text")
                          + (CONTEXT_FIELDS if context else ()) if k in p} for p in passages],
        }

    def collections(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for (names,) in self._query(f"SELECT {NAMES_SQL} FROM knowledge.books b"):
            for name in set(names):      # un livre compte une fois par nom
                counts[name] = counts.get(name, 0) + 1
        return dict(sorted(counts.items()))

    def books(self, collection: str | None) -> list[dict]:
        rows = self._query(
            f"SELECT b.title, b.file_name, {NAMES_SQL}, count(c.id), count(c.id) FILTER (WHERE c.kind = 'figure') "
            "FROM knowledge.books b LEFT JOIN knowledge.chunks c ON c.book_id = b.id "
            "GROUP BY b.id ORDER BY b.title COLLATE \"C\"")
        return [
            {"book": title, "file": file_name, "collections": sorted(set(names)),
             "passages": passages, "figures": figures}
            for title, file_name, names, passages, figures in rows
            if not collection or collection in set(names)
        ]

    # -- aides ----------------------------------------------------------------

    def _describe_many(self, chunk_ids: list[int]) -> dict[int, dict]:
        if not chunk_ids:
            return {}
        rows = self._query(
            f"SELECT c.id, c.position, c.section, c.text, c.kind, c.ref, b.title, b.file_name, b.meta, {NAMES_SQL} "
            "FROM knowledge.chunks c JOIN knowledge.books b ON b.id = c.book_id WHERE c.id = ANY(%s)", (list(chunk_ids),))
        return {row[0]: {"id": row[0], "position": row[1], "section": row[2], "text": row[3], "kind": row[4], "ref": row[5],
                         "title": row[6], "file": row[7], "meta": row[8] or {}, "names": row[9]} for row in rows}

    @staticmethod
    def _shape(row: dict, **extra) -> dict:
        """Le dictionnaire d'un passage décrit (clés et ordre figés par les tests)."""
        kind = STORE_NAMES.get(row["kind"], row["kind"])
        described = {
            "passage_id": row["id"],
            "book": row["title"],
            **row["meta"],      # url, author, published, source
            "file": row["file"],
            "section": row["section"],
            "position": row["position"],
            "collections": sorted(set(row["names"])),
            "kind": kind,
            **extra,
            "text": row["text"],
        }
        if kind == "figure":
            described["ref"] = row["ref"] or {}
        return described
