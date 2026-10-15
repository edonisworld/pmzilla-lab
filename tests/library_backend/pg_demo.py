"""Aides de test : base PostgreSQL jetable chargée avec la bibliothèque inventée (tests/fixtures_library/demo_library.py).

Le chargement se fait par de simples INSERT : c'est le constructeur de la bibliothèque inventée dans une base jetable (comptes attendus :
`demo.expected_counts()`). `add_book` ajoute un livre de plus (corpus d'un test). Rien n'est lu ni écrit dans les schémas réels : la base
est créée sous le nom pmzilla_test_<hex> et supprimée dans tous les cas.
"""
import contextlib
import json
import secrets
import sys
from pathlib import Path

import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
sys.path.insert(0, str(RACINE / "tests" / "db"))
sys.path.insert(0, str(RACINE / "tests" / "fixtures_library"))
import test_db as base          # noqa: E402  (connexion, base jetable, mot de passe)
from test_db import db          # noqa: E402
import demo_library as demo     # noqa: E402

KIND = {"texte": "text", "figure": "figure"}


def literal(angle: float) -> str:
    vector = np.frombuffer(demo.chunk_blob(angle), dtype=np.float16).astype(np.float32)
    return "[" + ",".join(f"{float(x):.8g}" for x in vector) + "]"


def literal_of(vector) -> str:
    """Littéral halfvec d'un vecteur numpy (valeurs float16 exactes)."""
    return "[" + ",".join(f"{float(x):.8g}" for x in vector.astype(np.float16).astype(np.float32)) + "]"


class ThrowawayDatabase:
    """Base jetable migrée et chargée. `connect()` rend une connexion qui lit sous le rôle pmzilla_knowledge_ro."""

    def __init__(self, testcase):
        if not base.BASE_DISPONIBLE:
            testcase.skipTest(base.MESSAGE_SAUT)
        self.name = "pmzilla_test_" + secrets.token_hex(6)
        self.admin = db.connect(base.URL_BASE, password=base.MOT_DE_PASSE, autocommit=True)
        testcase.addCleanup(self.drop)
        self.admin.execute(f'CREATE DATABASE "{self.name}"')
        self.url = base.url_vers(self.name)
        self.opened = []
        conn = self._raw()
        db.migrer(conn, db.lister_migrations(db.DOSSIER_MIGRATIONS))
        conn.commit()
        self.load(conn)

    def _raw(self):
        conn = db.connect(self.url, password=base.MOT_DE_PASSE)
        self.opened.append(conn)
        return conn

    def connect(self):
        conn = self._raw()
        conn.execute("SET ROLE pmzilla_knowledge_ro")
        conn.commit()       # le SET ROLE survit aux rollback que fait la recherche après chaque lecture
        return conn

    def load(self, conn):
        conn.execute("SET ROLE pmzilla_knowledge")
        collection_ids, book_ids = {}, {}
        for title, collections, meta in demo.BOOKS.values():
            for name in collections.split("|"):
                if name not in collection_ids:
                    collection_ids[name] = conn.execute("INSERT INTO knowledge.collections (name) VALUES (%s) RETURNING id", (name,)).fetchone()[0]
        for file_name, (title, collections, meta) in demo.BOOKS.items():
            book_id = conn.execute(
                "INSERT INTO knowledge.books (file_name, title, meta, sha256, model, indexed_at) VALUES (%s, %s, %s::jsonb, %s, %s, now()) RETURNING id",
                (file_name, title, json.dumps(meta), "sha-" + file_name, demo.MODEL)).fetchone()[0]
            book_ids[file_name] = book_id
            for name in collections.split("|"):
                conn.execute("INSERT INTO knowledge.book_collections VALUES (%s, %s)", (book_id, collection_ids[name]))
        for file_name, position, section, text, angle, kind, ref in demo.CHUNKS:
            conn.execute("INSERT INTO knowledge.chunks (book_id, position, section, text, embedding, kind, ref) "
                         "VALUES (%s, %s, %s, %s, %s::halfvec, %s, %s::jsonb)",
                         (book_ids[file_name], position, section, text, literal(angle), KIND[kind], json.dumps(ref)))
        conn.execute("RESET ROLE")
        conn.commit()

    def add_book(self, file_name: str, passages, collection: str = "produit") -> None:
        """Ajoute un livre sans métadonnées à une collection existante. `passages` : [(position, texte, vecteur numpy de 1024 valeurs)]."""
        conn = self._raw()
        conn.execute("SET ROLE pmzilla_knowledge")
        collection_id = conn.execute("SELECT id FROM knowledge.collections WHERE name = %s", (collection,)).fetchone()[0]
        book_id = conn.execute(
            "INSERT INTO knowledge.books (file_name, title, meta, sha256, model, indexed_at) VALUES (%s, %s, '{}'::jsonb, 'x', %s, now()) RETURNING id",
            (file_name, file_name, demo.MODEL)).fetchone()[0]
        conn.execute("INSERT INTO knowledge.book_collections VALUES (%s, %s)", (book_id, collection_id))
        for position, texte, vecteur in passages:
            conn.execute("INSERT INTO knowledge.chunks (book_id, position, section, text, embedding) VALUES (%s, %s, 'Début', %s, %s::halfvec)",
                         (book_id, position, texte, literal_of(vecteur)))
        conn.execute("RESET ROLE")
        conn.commit()

    def drop(self):
        for conn in self.opened:
            with contextlib.suppress(Exception):
                conn.close()
        with contextlib.suppress(Exception):
            self.admin.execute(f'DROP DATABASE IF EXISTS "{self.name}" WITH (FORCE)')
        self.admin.close()
