"""Lecteur de la liste des livres sur une base jetable chargée avec la bibliothèque inventée (pg_demo) : tâche 3.1, classe base.

    bash tools/dbtest.sh book_usage

Sautée sans base. Le lecteur réel (`fetch_books`) lit sous le rôle pmzilla_knowledge_ro ; aucune base réelle n'est jointe.
"""
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tests" / "library_backend"))
import pg_demo                  # noqa: E402  (ajoute tools/, tests/db et tests/fixtures_library au chemin)
import book_usage               # noqa: E402
import watch_paths              # noqa: E402


class ListeDesLivresSurBaseJetable(unittest.TestCase):
    def setUp(self):
        self.base = pg_demo.ThrowawayDatabase(self)      # saute le test sans base

    def test_lecteur_ne_garde_que_les_livres(self):
        livres = book_usage.fetch_books(connect=self.base.connect)
        attendus = {name for name, (title, coll, meta) in pg_demo.demo.BOOKS.items()
                    if not {"watch", "veille", watch_paths.OWN_COLLECTION} & set(coll.split("|"))}
        self.assertEqual({l["file"] for l in livres}, attendus)
        titres = {name: title for name, (title, coll, meta) in pg_demo.demo.BOOKS.items()}
        for livre in livres:
            self.assertEqual(livre["title"], titres[livre["file"]])
            self.assertTrue(livre["collections"])

    def test_le_role_de_lecture_ne_peut_pas_ecrire(self):
        conn = self.base.connect()
        with self.assertRaises(Exception):
            conn.execute("DELETE FROM knowledge.books")
        conn.rollback()


if __name__ == "__main__":
    unittest.main()
