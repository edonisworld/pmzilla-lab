"""
PMZilla Lab : la bibliothèque lue dans PostgreSQL (schéma knowledge, lot 4 de la base).

`PostgresLibrary` a la même interface publique que `pmzilla_lab_library.Library` (voie SQLite) : `search`, `read`, `collections`,
`books`, `check_types`, `refresh`, et les mêmes formes de réponse, pour que les quatre outils MCP restent
inchangés. Choisie par `serve --backend postgres` (ou PMZILLA_LAB_BACKEND=postgres) ; la voie SQLite reste la voie par défaut.

Connexion : `db.connect(role="pmzilla_knowledge_ro")` (lecture seule ; mot de passe lu dans le Trousseau, service
pmzilla-lab-db-pmzilla_knowledge_ro, ou dans PMZILLA_LAB_DB_PASSWORD_PMZILLA_KNOWLEDGE_RO ; jamais affiché). Si la base ne répond
pas, le serveur s'arrête avec un message clair : il ne bascule jamais en silence sur SQLite (c'est un choix explicite de
l'utilisateur : `--backend sqlite`). La question est transformée en vecteur par la même fonction que la voie SQLite
(`pmzilla_lab_library.embed`, bge-m3 par Ollama) ; la recherche elle-même est celle de hybrid_search.py.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hybrid_search  # noqa: E402
import pmzilla_lab_library as library  # noqa: E402  (embed, KINDS, constantes)

PG_KINDS = {"texte": "text", "figure": "figure"}
SQLITE_KINDS = {value: key for key, value in PG_KINDS.items()}
NAMES_SQL = ("ARRAY(SELECT co.name FROM knowledge.book_collections bc JOIN knowledge.collections co ON co.id = bc.collection_id "
             "WHERE bc.book_id = b.id)")


def default_connect():
    import db
    try:
        return db.connect(role="pmzilla_knowledge_ro")
    except db.ErreurBase as error:
        raise SystemExit(f"{error} Pour utiliser l'ancienne voie : --backend sqlite.") from None


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

    # -- interface de Library ------------------------------------------------

    @staticmethod
    def check_types(types):
        return library.Library.check_types(types)

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
        found = hybrid_search.hybrid_search(
            self.connection(), self.spec, query=query, vector=self._embedding(query), limit=limit, collections=wanted,
            since=since, kinds=pg_kinds, today=self.today, scan=self.scan, fulltext=self.fulltext,
            rank_norm=self.rank_norm, component=component, ef_search=self.ef_search)
        described = self._describe_many([chunk_id for chunk_id, _ in found])
        return [self._shape(described[chunk_id], score=round(score, 4)) for chunk_id, score in found]

    def read(self, passage_id: int, before: int, after: int) -> dict:
        rows = self._query("SELECT book_id, position FROM knowledge.chunks WHERE id = %s", (passage_id,))
        if not rows:
            return {"error": f"Unknown passage_id {passage_id}. Use an id returned by search_library."}
        book_id, position = rows[0]
        ids = [row[0] for row in self._query(
            "SELECT id FROM knowledge.chunks WHERE book_id = %s AND position BETWEEN %s AND %s ORDER BY position, id",
            (book_id, position - before, position + after))]
        described = self._describe_many(ids)
        passages = [self._shape(described[i]) for i in ids]
        return {
            "book": passages[0]["book"],
            **{k: passages[0][k] for k in library.META_FIELDS if k in passages[0]},
            "file": passages[0]["file"],
            "passages": [{k: p[k] for k in ("passage_id", "kind", "section", "position", "ref", "text") if k in p}
                         for p in passages],
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
        """Même dictionnaire que `Library._describe` (mêmes clés, même ordre)."""
        kind = SQLITE_KINDS.get(row["kind"], row["kind"])
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
