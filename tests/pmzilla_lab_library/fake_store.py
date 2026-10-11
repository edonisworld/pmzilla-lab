"""Faux magasin en mémoire de l'indexeur (tools/pmzilla_lab_library.py), pour les tests sans base (design.md D1 de db-direct-indexing).

Même interface que `pmzilla_lab_library.KnowledgeStore` : ouverture, verrou, lecture des livres stockés, remplacement d'un livre en
une « transaction » (tout ou rien), mise à jour sans recalcul, suppression, collections orphelines, renommage, comptes. Il ne crée
aucun fichier. `export_sqlite` recopie son contenu dans un index SQLite (library.DB_PATH du test) pour les seuls tests de la voie de
lecture SQLite (`Library`, conservée jusqu'au change R-27) : l'indexeur, lui, n'écrit jamais de fichier SQLite.
"""
import json
import time

import pmzilla_lab_library as library


class FakeStore:
    def __init__(self, dimensions: int = 128, available: bool = True, locked: bool = False):
        self.dimensions = dimensions
        self.available = available      # False : la base ne répond pas
        self.locked = locked            # True : une autre indexation tient le verrou
        self.books: dict[str, dict] = {}
        self.collections: set[str] = set()
        self.fail_on: set[str] = set()  # fichiers dont l'écriture échoue (la transaction est annulée)
        self.writes: list[tuple] = []   # ordres d'écriture reçus, dans l'ordre
        self.opened = self.closed = 0

    # -- connexion et verrou -------------------------------------------------

    def open(self) -> None:
        if not self.available:
            raise library.StoreUnavailable("OperationalError")
        self.opened += 1

    def try_lock(self) -> bool:
        return not self.locked

    def close(self) -> None:
        self.closed += 1

    # -- lectures --------------------------------------------------------------

    def stored_books(self) -> dict:
        return {name: library.StoredBook(name, b["sha256"], b["model"], b["title"], json.loads(json.dumps(b["meta"])),
                                         frozenset(b["collections"]))
                for name, b in self.books.items()}

    def passage_count(self) -> int:
        return sum(len(b["passages"]) for b in self.books.values())

    def passage_counts(self) -> dict[str, int]:
        return {name: len(b["passages"]) for name, b in self.books.items()}

    def counts(self) -> tuple[int, int, int, int]:
        figures = sum(p["kind"] == "figure" for b in self.books.values() for p in b["passages"])
        return len(self.books), self.passage_count(), figures, len(self.collections)

    # -- écritures (chacune tout ou rien) --------------------------------------

    def replace_book(self, record, rows) -> None:
        if record.file_name in self.fail_on:
            raise RuntimeError("écriture refusée")      # rien n'a changé : la transaction est annulée
        passages = [{"position": r.position, "section": r.section, "text": r.text, "kind": r.kind, "ref": dict(r.ref),
                     "vector": r.vector.copy()} for r in rows]
        self.books[record.file_name] = {"title": record.title, "meta": dict(record.meta), "sha256": record.sha256,
                                        "model": record.model, "collections": set(record.collections),
                                        "indexed_at": time.time(), "passages": passages}
        self.collections |= set(record.collections)
        self.writes.append(("replace", record.file_name))

    def update_book(self, file_name: str, title: str, meta: dict, collections) -> None:
        book = self.books[file_name]
        book.update(title=title, meta=dict(meta), collections=set(collections))
        self.collections |= set(collections)
        self.writes.append(("update", file_name))

    def delete_book(self, file_name: str) -> None:
        self.books.pop(file_name, None)
        self.writes.append(("delete", file_name))

    def delete_orphan_collections(self) -> list[str]:
        used = set().union(*(b["collections"] for b in self.books.values())) if self.books else set()
        orphans = sorted(self.collections - used)
        self.collections -= set(orphans)
        if orphans:
            self.writes.append(("orphans", tuple(orphans)))
        return orphans

    def set_collections(self, changes: dict) -> None:
        for file_name, names in changes.items():
            self.books[file_name]["collections"] = set(names)
            self.collections |= set(names)
        self.delete_orphan_collections()
        self.writes.append(("collections", tuple(sorted(changes))))


def export_sqlite(store: FakeStore) -> None:
    """Recopie le faux magasin dans l'index SQLite du test (library.DB_PATH, patché vers un dossier temporaire), pour les tests de
    la voie de lecture `Library`. Le genre « text » redevient « texte », comme dans l'index SQLite."""
    db = library.connect()
    with db:
        db.execute("DELETE FROM books")
        for name, book in sorted(store.books.items()):
            cursor = db.execute(
                "INSERT INTO books (file_name, title, sha256, collections, model, indexed_at, meta) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (name, book["title"], book["sha256"], "|".join(sorted(book["collections"])), book["model"], book["indexed_at"],
                 json.dumps(book["meta"], ensure_ascii=False, sort_keys=True)))
            db.executemany(
                "INSERT INTO chunks (book_id, position, section, text, embedding, kind, ref) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [(cursor.lastrowid, p["position"], p["section"], p["text"], p["vector"].tobytes(),
                  "texte" if p["kind"] == "text" else p["kind"], json.dumps(p["ref"], ensure_ascii=False, sort_keys=True))
                 for p in book["passages"]])
    db.close()
